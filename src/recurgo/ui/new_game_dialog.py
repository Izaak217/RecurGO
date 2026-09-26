"""Integrated new-game setup dialog."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from recurgo.engine import PRESETS

from .i18n import Language, localize_dialog_buttons, tr

MODE_VALUES = {
    "手动打谱": "manual",
    "公平对战": "fair",
    "辅助对战": "assisted",
}


@dataclass(frozen=True, slots=True)
class NewGameOptions:
    name: str
    black_player: str
    white_player: str
    mode: str
    human_color: str
    difficulty: str


class NewGameDialog(QDialog):
    """Collect game metadata as part of creating a game, not as a separate tool."""

    def __init__(
        self,
        *,
        initial_mode: str,
        initial_human_color: str,
        initial_difficulty: str,
        language: Language = "en",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.setWindowTitle(tr(language, "创建新棋局", "Create new game"))
        self.setMinimumWidth(430)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(tr(language, "未命名棋局", "Untitled game"))
        self.name_edit.setPlaceholderText(tr(language, "未命名棋局", "Untitled game"))
        form.addRow(tr(language, "棋谱名称：", "Game name:"), self.name_edit)
        self.black_edit = QLineEdit()
        self.black_edit.setPlaceholderText(tr(language, "可留空", "Optional"))
        form.addRow(tr(language, "黑方：", "Black:"), self.black_edit)
        self.white_edit = QLineEdit()
        self.white_edit.setPlaceholderText(tr(language, "可留空", "Optional"))
        form.addRow(tr(language, "白方：", "White:"), self.white_edit)

        self.mode_combo = QComboBox()
        for chinese, english, value in (
            ("手动打谱", "Manual study", "manual"),
            ("公平对战", "Fair play", "fair"),
            ("辅助对战", "Assisted play", "assisted"),
        ):
            self.mode_combo.addItem(tr(language, chinese, english), value)
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(initial_mode)))
        self.mode_combo.currentTextChanged.connect(self._mode_changed)
        form.addRow(tr(language, "模式：", "Mode:"), self.mode_combo)

        self.human_color_combo = QComboBox()
        self.human_color_combo.addItem(tr(language, "我执黑", "Black"), "black")
        self.human_color_combo.addItem(tr(language, "我执白", "White"), "white")
        self.human_color_combo.setCurrentIndex(
            max(0, self.human_color_combo.findData(initial_human_color))
        )
        form.addRow(tr(language, "执色：", "Play as:"), self.human_color_combo)

        self.difficulty_combo = QComboBox()
        for chinese, english in (
            ("入门", "Beginner"),
            ("初级", "Elementary"),
            ("中级", "Intermediate"),
            ("高级", "Advanced"),
            ("顶级", "Expert"),
            ("最强", "Strongest"),
        ):
            self.difficulty_combo.addItem(tr(language, chinese, english), chinese)
        difficulty = initial_difficulty if initial_difficulty in PRESETS else "中级"
        self.difficulty_combo.setCurrentIndex(self.difficulty_combo.findData(difficulty))
        form.addRow(tr(language, "对战难度：", "Play difficulty:"), self.difficulty_combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        localize_dialog_buttons(buttons, language)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._mode_changed(self.mode_combo.currentText())
        self.name_edit.selectAll()
        self.name_edit.setFocus()

    def _mode_changed(self, label: str) -> None:
        is_battle = self.mode_combo.currentData() in {"fair", "assisted"}
        self.human_color_combo.setEnabled(is_battle)
        self.difficulty_combo.setEnabled(is_battle)

    def options(self) -> NewGameOptions:
        return NewGameOptions(
            name=self.name_edit.text().strip()
            or tr(self.language, "未命名棋局", "Untitled game"),
            black_player=self.black_edit.text().strip(),
            white_player=self.white_edit.text().strip(),
            mode=str(self.mode_combo.currentData()),
            human_color=str(self.human_color_combo.currentData()),
            difficulty=str(self.difficulty_combo.currentData()),
        )


__all__ = ["MODE_VALUES", "NewGameDialog", "NewGameOptions"]
