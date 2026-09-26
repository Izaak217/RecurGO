"""Human-policy-based AI difficulty and reproducible move selection."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from recurgo.domain import BoardState, IllegalMove, Point
from recurgo.domain.coordinates import gtp_to_point


@dataclass(frozen=True, slots=True)
class DifficultyPreset:
    label: str
    human_profile: str
    max_visits: int
    objective_best: bool = False


PRESETS = {
    preset.label: preset
    for preset in (
        DifficultyPreset("入门", "rank_15k", 80),
        DifficultyPreset("初级", "rank_8k", 80),
        DifficultyPreset("中级", "rank_3k", 100),
        DifficultyPreset("高级", "rank_2d", 120),
        DifficultyPreset("顶级", "rank_6d", 180),
        DifficultyPreset("最强", "rank_9d", 800, objective_best=True),
    )
}


@dataclass(frozen=True, slots=True)
class MoveSelection:
    point: Point | None
    source: str
    probability: float | None


def select_ai_move(
    payload: dict[str, object],
    state: BoardState,
    preset: DifficultyPreset,
    *,
    random_seed: int,
) -> MoveSelection:
    """Pick a legal move, following KataGo's Human SL guidance for non-max levels."""
    best_move = _best_searched_move(payload, state)
    if preset.objective_best:
        return MoveSelection(best_move, "objective", None)

    # Official Human SL guidance recommends passing only when searched best move passes,
    # since weaker-rank historical policies can otherwise pass too early.
    if best_move is None:
        return MoveSelection(None, "searched-pass", None)

    policy = payload.get("humanPolicy")
    if not isinstance(policy, list):
        return MoveSelection(best_move, "fallback-objective", None)

    points: list[Point] = []
    weights: list[float] = []
    board_points = state.size * state.size
    for index, raw_weight in enumerate(policy[:board_points]):
        weight = _positive_number(raw_weight)
        if weight <= 0:
            continue
        point = Point(index % state.size, index // state.size)
        try:
            state.play(point)
        except IllegalMove:
            continue
        points.append(point)
        weights.append(weight)

    if not points or sum(weights) <= 0:
        return MoveSelection(best_move, "fallback-objective", None)

    generator = random.Random(random_seed)
    selected = generator.choices(points, weights=weights, k=1)[0]
    selected_probability = weights[points.index(selected)] / sum(weights)
    return MoveSelection(selected, "human-policy", selected_probability)


def human_policy_probability(
    payload: dict[str, object], move: str, board_size: int
) -> float | None:
    policy = payload.get("humanPolicy")
    if not isinstance(policy, list):
        return None
    point = gtp_to_point(move, board_size)
    index = board_size * board_size if point is None else point.y * board_size + point.x
    if not (0 <= index < len(policy)):
        return None
    value = _positive_number(policy[index])
    return value if value >= 0 else None


def _best_searched_move(payload: dict[str, object], state: BoardState) -> Point | None:
    move_infos = payload.get("moveInfos")
    if not isinstance(move_infos, list):
        return None
    ordered = sorted(
        (info for info in move_infos if isinstance(info, dict)),
        key=lambda info: _order_value(info.get("order")),
    )
    for info in ordered:
        move = str(info.get("move", "pass"))
        try:
            point = gtp_to_point(move, state.size)
            state.play(point)
        except (IllegalMove, ValueError):
            continue
        return point
    return None


def _order_value(value: object) -> int:
    return value if isinstance(value, int) else 1_000_000


def _positive_number(value: object) -> float:
    if not isinstance(value, (int, float)):
        return 0.0
    number = float(value)
    return number if math.isfinite(number) and number > 0 else 0.0
