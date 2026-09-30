import json
from dataclasses import replace
from pathlib import Path

import pytest

from recurgo.domain import BoardState, Color, Point
from recurgo.domain.scoring_estimate import UNSETTLED, prepare_proposal
from recurgo.domain.scoring_shape import shape_ownership

CASES = json.loads((Path(__file__).parent / "fixtures/scoring_cases.json").read_text())
LARGE_CASES = json.loads((Path(__file__).parent / "fixtures/scoring_cases_19.json").read_text())


def position(case):
    state = BoardState.from_setup({
        Point(x, y): Color.BLACK if ch == "X" else Color.WHITE
        for y, row in enumerate(case["board"]) for x, ch in enumerate(row) if ch != "."
    }, size=len(case["board"]))
    for _ in range(case["passes"]):
        state = state.play(None)
    return state


@pytest.mark.parametrize("case", CASES + LARGE_CASES,
                         ids=lambda c: f"{c['name']}-{len(c['board'])}")
def test_shapes_correct_noisy_first_predictions_without_manual_input(case):
    state = position(case)
    expected = tuple({"B": 1, "W": -1, "S": 0, "?": 2}[ch]
                     for row in case["expected"] for ch in row)
    # Deliberately weak/zero predictions; dead stones still need engine support.
    values = [0.7 if v == 1 else -0.7 if v == -1 else 0.0 for v in expected]
    if case["name"] == "dead_stone_in_live_territory":
        for y, row in enumerate(case["board"]):
            for x, ch in enumerate(row):
                if ch == "O":
                    values[y * state.size + x] = 0.99
    assert prepare_proposal(state, values, [0.05] * len(values)) == expected
    assert state == position(case)


def test_proven_live_group_and_eyes_override_bad_ai_but_not_the_board():
    state = position(CASES[0])
    assert prepare_proposal(state, [-1.] * 25, [0.0] * 25) == (1,) * 25
    assert state.stone_at(Point(1, 1)) is None


def test_single_eye_and_open_space_are_not_unconditional_life():
    state = BoardState.from_setup({
        Point(x, y): Color.BLACK for y in range(5) for x in range(5)
        if (x, y) != (2, 2)
    }, size=5)
    assert not shape_ownership(state)
    assert prepare_proposal(state, [0.] * 25) == (UNSETTLED,) * 25
    assert not shape_ownership(BoardState.new(size=19).play(Point(3, 3)))


def test_external_escape_prevents_seki_classification():
    state = position(CASES[1])
    stones = list(state.stones)
    stones[0] = 0
    escaped = replace(state, stones=tuple(stones), consecutive_passes=0)
    assert 0 not in shape_ownership(escaped).values()


def test_known_ko_is_not_automatically_shared():
    state = replace(position(CASES[1]), ko_point=Point(2, 1))
    assert 0 not in shape_ownership(state).values()
    assert prepare_proposal(state, [1.] * 25)[7] == UNSETTLED


def test_large_invadable_space_is_not_filled_just_because_boundary_is_alive():
    stones = {Point(x, y): Color.BLACK for y in range(9) for x in range(9)
              if x <= 1 or y in (0, 8) or x == 8}
    stones.pop(Point(0, 2))
    stones.pop(Point(0, 6))
    state = BoardState.from_setup(stones, size=9)
    proposal = prepare_proposal(state, [0.] * 81)
    assert proposal[4 * 9 + 4] == UNSETTLED
    assert proposal[2 * 9] == 1


def test_group_consistency_pools_matching_signals_without_overruling_disagreement():
    state = BoardState.from_setup({Point(x, 0): Color.BLACK for x in range(4)}, size=5)
    values = [0.99] * 3 + [0.7] + [0.] * 21
    assert prepare_proposal(state, values)[:4] == (1,) * 4
    values[3] = -0.99
    assert prepare_proposal(state, values)[:4] == (UNSETTLED,) * 4


def test_variation_withholds_unstable_prediction_and_rejects_invalid_statistics():
    state = BoardState.new(size=3)
    assert prepare_proposal(state, [0.95] * 9, [0.6] * 9) == (UNSETTLED,) * 9
    assert prepare_proposal(state, [0.95] * 9, [0.02] * 9) == (1,) * 9
    for invalid in ([float("nan")] * 9, [True] * 9, [1.1] * 9, [0.1]):
        assert prepare_proposal(state, [0.95] * 9, invalid) is None
