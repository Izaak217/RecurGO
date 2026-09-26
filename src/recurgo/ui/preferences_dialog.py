"""Appearance and built-in sound selection dialog."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from recurgo.domain import BoardState, Color, Point

from .audio import AudioFeedback
from .board_widget import BoardWidget
from .i18n import localize_dialog_buttons, normalize_language, tr
from .preferences import (
    BOARD_THEMES,
    CAPTURE_SOUNDS,
    PLACEMENT_SOUNDS,
    STONE_STYLES,
    AppPreferences,
)


class PreferencesDialog(QDialog):
    def __init__(self, preferences: AppPreferences, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._initial = preferences
        self.language = normalize_language(preferences.language)
        self.setWindowTitle(tr(self.language, "偏好设置", "Preferences"))
        self.resize(760, 680)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(
            self._build_appearance_tab(), tr(self.language, "棋盘与棋子", "Board and stones")
        )
        tabs.addTab(self._build_sound_tab(), tr(self.language, "声音", "Sound"))
        tabs.addTab(self._build_language_tab(), "Language / 语言")
        layout.addWidget(tabs, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        localize_dialog_buttons(buttons, self.language)
        reset_button = buttons.addButton(
            tr(self.language, "恢复默认", "Restore defaults"),
            QDialogButtonBox.ButtonRole.ResetRole,
        )
        reset_button.clicked.connect(self._reset_defaults)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._preview_audio = AudioFeedback(self)
        self._load_preferences(preferences)

    def _build_language_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("简体中文", "zh")
        form.addRow("Language / 语言", self.language_combo)
        layout.addLayout(form)
        note = QLabel(
            tr(
                self.language,
                "点击确定后界面立即切换；新的本机 AI 讲解使用所选语言。",
                "Select OK to switch the interface immediately. New local AI explanations use the selected language.",
            )
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    def _build_appearance_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.board_combo = QComboBox()
        theme_labels_en = {
            "classic": "Classic kaya",
            "light": "Light maple",
            "dark": "Dark walnut",
            "paper": "Paper board",
        }
        for key, theme in BOARD_THEMES.items():
            self.board_combo.addItem(tr(self.language, theme.label, theme_labels_en[key]), key)
        self.board_combo.currentIndexChanged.connect(self._update_board_preview)
        form.addRow(tr(self.language, "棋盘主题", "Board theme"), self.board_combo)

        self.stone_combo = QComboBox()
        stone_labels_en = {
            "classic": "Classic 3D",
            "matte": "Matte ceramic",
            "jade": "Jade",
            "flat": "Flat",
        }
        for key, style in STONE_STYLES.items():
            self.stone_combo.addItem(tr(self.language, style.label, stone_labels_en[key]), key)
        self.stone_combo.currentIndexChanged.connect(self._update_board_preview)
        form.addRow(tr(self.language, "棋子样式", "Stone style"), self.stone_combo)

        background_row = QHBoxLayout()
        self.custom_board_path = QLineEdit()
        self.custom_board_path.setReadOnly(True)
        self.custom_board_path.setPlaceholderText(
            tr(self.language, "未使用自定义棋盘背景", "No custom board background")
        )
        browse = QPushButton(tr(self.language, "选择图片…", "Choose image…"))
        browse.clicked.connect(self._choose_board_background)
        clear = QPushButton(tr(self.language, "清除", "Clear"))
        clear.clicked.connect(self._clear_board_background)
        background_row.addWidget(self.custom_board_path, 1)
        background_row.addWidget(browse)
        background_row.addWidget(clear)
        form.addRow(tr(self.language, "自定义棋盘", "Custom board"), background_row)
        layout.addLayout(form)

        note = QLabel(
            tr(
                self.language,
                "棋子仅提供内置样式；候选点、末手、领地和死子标记不受主题影响。",
                "Only built-in stone styles are available. Candidate, last-move, ownership, and dead-stone markers are unchanged by the theme.",
            )
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #aeb6bf;")
        layout.addWidget(note)

        self.board_preview = BoardWidget()
        self.board_preview.setMinimumSize(430, 430)
        self.board_preview.set_input_enabled(False)
        sample = BoardState.from_setup(
            {
                Point(3, 3): Color.BLACK,
                Point(4, 3): Color.WHITE,
                Point(9, 9): Color.BLACK,
                Point(15, 15): Color.WHITE,
            },
            size=19,
        )
        self.board_preview.set_position(sample, Point(15, 15))
        layout.addWidget(self.board_preview, 1, Qt.AlignmentFlag.AlignCenter)
        return page

    def _build_sound_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()

        placement_row = QHBoxLayout()
        self.placement_combo = QComboBox()
        sound_labels_en = {"wood": "Wooden", "crisp": "Crisp", "soft": "Soft"}
        for key, label in PLACEMENT_SOUNDS.items():
            self.placement_combo.addItem(tr(self.language, label, sound_labels_en[key]), key)
        self.placement_combo.currentIndexChanged.connect(self._configure_preview_audio)
        placement_preview = QPushButton(tr(self.language, "试听", "Preview"))
        placement_preview.clicked.connect(self._preview_placement)
        placement_row.addWidget(self.placement_combo, 1)
        placement_row.addWidget(placement_preview)
        form.addRow(tr(self.language, "落子声", "Move sound"), placement_row)

        capture_row = QHBoxLayout()
        self.capture_combo = QComboBox()
        capture_labels_en = {"wood": "Repeated wooden", "crisp": "Crisp", "soft": "Soft"}
        for key, label in CAPTURE_SOUNDS.items():
            self.capture_combo.addItem(tr(self.language, label, capture_labels_en[key]), key)
        self.capture_combo.currentIndexChanged.connect(self._configure_preview_audio)
        capture_preview = QPushButton(tr(self.language, "试听", "Preview"))
        capture_preview.clicked.connect(self._preview_capture)
        capture_row.addWidget(self.capture_combo, 1)
        capture_row.addWidget(capture_preview)
        form.addRow(tr(self.language, "提子声", "Capture sound"), capture_row)

        volume_row = QHBoxLayout()
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.valueChanged.connect(self._volume_changed)
        self.volume_label = QLabel()
        self.volume_label.setMinimumWidth(48)
        volume_row.addWidget(self.volume_slider, 1)
        volume_row.addWidget(self.volume_label)
        form.addRow(tr(self.language, "音量", "Volume"), volume_row)
        layout.addLayout(form)
        layout.addStretch(1)

        note = QLabel(
            tr(
                self.language,
                "所有音效均内置在程序中，不读取外部音频，也不需要联网。",
                "All sound effects are built in. They do not read external audio or require a network connection.",
            )
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #aeb6bf;")
        layout.addWidget(note)
        return page

    def preferences(self) -> AppPreferences:
        return AppPreferences(
            board_theme=str(self.board_combo.currentData()),
            custom_board_path=self.custom_board_path.text().strip(),
            stone_style=str(self.stone_combo.currentData()),
            placement_sound=str(self.placement_combo.currentData()),
            capture_sound=str(self.capture_combo.currentData()),
            volume=self.volume_slider.value(),
            muted=self._initial.muted,
            language=str(self.language_combo.currentData()),
        )

    def _load_preferences(self, preferences: AppPreferences) -> None:
        self._set_combo_data(self.board_combo, preferences.board_theme)
        self._set_combo_data(self.stone_combo, preferences.stone_style)
        self._set_combo_data(self.placement_combo, preferences.placement_sound)
        self._set_combo_data(self.capture_combo, preferences.capture_sound)
        self._set_combo_data(self.language_combo, preferences.language)
        self.custom_board_path.setText(preferences.custom_board_path)
        self.volume_slider.setValue(preferences.volume)
        self._volume_changed(preferences.volume)
        self._update_board_preview()
        self._configure_preview_audio()

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(max(0, index))

    def _current_preview_preferences(self) -> AppPreferences:
        return replace(self.preferences(), muted=False)

    def _update_board_preview(self, _index: int = -1) -> None:
        if hasattr(self, "board_preview"):
            self.board_preview.set_preferences(self._current_preview_preferences())

    def _choose_board_background(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            tr(self.language, "选择棋盘背景", "Choose board background"),
            "",
            tr(
                self.language,
                "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp);;所有文件 (*)",
                "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*)",
            ),
        )
        if selected:
            self.custom_board_path.setText(selected)
            self._update_board_preview()

    def _clear_board_background(self) -> None:
        self.custom_board_path.clear()
        self._update_board_preview()

    def _configure_preview_audio(self, _index: int = -1) -> None:
        if hasattr(self, "_preview_audio"):
            self._preview_audio.configure(self._current_preview_preferences())

    def _volume_changed(self, value: int) -> None:
        self.volume_label.setText(f"{value}%")
        self._configure_preview_audio()

    def _preview_placement(self) -> None:
        self._configure_preview_audio()
        self._preview_audio.preview_placement()

    def _preview_capture(self) -> None:
        self._configure_preview_audio()
        self._preview_audio.preview_capture()

    def _reset_defaults(self) -> None:
        self._load_preferences(AppPreferences(muted=self._initial.muted))
