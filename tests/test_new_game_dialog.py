from __future__ import annotations

from pytestqt.qtbot import QtBot

from recurgo.ui.new_game_dialog import NewGameDialog


def test_new_game_dialog_collects_metadata_and_battle_settings(qtbot: QtBot) -> None:
    dialog = NewGameDialog(
        initial_mode="assisted",
        initial_human_color="white",
        initial_difficulty="高级",
    )
    qtbot.addWidget(dialog)
    dialog.name_edit.setText("测试对局")
    dialog.black_edit.setText("黑方棋手")
    dialog.white_edit.setText("白方棋手")

    options = dialog.options()

    assert options.name == "测试对局"
    assert options.black_player == "黑方棋手"
    assert options.white_player == "白方棋手"
    assert options.mode == "assisted"
    assert options.human_color == "white"
    assert options.difficulty == "高级"
    assert dialog.human_color_combo.isEnabled()
    assert dialog.difficulty_combo.isEnabled()


def test_new_game_dialog_disables_battle_only_fields_for_manual_mode(
    qtbot: QtBot,
) -> None:
    dialog = NewGameDialog(
        initial_mode="manual",
        initial_human_color="black",
        initial_difficulty="中级",
        language="zh",
    )
    qtbot.addWidget(dialog)

    assert not dialog.human_color_combo.isEnabled()
    assert not dialog.difficulty_combo.isEnabled()
    assert dialog.options().name == "未命名棋局"
