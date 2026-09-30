from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from recurgo.domain import BoardState, Color, Point
from recurgo.domain.score_review import UNASSIGNED
from recurgo.i18n import Language
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


@pytest.mark.parametrize("language", ["zh", "en"])
def test_confirmation_hint_tracks_edits_reset_and_confirmation(
    qtbot: QtBot, language: Language,
) -> None:
    dialog = ScoringDialog(
        BoardState.new(size=3), rules="chinese", komi=7.5, last_move=None,
        initial_ownership=[0.0] * 2 + [1.0] * 7, language=language,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.confirm_hint.isVisible()
    assert "2" in dialog.confirm_hint.text()
    assert dialog.confirm_hint.geometry().bottom() <= dialog.confirm_button.geometry().top()
    assert dialog.confirm_hint.text() == dialog.confirm_button.accessibleDescription()
    dialog.brush_combo.setCurrentIndex(1)
    dialog._edit_point(0, 0)
    assert "1" in dialog.confirm_hint.text()
    assert not dialog.confirm_button.isEnabled()
    dialog._edit_point(1, 0)
    assert dialog.confirm_hint.isHidden()
    assert dialog.confirm_button.toolTip() == ""
    assert dialog.confirm_button.isEnabled()
    dialog._reset_points()
    assert dialog.confirm_hint.isVisible()
    assert "2" in dialog.confirm_hint.text()
    dialog._edit_point(0, 0)
    dialog._edit_point(1, 0)
    dialog._confirm()
    assert dialog.confirmed_score is not None
    assert dialog.confirm_hint.isHidden()


@pytest.mark.parametrize("language", ["zh", "en"])
@pytest.mark.parametrize("reason", ["missing", "rules", "komi"])
def test_disabled_confirmation_explains_the_actual_blocker(
    qtbot: QtBot, language: Language, reason: str,
) -> None:
    dialog = ScoringDialog(
        BoardState.new(size=3), rules="japanese" if reason == "rules" else "chinese",
        komi=7.25 if reason == "komi" else 7.5, last_move=None,
        initial_ownership=None if reason == "missing" else [1.0] * 9, language=language,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    assert not dialog.confirm_button.isEnabled()
    expected = {
        "zh": {"missing": "尚未载入", "rules": "中国围棋规则", "komi": "贴目无效"},
        "en": {"missing": "No live territory", "rules": "Chinese rules only", "komi": "komi"},
    }
    assert expected[language][reason] in dialog.confirm_hint.text()
    assert dialog.confirm_hint.isVisible()
    if reason == "missing":
        dialog.brush_combo.setCurrentIndex(1)
        for y in range(3):
            for x in range(3):
                dialog._edit_point(x, y)
        assert dialog.confirm_hint.isHidden()
        assert dialog.confirm_button.isEnabled()
