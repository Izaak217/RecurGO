"""v1.0.1.dev1: count the live territory display after manual review.

No shape solver, confidence filter, or engine request belongs in this module.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .board import BoardState, Color
from .coordinates import Point
from .scoring import ChineseScore

LIVE_OWNERSHIP_CUTOFF = 0.08  # The unchanged v1.0.0 live-board display cutoff.
BLACK, WHITE, SHARED, UNASSIGNED = 1, -1, 0, 2


def validate_assignments(values: object, size: int) -> tuple[int, ...] | None:
    if not isinstance(values, (list, tuple)) or len(values) != size * size:
        return None
    if any(type(v) is not int or v not in (BLACK, WHITE, SHARED, UNASSIGNED) for v in values):
        return None
    return tuple(values)


def live_assignments(values: object, size: int) -> tuple[int, ...] | None:
    """Snapshot exactly the black/white markers visible on the live board."""
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
            UNASSIGNED if abs(value) < LIVE_OWNERSHIP_CUTOFF else BLACK if value > 0 else WHITE
        )
    return tuple(result)


def assigned_dead(state: BoardState, owners: Sequence[int]) -> frozenset[Point]:
    """Identify stones assigned to the other side, without changing assignments."""
    return frozenset(
        Point(i % state.size, i // state.size)
        for i, stone in enumerate(state.stones)
        if (stone == Color.BLACK and owners[i] == WHITE)
        or (stone == Color.WHITE and owners[i] == BLACK)
    )


def count_assignments(
    state: BoardState,
    owners: Sequence[int],
    *,
    komi: float,
    dead_points: frozenset[Point] = frozenset(),
) -> ChineseScore:
    if validate_assignments(tuple(owners), state.size) is None:
        raise ValueError("Invalid point assignments")
    if not math.isfinite(komi) or not float(komi * 2).is_integer():
        raise ValueError("Komi must be a finite whole or half point")
    if any(
        not (0 <= p.x < state.size and 0 <= p.y < state.size) or state.stone_at(p) is None
        for p in dead_points
    ):
        raise ValueError("Dead points must be occupied intersections")
    shared = owners.count(SHARED)
    dead = assigned_dead(state, owners) | dead_points
    return ChineseScore(
        black_area=(2 * owners.count(BLACK) + shared) / 2,
        white_area=(2 * owners.count(WHITE) + shared) / 2,
        neutral_points=shared,
        dead_black=sum(state.stone_at(p) is Color.BLACK for p in dead),
        dead_white=sum(state.stone_at(p) is Color.WHITE for p in dead),
        komi=komi,
    )


def score_ownership(
    state: BoardState,
    owners: Sequence[int],
    *,
    komi: float,
    dead_points: frozenset[Point] = frozenset(),
) -> ChineseScore:
    score = count_assignments(state, owners, komi=komi, dead_points=dead_points)
    if UNASSIGNED in owners:
        raise ValueError("Complete unassigned points before confirming")
    return score
