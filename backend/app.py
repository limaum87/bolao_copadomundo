import os
import jwt
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash
from .database import engine, session_scope
from .models import Base, FinalsPrediction, Game, Participant, Prediction, TournamentOutcome, AdminUser, ScoringConfig
from .scoring import calculate_scores, score_prediction, get_scoring_config_dict


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = (BASE_DIR / "data.db").resolve()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev_secret_key_change_in_prod'
CORS(app)


# Initialize database on app startup
def ensure_db_exists():
    os.makedirs(DB_PATH.parent, exist_ok=True)
    Base.metadata.create_all(engine)


# Create tables at import time
with app.app_context():
    ensure_db_exists()


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
                'exp': datetime.utcnow() + timedelta(hours=24)
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

        if game.kickoff <= datetime.utcnow():
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
        participants = session.query(Participant).all()
        games = session.query(Game).all()
        predictions = session.query(Prediction).all()
        finals_predictions = session.query(FinalsPrediction).all()
        outcome = session.query(TournamentOutcome).get(1)
        config = session.query(ScoringConfig).get(1)
        scoring_cfg = get_scoring_config_dict(config)

        results = calculate_scores(
            participants=participants,
            games=games,
            predictions=predictions,
            finals_predictions=finals_predictions,
            outcome=outcome,
            scoring_cfg=scoring_cfg,
        )
        return jsonify(results)


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
    }


def parse_date(value: str) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)



if __name__ == "__main__":
    ensure_db_exists()
    app.run(debug=True, host="0.0.0.0", port=5000)
