"""Regression coverage for the v1.0.0-based live ownership review."""

import math

import pytest

from recurgo.domain import BoardState, Color, Point
from recurgo.domain.score_review import (
    UNASSIGNED,
    assigned_dead,
    count_assignments,
    live_assignments,
    score_ownership,
)


def test_live_mapping_keeps_every_visible_marker_without_group_inference() -> None:
    values = [0.08, -0.08, 0.079, -0.079, 1, -1, 0.4, -0.4, 0]
    assert live_assignments(values, 3) == (1, -1, 2, 2, 1, -1, 1, -1, 2)
    assert values == [0.08, -0.08, 0.079, -0.079, 1, -1, 0.4, -0.4, 0]


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, 1.1, True, "0.5"])
def test_invalid_live_data_is_not_silently_counted(value: object) -> None:
    assert live_assignments([value] * 9, 3) is None
    assert live_assignments([0.5], 3) is None
    assert live_assignments(None, 3) is None


def test_shared_points_count_half_each_and_quarter_stone_margin_is_exact() -> None:
    state = BoardState.new(size=3)
    owners = (1, 1, 1, 1, 1, -1, -1, -1, 0)
    score = score_ownership(state, owners, komi=7.5)
    assert (score.black_area, score.white_area, score.neutral_points) == (5.5, 3.5, 1)
    assert score.winning_margin_stones == 2.75
    assert score.sgf_result == "W+2.75"
    assert score.black_area + score.white_area == 9


def test_unassigned_is_never_counted_as_shared_or_confirmed() -> None:
    state = BoardState.new(size=3)
    owners = (1, -1, UNASSIGNED, 1, -1, 1, -1, 1, -1)
    score = count_assignments(state, owners, komi=0)
    assert (score.black_area, score.white_area, score.neutral_points) == (4, 4, 0)
    with pytest.raises(ValueError, match="unassigned"):
        score_ownership(state, owners, komi=0)


def test_dead_display_does_not_reassign_other_points_or_count_stones_twice() -> None:
    state = BoardState.from_setup(
        {Point(0, 0): Color.BLACK, Point(1, 0): Color.BLACK, Point(2, 2): Color.WHITE},
        size=3,
    )
    owners = (-1, 1, 1, 1, 1, -1, -1, -1, 1)
    assert assigned_dead(state, owners) == {Point(0, 0), Point(2, 2)}
    score = score_ownership(state, owners, komi=0)
    assert (score.black_area, score.white_area) == (5, 4)
    assert (score.dead_black, score.dead_white) == (1, 1)


@pytest.mark.parametrize("komi", [math.nan, math.inf, 7.25])
def test_invalid_komi_is_rejected(komi: float) -> None:
    with pytest.raises(ValueError):
        score_ownership(BoardState.new(size=3), (1,) * 9, komi=komi)
