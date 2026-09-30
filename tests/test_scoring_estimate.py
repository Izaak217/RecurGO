import math
from dataclasses import replace

import pytest

from recurgo.domain import BoardState, Color, Point
from recurgo.domain.scoring_estimate import (
    UNSETTLED,
    count_assignments,
    inferred_dead,
    ownership_points,
    prepare_proposal,
    score_ownership,
    scoring_issues,
)


def test_ai_uncertainty_is_not_shared_ownership():
    assert ownership_points([0, 0.079, -0.079, 0.08, -0.08, 0.899, -0.9, 1, -1], 3) == (
        2,
        2,
        2,
        2,
        2,
        2,
        -1,
        1,
        -1,
    )


@pytest.mark.parametrize("value", [math.nan, math.inf, True, "1", 1.1, -1.1])
def test_invalid_map_rejected(value):
    assert ownership_points([value] * 9, 3) is None
    assert ownership_points([0], 3) is None


def test_known_ko_requires_review_even_with_confident_prediction():
    state = replace(BoardState.new(size=3), ko_point=Point(1, 1))
    owners = prepare_proposal(state, [1.0] * 9)
    assert owners[4] == UNSETTLED
    with pytest.raises(ValueError, match="Resolve"):
        score_ownership(state, owners, komi=7.5)


def test_stones_are_not_double_counted_and_komi_applied_once():
    state = BoardState.from_setup({Point(0, 0): Color.BLACK, Point(2, 2): Color.WHITE}, size=3)
    score = score_ownership(state, [1] * 5 + [-1] * 4, komi=7.5)
    assert (score.black_area, score.white_area, score.neutral_points) == (5, 4, 0)
    assert score.black_lead_points == -6.5
    assert score.winning_margin_stones == 3.25
    assert state.stone_at(Point(0, 0)) is Color.BLACK


@pytest.mark.parametrize(("shared", "black", "white"), [(1, 184, 176), (2, 183, 176)])
def test_shared_points_conserve_361_and_quarter_stone_margin(shared, black, white):
    score = score_ownership(
        BoardState.new(),
        [1] * black + [-1] * white + [0] * shared,
        komi=7.5,
    )
    assert score.black_area == black + shared / 2
    assert score.white_area == white + shared / 2
    assert score.black_area + score.white_area == 361
    assert score.winning_margin_stones == 0.25
    assert score.winner is (Color.BLACK if shared == 1 else Color.WHITE)


def test_reviewed_seki_counts_private_eyes_but_splits_only_common_liberties():
    stones = {
        Point(x, y): Color.BLACK if x < 2 else Color.WHITE
        for y in range(5)
        for x in (0, 1, 3, 4)
        if (x, y) not in ((0, 2), (4, 2))
    }
    state = BoardState.from_setup(stones, size=5)
    owners = [1 if x < 2 else -1 if x > 2 else 0 for y in range(5) for x in range(5)]
    score = score_ownership(state, owners, komi=0)
    assert (score.black_area, score.white_area, score.neutral_points) == (12.5, 12.5, 5)
    assert score.winner is None
    assert not inferred_dead(state, owners)


def test_point_corrections_change_margin_in_half_and_whole_stones():
    state = BoardState.new(size=3)
    owners = [1] * 5 + [-1] * 4
    before = score_ownership(state, owners, komi=0)
    owners[0] = 0
    shared = score_ownership(state, owners, komi=0)
    assert before.black_lead_points - shared.black_lead_points == 1
    owners[0] = -1
    white = score_ownership(state, owners, komi=0)
    assert before.black_lead_points - white.black_lead_points == 2


def test_whole_group_life_death_and_removed_intersections():
    group = frozenset({Point(0, 0), Point(1, 0)})
    state = BoardState.from_setup({p: Color.BLACK for p in group}, size=3)
    owners = [1, -1] + [-1] * 7
    assert scoring_issues(state, owners) == group
    owners[0] = -1
    assert inferred_dead(state, owners) == group
    assert score_ownership(state, owners, komi=0).dead_black == 2
    owners[0] = 0
    # v1.0.1 revision: conflicts are advisory; the complete manual map is final.
    assert scoring_issues(state, owners) == group
    assert score_ownership(state, owners, komi=0).black_area == 0.5
    score = score_ownership(state, owners, komi=0, dead_points=group)
    assert score.dead_black == 2
    assert score.black_area == 0.5
    assert score_ownership(
        state, owners, komi=0, dead_points=frozenset({Point(0, 0)})
    ).dead_black == 1


def test_partial_preview_is_not_a_final_score():
    state = BoardState.new(size=3)
    owners = [1] * 4 + [-1] * 4 + [UNSETTLED]
    assert count_assignments(state, owners, komi=0).black_area == 4
    with pytest.raises(ValueError):
        score_ownership(state, owners, komi=0)


@pytest.mark.parametrize("komi", [math.nan, math.inf, 0.25])
def test_invalid_komi_is_rejected(komi):
    with pytest.raises(ValueError):
        score_ownership(BoardState.new(size=3), [1] * 9, komi=komi)


@pytest.mark.parametrize("owners", [[1], [0.5] * 9, [True] * 9, [3] * 9])
def test_invalid_assignments_cannot_be_scored(owners):
    with pytest.raises(ValueError):
        score_ownership(BoardState.new(size=3), owners, komi=7.5)
