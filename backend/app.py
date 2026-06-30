import os
import sys
import jwt
import subprocess
import logging
import threading
import time as _time_module
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash
from .database import engine, session_scope, DATABASE_URL
from .models import (AdminUser, Base, FinalsPrediction, Game, NotificationLog,
                    Participant, Prediction, PushSubscription, RankingSnapshot, ScoringConfig,
                    TournamentOutcome)
from .scoring import calculate_scores, calculate_daily_scores, score_prediction, get_scoring_config_dict


# Derive DB_PATH from the same DATABASE_URL used by the ORM
def _db_path_from_url(url: str) -> Path:
    """Convert sqlite:///path/to/db or sqlite:///path to a filesystem Path."""
    if url.startswith("sqlite:///"):
        p = url[len("sqlite:///" ):]
        if not os.path.isabs(p):
            p = os.path.join(os.getcwd(), p)
        return Path(p)
    return Path(url)


DB_PATH = _db_path_from_url(DATABASE_URL)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev_secret_key_change_in_prod'
CORS(app)


def _now_brt() -> datetime:
    """Horário de Brasília (BRT, UTC-3) como datetime 'naive' (sem tzinfo).

    O banco guarda `Game.kickoff` em horário de Brasília sem tzinfo. Portanto
    TODA comparação com kickoff (filtros de palpites, scheduler ao vivo, prazo
    das finais) e toda derivação de 'data de hoje' (snapshots de ranking,
    lembrete diário) deve usar este helper — nunca `datetime.now()`, que
    reflete o fuso do container e pode dessincronizar os horários das
    notificações quando o container não está em America/Sao_Paulo.
    """
    return datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)


# Initialize database on app startup
def ensure_db_exists():
    os.makedirs(DB_PATH.parent, exist_ok=True)
    Base.metadata.create_all(engine)

    # Auto-migrate: add finals_deadline column if missing
    import sqlite3
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(scoring_config)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'finals_deadline' not in columns:
            cursor.execute('ALTER TABLE scoring_config ADD COLUMN finals_deadline DATETIME')
            conn.commit()
        # daily_reminder_hour: fallback inicial = env var BOLAO_DAILY_REMINDER_HOUR (default 11).
        # Depois de criada, o banco é a única fonte de verdade (editável via /admin).
        if 'daily_reminder_hour' not in columns:
            init_hour = int(os.environ.get("BOLAO_DAILY_REMINDER_HOUR", "11"))
            cursor.execute(
                'ALTER TABLE scoring_config ADD COLUMN daily_reminder_hour INTEGER NOT NULL DEFAULT %d' % init_hour
            )
            conn.commit()

        # games.status: scheduled | live | finished
        # Permite ao poller ao vivo distinguir placar parcial (live) do placar
        # final travado (finished), movendo o ranking em tempo real durante os
        # jogos sem poluir a pontuação oficial.
        cursor.execute("PRAGMA table_info(games)")
        game_cols = [col[1] for col in cursor.fetchall()]
        if 'status' not in game_cols:
            cursor.execute(
                "ALTER TABLE games ADD COLUMN status VARCHAR NOT NULL DEFAULT 'scheduled'"
            )
            # Backfill: jogos que já têm placar -> finished; demais -> scheduled
            cursor.execute("UPDATE games SET status='finished' WHERE score_a IS NOT NULL")
            conn.commit()
        # games.espn_id: chave estável para casar jogos de mata-mata cujos times
        # mudam de placeholder -> time real (importados via sync ESPN).
        if 'espn_id' not in game_cols:
            cursor.execute('ALTER TABLE games ADD COLUMN espn_id VARCHAR')
            conn.commit()
        conn.close()
    except Exception:
        pass


# Create tables at import time
with app.app_context():
    ensure_db_exists()


# ---------------------------------------------------------------------------
# Auto-sync scheduler (a cada hora) — SÓ jogos que já começaram
# ---------------------------------------------------------------------------
# REGRA CRÍTICA de segurança: o sync automático NUNCA atualiza jogos
# futuros, para nunca alterar palpites ainda abertos dos usuários.
# Só toca em jogos cujo kickoff já passou (ao vivo ou no passado).
# ---------------------------------------------------------------------------

SYNC_INTERVAL_SECONDS = int(os.environ.get("BOLAO_SYNC_INTERVAL", "3600"))
_sync_log = logging.getLogger("bolao.sync")
_sync_started = False


def _do_sync(now=None):
    """
    Executa sincronização ESPN → banco.

    Proteções (em ordem):
      1. Só jogos finalizados segundo a ESPN (is_full_time = FT/AET/FT-Pens)
      2. 🔒 Só jogos cujo kickoff <= now (NUNCA jogos futuros)

    Comportamento de placar (modo "corrige ao fim"):
      - Jogo sem placar no bolão  → grava o placar final da ESPN
      - Jogo com placar que DIFERE do final da ESPN → SOBRESCREVE
        (corrige placares provisórios gravados por engano durante o jogo)
      - Jogo com placar igual ao final da ESPN → mantém

    Jogos futuros nunca são tocados: nunca têm is_full_time e o filtro
    de kickoff <= now também os blinda.

    Estratégia de datas: coleta todas as datas distintas de jogos
    passados (com buffer de -1 dia para tolerar diferença de fuso entre
    o kickoff salvo em Brasília e o horário UTC da ESPN).

    Retorna a lista de resultados (dicts).
    """
    from .sync_results import fetch_espn_games, parse_espn_event

    now = now or _now_brt()

    # 1. Snapshot read-only dos jogos (serializa para usar fora da sessão)
    with session_scope() as session:
        bolao_games = [
            {
                "id": g.id,
                "team_a": g.team_a,
                "team_b": g.team_b,
                "kickoff": g.kickoff,
                "score_a": g.score_a,
                "score_b": g.score_b,
                "matched": False,  # flag p/ não casar o mesmo jogo 2x
            }
            for g in session.query(Game).all()
        ]

    # 2. Coleta datas de jogos passados (com ou sem placar — podemos
    #    corrigir placares provisórios gravados durante o jogo).
    # Buffer de 1 dia antes para cobrir diferença de fuso UTC vs Brasília.
    dates_to_check = set()
    for g in bolao_games:
        if g["kickoff"] is None or g["kickoff"] > now:
            continue  # 🔒 jogo futuro — nunca tocar
        day = g["kickoff"].date()
        dates_to_check.add(day.strftime("%Y-%m-%d"))
        dates_to_check.add((day - timedelta(days=1)).strftime("%Y-%m-%d"))

    all_results = []
    if not dates_to_check:
        return all_results

    # 3. Coleta atualizações a fazer (fora de qualquer sessão)
    updates = []  # (game_id, score_a, score_b, team_a, team_b)
    for d in sorted(dates_to_check):
        try:
            espn_events = fetch_espn_games(d)
        except Exception as e:
            all_results.append({"date": d, "error": str(e)})
            continue

        for event in espn_events:
            parsed = parse_espn_event(event)
            if not parsed or not parsed.get("is_full_time"):
                continue

            home_pt = parsed["home"]["name_pt"]
            away_pt = parsed["away"]["name_pt"]

            match = None
            for g in bolao_games:
                # 🔒 PROTEÇÃO CRÍTICA: só jogos que já começaram.
                # Jogos futuros (kickoff > agora) são IGNORADOS para
                # nunca alterar palpites ainda abertos dos usuários.
                if g["kickoff"] is None or g["kickoff"] > now:
                    continue
                if g.get("matched"):
                    continue  # já casou com outro evento ESPN
                if (g["team_a"] == home_pt and g["team_b"] == away_pt) or \
                   (g["team_a"] == away_pt and g["team_b"] == home_pt):
                    match = g
                    g["matched"] = True
                    break

            if not match:
                all_results.append({
                    "status": "not_found",
                    "home": home_pt,
                    "away": away_pt,
                })
                continue

            # Determine scores in bolão order
            if match["team_a"] == home_pt:
                score_a = parsed["home"]["score"]
                score_b = parsed["away"]["score"]
            else:
                score_a = parsed["away"]["score"]
                score_b = parsed["home"]["score"]

            # Decisão: o placar no bolão bate com o final da ESPN?
            cur_a, cur_b = match["score_a"], match["score_b"]
            if cur_a == score_a and cur_b == score_b:
                # Já está correto — nada a fazer
                all_results.append({
                    "status": "already_correct",
                    "game_id": match["id"],
                })
                continue

            # Precisa gravar: novo placar (cur_a is None) OU correção
            # de placar provisório gravado durante o jogo.
            was_corrected = cur_a is not None
            updates.append((match["id"], score_a, score_b, match["team_a"], match["team_b"], was_corrected))
            # Atualiza snapshot para não reprocessar entre datas
            match["score_a"] = score_a
            match["score_b"] = score_b

    # 4. Aplica as atualizações numa sessão nova (double-check de concorrência)
    if updates:
        with session_scope() as session:
            for game_id, score_a, score_b, team_a, team_b, was_corrected in updates:
                game = session.get(Game, game_id)
                if not game:
                    continue
                # 🔒 Re-confirma proteção temporal: nunca jogos futuros
                if game.kickoff is None or game.kickoff > now:
                    continue
                # Só grava se for diferente do estado atual do banco
                # (pode ter mudado entre o snapshot e aqui)
                if game.score_a == score_a and game.score_b == score_b:
                    continue
                game.score_a = score_a
                game.score_b = score_b
                game.status = "finished"
                all_results.append({
                    "status": "corrected" if was_corrected else "updated",
                    "game_id": game_id,
                    "home": team_a,
                    "away": team_b,
                    "score_a": score_a,
                    "score_b": score_b,
                })

    return all_results


def _do_resolve_names():
    """Renomeia placeholders -> times reais nos jogos do mata-mata (automático).

    Casa por espn_id (chave estável) com a ESPN. Só toca jogos:
      - com espn_id definido
      - SEM placar (score_a IS NULL)  -> nunca altera resultados
    Renomeia apenas team_a/team_b quando a ESPN já definiu times reais
    (ex.: "2º Grupo J" -> "Croácia").

    Proteção de produção: nunca altera placar/status. Idempotente.
    """
    from .sync_results import fetch_espn_events_raw, parse_espn_event

    with session_scope() as session:
        # Jogos placeholder: têm espn_id e ainda sem placar.
        placeholders = session.query(Game).filter(
            Game.espn_id.isnot(None),
            Game.score_a.is_(None),
        ).all()

        if not placeholders:
            return []

        # Datas ESPN a buscar. A ESPN classifica cada evento pelo dia em
        # timezone *Eastern* (EDT/EST), que pode ser UM DIA ATRÁS do dia em
        # Brasília para jogos nas primeiras horas do dia BRT
        # (ex.: 03/07 00:00 BRT = 02/07 23:00 EDT -> a ESPN lista no dia 02/07).
        # Por isso buscamos também o dia anterior ao do kickoff. O casamento
        # é por espn_id (chave estável), então buscar datas a mais é seguro
        # (nunca renomeia o jogo errado). Mesma lógica já usada no _do_sync().
        espn_dates = set()
        for g in placeholders:
            if not g.kickoff:
                continue
            day = g.kickoff.date()
            espn_dates.add(day.strftime("%Y%m%d"))
            espn_dates.add((day - timedelta(days=1)).strftime("%Y%m%d"))

        # Indexa TODOS os eventos da ESPN por espn_id (casa por chave estável,
        # independente do dia em que a ESPN os classificou).
        espn_by_id = {}
        for date_str in sorted(espn_dates):
            try:
                events = fetch_espn_events_raw(date_str)
            except Exception as e:
                _sync_log.error("⏰ [rename] erro ESPN %s: %s", date_str, e)
                continue
            for ev in events:
                parsed = parse_espn_event(ev)
                if parsed and parsed.get("espn_id"):
                    espn_by_id[str(parsed["espn_id"])] = parsed

        results = []
        renamed = 0
        for g in placeholders:
            parsed = espn_by_id.get(str(g.espn_id))
            if not parsed:
                continue
            home_pt = parsed["home"]["name_pt"]
            away_pt = parsed["away"]["name_pt"]
            # Só renomeia se algum lado mudou.
            if g.team_a == home_pt and g.team_b == away_pt:
                continue
            old = f"{g.team_a} x {g.team_b}"
            g.team_a = home_pt
            g.team_b = away_pt
            renamed += 1
            results.append({"game_id": g.id, "from": old, "to": f"{home_pt} x {away_pt}"})
            _sync_log.info("🔁 [rename] jogo %d: %s -> %s", g.id, old, f"{home_pt} x {away_pt}")

        if renamed:
            _sync_log.info("⏰ [rename] %d jogo(s) renomeado(s) (placeholder -> time real)", renamed)
        return results


