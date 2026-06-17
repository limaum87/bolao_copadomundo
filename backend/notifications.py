"""Web Push (notificações push no celular/navegador).

Fluxo:
  1. O navegador pede permissão e se inscreve (PushManager) com a chave
     pública VAPID.
  2. A inscrição (endpoint + chaves) é salva no banco atrelada ao
     participant_uid do usuário (ver app.py → /push/subscribe).
  3. Para enviar, assinamos a mensagem com a chave privada VAPID e
     entregamos ao serviço de push do navegador (FCM/Apple/Mozilla).

Variáveis de ambiente (gere com `python -m backend.generate_vapid`):
  VAPID_PUBLIC_KEY   — base64url da chave pública (vai pro navegador)
  VAPID_PRIVATE_KEY  — PEM da chave privada (fica só no servidor)
  VAPID_SUBJECT      — contato (mailto:...) exigido pelo protocolo

Se VAPID não estiver configurado, tudo funciona em modo degradado:
inscrições continuam sendo salvas, mas o envio é ignorado.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta

_log = logging.getLogger("bolao.push")


# ---------------------------------------------------------------------------
# Configuração VAPID
# ---------------------------------------------------------------------------
def get_vapid_public_key() -> str | None:
    return os.environ.get("VAPID_PUBLIC_KEY")


def is_push_enabled() -> bool:
    return bool(os.environ.get("VAPID_PUBLIC_KEY") and os.environ.get("VAPID_PRIVATE_KEY"))


def _vapid_claims() -> dict:
    return {"sub": os.environ.get("VAPID_SUBJECT", "mailto:admin@bolao.local")}


def _normalize_vapid_private_key(raw: str) -> str:
    """O py_vapid (usado pelo pywebpush) espera a chave privada como base64url
    do DER (uma linha, sem cabeçalhos). Aceitamos também PEM (com quebras reais
    ou com '\\n' literais, como em arquivos .env) e convertemos para esse formato.
    """
    raw = raw.strip()
    if "-----BEGIN" not in raw:
        return raw  # já está em base64url (DER ou raw) — formato preferido
    import base64 as _b64
    from cryptography.hazmat.primitives import serialization
    pem = raw.replace("\\n", "\n")
    key_obj = serialization.load_pem_private_key(pem.encode("ascii"), password=None)
    der = key_obj.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return _b64.urlsafe_b64encode(der).rstrip(b"=").decode("ascii")


def _payload(title: str, body: str, url: str = "/", tag: str | None = None) -> dict:
    return {
        "title": title,
        "body": body,
        "url": url,
        "tag": tag,
        "icon": "/assets/img/notif-icon-192.png",
        "badge": "/assets/img/notif-badge-96.png",
    }


def _sub_to_dict(row) -> dict:
    return {
        "endpoint": row.endpoint,
        "keys": {"p256dh": row.p256dh, "auth": row.auth_key},
    }


# ---------------------------------------------------------------------------
# Envio propriamente dito (puro HTTP, sem tocar no banco)
# ---------------------------------------------------------------------------
def send_push(subscription: dict, payload: dict) -> str:
    """Envia uma push.

    Retorna:
      "ok"      — entregue ao serviço de push
      "expired" — inscrição inválida/expirada (404/410) → remover do banco
      "failed"  — erro transitório ou VAPID ausente
    """
    if not is_push_enabled():
        _log.debug("VAPID não configurado; push não enviado.")
        return "failed"

    try:
        from pywebpush import WebPushException, webpush

        private_key = _normalize_vapid_private_key(os.environ["VAPID_PRIVATE_KEY"])

        webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=private_key,
            vapid_claims=_vapid_claims(),
            ttl=86400,
        )
        return "ok"
    except WebPushException as ex:  # noqa: BLE001
        status = None
        resp = getattr(ex, "response", None)
        if resp is not None:
            status = getattr(resp, "status_code", None)
        if status in (404, 410):
            _log.info("Inscrição expirada/inválida (status=%s): %s", status, subscription.get("endpoint"))
            return "expired"
        _log.warning("Push falhou (status=%s): %s", status, ex)
        return "failed"
    except Exception as ex:  # noqa: BLE001
        _log.error("Erro inesperado no push: %s", ex)
        return "failed"


# ---------------------------------------------------------------------------
# Broadcast (envio para muitos) — usa a SESSÃO passada (sem session_scope aninhado)
# ---------------------------------------------------------------------------
def broadcast_to_all(session, title: str, body: str, url: str = "/", tag: str | None = None):
    """Envia para TODOS os inscritos.

    Se `tag` for informado, registra em NotificationLog para não reenviar
    (idempotência). Limpa inscrições expiradas. Usa a sessão passada para
    leitura/log (o commit é responsabilidade do chamador).

    Retorna (sent, total).
    """
    from .models import NotificationLog, PushSubscription

    if tag:
        if session.query(NotificationLog).filter_by(log_key=tag).first():
            return 0, 0

    rows = session.query(PushSubscription).all()
    if not rows:
        return 0, 0

    payload = _payload(title, body, url=url, tag=tag)
    sent = 0
    for row in rows:
        status = send_push(_sub_to_dict(row), payload)
        if status == "ok":
            sent += 1
        elif status == "expired":
            session.delete(row)

    if tag:
        session.add(NotificationLog(log_key=tag))
    return sent, len(rows)


def notify_uid(session, uid: str, title: str, body: str, url: str = "/", tag: str | None = None):
    """Envia para um único participante (todos os dispositivos dele).

    Retorna (sent, total).
    """
    from .models import NotificationLog, PushSubscription

    if tag:
        if session.query(NotificationLog).filter_by(log_key=tag).first():
            return 0, 0

    rows = session.query(PushSubscription).filter_by(participant_uid=uid).all()
    if not rows:
        return 0, 0

    payload = _payload(title, body, url=url, tag=tag)
    sent = 0
    for row in rows:
        status = send_push(_sub_to_dict(row), payload)
        if status == "ok":
            sent += 1
        elif status == "expired":
            session.delete(row)

    if tag:
        session.add(NotificationLog(log_key=tag))
    return sent, len(rows)


# ---------------------------------------------------------------------------
# Schedulers (entry points — abrem a própria sessão)
# ---------------------------------------------------------------------------
def dispatch_pregame_reminders() -> dict:
    """Lembretes de palpite: para jogos que começam em até N minutos, avisa
    os inscritos que ainda não palpitarão esse jogo. Idempotente por jogo+uid.

    Janela configurável: BOLAO_REMINDER_WINDOW_MIN (default 120).
    """
    from .database import session_scope
    from .models import (Game, NotificationLog, Participant, Prediction,
                         PushSubscription)

    if not is_push_enabled():
        return {"sent": 0, "reason": "push_disabled"}

    window_min = int(os.environ.get("BOLAO_REMINDER_WINDOW_MIN", "120"))
    now = datetime.now()
    horizon = now + timedelta(minutes=window_min)

    # Coleta o plano DENTRO da sessão; envia DEPOIS (fora dela).
    plan = []  # (uid, endpoint, sub_dict, payload, log_key)
    expired_endpoints = []

    with session_scope() as session:
        games = session.query(Game).filter(Game.kickoff > now, Game.kickoff <= horizon).all()
        if not games:
            return {"games": 0, "sent": 0}

        subs_uids = {
            r[0]
            for r in session.query(PushSubscription.participant_uid).distinct().all()
        }
        if not subs_uids:
            return {"games": len(games), "sent": 0}

        uid_to_p = {p.uid: p for p in session.query(Participant).all()}

        for game in games:
            minutes_to = max(1, int(round((game.kickoff - now).total_seconds() / 60)))
            # só enviar se a janela "bateu": minutos_to <= window_min (sempre true
            # pela query). Limitamos também a não lembrar com >24h (impossível aqui).
            title = f"⚽ Falta seu palpite: {game.team_a} x {game.team_b}"
            body = f"O jogo começa em ~{minutes_to} min. Dá seu palpite agora!"
            url = "/"  # preenchido por uid abaixo

            for uid in subs_uids:
                p = uid_to_p.get(uid)
                if not p:
                    continue
                log_key = f"pregame:{game.id}:{uid}"
                if session.query(NotificationLog).filter_by(log_key=log_key).first():
                    continue
                # Já palpitou? → não precisa lembrar.
                already = (
                    session.query(Prediction)
                    .filter_by(participant_id=p.id, game_id=game.id)
                    .first()
                )
                if already:
                    continue
                plan.append((uid, _payload(title, body, url=f"/user/{uid}", tag=log_key), log_key))

        if not plan:
            return {"games": len(games), "sent": 0}

    # Envia fora da sessão (cada send_push é só HTTP)
    sent = 0
    with session_scope() as session:
        for uid, payload, log_key in plan:
            ok = False
            for row in session.query(PushSubscription).filter_by(participant_uid=uid).all():
                status = send_push(_sub_to_dict(row), payload)
                if status == "ok":
                    ok = True
                elif status == "expired":
                    expired_endpoints.append(row.endpoint)
            if ok:
                sent += 1
            session.add(NotificationLog(log_key=log_key))
        for ep in expired_endpoints:
            session.query(PushSubscription).filter_by(endpoint=ep).delete()

    return {"games": len(games), "sent": sent}


def dispatch_daily_missing_reminders(force: bool = False) -> dict:
    """Lembrete diário (ex: às 11h): avisa cada inscrito que ainda NÃO
    palpitarou TODOS os jogos do dia. Idempotente por data
    (log_key `daily-missing:<YYYY-MM-DD>`).

    Considera apenas jogos cujo kickoff é HOJE e ainda aceitam palpites
    (kickoff > agora). Jogos da manhã que já começaram são ignorados
    (não dá mais pra palpitar). Só envia para quem tem inscrição ativa
    (PushSubscription).

    Horário disparado pelo scheduler: BOLAO_DAILY_REMINDER_HOUR (default 11).

    `force=True` ignora a idempotência e NÃO marca o log — modo teste
    (não bloqueia o disparo automático do dia).
    """
    from .database import session_scope
    from .models import (Game, NotificationLog, Participant, Prediction,
                         PushSubscription)

    if not is_push_enabled():
        return {"sent": 0, "reason": "push_disabled"}

    now = datetime.now()
    today = now.date()
    log_key = f"daily-missing:{today.isoformat()}"

    plan = []  # (uid, payload)
    expired_endpoints = []
    games_count = 0

    with session_scope() as session:
        # Idempotência global: se já rodou hoje, sai (a não ser que force).
        if not force and session.query(NotificationLog).filter_by(log_key=log_key).first():
            return {"sent": 0, "reason": "already_sent_today"}

        # Jogos do dia que ainda aceitam palpites (kickoff > agora e hoje).
        end_of_day = datetime.combine(today, datetime.max.time())
        games = (
            session.query(Game)
            .filter(Game.kickoff > now, Game.kickoff <= end_of_day)
            .order_by(Game.kickoff)
            .all()
        )
        games_count = len(games)

        if not games:
            if not force:
                session.add(NotificationLog(log_key=log_key))  # marca p/ não repetir
            return {"games": 0, "sent": 0, "reason": "no_games_today"}

        # UIDs com notificação ativa
        subs_uids = {
            r[0]
            for r in session.query(PushSubscription.participant_uid).distinct().all()
        }
        if not subs_uids:
            if not force:
                session.add(NotificationLog(log_key=log_key))
            return {"games": games_count, "sent": 0, "reason": "no_subscribers"}

        uid_to_p = {p.uid: p for p in session.query(Participant).all()}

        # Para cada inscrito, descobre quais jogos do dia faltam palpite.
        for uid in subs_uids:
            p = uid_to_p.get(uid)
            if not p:
                continue
            missing = []
            for game in games:
                already = (
                    session.query(Prediction)
                    .filter_by(participant_id=p.id, game_id=game.id)
                    .first()
                )
                if not already:
                    missing.append(game)

            if not missing:
                continue  # já completou todos do dia

            n = len(missing)
            if n == 1:
                g = missing[0]
                body = f"Hoje tem {g.team_a} x {g.team_b} e você ainda não palpitou. Dá seu palpite!"
            else:
                nomes = ", ".join(f"{g.team_a} x {g.team_b}" for g in missing)
                if len(nomes) > 120:
                    body = f"Faltam {n} palpites de hoje. Complete antes dos jogos começarem!"
                else:
                    body = f"Faltam {n} palpites de hoje: {nomes}"

            title = "⚽ Faltam seus palpites de hoje"
            plan.append((uid, _payload(title, body, url=f"/user/{uid}", tag=log_key)))

        # Marca como processado (só no modo normal) — evita reenvio/spam.
        if not force:
            session.add(NotificationLog(log_key=log_key))

    # Envia fora da sessão (cada send_push é só HTTP)
    sent = 0
    with session_scope() as session:
        for uid, payload in plan:
            ok = False
            for row in session.query(PushSubscription).filter_by(participant_uid=uid).all():
                status = send_push(_sub_to_dict(row), payload)
                if status == "ok":
                    ok = True
                elif status == "expired":
                    expired_endpoints.append(row.endpoint)
            if ok:
                sent += 1
        for ep in expired_endpoints:
            session.query(PushSubscription).filter_by(endpoint=ep).delete()

    return {"games": games_count, "targeted": len(plan), "sent": sent}


def dispatch_result_notifications(results: list) -> dict:
    """Notifica 'resultado disponível' para jogos recém-atualizados pelo sync.

    Idempotente por jogo (tag result:<game_id>). Recebe a lista retornada
    por _do_sync().
    """
    if not is_push_enabled():
        return {"sent": 0, "reason": "push_disabled"}

    targets = [
        r for r in results
        if r.get("status") in ("updated", "corrected") and r.get("home")
    ]
    if not targets:
        return {"sent": 0}

    from .database import session_scope

    sent_total = 0
    for r in targets:
        game_id = r.get("game_id")
        tag = f"result:{game_id}" if game_id else f"result:{r['home']}:{r['away']}"
        title = f"🏁 {r['home']} {r.get('score_a', '')} x {r.get('score_b', '')} {r['away']}"
        body = "Resultado disponível! Veja quantos pontos você fez."
        with session_scope() as session:
            sent, _ = broadcast_to_all(session, title, body, url="/", tag=tag)
            sent_total += sent
    return {"sent": sent_total}
