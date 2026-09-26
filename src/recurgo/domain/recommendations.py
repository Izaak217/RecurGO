"""Select genuinely reasonable KataGo candidates for recommendation display."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .board import Color


@dataclass(frozen=True, slots=True)
class RecommendationTier:
    """Maximum evaluation loss and minimum search support for one quality tier."""

    maximum_winrate_loss: float
    maximum_score_loss: float
    minimum_visit_ratio: float


RECOMMENDATION_TIERS = (
    RecommendationTier(1.2, 0.8, 0.02),
    RecommendationTier(2.5, 1.5, 0.075),
    RecommendationTier(4.0, 2.5, 0.20),
)
def select_recommended_candidates(
    move_infos: object,
    side: Color,
    *,
    maximum: int = 5,
) -> list[dict[str, object]]:
    """Return one to ``maximum`` candidates that remain credible alternatives.

    KataGo reports win rate and score lead from Black's perspective in this
    project. Values are normalized to the side to play before comparing every
    candidate with the searched best move.
    """
    if maximum <= 0 or not isinstance(move_infos, list):
        return []
    ordered = sorted(
        (value for value in move_infos if isinstance(value, dict)),
        key=_candidate_order,
    )
    if not ordered:
        return []

    best = ordered[0]
    selected = [best]
    seen_moves = {str(best.get("move", "pass")).upper()}
    for candidate in ordered[1:]:
        if len(selected) >= maximum:
            break
        move = str(candidate.get("move", "pass")).upper()
        if move in seen_moves or not _is_reasonable_alternative(best, candidate, side):
            continue
        selected.append(candidate)
        seen_moves.add(move)
    return selected


def _is_reasonable_alternative(
    best: dict[str, object],
    candidate: dict[str, object],
    side: Color,
) -> bool:
    best_winrate = _side_winrate(best, side)
    candidate_winrate = _side_winrate(candidate, side)
    best_score = _side_score(best, side)
    candidate_score = _side_score(candidate, side)
    winrate_loss = _loss(best_winrate, candidate_winrate)
    score_loss = _loss(best_score, candidate_score)
    if winrate_loss is None and score_loss is None:
        return False

    # Large absolute losses are not recommendations, regardless of visit count.
    if winrate_loss is not None and winrate_loss > 5.0:
        return False
    if score_loss is not None and score_loss > 3.0:
        return False

    # Do not recommend a move that changes a clear advantage into a clear deficit.
    if (
        best_winrate is not None
        and candidate_winrate is not None
        and best_winrate >= 51.0
        and candidate_winrate <= 49.0
    ):
        return False
    if (
        best_score is not None
        and candidate_score is not None
        and best_score >= 0.75
        and candidate_score <= -0.75
    ):
        return False

    visit_ratio = _visit_ratio(best, candidate)
    for tier in RECOMMENDATION_TIERS:
        if not _within(winrate_loss, tier.maximum_winrate_loss):
            continue
        if not _within(score_loss, tier.maximum_score_loss):
            continue
        if visit_ratio is None:
            # Without visits, only a very close evaluation is strong enough evidence.
            return tier is RECOMMENDATION_TIERS[0]
        return visit_ratio >= tier.minimum_visit_ratio
    return False


def _candidate_order(info: dict[str, object]) -> tuple[int, float]:
    raw_order = _finite_number(info.get("order"))
    order = int(raw_order) if raw_order is not None else 1_000_000
    visits = _finite_number(info.get("visits"))
    return order, -(visits or 0.0)


def _side_winrate(info: dict[str, object], side: Color) -> float | None:
    value = _finite_number(info.get("winrate"))
    if value is None:
        return None
    percentage = value * 100.0
    return percentage if side is Color.BLACK else 100.0 - percentage


def _side_score(info: dict[str, object], side: Color) -> float | None:
    value = _finite_number(info.get("scoreLead", info.get("scoreMean")))
    if value is None:
        return None
    return value if side is Color.BLACK else -value


def _visit_ratio(
    best: dict[str, object],
    candidate: dict[str, object],
) -> float | None:
    best_visits = _finite_number(best.get("visits"))
    candidate_visits = _finite_number(candidate.get("visits"))
    if best_visits is None or best_visits <= 0.0 or candidate_visits is None:
        return None
    return max(0.0, candidate_visits) / best_visits


def _loss(best: float | None, candidate: float | None) -> float | None:
    if best is None or candidate is None:
        return None
    return max(0.0, best - candidate)


def _within(loss: float | None, maximum: float) -> bool:
    return loss is None or loss <= maximum


def _finite_number(value: object) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


__all__ = [
    "RECOMMENDATION_TIERS",
    "RecommendationTier",
    "select_recommended_candidates",
]
