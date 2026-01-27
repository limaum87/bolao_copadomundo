from typing import Dict, List
from .models import FinalsPrediction, Game, Participant, Prediction, TournamentOutcome


def _result_code(goals_a: int, goals_b: int) -> int:
    if goals_a > goals_b:
        return 1
    if goals_a < goals_b:
        return -1
    return 0


def score_prediction(prediction: Prediction, game: Game) -> int:
    if game.score_a is None or game.score_b is None:
        return 0

    if prediction.goals_a == game.score_a and prediction.goals_b == game.score_b:
        return 10

    predicted_result = _result_code(prediction.goals_a, prediction.goals_b)
    actual_result = _result_code(game.score_a, game.score_b)

    if predicted_result == actual_result:
        return 5

    if prediction.goals_a == game.score_a or prediction.goals_b == game.score_b:
        return 2

    return 0


def score_finals(prediction: FinalsPrediction, outcome: TournamentOutcome) -> int:
    if not outcome or not prediction:
        return 0

    points = 0
    mapping = {
        "champion": 50,
        "runner_up": 15,
        "third_place": 10,
        "fourth_place": 10,
    }
    for field, pts in mapping.items():
        if getattr(prediction, field) and getattr(outcome, field):
            if getattr(prediction, field).lower() == getattr(outcome, field).lower():
                points += pts
    return points


def calculate_scores(
    participants: List[Participant],
    games: List[Game],
    predictions: List[Prediction],
    finals_predictions: List[FinalsPrediction],
    outcome: TournamentOutcome,
) -> List[Dict]:
    predictions_by_participant: Dict[int, List[Prediction]] = {}
    for pred in predictions:
        predictions_by_participant.setdefault(pred.participant_id, []).append(pred)

    finals_by_participant: Dict[int, FinalsPrediction] = {
        fp.participant_id: fp for fp in finals_predictions
    }

    game_lookup = {game.id: game for game in games}

    results = []
    for participant in participants:
        total = 0
        for pred in predictions_by_participant.get(participant.id, []):
            game = game_lookup.get(pred.game_id)
            if game:
                total += score_prediction(pred, game)

        total += score_finals(finals_by_participant.get(participant.id), outcome)

        results.append({
            "id": participant.id,
            "name": participant.name,
            "uid": participant.uid,
            "total_points": total,
            "games_predicted": len(predictions_by_participant.get(participant.id, [])),
        })

    results.sort(key=lambda item: item["total_points"], reverse=True)
    return results


def get_score_breakdown(
    participant: Participant,
    games: List[Game],
    predictions: List[Prediction],
    finals_prediction: FinalsPrediction,
    outcome: TournamentOutcome,
) -> List[Dict]:
    breakdown = []
    game_lookup = {game.id: game for game in games}

    # Points from games
    for pred in predictions:
        game = game_lookup.get(pred.game_id)
        if not game or game.score_a is None or game.score_b is None:
            continue

        pts = score_prediction(pred, game)
        if pts > 0:
            text = ""
            if pts == 10:
                text = f"Acertou em cheio o placar {game.team_a} × {game.team_b}!"
            elif pts == 5:
                text = f"Acertou o vencedor e o saldo de {game.team_a} × {game.team_b}!"
            elif pts == 2:
                text = f"Acertou o vencedor de {game.team_a} × {game.team_b}!"

            breakdown.append({
                "type": "game",
                "label": f"{game.team_a} × {game.team_b}",
                "points": pts,
                "description": text
            })

    # Points from finals
    if finals_prediction and outcome:
        mapping = {
            "champion": ("Campeão", 50),
            "runner_up": ("Vice-campeão", 15),
            "third_place": ("3º Lugar", 10),
            "fourth_place": ("4º Lugar", 10),
        }
        for field, (label, pts) in mapping.items():
            pred_team = getattr(finals_prediction, field)
            real_team = getattr(outcome, field)
            if pred_team and real_team and pred_team.lower() == real_team.lower():
                breakdown.append({
                    "type": "finals",
                    "label": label,
                    "points": pts,
                    "description": f"Acertou o {label} ({real_team})!"
                })

    return breakdown
