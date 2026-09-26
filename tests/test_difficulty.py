from recurgo.domain import BoardState, Point
from recurgo.engine.difficulty import (
    PRESETS,
    human_policy_probability,
    select_ai_move,
)


def _payload(*, best_move: str = "A5") -> dict[str, object]:
    policy = [0.0] * 26
    policy[0] = 0.25
    policy[24] = 0.75
    policy[25] = 0.99
    return {
        "moveInfos": [
            {"move": best_move, "order": 0},
            {"move": "E1", "order": 1},
        ],
        "humanPolicy": policy,
    }


def test_human_difficulty_samples_reproducibly_across_good_and_other_moves() -> None:
    state = BoardState.new(size=5)
    preset = PRESETS["入门"]

    first = select_ai_move(_payload(), state, preset, random_seed=42)
    repeated = select_ai_move(_payload(), state, preset, random_seed=42)
    observed = {
        select_ai_move(_payload(), state, preset, random_seed=seed).point for seed in range(100)
    }

    assert first == repeated
    assert observed == {Point(0, 0), Point(4, 4)}
    assert first.source == "human-policy"


def test_maximum_difficulty_uses_searched_best_move() -> None:
    selection = select_ai_move(
        _payload(),
        BoardState.new(size=5),
        PRESETS["最强"],
        random_seed=1,
    )

    assert selection.point == Point(0, 0)
    assert selection.source == "objective"


def test_human_policy_does_not_pass_early_when_search_prefers_board_move() -> None:
    observed = {
        select_ai_move(
            _payload(),
            BoardState.new(size=5),
            PRESETS["初级"],
            random_seed=seed,
        ).point
        for seed in range(50)
    }

    assert None not in observed


def test_search_pass_overrides_human_board_policy() -> None:
    selection = select_ai_move(
        _payload(best_move="pass"),
        BoardState.new(size=5),
        PRESETS["中级"],
        random_seed=7,
    )

    assert selection.point is None
    assert selection.source == "searched-pass"


def test_human_policy_coordinates_are_top_left_row_major() -> None:
    payload = _payload()

    assert human_policy_probability(payload, "A5", 5) == 0.25
    assert human_policy_probability(payload, "E1", 5) == 0.75
    assert human_policy_probability(payload, "pass", 5) == 0.99
