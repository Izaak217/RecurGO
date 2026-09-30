from __future__ import annotations

from pytestqt.qtbot import QtBot

from recurgo.domain import BoardState, Color, Point
from recurgo.domain.score_review import UNASSIGNED
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
        initial_ownership=[1.0] * 6 + [-1.0] * 3,
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


def test_live_snapshot_manual_priority_reset_and_closed_edits(qtbot: QtBot) -> None:
    raw = [0.12, -0.12, 0, 1, -1, 1, -1, 1, -1]
    dialog = ScoringDialog(
        BoardState.new(size=3), rules="chinese", komi=7.5, last_move=None, initial_ownership=raw
    )
    qtbot.addWidget(dialog)
    assert dialog.ownership == (1, -1, 2, 1, -1, 1, -1, 1, -1)
    assert not dialog.confirm_button.isEnabled()
    raw[0] = -1
    assert dialog.ownership[0] == 1
    dialog.brush_combo.setCurrentIndex(3)
    dialog._edit_point(2, 0)
    assert dialog.ownership[2] == 0
    assert dialog.confirm_button.isEnabled()
    dialog._reset_points()
    assert dialog.ownership[2] == UNASSIGNED
    dialog.brush_combo.setCurrentIndex(1)
    dialog._edit_point(2, 0)
    dialog._confirm()
    confirmed = dialog.ownership
    dialog._edit_point(0, 0)
    dialog._reset_points()
    assert dialog.ownership == confirmed


def test_dead_visibility_changes_only_rendering_and_allows_restore(qtbot: QtBot) -> None:
    state = BoardState.from_setup({Point(0, 0): Color.BLACK, Point(1, 0): Color.BLACK}, size=3)
    dialog = ScoringDialog(
        state,
        rules="chinese",
        komi=0,
        last_move=None,
        initial_ownership=[-0.5, -0.5] + [0.5] * 7,
    )
    qtbot.addWidget(dialog)
    assert dialog.dead_points == {Point(0, 0), Point(1, 0)}
    owners = dialog.ownership
    label = dialog.score_label.text()
    for checked in (True, False, True):
        dialog.show_dead_checkbox.setChecked(checked)
        assert dialog.ownership == owners
        assert dialog.score_label.text() == label
        assert dialog.state == state
    dialog._toggle_dead_group(0, 0)
    assert not dialog.dead_points
    assert dialog.ownership[:2] == (1, 1)
    dialog._toggle_dead_group(1, 0)
    assert dialog.dead_points == {Point(0, 0), Point(1, 0)}
    dialog._confirm()
    assert dialog.confirmed_score is not None
    assert dialog.show_dead_checkbox.isEnabled()
    assert not dialog.board._input_enabled


def test_missing_map_and_other_rules_cannot_confirm(qtbot: QtBot) -> None:
    for rules, raw in (("chinese", None), ("japanese", [1.0] * 9)):
        dialog = ScoringDialog(
            BoardState.new(size=3), rules=rules, komi=7.5, last_move=None, initial_ownership=raw
        )
        qtbot.addWidget(dialog)
        dialog._confirm()
        assert dialog.confirmed_score is None
        assert not dialog.confirm_button.isEnabled()


def test_point_override_can_restore_a_saved_dead_stone(qtbot: QtBot) -> None:
    state = BoardState.from_setup({Point(0, 0): Color.BLACK}, size=3)
    dialog = ScoringDialog(
        state,
        rules="chinese",
        komi=0,
        last_move=None,
        confirmed_ownership=(-1,) + (1,) * 8,
        initial_dead_points=frozenset({Point(0, 0)}),
    )
    qtbot.addWidget(dialog)
    dialog.brush_combo.setCurrentIndex(1)
    dialog._edit_point(0, 0)
    assert not dialog.dead_points
