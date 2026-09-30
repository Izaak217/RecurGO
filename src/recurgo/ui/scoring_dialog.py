"""v1.0.1.dev1: review the existing live ownership map, without reanalysis."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from recurgo.domain import BoardState, ChineseScore, Color, Point, connected_group
from recurgo.domain.score_review import (
    UNASSIGNED,
    assigned_dead,
    count_assignments,
    live_assignments,
    score_ownership,
    validate_assignments,
)
from recurgo.i18n import Language, tr

from .board_widget import BoardWidget
from .formatting import format_rules_and_komi


def _score_result(score: ChineseScore, language: Language) -> str:
    if language != "en":
        return score.display_result
    if score.winner is None:
        return "Draw"
    winner = "Black" if score.winner is Color.BLACK else "White"
    return f"{winner} wins by {score.winning_margin_stones:g} stones"


class ScoringDialog(QDialog):
    def __init__(
        self,
        state: BoardState,
        *,
        rules: str,
        komi: float,
        last_move: Point | None,
        language: Language = "en",
        initial_ownership: list[float] | None = None,
        confirmed_ownership: tuple[int, ...] | None = None,
        initial_dead_points: frozenset[Point] = frozenset(),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.state, self.rules, self.komi, self.language = state, rules, komi, language
        self.confirmed_score: ChineseScore | None = None
        self.action = "continue"
        self._closed = False
        self._explicit_dead = initial_dead_points
        initial = (
            validate_assignments(confirmed_ownership, state.size)
            if confirmed_ownership is not None
            else live_assignments(initial_ownership, state.size)
        )
        self._base_ownership = initial or (UNASSIGNED,) * (state.size * state.size)
        self._overrides: dict[int, int] = {}
        self.setWindowTitle(
            tr(language, "结束对局 · 中国规则数子", "Finish game · Chinese area scoring")
        )
        self.resize(1100, 760)
        layout = QHBoxLayout(self)
        self.board = BoardWidget()
        self.board.setMinimumSize(640, 640)
        self.board.set_position(state, last_move)
        self.board.set_scoring_mode(True, edit_ownership=True)
        self.board.score_point_clicked.connect(self._edit_point)
        layout.addWidget(self.board, 1)
        side = QFrame()
        side.setMinimumWidth(330)
        panel = QVBoxLayout(side)
        title = QLabel(tr(language, "核对数子结果", "Review the score"))
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        panel.addWidget(title)
        self.instructions = QLabel(
            tr(
                language,
                "使用当前局面的实时领地数据。用户可修改黑白归属、指定双方共有空点，"
                "或整块标记和恢复死子。最终以用户确认的结果为准。",
                "Uses this position’s live territory data. Users can adjust ownership, "
                "assign shared points, and mark or restore dead groups. "
                "Users’ confirmed decisions take priority.",
            )
        )
        self.instructions.setWordWrap(True)
        panel.addWidget(self.instructions)
        self.source_label = QLabel(
            tr(
                language,
                "已载入当前局面的实时领地。"
                if initial is not None
                else "当前局面暂无实时领地；可返回棋局开启领地分析，或手动指定。",
                "Loaded this position’s live territory."
                if initial is not None
                else "No live territory for this position. Return to the game to enable "
                "territory analysis, or assign points manually.",
            )
        )
        self.source_label.setWordWrap(True)
        panel.addWidget(self.source_label)
        self.brush_combo = QComboBox()
        for zh, en, value in (
            ("点击循环", "Click to cycle", None),
            ("归黑方", "Assign Black", 1),
            ("归白方", "Assign White", -1),
            ("双方各半", "Shared: half each", 0),
            ("待确认", "Unassigned", UNASSIGNED),
            ("标记／恢复整块死子", "Toggle dead group", "dead"),
        ):
            self.brush_combo.addItem(tr(language, zh, en), value)
        panel.addWidget(self.brush_combo)
        self.show_dead_checkbox = QCheckBox(tr(language, "显示死子", "Show dead stones"))
        self.show_dead_checkbox.setToolTip(
            tr(
                language,
                "淡化显示死子的原位置，不改变计分。",
                "Shows faded dead stones at their original positions. Scoring is unchanged.",
            )
        )
        self.show_dead_checkbox.toggled.connect(self.board.set_show_dead_stones)
        panel.addWidget(self.show_dead_checkbox)
        self.reset_button = QPushButton(
            tr(language, "撤销全部点位修改", "Undo all point corrections")
        )
        self.reset_button.clicked.connect(self._reset_points)
        panel.addWidget(self.reset_button)
        self.score_label = QLabel()
        self.score_label.setWordWrap(True)
        self.score_label.setStyleSheet("font-size: 16px; padding: 10px;")
        panel.addWidget(self.score_label)
        notice = QLabel(
            tr(
                language,
                "黑白各半方块表示共有，每方计半子；空心小方框表示待确认。"
                "未显示归属的点不会自动按双方共有计算。",
                "Split squares are shared, half a stone for each side. Small hollow "
                "squares need assignment; missing ownership is not automatically shared.",
            )
        )
        notice.setWordWrap(True)
        panel.addWidget(notice)
        panel.addStretch(1)
        self.confirm_button = QPushButton(
            tr(language, "确认数子结果并结束对局", "Confirm score and finish game")
        )
        self.confirm_button.clicked.connect(self._confirm)
        panel.addWidget(self.confirm_button)
        self.continue_button = QPushButton(tr(language, "返回棋局继续下", "Return to game"))
        self.continue_button.clicked.connect(self.reject)
        panel.addWidget(self.continue_button)
        self.stay_button = QPushButton(
            tr(language, "关闭结果界面，停留在当前棋局", "Close result and stay in this game")
        )
        self.stay_button.clicked.connect(self._stay)
        self.stay_button.hide()
        panel.addWidget(self.stay_button)
        self.new_game_button = QPushButton(tr(language, "新一盘棋", "New game"))
        self.new_game_button.clicked.connect(self._new_game)
        self.new_game_button.hide()
        panel.addWidget(self.new_game_button)
        layout.addWidget(side)
        self._update_score()

    @property
    def ownership(self) -> tuple[int, ...]:
        return tuple(self._overrides.get(i, v) for i, v in enumerate(self._base_ownership))

    @property
    def dead_points(self) -> frozenset[Point]:
        return assigned_dead(self.state, self.ownership) | self._explicit_dead

    def _edit_point(self, x: int, y: int) -> None:
        if self._closed or not (0 <= x < self.state.size and 0 <= y < self.state.size):
            return
        brush = self.brush_combo.currentData()
        if brush == "dead":
            self._toggle_dead_group(x, y)
            return
        index = y * self.state.size + x
        self._explicit_dead = self._explicit_dead.difference({Point(x, y)})
        self._overrides[index] = (
            {UNASSIGNED: 1, 1: -1, -1: 0, 0: UNASSIGNED}[self.ownership[index]]
            if brush is None
            else int(brush)
        )
        self._update_score()

    def _toggle_dead_group(self, x: int, y: int) -> None:
        if self._closed or not (0 <= x < self.state.size and 0 <= y < self.state.size):
            return
        group = connected_group(self.state, Point(x, y))
        restore = group.issubset(self.dead_points)
        self._explicit_dead = self._explicit_dead.difference(group)
        for point in group:
            owner = 1 if self.state.stone_at(point) is Color.BLACK else -1
            self._overrides[point.y * self.state.size + point.x] = owner if restore else -owner
        self._update_score()

    def _reset_points(self) -> None:
        if not self._closed:
            self._overrides.clear()
            self._explicit_dead = frozenset()
            self._update_score()

    def _update_score(self) -> None:
        owners = self.ownership
        self.board.set_ownership([float(v) if v in (-1, 1) else 0.0 for v in owners])
        self.board.set_scoring_assignments(owners)
        self.board.set_scoring_mode(True, self.dead_points, edit_ownership=True)
        self.reset_button.setEnabled(bool(self._overrides) and not self._closed)
        pending = owners.count(UNASSIGNED)
        supported = self.rules.lower() in {"chinese", "chinese-ogs"}
        self.confirm_button.setEnabled(not pending and supported and not self._closed)
        try:
            score = count_assignments(
                self.state, owners, komi=self.komi, dead_points=self._explicit_dead
            )
        except ValueError:
            self.confirm_button.setEnabled(False)
            self.score_label.setText(
                tr(
                    self.language,
                    "计分数据或贴目无效，请返回检查棋局。",
                    "Invalid scoring data or komi; return and check the game.",
                )
            )
            return
        rules = format_rules_and_komi(self.rules, self.komi, language=self.language)
        result = (
            _score_result(score, self.language)
            if not pending
            else tr(self.language, "请补齐待确认点。", "Assign the remaining points.")
        )
        if not supported:
            result = tr(self.language, "此计分器仅支持中国规则。", "Chinese rules only.")
        self.score_label.setText(
            tr(
                self.language,
                f"{rules}\n\n黑方：{score.black_area:g} 子\n白方：{score.white_area:g} 子\n"
                f"共有空点：{score.neutral_points}（已各分一半）\n待确认：{pending} 点\n"
                f"手动修改：{len(self._overrides)} 点\n\n按当前归属：{result}",
                f"{rules}\n\nBlack area: {score.black_area:g}\n"
                f"White area: {score.white_area:g}\n"
                f"Shared points: {score.neutral_points} (half each included)\n"
                f"Unassigned: {pending}\n"
                f"Edited points: {len(self._overrides)}\n\nFrom current assignments: {result}",
            )
        )

    def done(self, result: int) -> None:
        self._closed = True
        super().done(result)

    def _confirm(self) -> None:
        if self._closed or not self.confirm_button.isEnabled():
            return
        self.confirmed_score = score_ownership(
            self.state, self.ownership, komi=self.komi, dead_points=self._explicit_dead
        )
        self._closed = True
        self.board.set_input_enabled(False)
        self.brush_combo.setEnabled(False)
        self.reset_button.setEnabled(False)
        self.setWindowTitle(tr(self.language, "对局结束", "Game over"))
        self.instructions.setText(
            tr(
                self.language,
                "已确认数子结果，关闭后保存到棋谱库。",
                "Score confirmed. Close this result to save to the game library.",
            )
        )
        self.confirm_button.hide()
        self.continue_button.hide()
        self.stay_button.show()
        self.new_game_button.show()

    def _stay(self) -> None:
        self.action = "stay"
        self.accept()

    def _new_game(self) -> None:
        self.action = "new"
        self.accept()


class CompletedGameDialog(QDialog):
    def __init__(
        self,
        result_text: str,
        parent: QWidget | None = None,
        *,
        language: Language = "en",
    ) -> None:
        super().__init__(parent)
        self.action = "stay"
        self.setWindowTitle(tr(language, "对局结束", "Game over"))
        self.resize(460, 260)
        layout = QVBoxLayout(self)
        title = QLabel(result_text)
        title.setStyleSheet("font-size: 28px; font-weight: 700;")
        layout.addWidget(title)
        detail = QLabel(
            tr(
                language,
                "结果已自动保存到棋谱库，导出 SGF 时也会保留。",
                "The result was saved in the game library and will be retained "
                "in exported SGF.",
            )
        )
        detail.setWordWrap(True)
        layout.addWidget(detail)
        layout.addStretch(1)
        stay_button = QPushButton(
            tr(language, "关闭结果界面，停留在当前棋局", "Close result and stay in this game")
        )
        stay_button.clicked.connect(self.accept)
        layout.addWidget(stay_button)
        new_button = QPushButton(tr(language, "新一盘棋", "New game"))
        new_button.clicked.connect(self._new_game)
        layout.addWidget(new_button)

    def _new_game(self) -> None:
        self.action = "new"
        self.accept()