def start_sync_scheduler():
    """Inicia o scheduler de sync em background. Idempotente por processo."""
    global _sync_started
    if _sync_started:
        return
    _sync_started = True

    def _loop():
        _time_module.sleep(15)  # espera o app ficar pronto
        while True:
            try:
                _sync_log.info("⏰ [scheduler] iniciando sync horário")
                results = _do_sync()
                updated = sum(1 for r in results if r.get("status") == "updated")
                corrected = sum(1 for r in results if r.get("status") == "corrected")
                not_found = sum(1 for r in results if r.get("status") == "not_found")
                _sync_log.info(
                    "⏰ [scheduler] sync concluído: %d novo(s), %d corrigido(s), %d não encontrado(s)",
                    updated, corrected, not_found,
                )
                # Renomeação automática de placeholders -> times reais (mata-mata).
                # Independente e isolado: falhar aqui não afeta o sync de placar.
                try:
                    renamed_results = _do_resolve_names()
                    if renamed_results:
                        _sync_log.info(
                            "⏰ [scheduler] renomeação: %d jogo(s) atualizado(s)",
                            len(renamed_results),
                        )
                except Exception as re:
                    _sync_log.error("⏰ [scheduler] erro na renomeação: %s", re)
                try:
                    from .notifications import dispatch_result_notifications
                    n = dispatch_result_notifications(results)
                    if n.get("sent"):
                        _sync_log.info("🔔 [scheduler] notificações de resultado: %s", n)
                except Exception as ne:
                    _sync_log.error("🔔 [scheduler] erro ao notificar resultados: %s", ne)
            except Exception as e:
                _sync_log.error("⏰ [scheduler] erro no sync: %s", e)
            _time_module.sleep(SYNC_INTERVAL_SECONDS)

    t = threading.Thread(target=_loop, daemon=True, name="bolao-sync-scheduler")
    t.start()
    _sync_log.info("⏰ Scheduler de sync horário iniciado (intervalo=%ds)", SYNC_INTERVAL_SECONDS)


def _bootstrap_future_games():
    """Cria jogos futuros da ESPN (mata-mata) que ainda não existem no bolão.

    Roda UMA vez no boot do app (em thread separada para não atrasar o startup).
    Cobre o cenário de deploy: o data.db não entra no git, então ao subir em
    produção faltam os jogos do mata-mata. Esta função os importa automaticamente,
    inclusive placeholders (times indefinidos).

    Proteções:
      - Só cria jogos FUTUROS (kickoff >= agora): nunca toca dados de produção.
      - Idempotente: casa por espn_id, não duplica.
      - Erros ESPN (offline) são silenciosos: tenta de novo no próximo boot/sync.
    """
    from .sync_results import (
        fetch_espn_events_raw, parse_espn_event, _espn_date_to_brt_iso, BRT_TZ,
    )

    def _run():
        try:
            _time_module.sleep(30)  # espera o app estabilizar
            _sync_log.info("🚀 [bootstrap] checando jogos futuros da ESPN...")
            now = datetime.now(BRT_TZ)

            # Janela: de hoje até ~5 meses à frente (cobre a Copa toda).
            inicio = now.strftime("%Y%m%d")
            fim = (now + timedelta(days=150)).strftime("%Y%m%d")
            events = fetch_espn_events_raw(f"{inicio}-{fim}")

            # espn_ids e matchups já presentes no bolão.
            with session_scope() as session:
                existing_ids = {
                    str(r[0]) for r in session.query(Game.espn_id).filter(Game.espn_id.isnot(None)).all()
                }
                # Nome dos times (em qualquer ordem) para evitar duplicar jogos
                # antigos da fase de grupos que entraram sem espn_id.
                existing_matchups = set()
                for g in session.query(Game).all():
                    existing_matchups.add((g.team_a, g.team_b))
                    existing_matchups.add((g.team_b, g.team_a))

            to_import = []
            for event in events:
                parsed = parse_espn_event(event)
                if not parsed:
                    continue
                espn_id = parsed.get("espn_id") or None
                home_pt = parsed["home"]["name_pt"]
                away_pt = parsed["away"]["name_pt"]
                # Idempotente: pula se já existe por espn_id OU por matchup de nomes.
                if espn_id and str(espn_id) in existing_ids:
                    continue
                if (home_pt, away_pt) in existing_matchups:
                    continue
                kickoff = _espn_date_to_brt_iso(parsed.get("date"))
                if not kickoff:
                    continue
                # 🔒 Só jogos futuros: protege dados de produção.
                try:
                    ko_dt = datetime.fromisoformat(kickoff).replace(tzinfo=BRT_TZ)
                except Exception:
                    continue
                if ko_dt < now:
                    continue
                to_import.append({
                    "kickoff": kickoff,
                    "team_a": parsed["home"]["name_pt"],
                    "team_b": parsed["away"]["name_pt"],
                    "espn_id": espn_id,
                })

            if not to_import:
                _sync_log.info("🚀 [bootstrap] nenhum jogo novo para importar.")
                return

            # Importa via endpoint interno (usa o app). Dedupe por espn_id.
            with app.test_client() as client:
                # token admin efêmero para o import.
                from .models import AdminUser
                admin_id = None
                with session_scope() as session:
                    admin = session.query(AdminUser).first()
                    if admin:
                        admin_id = admin.id  # captura id antes de fechar a sessão
                headers = {}
                if admin_id:
                    token = jwt.encode(
                        {"user_id": admin_id, "exp": datetime.utcnow() + timedelta(minutes=5)},
                        app.config["SECRET_KEY"], algorithm="HS256",
                    )
                    headers["Authorization"] = f"Bearer {token}"
                resp = client.post("/games/import", json=to_import, headers=headers)
                if resp.status_code == 200:
                    _sync_log.info("🚀 [bootstrap] importação: %s", resp.get_json())
                else:
                    _sync_log.error("🚀 [bootstrap] falha no import: %s %s", resp.status_code, resp.data)
        except Exception as e:
            _sync_log.error("🚀 [bootstrap] erro ao importar jogos: %s", e)

    t = threading.Thread(target=_run, daemon=True, name="bolao-bootstrap-games")
    t.start()


start_sync_scheduler()


# Cria jogos futuros da ESPN (mata-mata) no boot — garante que PROD tenha
# os jogos mesmo sem o data.db (que não entra no git). Idempotente.
_bootstrap_future_games()


# ---------------------------------------------------------------------------
# Live scheduler (alta frequência, default 30s) — ranking ao vivo
# ---------------------------------------------------------------------------
# Diferente do _do_sync horário (que só trava resultados no FT), este poller
# atualiza o PLACAR PARCIAL durante o jogo (state=in) para que o ranking se
# mova em tempo real. Marca status='live' para o parcial e 'finished' no FT.
#
# Proteções:
#   - Só busca na ESPN quando há jogo "em janela" (kickoff <= agora E
#     status != 'finished'). Sem jogo em andamento, dorme sem chamar a ESPN.
#   - 🔒 Nunca toca em jogos futuros (kickoff > agora).
#   - Push de resultado (🏁) só dispara no FT (updated/corrected). As
#     atualizações ao vivo usam o status interno 'live_updated' (fora do
#     gatilho do push), então o aviso de resultado sai uma única vez, no fim.
# ---------------------------------------------------------------------------

LIVE_INTERVAL_SECONDS = int(os.environ.get("BOLAO_LIVE_INTERVAL", "30"))
_live_started = False


def _do_live_sync(now=None):
    """Sincronização AO VIVO: grava o placar parcial durante o jogo e trava o
    final assim que a ESPN confirma FT, para o ranking se mover em tempo real.

    Janela: jogos com kickoff <= now E status != 'finished'.

    Retorna lista de dicts; campo 'status' interno:
      - 'live_updated'        : placar parcial gravado/atualizado (NÃO dispara push)
      - 'updated'/'corrected' : placar FINAL travado (dispara push de resultado)
      - 'already_correct' / 'not_found'
    """
    from .sync_results import fetch_espn_games, parse_espn_event

    now = now or _now_brt()

    # 1. Snapshot read-only dos jogos em janela (kickoff <= now, não finished)
    with session_scope() as session:
        in_window = [
            {
                "id": g.id,
                "team_a": g.team_a,
                "team_b": g.team_b,
                "kickoff": g.kickoff,
                "score_a": g.score_a,
                "score_b": g.score_b,
                "status": g.status or "scheduled",
            }
            for g in session.query(Game).all()
            if g.kickoff is not None
            and g.kickoff <= now
            and (g.status or "scheduled") != "finished"
        ]

    if not in_window:
        return []

    for g in in_window:
        g["matched"] = False

    # 2. Datas a checar (dia do kickoff +/- 1 dia p/ tolerar fuso UTC vs BRT)
    dates_to_check = set()
    for g in in_window:
        day = g["kickoff"].date()
        dates_to_check.add(day.strftime("%Y-%m-%d"))
        dates_to_check.add((day - timedelta(days=1)).strftime("%Y-%m-%d"))

    all_results = []
    updates = []  # (game_id, score_a, score_b, target_status, team_a, team_b, was_corrected)

    for d in sorted(dates_to_check):
        try:
            espn_events = fetch_espn_games(d)
        except Exception as e:
            all_results.append({"date": d, "error": str(e)})
            continue

        for event in espn_events:
            parsed = parse_espn_event(event)
            if not parsed:
                continue

            is_live = parsed.get("state") == "in"
            is_ft = parsed.get("is_full_time")
            if not (is_live or is_ft):
                continue  # agendado — ignora

            home_pt = parsed["home"]["name_pt"]
            away_pt = parsed["away"]["name_pt"]

            match = None
            for g in in_window:
                if g.get("matched"):
                    continue
                if (g["team_a"] == home_pt and g["team_b"] == away_pt) or \
                   (g["team_a"] == away_pt and g["team_b"] == home_pt):
                    match = g
                    g["matched"] = True
                    break

            if not match:
                all_results.append({"status": "not_found", "home": home_pt, "away": away_pt})
                continue

            # Placar na ordem do bolão
            if match["team_a"] == home_pt:
                score_a = parsed["home"]["score"]
                score_b = parsed["away"]["score"]
            else:
                score_a = parsed["away"]["score"]
                score_b = parsed["home"]["score"]

            target_status = "finished" if is_ft else "live"
            cur_a, cur_b = match["score_a"], match["score_b"]

            if cur_a == score_a and cur_b == score_b and match["status"] == target_status:
                all_results.append({"status": "already_correct", "game_id": match["id"]})
                continue

            # já tinha placar (parcial/provisório) — relevante só no FT (corrected)
            was_corrected = cur_a is not None
            updates.append((match["id"], score_a, score_b, target_status,
                            match["team_a"], match["team_b"], was_corrected))
            match["score_a"] = score_a
            match["score_b"] = score_b
            match["status"] = target_status

    # 3. Aplica as atualizações (double-check de concorrência)
    if updates:
        with session_scope() as session:
            for game_id, score_a, score_b, target_status, team_a, team_b, was_corrected in updates:
                game = session.get(Game, game_id)
                if not game:
                    continue
                # 🔒 Re-confirma proteção temporal: nunca jogos futuros
                if game.kickoff is None or game.kickoff > now:
                    continue
                # 🔒 Nunca rebaixar um jogo já finalizado de volta para 'live'
                if (game.status or "scheduled") == "finished" and target_status == "live":
                    continue
                if game.score_a == score_a and game.score_b == score_b \
                        and (game.status or "scheduled") == target_status:
                    continue
                game.score_a = score_a
                game.score_b = score_b
                game.status = target_status
                if target_status == "finished":
                    internal = "corrected" if was_corrected else "updated"
                else:
                    internal = "live_updated"
                all_results.append({
                    "status": internal,
                    "game_id": game_id,
                    "home": team_a,
                    "away": team_b,
                    "score_a": score_a,
                    "score_b": score_b,
                })

    return all_results


