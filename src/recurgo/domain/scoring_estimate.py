"""v1.0.1: Chinese area scoring from reviewed KataGo ownership proposals."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .board import BoardState, Color
from .coordinates import Point
from .scoring import ChineseScore, connected_group

# The old live-board rendering cutoff is unchanged.
OWNERSHIP_NEUTRAL_THRESHOLD = 0.08
# This is a review heuristic, never proof of life/death or shared ownership.
AI_ASSIGNMENT_THRESHOLD = 0.9
BLACK, WHITE, SHARED, UNSETTLED = 1, -1, 0, 2


def validate_assignments(values: object, size: int) -> tuple[int, ...] | None:
    if not isinstance(values, (list, tuple)) or len(values) != size * size:
        return None
    if any(
        type(value) is not int or value not in (BLACK, WHITE, SHARED, UNSETTLED)
        for value in values
    ):
        return None
    return tuple(values)


def ownership_points(values: object, size: int) -> tuple[int, ...] | None:
    """AI uncertainty is UNSETTLED, never automatically half for both sides."""
    if not isinstance(values, (list, tuple)) or len(values) != size * size:
        return None
    result = []
    for value in values:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not -1 <= value <= 1
        ):
            return None
        result.append(
            UNSETTLED if abs(value) < AI_ASSIGNMENT_THRESHOLD else BLACK if value > 0 else WHITE
        )
    return tuple(result)


def prepare_proposal(state: BoardState, values: object) -> tuple[int, ...] | None:
    points = ownership_points(values, state.size)
    if points is None:
        return None
    result = list(points)
    if state.ko_point is not None:
        result[state.ko_point.y * state.size + state.ko_point.x] = UNSETTLED
    return tuple(result)


def _groups(state: BoardState) -> list[frozenset[Point]]:
    seen: set[Point] = set()
    groups = []
    for y in range(state.size):
        for x in range(state.size):
            point = Point(x, y)
            if point in seen or state.stone_at(point) is None:
                continue
            group = connected_group(state, point)
            groups.append(group)
            seen.update(group)
    return groups


def scoring_issues(
    state: BoardState,
    owners: Sequence[int],
    dead_points: frozenset[Point] = frozenset(),
) -> frozenset[Point]:
    if validate_assignments(tuple(owners), state.size) is None:
        raise ValueError("Invalid ownership assignments")
    issues = {
        Point(i % state.size, i // state.size)
        for i, value in enumerate(owners)
        if value == UNSETTLED
    }
    occupied: set[Point] = set()
    for group in _groups(state):
        occupied.update(group)
        if group & dead_points:
            if not group.issubset(dead_points):
                issues.update(group)
            continue
        colors = {owners[p.y * state.size + p.x] for p in group}
        if colors not in ({BLACK}, {WHITE}):
            issues.update(group)
    issues.update(dead_points - occupied)
    return frozenset(issues)


def inferred_dead(
    state: BoardState,
    owners: Sequence[int],
) -> frozenset[Point]:
    dead: set[Point] = set()
    for group in _groups(state):
        color = state.stone_at(next(iter(group)))
        opponent_owner = WHITE if color is Color.BLACK else BLACK
        if all(owners[p.y * state.size + p.x] == opponent_owner for p in group):
            dead.update(group)
    return frozenset(dead)


def count_assignments(
    state: BoardState,
    owners: Sequence[int],
    *,
    komi: float,
    dead_points: frozenset[Point] = frozenset(),
) -> ChineseScore:
    if validate_assignments(tuple(owners), state.size) is None:
        raise ValueError("Invalid ownership assignments")
    if not math.isfinite(komi) or not float(komi * 2).is_integer():
        raise ValueError("Chinese scoring requires integer or half-point komi")
    shared = sum(value == SHARED for value in owners)
    # Integer half-point units make shared areas and quarter-stone margins exact.
    black_halves = 2 * sum(value == BLACK for value in owners) + shared
    white_halves = 2 * sum(value == WHITE for value in owners) + shared
    dead = dead_points | inferred_dead(state, owners)
    return ChineseScore(
        black_area=black_halves / 2,
        white_area=white_halves / 2,
        neutral_points=shared,
        dead_black=sum(state.stone_at(p) is Color.BLACK for p in dead),
        dead_white=sum(state.stone_at(p) is Color.WHITE for p in dead),
        komi=komi,
    )


def score_ownership(
    state: BoardState,
    ownership: Sequence[int],
    *,
    komi: float,
    dead_points: frozenset[Point] = frozenset(),
) -> ChineseScore:
    """Only complete, consistent assignments can become an agreed final score."""
    if scoring_issues(state, ownership, dead_points):
        raise ValueError("Resolve pending ownership and whole-group life/death first")
    score = count_assignments(state, ownership, komi=komi, dead_points=dead_points)
    if score.black_area + score.white_area != state.size * state.size:
        raise ValueError("Area must cover the entire board")
    return score
