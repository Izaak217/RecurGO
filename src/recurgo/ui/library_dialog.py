"""Saved-game browser with explicit open and confirmed deletion actions."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from recurgo.i18n import Language
from recurgo.storage import GameRepository, GameSummary

from .formatting import format_result
from .i18n import localize_dialog_buttons, tr


class GameLibraryDialog(QDialog):
    """Browse saved games while keeping single-click and double-click workflows."""

    MODE_NAMES = {
        "manual": "手动打谱",
        "fair": "公平对战",
        "assisted": "辅助对战",
    }

    def __init__(
        self,
        repository: GameRepository,
        *,
        current_game_id: str,
        language: Language = "en",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.current_game_id = current_game_id
        self.language = language
        self.selected_game_id: str | None = None
        self.metadata_updates: dict[str, tuple[str, str, str]] = {}
        self._all_summaries: list[GameSummary] = []
        self._summaries: list[GameSummary] = []

        self.setWindowTitle(self._tr("棋谱库", "Game library"))
        self.resize(1040, 520)
        layout = QVBoxLayout(self)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel(self._tr("搜索棋谱：", "Search games:")))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            self._tr(
                "棋谱名称、黑方、白方、日期、结果或模式", "Name, players, date, result, or mode"
            )
        )
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._search_changed)
        search_row.addWidget(self.search_edit, 1)
        layout.addLayout(search_row)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                self._tr(zh, en)
                for zh, en in (
                    ("棋谱", "Game"),
                    ("黑方", "Black"),
                    ("白方", "White"),
                    ("手数", "Moves"),
                    ("模式", "Mode"),
                    ("结果", "Result"),
                    ("最后保存", "Last saved"),
                )
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self._open_row)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self.table)

        self.hint = QLabel(
            self._tr(
                "单击选择棋谱后点击“进入棋谱”，或直接双击棋谱。",
                "Select a game and click Open, or double-click it.",
            )
        )
        self.hint.setStyleSheet("color: #aeb6bf;")
        layout.addWidget(self.hint)

        buttons = QHBoxLayout()
        self.edit_button = QPushButton(self._tr("修改信息", "Edit details"))
        self.edit_button.clicked.connect(self._edit_selected)
        buttons.addWidget(self.edit_button)
        self.delete_button = QPushButton(self._tr("删除棋谱", "Delete game"))
        self.delete_button.clicked.connect(self._delete_selected)
        buttons.addWidget(self.delete_button)
        buttons.addStretch(1)
        cancel_button = QPushButton(self._tr("取消", "Cancel"))
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        self.open_button = QPushButton(self._tr("进入棋谱", "Open game"))
        self.open_button.setDefault(True)
        self.open_button.clicked.connect(self._open_selected)
        buttons.addWidget(self.open_button)
        layout.addLayout(buttons)

        self._reload()

    def _tr(self, chinese: str, english: str) -> str:
        return tr(self.language, chinese, english)

    def _mode_name(self, mode: str) -> str:
        return self._tr(
            self.MODE_NAMES.get(mode, mode),
            {
                "manual": "Manual study",
                "fair": "Fair play",
                "assisted": "Assisted play",
            }.get(mode, mode),
        )

    def _result_name(self, result: str) -> str:
        return (
            format_result(result, language=self.language)
            if result
            else self._tr("进行中", "In progress")
        )

    def _reload(self, *, select_first: bool = True) -> None:
        self._all_summaries = self.repository.list_games(limit=None)
        self._apply_search(select_first=select_first)

    def _search_changed(self, _text: str) -> None:
        self.selected_game_id = None
        self._apply_search(select_first=False)

    def _apply_search(self, *, select_first: bool) -> None:
        query = self.search_edit.text().strip().casefold()
        self._summaries = [
            summary
            for summary in self._all_summaries
            if not query or query in self._searchable_text(summary)
        ]
        self.table.setRowCount(len(self._summaries))
        for row, summary in enumerate(self._summaries):
            values = [
                summary.name,
                summary.black_player or self._tr("未知", "Unknown"),
                summary.white_player or self._tr("未知", "Unknown"),
                str(summary.move_count),
                self._mode_name(summary.mode),
                self._result_name(summary.result),
                summary.updated_at.replace("T", " ")[:19],
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, summary.id)
                self.table.setItem(row, column, item)
        if select_first and self._summaries:
            self.table.selectRow(0)
        else:
            self.table.clearSelection()
            self.table.setCurrentCell(-1, -1)
        self._selection_changed()

    def _searchable_text(self, summary: GameSummary) -> str:
        displayed_result = self._result_name(summary.result)
        values = (
            summary.name,
            summary.black_player,
            summary.white_player,
            summary.updated_at,
            summary.updated_at.replace("T", " ")[:19],
            summary.result,
            displayed_result,
            summary.mode,
            self.MODE_NAMES.get(summary.mode, summary.mode),
            self._mode_name(summary.mode),
        )
        return "\n".join(values).casefold()

    def _selected_row(self) -> int | None:
        row = self.table.currentRow()
        return row if 0 <= row < len(self._summaries) else None

    def _selection_changed(self) -> None:
        row = self._selected_row()
        has_selection = row is not None
        self.open_button.setEnabled(has_selection)
        self.edit_button.setEnabled(has_selection)
        selected_is_current = (
            False if row is None else self._summaries[row].id == self.current_game_id
        )
        self.delete_button.setEnabled(has_selection and not selected_is_current)
        if not self._summaries and self.search_edit.text().strip():
            self.hint.setText(
                self._tr(
                    "没有匹配的棋谱，可清空搜索条件查看全部棋谱。",
                    "No matching games. Clear the search to see all games.",
                )
            )
        elif selected_is_current:
            self.hint.setText(
                self._tr(
                    "当前正在打开的棋谱不能删除；可双击或点击“进入棋谱”返回。",
                    "The current game cannot be deleted. Double-click it or click Open to return.",
                )
            )
        else:
            self.hint.setText(
                self._tr(
                    "单击选择棋谱后点击“进入棋谱”，或直接双击棋谱。",
                    "Select a game and click Open, or double-click it.",
                )
            )

    def _open_selected(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        self.selected_game_id = self._summaries[row].id
        self.accept()

    def _open_row(self, row: int, _column: int) -> None:
        if not (0 <= row < len(self._summaries)):
            return
        self.table.selectRow(row)
        self.selected_game_id = self._summaries[row].id
        self.accept()

    def _edit_selected(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        summary = self._summaries[row]
        metadata = self._prompt_metadata(summary)
        if metadata is None:
            return
        name, black_player, white_player = metadata
        try:
            self.repository.update_metadata(
                summary.id,
                name=name,
                black_player=black_player,
                white_player=white_player,
            )
        except Exception as error:  # noqa: BLE001 - keep the library usable.
            QMessageBox.critical(
                self,
                self._tr("保存失败", "Save failed"),
                self._tr(
                    f"无法保存棋谱信息。\n\n错误信息：{error}",
                    f"Could not save game details.\n\nError: {error}",
                ),
            )
            return
        self.metadata_updates[summary.id] = (name, black_player, white_player)
        self._reload(select_first=False)
        for updated_row, updated_summary in enumerate(self._summaries):
            if updated_summary.id == summary.id:
                self.table.selectRow(updated_row)
                break
        self.hint.setText(
            self._tr("棋谱名称和对局双方已保存。", "Game name and players saved.")
        )

    def _prompt_metadata(self, summary: GameSummary) -> tuple[str, str, str] | None:
        editor = QDialog(self)
        editor.setWindowTitle(self._tr("修改棋谱信息", "Edit game details"))
        editor.setMinimumWidth(420)
        layout = QVBoxLayout(editor)
        form = QFormLayout()
        name_edit = QLineEdit(summary.name)
        name_edit.setPlaceholderText(self._tr("未命名棋局", "Untitled game"))
        form.addRow(self._tr("棋谱名称：", "Game name:"), name_edit)
        black_edit = QLineEdit(summary.black_player)
        black_edit.setPlaceholderText(self._tr("未知", "Unknown"))
        form.addRow(self._tr("黑方：", "Black:"), black_edit)
        white_edit = QLineEdit(summary.white_player)
        white_edit.setPlaceholderText(self._tr("未知", "Unknown"))
        form.addRow(self._tr("白方：", "White:"), white_edit)
        layout.addLayout(form)
        dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        localize_dialog_buttons(dialog_buttons, self.language)
        dialog_buttons.accepted.connect(editor.accept)
        dialog_buttons.rejected.connect(editor.reject)
        layout.addWidget(dialog_buttons)
        name_edit.selectAll()
        name_edit.setFocus()
        if editor.exec() != QDialog.DialogCode.Accepted:
            return None
        return (
            name_edit.text().strip() or self._tr("未命名棋局", "Untitled game"),
            black_edit.text().strip(),
            white_edit.text().strip(),
        )

    def _delete_selected(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        summary = self._summaries[row]
        if summary.id == self.current_game_id:
            QMessageBox.information(
                self,
                self._tr("不能删除", "Cannot delete"),
                self._tr(
                    "当前正在打开的棋谱不能删除。", "The currently open game cannot be deleted."
                ),
            )
            return
        choice = QMessageBox.question(
            self,
            self._tr("确认删除棋谱", "Confirm deletion"),
            self._tr(
                "确定永久删除以下棋谱吗？\n\n"
                f"棋谱名称：{summary.name}\n黑方：{summary.black_player or '未知'}\n"
                f"白方：{summary.white_player or '未知'}\n总手数：{summary.move_count}\n"
                f"对局模式：{self._mode_name(summary.mode)}\n对局结果：{self._result_name(summary.result)}\n"
                f"最后保存：{summary.updated_at.replace('T', ' ')[:19]}\n\n"
                "该棋谱、全部分支及关联复盘分析数据将被永久删除，且无法撤销。",
                "Permanently delete this game?\n\n"
                f"Name: {summary.name}\nBlack: {summary.black_player or 'Unknown'}\n"
                f"White: {summary.white_player or 'Unknown'}\nMoves: {summary.move_count}\n"
                f"Mode: {self._mode_name(summary.mode)}\nResult: {self._result_name(summary.result)}\n"
                f"Last saved: {summary.updated_at.replace('T', ' ')[:19]}\n\n"
                "This game, all branches, and linked review data will be permanently deleted. This cannot be undone.",
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            self.repository.delete_game(summary.id)
        except Exception as error:  # noqa: BLE001 - keep the library usable on storage errors.
            QMessageBox.critical(
                self,
                self._tr("删除失败", "Deletion failed"),
                self._tr(
                    f"无法删除棋谱“{summary.name}”。数据库未完成本次删除。\n\n错误信息：{error}",
                    f"Could not delete game “{summary.name}”. The database did not complete deletion.\n\nError: {error}",
                ),
            )
            return
        self.selected_game_id = None
        self._reload(select_first=False)
        QMessageBox.information(
            self,
            self._tr("删除成功", "Deleted"),
            self._tr("棋谱及关联复盘数据已删除。", "Game and linked review data deleted."),
        )
