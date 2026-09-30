"""v1.0.1: Chinese area scoring from reviewed KataGo ownership proposals."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .board import BoardState, Color
from .coordinates import Point
from .scoring import ChineseScore, connected_group
from .scoring_shape import shape_ownership, suggested_eye_ownership

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


def prepare_proposal(
    state: BoardState, values: object, ownership_stdev: object = None,
) -> tuple[int, ...] | None:
    """v1.0.1 revision: combine shape evidence and stable, whole-chain AI estimates.

    Thresholds remain review heuristics, not calibrated probabilities. Search
    variation is used to withhold unstable suggestions, never to prove life.
    Manual assignments are layered on afterwards by the dialog.
    """
    points = ownership_points(values, state.size)
    if points is None:
        return None
    assert isinstance(values, (list, tuple))
    deviations: tuple[float, ...] | None = None
    if ownership_stdev is not None:
        if (not isinstance(ownership_stdev, (list, tuple))
                or len(ownership_stdev) != len(points)
                or any(isinstance(v, bool) or not isinstance(v, (int, float))
                       or not math.isfinite(v) or not 0 <= v <= 1
                       for v in ownership_stdev)):
            return None
        deviations = tuple(float(v) for v in ownership_stdev)
    result = list(points)
    if deviations is not None:
        for i, deviation in enumerate(deviations):
            if abs(values[i]) - deviation < 0.75:
                result[i] = UNSETTLED
    structural = shape_ownership(state)
    for group in _groups(state):
        indexes = [p.y * state.size + p.x for p in group]
        mean = sum(values[i] for i in indexes) / len(indexes)
        owner = BLACK if mean > 0 else WHITE
        # Connected stones have a common fate. Pool a consistent strong signal,
        # but do not vote away a contrary prediction or high search variation.
        stable = (
            abs(mean) >= AI_ASSIGNMENT_THRESHOLD
            and all(values[i] * owner >= 0.5 for i in indexes)
            and (deviations is None
                 or all(values[i] * owner - deviations[i] >= 0.5 for i in indexes))
        )
        for i in indexes:
            result[i] = owner if stable else UNSETTLED
    for point, owner in structural.items():
        result[point.y * state.size + point.x] = owner
    for point, owner in suggested_eye_ownership(state, tuple(result)).items():
        index = point.y * state.size + point.x
        # A strong contrary prediction needs review rather than being silently
        # overwritten by a conditional life assumption. Proven shapes win below.
        if result[index] in (owner, UNSETTLED) and values[index] * owner >= 0:
            result[index] = owner
    for point, owner in structural.items():
        result[point.y * state.size + point.x] = owner
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
    if any(not (0 <= p.x < state.size and 0 <= p.y < state.size)
           or state.stone_at(p) is None for p in dead_points):
        raise ValueError("Dead points must be occupied board intersections")
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
    """Count the user's complete decision; shape disagreements are advisory.

    v1.0.1 revision: a manual decision is authoritative even when a suggested
    whole-group status disagrees. Invalid data and missing assignments still fail.
    """
    if validate_assignments(tuple(ownership), state.size) is None:
        raise ValueError("Invalid ownership assignments")
    if UNSETTLED in ownership:
        raise ValueError("Resolve pending ownership first")
    score = count_assignments(state, ownership, komi=komi, dead_points=dead_points)
    if score.black_area + score.white_area != state.size * state.size:
        raise ValueError("Area must cover the entire board")
    return score
