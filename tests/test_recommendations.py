from __future__ import annotations

from recurgo.domain import Color, select_recommended_candidates


def _candidate(
    move: str,
    order: int,
    winrate: float,
    score: float,
    visits: int,
) -> dict[str, object]:
    return {
        "move": move,
        "order": order,
        "winrate": winrate,
        "scoreLead": score,
        "visits": visits,
    }


def _moves(candidates: list[dict[str, object]]) -> list[str]:
    return [str(candidate["move"]) for candidate in candidates]


def test_unique_solution_keeps_only_the_best_move() -> None:
    candidates = [
        _candidate("P5", 0, 0.412, 1.3, 2_194),
        _candidate("Q5", 1, 0.340, -1.1, 1_100),
        _candidate("P4", 2, 0.325, -2.0, 700),
    ]

    selected = select_recommended_candidates(candidates, Color.BLACK)

    assert _moves(selected) == ["P5"]


def test_two_close_moves_are_kept_but_a_large_winrate_loss_is_removed() -> None:
    candidates = [
        _candidate("N5", 0, 0.442, 0.7, 540),
        _candidate("P2", 1, 0.429, 0.8, 340),
        _candidate("M3", 2, 0.332, 3.3, 70),
    ]

    selected = select_recommended_candidates(candidates, Color.BLACK)

    assert _moves(selected) == ["N5", "P2"]


def test_several_supported_nearby_moves_can_fill_all_five_slots() -> None:
    candidates = [
        _candidate("D4", 0, 0.600, 3.0, 500),
        _candidate("Q16", 1, 0.594, 2.7, 310),
        _candidate("D16", 2, 0.588, 2.3, 180),
        _candidate("Q4", 3, 0.580, 1.8, 110),
        _candidate("K10", 4, 0.565, 0.8, 105),
        _candidate("C3", 5, 0.540, -0.2, 300),
    ]

    selected = select_recommended_candidates(candidates, Color.BLACK)

    assert _moves(selected) == ["D4", "Q16", "D16", "Q4", "K10"]


def test_white_perspective_reverses_black_winrate_and_score_direction() -> None:
    candidates = [
        _candidate("N5", 0, 0.420, -2.0, 500),
        _candidate("P2", 1, 0.430, -1.5, 180),
        _candidate("M3", 2, 0.520, 1.5, 300),
    ]

    selected = select_recommended_candidates(candidates, Color.WHITE)

    assert _moves(selected) == ["N5", "P2"]


def test_low_visit_candidate_is_not_promoted_only_to_fill_the_table() -> None:
    candidates = [
        _candidate("D4", 0, 0.550, 1.5, 800),
        _candidate("Q16", 1, 0.545, 1.2, 8),
    ]

    selected = select_recommended_candidates(candidates, Color.BLACK)

    assert _moves(selected) == ["D4"]


def test_missing_evaluation_data_falls_back_to_the_best_move_only() -> None:
    candidates: list[dict[str, object]] = [
        {"move": "D4", "order": 0},
        {"move": "Q16", "order": 1},
    ]

    selected = select_recommended_candidates(candidates, Color.BLACK)

    assert _moves(selected) == ["D4"]


def test_displayed_first_choice_is_always_katago_order_zero() -> None:
    candidates = [
        _candidate("Q16", 2, 0.610, 3.2, 5_000),
        _candidate("D4", 0, 0.600, 3.0, 100),
        _candidate("C3", 1, 0.605, 3.1, 2_000),
    ]

    selected = select_recommended_candidates(candidates, Color.BLACK)

    assert selected[0]["move"] == "D4"
    assert selected[0]["order"] == 0
