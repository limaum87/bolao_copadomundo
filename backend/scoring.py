from typing import Dict, List, Optional
from .models import FinalsPrediction, Game, Participant, Prediction, ScoringConfig, TournamentOutcome


DEFAULT_SCORING = {
    "exact_score": 10,
    "correct_result": 5,
    "partial_score": 2,
    "champion": 50,
    "runner_up": 15,
    "third_place": 10,
    "fourth_place": 10,
}


def get_scoring_config_dict(config: Optional[ScoringConfig]) -> Dict[str, int]:
    if not config:
        return dict(DEFAULT_SCORING)
    return {
        "exact_score": config.exact_score,
        "correct_result": config.correct_result,
        "partial_score": config.partial_score,
        "champion": config.champion,
        "runner_up": config.runner_up,
        "third_place": config.third_place,
        "fourth_place": config.fourth_place,
    }


def _result_code(goals_a: int, goals_b: int) -> int:
    if goals_a > goals_b:
        return 1
    if goals_a < goals_b:
        return -1
    return 0


def score_prediction(prediction: Prediction, game: Game, scoring_cfg: Optional[Dict[str, int]] = None) -> int:
    cfg = scoring_cfg or DEFAULT_SCORING

    if game.score_a is None or game.score_b is None:
        return 0

    if prediction.goals_a == game.score_a and prediction.goals_b == game.score_b:
        return cfg["exact_score"]

    predicted_result = _result_code(prediction.goals_a, prediction.goals_b)
    actual_result = _result_code(game.score_a, game.score_b)

    if predicted_result == actual_result:
        return cfg["correct_result"]

    if prediction.goals_a == game.score_a or prediction.goals_b == game.score_b:
        return cfg["partial_score"]

    return 0


def score_finals(prediction: FinalsPrediction, outcome: TournamentOutcome, scoring_cfg: Optional[Dict[str, int]] = None) -> int:
    if not outcome or not prediction:
        return 0

    cfg = scoring_cfg or DEFAULT_SCORING
    points = 0
    for field in ("champion", "runner_up", "third_place", "fourth_place"):
        pts = cfg[field]
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
    scoring_cfg: Optional[Dict[str, int]] = None,
) -> List[Dict]:
    cfg = scoring_cfg or DEFAULT_SCORING

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
                total += score_prediction(pred, game, scoring_cfg=cfg)

        total += score_finals(finals_by_participant.get(participant.id), outcome, scoring_cfg=cfg)

        results.append({
            "id": participant.id,
            "name": participant.name,
            "uid": participant.uid,
            "total_points": total,
            "games_predicted": len(predictions_by_participant.get(participant.id, [])),
        })

    results.sort(key=lambda item: (-item["total_points"], item["name"].lower()))
    return results


def calculate_daily_scores(
    participants: List[Participant],
    games: List[Game],
    predictions: List[Prediction],
    target_date,
    scoring_cfg: Optional[Dict[str, int]] = None,
) -> List[Dict]:
    """Ranking dos pontos ganhos APENAS nos jogos finalizados cujo kickoff
    caiu em `target_date` (compara só a data, ignorando hora/fuso).

    É o ranking de "melhor do dia": não acumula rodadas anteriores nem conta
    palpites de finais (que não têm um dia associado). Determinístico a
    partir dos jogos finalizados daquele dia.

    Retorna lista ordenada por pontos (desc) e nome (asc):
      { id, name, total_points }
    """
    cfg = scoring_cfg or DEFAULT_SCORING

    day_games = [
        g for g in games
        if g.score_a is not None
        and g.kickoff is not None
        and g.kickoff.date() == target_date
    ]
    game_lookup = {g.id: g for g in day_games}

    predictions_by_participant: Dict[int, List[Prediction]] = {}
    for pred in predictions:
        if pred.game_id in game_lookup:
            predictions_by_participant.setdefault(pred.participant_id, []).append(pred)

    results = []
    for participant in participants:
        total = 0
        for pred in predictions_by_participant.get(participant.id, []):
            game = game_lookup.get(pred.game_id)
            if game:
                total += score_prediction(pred, game, scoring_cfg=cfg)
        results.append({
            "id": participant.id,
            "name": participant.name,
            "total_points": total,
        })

    results.sort(key=lambda item: (-item["total_points"], item["name"].lower()))
    return results


def get_score_breakdown(
    participant: Participant,
    games: List[Game],
    predictions: List[Prediction],
    finals_prediction: FinalsPrediction,
    outcome: TournamentOutcome,
    scoring_cfg: Optional[Dict[str, int]] = None,
) -> List[Dict]:
    cfg = scoring_cfg or DEFAULT_SCORING
    breakdown = []
    game_lookup = {game.id: game for game in games}

    # Points from games
    for pred in predictions:
        game = game_lookup.get(pred.game_id)
        if not game or game.score_a is None or game.score_b is None:
            continue

        pts = score_prediction(pred, game, scoring_cfg=cfg)
        if pts > 0:
            text = ""
            if pts == cfg["exact_score"]:
                text = f"Acertou em cheio o placar {game.team_a} {game.score_a} × {game.score_b} {game.team_b}!"
            elif pts == cfg["correct_result"]:
                text = f"Acertou o resultado (vencedor/empate) de {game.team_a} × {game.team_b}!"
            elif pts == cfg["partial_score"]:
                text = f"Acertou a quantidade de gols de um dos times em {game.team_a} × {game.team_b}!"

            breakdown.append({
                "type": "game",
                "label": f"{game.team_a} × {game.team_b}",
                "points": pts,
                "description": text
            })

    # Points from finals
    if finals_prediction and outcome:
        finals_labels = {
            "champion": "Campeão",
            "runner_up": "Vice-campeão",
            "third_place": "3º Lugar",
            "fourth_place": "4º Lugar",
        }
        for field, label in finals_labels.items():
            pts = cfg[field]
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