def start_live_scheduler():
    """Poller de alta frequência (default 30s) para o ranking ao vivo.
    Idempotente por processo. Só bate na ESPN quando há jogo em andamento."""
    global _live_started
    if _live_started:
        return
    _live_started = True

    def _loop():
        _time_module.sleep(20)  # espera o app/banco ficarem prontos
        while True:
            try:
                now = _now_brt()
                # Checagem barata: há jogo em janela?
                with session_scope() as session:
                    has_in_window = session.query(Game).filter(
                        Game.kickoff.isnot(None),
                        Game.kickoff <= now,
                    ).filter(
                        (Game.status != "finished") | (Game.status.is_(None))
                    ).first() is not None

                if has_in_window:
                    results = _do_live_sync(now=now)
                    live_up = sum(1 for r in results if r.get("status") == "live_updated")
                    finished = sum(1 for r in results if r.get("status") in ("updated", "corrected"))
                    if live_up or finished:
                        _sync_log.info(
                            "🔴 [live] placar ao vivo sincronizado: %d parcial(is), %d final(is)",
                            live_up, finished,
                        )
                    # Push de resultado SÓ no FT (updated/corrected).
                    # 'live_updated' fica de fora — nunca dispara "🏁 resultado".
                    try:
                        from .notifications import dispatch_result_notifications
                        ft_results = [r for r in results if r.get("status") in ("updated", "corrected")]
                        n = dispatch_result_notifications(ft_results)
                        if n.get("sent"):
                            _sync_log.info("🏁 [live] push de resultado enviado: %s", n)
                    except Exception as ne:
                        _sync_log.error("🏁 [live] erro no push de resultado: %s", ne)
            except Exception as e:
                _sync_log.error("🔴 [live] erro no poller ao vivo: %s", e)
            _time_module.sleep(LIVE_INTERVAL_SECONDS)

    t = threading.Thread(target=_loop, daemon=True, name="bolao-live-scheduler")
    t.start()
    _sync_log.info("🔴 Poller ao vivo iniciado (intervalo=%ds)", LIVE_INTERVAL_SECONDS)


start_live_scheduler()


# ---------------------------------------------------------------------------
# Auto-notification scheduler (a cada N min) — lembretes de palpite
# ---------------------------------------------------------------------------
NOTIFY_INTERVAL_SECONDS = int(os.environ.get("BOLAO_NOTIFY_INTERVAL", "300"))
_notify_started = False


def start_notification_scheduler():
    """Idempotente por processo. Dispara lembretes de palpite para jogos
    próximos (configurável via BOLAO_REMINDER_WINDOW_MIN)."""
    global _notify_started
    if _notify_started:
        return
    _notify_started = True

    def _loop():
        _time_module.sleep(30)  # dá tempo do app/banco ficarem prontos
        while True:
            try:
                from .notifications import dispatch_pregame_reminders
                result = dispatch_pregame_reminders()
                if result.get("sent"):
                    _sync_log.info("🔔 [notify] lembretes enviados: %s", result)
            except Exception as e:
                _sync_log.error("🔔 [notify] erro nos lembretes: %s", e)
            _time_module.sleep(NOTIFY_INTERVAL_SECONDS)

    t = threading.Thread(target=_loop, daemon=True, name="bolao-notify-scheduler")
    t.start()
    _sync_log.info("🔔 Scheduler de notificações iniciado (intervalo=%ds)", NOTIFY_INTERVAL_SECONDS)


start_notification_scheduler()


# ---------------------------------------------------------------------------
# Daily reminder scheduler (1x/dia, a partir das HH:00) — palpites faltantes
# do dia. Idempotente por data (log_key daily-missing:<YYYY-MM-DD>).
# ---------------------------------------------------------------------------
_daily_started = False


def _get_daily_reminder_hour() -> int:
    """Lê a hora configurada no banco (admin pode mudar a qualquer momento).
    Fallback: 11 (ou a env var BOLAO_DAILY_REMINDER_HOUR, só se a row não existir)."""
    try:
        with session_scope() as session:
            cfg = session.query(ScoringConfig).get(1)
            if cfg and cfg.daily_reminder_hour is not None:
                return int(cfg.daily_reminder_hour)
    except Exception as e:
        _sync_log.error("🔔 [daily] erro ao ler daily_reminder_hour: %s", e)
    return int(os.environ.get("BOLAO_DAILY_REMINDER_HOUR", "11"))


def start_daily_reminder_scheduler():
    """A partir das HH:00 (lido do banco), dispara 1x/dia o lembrete de
    palpites faltantes do dia para quem tem notificação ativa."""
    global _daily_started
    if _daily_started:
        return
    _daily_started = True

    def _loop():
        _time_module.sleep(45)  # dá tempo do app/banco ficarem prontos
        while True:
            try:
                now = _now_brt()
                if now.hour >= _get_daily_reminder_hour():
                    from .notifications import dispatch_daily_missing_reminders
                    result = dispatch_daily_missing_reminders()
                    # already_sent_today é esperado nas chamadas seguintes do dia
                    if result.get("sent"):
                        _sync_log.info("🔔 [daily] lembrete diário enviado: %s", result)
            except Exception as e:
                _sync_log.error("🔔 [daily] erro no lembrete diário: %s", e)
            _time_module.sleep(60)

    t = threading.Thread(target=_loop, daemon=True, name="bolao-daily-scheduler")
    t.start()
    _sync_log.info("🔔 Scheduler diário iniciado (hora lida do banco, default 11h)")


start_daily_reminder_scheduler()


# ---------------------------------------------------------------------------
# Ranking snapshot scheduler (1x/dia) — congela a posição de cada participante
# no fechamento do dia anterior, para alimentar a coluna de variação (↑/↓).
# Idempotente por data: se já existe snapshot de ontem, não faz nada.
# ---------------------------------------------------------------------------
# Hora (0-23) do snapshot diário do ranking. Default 5h: garante que todos
# os jogos do dia anterior já terminaram e foram sincronizados (inclusive os
# que terminam logo após a meia-noite) antes de congelar o ranking de ontem.
SNAPSHOT_HOUR = int(os.environ.get("BOLAO_SNAPSHOT_HOUR", "5"))
_snapshot_started = False


def _compute_ranking_results(session):
    """Calcula o ranking completo a partir do estado atual do banco."""
    participants = session.query(Participant).all()
    games = session.query(Game).all()
    predictions = session.query(Prediction).all()
    finals_predictions = session.query(FinalsPrediction).all()
    outcome = session.query(TournamentOutcome).get(1)
    config = session.query(ScoringConfig).get(1)
    scoring_cfg = get_scoring_config_dict(config)
    return calculate_scores(
        participants=participants,
        games=games,
        predictions=predictions,
        finals_predictions=finals_predictions,
        outcome=outcome,
        scoring_cfg=scoring_cfg,
    )


def _capture_ranking_snapshot(session, target_date, results):
    """Insere (idempotente) um snapshot do ranking para `target_date`.

    `results` deve ser a lista já ordenada retornada por calculate_scores
    (maior pontuação primeiro). A posição é ordinal (1-based).
    Retorna True se criou o snapshot, False se já existia.
    """
    exists = session.query(RankingSnapshot.id).filter_by(snapshot_date=target_date).first()
    if exists:
        return False
    for idx, item in enumerate(results):
        session.add(RankingSnapshot(
            snapshot_date=target_date,
            participant_id=item["id"],
            position=idx + 1,
            points=item.get("total_points", 0),
        ))
    return True


def _ranking_as_of(session, target_date):
    """Ranking (posição + pontos) considerando APENAS os jogos finalizados
    com kickoff até `target_date`.

    SEMPRE recalcula a partir dos jogos — não depende de snapshots. Isso
    garante que o resultado reflita fielmente o estado daquele dia, mesmo se
    os snapshots do ranking tiverem sido (re)criados depois com pontos já
    atualizados (o que tornaria pontos/posição iguais em todos os dias e
    zaria a variação). Determinístico a partir dos jogos finalizados.

    Retorna lista de dicts (ordenada por pontos desc / nome asc):
      { participant_id, name, points, position }   (position é 1-based)
    """
    finished_games = session.query(Game).filter(Game.score_a.isnot(None)).all()
    games_up_to = [
        g for g in finished_games
        if g.kickoff is not None and g.kickoff.date() <= target_date
    ]
    results = calculate_scores(
        participants=session.query(Participant).all(),
        games=games_up_to,
        predictions=session.query(Prediction).all(),
        finals_predictions=session.query(FinalsPrediction).all(),
        outcome=session.query(TournamentOutcome).get(1),
        scoring_cfg=get_scoring_config_dict(session.query(ScoringConfig).get(1)),
    )
    return [
        {
            "participant_id": item["id"],
            "name": item["name"],
            "points": item.get("total_points", 0),
            "position": idx + 1,
        }
        for idx, item in enumerate(results)
    ]


def ensure_yesterday_snapshot(now=None):
    """Cria o snapshot de ontem (se ainda não existir) com o ranking atual.
    Idempotente. Usado pelo scheduler em background."""
    now = now or _now_brt()
    today = now.date() if isinstance(now, datetime) else now
    yesterday = today - timedelta(days=1)
    with session_scope() as session:
        results = _compute_ranking_results(session)
        return _capture_ranking_snapshot(session, yesterday, results)


