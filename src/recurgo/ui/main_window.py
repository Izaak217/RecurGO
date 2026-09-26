"""Main desktop window for manual records, AI play, and live analysis."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from pyqtgraph import (
    BarGraphItem,
    InfiniteLine,
    PlotWidget,
    ScatterPlotItem,
    SignalProxy,
    TextItem,
    mkPen,
)
from PySide6.QtCore import QEvent, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from recurgo.domain import (
    BoardState,
    Color,
    GameTree,
    IllegalMove,
    MoveReview,
    Point,
    ReviewSummary,
    SideReviewSummary,
    black_winrate,
    build_move_reviews,
    explain_candidate,
    select_recommended_candidates,
    summarize_reviews,
)
from recurgo.domain.coordinates import gtp_to_point
from recurgo.domain.explanation import CandidateExplanation
from recurgo.domain.ollama_context import build_ollama_messages
from recurgo.engine import (
    PRESETS,
    AnalysisUpdate,
    EngineFailure,
    KataGoEngine,
    human_policy_probability,
    select_ai_move,
)
from recurgo.i18n import localize_error
from recurgo.llm.ollama import OllamaClient
from recurgo.llm.settings import OllamaSettings
from recurgo.storage import (
    GameRecord,
    GameRepository,
    export_sgf,
    import_sgf,
)

from .analysis_settings_dialog import AnalysisSettings, AnalysisSettingsDialog
from .audio import AudioFeedback, MoveAudio
from .board_widget import BoardWidget
from .formatting import format_result, format_rules_and_komi
from .i18n import normalize_language, tr
from .image_import_dialog import ImageImportDialog
from .library_dialog import GameLibraryDialog
from .new_game_dialog import NewGameDialog
from .ollama_dialog import OllamaSettingsDialog
from .preferences import AppPreferences
from .preferences_dialog import PreferencesDialog
from .scoring_dialog import CompletedGameDialog, ScoringDialog


def _as_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float, str)):
        try:
            return float(value)
        except ValueError:
            pass
    return default


class _HoverPlotWidget(PlotWidget):  # type: ignore[misc]
    """Plot widget that also reports when the real mouse leaves its viewport."""

    mouse_left = Signal()

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt API name
        self.mouse_left.emit()
        super().leaveEvent(event)


class MainWindow(QMainWindow):
    MODE_VALUES = {
        "手动打谱": "manual",
        "公平对战": "fair",
        "辅助对战": "assisted",
    }

    def _tr(self, chinese: str, english: str) -> str:
        return tr(self.language, chinese, english)

    def _ollama_failure_status(
        self, message: str, chinese_prefix: str, english_prefix: str
    ) -> str:
        detail = localize_error(message, self.language).strip()
        if self.language == "en" and detail.endswith(("。", "！", "？")):
            detail = detail[:-1] + {"。": ".", "！": "!", "？": "?"}[detail[-1]]
        separator = (
            ""
            if detail.endswith(("。", ".", "！", "!", "？", "?"))
            else self._tr("。", ".")
        )
        suffix = self._tr(
            "现有 KataGo 说明仍可使用。", "KataGo explanations remain available."
        )
        space = " " if self.language == "en" else ""
        return f"{self._tr(chinese_prefix, english_prefix)}{detail}{separator}{space}{suffix}"

    def _remember_text(
        self, setter: Callable[[str], None], chinese: str, english: str
    ) -> None:
        self._static_texts.append((setter, chinese, english))

    def _grade_label(self, grade: str) -> str:
        english = {
            "好手": "Good move",
            "正常": "Normal",
            "疑问手": "Dubious move",
            "坏手": "Bad move",
            "严重失误": "Blunder",
        }
        return self._tr(grade, english.get(grade, grade))

    def _difficulty_label(self, difficulty: str) -> str:
        english = {
            "入门": "Beginner",
            "初级": "Elementary",
            "中级": "Intermediate",
            "高级": "Advanced",
            "顶级": "Expert",
            "最强": "Strongest",
        }
        return self._tr(difficulty, english.get(difficulty, difficulty))

    def __init__(
        self,
        repository: GameRepository,
        record: GameRecord,
        tree: GameTree,
        engine: KataGoEngine | None = None,
        audio_feedback: MoveAudio | None = None,
        engine_unavailable_reason: str | None = None,
        ollama_client: OllamaClient | None = None,
    ) -> None:
        super().__init__()
        self.repository = repository
        self.record = record
        self.tree = tree
        self.engine = engine
        self._engine_unavailable_reason = engine_unavailable_reason
        self.ollama_settings = OllamaSettings.from_mapping(
            self.repository.load_setting("ollama")
        )
        self.ollama_client = ollama_client or OllamaClient(self)
        self._ollama_generation = 0
        self._ollama_request_id: str | None = None
        self._ollama_request_generation: int | None = None
        self._ollama_closed = False
        self._ollama_auto_attempted = False
        self._ollama_idle_status: str | None = None
        self._ollama_timer = QTimer(self)
        self._ollama_timer.setSingleShot(True)
        self._ollama_timer.setInterval(350)
        self._ollama_timer.timeout.connect(self._generate_ollama_explanation)
        self._candidate_explanation: CandidateExplanation | None = None
        self._analysis_payload_fingerprint: str | None = None
        self.preferences = AppPreferences.from_mapping(
            self.repository.load_setting("appearance_audio")
        )
        self.language = normalize_language(self.preferences.language)
        self._static_texts: list[tuple[Callable[[str], None], str, str]] = []
        self.analysis_settings = AnalysisSettings.from_mapping(
            self.repository.load_setting("analysis")
        )
        self.audio_feedback = audio_feedback or AudioFeedback(self)
        self._configure_audio_feedback()
        self._analysis_payload_by_node = self._load_analysis_payloads(record.id)
        self._ownership_by_node = self._load_cached_ownership(record.id)
        self._analysis_by_node = self._black_winrates_from_payloads()
        self._candidate_payloads: list[dict[str, object]] = []
        self._displayed_analysis_payload: dict[str, object] | None = None
        self._last_engine_failure: EngineFailure | None = None
        self._last_engine_diagnostic_path: Path | None = None
        self._last_engine_error_message: str | None = None
        self._resume_after_scoring = False
        self._review_line_ids = [node.id for node in self.tree.line_through()]
        self._startup_resume_pending = self._is_unfinished_battle_record(self.record)
        self._review_mode_active = (
            self.record.status == "completed" or self._startup_resume_pending
        )
        self._full_analysis_active = False
        self._full_analysis_queue: list[str] = []
        self._full_analysis_total = 0
        self._full_analysis_completed = 0
        self._full_analysis_visits = self.analysis_settings.visits
        self._full_analysis_current_visits = 0
        self._active_realtime_request_id: str | None = None
        self._active_full_request_id: str | None = None
        self._ignored_analysis_requests: set[str] = set()
        self.setWindowTitle(self._tr("RecurGO — 本地围棋教练", "RecurGO — Local Go Coach"))
        self.resize(1460, 900)
        self._build_toolbar()
        self._build_content()
        self.ollama_client.explanation_ready.connect(self._ollama_explanation_ready)
        self.ollama_client.explanation_partial.connect(self._ollama_explanation_partial)
        self.ollama_client.request_failed.connect(self._ollama_request_failed)
        self._connect_engine()
        self._apply_mode_controls()
        self._refresh()
        if not self._startup_resume_pending:
            QTimer.singleShot(0, self._request_analysis)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar(self._tr("对局", "Game"))
        self.game_toolbar = toolbar
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        new_action = QAction(self._tr("新棋局", "New game"), self)
        new_action.triggered.connect(self._new_game)
        toolbar.addAction(new_action)

        library_action = QAction(self._tr("棋谱库", "Game library"), self)
        library_action.triggered.connect(self._open_library)
        toolbar.addAction(library_action)

        undo_action = QAction(self._tr("悔棋", "Undo"), self)
        undo_action.triggered.connect(self._undo)
        toolbar.addAction(undo_action)

        redo_action = QAction(self._tr("前进", "Redo"), self)
        redo_action.triggered.connect(self._redo)
        toolbar.addAction(redo_action)

        pass_action = QAction(self._tr("停一手", "Pass"), self)
        pass_action.triggered.connect(self._pass)
        toolbar.addAction(pass_action)

        score_action = QAction(self._tr("结束/数子", "Finish / Score"), self)
        score_action.triggered.connect(self._open_scoring)
        toolbar.addAction(score_action)

        resign_action = QAction(self._tr("认输", "Resign"), self)
        resign_action.triggered.connect(self._resign)
        toolbar.addAction(resign_action)

        self.mute_action = QAction(self._tr("静音", "Mute"), self)
        self.mute_action.setCheckable(True)
        self.mute_action.setChecked(self.preferences.muted)
        self.mute_action.toggled.connect(self._mute_changed)
        toolbar.addAction(self.mute_action)

        preferences_action = QAction(self._tr("偏好设置", "Preferences"), self)
        preferences_action.triggered.connect(self._open_preferences)
        toolbar.addAction(preferences_action)

        analysis_settings_action = QAction(self._tr("分析设置", "Analysis settings"), self)
        analysis_settings_action.triggered.connect(self._open_analysis_settings)
        toolbar.addAction(analysis_settings_action)

        self.ollama_settings_action = QAction(
            self._tr("本机 AI 解释设置", "Local AI explanation settings"), self
        )
        self.ollama_settings_action.triggered.connect(self._open_ollama_settings)
        toolbar.addAction(self.ollama_settings_action)

        import_action = QAction(self._tr("导入 SGF", "Import SGF"), self)
        import_action.triggered.connect(self._import_sgf)
        toolbar.addAction(import_action)

        image_import_action = QAction(self._tr("图片识谱", "Recognize image"), self)
        image_import_action.triggered.connect(self._import_image_position)
        toolbar.addAction(image_import_action)

        export_action = QAction(self._tr("导出 SGF", "Export SGF"), self)
        export_action.triggered.connect(self._export_sgf)
        toolbar.addAction(export_action)

        self.full_analysis_action = QAction(self._tr("全盘AI分析", "Analyze full game"), self)
        self.full_analysis_action.triggered.connect(self._toggle_full_game_analysis)
        toolbar.addAction(self.full_analysis_action)

        overflow_button_style = (
            "QToolButton#qt_toolbar_ext_button { background: #ffffff; "
            "border: 1px solid #ffffff; border-radius: 3px; }"
            "QToolButton#qt_toolbar_ext_button:hover { background: #dbeafe; }"
            "QToolButton#qt_toolbar_ext_button:pressed { background: #bfdbfe; }"
        )
        toolbar.setStyleSheet(overflow_button_style)
        toolbar.addSeparator()

        mode_label = QLabel(self._tr(" 模式 ", " Mode "))
        toolbar.addWidget(mode_label)
        self.mode_combo = QComboBox()
        for chinese, english, value in (
            ("手动打谱", "Manual study", "manual"),
            ("公平对战", "Fair play", "fair"),
            ("辅助对战", "Assisted play", "assisted"),
        ):
            self.mode_combo.addItem(self._tr(chinese, english), value)
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(self.record.mode)))
        toolbar.addWidget(self.mode_combo)

        difficulty_label = QLabel(self._tr("  难度 ", "  Difficulty "))
        toolbar.addWidget(difficulty_label)
        self.difficulty_combo = QComboBox()
        for chinese, english in (
            ("入门", "Beginner"),
            ("初级", "Elementary"),
            ("中级", "Intermediate"),
            ("高级", "Advanced"),
            ("顶级", "Expert"),
            ("最强", "Strongest"),
        ):
            self.difficulty_combo.addItem(self._tr(chinese, english), chinese)
        difficulty = self.record.difficulty if self.record.difficulty in PRESETS else "中级"
        self.difficulty_combo.setCurrentIndex(self.difficulty_combo.findData(difficulty))
        toolbar.addWidget(self.difficulty_combo)

        color_label = QLabel(self._tr("  执色 ", "  Play as "))
        toolbar.addWidget(color_label)
        self.human_color_combo = QComboBox()
        self.human_color_combo.addItem(self._tr("我执黑", "Black"), "black")
        self.human_color_combo.addItem(self._tr("我执白", "White"), "white")
        self.human_color_combo.setCurrentIndex(
            max(0, self.human_color_combo.findData(self.record.human_color))
        )
        self.human_color_combo.currentTextChanged.connect(self._human_color_changed)
        toolbar.addWidget(self.human_color_combo)

        self.analysis_checkbox = QCheckBox(self._tr("实时分析", "Real-time analysis"))
        self.analysis_checkbox.setChecked(False)
        self.analysis_checkbox.toggled.connect(self._analysis_toggled)
        toolbar.addWidget(self.analysis_checkbox)

        self.ownership_checkbox = QCheckBox(self._tr("领地", "Ownership"))
        self.ownership_checkbox.setChecked(False)
        self.ownership_checkbox.toggled.connect(self._analysis_option_changed)
        toolbar.addWidget(self.ownership_checkbox)
        self.difficulty_combo.currentTextChanged.connect(self._difficulty_changed)
        self.mode_combo.currentTextChanged.connect(self._mode_changed)
        for widget, chinese, english in (
            (new_action, "新棋局", "New game"),
            (library_action, "棋谱库", "Game library"),
            (undo_action, "悔棋", "Undo"),
            (redo_action, "前进", "Redo"),
            (pass_action, "停一手", "Pass"),
            (score_action, "结束/数子", "Finish / Score"),
            (resign_action, "认输", "Resign"),
            (self.mute_action, "静音", "Mute"),
            (preferences_action, "偏好设置", "Preferences"),
            (analysis_settings_action, "分析设置", "Analysis settings"),
            (self.ollama_settings_action, "本机 AI 解释设置", "Local AI explanation settings"),
            (import_action, "导入 SGF", "Import SGF"),
            (image_import_action, "图片识谱", "Recognize image"),
            (export_action, "导出 SGF", "Export SGF"),
            (mode_label, " 模式 ", " Mode "),
            (difficulty_label, "  难度 ", "  Difficulty "),
            (color_label, "  执色 ", "  Play as "),
            (self.analysis_checkbox, "实时分析", "Real-time analysis"),
            (self.ownership_checkbox, "领地", "Ownership"),
        ):
            self._remember_text(widget.setText, chinese, english)

        self._build_toolbar_menu(
            new_action=new_action,
            library_action=library_action,
            undo_action=undo_action,
            redo_action=redo_action,
            pass_action=pass_action,
            score_action=score_action,
            resign_action=resign_action,
            preferences_action=preferences_action,
            analysis_settings_action=analysis_settings_action,
            import_action=import_action,
            image_import_action=image_import_action,
            export_action=export_action,
        )

    def _build_toolbar_menu(
        self,
        *,
        new_action: QAction,
        library_action: QAction,
        undo_action: QAction,
        redo_action: QAction,
        pass_action: QAction,
        score_action: QAction,
        resign_action: QAction,
        preferences_action: QAction,
        analysis_settings_action: QAction,
        import_action: QAction,
        image_import_action: QAction,
        export_action: QAction,
    ) -> None:
        menu_bar = self.menuBar()
        root_menu = menu_bar.addMenu(self._tr("菜单", "Menu"))
        self._remember_text(root_menu.setTitle, "菜单", "Menu")

        def section(chinese: str, english: str) -> QMenu:
            menu = root_menu.addMenu(self._tr(chinese, english))
            self._remember_text(menu.setTitle, chinese, english)
            return menu

        game_menu = section("棋局", "Game")
        for action in (new_action, library_action):
            game_menu.addAction(action)
        game_menu.addSeparator()
        for action in (undo_action, redo_action, pass_action, score_action, resign_action):
            game_menu.addAction(action)
        game_menu.addSeparator()
        for action in (import_action, image_import_action, export_action):
            game_menu.addAction(action)

        self._toolbar_combo_menus: list[tuple[QMenu, QComboBox, list[QAction]]] = []
        self._toolbar_menu_groups: list[QActionGroup] = []
        play_menu = section("对战", "Play")
        for chinese, english, combo in (
            ("模式", "Mode", self.mode_combo),
            ("难度", "Difficulty", self.difficulty_combo),
            ("执色", "Play as", self.human_color_combo),
        ):
            self._add_combo_menu(play_menu, chinese, english, combo)

        analysis_menu = section("分析", "Analysis")
        self.analysis_menu_action = QAction(self._tr("实时分析", "Real-time analysis"), self)
        self.analysis_menu_action.setCheckable(True)
        self.analysis_menu_action.triggered.connect(
            lambda checked: self._set_checkbox_from_menu(
                self.analysis_checkbox, self.analysis_menu_action, checked
            )
        )
        analysis_menu.addAction(self.analysis_menu_action)
        self._remember_text(self.analysis_menu_action.setText, "实时分析", "Real-time analysis")

        self.ownership_menu_action = QAction(self._tr("领地", "Ownership"), self)
        self.ownership_menu_action.setCheckable(True)
        self.ownership_menu_action.triggered.connect(
            lambda checked: self._set_checkbox_from_menu(
                self.ownership_checkbox, self.ownership_menu_action, checked
            )
        )
        analysis_menu.addAction(self.ownership_menu_action)
        self._remember_text(self.ownership_menu_action.setText, "领地", "Ownership")
        analysis_menu.addAction(self.full_analysis_action)
        analysis_menu.addSeparator()
        analysis_menu.addAction(analysis_settings_action)
        analysis_menu.addAction(self.ollama_settings_action)

        settings_menu = section("设置", "Settings")
        settings_menu.addAction(preferences_action)
        settings_menu.addAction(self.mute_action)
        root_menu.aboutToShow.connect(self._sync_toolbar_menu)
        self._sync_toolbar_menu()

    def _add_combo_menu(
        self, parent: QMenu, chinese: str, english: str, combo: QComboBox
    ) -> None:
        menu = parent.addMenu(self._tr(chinese, english))
        self._remember_text(menu.setTitle, chinese, english)
        group = QActionGroup(menu)
        group.setExclusive(True)
        self._toolbar_menu_groups.append(group)
        actions: list[QAction] = []
        for index in range(combo.count()):
            action = QAction(combo.itemText(index), menu)
            action.setCheckable(True)
            group.addAction(action)
            menu.addAction(action)
            value = combo.itemData(index)
            action.triggered.connect(
                lambda _checked, selected=value, target=combo: self._select_toolbar_combo(
                    target, selected
                )
            )
            actions.append(action)
        self._toolbar_combo_menus.append((menu, combo, actions))

    @staticmethod
    def _select_toolbar_combo(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if combo.isEnabled() and index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _set_checkbox_from_menu(checkbox: QCheckBox, action: QAction, checked: bool) -> None:
        if checkbox.isEnabled():
            checkbox.setChecked(checked)
        action.setChecked(checkbox.isChecked())

    def _sync_toolbar_menu(self) -> None:
        for menu, combo, actions in self._toolbar_combo_menus:
            menu.setEnabled(combo.isEnabled())
            for index, action in enumerate(actions):
                action.setText(combo.itemText(index))
                action.setChecked(index == combo.currentIndex())
        for action, checkbox in (
            (self.analysis_menu_action, self.analysis_checkbox),
            (self.ownership_menu_action, self.ownership_checkbox),
        ):
            action.setEnabled(checkbox.isEnabled())
            action.setChecked(checkbox.isChecked())

    def _build_content(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_title = QLabel(self._tr("思路说明", "Move explanation"))
        left_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        left_layout.addWidget(left_title)
        self.explanation = QTextEdit()
        self.explanation.setReadOnly(True)
        self.explanation.setPlaceholderText(
            self._tr(
                "接入实时分析后，点击候选手将在这里显示棋理判断和主要变化。",
                "When real-time analysis is available, select a candidate to see its reasoning and reference variation.",
            )
        )
        left_layout.addWidget(self.explanation, 1)
        ollama_title = QLabel(self._tr("本机 AI 棋理解释", "Local AI explanation"))
        ollama_title.setStyleSheet("font-size: 14px; font-weight: 600;")
        left_layout.addWidget(ollama_title)
        ollama_notice = QLabel(
            self._tr(
                "AI 文字解释可能出错，落点和数值以 KataGo 为准。",
                "AI text can be wrong. Use KataGo for moves and figures.",
            )
        )
        ollama_notice.setWordWrap(True)
        left_layout.addWidget(ollama_notice)
        self.ollama_explanation = QTextEdit()
        self.ollama_explanation.setReadOnly(True)
        self.ollama_explanation.setPlaceholderText(
            self._tr(
                "启用本机 Ollama 后，将在分析完成时自动补充；上方规则说明即时显示。",
                "With local Ollama enabled, a text explanation appears after analysis. The rules explanation above updates immediately.",
            )
        )
        left_layout.addWidget(self.ollama_explanation, 1)
        ollama_buttons = QHBoxLayout()
        self.ollama_generate_button = QPushButton(self._tr("重新生成", "Generate again"))
        self.ollama_generate_button.clicked.connect(self._generate_ollama_explanation)
        ollama_buttons.addWidget(self.ollama_generate_button)
        self.ollama_cancel_button = QPushButton(self._tr("取消生成", "Cancel generation"))
        self.ollama_cancel_button.clicked.connect(self._cancel_ollama_explanation)
        ollama_buttons.addWidget(self.ollama_cancel_button)
        left_layout.addLayout(ollama_buttons)
        self.ollama_status = QLabel()
        self.ollama_status.setTextFormat(Qt.TextFormat.PlainText)
        self.ollama_status.setWordWrap(True)
        left_layout.addWidget(self.ollama_status)
        self.game_info = QLabel()
        self.game_info.setWordWrap(True)
        self.game_info.setStyleSheet("padding: 12px; background: #30363d; border-radius: 6px;")
        left_layout.addWidget(self.game_info)

        center_panel = QFrame()
        center_layout = QVBoxLayout(center_panel)
        self.board_widget = BoardWidget()
        self.board_widget.set_preferences(self.preferences)
        self.board_widget.point_clicked.connect(self._play_point)
        center_layout.addWidget(self.board_widget, 1)
        navigation = QHBoxLayout()
        self.first_move_button = QPushButton(self._tr("首手", "First"))
        self.previous_move_button = QPushButton(self._tr("上一手", "Previous"))
        self.next_move_button = QPushButton(self._tr("下一手", "Next"))
        self.last_move_button = QPushButton(self._tr("末手", "Last"))
        self.first_move_button.clicked.connect(lambda: self._navigate_review(0))
        self.previous_move_button.clicked.connect(self._navigate_previous)
        self.next_move_button.clicked.connect(self._navigate_next)
        self.last_move_button.clicked.connect(self._navigate_last)
        navigation.addWidget(self.first_move_button)
        navigation.addWidget(self.previous_move_button)
        self.move_slider = QSlider(Qt.Orientation.Horizontal)
        self.move_slider.setTracking(False)
        self.move_slider.valueChanged.connect(self._navigate_review)
        navigation.addWidget(self.move_slider, 1)
        self.move_spin = QSpinBox()
        self.move_spin.setPrefix(self._tr("第 ", "Move "))
        self.move_spin.setSuffix(self._tr(" 手", ""))
        self.move_spin.valueChanged.connect(self._navigate_review)
        navigation.addWidget(self.move_spin)
        navigation.addWidget(self.next_move_button)
        navigation.addWidget(self.last_move_button)
        center_layout.addLayout(navigation)
        self.navigation_label = QLabel()
        self.navigation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self.navigation_label)

        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        title = QLabel(self._tr("当前局面分析", "Current position analysis"))
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        right_layout.addWidget(title)
        if self.engine is None and self._engine_unavailable_reason:
            engine_text = self._tr(
                f"KataGo：运行配置不可用：{self._engine_unavailable_reason}",
                f"KataGo: runtime configuration unavailable: {localize_error(self._engine_unavailable_reason, self.language)}",
            )
        elif self.engine is None:
            engine_text = self._tr(
                "KataGo：运行配置不可用", "KataGo: runtime configuration unavailable"
            )
        else:
            engine_text = self._tr("KataGo：尚未启动", "KataGo: not started")
        self.engine_status = QLabel(engine_text)
        self.engine_status.setWordWrap(True)
        self.engine_status.setStyleSheet("padding: 8px; color: #d9b44a; background: #30363d;")
        right_layout.addWidget(self.engine_status)
        engine_actions = QHBoxLayout()
        self.engine_retry_button = QPushButton(self._tr("重试分析", "Retry analysis"))
        self.engine_retry_button.clicked.connect(self._retry_engine_analysis)
        self.engine_retry_button.hide()
        engine_actions.addWidget(self.engine_retry_button)
        self.engine_close_analysis_button = QPushButton(self._tr("关闭分析", "Close analysis"))
        self.engine_close_analysis_button.clicked.connect(self._close_failed_analysis)
        self.engine_close_analysis_button.hide()
        engine_actions.addWidget(self.engine_close_analysis_button)
        engine_actions.addStretch(1)
        right_layout.addLayout(engine_actions)
        self.full_analysis_progress = QProgressBar()
        self.full_analysis_progress.setTextVisible(True)
        self.full_analysis_progress.hide()
        right_layout.addWidget(self.full_analysis_progress)

        self.candidate_table = QTableWidget(0, 5)
        self.candidate_table.setHorizontalHeaderLabels(
            [
                self._tr("候选点", "Candidate"),
                self._tr("人类偏好", "Human preference"),
                self._tr("胜率", "Win rate"),
                self._tr("目差", "Score lead"),
                self._tr("计算量", "Visits"),
            ]
        )
        self.candidate_table.horizontalHeader().setStretchLastSection(True)
        self.candidate_table.cellClicked.connect(self._candidate_selected)
        right_layout.addWidget(self.candidate_table, 2)

        review_header = QHBoxLayout()
        review_title = QLabel(self._tr("全盘复盘", "Full-game review"))
        review_header.addWidget(review_title)
        review_header.addStretch(1)
        review_scope_label = QLabel(self._tr("范围", "Scope"))
        review_header.addWidget(review_scope_label)
        self.review_scope_combo = QComboBox()
        for chinese, english, value in (
            ("全盘", "Whole game", "all"),
            ("布局（1-60手）", "Opening (moves 1–60)", "opening"),
            ("中盘（61-160手）", "Middle game (moves 61–160)", "middle"),
            ("官子（161手后）", "Endgame (move 161 onward)", "endgame"),
        ):
            self.review_scope_combo.addItem(self._tr(chinese, english), value)
        self.review_scope_combo.currentTextChanged.connect(self._update_review_summary)
        review_header.addWidget(self.review_scope_combo)
        right_layout.addLayout(review_header)

        self.review_tabs = QTabWidget()

        winrate_page = QWidget()
        winrate_layout = QVBoxLayout(winrate_page)
        zoom_controls = QHBoxLayout()
        horizontal_label = QLabel(self._tr("横向", "Horizontal"))
        zoom_controls.addWidget(horizontal_label)
        self.winrate_horizontal_zoom = QComboBox()
        self.winrate_horizontal_zoom.addItems(["1×", "2×", "4×", "8×"])
        self.winrate_horizontal_zoom.currentTextChanged.connect(self._winrate_zoom_changed)
        zoom_controls.addWidget(self.winrate_horizontal_zoom)
        vertical_label = QLabel(self._tr("纵向", "Vertical"))
        zoom_controls.addWidget(vertical_label)
        self.winrate_vertical_zoom = QComboBox()
        self.winrate_vertical_zoom.addItems(["1×", "2×", "4×"])
        self.winrate_vertical_zoom.currentTextChanged.connect(self._winrate_zoom_changed)
        zoom_controls.addWidget(self.winrate_vertical_zoom)
        reset_zoom = QPushButton(self._tr("还原", "Reset"))
        reset_zoom.clicked.connect(self._reset_winrate_zoom)
        zoom_controls.addWidget(reset_zoom)
        zoom_controls.addStretch(1)
        winrate_layout.addLayout(zoom_controls)
        self.winrate_plot = PlotWidget()
        self.winrate_plot.setBackground("#252a30")
        self.winrate_plot.setYRange(0, 100)
        self.winrate_plot.setLabel("left", self._tr("黑胜率", "Black win rate"), units="%")
        self.winrate_plot.setLabel("bottom", self._tr("手数", "Move"))
        self.winrate_plot.showGrid(x=True, y=True, alpha=0.2)
        self.winrate_plot.setMinimumHeight(170)
        self.winrate_plot.setMaximumHeight(210)
        self.winrate_curve = self.winrate_plot.plot(
            [],
            [],
            pen="#43a8ff",
            symbol="o",
            symbolSize=6,
        )
        self.winrate_cursor = InfiniteLine(
            angle=90,
            movable=False,
            pen="#d9b44a",
        )
        self.winrate_cursor.hide()
        self.winrate_plot.addItem(self.winrate_cursor)
        self.winrate_tooltip = TextItem(
            color="#ffffff",
            fill=(35, 39, 46, 235),
            border="#43a8ff",
            anchor=(0.5, 1.25),
        )
        self.winrate_tooltip.hide()
        self.winrate_plot.addItem(self.winrate_tooltip)
        self._winrate_mouse_proxy = SignalProxy(
            self.winrate_plot.scene().sigMouseMoved,
            rateLimit=45,
            slot=self._winrate_mouse_moved,
        )
        winrate_layout.addWidget(self.winrate_plot, 1)
        self.review_tabs.addTab(winrate_page, self._tr("胜率走势", "Win-rate trend"))

        quality_page = QWidget()
        quality_layout = QVBoxLayout(quality_page)
        self.quality_details = QLabel(self._tr("● 黑方　○ 白方", "● Black   ○ White"))
        self.quality_details.setWordWrap(True)
        quality_layout.addWidget(self.quality_details)
        self.quality_plot = PlotWidget()
        self.quality_plot.setBackground("#252a30")
        self.quality_plot.setLabel("left", self._tr("手数", "Moves"))
        self.quality_plot.getAxis("bottom").setTicks(
            [
                [
                    (0, self._grade_label("好手")),
                    (1, self._grade_label("正常")),
                    (2, self._grade_label("疑问手")),
                    (3, self._grade_label("坏手")),
                    (4, self._grade_label("严重失误")),
                ]
            ]
        )
        self.quality_plot.showGrid(y=True, alpha=0.2)
        self.quality_plot.setMouseEnabled(x=False, y=False)
        quality_layout.addWidget(self.quality_plot, 1)
        self.review_tabs.addTab(quality_page, self._tr("着法质量", "Move quality"))

        problems_page = QWidget()
        problems_layout = QVBoxLayout(problems_page)
        self.problem_details = QLabel(
            self._tr(
                "点击图中的问题手可跳转到对应局面。",
                "Click a problem move in the chart to jump to its position.",
            )
        )
        self.problem_details.setWordWrap(True)
        problems_layout.addWidget(self.problem_details)
        self.problem_plot = _HoverPlotWidget()
        self.problem_plot.setBackground("#252a30")
        self.problem_plot.setLabel("bottom", self._tr("手数", "Move"))
        self.problem_plot.getAxis("left").setTicks(
            [
                [
                    (-3, self._tr("白严重", "White blunder")),
                    (-2, self._tr("白坏手", "White bad")),
                    (-1, self._tr("白疑问", "White dubious")),
                    (1, self._tr("黑疑问", "Black dubious")),
                    (2, self._tr("黑坏手", "Black bad")),
                    (3, self._tr("黑严重", "Black blunder")),
                ]
            ]
        )
        self.problem_plot.setYRange(-3.5, 3.5, padding=0.03)
        self.problem_plot.showGrid(x=True, y=True, alpha=0.15)
        self.problem_plot.setMouseEnabled(x=True, y=False)
        self.problem_plot.setMenuEnabled(False)
        self.problem_plot.hideButtons()
        self.problem_scatter = ScatterPlotItem(size=13, pxMode=True)
        self.problem_scatter.setZValue(3)
        self.problem_scatter.sigClicked.connect(self._review_scatter_clicked)
        self.problem_plot.addItem(self.problem_scatter)
        self._problem_review_positions: list[tuple[MoveReview, float]] = []
        self.problem_cursor = InfiniteLine(
            angle=90,
            movable=False,
            pen="#d9b44a",
        )
        self.problem_cursor.setZValue(10)
        self.problem_cursor.hide()
        self.problem_plot.addItem(self.problem_cursor)
        self.problem_tooltip = TextItem(
            color="#ffffff",
            fill=(35, 39, 46, 235),
            border="#d9b44a",
            anchor=(0.5, 0.0),
        )
        self.problem_tooltip.setZValue(11)
        self.problem_tooltip.hide()
        self.problem_plot.addItem(self.problem_tooltip)
        self._problem_mouse_proxy = SignalProxy(
            self.problem_plot.scene().sigMouseMoved,
            rateLimit=45,
            slot=self._problem_mouse_moved,
        )
        self.problem_plot.mouse_left.connect(self._hide_problem_hover)
        problems_layout.addWidget(self.problem_plot, 1)
        self.review_tabs.addTab(problems_page, self._tr("问题手", "Problem moves"))

        match_page = QWidget()
        match_layout = QVBoxLayout(match_page)
        self.match_details = QLabel(
            self._tr(
                "红色=黑方逐手记录　蓝色=白方逐手记录　绿色=连续好手；"
                "鼠标悬停可查看手数与该手分类。",
                "Red = Black moves; blue = White moves; green = good-move streaks. Hover for move number and grade.",
            )
        )
        self.match_details.setWordWrap(True)
        self.match_details.setStyleSheet("color: #c7d0d9; padding: 2px 4px;")
        match_layout.addWidget(self.match_details)
        match_content = QHBoxLayout()
        match_content.setSpacing(0)
        match_content.setContentsMargins(0, 0, 0, 0)
        self.match_plot = _HoverPlotWidget()
        self.match_plot.setBackground("#343a43")
        self.match_plot.setLabel("bottom", self._tr("手数", "Move"))
        self.match_plot.getAxis("left").setTicks(
            [[(0.40, self._tr("白方", "White")), (1.60, self._tr("黑方", "Black"))]]
        )
        self.match_plot.setYRange(-0.12, 2.12, padding=0.01)
        self.match_plot.showGrid(x=True, y=False, alpha=0.12)
        self.match_plot.setMouseEnabled(x=True, y=False)
        self.match_plot.setMenuEnabled(False)
        self.match_plot.hideButtons()
        self.match_plot.setMinimumHeight(240)
        self._match_graphics: list[object] = []
        self.match_scatter = ScatterPlotItem(size=12, symbol="s", pxMode=True)
        self.match_scatter.setZValue(3)
        self.match_scatter.sigClicked.connect(self._review_scatter_clicked)
        self.match_plot.addItem(self.match_scatter)
        self._match_reviews_by_color: dict[Color, list[MoveReview]] = {
            Color.BLACK: [],
            Color.WHITE: [],
        }
        self.match_cursor = InfiniteLine(
            angle=90,
            movable=False,
            pen="#d9b44a",
        )
        self.match_cursor.setZValue(10)
        self.match_cursor.hide()
        self.match_plot.addItem(self.match_cursor)
        self.match_tooltip = TextItem(
            color="#ffffff",
            fill=(35, 39, 46, 235),
            border="#d9b44a",
            anchor=(0.5, 0.0),
        )
        self.match_tooltip.setZValue(11)
        self.match_tooltip.hide()
        self.match_plot.addItem(self.match_tooltip)
        self._match_mouse_proxy = SignalProxy(
            self.match_plot.scene().sigMouseMoved,
            rateLimit=45,
            slot=self._match_mouse_moved,
        )
        self.match_plot.mouse_left.connect(self._hide_match_hover)
        match_content.addWidget(self.match_plot, 1)

        match_summary_frame = QFrame()
        match_summary_frame.setMinimumWidth(146)
        match_summary_frame.setMaximumWidth(180)
        match_summary_frame.setMinimumHeight(240)
        match_summary_frame.setStyleSheet(
            "QFrame { background: #343a43; border-left: 1px solid #4b535d; }"
        )
        match_summary_layout = QVBoxLayout(match_summary_frame)
        match_summary_layout.setContentsMargins(10, 18, 10, 30)
        match_summary_layout.setSpacing(0)
        self.match_black_summary = QLabel(
            self._tr("等待黑方分析", "Waiting for Black analysis")
        )
        self.match_black_summary.setWordWrap(True)
        self.match_black_summary.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self.match_black_summary.setStyleSheet(
            "border: none; border-bottom: 1px solid #4b535d; color: #e7edf3;"
        )
        self.match_white_summary = QLabel(
            self._tr("等待白方分析", "Waiting for White analysis")
        )
        self.match_white_summary.setWordWrap(True)
        self.match_white_summary.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self.match_white_summary.setStyleSheet("border: none; color: #e7edf3;")
        match_summary_layout.addWidget(self.match_black_summary, 1)
        match_summary_layout.addWidget(self.match_white_summary, 1)
        match_content.addWidget(match_summary_frame)
        match_layout.addLayout(match_content, 1)
        self.review_tabs.addTab(match_page, self._tr("吻合度", "Match rate"))

        overview_page = QWidget()
        overview_layout = QVBoxLayout(overview_page)
        self.review_summary = QLabel(
            self._tr("尚未进行全盘AI分析", "Full-game analysis has not run")
        )
        self.review_summary.setWordWrap(True)
        self.review_summary.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.review_summary.setStyleSheet(
            "padding: 10px; background: #30363d; border-radius: 6px;"
        )
        overview_layout.addWidget(self.review_summary, 1)
        self.review_tabs.addTab(overview_page, self._tr("概览", "Overview"))

        right_layout.addWidget(self.review_tabs, 2)

        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([320, 720, 520])
        self.setCentralWidget(splitter)
        for widget, chinese, english in (
            (left_title, "思路说明", "Move explanation"),
            (ollama_title, "本机 AI 棋理解释", "Local AI explanation"),
            (
                ollama_notice,
                "AI 文字解释可能出错，落点和数值以 KataGo 为准。",
                "AI text can be wrong. Use KataGo for moves and figures.",
            ),
            (self.ollama_generate_button, "重新生成", "Generate again"),
            (self.ollama_cancel_button, "取消生成", "Cancel generation"),
            (self.first_move_button, "首手", "First"),
            (self.previous_move_button, "上一手", "Previous"),
            (self.next_move_button, "下一手", "Next"),
            (self.last_move_button, "末手", "Last"),
            (title, "当前局面分析", "Current position analysis"),
            (self.engine_retry_button, "重试分析", "Retry analysis"),
            (self.engine_close_analysis_button, "关闭分析", "Close analysis"),
            (review_title, "全盘复盘", "Full-game review"),
            (review_scope_label, "范围", "Scope"),
            (horizontal_label, "横向", "Horizontal"),
            (vertical_label, "纵向", "Vertical"),
            (reset_zoom, "还原", "Reset"),
        ):
            self._remember_text(widget.setText, chinese, english)
        self.statusBar().showMessage(
            self._tr("棋谱已启用逐手自动保存", "Moves are saved automatically")
        )

    def _play_point(self, x: int, y: int) -> None:
        if self._full_analysis_active:
            self.statusBar().showMessage(
                self._tr(
                    "全盘分析期间不能修改棋谱",
                    "The game cannot be changed during full-game analysis",
                ),
                3000,
            )
            return
        if self._is_ai_turn():
            self.statusBar().showMessage(
                self._tr(
                    "现在轮到本地 AI 行棋，请稍候", "The local AI is playing; please wait"
                ),
                3000,
            )
            return
        before = self.tree.current.state
        try:
            node, _created = self.tree.play(Point(x, y))
        except IllegalMove as exc:
            self.statusBar().showMessage(
                self._tr(f"不能落子：{exc}", f"Illegal move: {exc}"), 3500
            )
            return
        self.repository.save_node(self.record.id, node)
        self._set_review_line_from_current()
        self._resume_after_scoring = False
        captured = (
            node.state.black_captures + node.state.white_captures
            > before.black_captures + before.white_captures
        )
        self.audio_feedback.play_move(captured=captured)
        self._refresh()
        self._request_analysis()

    def _pass(self) -> None:
        if self._full_analysis_active:
            self.statusBar().showMessage(
                self._tr(
                    "全盘分析期间不能修改棋谱",
                    "The game cannot be changed during full-game analysis",
                ),
                3000,
            )
            return
        if self._is_ai_turn():
            self.statusBar().showMessage(
                self._tr(
                    "现在轮到本地 AI 行棋，请稍候", "The local AI is playing; please wait"
                ),
                3000,
            )
            return
        node, _created = self.tree.play(None)
        self.repository.save_node(self.record.id, node)
        self._set_review_line_from_current()
        self._resume_after_scoring = False
        self._refresh()
        if node.state.is_game_over:
            QTimer.singleShot(0, self._open_scoring)
        else:
            self._request_analysis()

    def _undo(self) -> None:
        if self._review_mode_active:
            self._navigate_previous()
            return
        if self.engine is not None and not self._full_analysis_active:
            self.engine.stop_analysis()
        node = self.tree.undo()
        if self._is_battle_mode():
            while node.parent_id is not None and node.state.to_play is self._ai_color():
                node = self.tree.undo()
        self.repository.set_current(self.record.id, node.id)
        self._refresh()
        self._request_analysis()

    def _redo(self) -> None:
        if self._review_mode_active:
            self._navigate_next()
            return
        if self.engine is not None and not self._full_analysis_active:
            self.engine.stop_analysis()
        node = self.tree.redo()
        if self._is_battle_mode():
            while node.children and node.state.to_play is self._ai_color():
                node = self.tree.redo()
        self.repository.set_current(self.record.id, node.id)
        self._refresh()
        self._request_analysis()

    def _new_game(self) -> None:
        dialog = NewGameDialog(
            initial_mode=self.record.mode,
            initial_human_color=self.record.human_color,
            initial_difficulty=self.record.difficulty,
            language=self.language,
            parent=self,
        )
        if dialog.exec() != NewGameDialog.DialogCode.Accepted:
            return
        options = dialog.options()
        if self.engine is not None:
            self.engine.stop_analysis()
        self._stop_full_game_analysis(request_realtime=False)
        tree = GameTree()
        record = self.repository.create_game(
            tree,
            name=options.name,
            black_player=options.black_player,
            white_player=options.white_player,
            mode=options.mode,
            human_color=options.human_color,
            difficulty=options.difficulty,
        )
        self._apply_loaded_game(record, tree, review_mode=False)
        self._request_analysis()
        self.statusBar().showMessage(
            self._tr(
                "已创建新棋局；旧棋谱仍保留在棋谱库中",
                "New game created; the previous game remains in the library",
            ),
            5000,
        )

    def _open_preferences(self) -> None:
        dialog = PreferencesDialog(self.preferences, self)
        if dialog.exec() != PreferencesDialog.DialogCode.Accepted:
            return
        self.preferences = dialog.preferences()
        self.repository.save_setting("appearance_audio", self.preferences.to_mapping())
        self.board_widget.set_preferences(self.preferences)
        self._configure_audio_feedback()
        new_language = normalize_language(self.preferences.language)
        if new_language != self.language:
            self._invalidate_ollama_explanation()
            self.language = new_language
            self._retranslate_ui()
        self.statusBar().showMessage(self._tr("偏好设置已保存", "Preferences saved"), 4000)

    @staticmethod
    def _set_combo_texts(combo: QComboBox, labels: tuple[str, ...]) -> None:
        previous = combo.blockSignals(True)
        try:
            for index, label in enumerate(labels):
                combo.setItemText(index, label)
        finally:
            combo.blockSignals(previous)

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(self._tr("RecurGO — 本地围棋教练", "RecurGO — Local Go Coach"))
        self.game_toolbar.setWindowTitle(self._tr("对局", "Game"))
        for setter, chinese, english in self._static_texts:
            setter(self._tr(chinese, english))
        self.full_analysis_action.setText(
            self._tr("停止全盘分析", "Stop full-game analysis")
            if self._full_analysis_active
            else self._tr("全盘AI分析", "Analyze full game")
        )
        self._set_combo_texts(
            self.mode_combo,
            tuple(
                self._tr(chinese, english)
                for chinese, english in (
                    ("手动打谱", "Manual study"),
                    ("公平对战", "Fair play"),
                    ("辅助对战", "Assisted play"),
                )
            ),
        )
        self._set_combo_texts(
            self.difficulty_combo,
            tuple(
                self._tr(chinese, english)
                for chinese, english in (
                    ("入门", "Beginner"),
                    ("初级", "Elementary"),
                    ("中级", "Intermediate"),
                    ("高级", "Advanced"),
                    ("顶级", "Expert"),
                    ("最强", "Strongest"),
                )
            ),
        )
        self._set_combo_texts(
            self.human_color_combo,
            (self._tr("我执黑", "Black"), self._tr("我执白", "White")),
        )
        self._set_combo_texts(
            self.review_scope_combo,
            tuple(
                self._tr(chinese, english)
                for chinese, english in (
                    ("全盘", "Whole game"),
                    ("布局（1-60手）", "Opening (moves 1–60)"),
                    ("中盘（61-160手）", "Middle game (moves 61–160)"),
                    ("官子（161手后）", "Endgame (move 161 onward)"),
                )
            ),
        )
        self._sync_toolbar_menu()
        self.explanation.setPlaceholderText(
            self._tr(
                "接入实时分析后，点击候选手将在这里显示棋理判断和主要变化。",
                "When real-time analysis is available, select a candidate to see its "
                "reasoning and reference variation.",
            )
        )
        self.ollama_explanation.setPlaceholderText(
            self._tr(
                "启用本机 Ollama 后，将在分析完成时自动补充；上方规则说明即时显示。",
                "With local Ollama enabled, a text explanation appears after analysis. "
                "The rules explanation above updates immediately.",
            )
        )
        self.move_spin.setPrefix(self._tr("第 ", "Move "))
        self.move_spin.setSuffix(self._tr(" 手", ""))
        self.candidate_table.setHorizontalHeaderLabels(
            [
                self._tr("候选点", "Candidate"),
                self._tr("人类偏好", "Human preference"),
                self._tr("胜率", "Win rate"),
                self._tr("目差", "Score lead"),
                self._tr("计算量", "Visits"),
            ]
        )
        for index, (chinese, english) in enumerate(
            (
                ("胜率走势", "Win-rate trend"),
                ("着法质量", "Move quality"),
                ("问题手", "Problem moves"),
                ("吻合度", "Match rate"),
                ("概览", "Overview"),
            )
        ):
            self.review_tabs.setTabText(index, self._tr(chinese, english))
        self.winrate_plot.setLabel("left", self._tr("黑胜率", "Black win rate"), units="%")
        self.winrate_plot.setLabel("bottom", self._tr("手数", "Move"))
        self.quality_plot.setLabel("left", self._tr("手数", "Moves"))
        quality_ticks = [
            (index, self._grade_label(grade))
            for index, grade in enumerate(("好手", "正常", "疑问手", "坏手", "严重失误"))
        ]
        self.quality_plot.getAxis("bottom").setTicks([quality_ticks])
        self.problem_plot.setLabel("bottom", self._tr("手数", "Move"))
        problem_ticks = [
            (-3, self._tr("白严重", "White blunder")),
            (-2, self._tr("白坏手", "White bad")),
            (-1, self._tr("白疑问", "White dubious")),
            (1, self._tr("黑疑问", "Black dubious")),
            (2, self._tr("黑坏手", "Black bad")),
            (3, self._tr("黑严重", "Black blunder")),
        ]
        self.problem_plot.getAxis("left").setTicks([problem_ticks])
        self.match_plot.setLabel("bottom", self._tr("手数", "Move"))
        self.match_plot.getAxis("left").setTicks(
            [[(0.40, self._tr("白方", "White")), (1.60, self._tr("黑方", "Black"))]]
        )
        self.winrate_tooltip.hide()
        self._hide_problem_hover()
        self._hide_match_hover()
        problem_x_range = tuple(self.problem_plot.viewRange()[0])
        match_x_range = tuple(self.match_plot.viewRange()[0])
        self._render_game_info()
        self._sync_navigation_controls()
        self._update_review_summary()
        self.problem_plot.setXRange(*problem_x_range, padding=0)
        self.match_plot.setXRange(*match_x_range, padding=0)
        self._update_ollama_controls()
        if self._candidate_explanation is not None:
            move = self._candidate_explanation.move
            for row, info in enumerate(self._candidate_payloads):
                if str(info.get("move", "pass")) == move:
                    self._show_candidate_explanation(row)
                    break
        elif self._displayed_analysis_payload is None:
            self._show_manual_candidate_placeholder()
        self._retranslate_engine_status()
        if not self.full_analysis_progress.isHidden():
            if self._last_engine_failure is not None:
                self.full_analysis_progress.setFormat(
                    self._tr(
                        "分析已暂停 · 可重试或关闭分析",
                        "Analysis paused · retry or close analysis",
                    )
                )
            elif self._full_analysis_active:
                self._update_full_analysis_progress(self._full_analysis_current_visits)
            else:
                self.full_analysis_progress.setFormat(
                    self._tr(
                        f"%p% · 已完成 {self._full_analysis_completed}/"
                        f"{self._full_analysis_total} 个局面",
                        f"%p% · Completed {self._full_analysis_completed}/"
                        f"{self._full_analysis_total} positions",
                    )
                )

    def _retranslate_engine_status(self) -> None:
        if self._last_engine_failure is not None:
            message = self._last_engine_failure.message
            diagnostic = (
                self._tr(
                    f" · 诊断已保存至 {self._last_engine_diagnostic_path}",
                    f" · diagnostic saved to {self._last_engine_diagnostic_path}",
                )
                if self._last_engine_diagnostic_path is not None
                else ""
            )
            self.engine_status.setText(
                self._tr(
                    f"KataGo错误：{message}",
                    f"KataGo error: {localize_error(message, self.language)}",
                ) + diagnostic
            )
            return
        if self._last_engine_error_message is not None:
            message = self._last_engine_error_message
            self.engine_status.setText(
                self._tr(
                    f"KataGo错误：{message}",
                    f"KataGo error: {localize_error(message, self.language)}",
                )
            )
            return
        if self.engine is None:
            if self._engine_unavailable_reason:
                self.engine_status.setText(
                    self._tr(
                        f"KataGo：运行配置不可用：{self._engine_unavailable_reason}",
                        "KataGo: runtime configuration unavailable: "
                        + localize_error(self._engine_unavailable_reason, self.language),
                    )
                )
            else:
                self.engine_status.setText(
                    self._tr(
                        "KataGo：运行配置不可用",
                        "KataGo: runtime configuration unavailable",
                    )
                )
            return
        if self._full_analysis_active:
            self.engine_status.setText(
                self._tr("KataGo：正在进行全盘分析", "KataGo: analyzing the full game")
            )
            return
        state = getattr(self.engine, "state", "stopped")
        statuses = {
            "starting": ("KataGo：正在启动…", "KataGo: starting…"),
            "loading": ("KataGo：正在加载模型…", "KataGo: loading models…"),
            "analyzing": ("KataGo：正在分析当前局面", "KataGo: analyzing current position"),
            "ready": ("KataGo：已就绪", "KataGo: ready"),
            "stopping": ("KataGo：正在停止…", "KataGo: stopping…"),
            "failed": ("KataGo：分析出错", "KataGo: analysis error"),
            "stopped": ("KataGo：已停止", "KataGo: stopped"),
        }
        chinese, english = statuses.get(str(state), statuses["stopped"])
        self.engine_status.setText(self._tr(chinese, english))

    def _open_analysis_settings(self) -> None:
        dialog = AnalysisSettingsDialog(self.analysis_settings, self, language=self.language)
        if dialog.exec() != AnalysisSettingsDialog.DialogCode.Accepted:
            return
        settings = dialog.settings()
        if settings == self.analysis_settings:
            return
        for request_id in (self._active_realtime_request_id, self._active_full_request_id):
            if request_id is not None:
                self._ignored_analysis_requests.add(request_id)
        self._active_realtime_request_id = None
        self._active_full_request_id = None
        if self._full_analysis_active:
            self._stop_full_game_analysis(request_realtime=False)
            self.full_analysis_progress.hide()
        elif self.engine is not None and not self._is_ai_turn():
            self.engine.stop_analysis()
        self.repository.save_setting("analysis", settings.to_mapping())
        self.analysis_settings = settings
        self._full_analysis_visits = settings.visits
        self._analysis_payload_by_node = self._load_analysis_payloads(self.record.id)
        self._ownership_by_node = self._load_cached_ownership(self.record.id)
        self._analysis_by_node = self._black_winrates_from_payloads()
        self._clear_analysis_display()
        self._refresh()
        self._request_analysis()
        self.statusBar().showMessage(
            self._tr(
                f"分析访问量已设为 {settings.visits} visits",
                f"Analysis visits set to {settings.visits}",
            ),
            5000,
        )

    def _open_ollama_settings(self) -> None:
        dialog = OllamaSettingsDialog(
            self.ollama_settings, self.ollama_client, self, language=self.language
        )
        if dialog.exec() != OllamaSettingsDialog.DialogCode.Accepted:
            return
        settings = dialog.settings()
        if settings == self.ollama_settings:
            return
        self.repository.save_setting("ollama", settings.to_mapping())
        self.ollama_settings = settings
        self._invalidate_ollama_explanation()
        self._schedule_ollama_explanation()
        self.statusBar().showMessage(
            self._tr("本机 AI 解释设置已保存", "Local AI explanation settings saved"), 4000
        )

    def _update_ollama_controls(self) -> None:
        busy = self._ollama_request_id is not None
        available = (
            not self._ollama_closed
            and self.ollama_settings.enabled
            and self.record.mode != "fair"
            and self._candidate_explanation is not None
            and self._displayed_analysis_payload is not None
            and self._displayed_analysis_payload.get("isDuringSearch") is not True
            and not self._ollama_katago_busy()
        )
        self.ollama_generate_button.setEnabled(available and not busy)
        self.ollama_cancel_button.setEnabled(
            (busy or self._ollama_timer.isActive()) and not self._ollama_closed
        )
        if self._ollama_closed:
            return
        if self.record.mode == "fair":
            self.ollama_status.setText(
                self._tr(
                    "公平对战中不提供 AI 棋理解释。",
                    "AI explanations are unavailable during fair play.",
                )
            )
        elif not self.ollama_settings.enabled:
            self.ollama_status.setText(
                self._tr(
                    "尚未启用；可在“本机 AI 解释设置”中配置。",
                    "Not enabled. Configure it in Local AI Explanation Settings.",
                )
            )
        elif self._candidate_explanation is None:
            self.ollama_status.setText(
                self._tr(
                    "需要先取得 KataGo 分析并选择候选手。",
                    "Wait for KataGo analysis, then select a candidate move.",
                )
            )
        elif self._ollama_katago_busy():
            self.ollama_status.setText(
                self._tr(
                    "KataGo 分析优先；完成后将自动补充文字解释。",
                    "KataGo analysis has priority. A text explanation will follow automatically.",
                )
            )
        elif (
            self._displayed_analysis_payload is not None
            and self._displayed_analysis_payload.get("isDuringSearch") is True
        ):
            self.ollama_status.setText(
                self._tr(
                    "等待 KataGo 搜索完成；上方规则说明实时更新。",
                    "Waiting for KataGo search to finish. The rules explanation above updates live.",
                )
            )
        elif not busy and self._ollama_idle_status is not None:
            self.ollama_status.setText(self._ollama_idle_status)
        elif (
            not busy
            and not self.ollama_explanation.toPlainText()
            and not self._ollama_auto_attempted
        ):
            self.ollama_status.setText(
                self._tr(
                    f"已就绪 · {self.ollama_settings.model}",
                    f"Ready · {self.ollama_settings.model}",
                )
            )

    def _ollama_katago_busy(self) -> bool:
        return (
            self._full_analysis_active
            or getattr(self.engine, "active_request_id", None) is not None
            or getattr(self.engine, "state", None) in {"starting", "loading", "analyzing"}
        )

    def _invalidate_ollama_explanation(self, *, suppress_auto: bool = False) -> None:
        self._ollama_timer.stop()
        self._ollama_auto_attempted = suppress_auto
        self._ollama_idle_status = None
        self._ollama_generation += 1
        request_id = self._ollama_request_id
        self._ollama_request_id = None
        self._ollama_request_generation = None
        if request_id is not None:
            self.ollama_client.cancel(request_id)
        self.ollama_explanation.clear()
        self._update_ollama_controls()

    def _cancel_ollama_explanation(self) -> None:
        if self._ollama_request_id is None and not self._ollama_timer.isActive():
            return
        self._invalidate_ollama_explanation(suppress_auto=True)
        self._ollama_idle_status = self._tr(
            "已取消；KataGo 数据与本地规则说明仍可使用。",
            "Cancelled. KataGo data and local rules explanations remain available.",
        )
        self.ollama_status.setText(self._ollama_idle_status)

    def _schedule_ollama_explanation(self) -> None:
        if (
            self._ollama_closed
            or not self.ollama_settings.enabled
            or self.record.mode == "fair"
            or self._candidate_explanation is None
            or self._displayed_analysis_payload is None
            or self._displayed_analysis_payload.get("isDuringSearch") is True
            or self._ollama_request_id is not None
            or self._ollama_auto_attempted
        ):
            return
        if self._ollama_katago_busy():
            self._ollama_timer.stop()
            self._update_ollama_controls()
            return
        if not self._ollama_timer.isActive():
            self._ollama_timer.start()
        self._update_ollama_controls()
        self.ollama_status.setText(
            self._tr(
                f"将自动补充棋理解释 · {self.ollama_settings.model}",
                f"Automatic explanation pending · {self.ollama_settings.model}",
            )
        )

    def _generate_ollama_explanation(self) -> None:
        if (
            self._ollama_closed
            or not self.ollama_settings.enabled
            or self.record.mode == "fair"
            or self._candidate_explanation is None
            or self._displayed_analysis_payload is None
            or self._displayed_analysis_payload.get("isDuringSearch") is True
            or self._ollama_request_id is not None
        ):
            return
        if self._ollama_katago_busy():
            self._ollama_timer.stop()
            self._update_ollama_controls()
            return
        self._invalidate_ollama_explanation(suppress_auto=True)
        try:
            if self.language == "en":
                messages = build_ollama_messages(
                    self.tree.current.state,
                    self._candidate_explanation,
                    rules=self.record.rules,
                    komi=self.record.komi,
                    language="en",
                )
            else:
                messages = build_ollama_messages(
                    self.tree.current.state,
                    self._candidate_explanation,
                    rules=self.record.rules,
                    komi=self.record.komi,
                )
            request_id = self.ollama_client.generate(
                self.ollama_settings.base_url,
                self.ollama_settings.model,
                messages,
            )
        except ValueError as exc:
            self._ollama_idle_status = self._ollama_failure_status(
                str(exc), "无法生成：", "Could not generate: "
            )
            self.ollama_status.setText(self._ollama_idle_status)
            return
        self._ollama_request_id = request_id
        self._ollama_request_generation = self._ollama_generation
        self._update_ollama_controls()
        self.ollama_status.setText(
            self._tr(
                f"正在生成 · {self.ollama_settings.model}",
                f"Generating · {self.ollama_settings.model}",
            )
        )

    def _ollama_explanation_partial(self, request_id: str, text: str) -> None:
        if (
            self._ollama_closed
            or request_id != self._ollama_request_id
            or self._ollama_request_generation != self._ollama_generation
        ):
            return
        self.ollama_explanation.setPlainText(text)
        self.ollama_status.setText(
            self._tr(
                f"正在生成 · {self.ollama_settings.model}",
                f"Generating · {self.ollama_settings.model}",
            )
        )

    def _ollama_explanation_ready(self, request_id: str, text: str) -> None:
        if (
            self._ollama_closed
            or request_id != self._ollama_request_id
            or self._ollama_request_generation != self._ollama_generation
        ):
            return
        self._ollama_request_id = None
        self._ollama_request_generation = None
        self.ollama_explanation.setPlainText(text)
        self._ollama_idle_status = self._tr(
            f"生成完成 · {self.ollama_settings.model} · 请结合 KataGo 核对",
            f"Done · {self.ollama_settings.model} · Verify against KataGo",
        )
        self._update_ollama_controls()

    def _ollama_request_failed(self, request_id: str, message: str) -> None:
        if (
            self._ollama_closed
            or request_id != self._ollama_request_id
            or self._ollama_request_generation != self._ollama_generation
        ):
            return
        self._ollama_request_id = None
        self._ollama_request_generation = None
        self.ollama_explanation.clear()
        self._ollama_idle_status = self._ollama_failure_status(
            message, "生成失败：", "Generation failed: "
        )
        self._update_ollama_controls()

    def _configure_audio_feedback(self) -> None:
        configure = getattr(self.audio_feedback, "configure", None)
        if callable(configure):
            configure(self.preferences)
        else:
            self.audio_feedback.set_muted(self.preferences.muted)

    def _mute_changed(self, muted: bool) -> None:
        self.preferences = replace(self.preferences, muted=muted)
        self.audio_feedback.set_muted(muted)
        self.repository.save_setting("appearance_audio", self.preferences.to_mapping())

    def _open_library(self) -> None:
        dialog = GameLibraryDialog(
            self.repository,
            current_game_id=self.record.id,
            parent=self,
            language=self.language,
        )
        result = dialog.exec()
        current_metadata = dialog.metadata_updates.get(self.record.id)
        if current_metadata is not None:
            name, black_player, white_player = current_metadata
            self.record = replace(
                self.record,
                name=name,
                black_player=black_player,
                white_player=white_player,
            )
            self._refresh()
        if result != GameLibraryDialog.DialogCode.Accepted:
            return
        selected_game_id = dialog.selected_game_id
        if selected_game_id is None:
            return
        record, tree = self.repository.load_game(selected_game_id)
        review_mode = True
        action = "review"
        if self._is_unfinished_battle_record(record):
            action = self._choose_unfinished_game_action(record)
            if action == "cancel":
                self.statusBar().showMessage(
                    self._tr("已取消切换棋谱", "Game switch cancelled"), 3000
                )
                return
            review_mode = action != "continue"
        if self.engine is not None:
            self.engine.stop_analysis()
        self._stop_full_game_analysis(request_realtime=False)
        self._apply_loaded_game(record, tree, review_mode=review_mode)
        mode_text = (
            self._tr("继续对弈", "Continue playing")
            if action == "continue"
            else self._tr("仅复盘", "Review only")
        )
        self.statusBar().showMessage(
            self._tr(
                f"已打开棋谱：{record.name} · {mode_text}",
                f"Opened game: {record.name} · {mode_text}",
            ),
            5000,
        )
        self._request_analysis()

    def _import_image_position(self) -> None:
        dialog = ImageImportDialog(self, language=self.language)
        if dialog.exec() != ImageImportDialog.DialogCode.Accepted:
            return
        options = dialog.options()
        if self.engine is not None:
            self.engine.stop_analysis()
        self._stop_full_game_analysis(request_realtime=False)
        state = BoardState.from_setup(
            options.stones,
            size=options.board_size,
            to_play=options.to_play,
        )
        tree = GameTree(state)
        player = "black" if options.to_play is Color.BLACK else "white"
        record = self.repository.create_game(
            tree,
            name=self._tr(
                f"图片局面 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                f"Image position {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            ),
            rules=self.record.rules,
            komi=self.record.komi,
            mode="manual",
            human_color=player,
            difficulty=self.record.difficulty,
        )
        self._apply_loaded_game(record, tree, review_mode=False)
        self._request_analysis()
        side = (
            self._tr("黑方", "Black")
            if options.to_play is Color.BLACK
            else self._tr("白方", "White")
        )
        self.statusBar().showMessage(
            self._tr(
                f"图片局面已创建 · {options.board_size} 路 · 当前{side}落子",
                f"Image position created · {options.board_size}×{options.board_size} · {side} to play",
            ),
            6000,
        )

    def _choose_unfinished_game_action(self, record: GameRecord) -> str:
        prompt = QMessageBox(self)
        prompt.setWindowTitle(self._tr("未完成的对局", "Unfinished game"))
        prompt.setText(
            self._tr(
                f"棋谱“{record.name}”尚未结束，请选择打开方式。",
                f"The game “{record.name}” is unfinished. Choose how to open it.",
            )
        )
        continue_button = prompt.addButton(
            self._tr("继续对弈", "Continue playing"),
            QMessageBox.ButtonRole.AcceptRole,
        )
        review_button = prompt.addButton(
            self._tr("仅复盘", "Review only"),
            QMessageBox.ButtonRole.ActionRole,
        )
        cancel_button = prompt.addButton(
            self._tr("取消", "Cancel"),
            QMessageBox.ButtonRole.RejectRole,
        )
        prompt.setDefaultButton(review_button)
        prompt.exec()
        selected = prompt.clickedButton()
        if selected is continue_button:
            return "continue"
        if selected is review_button:
            return "review"
        if selected is cancel_button:
            return "cancel"
        return "cancel"

    def _apply_loaded_game(
        self,
        record: GameRecord,
        tree: GameTree,
        *,
        review_mode: bool,
    ) -> None:
        self.record = record
        self.tree = tree
        self._analysis_payload_by_node = self._load_analysis_payloads(record.id)
        self._ownership_by_node = self._load_cached_ownership(record.id)
        self._analysis_by_node = self._black_winrates_from_payloads()
        self._review_line_ids = [node.id for node in tree.line_through()]
        self._review_mode_active = review_mode
        self._startup_resume_pending = False
        self.full_analysis_progress.hide()
        self._resume_after_scoring = False
        self._sync_game_controls()
        self._apply_mode_controls()
        self._refresh()

    def _sync_game_controls(self) -> None:
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(self.record.mode)))
        self.mode_combo.blockSignals(False)
        self.human_color_combo.blockSignals(True)
        self.human_color_combo.setCurrentIndex(
            max(0, self.human_color_combo.findData(self.record.human_color))
        )
        self.human_color_combo.blockSignals(False)
        self.difficulty_combo.blockSignals(True)
        difficulty = self.record.difficulty if self.record.difficulty in PRESETS else "中级"
        self.difficulty_combo.setCurrentIndex(self.difficulty_combo.findData(difficulty))
        self.difficulty_combo.blockSignals(False)

    def _import_sgf(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            self._tr("导入 SGF 棋谱", "Import SGF game"),
            "",
            self._tr(
                "Smart Game Format (*.sgf);;所有文件 (*)",
                "Smart Game Format (*.sgf);;All files (*)",
            ),
        )
        if not selected:
            return
        try:
            imported = import_sgf(Path(selected))
            record = self.repository.import_game_tree(
                imported.tree,
                name=imported.name,
                black_player=imported.black_player,
                white_player=imported.white_player,
                rules=imported.rules,
                komi=imported.komi,
                result=imported.result,
                mode="manual",
            )
        except (OSError, ValueError, KeyError, sqlite3.DatabaseError) as exc:
            QMessageBox.warning(self, self._tr("SGF 导入失败", "SGF import failed"), str(exc))
            return
        if self.engine is not None:
            self.engine.stop_analysis()
        self._stop_full_game_analysis(request_realtime=False)
        self._apply_loaded_game(record, imported.tree, review_mode=True)
        self.statusBar().showMessage(
            self._tr(
                f"已导入 {Path(selected).name}，变化分支已保留并自动保存",
                f"Imported {Path(selected).name}; variations were retained and saved",
            ),
            6000,
        )
        self._request_analysis()

    def _export_sgf(self) -> None:
        suggested = f"{self.record.name or self._tr('棋谱', 'Game')}.sgf"
        selected, _filter = QFileDialog.getSaveFileName(
            self,
            self._tr("导出 SGF 棋谱", "Export SGF game"),
            suggested,
            "Smart Game Format (*.sgf)",
        )
        if not selected:
            return
        destination = Path(selected)
        if destination.suffix.lower() != ".sgf":
            destination = destination.with_suffix(".sgf")
        try:
            export_sgf(
                destination,
                self.tree,
                name=self.record.name,
                rules=self.record.rules,
                komi=self.record.komi,
                result=self.record.result,
                black_player=self.record.black_player,
                white_player=self.record.white_player,
            )
        except OSError as exc:
            QMessageBox.warning(self, self._tr("SGF 导出失败", "SGF export failed"), str(exc))
            return
        self.statusBar().showMessage(
            self._tr(f"棋谱已导出：{destination}", f"Game exported: {destination}"), 6000
        )

    def _refresh(self) -> None:
        self._candidate_explanation = None
        self._analysis_payload_fingerprint = None
        self._invalidate_ollama_explanation()
        node = self.tree.current
        last_move = None if node.move is None else node.move.point
        self.board_widget.set_position(node.state, last_move)
        self.board_widget.set_input_enabled(
            self.record.status != "completed"
            and not self._review_mode_active
            and not self._full_analysis_active
            and not self._is_ai_turn()
            and (not node.state.is_game_over or self._resume_after_scoring)
        )
        self.board_widget.set_candidates([])
        self._candidate_payloads = []
        self._displayed_analysis_payload = None
        self.explanation.clear()
        self._render_game_info()
        state = node.state
        self._sync_navigation_controls()
        self._redraw_winrate_plot()
        self._show_manual_candidate_placeholder()
        self._show_cached_analysis_for_current()
        self._update_review_summary()
        self.statusBar().showMessage(
            self._tr(
                f"第 {state.move_number} 手已保存 · 节点 {node.id[:8]}",
                f"Move {state.move_number} saved · node {node.id[:8]}",
            )
        )

    def _render_game_info(self) -> None:
        state = self.tree.current.state
        side = (
            self._tr("黑", "Black")
            if state.to_play.short_name == "B"
            else self._tr("白", "White")
        )
        result_line = (
            self._tr(
                f"\n结果：{format_result(self.record.result, language=self.language)}",
                f"\nResult: {format_result(self.record.result, language=self.language)}",
            )
            if self.record.result
            else ""
        )
        battle_line = ""
        if self._is_battle_mode():
            human = (
                self._tr("黑", "Black")
                if self._human_color() is Color.BLACK
                else self._tr("白", "White")
            )
            ai = (
                self._tr("白", "White")
                if self._ai_color() is Color.WHITE
                else self._tr("黑", "Black")
            )
            battle_line = self._tr(
                f"\n对战执色：你执{human} · AI执{ai}",
                f"\nColors: you play {human} · AI plays {ai}",
            )
        review_line = self._current_move_review_text()
        if self.language == "en":
            self.game_info.setText(
                f"Game: {self.record.name}\n"
                f"Black: {self.record.black_player or 'Unknown'}   "
                f"White: {self.record.white_player or 'Unknown'}\n"
                f"Move number: {state.move_number}\n"
                f"To play: {side}\n"
                f"Black captures: {state.black_captures}   White captures: {state.white_captures}\n"
                f"Rules: {format_rules_and_komi(self.record.rules, self.record.komi, language='en')}\n"
                f"Saved automatically{battle_line}{result_line}{review_line}"
            )
        else:
            self.game_info.setText(
                f"棋谱：{self.record.name}\n"
                f"黑方：{self.record.black_player or '未知'}　"
                f"白方：{self.record.white_player or '未知'}\n"
                f"手数：{state.move_number}\n"
                f"轮到：{side}方\n"
                f"黑提子：{state.black_captures}　白提子：{state.white_captures}\n"
                f"规则：{format_rules_and_komi(self.record.rules, self.record.komi)}\n"
                f"保存：已自动保存{battle_line}{result_line}{review_line}"
            )

    def _show_manual_candidate_placeholder(self) -> None:
        self.candidate_table.setRowCount(1)
        values = ["—", "—", "—", "—", self._tr("等待AI分析", "Waiting for AI analysis")]
        for column, value in enumerate(values):
            self.candidate_table.setItem(0, column, QTableWidgetItem(value))

    def _black_winrates_from_payloads(self) -> dict[str, float]:
        values: dict[str, float] = {}
        for node_id, payload in self._analysis_payload_by_node.items():
            if node_id not in self.tree.nodes:
                continue
            value = black_winrate(self.tree, node_id, payload)
            if value is not None:
                values[node_id] = value
        return values

    def _load_analysis_payloads(self, game_id: str) -> dict[str, dict[str, object]]:
        visits = self.analysis_settings.visits
        return self.repository.analysis_snapshots_for_game(
            game_id,
            cache_keys=(
                f"realtime-{visits}-0",
                f"realtime-{visits}-1",
                f"full-game-{visits}",
            ),
        )

    def _load_cached_ownership(self, game_id: str) -> dict[str, list[float]]:
        snapshots = self.repository.analysis_snapshots_for_game(
            game_id,
            cache_keys=(f"realtime-{self.analysis_settings.visits}-1",),
        )
        ownership_by_node: dict[str, list[float]] = {}
        for node_id, payload in snapshots.items():
            ownership = self._ownership_values(payload)
            if ownership is not None:
                ownership_by_node[node_id] = ownership
        return ownership_by_node

    @staticmethod
    def _ownership_values(payload: dict[str, object]) -> list[float] | None:
        raw = payload.get("ownership")
        if not isinstance(raw, list):
            return None
        values: list[float] = []
        for value in raw:
            if not isinstance(value, (int, float)):
                return None
            values.append(float(value))
        return values

    def _set_review_line_from_current(self) -> None:
        self._review_line_ids = [node.id for node in self.tree.line_through()]

    def _review_index(self) -> int:
        try:
            return self._review_line_ids.index(self.tree.current_id)
        except ValueError:
            self._set_review_line_from_current()
            return self._review_line_ids.index(self.tree.current_id)

    def _sync_navigation_controls(self) -> None:
        maximum = max(0, len(self._review_line_ids) - 1)
        current_index = min(self._review_index(), maximum)
        for control in (self.move_slider, self.move_spin):
            control.blockSignals(True)
            control.setRange(0, maximum)
            control.setValue(current_index)
            control.blockSignals(False)
        current_move = self.tree.current.state.move_number
        last_move = self.tree.nodes[self._review_line_ids[-1]].state.move_number
        self.navigation_label.setText(
            self._tr(
                f"第 {current_move} / {last_move} 手",
                f"Move {current_move} / {last_move}",
            )
        )
        self.first_move_button.setEnabled(current_index > 0)
        self.previous_move_button.setEnabled(current_index > 0)
        self.next_move_button.setEnabled(current_index < maximum)
        self.last_move_button.setEnabled(current_index < maximum)

    def _navigate_review(self, index: int) -> None:
        if not self._review_line_ids:
            return
        bounded = max(0, min(int(index), len(self._review_line_ids) - 1))
        node_id = self._review_line_ids[bounded]
        if node_id == self.tree.current_id:
            self._sync_navigation_controls()
            return
        if self.engine is not None and not self._full_analysis_active:
            self.engine.stop_analysis()
        self.tree.go_to(node_id)
        self.repository.set_current(self.record.id, node_id)
        self._refresh()
        self._request_analysis()

    def _navigate_previous(self) -> None:
        self._navigate_review(self._review_index() - 1)

    def _navigate_next(self) -> None:
        self._navigate_review(self._review_index() + 1)

    def _navigate_last(self) -> None:
        self._navigate_review(len(self._review_line_ids) - 1)

    def _show_cached_analysis_for_current(self) -> None:
        payload = self._analysis_payload_by_node.get(self.tree.current_id)
        if payload is not None:
            self._display_analysis_payload(self.tree.current_id, payload)
        else:
            self._show_cached_ownership_for_current()

    def _show_cached_ownership_for_current(self) -> None:
        if not (self.analysis_checkbox.isChecked() and self.ownership_checkbox.isChecked()):
            self.board_widget.set_ownership(None)
            return
        self.board_widget.set_ownership(self._ownership_by_node.get(self.tree.current_id))

    def _move_reviews(self) -> list[MoveReview]:
        return build_move_reviews(
            self.tree,
            self._review_line_ids,
            self._analysis_payload_by_node,
        )

    def _current_move_review_text(self) -> str:
        if self.tree.current_id == self.tree.root_id:
            return ""
        for review in self._move_reviews():
            if review.node_id != self.tree.current_id:
                continue
            if self.language == "en":
                loss_en = (
                    "waiting for the next position's analysis"
                    if review.winrate_loss is None
                    else f"win-rate loss {review.winrate_loss:.1f}%"
                )
                score_en = (
                    "" if review.score_loss is None else f", score loss {review.score_loss:.1f}"
                )
                match_en = (
                    "matches the AI's top move"
                    if review.matches_best
                    else f"AI top move {review.best_move}"
                )
                return f"\nThis move: {self._grade_label(review.grade)} · {loss_en}{score_en} · {match_en}"
            loss = (
                "等待后续局面分析"
                if review.winrate_loss is None
                else f"胜率损失 {review.winrate_loss:.1f}%"
            )
            score = "" if review.score_loss is None else f"、目差损失 {review.score_loss:.1f}"
            match = "吻合AI首选" if review.matches_best else f"AI首选 {review.best_move}"
            return f"\n本手复盘：{review.grade} · {loss}{score} · {match}"
        return ""

    def _update_review_summary(self, _scope: str = "") -> None:
        total_positions = len(self._review_line_ids)
        analyzed_positions = sum(
            node_id in self._analysis_payload_by_node for node_id in self._review_line_ids
        )
        all_reviews = build_move_reviews(
            self.tree,
            self._review_line_ids,
            self._analysis_payload_by_node,
        )
        reviews = [review for review in all_reviews if self._review_in_selected_scope(review)]
        self._populate_problem_plot(reviews)
        if not reviews:
            if self.language == "en":
                self.review_summary.setText(
                    f"Analyzed positions: {analyzed_positions}/{total_positions}\n"
                    f"Scope: {self.review_scope_combo.currentText()}\n\n"
                    "After full-game analysis, move quality, problem moves, and match rates will be shown separately for Black and White."
                )
                self._clear_review_plots()
                return
            self.review_summary.setText(
                f"已分析局面：{analyzed_positions}/{total_positions}\n"
                f"当前范围：{self.review_scope_combo.currentText()}\n\n"
                "完成全盘分析后，将按黑方、白方分别显示着法质量、问题手和吻合度。"
            )
            self._clear_review_plots()
            return
        summary = summarize_reviews(reviews)
        if self.language == "en":
            self.review_summary.setText(
                f"Analyzed positions: {analyzed_positions}/{total_positions}\n"
                f"Scope: {self.review_scope_combo.currentText()}\n\n"
                f"Black: Good {summary.black.grade_counts['好手']} · "
                f"Normal {summary.black.grade_counts['正常']} · "
                f"Dubious {summary.black.grade_counts['疑问手']} · "
                f"Bad {summary.black.grade_counts['坏手']} · "
                f"Blunder {summary.black.grade_counts['严重失误']}\n"
                f"White: Good {summary.white.grade_counts['好手']} · "
                f"Normal {summary.white.grade_counts['正常']} · "
                f"Dubious {summary.white.grade_counts['疑问手']} · "
                f"Bad {summary.white.grade_counts['坏手']} · "
                f"Blunder {summary.white.grade_counts['严重失误']}\n\n"
                "See Move Quality, Problem Moves, and Match Rate for details."
            )
            self._populate_quality_plot(summary)
            self._populate_match_plot(summary, reviews)
            return
        self.review_summary.setText(
            f"已分析局面：{analyzed_positions}/{total_positions}\n"
            f"当前范围：{self.review_scope_combo.currentText()}\n\n"
            f"黑方：好手 {summary.black.grade_counts['好手']} · "
            f"正常 {summary.black.grade_counts['正常']} · "
            f"疑问手 {summary.black.grade_counts['疑问手']} · "
            f"坏手 {summary.black.grade_counts['坏手']} · "
            f"严重失误 {summary.black.grade_counts['严重失误']}\n"
            f"白方：好手 {summary.white.grade_counts['好手']} · "
            f"正常 {summary.white.grade_counts['正常']} · "
            f"疑问手 {summary.white.grade_counts['疑问手']} · "
            f"坏手 {summary.white.grade_counts['坏手']} · "
            f"严重失误 {summary.white.grade_counts['严重失误']}\n\n"
            "详细数据可切换到“着法质量”“问题手”“吻合度”查看。"
        )
        self._populate_quality_plot(summary)
        self._populate_match_plot(summary, reviews)

    def _review_in_selected_scope(self, review: MoveReview) -> bool:
        scope = self.review_scope_combo.currentData()
        if scope == "opening":
            return review.move_number <= 60
        if scope == "middle":
            return 61 <= review.move_number <= 160
        if scope == "endgame":
            return review.move_number >= 161
        return True

    def _clear_review_plots(self) -> None:
        self.quality_plot.clear()
        self.problem_scatter.setData([])
        self._problem_review_positions.clear()
        self._hide_problem_hover()
        self._clear_match_graphics()
        self.match_scatter.setData([])
        self._match_reviews_by_color = {Color.BLACK: [], Color.WHITE: []}
        self._hide_match_hover()
        self.quality_details.setText(
            self._tr(
                "● 黑方　○ 白方 · 暂无当前范围的分析数据",
                "● Black   ○ White · No analysis in this scope",
            )
        )
        self.problem_details.setText(
            self._tr("当前范围内暂无问题手。", "No problem moves in this scope.")
        )
        self.match_details.setText(
            self._tr("当前范围内暂无吻合度数据。", "No match-rate data in this scope.")
        )
        self.match_black_summary.setText(self._tr("等待黑方分析", "Waiting for Black analysis"))
        self.match_white_summary.setText(self._tr("等待白方分析", "Waiting for White analysis"))

    def _populate_quality_plot(self, summary: ReviewSummary) -> None:
        grades = ("好手", "正常", "疑问手", "坏手", "严重失误")
        positions = list(range(len(grades)))
        black_counts = [summary.black.grade_counts[grade] for grade in grades]
        white_counts = [summary.white.grade_counts[grade] for grade in grades]
        self.quality_plot.clear()
        self.quality_plot.addItem(
            BarGraphItem(
                x=[position - 0.19 for position in positions],
                height=black_counts,
                width=0.36,
                brush="#20242a",
                pen="#43a8ff",
            )
        )
        self.quality_plot.addItem(
            BarGraphItem(
                x=[position + 0.19 for position in positions],
                height=white_counts,
                width=0.36,
                brush="#e8edf2",
                pen="#ffffff",
            )
        )
        self.quality_plot.setXRange(-0.65, 4.65, padding=0.02)
        maximum = max([1, *black_counts, *white_counts])
        self.quality_plot.setYRange(0, maximum * 1.15, padding=0.02)
        self.quality_details.setText(
            self._tr(
                "● 黑方　○ 白方　"
                f"黑：{summary.black.analyzed_moves}手　白：{summary.white.analyzed_moves}手",
                "● Black   ○ White   "
                f"Black: {summary.black.analyzed_moves} moves   White: {summary.white.analyzed_moves} moves",
            )
        )

    def _populate_match_plot(
        self,
        summary: ReviewSummary,
        reviews: list[MoveReview],
    ) -> None:
        self._clear_match_graphics()
        if not reviews:
            self.match_scatter.setData([])
            self._match_reviews_by_color = {Color.BLACK: [], Color.WHITE: []}
            self._hide_match_hover()
            self.match_black_summary.setText(
                self._tr("等待黑方分析", "Waiting for Black analysis")
            )
            self.match_white_summary.setText(
                self._tr("等待白方分析", "Waiting for White analysis")
            )
            return

        self._match_reviews_by_color = {
            color: sorted(
                (review for review in reviews if review.color is color),
                key=lambda review: review.move_number,
            )
            for color in (Color.BLACK, Color.WHITE)
        }

        first_move = min(review.move_number for review in reviews)
        last_move = max(review.move_number for review in reviews)
        visible_span = max(10.0, float(last_move - first_move + 1))
        tick_width = max(0.75, min(1.7, visible_span / 115.0))
        side_settings = (
            (
                Color.BLACK,
                1.60,
                "#553b43",
                "#ff5964",
            ),
            (
                Color.WHITE,
                0.40,
                "#344b61",
                "#5aa5fa",
            ),
        )
        spots: list[dict[str, object]] = []
        for color, lane_y, lane_brush, tick_color in side_settings:
            side_reviews = self._match_reviews_by_color[color]
            lane = BarGraphItem(
                x=[(first_move + last_move) / 2.0],
                y0=[lane_y - 0.21],
                height=[0.42],
                width=[visible_span],
                brush=lane_brush,
                pen=None,
            )
            lane.setZValue(-3)
            self.match_plot.addItem(lane)
            self._match_graphics.append(lane)

            if side_reviews:
                ticks = BarGraphItem(
                    x=[review.move_number for review in side_reviews],
                    y0=[lane_y - 0.17] * len(side_reviews),
                    height=[0.34] * len(side_reviews),
                    width=tick_width,
                    brush=tick_color,
                    pen=None,
                )
                ticks.setZValue(-2)
                self.match_plot.addItem(ticks)
                self._match_graphics.append(ticks)

            for streak in self._good_streaks(side_reviews):
                streak_start = streak[0].move_number - tick_width / 2.0
                streak_end = streak[-1].move_number + tick_width / 2.0
                streak_bar = self.match_plot.plot(
                    [streak_start, streak_end],
                    [lane_y - 0.37, lane_y - 0.37],
                    pen=mkPen("#7ed321", width=9),
                )
                streak_bar.setZValue(0)
                self._match_graphics.append(streak_bar)

            for review in side_reviews:
                spots.append(
                    {
                        "pos": (review.move_number, lane_y),
                        "brush": (0, 0, 0, 0),
                        "pen": (0, 0, 0, 0),
                        "data": review.node_id,
                    }
                )

        self.match_scatter.setData(spots)
        self._set_review_plot_x_range(self.match_plot, reviews)
        black_good_rate = self._side_good_rate(summary.black)
        white_good_rate = self._side_good_rate(summary.white)
        self.match_black_summary.setText(
            self._tr(
                "<span style='color:#ff6670'>●</span> <b>黑方</b><br>"
                f"一选　{summary.black.best_match_rate:.1f}%<br>"
                f"前三　{summary.black.top_three_match_rate:.1f}%<br>"
                f"好手　{black_good_rate:.1f}%<br>"
                f"分析　{summary.black.analyzed_moves}手",
                "<span style='color:#ff6670'>●</span> <b>Black</b><br>"
                f"Top move {summary.black.best_match_rate:.1f}%<br>"
                f"Top three {summary.black.top_three_match_rate:.1f}%<br>"
                f"Good moves {black_good_rate:.1f}%<br>"
                f"Analyzed {summary.black.analyzed_moves} moves",
            )
        )
        self.match_white_summary.setText(
            self._tr(
                "<span style='color:#69adff'>●</span> <b>白方</b><br>"
                f"一选　{summary.white.best_match_rate:.1f}%<br>"
                f"前三　{summary.white.top_three_match_rate:.1f}%<br>"
                f"好手　{white_good_rate:.1f}%<br>"
                f"分析　{summary.white.analyzed_moves}手",
                "<span style='color:#69adff'>●</span> <b>White</b><br>"
                f"Top move {summary.white.best_match_rate:.1f}%<br>"
                f"Top three {summary.white.top_three_match_rate:.1f}%<br>"
                f"Good moves {white_good_rate:.1f}%<br>"
                f"Analyzed {summary.white.analyzed_moves} moves",
            )
        )
        self.match_details.setText(
            self._tr(
                "红色=黑方逐手记录　蓝色=白方逐手记录　绿色=连续好手；"
                "鼠标悬停可查看手数与该手分类，点击色块可跳转。",
                "Red = Black moves; blue = White moves; green = good-move streaks. Hover for move number and grade, or click a block to jump.",
            )
        )

    def _clear_match_graphics(self) -> None:
        for item in self._match_graphics:
            self.match_plot.removeItem(item)
        self._match_graphics.clear()

    def _match_mouse_moved(self, event: tuple[object, ...]) -> None:
        if not event or not isinstance(event[0], QPointF):
            return
        scene_position = event[0]
        view_box = self.match_plot.plotItem.vb
        if not view_box.sceneBoundingRect().contains(scene_position) or not any(
            self._match_reviews_by_color.values()
        ):
            self._hide_match_hover()
            return
        view_position = view_box.mapSceneToView(scene_position)
        lane_positions = {Color.BLACK: 1.60, Color.WHITE: 0.40}
        color = min(
            lane_positions,
            key=lambda candidate: abs(lane_positions[candidate] - view_position.y()),
        )
        if abs(lane_positions[color] - view_position.y()) > 0.48:
            self._hide_match_hover()
            return
        side_reviews = self._match_reviews_by_color[color]
        if not side_reviews:
            self._hide_match_hover()
            return
        review = min(
            side_reviews,
            key=lambda candidate: abs(candidate.move_number - view_position.x()),
        )
        move_number = review.move_number
        color_name = (
            self._tr("黑方", "Black")
            if review.color is Color.BLACK
            else self._tr("白方", "White")
        )
        if review.matches_best:
            match_label = self._tr("AI首选", "AI top move")
        elif review.matches_top_three:
            match_label = self._tr("AI前三候选", "AI top-three candidate")
        else:
            match_label = self._tr("未进AI前三", "Outside AI top three")
        lane_y = lane_positions[review.color]
        self.match_cursor.setPos(move_number)
        self.match_cursor.show()
        self.match_tooltip.setText(
            self._tr(
                f"第 {move_number} 手 · {color_name} · {review.move}\n"
                f"{review.grade} · {match_label}",
                f"Move {move_number} · {color_name} · {review.move}\n"
                f"{self._grade_label(review.grade)} · {match_label}",
            )
        )
        self._place_plot_tooltip(
            self.match_plot,
            self.match_tooltip,
            QPointF(float(move_number), lane_y + 0.31),
        )

    def _hide_match_hover(self) -> None:
        self.match_cursor.hide()
        self.match_tooltip.hide()

    @staticmethod
    def _place_plot_tooltip(
        plot: PlotWidget,
        tooltip: TextItem,
        view_position: QPointF,
    ) -> None:
        """Place a pyqtgraph tooltip and keep its rendered pixels inside the plot."""

        view_box = plot.plotItem.vb
        tooltip.setPos(view_position)
        tooltip.setVisible(True)
        item_bounds = tooltip.mapRectToScene(tooltip.boundingRect())
        plot_bounds = view_box.sceneBoundingRect().adjusted(4.0, 4.0, -4.0, -4.0)
        dx = 0.0
        dy = 0.0
        if item_bounds.left() < plot_bounds.left():
            dx = plot_bounds.left() - item_bounds.left()
        elif item_bounds.right() > plot_bounds.right():
            dx = plot_bounds.right() - item_bounds.right()
        if item_bounds.top() < plot_bounds.top():
            dy = plot_bounds.top() - item_bounds.top()
        elif item_bounds.bottom() > plot_bounds.bottom():
            dy = plot_bounds.bottom() - item_bounds.bottom()
        if dx or dy:
            parent = tooltip.parentItem()
            if parent is not None:
                scene_anchor = tooltip.mapToScene(QPointF(0.0, 0.0))
                tooltip.setPos(parent.mapFromScene(scene_anchor + QPointF(dx, dy)))

    @staticmethod
    def _good_streaks(reviews: list[MoveReview]) -> list[list[MoveReview]]:
        streaks: list[list[MoveReview]] = []
        current: list[MoveReview] = []
        for review in sorted(reviews, key=lambda item: item.move_number):
            continues = bool(current) and review.move_number == current[-1].move_number + 2
            if review.grade == "好手":
                if not continues:
                    if len(current) >= 2:
                        streaks.append(current)
                    current = []
                current.append(review)
            else:
                if len(current) >= 2:
                    streaks.append(current)
                current = []
        if len(current) >= 2:
            streaks.append(current)
        return streaks

    @staticmethod
    def _side_good_rate(summary: SideReviewSummary) -> float:
        if summary.analyzed_moves <= 0:
            return 0.0
        return summary.grade_counts["好手"] * 100.0 / summary.analyzed_moves

    def _populate_problem_plot(self, reviews: list[MoveReview]) -> None:
        problems = [
            review for review in reviews if review.grade in {"疑问手", "坏手", "严重失误"}
        ]
        levels = {"疑问手": 1, "坏手": 2, "严重失误": 3}
        colors = {"疑问手": "#f2c94c", "坏手": "#f2994a", "严重失误": "#eb5757"}
        spots: list[dict[str, object]] = []
        self._problem_review_positions = []
        self._hide_problem_hover()
        for review in problems:
            level = levels[review.grade]
            y_position = float(level if review.color is Color.BLACK else -level)
            self._problem_review_positions.append((review, y_position))
            spots.append(
                {
                    "pos": (
                        review.move_number,
                        y_position,
                    ),
                    "brush": colors[review.grade],
                    "pen": "#111111" if review.color is Color.BLACK else "#ffffff",
                    "symbol": "o" if review.color is Color.BLACK else "s",
                    "data": review.node_id,
                }
            )
        self.problem_scatter.setData(spots)
        self._set_review_plot_x_range(self.problem_plot, reviews)
        black_count = sum(review.color is Color.BLACK for review in problems)
        white_count = len(problems) - black_count
        self.problem_details.setText(
            self._tr(
                f"黑方问题手 {black_count} · 白方问题手 {white_count}　"
                "圆点=黑方，方点=白方；悬停查看损失，点击标记可跳转。",
                f"Black problem moves {black_count} · White problem moves {white_count}. "
                "Circles = Black, squares = White. Hover for losses or click to jump.",
            )
        )

    def _problem_mouse_moved(self, event: tuple[object, ...]) -> None:
        if not event or not isinstance(event[0], QPointF):
            return
        scene_position = event[0]
        view_box = self.problem_plot.plotItem.vb
        if (
            not view_box.sceneBoundingRect().contains(scene_position)
            or not self._problem_review_positions
        ):
            self._hide_problem_hover()
            return

        def distance_squared(item: tuple[MoveReview, float]) -> float:
            review, y_position = item
            marker = view_box.mapViewToScene(QPointF(float(review.move_number), y_position))
            return float(
                (marker.x() - scene_position.x()) ** 2 + (marker.y() - scene_position.y()) ** 2
            )

        review, y_position = min(
            self._problem_review_positions,
            key=distance_squared,
        )
        if distance_squared((review, y_position)) > 18.0**2:
            self._hide_problem_hover()
            return

        color_name = (
            self._tr("黑方", "Black")
            if review.color is Color.BLACK
            else self._tr("白方", "White")
        )
        winrate_loss = (
            self._tr("暂无", "N/A")
            if review.winrate_loss is None
            else f"{review.winrate_loss:.1f}%"
        )
        score_loss = (
            self._tr("暂无", "N/A")
            if review.score_loss is None
            else self._tr(f"{review.score_loss:.1f}目", f"{review.score_loss:.1f} points")
        )
        self.problem_cursor.setPos(review.move_number)
        self.problem_cursor.show()
        self.problem_tooltip.setText(
            self._tr(
                f"第 {review.move_number} 手 · {color_name} · 落点 {review.move}\n"
                f"等级：{review.grade}\n"
                f"胜率损失：{winrate_loss}\n目差损失：{score_loss}",
                f"Move {review.move_number} · {color_name} · {review.move}\n"
                f"Grade: {self._grade_label(review.grade)}\n"
                f"Win-rate loss: {winrate_loss}\nScore loss: {score_loss}",
            )
        )
        self._place_plot_tooltip(
            self.problem_plot,
            self.problem_tooltip,
            QPointF(float(review.move_number), y_position + 0.38),
        )

    def _hide_problem_hover(self) -> None:
        self.problem_cursor.hide()
        self.problem_tooltip.hide()

    @staticmethod
    def _set_review_plot_x_range(plot: PlotWidget, reviews: list[MoveReview]) -> None:
        if not reviews:
            plot.setXRange(0, 10, padding=0.02)
            return
        first_move = min(review.move_number for review in reviews)
        last_move = max(review.move_number for review in reviews)
        plot.setXRange(
            max(0, first_move - 3),
            max(first_move + 10, last_move + 3),
            padding=0.02,
        )

    def _review_scatter_clicked(
        self,
        _item: object,
        points: object,
        _event: object,
    ) -> None:
        if not isinstance(points, (list, tuple)) or not points:
            return
        data_method = getattr(points[0], "data", None)
        node_id = data_method() if callable(data_method) else None
        if not isinstance(node_id, str):
            return
        try:
            index = self._review_line_ids.index(node_id)
        except ValueError:
            return
        self._navigate_review(index)

    def _connect_engine(self) -> None:
        if self.engine is None:
            return
        self.engine.status_changed.connect(self._engine_status_changed)
        self.engine.failure_reported.connect(self._engine_failure)
        self.engine.analysis_updated.connect(self._analysis_update)
        self.engine.analysis_finished.connect(self._analysis_finished)

    def _engine_status_changed(self, message: str) -> None:
        self._last_engine_error_message = None
        english = {
            "KataGo：正在加载模型…": "KataGo: loading models…",
            "KataGo：分析已取消": "KataGo: analysis cancelled",
            "KataGo：正在重新启动…": "KataGo: restarting…",
            "KataGo：正在分析当前局面": "KataGo: analyzing current position",
            "KataGo：分析完成": "KataGo: analysis complete",
            "KataGo：已就绪": "KataGo: ready",
            "KataGo：进程已启动，正在加载模型…": "KataGo: process started; loading models…",
            "KataGo：已停止": "KataGo: stopped",
            "KataGo：启动超时": "KataGo: startup timed out",
            "KataGo：分析长时间无响应": "KataGo: analysis stalled",
        }
        self.engine_status.setText(
            self._tr(message, english.get(message, localize_error(message, self.language)))
        )

    def _analysis_toggled(self, enabled: bool) -> None:
        if self.engine is None:
            reason = (
                f"：{self._engine_unavailable_reason}"
                if self._engine_unavailable_reason
                else ""
            )
            reason_en = (
                f": {localize_error(self._engine_unavailable_reason, self.language)}"
                if self._engine_unavailable_reason
                else ""
            )
            self.engine_status.setText(
                self._tr(
                    f"KataGo：运行配置不可用{reason}",
                    f"KataGo: runtime configuration unavailable{reason_en}",
                )
            )
            self.analysis_checkbox.blockSignals(True)
            self.analysis_checkbox.setChecked(False)
            self.analysis_checkbox.blockSignals(False)
            return
        if enabled:
            self._show_cached_ownership_for_current()
            self._request_analysis()
        else:
            self.engine.stop_analysis()
            self._clear_analysis_display()
            self.engine_status.setText(
                self._tr("KataGo：实时分析已关闭", "KataGo: real-time analysis off")
            )

    def _analysis_option_changed(self, _value: object) -> None:
        self._invalidate_ollama_explanation()
        if not self.ownership_checkbox.isChecked():
            self.board_widget.set_ownership(None)
        else:
            self._show_cached_ownership_for_current()
        self._request_analysis()

    def _toggle_full_game_analysis(self) -> None:
        if self._full_analysis_active:
            self._stop_full_game_analysis(request_realtime=True)
            self.statusBar().showMessage(
                self._tr(
                    "已停止全盘AI分析；已完成部分仍已保存",
                    "Full-game analysis stopped; completed positions remain saved",
                ),
                6000,
            )
            return
        self._start_full_game_analysis()

    def _start_full_game_analysis(self) -> None:
        if self.engine is None:
            self.engine_status.setText(
                self._tr(
                    "KataGo：运行配置不可用，无法进行全盘分析",
                    "KataGo: runtime configuration unavailable; cannot analyze full game",
                )
            )
            return
        if not self._review_line_ids:
            return
        self.engine.stop_analysis()
        completed_snapshots = self.repository.analysis_snapshots_for_game(
            self.record.id,
            cache_keys=(f"full-game-{self._full_analysis_visits}",),
        )
        self._analysis_payload_by_node.update(completed_snapshots)
        self._analysis_by_node = self._black_winrates_from_payloads()
        missing = [
            node_id for node_id in self._review_line_ids if node_id not in completed_snapshots
        ]
        self._full_analysis_total = len(self._review_line_ids)
        self._full_analysis_completed = self._full_analysis_total - len(missing)
        self.full_analysis_progress.setRange(
            0,
            self._full_analysis_total * self._full_analysis_visits,
        )
        self.full_analysis_progress.setValue(
            self._full_analysis_completed * self._full_analysis_visits
        )
        self.full_analysis_progress.setFormat(
            self._tr(
                f"%p% · 已完成 {self._full_analysis_completed}/"
                f"{self._full_analysis_total} 个局面",
                f"%p% · Completed {self._full_analysis_completed}/{self._full_analysis_total} positions",
            )
        )
        self.full_analysis_progress.show()
        if not missing:
            self.engine_status.setText(
                self._tr(
                    "KataGo：这条棋谱已经完成全盘分析",
                    "KataGo: full-game analysis is already complete for this game",
                )
            )
            self.statusBar().showMessage(
                self._tr(
                    "全盘分析结果已从本地缓存恢复",
                    "Full-game analysis restored from local cache",
                ),
                6000,
            )
            self._refresh()
            return
        self._full_analysis_queue = list(reversed(missing))
        self._full_analysis_active = True
        self._review_mode_active = True
        self.full_analysis_action.setText(self._tr("停止全盘分析", "Stop full-game analysis"))
        self._apply_mode_controls()
        self._refresh()
        self._start_next_full_game_position()

    def _start_next_full_game_position(self) -> None:
        if not self._full_analysis_active:
            return
        if self.engine is None:
            self._stop_full_game_analysis(request_realtime=False)
            self.engine_status.setText(
                self._tr(
                    "KataGo：运行配置不可用，已停止全盘分析",
                    "KataGo: runtime unavailable; full-game analysis stopped",
                )
            )
            return
        if not self._full_analysis_queue:
            self._full_analysis_active = False
            self.full_analysis_action.setText(self._tr("全盘AI分析", "Analyze full game"))
            self._apply_mode_controls()
            self.full_analysis_progress.setValue(
                self._full_analysis_total * self._full_analysis_visits
            )
            self.full_analysis_progress.setFormat(
                self._tr(
                    f"100% · 已完成 {self._full_analysis_total}/"
                    f"{self._full_analysis_total} 个局面",
                    f"100% · Completed {self._full_analysis_total}/{self._full_analysis_total} positions",
                )
            )
            self.engine_status.setText(
                self._tr("KataGo：全盘分析完成", "KataGo: full-game analysis complete")
            )
            self.statusBar().showMessage(
                self._tr(
                    f"全盘AI分析完成，共 {self._full_analysis_total} 个局面",
                    f"Full-game analysis complete: {self._full_analysis_total} positions",
                ),
                8000,
            )
            self._refresh()
            return
        node_id = self._full_analysis_queue.pop()
        node = self.tree.nodes[node_id]
        self._update_full_analysis_progress(0)
        self._active_full_request_id = self.engine.analyze(
            tree=self.tree,
            node_id=node_id,
            rules=self.record.rules,
            komi=self.record.komi,
            max_visits=self._full_analysis_visits,
            human_profile=None,
            include_ownership=False,
            purpose="full_game",
        )
        self.engine_status.setText(
            self._tr(
                f"KataGo：全盘分析 "
                f"{self._full_analysis_completed + 1}/{self._full_analysis_total}"
                f"（第 {node.state.move_number} 手）",
                f"KataGo: full-game analysis {self._full_analysis_completed + 1}/"
                f"{self._full_analysis_total} (move {node.state.move_number})",
            )
        )

    def _stop_full_game_analysis(self, *, request_realtime: bool) -> None:
        if not self._full_analysis_active:
            return
        self._full_analysis_active = False
        self._full_analysis_queue.clear()
        if self.engine is not None:
            self.engine.stop_analysis()
        self.full_analysis_action.setText(self._tr("全盘AI分析", "Analyze full game"))
        self._apply_mode_controls()
        if request_realtime:
            self._request_analysis()
        if not self._ollama_katago_busy():
            self._show_cached_analysis_for_current()
        self._schedule_ollama_explanation()

    def _request_analysis(self) -> None:
        if self._is_ai_turn():
            self._request_ai_move()
            return
        if (
            self.engine is None
            or self._full_analysis_active
            or not self.analysis_checkbox.isChecked()
            or self.mode_combo.currentData() == "fair"
        ):
            return
        preset = PRESETS[str(self.difficulty_combo.currentData())]
        self._ollama_timer.stop()
        if self._ollama_request_id is not None:
            self._invalidate_ollama_explanation()
        self._active_realtime_request_id = self.engine.analyze(
            tree=self.tree,
            node_id=self.tree.current_id,
            rules=self.record.rules,
            komi=self.record.komi,
            max_visits=self.analysis_settings.visits,
            human_profile=preset.human_profile,
            include_ownership=self.ownership_checkbox.isChecked(),
            purpose="realtime",
        )
        self.engine_status.setText(
            self._tr("KataGo：等待当前局面分析", "KataGo: waiting to analyze current position")
        )
        self._update_ollama_controls()

    def _analysis_update(self, update: AnalysisUpdate) -> None:
        if update.request_id in self._ignored_analysis_requests:
            return
        if update.purpose not in {"realtime", "full_game"}:
            return
        if update.purpose == "full_game" and self._full_analysis_active:
            root_info = update.payload.get("rootInfo")
            if isinstance(root_info, dict):
                visits = root_info.get("visits", 0)
                if isinstance(visits, (int, float)):
                    self._update_full_analysis_progress(int(visits))
        if update.node_id != self.tree.current_id:
            return
        self._display_analysis_payload(update.node_id, update.payload)

    def _update_full_analysis_progress(self, current_visits: int) -> None:
        visits = max(0, min(current_visits, self._full_analysis_visits))
        self._full_analysis_current_visits = visits
        total_work = self._full_analysis_total * self._full_analysis_visits
        completed_work = self._full_analysis_completed * self._full_analysis_visits
        self.full_analysis_progress.setRange(0, total_work)
        self.full_analysis_progress.setValue(min(completed_work + visits, total_work))
        current_position = min(
            self._full_analysis_completed + 1,
            self._full_analysis_total,
        )
        self.full_analysis_progress.setFormat(
            self._tr(
                f"%p% · 局面 {current_position}/{self._full_analysis_total} · "
                f"{visits}/{self._full_analysis_visits} visits",
                f"%p% · Position {current_position}/{self._full_analysis_total} · "
                f"{visits}/{self._full_analysis_visits} visits",
            )
        )

    def _display_analysis_payload(
        self,
        node_id: str,
        payload: dict[str, object],
    ) -> None:
        move_infos_raw = payload.get("moveInfos")
        root_raw = payload.get("rootInfo")
        if not isinstance(move_infos_raw, list) or not isinstance(root_raw, dict):
            self._invalidate_ollama_explanation(suppress_auto=True)
            return
        fingerprint = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if fingerprint != self._analysis_payload_fingerprint:
            self._invalidate_ollama_explanation()
            self._analysis_payload_fingerprint = fingerprint
        state = self.tree.nodes[node_id].state
        move_infos = select_recommended_candidates(move_infos_raw, state.to_play)
        self._displayed_analysis_payload = payload
        self._candidate_payloads = move_infos
        side_is_black = state.to_play is Color.BLACK
        overlays: list[tuple[Point, int, float]] = []
        self.candidate_table.setRowCount(len(move_infos))
        for row, info in enumerate(move_infos):
            move = str(info.get("move", "pass"))
            raw_winrate = _as_float(info.get("winrate"), 0.5)
            display_winrate = (raw_winrate if side_is_black else 1.0 - raw_winrate) * 100.0
            raw_score = _as_float(info.get("scoreLead", info.get("scoreMean", 0.0)))
            display_score = raw_score if side_is_black else -raw_score
            policy_probability = human_policy_probability(payload, move, state.size)
            human_prior = (
                "—" if policy_probability is None else f"{policy_probability * 100.0:.1f}%"
            )
            visits = int(_as_float(info.get("visits")))
            values = [
                move,
                human_prior,
                f"{display_winrate:.1f}%",
                f"{display_score:+.1f}",
                f"{visits:,}",
            ]
            for column, value in enumerate(values):
                self.candidate_table.setItem(row, column, QTableWidgetItem(value))
            point = gtp_to_point(move, state.size)
            if point is not None:
                overlays.append((point, row + 1, display_winrate))
        self.board_widget.set_candidates(overlays)
        ownership = self._ownership_values(payload)
        if ownership is not None:
            self._ownership_by_node[node_id] = ownership
        self._show_cached_ownership_for_current()

        root_winrate = black_winrate(self.tree, node_id, payload)
        if root_winrate is not None:
            self._analysis_by_node[node_id] = root_winrate
        self._redraw_winrate_plot()
        if move_infos:
            self._show_candidate_explanation(0)
        else:
            self._candidate_explanation = None
            self.explanation.clear()
            self._invalidate_ollama_explanation()

    def _analysis_finished(self, update: AnalysisUpdate) -> None:
        if update.request_id in self._ignored_analysis_requests:
            return
        if update.request_id == self._active_realtime_request_id:
            self._active_realtime_request_id = None
        if update.request_id == self._active_full_request_id:
            self._active_full_request_id = None
        if update.purpose == "ai_move":
            if update.node_id == self.tree.current_id:
                self._play_ai_move(update)
            return
        if update.purpose == "full_game":
            self._save_analysis_snapshot(
                update,
                cache_key=f"full-game-{self._full_analysis_visits}",
                max_visits=self._full_analysis_visits,
                include_ownership=False,
            )
            self._analysis_payload_by_node[update.node_id] = update.payload
            node_winrate = black_winrate(self.tree, update.node_id, update.payload)
            if node_winrate is not None:
                self._analysis_by_node[update.node_id] = node_winrate
            self._full_analysis_completed += 1
            self.full_analysis_progress.setValue(
                self._full_analysis_completed * self._full_analysis_visits
            )
            self.full_analysis_progress.setFormat(
                self._tr(
                    f"%p% · 已完成 {self._full_analysis_completed}/"
                    f"{self._full_analysis_total} 个局面",
                    f"%p% · Completed {self._full_analysis_completed}/{self._full_analysis_total} positions",
                )
            )
            if update.node_id == self.tree.current_id:
                self._display_analysis_payload(update.node_id, update.payload)
            else:
                self._redraw_winrate_plot()
            self._update_review_summary()
            self._start_next_full_game_position()
            return
        if update.purpose != "realtime":
            return
        self._save_analysis_snapshot(
            update,
            cache_key=(
                f"realtime-{self.analysis_settings.visits}-"
                f"{int(self.ownership_checkbox.isChecked())}"
            ),
            max_visits=self.analysis_settings.visits,
            include_ownership=self.ownership_checkbox.isChecked(),
        )
        self._analysis_payload_by_node[update.node_id] = update.payload
        if self.ownership_checkbox.isChecked():
            ownership = self._ownership_values(update.payload)
            if ownership is not None:
                self._ownership_by_node[update.node_id] = ownership
        if update.node_id == self.tree.current_id:
            self._update_ollama_controls()
            self._schedule_ollama_explanation()

    def _save_analysis_snapshot(
        self,
        update: AnalysisUpdate,
        *,
        cache_key: str,
        max_visits: int,
        include_ownership: bool,
    ) -> None:
        self.repository.save_analysis_snapshot(
            game_id=self.record.id,
            node_id=update.node_id,
            cache_key=cache_key,
            engine_version=(
                self.engine.runtime.engine_version if self.engine is not None else "unknown"
            ),
            model_hash=(
                self.engine.runtime.model_sha256 if self.engine is not None else "unknown"
            ),
            parameters={
                "maxVisits": max_visits,
                "includeOwnership": include_ownership,
                "difficulty": self.difficulty_combo.currentData(),
            },
            result=update.payload,
        )

    def _candidate_selected(self, row: int, _column: int) -> None:
        self._show_candidate_explanation(row)

    def _show_candidate_explanation(self, row: int) -> None:
        if (
            not (0 <= row < len(self._candidate_payloads))
            or self._displayed_analysis_payload is None
        ):
            return
        info = self._candidate_payloads[row]
        move = str(info.get("move", "pass"))
        same_candidate = (
            self._candidate_explanation is not None and move == self._candidate_explanation.move
        )
        if not same_candidate:
            self._invalidate_ollama_explanation()
        explanation = explain_candidate(
            self.tree.current.state,
            self._displayed_analysis_payload,
            info,
            rank=row + 1,
            language=self.language,
        )
        self._candidate_explanation = explanation
        rendered = explanation.render()
        if rendered != self.explanation.toPlainText():
            # Keep the reader's place when the same candidate gains new search evidence.
            scroll_bar = self.explanation.verticalScrollBar()
            scroll_position = scroll_bar.value() if same_candidate else 0
            self.explanation.setPlainText(rendered)
            scroll_bar.setValue(scroll_position)
        self._update_ollama_controls()
        self._schedule_ollama_explanation()

    def _engine_failure(self, failure: object) -> None:
        if not isinstance(failure, EngineFailure):
            return
        self._last_engine_failure = failure
        log_path = self._write_engine_diagnostic(failure)
        self._last_engine_diagnostic_path = log_path
        self._last_engine_error_message = None
        self._clear_analysis_display()
        if self._full_analysis_active:
            self.full_analysis_progress.setFormat(
                self._tr(
                    "分析已暂停 · 可重试或关闭分析", "Analysis paused · retry or close analysis"
                )
            )
        diagnostic = (
            self._tr(f" · 诊断已保存至 {log_path}", f" · diagnostic saved to {log_path}")
            if log_path is not None
            else ""
        )
        error = self._tr(
            f"KataGo错误：{failure.message}",
            f"KataGo error: {localize_error(failure.message, self.language)}",
        )
        self.engine_status.setText(error + diagnostic)
        self.statusBar().showMessage(error, 10000)
        self.engine_retry_button.setVisible(failure.recoverable)
        self.engine_close_analysis_button.show()

    def _write_engine_diagnostic(self, failure: EngineFailure) -> Path | None:
        path = self.repository.database_path.parent / "katago_engine_diagnostics.log"
        lines = [
            f"[{datetime.now().astimezone().isoformat(timespec='seconds')}]",
            f"kind={failure.kind}",
            f"message={failure.message}",
            f"request_id={failure.request_id or ''}",
            f"node_id={failure.node_id or ''}",
            f"purpose={failure.purpose or ''}",
        ]
        if failure.stderr_tail:
            lines.extend(("stderr:", failure.stderr_tail))
        try:
            with path.open("a", encoding="utf-8") as stream:
                stream.write("\n".join(lines) + "\n\n")
        except OSError:
            return None
        return path

    def _retry_engine_analysis(self) -> None:
        if self.engine is None:
            return
        request_id = self.engine.retry_last_request()
        if request_id is None:
            self.engine.restart()
            self.engine_status.setText(self._tr("KataGo：正在重新启动…", "KataGo: restarting…"))
        else:
            self.engine_status.setText(
                self._tr("KataGo：正在重试上次分析…", "KataGo: retrying the last analysis…")
            )
        self._last_engine_failure = None
        self._last_engine_diagnostic_path = None
        self._last_engine_error_message = None
        self.engine_retry_button.hide()
        self.engine_close_analysis_button.hide()

    def _close_failed_analysis(self) -> None:
        if self.engine is not None:
            self.engine.cancel_analysis()
        if self._full_analysis_active:
            self._stop_full_game_analysis(request_realtime=False)
        self.analysis_checkbox.blockSignals(True)
        self.analysis_checkbox.setChecked(False)
        self.analysis_checkbox.blockSignals(False)
        if self._is_battle_mode():
            self._review_mode_active = True
        self._last_engine_failure = None
        self._last_engine_diagnostic_path = None
        self._last_engine_error_message = None
        self.engine_retry_button.hide()
        self.engine_close_analysis_button.hide()
        self._refresh()
        self._clear_analysis_display()
        self.engine_status.setText(
            self._tr(
                "KataGo：分析已关闭，棋谱仍可浏览",
                "KataGo: analysis closed; game remains available",
            )
        )

    def _clear_analysis_display(self) -> None:
        self._candidate_explanation = None
        self._analysis_payload_fingerprint = None
        self._invalidate_ollama_explanation()
        self.board_widget.set_candidates([])
        self.board_widget.set_ownership(None)
        self._candidate_payloads = []
        self._displayed_analysis_payload = None
        self.explanation.clear()
        self._show_manual_candidate_placeholder()

    def _engine_error(self, message: str) -> None:
        self._last_engine_error_message = message
        if self._full_analysis_active:
            self._stop_full_game_analysis(request_realtime=False)
            self.full_analysis_progress.setFormat(
                self._tr(
                    "分析已停止 · 请查看上方错误", "Analysis stopped · see the error above"
                )
            )
        error = self._tr(
            f"KataGo错误：{message}", f"KataGo error: {localize_error(message, self.language)}"
        )
        self.engine_status.setText(error)
        self.statusBar().showMessage(error, 8000)

    def _current_winrate_series(self) -> tuple[list[int], list[float]]:
        move_numbers: list[int] = []
        winrates: list[float] = []
        nodes = (
            [self.tree.nodes[node_id] for node_id in self._review_line_ids]
            if self._review_mode_active or self._full_analysis_active
            else self.tree.path_to()
        )
        for node in nodes:
            winrate = self._analysis_by_node.get(node.id)
            if winrate is None:
                continue
            move_numbers.append(node.state.move_number)
            winrates.append(winrate)
        return move_numbers, winrates

    def _redraw_winrate_plot(self) -> None:
        move_numbers, winrates = self._current_winrate_series()
        self.winrate_curve.setData(move_numbers, winrates)
        self.winrate_cursor.hide()
        self.winrate_tooltip.hide()
        x_max = (
            self.tree.nodes[self._review_line_ids[-1]].state.move_number
            if self._review_mode_active and self._review_line_ids
            else self.tree.current.state.move_number
        )
        full_x_span = max(10.0, float(x_max))
        horizontal_zoom = self._zoom_factor(self.winrate_horizontal_zoom.currentText())
        visible_x_span = max(10.0, full_x_span / horizontal_zoom)
        current_move = float(self.tree.current.state.move_number)
        x_min = max(
            0.0,
            min(current_move - visible_x_span / 2.0, full_x_span - visible_x_span),
        )
        self.winrate_plot.setXRange(
            x_min,
            x_min + visible_x_span,
            padding=0.02,
        )
        vertical_zoom = self._zoom_factor(self.winrate_vertical_zoom.currentText())
        visible_y_span = 100.0 / vertical_zoom
        focus_winrate = self._analysis_by_node.get(self.tree.current_id)
        if focus_winrate is None:
            focus_winrate = winrates[-1] if winrates else 50.0
        y_min = max(
            0.0,
            min(focus_winrate - visible_y_span / 2.0, 100.0 - visible_y_span),
        )
        self.winrate_plot.setYRange(y_min, y_min + visible_y_span, padding=0.02)

    @staticmethod
    def _zoom_factor(label: str) -> float:
        try:
            return max(1.0, float(label.rstrip("×")))
        except ValueError:
            return 1.0

    def _winrate_zoom_changed(self, _value: str) -> None:
        self._redraw_winrate_plot()

    def _reset_winrate_zoom(self) -> None:
        self.winrate_horizontal_zoom.setCurrentText("1×")
        self.winrate_vertical_zoom.setCurrentText("1×")
        self._redraw_winrate_plot()

    def _nearest_winrate(self, x_position: float) -> tuple[int, float] | None:
        move_numbers, winrates = self._current_winrate_series()
        if not move_numbers:
            return None
        index = min(
            range(len(move_numbers)),
            key=lambda candidate: abs(move_numbers[candidate] - x_position),
        )
        return move_numbers[index], winrates[index]

    def _winrate_mouse_moved(self, event: tuple[object, ...]) -> None:
        if not event or not isinstance(event[0], QPointF):
            return
        scene_position = event[0]
        if not self.winrate_plot.sceneBoundingRect().contains(scene_position):
            self.winrate_cursor.hide()
            self.winrate_tooltip.hide()
            return
        view_position = self.winrate_plot.plotItem.vb.mapSceneToView(scene_position)
        nearest = self._nearest_winrate(view_position.x())
        if nearest is None:
            self.winrate_cursor.hide()
            self.winrate_tooltip.hide()
            return
        move_number, winrate = nearest
        self.winrate_cursor.setPos(move_number)
        self.winrate_cursor.show()
        self.winrate_tooltip.setText(
            self._tr(
                f"第 {move_number} 手\n黑胜率 {winrate:.1f}%",
                f"Move {move_number}\nBlack win rate {winrate:.1f}%",
            )
        )
        self.winrate_tooltip.setPos(move_number, winrate)
        self.winrate_tooltip.show()

    def _is_battle_mode(self) -> bool:
        return self.mode_combo.currentData() in {"fair", "assisted"}

    @staticmethod
    def _is_unfinished_battle_record(record: GameRecord) -> bool:
        return record.status != "completed" and record.mode in {"fair", "assisted"}

    def _human_color_name(self) -> str:
        return str(self.human_color_combo.currentData())

    def _human_color(self) -> Color:
        return Color.WHITE if self.record.human_color == "white" else Color.BLACK

    def _ai_color(self) -> Color:
        return self._human_color().opponent

    def _is_ai_turn(self) -> bool:
        state = self.tree.current.state
        return (
            self.record.status != "completed"
            and not self._review_mode_active
            and self._is_battle_mode()
            and state.to_play is self._ai_color()
            and (not state.is_game_over or self._resume_after_scoring)
        )

    def _human_color_changed(self, _label: str) -> None:
        human_color = self._human_color_name()
        self.repository.update_human_color(self.record.id, human_color)
        self.record = replace(self.record, human_color=human_color)
        if self.engine is not None:
            self.engine.stop_analysis()
        self._apply_mode_controls()
        self._refresh()
        self._request_analysis()

    def _mode_changed(self, label: str) -> None:
        mode = str(self.mode_combo.currentData())
        self.repository.update_mode(self.record.id, mode)
        self.record = replace(self.record, mode=mode)
        if self.engine is not None:
            self.engine.stop_analysis()
        self._apply_mode_controls()
        self._refresh()
        self._request_analysis()

    def _difficulty_changed(self, label: str) -> None:
        difficulty = str(self.difficulty_combo.currentData())
        if difficulty not in PRESETS:
            return
        self._invalidate_ollama_explanation()
        self.repository.update_difficulty(self.record.id, difficulty)
        self.record = replace(self.record, difficulty=difficulty)
        if self.engine is not None:
            self.engine.stop_analysis()
        self._request_analysis()

    def _apply_mode_controls(self) -> None:
        fair = self.mode_combo.currentData() == "fair"
        if fair:
            self._invalidate_ollama_explanation()
            self.analysis_checkbox.setChecked(False)
        self.mode_combo.setEnabled(not self._full_analysis_active)
        self.difficulty_combo.setEnabled(not self._full_analysis_active)
        self.human_color_combo.setEnabled(
            self._is_battle_mode() and not self._full_analysis_active
        )
        self.analysis_checkbox.setEnabled(not fair and not self._full_analysis_active)
        self.ownership_checkbox.setEnabled(not fair and not self._full_analysis_active)
        if self._is_battle_mode():
            human = (
                self._tr("黑", "Black")
                if self._human_color() is Color.BLACK
                else self._tr("白", "White")
            )
            ai = (
                self._tr("白", "White")
                if self._ai_color() is Color.WHITE
                else self._tr("黑", "Black")
            )
            self.statusBar().showMessage(
                self._tr(
                    f"对战模式：你执{human}，本地 AI 执{ai}",
                    f"Play mode: you play {human}; local AI plays {ai}",
                )
            )

    def _request_ai_move(self) -> None:
        if self.engine is None:
            self.engine_status.setText(
                self._tr(
                    "KataGo：运行配置不可用，AI 无法落子",
                    "KataGo: runtime unavailable; AI cannot play",
                )
            )
            return
        preset = PRESETS[str(self.difficulty_combo.currentData())]
        self.engine.analyze(
            tree=self.tree,
            node_id=self.tree.current_id,
            rules=self.record.rules,
            komi=self.record.komi,
            max_visits=preset.max_visits,
            human_profile=preset.human_profile,
            include_ownership=False,
            purpose="ai_move",
        )
        self.engine_status.setText(
            self._tr(
                f"KataGo：{preset.label} AI 正在思考（{preset.human_profile}）",
                f"KataGo: {self._difficulty_label(preset.label)} AI is thinking ({preset.human_profile})",
            )
        )

    def _play_ai_move(self, update: AnalysisUpdate) -> None:
        if not self._is_ai_turn() or update.node_id != self.tree.current_id:
            return
        preset = PRESETS[str(self.difficulty_combo.currentData())]
        node_seed = int(update.node_id.replace("-", "")[:16], 16)
        selection = select_ai_move(
            update.payload,
            self.tree.current.state,
            preset,
            random_seed=self.record.random_seed ^ node_seed,
        )
        before = self.tree.current.state
        try:
            node, _created = self.tree.play(selection.point)
        except IllegalMove as exc:
            self._engine_error(self._tr(f"AI候选手非法：{exc}", f"Illegal AI candidate: {exc}"))
            return
        self.repository.save_node(self.record.id, node)
        self._set_review_line_from_current()
        self._resume_after_scoring = False
        if selection.point is not None:
            captured = (
                node.state.black_captures + node.state.white_captures
                > before.black_captures + before.white_captures
            )
            self.audio_feedback.play_move(captured=captured)
        source_text = {
            "human-policy": self._tr("人类棋风概率抽样", "human-style sampling"),
            "objective": self._tr("主模型最佳手", "main-model best move"),
            "searched-pass": self._tr("主模型判断应停一手", "main model chose to pass"),
            "fallback-objective": self._tr("主模型后备候选", "main-model fallback candidate"),
        }.get(selection.source, selection.source)
        self._refresh()
        self.statusBar().showMessage(
            self._tr(
                f"AI 已落子 · {preset.label} · {source_text}",
                f"AI played · {self._difficulty_label(preset.label)} · {source_text}",
            ),
            5000,
        )
        if node.state.is_game_over:
            QTimer.singleShot(0, self._open_scoring)
        else:
            self._request_analysis()

    def _open_scoring(self) -> None:
        if self.record.status == "completed":
            self._show_completed_result()
            return
        self._stop_full_game_analysis(request_realtime=False)
        if self.engine is not None:
            self.engine.stop_analysis()
        last_move = None if self.tree.current.move is None else self.tree.current.move.point
        dialog = ScoringDialog(
            self.tree.current.state,
            rules=self.record.rules,
            komi=self.record.komi,
            last_move=last_move,
            language=self.language,
            parent=self,
        )
        dialog.exec()
        score = dialog.confirmed_score
        if score is None:
            self._resume_after_scoring = self.tree.current.state.is_game_over
            self._refresh()
            self._request_analysis()
            return
        self._finish_game(score.sgf_result)
        if dialog.action == "new":
            self._new_game()
        else:
            self._refresh()

    def _resign(self) -> None:
        if self.record.status == "completed":
            self._show_completed_result()
            return
        self._stop_full_game_analysis(request_realtime=False)
        resigning = (
            self._human_color() if self._is_battle_mode() else self.tree.current.state.to_play
        )
        resigning_name = (
            self._tr("黑方", "Black") if resigning is Color.BLACK else self._tr("白方", "White")
        )
        choice = QMessageBox.question(
            self,
            self._tr("确认认输", "Confirm resignation"),
            self._tr(
                f"确认{resigning_name}认输并结束这一盘棋吗？",
                f"Resign as {resigning_name} and end this game?",
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        winner = resigning.opponent
        result = "B+R" if winner is Color.BLACK else "W+R"
        self._finish_game(result)
        self._show_completed_result()

    def _finish_game(self, result: str) -> None:
        if self.engine is not None:
            self.engine.stop_analysis()
        self.repository.finish_game(self.record.id, result)
        self._resume_after_scoring = False
        self.record = replace(
            self.record,
            status="completed",
            result=result,
        )
        self._refresh()

    def _show_completed_result(self) -> None:
        dialog = CompletedGameDialog(
            format_result(self.record.result, language=self.language),
            self,
            language=self.language,
        )
        dialog.exec()
        if dialog.action == "new":
            self._new_game()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 - Qt API name
        super().showEvent(event)
        if not self._startup_resume_pending:
            return
        self._startup_resume_pending = False
        QTimer.singleShot(0, self._resolve_startup_unfinished_game)

    def _resolve_startup_unfinished_game(self) -> None:
        action = self._choose_unfinished_game_action(self.record)
        self._review_mode_active = action != "continue"
        self._refresh()
        if action == "continue":
            self.statusBar().showMessage(
                self._tr("已恢复未完成对局", "Unfinished game resumed"), 5000
            )
            self._request_analysis()
        elif action == "review":
            self.statusBar().showMessage(
                self._tr(
                    "已按仅复盘方式打开未完成对局", "Unfinished game opened for review only"
                ),
                5000,
            )
            self._request_analysis()
        else:
            self.statusBar().showMessage(
                self._tr(
                    "未完成对局保持暂停；可从棋谱库重新选择打开方式",
                    "Unfinished game remains paused; reopen it from the library to choose how to continue",
                ),
                6000,
            )

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._ollama_closed:
            event.accept()
            return
        self._ollama_closed = True
        self._invalidate_ollama_explanation()
        self.ollama_client.shutdown()
        try:
            if self.engine is not None:
                self.engine.shutdown()
            self.repository.set_current(self.record.id, self.tree.current_id)
            self.repository.close()
        except Exception as exc:  # pragma: no cover - last-chance user warning
            QMessageBox.warning(
                self,
                self._tr("保存提示", "Save warning"),
                self._tr(
                    f"关闭前保存棋谱时发生错误：{exc}",
                    f"Could not save the game before closing: {exc}",
                ),
            )
        event.accept()
