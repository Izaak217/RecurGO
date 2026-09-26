from __future__ import annotations

from pytestqt.qtbot import QtBot

from recurgo.domain import BoardState, Color, Point
from recurgo.ui.scoring_dialog import CompletedGameDialog, ScoringDialog


def test_scoring_dialog_marks_whole_group_and_exposes_end_choices(
    qtbot: QtBot,
) -> None:
    state = BoardState.from_setup(
        {
            Point(0, 0): Color.BLACK,
            Point(1, 0): Color.BLACK,
            Point(2, 2): Color.WHITE,
        },
        size=3,
    )
    dialog = ScoringDialog(
        state,
        rules="chinese",
        komi=7.5,
        last_move=None,
    )
    qtbot.addWidget(dialog)

    assert dialog.board.ownership is not None

    dialog._toggle_dead_group(0, 0)
    assert dialog.dead_points == {Point(0, 0), Point(1, 0)}
    assert dialog.board.ownership is not None

    dialog._confirm()
    assert dialog.confirmed_score is not None
    assert dialog.confirm_button.isHidden()
    assert not dialog.stay_button.isHidden()
    assert not dialog.new_game_button.isHidden()


def test_completed_game_dialog_can_request_new_game(qtbot: QtBot) -> None:
    dialog = CompletedGameDialog("白胜¼子")
    qtbot.addWidget(dialog)

    dialog._new_game()

    assert dialog.action == "new"
