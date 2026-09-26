"""Draft-only settings and model discovery for the local Ollama service."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from recurgo.i18n import localize_error
from recurgo.llm.ollama import OllamaClient
from recurgo.llm.settings import OllamaSettings

from .i18n import Language, localize_dialog_buttons, tr


class OllamaSettingsDialog(QDialog):
    def __init__(
        self,
        settings: OllamaSettings,
        client: OllamaClient,
        parent: QWidget | None = None,
        *,
        language: Language = "en",
    ) -> None:
        super().__init__(parent)
        self.language = language
        self._settings = settings
        self._client = client
        self._list_request_id: str | None = None
        self._signals_connected = True
        self.setWindowTitle(tr(language, "本机 AI 解释设置", "Local AI explanation settings"))
        self.resize(570, 310)

        layout = QVBoxLayout(self)
        notice = QLabel(
            tr(
                language,
                "本机 Ollama 可补充文字解释；落点、胜率和目差仍由 KataGo 计算。"
                "此处可设置服务地址并选择已安装的模型，不会下载模型。"
                "首次配置请参阅《安装指南》中的“可选：使用 Ollama 补充棋理讲解”。",
                "Local Ollama can add text explanations; KataGo still calculates moves, win rates, and score leads. "
                "Set the service address and choose an installed model here. No model is downloaded. "
                "For first-time setup, see 'Optional: use Ollama for supplemental explanations' in the Installation Guide.",
            )
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.enabled_checkbox = QCheckBox(
            tr(language, "启用本机 AI 棋理解释", "Enable local AI explanations")
        )
        self.enabled_checkbox.setChecked(settings.enabled)
        layout.addWidget(self.enabled_checkbox)

        form = QFormLayout()
        self.base_url_edit = QLineEdit(settings.base_url)
        self.base_url_edit.setPlaceholderText("http://127.0.0.1:11434")
        form.addRow(tr(language, "本机服务地址", "Local service address"), self.base_url_edit)
        model_row = QHBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItem(settings.model)
        model_row.addWidget(self.model_combo, 1)
        self.detect_button = QPushButton(tr(language, "检测本机模型", "Detect local models"))
        self.detect_button.clicked.connect(self._detect_models)
        model_row.addWidget(self.detect_button)
        form.addRow(tr(language, "模型", "Model"), model_row)
        layout.addLayout(form)
        self.status_label = QLabel(
            tr(
                language,
                "仅连接本机 HTTP 服务；请先启动 Ollama。",
                "Only a local HTTP service is allowed. Start Ollama first.",
            )
        )
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        localize_dialog_buttons(self.buttons, language)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.base_url_edit.textChanged.connect(self._endpoint_changed)
        self._client.models_ready.connect(self._models_ready)
        self._client.request_failed.connect(self._request_failed)

    def settings(self) -> OllamaSettings:
        return self._settings

    def _cancel_model_detection(self) -> None:
        request_id = self._list_request_id
        self._list_request_id = None
        if request_id is not None:
            self._client.cancel(request_id)
        self.detect_button.setEnabled(True)

    def _endpoint_changed(self, _text: str) -> None:
        self._cancel_model_detection()
        self.status_label.setText(
            tr(
                self.language,
                "服务地址已修改；可重新检测本机模型。",
                "Service address changed. You can detect local models again.",
            )
        )

    def _detect_models(self) -> None:
        if self._list_request_id is not None:
            return
        try:
            request_id = self._client.list_models(self.base_url_edit.text())
        except ValueError as exc:
            self.status_label.setText(localize_error(str(exc), self.language))
            return
        self._list_request_id = request_id
        self.detect_button.setEnabled(False)
        self.status_label.setText(
            tr(self.language, "正在检测本机 Ollama…", "Detecting local Ollama…")
        )

    def _models_ready(self, request_id: str, models: object) -> None:
        if request_id != self._list_request_id:
            return
        self._list_request_id = None
        self.detect_button.setEnabled(True)
        names = (
            [name for name in models if isinstance(name, str)]
            if isinstance(models, list)
            else []
        )
        if not names:
            self.status_label.setText(
                tr(
                    self.language,
                    "服务已连接，但未发现可用的本机模型。请先在 Ollama 下载模型。",
                    "Connected, but no usable local model was found. Download a model in Ollama first.",
                )
            )
            return
        previous = self.model_combo.currentText()
        self.model_combo.clear()
        self.model_combo.addItems(names)
        if previous in names:
            self.model_combo.setCurrentText(previous)
        self.status_label.setText(
            tr(
                self.language,
                f"检测到 {len(names)} 个本机模型；保存后才会应用设置。",
                f"Found {len(names)} local models. Save to apply the setting.",
            )
        )

    def _request_failed(self, request_id: str, message: str) -> None:
        if request_id != self._list_request_id:
            return
        self._list_request_id = None
        self.detect_button.setEnabled(True)
        self.status_label.setText(
            tr(
                self.language,
                f"检测失败：{message}",
                f"Detection failed: {localize_error(message, self.language)}",
            )
        )

    def accept(self) -> None:
        try:
            settings = OllamaSettings(
                enabled=self.enabled_checkbox.isChecked(),
                base_url=self.base_url_edit.text(),
                model=self.model_combo.currentText(),
            )
        except ValueError as exc:
            self.status_label.setText(localize_error(str(exc), self.language))
            return
        self._settings = settings
        super().accept()

    def done(self, result: int) -> None:
        self._cancel_model_detection()
        if self._signals_connected:
            self._signals_connected = False
            self._client.models_ready.disconnect(self._models_ready)
            self._client.request_failed.disconnect(self._request_failed)
        super().done(result)
