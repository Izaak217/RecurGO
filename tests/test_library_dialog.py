from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from recurgo.domain import GameTree
from recurgo.storage import GameRepository
from recurgo.ui.library_dialog import GameLibraryDialog


def _row_for_game(dialog: GameLibraryDialog, game_id: str) -> int:
    for row in range(dialog.table.rowCount()):
        item = dialog.table.item(row, 0)
        if item is not None and item.data(Qt.ItemDataRole.UserRole) == game_id:
            return row
    raise AssertionError(f"game not found: {game_id}")


def _visible_game_ids(dialog: GameLibraryDialog) -> set[str]:
    return {
        str(item.data(Qt.ItemDataRole.UserRole))
        for row in range(dialog.table.rowCount())
        if (item := dialog.table.item(row, 0)) is not None
    }


def test_single_selection_open_and_double_click_open_exact_row(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    repository = GameRepository(tmp_path / "library.db")
    first = repository.create_game(GameTree(), name="第一盘")
    second = repository.create_game(GameTree(), name="第二盘")

    single_dialog = GameLibraryDialog(
        repository,
        current_game_id=first.id,
    )
    qtbot.addWidget(single_dialog)
    single_dialog.table.selectRow(_row_for_game(single_dialog, second.id))
    single_dialog._open_selected()
    assert single_dialog.selected_game_id == second.id
    assert single_dialog.result() == GameLibraryDialog.DialogCode.Accepted

    double_dialog = GameLibraryDialog(
        repository,
        current_game_id=first.id,
    )
    qtbot.addWidget(double_dialog)
    target_row = _row_for_game(double_dialog, second.id)
    double_dialog._open_row(target_row, 0)
    assert double_dialog.selected_game_id == second.id
    assert double_dialog.result() == GameLibraryDialog.DialogCode.Accepted
    repository.close()


def test_delete_button_permanently_deletes_selected_noncurrent_game(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = GameRepository(tmp_path / "library-delete.db")
    current = repository.create_game(GameTree(), name="当前")
    doomed = repository.create_game(GameTree(), name="删除我")
    dialog = GameLibraryDialog(repository, current_game_id=current.id)
    qtbot.addWidget(dialog)
    dialog.table.selectRow(_row_for_game(dialog, doomed.id))
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Ok,
    )

    dialog._delete_selected()

    with pytest.raises(KeyError):
        repository.load_game(doomed.id)
    assert dialog.table.rowCount() == 1
    assert dialog.table.currentRow() == -1
    assert dialog.table.selectedItems() == []
    assert dialog.open_button.isEnabled() is False
    assert dialog.edit_button.isEnabled() is False
    assert dialog.delete_button.isEnabled() is False
    assert dialog.selected_game_id is None
    repository.close()


def test_library_can_edit_game_name_and_both_players(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = GameRepository(tmp_path / "library-edit.db")
    current = repository.create_game(GameTree(), name="当前")
    target = repository.create_game(GameTree(), name="修改前")
    dialog = GameLibraryDialog(repository, current_game_id=current.id)
    qtbot.addWidget(dialog)
    dialog.table.selectRow(_row_for_game(dialog, target.id))
    monkeypatch.setattr(
        dialog,
        "_prompt_metadata",
        lambda _summary: ("修改后", "黑方棋手", "白方棋手"),
    )

    dialog._edit_selected()

    loaded, _tree = repository.load_game(target.id)
    assert loaded.name == "修改后"
    assert loaded.black_player == "黑方棋手"
    assert loaded.white_player == "白方棋手"
    assert dialog.metadata_updates[target.id] == ("修改后", "黑方棋手", "白方棋手")
    selected_row = _row_for_game(dialog, target.id)
    assert dialog.table.currentRow() == selected_row
    assert dialog.table.item(selected_row, 0).text() == "修改后"
    assert dialog.table.item(selected_row, 1).text() == "黑方棋手"
    assert dialog.table.item(selected_row, 2).text() == "白方棋手"
    repository.close()


def test_library_searches_displayed_metadata_result_date_and_mode(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    repository = GameRepository(tmp_path / "library-search.db")
    current = repository.create_game(GameTree(), name="当前对局")
    spring = repository.create_game(
        GameTree(),
        name="春季棋谱",
        black_player="Alpha",
        white_player="白方乙",
        mode="manual",
    )
    repository.finish_game(spring.id, "B+R")
    training = repository.create_game(
        GameTree(),
        name="训练对局",
        black_player="黑方丙",
        white_player="Delta",
        mode="assisted",
    )
    with repository.connection:
        repository.connection.execute(
            "UPDATE games SET updated_at = '2026-04-03T08:09:10+00:00' WHERE id = ?",
            (spring.id,),
        )
        repository.connection.execute(
            "UPDATE games SET updated_at = '2026-05-04T08:09:10+00:00' WHERE id = ?",
            (training.id,),
        )
    dialog = GameLibraryDialog(repository, current_game_id=current.id, language="zh")
    qtbot.addWidget(dialog)

    for query in ("春季", "Alpha", "白方乙", "2026-04-03", "黑中盘胜"):
        dialog.search_edit.setText(query)
        assert _visible_game_ids(dialog) == {spring.id}

    dialog.search_edit.setText("辅助对战")
    assert _visible_game_ids(dialog) == {training.id}
    dialog.search_edit.setText("Delta")
    assert _visible_game_ids(dialog) == {training.id}
    dialog.search_edit.clear()
    assert _visible_game_ids(dialog) == {current.id, spring.id, training.id}
    repository.close()


def test_filtered_game_can_still_be_opened_by_double_click(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    repository = GameRepository(tmp_path / "library-filter-open.db")
    current = repository.create_game(GameTree(), name="当前")
    target = repository.create_game(GameTree(), name="唯一目标")
    dialog = GameLibraryDialog(repository, current_game_id=current.id)
    qtbot.addWidget(dialog)
    dialog.search_edit.setText("唯一目标")

    dialog._open_row(0, 0)

    assert dialog.selected_game_id == target.id
    assert dialog.result() == GameLibraryDialog.DialogCode.Accepted
    repository.close()


def test_filtered_game_can_still_be_edited_and_deleted(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = GameRepository(tmp_path / "library-filter-actions.db")
    current = repository.create_game(GameTree(), name="当前")
    target = repository.create_game(GameTree(), name="目标原名")
    dialog = GameLibraryDialog(repository, current_game_id=current.id)
    qtbot.addWidget(dialog)
    dialog.search_edit.setText("目标")
    dialog.table.selectRow(0)
    monkeypatch.setattr(
        dialog,
        "_prompt_metadata",
        lambda _summary: ("目标新名", "黑方", "白方"),
    )

    dialog._edit_selected()

    assert dialog.table.rowCount() == 1
    assert repository.load_game(target.id)[0].name == "目标新名"
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Ok,
    )
    dialog._delete_selected()

    assert dialog.table.rowCount() == 0
    assert dialog.selected_game_id is None
    with pytest.raises(KeyError):
        repository.load_game(target.id)
    repository.close()


def test_delete_confirmation_describes_selected_game(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = GameRepository(tmp_path / "library-confirm.db")
    current = repository.create_game(GameTree(), name="当前")
    doomed_tree = GameTree()
    doomed = repository.create_game(
        doomed_tree,
        name="待确认棋谱",
        black_player="黑方甲",
        white_player="白方乙",
        mode="manual",
    )
    move, _created = doomed_tree.play(None)
    repository.save_node(doomed.id, move)
    dialog = GameLibraryDialog(repository, current_game_id=current.id, language="zh")
    qtbot.addWidget(dialog)
    dialog.table.selectRow(_row_for_game(dialog, doomed.id))
    confirmation_texts: list[str] = []

    def reject_delete(*args: object, **_kwargs: object) -> QMessageBox.StandardButton:
        confirmation_texts.append(str(args[2]))
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", reject_delete)

    dialog._delete_selected()

    assert confirmation_texts
    confirmation = confirmation_texts[0]
    assert "棋谱名称：待确认棋谱" in confirmation
    assert "黑方：黑方甲" in confirmation
    assert "白方：白方乙" in confirmation
    assert "总手数：1" in confirmation
    assert "对局模式：手动打谱" in confirmation
    assert "对局结果：进行中" in confirmation
    assert "最后保存：" in confirmation
    assert "全部分支及关联复盘分析数据" in confirmation
    assert repository.load_game(doomed.id)[0].name == "待确认棋谱"
    repository.close()


def test_delete_failure_keeps_selection_and_library_usable(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = GameRepository(tmp_path / "library-failure.db")
    current = repository.create_game(GameTree(), name="当前")
    doomed = repository.create_game(GameTree(), name="删除失败棋谱")
    dialog = GameLibraryDialog(repository, current_game_id=current.id)
    qtbot.addWidget(dialog)
    doomed_row = _row_for_game(dialog, doomed.id)
    dialog.table.selectRow(doomed_row)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    errors: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda _parent, _title, message: errors.append(message)
        or QMessageBox.StandardButton.Ok,
    )

    def fail_delete(_game_id: str) -> None:
        raise RuntimeError("模拟数据库错误")

    monkeypatch.setattr(repository, "delete_game", fail_delete)

    dialog._delete_selected()

    assert errors and "模拟数据库错误" in errors[0]
    assert repository.load_game(doomed.id)[0].name == "删除失败棋谱"
    assert dialog.table.rowCount() == 2
    assert dialog.table.currentRow() == doomed_row
    assert dialog.delete_button.isEnabled() is True
    assert dialog.open_button.isEnabled() is True
    repository.close()
