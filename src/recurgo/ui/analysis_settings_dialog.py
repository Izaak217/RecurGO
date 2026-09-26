"""Persistent search-budget setting for objective analysis and review."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .i18n import Language, localize_dialog_buttons, tr


@dataclass(frozen=True, slots=True)
class AnalysisSettings:
    visits: int = 800

    @classmethod
    def from_mapping(cls, raw: dict[str, object] | None) -> AnalysisSettings:
        value = raw.get("visits") if raw is not None else None
        if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 1_000_000:
            return cls(value)
        return cls()

    def to_mapping(self) -> dict[str, object]:
        return {"visits": self.visits}


class AnalysisSettingsDialog(QDialog):
    def __init__(
        self,
        settings: AnalysisSettings,
        parent: QWidget | None = None,
        *,
        language: Language = "en",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr(language, "分析设置", "Analysis settings"))
        self.resize(480, 200)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.visits_spin = QSpinBox()
        self.visits_spin.setRange(1, 1_000_000)
        self.visits_spin.setValue(settings.visits)
        self.visits_spin.setSuffix(" visits")
        form.addRow(tr(language, "每个局面的访问量", "Visits per position"), self.visits_spin)
        layout.addLayout(form)
        notice = QLabel(
            tr(
                language,
                "默认 800。提高访问量通常需要更久；降低访问量可能使搜索不充分。"
                "此设置仅影响实时分析与全盘复盘，不影响对战中的“最强”AI。",
                "The default is 800. More visits usually take longer; fewer visits can leave the search incomplete. This setting affects real-time analysis and full-game review, not Strongest play.",
            )
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        localize_dialog_buttons(buttons, language)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def settings(self) -> AnalysisSettings:
        return AnalysisSettings(self.visits_spin.value())
