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
from datetime import datetime, timedelta, timezone

_log = logging.getLogger("bolao.push")

# Fuso do bolão: America/Sao_Paulo (UTC-3), sem DST desde 2019.
# O banco guarda `kickoff` em hora de Brasília sem tzinfo (datetime 'naive').
# Por isso TODA comparação com kickoff (filtros SQL e aritmética) deve usar um
# datetime naive em BRT. Importante: NÃO usar datetime.now() puro, que reflete
# o fuso do container (que pode estar em UTC) e desloca os horários.
BRT_TZ = timezone(timedelta(hours=-3))


def _now_brt_naive() -> datetime:
    """Horário atual de Brasília como datetime naive (sem tzinfo)."""
    return datetime.now(BRT_TZ).replace(tzinfo=None)


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
def _reminder_checkpoints() -> list[int]:
    """Minutos antes do kickoff em que disparar lembretes (decrescente).

    Configurável via BOLAO_REMINDER_CHECKPOINTS (default "180,120,60" =
    3h, 2h e 1h antes). Checkpoints devem ficar espaçados entre si por mais
    que 2x a tolerância (_reminder_tolerance_min) para não sobrepor janelas.
    """
    raw = os.environ.get("BOLAO_REMINDER_CHECKPOINTS", "180,120,60")
    pts: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            pts.append(int(part))
        except ValueError:
            _log.warning("BOLAO_REMINDER_CHECKPOINTS: valor inválido ignorado: %r", part)
    pts = sorted(set(pts), reverse=True)
    return pts or [180, 120, 60]


def _reminder_tolerance_min() -> int:
    """Margem (min) ao redor de cada checkpoint para considerar "na hora".

    O scheduler roda a cada BOLAO_NOTIFY_INTERVAL (default 300s = 5 min). A
    tolerância cobre ao menos 2 ciclos para que um restart/curta
    indisponibilidade não faça perder o checkpoint. Default 15 min.
    """
    try:
        return max(5, int(os.environ.get("BOLAO_REMINDER_TOLERANCE_MIN", "15")))
    except ValueError:
        return 15


def _humanize_minutes(m: int) -> str:
    """180 -> '3h', 120 -> '2h', 60 -> '1h', 45 -> '45 min'."""
    if m >= 60 and m % 60 == 0:
        return f"{m // 60}h"
    if m >= 60:
        return f"~{m // 60}h"
    return f"{m} min"


def _plan_pregame_reminders(session, now: datetime | None = None,
                            checkpoints: list[int] | None = None,
                            tol: int | None = None) -> list[tuple[str, dict, str]]:
    """Monta o plano de lembretes (SEM enviar) para a data/hora `now`.

    Para cada jogo futuro dentro do horizonte (até o maior checkpoint + tol),
    e para cada checkpoint C cuja janela [C-tol, C] engloba minutos_to, avisa
    inscritos sem palpite e sem log `pregame:{game}:{uid}:{C}`.

    Retorna lista de (uid, payload, log_key). NÃO cria os logs (quem envia
    é o dispatch) — separada do envio p/ ser testável sem VAPID.
    """
    from .models import (Game, NotificationLog, Participant, Prediction,
                         PushSubscription)

    now = now or _now_brt_naive()
    checkpoints = checkpoints or _reminder_checkpoints()
    tol = tol if tol is not None else _reminder_tolerance_min()

    horizon = now + timedelta(minutes=max(checkpoints) + tol)
    games = session.query(Game).filter(Game.kickoff > now, Game.kickoff <= horizon).all()
    if not games:
        return []

    subs_uids = {
        r[0]
        for r in session.query(PushSubscription.participant_uid).distinct().all()
    }
    if not subs_uids:
        return []

    uid_to_p = {p.uid: p for p in session.query(Participant).all()}

    # Cache de quem já palpitou (participant_id, game_id) p/ evitar N queries.
    predicted_pairs = {
        (pred.participant_id, pred.game_id)
        for pred in session.query(Prediction).all()
    }

    plan: list[tuple[str, dict, str]] = []
    for game in games:
        minutes_to = int(round((game.kickoff - now).total_seconds() / 60))
        if minutes_to <= 0:
            continue
        for C in checkpoints:
            # Janela: faltam entre (C - tol) e C minutos.
            if not (C - tol <= minutes_to <= C):
                continue
            title = f"⚽ Falta seu palpite: {game.team_a} x {game.team_b}"
            body = f"Faltam {_humanize_minutes(minutes_to)} pro jogo. Dá seu palpite agora!"
            for uid in subs_uids:
                p = uid_to_p.get(uid)
                if not p:
                    continue
                if (p.id, game.id) in predicted_pairs:
                    continue  # já palpitou
                log_key = f"pregame:{game.id}:{uid}:{C}"
                if session.query(NotificationLog).filter_by(log_key=log_key).first():
                    continue  # já avisou esse checkpoint
                plan.append((uid, _payload(title, body, url=f"/user/{uid}", tag=log_key), log_key))
    return plan


def dispatch_pregame_reminders() -> dict:
    """Lembretes de palpite multi-checkpoint.

    Dispara notificações em vários checkpoints antes do jogo (default
    3h, 2h e 1h antes) para os inscritos que ainda não palpitarão o jogo.
    Idempotente por jogo+uid+checkpoint (log_key `pregame:{game}:{uid}:{C}`),
    então cada checkpoint é enviado no máximo 1x por participante.

    Cada checkpoint tem uma tolerância (default 15 min) ao redor, garantindo
    o disparo mesmo com restarts curtos do servidor ou com o scheduler
    rodando a cada 5 min.
    """
    from .database import session_scope
    from .models import Game, NotificationLog, PushSubscription

    if not is_push_enabled():
        return {"sent": 0, "reason": "push_disabled"}

    now = _now_brt_naive()
    checkpoints = _reminder_checkpoints()
    tol = _reminder_tolerance_min()
    horizon = now + timedelta(minutes=max(checkpoints) + tol)
    expired_endpoints: list[str] = []

    with session_scope() as session:
        plan = _plan_pregame_reminders(session, now=now, checkpoints=checkpoints, tol=tol)
        games_count = session.query(Game).filter(Game.kickoff > now, Game.kickoff <= horizon).count()

    if not plan:
        return {"games": games_count, "sent": 0}

    # Envia fora da sessão (cada send_push é só HTTP); marca o log por checkpoint.
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

    return {"games": games_count, "sent": sent, "checkpoints": len(plan)}


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

    now = _now_brt_naive()
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