def _seconds_until_next_snapshot(now=None):
    """Segundos até a próxima hora agendada do snapshot (default 5h)."""
    now = now or _now_brt()
    target = now.replace(hour=SNAPSHOT_HOUR, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return max(int((target - now).total_seconds()), 60)


def start_ranking_snapshot_scheduler():
    """Idempotente por processo. Roda 1x/dia, à hora agendada (default 5h),
    criando o snapshot do ranking do dia anterior.

    Por que esperar até as 5h? Para garantir que TODOS os jogos do dia anterior
    já terminaram e foram sincronizados (inclusive os que terminam logo após
    a meia-noite) — só assim o ranking de ontem é congelado com o estado final
    correto, consistente com o backfill (que atribui jogos pela data do kickoff).
    """
    global _snapshot_started
    if _snapshot_started:
        return
    _snapshot_started = True

    def _loop():
        _time_module.sleep(60)  # dá tempo do app/banco ficarem prontos
        while True:
            now = _now_brt()
            try:
                # Só cria após a hora agendada. Antes disso, apenas aguarda.
                # Idempotente: se já existe (ex.: criado por outra chamada), no-op.
                if now.hour >= SNAPSHOT_HOUR:
                    created = ensure_yesterday_snapshot(now)
                    if created:
                        _sync_log.info("📸 [snapshot] snapshot do dia anterior criado (%dh)", SNAPSHOT_HOUR)
                    # Feito por hoje: dorme até amanhã na hora agendada.
                    _time_module.sleep(_seconds_until_next_snapshot())
                    continue
            except Exception as e:
                _sync_log.error("📸 [snapshot] erro ao criar snapshot: %s", e)
            # Antes da hora OU falhou: re-checa em alguns minutos (retry rápido
            # em caso de erro; espera curta antes da hora agendada).
            _time_module.sleep(300)

    t = threading.Thread(target=_loop, daemon=True, name="bolao-snapshot-scheduler")
    t.start()
    _sync_log.info("📸 Scheduler de snapshot de ranking iniciado (diário às %dh)", SNAPSHOT_HOUR)


start_ranking_snapshot_scheduler()


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/date")
@app.route("/api/date")
def server_date():
    """Diagnóstico de fuso/horário do servidor (público, sem auth).

    Expõe várias leituras de relógio para auditar de onde vem o 'agora' usado
    pelas comparações com `Game.kickoff` (sempre em horário de Brasília/BRT,
    guardado sem tzinfo). A chave para entender problemas de notificação é
    comparar `container_local` (o que datetime.now() devolve) com `brt_naive`
    (o que as notificações de fato usam via _now_brt_naive) e o `drift_seconds`.
    """
    from datetime import timezone, timedelta as _td

    brt = timezone(_td(hours=-3))
    now_local = datetime.now()                       # relógio cru do container
    now_brt_naive = datetime.now(brt).replace(tzinfo=None)  # usado pelas notificações
    now_utc = datetime.utcnow()

    local_aware = now_local.astimezone()             # tz reconhecida pelo sistema
    offset = local_aware.utcoffset()
    drift = (now_local - now_brt_naive).total_seconds()

    if offset is not None:
        total = offset.total_seconds()
        sign = "+" if total >= 0 else "-"
        total = abs(total)
        offset_str = f"{sign}{int(total // 3600):02d}:{int((total % 3600) // 60):02d}"
        offset_hours = round(total / 3600, 2) * (1 if sign == "+" else -1)
    else:
        offset_str = None
        offset_hours = None

    aligned = abs(drift) < 1

    # Próximo jogo + janelas de lembrete, para visualizar quando disparariam.
    next_game = None
    checkpoints = []
    try:
        from .notifications import _reminder_checkpoints
        cps = sorted(_reminder_checkpoints())
        with session_scope() as session:
            g = (
                session.query(Game)
                .filter(Game.kickoff.isnot(None), Game.kickoff > now_brt_naive)
                .order_by(Game.kickoff)
                .first()
            )
            if g:
                next_game = {
                    "id": g.id,
                    "team_a": g.team_a,
                    "team_b": g.team_b,
                    "kickoff_brt": g.kickoff.isoformat(),
                }
                for c in cps:
                    checkpoints.append({
                        "checkpoint_min": c,
                        "fire_at_brt": (g.kickoff - _td(minutes=c)).isoformat(),
                    })
    except Exception as e:
        next_game = {"error": repr(e)}

    return {
        "container_local": now_local.isoformat(timespec="seconds"),
        "container_tz": local_aware.tzname(),
        "container_offset": offset_str,
        "container_offset_hours": offset_hours,
        "tz_env": os.environ.get("TZ"),
        "brt_naive": now_brt_naive.isoformat(timespec="seconds"),
        "utc": now_utc.isoformat(timespec="seconds"),
        "container_equals_brt": aligned,
        "drift_seconds": int(drift),
        "notifications_use_brt_naive": True,
        "verdict": "aligned" if aligned else "misaligned",
        "next_game": next_game,
        "pregame_checkpoints": checkpoints,
        "summary": (
            "OK: o relógio do container bate com BRT."
            if aligned else
            f"ATENÇÃO: o container está dessincronizado do BRT em {int(drift)}s; "
            "as comparações de kickoff agora usam _now_brt() e seguem corretas, "
            "mas vale revisar o TZ do container.",
        ),
    }


def verify_auth_token():
    token = None
    if 'Authorization' in request.headers:
        token = request.headers['Authorization'].split(" ")[1] if " " in request.headers['Authorization'] else request.headers['Authorization']
    
    if not token:
        return False
    
    try:
        jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        return True
    except:
        return False


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not verify_auth_token():
             return jsonify({'message': 'Token is missing or invalid!'}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["POST"])
def login():
    auth = request.get_json()
    if not auth or not auth.get('username') or not auth.get('password'):
        return jsonify({'message': 'Could not verify'}), 401
    
    with session_scope() as session:
        user = session.query(AdminUser).filter_by(username=auth.get('username')).first()
        if not user:
             return jsonify({'message': 'Could not verify'}), 401
        
        if check_password_hash(user.password_hash, auth.get('password')):
            token = jwt.encode({
                'user_id': user.id,
                'exp': datetime.utcnow() + timedelta(days=7)
            }, app.config['SECRET_KEY'], algorithm="HS256")
            return jsonify({'token': token})
    
    return jsonify({'message': 'Could not verify'}), 401


@app.route("/admin/diagnostics/notifications")
def admin_diagnostics_notifications():
    """Diagnóstico do lembrete diário 'faltam palpites de hoje'.

    Expõe:
      - status do fuso horário do processo Python (UTC vs BRT);
      - hora configurada do lembrete + checkpoints pré-jogo;
      - para cada notificação daily-missing já enviada: horário (UTC e BRT),
        jogos do dia considerados ativos pela rotina vs interpretação correta,
        quem SERIA avisado e quem palpitou tudo (não deveria receber).

    Útil para auditar reclamações do tipo 'recebi aviso mas já tinha palpitado'.
    """
    now = datetime.now()
    utcnow = datetime.utcnow()
    tz_env = os.environ.get("TZ")
    running_in_utc = now.replace(microsecond=0) == utcnow.replace(microsecond=0)

    with session_scope() as session:
        cfg = session.query(ScoringConfig).get(1)
        daily_hour = (
            int(cfg.daily_reminder_hour)
            if cfg and cfg.daily_reminder_hour is not None
            else int(os.environ.get("BOLAO_DAILY_REMINDER_HOUR", "11"))
        )

        from .notifications import _reminder_checkpoints
        checkpoints = _reminder_checkpoints()

        uid_to_p = {p.uid: p for p in session.query(Participant).all()}
        sub_uids = sorted({
            r[0] for r in session.query(PushSubscription.participant_uid).distinct().all()
        })

        # Cache de quem já palpitou (participant_id, game_id) para evitar N queries.
        predicted_pairs = {
            (pred.participant_id, pred.game_id)
            for pred in session.query(Prediction).all()
        }

        logs = (
            session.query(NotificationLog)
            .filter(NotificationLog.log_key.like("daily-missing:%"))
            .order_by(NotificationLog.created_at)
            .all()
        )

        runs = []
        for log in logs:
            day_str = log.log_key.split(":", 1)[1]
            try:
                day = datetime.strptime(day_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            # created_at é UTC (model usa datetime.utcnow).
            fired_at = log.created_at
            fired_at_brt = fired_at - timedelta(hours=3)
            start_of_day = datetime.combine(day, datetime.min.time())
            end_of_day = datetime.combine(day, datetime.max.time())

            games = (
                session.query(Game)
                .filter(Game.kickoff >= start_of_day, Game.kickoff <= end_of_day)
                .order_by(Game.kickoff)
                .all()
            )
            games_that_day = [
                {
                    "id": g.id,
                    "teams": f"{g.team_a} x {g.team_b}",
                    "kickoff": g.kickoff.strftime("%Y-%m-%d %H:%M"),
                    "has_result": g.score_a is not None,
                }
                for g in games
            ]

            # O que a rotina fez: compara kickoff (BRT) > now (UTC) -> reproduz o
            # bug quando o processo está em UTC.
            active_routine = [g for g in games if g.kickoff > fired_at]
            # Interpretação correta: ambos em BRT.
            active_correct = [g for g in games if g.kickoff > fired_at_brt]

            targeted = []
            complete = []
            for uid in sub_uids:
                p = uid_to_p.get(uid)
                if not p:
                    continue
                missing = [
                    g.id
                    for g in active_routine
                    if (p.id, g.id) not in predicted_pairs
                ]
                if missing:
                    targeted.append({"name": p.name, "uid": uid[:8], "missing": missing})
                else:
                    complete.append(p.name)

            runs.append({
                "log_key": log.log_key,
                "fired_at_utc": fired_at.strftime("%Y-%m-%d %H:%M:%S"),
                "fired_at_brt": fired_at_brt.strftime("%Y-%m-%d %H:%M:%S"),
                "configured_hour_brt": daily_hour,
                "fired_on_time_brt": fired_at_brt.hour >= daily_hour,
                "games_that_day": games_that_day,
                "games_active_per_routine": [g.id for g in active_routine],
                "games_active_correct_brt": [g.id for g in active_correct],
                "games_wrongly_excluded": [
                    g.id for g in active_correct if g not in active_routine
                ],
                "would_be_targeted": targeted,
                "subscribed_but_completed_all": complete,
            })

    return jsonify({
        "timezone": {
            "tz_env": tz_env,
            "python_now": now.strftime("%Y-%m-%d %H:%M:%S"),
            "python_utcnow": utcnow.strftime("%Y-%m-%d %H:%M:%S"),
            "running_in_utc": running_in_utc,
            "tz_applied_to_process": not running_in_utc,
            "note": (
                "Processo em UTC: o lembrete dispara ~3h cedo (11h UTC = 08h BRT) "
                "e jogos matinais (BRT) podem ser excluídos da checagem."
                if running_in_utc
                else "Processo em BRT (TZ aplicado): lembrete dispara no horário correto."
            ),
        },
        "daily_reminder_hour_brt": daily_hour,
        "pregame_checkpoints_min": checkpoints,
        "subscribed_participant_count": len(sub_uids),
        "daily_missing_runs": runs,
    })


@app.route("/admin/diagnostics/notifications/upcoming")
def admin_diagnostics_notifications_upcoming():
    """Previsão (forward-looking) das PRÓXIMAS notificações automáticas e seus
    horários previstos. Complemento do /admin/diagnostics/notifications (que
    olha para trás, mostrando o que já disparou). Útil para conferir ANTES do
    tempo se o agendamento está correto.

    Cobre os dois schedulers de push:
      1. Lembretes pré-jogo: para cada jogo futuro, em cada checkpoint
         (default 180/120/60 min antes do kickoff, com tolerância), mostra a
         janela de disparo [kickoff-C, kickoff-(C-tol)], o status
         (scheduled/active/fired/missed) e os inscritos que seriam avisados
         (os que ainda não palpitararam aquele jogo).
      2. Lembrete diário de palpites faltantes (1x/dia às HH:00 BRT): hoje e
         próximos dias até o último jogo, com horário previsto, status e nº de
         jogos do dia.

    Query params:
      hours — horizonte (h) p/ lembretes pré-jogo (default 72)
      days  — nº de dias futuros no lembrete diário (default 7)

    Público (sem auth), como os demais endpoints de diagnóstico.
    """
    from .notifications import (_reminder_checkpoints, _reminder_tolerance_min,
                                _now_brt_naive, _humanize_minutes, is_push_enabled)

    now = _now_brt_naive()
    try:
        horizon_hours = max(1, int(request.args.get("hours", "72")))
    except ValueError:
        horizon_hours = 72
    try:
        daily_days = max(1, int(request.args.get("days", "7")))
    except ValueError:
        daily_days = 7

    checkpoints = _reminder_checkpoints()
    tol = _reminder_tolerance_min()
    max_cp = max(checkpoints)
    lookback = timedelta(hours=6)          # mostra janelas "missed" até 6h atrás
    horizon_end = now + timedelta(hours=horizon_hours)

    def _fmt(dt):
        return dt.strftime("%Y-%m-%d %H:%M") if dt else None

    with session_scope() as session:
        cfg = session.query(ScoringConfig).get(1)
        daily_hour = (
            int(cfg.daily_reminder_hour)
            if cfg and cfg.daily_reminder_hour is not None
            else int(os.environ.get("BOLAO_DAILY_REMINDER_HOUR", "11"))
        )

        sub_uids = sorted({
            r[0] for r in session.query(PushSubscription.participant_uid).distinct().all()
        })
        uid_to_p = {p.uid: p for p in session.query(Participant).all()}
        predicted_pairs = {
            (pred.participant_id, pred.game_id)
            for pred in session.query(Prediction).all()
        }

        # log_key -> created_at (UTC) para pré-jogo e diário
        pregame_logs = {
            r[0]: r[1]
            for r in session.query(NotificationLog.log_key, NotificationLog.created_at)
            .filter(NotificationLog.log_key.like("pregame:%")).all()
        }
        daily_logs = {
            r[0].split(":", 1)[1]: r[1]
            for r in session.query(NotificationLog.log_key, NotificationLog.created_at)
            .filter(NotificationLog.log_key.like("daily-missing:%")).all()
        }

        # ----- 1) Lembretes pré-jogo -----------------------------------------
        games = (
            session.query(Game)
            .filter(Game.kickoff > now - timedelta(minutes=max_cp + tol))
            .filter(Game.kickoff <= horizon_end + timedelta(minutes=max_cp))
            .order_by(Game.kickoff)
            .all()
        )

        pregame = []
        pregame_summary = {"scheduled": 0, "active": 0, "fired": 0, "missed": 0}
        for game in games:
            # Alvos atuais (instantâneo): inscritos push sem palpite neste jogo
            targets = []
            for uid in sub_uids:
                p = uid_to_p.get(uid)
                if not p or (p.id, game.id) in predicted_pairs:
                    continue
                targets.append({"name": p.name, "uid": uid, "short": uid[:8]})

            for C in checkpoints:
                earliest = game.kickoff - timedelta(minutes=C)
                latest = game.kickoff - timedelta(minutes=max(C - tol, 1))
                if earliest < now - lookback or earliest > horizon_end:
                    continue  # fora da janela de interesse

                notified = [
                    t for t in targets
                    if f"pregame:{game.id}:{t['uid']}:{C}" in pregame_logs
                ]
                first_fired_brt = None
                if notified:
                    fired_utc = min(pregame_logs[f"pregame:{game.id}:{t['uid']}:{C}"] for t in notified)
                    first_fired_brt = fired_utc - timedelta(hours=3)

                window_passed = now > latest
                if window_passed:
                    status = "fired" if (not targets or len(notified) == len(targets)) else "missed"
                elif now >= earliest:
                    status = "active"
                else:
                    status = "scheduled"
                pregame_summary[status] += 1

                pregame.append({
                    "game_id": game.id,
                    "teams": f"{game.team_a} x {game.team_b}",
                    "kickoff_brt": _fmt(game.kickoff),
                    "checkpoint_min": C,
                    "checkpoint_label": _humanize_minutes(C),
                    "fire_window_brt": {"earliest": _fmt(earliest), "latest": _fmt(latest)},
                    "status": status,
                    "target_count": len(targets),
                    "already_notified_count": len(notified),
                    "first_fired_at_brt": _fmt(first_fired_brt),
                    "targets": [{"name": t["name"], "uid": t["short"]} for t in targets[:200]],
                })

        pregame.sort(key=lambda e: (e["fire_window_brt"]["earliest"], e["game_id"], e["checkpoint_min"]))

        # ----- 2) Lembrete diário de palpites faltantes ----------------------
        last_game = session.query(Game).order_by(Game.kickoff.desc()).first()
        last_date = last_game.kickoff.date() if last_game else now.date()
        end_date = min(now.date() + timedelta(days=daily_days - 1), last_date)

        daily = []
        daily_summary = {"scheduled": 0, "active": 0, "fired": 0, "missed": 0, "no_games": 0}
        d = now.date()
        while d <= end_date:
            day_key = d.isoformat()
            start_of_day = datetime.combine(d, datetime.min.time())
            end_of_day = datetime.combine(d, datetime.max.time())
            games_day = (
                session.query(Game)
                .filter(Game.kickoff >= start_of_day, Game.kickoff <= end_of_day)
                .order_by(Game.kickoff).all()
            )
            fire_at = datetime.combine(d, datetime.min.time()) + timedelta(hours=daily_hour)

            entry = {
                "date": day_key,
                "fire_at_brt": _fmt(fire_at),
                "games_that_day": len(games_day),
                "games_open_now": None,
                "status": None,
                "fired_at_brt": None,
                "target_count": 0,
                "targets": [],
            }

            if day_key in daily_logs:
                entry["status"] = "fired"
                entry["fired_at_brt"] = (daily_logs[day_key] - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
            elif d < now.date():
                entry["status"] = "missed" if games_day else "no_games"
            elif not games_day:
                entry["status"] = "no_games"
            elif d == now.date() and now >= fire_at:
                entry["status"] = "active"  # dispara no próximo tick (<=60s)
            else:
                entry["status"] = "scheduled"

            # Alvos: só computa para HOJE (outros dias o palpite ainda muda)
            if d == now.date() and games_day:
                open_games = [g for g in games_day if g.kickoff > now]
                entry["games_open_now"] = len(open_games)
                for uid in sub_uids:
                    p = uid_to_p.get(uid)
                    if not p:
                        continue
                    missing = [g.id for g in open_games if (p.id, g.id) not in predicted_pairs]
                    if missing:
                        entry["targets"].append({"name": p.name, "uid": uid[:8], "missing_games": missing})
                entry["target_count"] = len(entry["targets"])

            daily_summary[entry["status"]] = daily_summary.get(entry["status"], 0) + 1
            daily.append(entry)
            d += timedelta(days=1)

    return jsonify({
        "now_brt": now.strftime("%Y-%m-%d %H:%M:%S"),
        "push_enabled": is_push_enabled(),
        "config": {
            "pregame_checkpoints_min": checkpoints,
            "pregame_tolerance_min": tol,
            "notify_interval_seconds": NOTIFY_INTERVAL_SECONDS,
            "daily_reminder_hour_brt": daily_hour,
            "horizon_hours": horizon_hours,
            "daily_days": daily_days,
        },
        "summary": {"pregame": pregame_summary, "daily": daily_summary},
        "pregame": pregame,
        "daily": daily,
    })


@app.route("/change-password", methods=["POST"])
@token_required
def change_password():
    data = request.get_json()
    new_password = data.get('new_password')
    if not new_password:
        return jsonify({'message': 'New password required'}), 400
        
    with session_scope() as session:
        user = session.query(AdminUser).filter_by(username="admin").first()
        if user:
            user.password_hash = generate_password_hash(new_password)
            return jsonify({'message': 'Password updated successfully'})
            
    return jsonify({'message': 'User not found'}), 404


# Participants CRUD
@app.route("/participants", methods=["GET", "POST"])
def participants():
    with session_scope() as session:
        if request.method == "GET":
            is_admin = verify_auth_token()
            rows = session.query(Participant).all()
            if is_admin:
                return jsonify([serialize_participant(row) for row in rows])
            else:
                return jsonify([{"id": row.id, "name": row.name} for row in rows])

        if not verify_auth_token():
            return jsonify({'message': 'Unauthorized'}), 401

        data = request.get_json()
        participant = Participant(name=data.get("name"), email=data.get("email"))
        session.add(participant)
        session.flush()
        return serialize_participant(participant), 201


@app.route("/participants/<int:participant_id>", methods=["GET", "PUT", "DELETE"])
def participant_detail(participant_id: int):
    with session_scope() as session:
        participant = session.get(Participant, participant_id)
        if not participant:
            return {"error": "Participant not found"}, 404

        if request.method == "GET":
            return serialize_participant(participant)

        if not verify_auth_token():
            return jsonify({'message': 'Unauthorized'}), 401

        if request.method == "DELETE":
            session.delete(participant)
            return "", 204

        data = request.get_json()
        participant.name = data.get("name", participant.name)
        participant.email = data.get("email", participant.email)
        return serialize_participant(participant)


# Games CRUD
@app.route("/games", methods=["GET", "POST"])
def games():
    with session_scope() as session:
        if request.method == "GET":
            rows = session.query(Game).order_by(Game.kickoff).all()
            return jsonify([serialize_game(row) for row in rows])

        if not verify_auth_token():
            return jsonify({'message': 'Unauthorized'}), 401

        data = request.get_json()
        game = Game(
            kickoff=parse_date(data.get("kickoff")),
            team_a=data.get("team_a"),
            team_b=data.get("team_b"),
            score_a=data.get("score_a"),
            score_b=data.get("score_b"),
            espn_id=data.get("espn_id"),
        )
        session.add(game)
        session.flush()
        return serialize_game(game), 201


@app.route("/games/all", methods=["DELETE"])
@token_required
def delete_all_games():
    """Delete all games and their predictions."""
    with session_scope() as session:
        # Delete all predictions first (foreign key constraint)
        session.query(Prediction).delete()
        # Delete all games
        count = session.query(Game).delete()
        return {"deleted": count}


@app.route("/games/import", methods=["POST"])
@token_required
def import_games():
    """Import multiple games from JSON array. Skips duplicates by team_a + team_b + kickoff."""
    data = request.get_json()
    if not isinstance(data, list):
        return {"error": "Expected a JSON array"}, 400

    imported = 0
    skipped = 0
    with session_scope() as session:
        for item in data:
            kickoff = item.get("kickoff")
            team_a = item.get("team_a")
            team_b = item.get("team_b")

            if not kickoff or not team_a or not team_b:
                continue

            existing = None
            espn_id = item.get("espn_id")
            kickoff_dt = parse_date(kickoff)
            # Dedupe por espn_id (chave estável) quando presente; senão pelo
            # trio team_a + team_b + kickoff (comportamento legado).
            if espn_id:
                existing = session.query(Game).filter(Game.espn_id == espn_id).first()
            if not existing:
                existing = session.query(Game).filter(
                    Game.team_a == team_a,
                    Game.team_b == team_b,
                    Game.kickoff == kickoff_dt,
                ).first()

            if existing:
                skipped += 1
                continue

            game = Game(
                kickoff=kickoff_dt,
                team_a=team_a,
                team_b=team_b,
                score_a=item.get("score_a"),
                score_b=item.get("score_b"),
                espn_id=espn_id,
            )
            session.add(game)
            imported += 1

    return {"imported": imported, "skipped": skipped}


@app.route("/games/<int:game_id>", methods=["GET", "PUT", "DELETE"])
def game_detail(game_id: int):
    with session_scope() as session:
        game = session.get(Game, game_id)
        if not game:
            return {"error": "Game not found"}, 404

        if request.method == "GET":
            return serialize_game(game)

        if not verify_auth_token():
            return jsonify({'message': 'Unauthorized'}), 401

        if request.method == "DELETE":
            session.delete(game)
            return "", 204

        data = request.get_json()
        if "kickoff" in data:
            game.kickoff = parse_date(data.get("kickoff"))
        game.team_a = data.get("team_a", game.team_a)
        game.team_b = data.get("team_b", game.team_b)
        game.score_a = data.get("score_a", game.score_a)
        game.score_b = data.get("score_b", game.score_b)
        if "espn_id" in data:
            game.espn_id = data.get("espn_id")
        # Sincroniza status quando o admin define/remove placar manualmente
        if "score_a" in data and "score_b" in data:
            if game.score_a is not None and game.score_b is not None:
                game.status = "finished"
            else:
                game.status = "scheduled"
        return serialize_game(game)


@app.route("/games/result", methods=["PUT"])
@token_required
def game_result():
    """Update the result of a game by team abbreviations."""
    data = request.get_json()

    team_a = data.get("team_a", "").strip().upper()
    team_b = data.get("team_b", "").strip().upper()
    score_a = data.get("score_a")
    score_b = data.get("score_b")
    date_str = data.get("date")  # Opcional: formato "YYYY-MM-DD"

    if not team_a or not team_b:
        return {"error": "Both team_a and team_b are required (3-letter country codes)"}, 400

    if score_a is None or score_b is None:
        return {"error": "Both score_a and score_b are required"}, 400

    if not isinstance(score_a, int) or score_a < 0:
        return {"error": "score_a must be a non-negative integer"}, 400
    if not isinstance(score_b, int) or score_b < 0:
        return {"error": "score_b must be a non-negative integer"}, 400

    with session_scope() as session:
        # Busca jogos entre os dois times (em qualquer ordem)
        query = session.query(Game).filter(
            ((Game.team_a.ilike(f"%{team_a}%")) & (Game.team_b.ilike(f"%{team_b}%"))) |
            ((Game.team_a.ilike(f"%{team_b}%")) & (Game.team_b.ilike(f"%{team_a}%")))
        )

        # Filtra por data se fornecida
        if date_str:
            try:
                from sqlalchemy import func
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                query = query.filter(func.date(Game.kickoff) == target_date)
            except ValueError:
                return {"error": "Invalid date format. Use YYYY-MM-DD"}, 400

        games = query.order_by(Game.kickoff).all()

        if not games:
            msg = f"Game not found between {team_a} and {team_b}"
            if date_str:
                msg += f" on {date_str}"
            return {"error": msg}, 404

        if len(games) > 1:
            # Se houver múltiplos jogos, pega o primeiro sem resultado
            game = next((g for g in games if g.score_a is None), None)
            if not game:
                # Todos já têm resultado, pega o último
                game = games[-1]
        else:
            game = games[0]

        # Ajusta o placar conforme a ordem dos times no jogo
        if team_a.upper() in game.team_a.upper():
            game.score_a = score_a
            game.score_b = score_b
        else:
            game.score_a = score_b
            game.score_b = score_a

        game.status = "finished"
        return serialize_game(game)


# Predictions
@app.route("/predictions", methods=["POST", "GET"])
def predictions():
    with session_scope() as session:
        if request.method == "GET":
            participant_uid = request.args.get("participant_uid")
            game_id = request.args.get("game_id")
            is_admin = verify_auth_token()
            
            query = session.query(Prediction)
            
            # Bloqueia listagem geral para não-admins para evitar bisbilhoteiros
            if not is_admin and not participant_uid and not game_id:
                return jsonify([])
            
            if participant_uid:
                participant = session.query(Participant).filter_by(uid=participant_uid).first()
                if not participant:
                    return {"error": "Participant not found"}, 404
                query = query.filter(Prediction.participant_id == participant.id)
            
            if game_id:
                # Se não for admin e não estiver filtrando pelo próprio participante, 
                # só permite ver palpites de jogos que já começaram.
                if not is_admin and not participant_uid:
                    game = session.get(Game, game_id)
                    if game and game.kickoff > _now_brt():
                        return jsonify([]) # Esconde palpites alheios antes do jogo
                
                query = query.filter(Prediction.game_id == game_id)
                
            rows = query.all()
            
            results = []
            for row in rows:
                data = serialize_prediction(row)
                # Inclui o nome do participante para facilitar exibição no admin
                data["participant_name"] = row.participant.name if row.participant else "Desconhecido"
                results.append(data)
                
            return jsonify(results)

        data = request.get_json()
        participant_uid = data.get("participant_uid")
        participant = session.query(Participant).filter_by(uid=participant_uid).first()
        if not participant:
            return {"error": "Participant not found"}, 404

        game = session.get(Game, data.get("game_id"))
        if not game:
            return {"error": "Game not found"}, 404

        if game.kickoff <= _now_brt():
            return {"error": "Predictions are closed for this game"}, 400

        existing = (
            session.query(Prediction)
            .filter_by(participant_id=participant.id, game_id=game.id)
            .first()
        )
        if existing:
            existing.goals_a = data.get("goals_a", existing.goals_a)
            existing.goals_b = data.get("goals_b", existing.goals_b)
            prediction = existing
        else:
            prediction = Prediction(
                participant_id=participant.id,
                game_id=game.id,
                goals_a=data.get("goals_a"),
                goals_b=data.get("goals_b"),
            )
            session.add(prediction)
        session.flush()
        return serialize_prediction(prediction), 201


def _knockout_started(session) -> bool:
    """True quando o mata-mata já começou (fase eliminatória em andamento).

    Detecção baseada na estrutura do torneio, sem campo de "fase" no banco:
      - A Copa 2026 (48 times, 12 grupos de 4) tem 72 jogos na fase de grupos
        e exatamente 32 no mata-mata (fase de 32 = 16, oitavas = 8, quartas = 4,
        semifinal = 2, final = 1, disputa de 3º = 1).
      - O primeiro jogo eliminatório é o (total - 32)-ésimo por kickoff
        (índice 0-based), pois TODA a fase de grupos acaba antes do mata-mata.
      - O mata-mata "começou" quando o kickoff desse jogo já passou.

    Robusto: funciona enquanto houver ao menos 33 jogos cadastrados.
    """
    games = (
        session.query(Game)
        .filter(Game.kickoff.isnot(None))
        .order_by(Game.kickoff)
        .all()
    )
    knockout_count = 32
    if len(games) <= knockout_count:
        return False
    first_knockout = games[len(games) - knockout_count]
    return first_knockout.kickoff <= _now_brt()


@app.route("/finals_predictions/board", methods=["GET"])
def finals_predictions_board():
    """Board público dos palpites finais (campeão/vice/3º/4º) de TODOS.

    Só expõe os palpites quando o mata-mata já começou — nesse ponto o prazo
    de palpites já encerrou, então ninguém pode mais alterar o seu, e faz
    sentido liberar a visualização para comparar com os outros.

    Não expõe credenciais sensíveis: retorna apenas o nome do participante e
    os 4 times (sem uid, email ou participant_id). Quando o mata-mata ainda
    não começou, retorna {visible: false} para o front ocultar a área.
    """
    with session_scope() as session:
        visible = _knockout_started(session)
        if not visible:
            return jsonify({
                "visible": False,
                "outcome": None,
                "predictions": [],
            })

        rows = (
            session.query(FinalsPrediction)
            .join(Participant, Participant.id == FinalsPrediction.participant_id)
            .order_by(Participant.name)
            .all()
        )
        outcome = session.query(TournamentOutcome).get(1)

        return jsonify({
            "visible": True,
            "outcome": serialize_outcome(outcome) if outcome else None,
            "predictions": [
                {
                    "name": r.participant.name if r.participant else "Desconhecido",
                    "champion": r.champion,
                    "runner_up": r.runner_up,
                    "third_place": r.third_place,
                    "fourth_place": r.fourth_place,
                }
                for r in rows
            ],
        })


@app.route("/finals_predictions", methods=["POST", "GET"])
def finals_predictions():
    with session_scope() as session:
        if request.method == "GET":
            participant_uid = request.args.get("participant_uid")
            is_admin = verify_auth_token()
            
            # Bloqueia listagem geral para não-admins
            if not is_admin and not participant_uid:
                return jsonify([])
                
            query = session.query(FinalsPrediction)
            if participant_uid:
                query = query.join(Participant).filter(Participant.uid == participant_uid)
            rows = query.all()
            return jsonify([serialize_finals(row) for row in rows])

        data = request.get_json()
        participant_uid = data.get("participant_uid")
        participant = session.query(Participant).filter_by(uid=participant_uid).first()
        if not participant:
            return {"error": "Participant not found"}, 404

        # Check finals deadline
        config = session.query(ScoringConfig).get(1)
        if config and getattr(config, 'finals_deadline', None):
            if _now_brt() > config.finals_deadline:
                return {"error": "O prazo para palpites finais já encerrou."}, 400

        record = (
            session.query(FinalsPrediction)
            .filter_by(participant_id=participant.id)
            .first()
        )
        if not record:
            record = FinalsPrediction(participant_id=participant.id)
            session.add(record)

        record.champion = data.get("champion", record.champion)
        record.runner_up = data.get("runner_up", record.runner_up)
        record.third_place = data.get("third_place", record.third_place)
        record.fourth_place = data.get("fourth_place", record.fourth_place)
        session.flush()
        return serialize_finals(record), 201


@app.route("/tournament_outcome", methods=["GET", "PUT"])
def tournament_outcome():
    with session_scope() as session:
        outcome = session.query(TournamentOutcome).get(1)
        if not outcome:
            outcome = TournamentOutcome(id=1)
            session.add(outcome)
            session.flush()

        if request.method == "GET":
            return serialize_outcome(outcome)

        if not verify_auth_token():
            return jsonify({'message': 'Unauthorized'}), 401

        data = request.get_json()
        outcome.champion = data.get("champion", outcome.champion)
        outcome.runner_up = data.get("runner_up", outcome.runner_up)
        outcome.third_place = data.get("third_place", outcome.third_place)
        outcome.fourth_place = data.get("fourth_place", outcome.fourth_place)
        return serialize_outcome(outcome)


@app.route("/scores", methods=["GET"])
def scores():
    with session_scope() as session:
        results = _compute_ranking_results(session)
        # Não expõe o `uid` (credencial de autenticação) na resposta pública.
        for item in results:
            item.pop("uid", None)

        # Garante o snapshot de ontem (idempotente) — mas SOMENTE após a hora
        # agendada (default 5h). Isso garante que todos os jogos de ontem já
        # terminaram e foram sincronizados antes de congelar o ranking,
        # mantendo consistência com o backfill (jogos atribuídos pela data do
        # kickoff) e com o scheduler diário. Robustez caso o scheduler não rode.
        today = _now_brt().date()
        try:
            if _now_brt().hour >= SNAPSHOT_HOUR:
                yesterday = today - timedelta(days=1)
                _capture_ranking_snapshot(session, yesterday, results)
                session.flush()  # garante visibilidade na leitura de referência abaixo
        except Exception as e:
            _sync_log.error("📸 [scores] erro ao garantir snapshot: %s", e)

        # Variação de posição vs snapshot de referência = dia mais recente
        # estritamente anterior a hoje (geralmente ontem).
        from sqlalchemy import func
        latest_date = session.query(func.max(RankingSnapshot.snapshot_date)).filter(
            RankingSnapshot.snapshot_date < today
        ).scalar()
        ref_map = {}
        if latest_date:
            rows = session.query(RankingSnapshot).filter_by(snapshot_date=latest_date).all()
            ref_map = {r.participant_id: r.position for r in rows}

        for idx, item in enumerate(results):
            current_pos = idx + 1
            prev_pos = ref_map.get(item["id"])
            # variation = posicao_anterior - posicao_atual
            #   > 0 : subiu (verde ↑)
            #   < 0 : desceu (vermelho ↓)
            #   0   : manteve
            #   None: sem histórico (participante novo / ainda não há snapshot)
            item["variation"] = (prev_pos - current_pos) if prev_pos is not None else None

        return jsonify(results)


@app.route("/ranking", methods=["GET"])
def ranking():
    """Ranking simplificado: apenas nome e pontuação, do maior para o menor."""
    with session_scope() as session:
        results = _compute_ranking_results(session)
        # calculate_scores já ordena por pontos (desc) e nome (asc)
        return jsonify([
            {"name": item["name"], "points": item["total_points"]}
            for item in results
        ])


@app.route("/scores/daily", methods=["GET"])
def scores_daily():
    """Ranking dos pontos ganhos em um dia específico ("melhor do dia").

    Considera APENAS os jogos finalizados cujo kickoff caiu no dia escolhido
    — não acumula rodadas anteriores nem conta palpites de finais (que não
    têm um dia associado). É o ranking de performance daquele dia.

    Query param:
      - date (ou "data"): "YYYY-MM-DD". Default: o dia mais recente que
        teve ao menos um jogo finalizado. Se ainda não há jogos
        finalizados, usa a data de hoje (ranking vazio).

    Retorna:
      - date: o dia efetivamente usado (ISO)
      - available_dates: lista de dias (desc) com jogos finalizados, para
        alimentar o seletor de data no front
      - ranking: [{ id, name, total_points }] ordenado (maior primeiro)
    """
    date_str = request.args.get("date") or request.args.get("data")

    with session_scope() as session:
        # Dias que tiveram ao menos um jogo finalizado (pela data do kickoff).
        finished_games = session.query(Game).filter(Game.score_a.isnot(None)).all()
        available = sorted(
            {g.kickoff.date() for g in finished_games if g.kickoff is not None},
            reverse=True,
        )

        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return {"error": "Invalid date format. Use YYYY-MM-DD"}, 400
        elif available:
            target_date = available[0]
        else:
            target_date = _now_brt().date()

        config = session.query(ScoringConfig).get(1)
        scoring_cfg = get_scoring_config_dict(config)
        results = calculate_daily_scores(
            participants=session.query(Participant).all(),
            games=session.query(Game).all(),
            predictions=session.query(Prediction).all(),
            target_date=target_date,
            scoring_cfg=scoring_cfg,
        )

        return jsonify({
            "date": target_date.isoformat(),
            "available_dates": [d.isoformat() for d in available],
            "ranking": results,
        })


@app.route("/ranking/daily", methods=["GET"])
def ranking_daily():
    """Ranking de um dia específico com a variação de posição vs dia anterior.

    Query param:
      - date (ou "data"): "YYYY-MM-DD" (default: hoje).

    Retorna, do maior para o menor pontuador naquele dia:
      - name: nome do participante
      - points: pontuação acumulada até o fim daquele dia
      - variacao: variação de posição em relação ao dia anterior,
        formatada como "+1" (subiu), "-2" (desceu) ou "0" (manteve/
        sem histórico anterior).
    """
    date_str = request.args.get("date") or request.args.get("data")
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return {"error": "Invalid date format. Use YYYY-MM-DD"}, 400
    else:
        target_date = _now_brt().date()

    with session_scope() as session:
        today_ranking = _ranking_as_of(session, target_date)
        prev_ranking = _ranking_as_of(session, target_date - timedelta(days=1))
        prev_pos = {item["participant_id"]: item["position"] for item in prev_ranking}

        result = []
        for item in today_ranking:
            before = prev_pos.get(item["participant_id"])
            if before is None:
                variacao = "0"
            else:
                # delta = posicao_anterior - posicao_atual
                #   > 0 : subiu (ex.: "+1")   < 0 : desceu (ex.: "-2")
                delta = before - item["position"]
                variacao = f"{delta:+d}" if delta else "0"
            result.append({
                "name": item["name"],
                "points": item["points"],
                "variacao": variacao,
            })
        return jsonify(result)

@app.route("/ranking/snapshot", methods=["POST"])
@token_required
def ranking_snapshot():
    """Captura/força um snapshot do ranking para uma data (admin).

    Body (opcional):
      - date: "YYYY-MM-DD" (default: ontem). Útil para backfill de dias
        anteriores ou para reprocessar um snapshot.
    Retorna a data do snapshot criado/ignorado e a lista de posições.
    """
    data = request.get_json(silent=True) or {}
    date_str = data.get("date")
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return {"error": "Invalid date format. Use YYYY-MM-DD"}, 400
    else:
        target_date = _now_brt().date() - timedelta(days=1)

    with session_scope() as session:
        results = _compute_ranking_results(session)
        created = _capture_ranking_snapshot(session, target_date, results)
        return jsonify({
            "created": created,
            "snapshot_date": target_date.isoformat(),
            "positions": [
                {"participant_id": item["id"], "name": item["name"],
                 "position": idx + 1, "points": item.get("total_points", 0)}
                for idx, item in enumerate(results)
            ],
        })


@app.route("/ranking/backfill", methods=["POST"])
@token_required
def ranking_backfill():
    """Recria o histórico de snapshots do ranking a partir dos jogos finalizados.

    Para cada dia em que houve jogo finalizado (data do kickoff, anterior a
    hoje), recalcula o ranking considerando APENAS os jogos terminados até
    aquele dia e congela um snapshot. Assim a coluna de variação (↑/↓) passa
    a ter uma base histórica real desde o primeiro jogo.

    Útil quando o recurso foi adicionado depois do início do torneio.
    Idempotente: pode ser executado quantas vezes quiser — sempre reconstrói
    do zero os snapshots históricos.
    """
    with session_scope() as session:
        finished_games = session.query(Game).filter(Game.score_a.isnot(None)).all()
        today = _now_brt().date()
        # Datas distintas de jogos finalizados (dia do kickoff) anteriores a hoje.
        gamedays = sorted({
            g.kickoff.date() for g in finished_games
            if g.kickoff is not None and g.kickoff.date() < today
        })

        participants = session.query(Participant).all()
        predictions = session.query(Prediction).all()
        finals_predictions = session.query(FinalsPrediction).all()
        outcome = session.query(TournamentOutcome).get(1)
        config = session.query(ScoringConfig).get(1)
        scoring_cfg = get_scoring_config_dict(config)

        # Reconstrói do zero os snapshots históricos.
        session.query(RankingSnapshot).delete()

        summary = []
        for d in gamedays:
            games_up_to = [g for g in finished_games if g.kickoff.date() <= d]
            results = calculate_scores(
                participants=participants,
                games=games_up_to,
                predictions=predictions,
                finals_predictions=finals_predictions,
                outcome=outcome,
                scoring_cfg=scoring_cfg,
            )
            for idx, item in enumerate(results):
                session.add(RankingSnapshot(
                    snapshot_date=d,
                    participant_id=item["id"],
                    position=idx + 1,
                    points=item.get("total_points", 0),
                ))
            summary.append({
                "date": d.isoformat(),
                "games_counted": len(games_up_to),
                "top3": [
                    {"position": i + 1, "name": r["name"], "points": r["total_points"]}
                    for i, r in enumerate(results[:3])
                ],
            })

        _sync_log.info("📸 [backfill] %d snapshot(s) históricos recriados", len(gamedays))
        return jsonify({
            "rebuilt_dates": len(gamedays),
            "dates": [d.isoformat() for d in gamedays],
            "summary": summary,
        })


@app.route("/reminders/force", methods=["POST"])
@token_required
def reminders_force():
    """Dispara os lembretes de palpite (3h/2h/1h antes) imediatamente.

    Executa a MESMA rotina do scheduler automático, mas sob demanda. Útil para
    testar a notificação sem esperar o próximo ciclo, ou para garantir o
    disparo após uma indisponibilidade do servidor. Idempotente (respeita o
    log de checkpoints já enviados).
    """
    from .notifications import dispatch_pregame_reminders
    result = dispatch_pregame_reminders()
    return jsonify(result)


@app.route("/me", methods=["GET"])
def me():
    """Retorna apenas id e nome do dono do participant_uid.

    Não expõe dados de outros participantes (usado para destacar a própria
    linha no ranking e obter o próprio nome sem vazar uids alheios).
    """
    participant_uid = request.args.get("participant_uid")
    if not participant_uid:
        return {"error": "participant_uid is required"}, 400
    with session_scope() as session:
        participant = session.query(Participant).filter_by(uid=participant_uid).first()
        if not participant:
            return {"error": "Participant not found"}, 404
        return jsonify({"id": participant.id, "name": participant.name})


@app.route("/scores/<int:participant_id>/details", methods=["GET"])
def score_details(participant_id: int):
    with session_scope() as session:
        participant = session.query(Participant).get(participant_id)
        if not participant:
            return {"error": "Participant not found"}, 404

        games = session.query(Game).all()
        predictions = session.query(Prediction).filter_by(participant_id=participant_id).all()
        finals_prediction = session.query(FinalsPrediction).filter_by(participant_id=participant_id).first()
        outcome = session.query(TournamentOutcome).get(1)
        config = session.query(ScoringConfig).get(1)
        scoring_cfg = get_scoring_config_dict(config)

        # Filtro de dia (opcional): quando passado, mostra só os pontos ganhos
        # naquele dia (modo "Do Dia" do ranking) e ignora finais (que não têm
        # um dia associado). Sem `date`, mostra o histórico completo.
        date_str = request.args.get("date")
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return {"error": "Invalid date format. Use YYYY-MM-DD"}, 400
            games = [
                g for g in games
                if g.score_a is not None
                and g.kickoff is not None
                and g.kickoff.date() == target_date
            ]
            outcome = None

        from .scoring import get_score_breakdown
        breakdown = get_score_breakdown(
            participant=participant,
            games=games,
            predictions=predictions,
            finals_prediction=finals_prediction,
            outcome=outcome,
            scoring_cfg=scoring_cfg,
        )

        return jsonify({
            "participant": {
                "name": participant.name,
                "total_points": sum(item["points"] for item in breakdown)
            },
            "breakdown": breakdown
        })


@app.route("/score_preview", methods=["POST"])
def score_preview():
    data = request.get_json()
    prediction_stub = Prediction(goals_a=data.get("goals_a"), goals_b=data.get("goals_b"))
    game_stub = Game(score_a=data.get("score_a"), score_b=data.get("score_b"))
    with session_scope() as session:
        config = session.query(ScoringConfig).get(1)
        scoring_cfg = get_scoring_config_dict(config)
    return {"points": score_prediction(prediction_stub, game_stub, scoring_cfg=scoring_cfg)}


@app.route("/scoring_config", methods=["GET", "PUT"])
def scoring_config():
    with session_scope() as session:
        config = session.query(ScoringConfig).get(1)
        if not config:
            config = ScoringConfig(id=1)
            session.add(config)
            session.flush()

        if request.method == "GET":
            return jsonify(serialize_scoring_config(config))

        if not verify_auth_token():
            return jsonify({'message': 'Unauthorized'}), 401

        data = request.get_json()
        for field in ("exact_score", "correct_result", "partial_score",
                      "champion", "runner_up", "third_place", "fourth_place"):
            if field in data:
                value = data[field]
                if not isinstance(value, int) or value < 0:
                    return {"error": f"{field} must be a non-negative integer"}, 400
                setattr(config, field, value)
        if "daily_reminder_hour" in data:
            value = data["daily_reminder_hour"]
            if not isinstance(value, int) or not (0 <= value <= 23):
                return {"error": "daily_reminder_hour must be an integer between 0 and 23"}, 400
            config.daily_reminder_hour = value
        if "finals_deadline" in data:
            value = data["finals_deadline"]
            if value is None or value == "":
                config.finals_deadline = None
            else:
                try:
                    config.finals_deadline = parse_date(value)
                except (ValueError, TypeError):
                    return {"error": "Invalid finals_deadline format. Use ISO 8601."}, 400
        return jsonify(serialize_scoring_config(config))


@app.route("/backup/export", methods=["GET"])
@token_required
def export_backup():
    ensure_db_exists()
    return send_file(DB_PATH, as_attachment=True, download_name="bolao_backup.sqlite")


@app.route("/backup/import", methods=["POST"])
@token_required
def import_backup():
    if "file" not in request.files:
        return {"error": "Missing file"}, 400
    file = request.files["file"]
    ensure_db_exists()
    file.save(DB_PATH)
    return {"status": "imported"}


def serialize_participant(participant: Participant):
    return {
        "id": participant.id,
        "name": participant.name,
        "email": participant.email,
        "uid": participant.uid,
        "created_at": participant.created_at.isoformat() if participant.created_at else None,
    }


def serialize_game(game: Game):
    return {
        "id": game.id,
        "kickoff": game.kickoff.isoformat() if game.kickoff else None,
        "team_a": game.team_a,
        "team_b": game.team_b,
        "score_a": game.score_a,
        "score_b": game.score_b,
        "status": game.status or "scheduled",
        "espn_id": game.espn_id,
    }


def serialize_prediction(prediction: Prediction):
    return {
        "id": prediction.id,
        "participant_id": prediction.participant_id,
        "game_id": prediction.game_id,
        "goals_a": prediction.goals_a,
        "goals_b": prediction.goals_b,
    }


def serialize_finals(prediction: FinalsPrediction):
    # Nome do participante vem do relacionamento (None se não estiver carregado).
    participant_name = None
    if prediction.participant is not None:
        participant_name = prediction.participant.name
    return {
        "id": prediction.id,
        "participant_id": prediction.participant_id,
        "participant_name": participant_name,
        "champion": prediction.champion,
        "runner_up": prediction.runner_up,
        "third_place": prediction.third_place,
        "fourth_place": prediction.fourth_place,
    }


def serialize_outcome(outcome: TournamentOutcome):
    return {
        "champion": outcome.champion,
        "runner_up": outcome.runner_up,
        "third_place": outcome.third_place,
        "fourth_place": outcome.fourth_place,
    }


def serialize_scoring_config(config: ScoringConfig):
    return {
        "exact_score": config.exact_score,
        "correct_result": config.correct_result,
        "partial_score": config.partial_score,
        "champion": config.champion,
        "runner_up": config.runner_up,
        "third_place": config.third_place,
        "fourth_place": config.fourth_place,
        "finals_deadline": config.finals_deadline.isoformat() if getattr(config, 'finals_deadline', None) else None,
        "daily_reminder_hour": getattr(config, 'daily_reminder_hour', 11),
    }


@app.route("/games/fix-kickoffs", methods=["POST"])
@token_required
def fix_kickoffs():
    """Apply kickoff corrections to match the official FIFA schedule."""
    corrections = [
        {"team_a": "Austrália", "team_b": "Turquia", "kickoff": "2026-06-14T01:00:00"},
        {"team_a": "Uzbequistão", "team_b": "Colômbia", "kickoff": "2026-06-17T21:00:00"},
        {"team_a": "Turquia", "team_b": "Paraguai", "kickoff": "2026-06-20T00:00:00"},
        {"team_a": "Brasil", "team_b": "Haiti", "kickoff": "2026-06-19T21:30:00"},
        {"team_a": "Tunísia", "team_b": "Japão", "kickoff": "2026-06-21T01:00:00"},
        {"team_a": "Egito", "team_b": "Irã", "kickoff": "2026-06-27T00:00:00"},
        {"team_a": "Nova Zelândia", "team_b": "Bélgica", "kickoff": "2026-06-27T00:00:00"},
    ]

    updated = []
    skipped = []

    with session_scope() as session:
        for fix in corrections:
            game = session.query(Game).filter(
                Game.team_a == fix["team_a"],
                Game.team_b == fix["team_b"],
            ).first()

            if not game:
                skipped.append({"match": f"{fix['team_a']} x {fix['team_b']}", "reason": "not found"})
                continue

            old_kickoff = game.kickoff.isoformat() if game.kickoff else None
            new_kickoff_dt = datetime.fromisoformat(fix["kickoff"])

            if game.kickoff == new_kickoff_dt:
                skipped.append({"match": f"{fix['team_a']} x {fix['team_b']}", "reason": "already correct"})
                continue

            game.kickoff = new_kickoff_dt
            updated.append({
                "match": f"{fix['team_a']} x {fix['team_b']}",
                "old_kickoff": old_kickoff,
                "new_kickoff": fix["kickoff"],
            })

    return {"updated": updated, "skipped": skipped, "total": len(corrections)}


def parse_date(value: str) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)



@app.route("/sync", methods=["POST"])
@token_required
def sync_results():
    """Dispara sincronização de resultados via ESPN API.

    Usa a mesma lógica do scheduler automático — só atualiza jogos
    finalizados cujo kickoff já passou (nunca jogos futuros).
    """
    all_results = _do_sync()
    updated = sum(1 for r in all_results if r.get("status") == "updated")
    notified = 0
    try:
        from .notifications import dispatch_result_notifications
        notified = dispatch_result_notifications(all_results).get("sent", 0)
    except Exception as ne:
        _sync_log.error("🔔 [sync] erro ao notificar resultados: %s", ne)
    return {
        "status": "ok",
        "updated": updated,
        "notified": notified,
        "total_checked": len(all_results),
        "results": all_results,
    }


@app.route("/live")
def live_matches():
    """Endpoint público: retorna jogos ao vivo e próximo jogo da ESPN."""
    from .sync_results import fetch_espn_games, parse_espn_event

    now_brt = _now_brt()
    today = now_brt.strftime("%Y-%m-%d")
    tomorrow = (now_brt + timedelta(days=1)).strftime("%Y-%m-%d")

    live_games = []
    next_game = None

    for d in [today, tomorrow]:
        try:
            espn_events = fetch_espn_games(d)
        except Exception:
            continue

        for event in espn_events:
            parsed = parse_espn_event(event)
            if not parsed:
                continue

            # Traduz detail para português
            detail_pt = parsed["detail"]
            if parsed["state"] == "pre" and parsed.get("date"):
                try:
                    from datetime import timezone as _tz
                    dt = datetime.fromisoformat(parsed["date"].replace("Z", "+00:00"))
                    local_dt = dt.astimezone(_tz(timedelta(hours=-3)))  # Brasília
                    dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
                    dia = dias[local_dt.weekday()]
                    detail_pt = f"{dia}, {local_dt.strftime('%d/%m %H:%M')}"
                except Exception:
                    detail_pt = parsed["detail"]
            elif parsed["state"] == "post":
                detail_pt = "Finalizado"

            game_info = {
                "home": parsed["home"]["name_pt"],
                "home_flag": parsed["home"]["name_pt"],
                "away": parsed["away"]["name_pt"],
                "away_flag": parsed["away"]["name_pt"],
                "score_a": parsed["home"]["score"],
                "score_b": parsed["away"]["score"],
                "state": parsed["state"],
                "clock": parsed["display_clock"],
                "detail": detail_pt,
                "date": parsed.get("date", ""),
            }

            if parsed["state"] == "in":
                live_games.append(game_info)
            elif parsed["state"] == "pre" and next_game is None:
                next_game = game_info
            elif parsed["state"] == "post" and parsed["is_full_time"]:
                # Inclui jogos finalizados de hoje também (últimas 3h)
                pass

        if live_games:
            break  # Se já tem jogos ao vivo, não precisa de amanhã

    # Busca palpites de cada jogo ao vivo (se houver).
    # IMPORTANTE: a lista de palpites deve ser própria de cada jogo.
    # Antes ela era declarada fora do loop e acumulava palpites de todos os
    # jogos ao vivo, fazendo cada jogo exibir palpites somados (bug quando há
    # mais de um jogo ao vivo simultâneo, ex: jogo interrompido e retomado).
    with session_scope() as session:
        for lg in live_games:
            lg_preds = []
            # Encontra o game_id no bolão
            game = session.query(Game).filter(
                ((Game.team_a == lg["home"]) & (Game.team_b == lg["away"])) |
                ((Game.team_a == lg["away"]) & (Game.team_b == lg["home"]))
            ).first()
            if game:
                lg["game_id"] = game.id
                # Busca TODOS os palpites deste jogo
                preds = session.query(Prediction).filter_by(game_id=game.id).all()
                for p in preds:
                    participant = session.query(Participant).get(p.participant_id)
                    # Ajusta placar conforme ordem do bolão
                    if game.team_a == lg["home"]:
                        ga, gb = p.goals_a, p.goals_b
                    else:
                        ga, gb = p.goals_b, p.goals_a
                    lg_preds.append({
                        "participant_name": participant.name if participant else "?",
                        "goals_a": ga,
                        "goals_b": gb,
                    })
            lg["predictions"] = lg_preds

    return {
        "live": live_games,
        "next": next_game,
    }


# ---------------------------------------------------------------------------
# Web Push — notificações no celular/navegador (VAPID)
# ---------------------------------------------------------------------------
@app.route("/push/vapid-public")
def push_vapid_public():
    """Chave pública VAPID (vai para o navegador) + se o push está habilitado."""
    from .notifications import get_vapid_public_key, is_push_enabled
    return jsonify({"enabled": is_push_enabled(), "publicKey": get_vapid_public_key()})


@app.route("/push/subscribe", methods=["POST"])
def push_subscribe():
    """Salva/atualiza uma inscrição de push atrelada ao participant_uid.

    Body: { participant_uid, subscription: { endpoint, keys: {p256dh, auth} } }
    """
    data = request.get_json(silent=True) or {}
    uid = data.get("participant_uid")
    subscription = data.get("subscription") or {}
    endpoint = subscription.get("endpoint")
    keys = subscription.get("keys") or {}
    if not uid or not endpoint:
        return {"error": "participant_uid and subscription.endpoint are required"}, 400

    ua = (request.headers.get("User-Agent") or "")[:255]
    with session_scope() as session:
        existing = session.query(PushSubscription).filter_by(endpoint=endpoint).first()
        if existing:
            existing.participant_uid = uid
            existing.p256dh = keys.get("p256dh")
            existing.auth_key = keys.get("auth")
            existing.user_agent = ua
        else:
            session.add(PushSubscription(
                participant_uid=uid,
                endpoint=endpoint,
                p256dh=keys.get("p256dh"),
                auth_key=keys.get("auth"),
                user_agent=ua,
            ))
    return {"status": "subscribed"}


@app.route("/push/unsubscribe", methods=["POST"])
def push_unsubscribe():
    """Remove uma inscrição (por endpoint)."""
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    if not endpoint:
        return {"error": "endpoint is required"}, 400
    with session_scope() as session:
        session.query(PushSubscription).filter_by(endpoint=endpoint).delete()
    return {"status": "unsubscribed"}


@app.route("/push/test", methods=["POST"])
@token_required
def push_test():
    """Envia uma notificação de teste (admin only).

    Body opcional: { participant_uid, title, body } — sem participant_uid,
    faz broadcast para todos os inscritos.
    """
    from .notifications import broadcast_to_all, notify_uid

    data = request.get_json(silent=True) or {}
    uid = data.get("participant_uid")
    title = data.get("title") or "🔔 Teste de notificação"
    body = data.get("body") or "Se você está vendo isto, as notificações funcionam! 🎉"
    with session_scope() as session:
        if uid:
            sent, total = notify_uid(session, uid, title, body, url=f"/user/{uid}")
        else:
            sent, total = broadcast_to_all(session, title, body, url="/")
    return {"sent": sent, "total": total}


@app.route("/push/daily-reminder", methods=["POST"])
@token_required
def push_daily_reminder():
    """Dispara/testa o lembrete diário de palpites faltantes do dia (admin).

    Body opcional: { "force": true } — ignora a idempotência e NÃO marca o
    log (modo teste: não bloqueia o disparo automático do dia).
    Retorna { games, targeted, sent }.
    """
    from .notifications import dispatch_daily_missing_reminders

    data = request.get_json(silent=True) or {}
    force = bool(data.get("force", False))
    return jsonify(dispatch_daily_missing_reminders(force=force))


@app.route("/push/subscriptions", methods=["GET"])
@token_required
def push_subscriptions():
    """Lista a contagem de inscrições de push por participant_uid (admin).

    Útil para o admin saber quais participantes ativaram as notificações.
    Retorna: { "<uid>": <n_dispositivos>, ... }
    """
    from sqlalchemy import func as _func
    with session_scope() as session:
        rows = (
            session.query(PushSubscription.participant_uid, _func.count(PushSubscription.id))
            .group_by(PushSubscription.participant_uid)
            .all()
        )
    return jsonify({uid: cnt for uid, cnt in rows})


if __name__ == "__main__":
    ensure_db_exists()
    app.run(debug=True, host="0.0.0.0", port=5000)
