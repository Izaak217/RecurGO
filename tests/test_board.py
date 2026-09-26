from __future__ import annotations

import pytest

from recurgo.domain import (
    BoardState,
    Color,
    OccupiedPoint,
    OutOfBounds,
    Point,
    SuicideMove,
    SuperkoViolation,
)


def test_capture_single_stone() -> None:
    state = BoardState.from_setup(
        {
            Point(1, 1): Color.WHITE,
            Point(0, 1): Color.BLACK,
            Point(1, 0): Color.BLACK,
            Point(2, 1): Color.BLACK,
        },
        size=5,
        to_play=Color.BLACK,
    )
    result = state.play(Point(1, 2))
    assert result.stone_at(Point(1, 1)) is None
    assert result.black_captures == 1
    assert result.to_play is Color.WHITE


def test_suicide_is_rejected() -> None:
    state = BoardState.from_setup(
        {
            Point(1, 0): Color.BLACK,
            Point(0, 1): Color.BLACK,
            Point(2, 1): Color.BLACK,
            Point(1, 2): Color.BLACK,
        },
        size=3,
        to_play=Color.WHITE,
    )
    with pytest.raises(SuicideMove):
        state.play(Point(1, 1))


def test_immediate_ko_recapture_is_rejected_by_superko() -> None:
    state = BoardState.from_setup(
        {
            Point(0, 1): Color.BLACK,
            Point(1, 0): Color.BLACK,
            Point(1, 2): Color.BLACK,
            Point(1, 1): Color.WHITE,
            Point(2, 0): Color.WHITE,
            Point(2, 2): Color.WHITE,
            Point(3, 1): Color.WHITE,
        },
        size=5,
        to_play=Color.BLACK,
    )
    after_capture = state.play(Point(2, 1))
    assert after_capture.ko_point == Point(1, 1)
    assert after_capture.stone_at(Point(1, 1)) is None
    with pytest.raises(SuperkoViolation):
        after_capture.play(Point(1, 1))


def test_two_passes_end_the_game() -> None:
    state = BoardState.new(size=5)
    state = state.play(None)
    assert not state.is_game_over
    state = state.play(None)
    assert state.is_game_over
    assert state.move_number == 2


def test_occupied_and_out_of_bounds_are_rejected() -> None:
    state = BoardState.new(size=5).play(Point(1, 1))
    with pytest.raises(OccupiedPoint):
        state.play(Point(1, 1))
    with pytest.raises(OutOfBounds):
        state.play(Point(8, 8))
