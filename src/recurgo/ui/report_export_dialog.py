"""v1.2.0: choose one saved analysis source for an independent report."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from recurgo.reporting.data import ReportSource

from .i18n import Language, tr


class ReportExportDialog(QDialog):
    def __init__(
        self,
        sources: list[ReportSource],
        *,
        preferred_identity: str = "",
        preferred_visits: int = 0,
        language: Language = "zh",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sources = sources
        self.language = language
        self.setWindowTitle(tr(language, "导出交互式分析报告", "Export interactive report"))
        self.resize(620, 330)
        layout = QVBoxLayout(self)
        introduction = QLabel(tr(
            language,
            "导出逐手棋盘、候选变化和全盘复盘图表。报告保存为单个 HTML 文件，"
            "可使用浏览器（如 Edge、Chrome）打开。",
            "Export the move-by-move board, candidate variations, and review charts "
            "as one HTML file. Open it in a browser, such as Edge or Chrome.",
        ))
        introduction.setWordWrap(True)
        layout.addWidget(introduction)
        layout.addWidget(QLabel(tr(language, "选择已保存的分析", "Saved analysis")))
        self.source_combo = QComboBox()
        preferred_index = 0
        for index, source in enumerate(sources):
            model = source.model_hash[:12] or tr(language, "未知模型", "Unknown model")
            variant = source.identity.removeprefix("legacy-")[:8]
            legacy = tr(language, "旧版记录", "Legacy") if source.identity.startswith(
                "legacy-",
            ) else tr(language, "来源", "Source")
            self.source_combo.addItem(
                f"KataGo {source.engine_version} · {source.visits} visits · "
                f"{model} · {legacy} {variant}",
            )
            if source.identity == preferred_identity and source.visits == preferred_visits:
                preferred_index = index
        self.source_combo.setCurrentIndex(preferred_index)
        self.source_combo.currentIndexChanged.connect(self._update_details)
        layout.addWidget(self.source_combo)
        self.details = QLabel()
        self.details.setWordWrap(True)
        layout.addWidget(self.details)
        note = QLabel(tr(
            language,
            "只导出所选模型和访问量的数据；未分析或不完整的局面会明确标注。"
            "需要补全时，可先运行“全盘 AI 分析”。如果使用浏览器打开后仍无法操作，"
            "请检查浏览器是否已开启 JavaScript。附件预览可能只显示打开说明。",
            "Only the selected model and visit budget are included. Missing or incomplete "
            "analysis is marked explicitly. Run Analyze full game first to fill gaps. "
            "If the report still does not respond after opening it in a browser, "
            "check whether JavaScript is enabled. "
            "Attachment previews may only show opening instructions.",
        ))
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(
            tr(language, "导出 HTML", "Export HTML"),
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(bool(sources))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            tr(language, "取消", "Cancel"),
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._update_details()

    def selected_source(self) -> ReportSource | None:
        index = self.source_combo.currentIndex()
        return self.sources[index] if 0 <= index < len(self.sources) else None

    def _update_details(self, _index: int = 0) -> None:
        source = self.selected_source()
        if source is None:
            self.details.setText(tr(self.language, "暂无已保存的分析。", "No saved analysis."))
            return
        self.details.setText(tr(
            self.language,
            f"已完成分析：{source.completed_positions} 个局面\n"
            f"有保存数据：{source.available_positions} 个局面\n"
            f"最近保存：{source.latest_at}",
            f"Complete analysis: {source.completed_positions} positions\n"
            f"Saved data: {source.available_positions} positions\n"
            f"Last saved: {source.latest_at}",
        ))
