import os
import sys
import jwt
import subprocess
import logging
import threading
import time as _time_module
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash
from .database import engine, session_scope, DATABASE_URL
from .models import (AdminUser, Base, FinalsPrediction, Game, NotificationLog,
                    Participant, Prediction, PushSubscription, RankingSnapshot, ScoringConfig,
                    TournamentOutcome)
from .scoring import calculate_scores, score_prediction, get_scoring_config_dict


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
      1. Só jogos finalizados segundo a ESPN (is_full_time = FT/AET/PEN)
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

    now = now or datetime.now()

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
                all_results.append({
                    "status": "corrected" if was_corrected else "updated",
                    "game_id": game_id,
                    "home": team_a,
                    "away": team_b,
                    "score_a": score_a,
                    "score_b": score_b,
                })

    return all_results


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


start_sync_scheduler()


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
                now = datetime.now()
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
    now = now or datetime.now()
    today = now.date() if isinstance(now, datetime) else now
    yesterday = today - timedelta(days=1)
    with session_scope() as session:
        results = _compute_ranking_results(session)
        return _capture_ranking_snapshot(session, yesterday, results)


def _seconds_until_next_snapshot(now=None):
    """Segundos até a próxima hora agendada do snapshot (default 5h)."""
    now = now or datetime.now()
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
            now = datetime.now()
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

            kickoff_dt = parse_date(kickoff)
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
                    if game and game.kickoff > datetime.now():
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

        if game.kickoff <= datetime.now():
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
            if datetime.now() > config.finals_deadline:
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
        today = datetime.now().date()
        try:
            if datetime.now().hour >= SNAPSHOT_HOUR:
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


@app.route("/ranking/daily", methods=["GET"])
def ranking_daily():
    """Ranking de um dia específico com a variação de posição vs dia anterior.

    Query param:
      - date: "YYYY-MM-DD" (default: hoje).

    Retorna, do maior para o menor pontuador naquele dia:
      - name: nome do participante
      - points: pontuação acumulada até o fim daquele dia
      - variacao: variação de posição em relação ao dia anterior,
        formatada como "+1" (subiu), "-2" (desceu) ou "0" (manteve/
        sem histórico anterior).
    """
    date_str = request.args.get("date")
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return {"error": "Invalid date format. Use YYYY-MM-DD"}, 400
    else:
        target_date = datetime.now().date()

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
        target_date = datetime.now().date() - timedelta(days=1)

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
        today = datetime.now().date()
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
    return {
        "id": prediction.id,
        "participant_id": prediction.participant_id,
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
        {"team_a": "Turquia", "team_b": "Paraguai", "kickoff": "2026-06-19T00:00:00"},
        {"team_a": "Brasil", "team_b": "Haiti", "kickoff": "2026-06-19T21:30:00"},
        {"team_a": "Tunísia", "team_b": "Japão", "kickoff": "2026-06-20T23:00:00"},
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

    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

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

    # Busca palpites do jogo ao vivo (se houver)
    predictions_for_live = []
    with session_scope() as session:
        for lg in live_games:
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
                    predictions_for_live.append({
                        "participant_name": participant.name if participant else "?",
                        "goals_a": ga,
                        "goals_b": gb,
                    })
                lg["predictions"] = predictions_for_live

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
