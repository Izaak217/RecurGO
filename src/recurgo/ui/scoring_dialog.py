"""v1.0.1: review final-position ownership under Chinese area-scoring rules."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from recurgo.domain import BoardState, ChineseScore, Color, GameTree, Point, connected_group
from recurgo.domain.scoring_estimate import (
    UNSETTLED,
    count_assignments,
    inferred_dead,
    prepare_proposal,
    score_ownership,
    scoring_issues,
    validate_assignments,
)
from recurgo.engine import AnalysisUpdate, EngineFailure, KataGoEngine
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
        engine: KataGoEngine | None = None,
        tree: GameTree | None = None,
        max_visits: int = 800,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.state, self.language, self.rules, self.komi = state, language, rules, komi
        self.confirmed_score: ChineseScore | None = None
        self.action = "continue"
        self._engine = engine if tree is not None else None
        self._tree = tree
        self._node_id = tree.current_id if tree is not None else None
        self._max_visits = max_visits
        self._request_id: str | None = None
        self._closed = False
        self._explicit_dead = initial_dead_points
        self._analysis_pending = self._engine is not None and confirmed_ownership is None
        initial = (
            validate_assignments(confirmed_ownership, state.size)
            if confirmed_ownership is not None
            else prepare_proposal(state, initial_ownership)
        )
        self._has_map = initial is not None
        self._base_ownership = initial or tuple(
            1 if v == int(Color.BLACK) else -1 if v == int(Color.WHITE) else UNSETTLED
            for v in state.stones
        )
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
        side_layout = QVBoxLayout(side)
        title = QLabel(tr(language, "核对数子结果", "Review the score"))
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        side_layout.addWidget(title)
        self.instructions = QLabel(
            tr(
                language,
                "结合 KataGo 和棋形给出数子建议。用户可逐点设为归黑方、归白方、"
                "双方各半或待确认，也可整块标记死子。手动修改优先，重新分析时保留。",
                "KataGo analysis and board shapes provide an initial scoring suggestion. "
                "Users can assign points to Black, White, shared or unresolved, "
                "and mark dead groups. Manual decisions take priority and survive refreshes.",
            )
        )
        self.instructions.setWordWrap(True)
        side_layout.addWidget(self.instructions)
        self.source_label = QLabel(
            tr(
                language,
                "已载入当前局面的领地估算，供核对。"
                if self._has_map
                else "暂无 AI 领地；可获取分析或手动指定。",
                "Loaded this position's territory estimate for review."
                if self._has_map
                else "No AI ownership yet; request analysis or assign points manually.",
            )
        )
        self.source_label.setWordWrap(True)
        side_layout.addWidget(self.source_label)
        self.brush_combo = QComboBox()
        for zh, en, value in (
            ("点击循环", "Click to cycle", None),
            ("归黑方", "Assign Black", 1),
            ("归白方", "Assign White", -1),
            ("双方各半", "Shared: half each", 0),
            ("待确认", "Unresolved", UNSETTLED),
            ("标记／恢复整块死子", "Toggle dead group", "dead"),
        ):
            self.brush_combo.addItem(tr(language, zh, en), value)
        side_layout.addWidget(self.brush_combo)
        self.refresh_button = QPushButton(
            tr(language, "重新分析数子", "Analyze score again")
        )
        self.refresh_button.setToolTip(
            tr(language, "保留用户手动修改的点位。", "Preserves users' manual corrections.")
        )
        self.refresh_button.setEnabled(self._engine is not None)
        self.refresh_button.clicked.connect(self._request_estimate)
        side_layout.addWidget(self.refresh_button)
        self.reset_button = QPushButton(
            tr(language, "撤销全部点位修改", "Undo all point corrections")
        )
        self.reset_button.clicked.connect(self._reset_points)
        side_layout.addWidget(self.reset_button)
        self.score_label = QLabel()
        self.score_label.setWordWrap(True)
        self.score_label.setStyleSheet("font-size: 16px; padding: 10px;")
        side_layout.addWidget(self.score_label)
        notice = QLabel(
            tr(
                language,
                "黑白各半方块表示共有，橙色问号表示待确认。共有空点每方计 ½ 子。"
                "AI 不确定不等于双方各半。",
                "Split squares are shared; orange ? marks are unresolved. "
                "Each shared empty point adds half a stone to each side. "
                "AI uncertainty is not proof of shared ownership.",
            )
        )
        notice.setWordWrap(True)
        side_layout.addWidget(notice)
        side_layout.addStretch(1)
        self.confirm_button = QPushButton(
            tr(language, "确认数子结果并结束对局", "Confirm score and finish game")
        )
        self.confirm_button.clicked.connect(self._confirm)
        side_layout.addWidget(self.confirm_button)
        self.continue_button = QPushButton(tr(language, "返回棋局继续下", "Return to game"))
        self.continue_button.clicked.connect(self.reject)
        side_layout.addWidget(self.continue_button)
        self.stay_button = QPushButton(
            tr(language, "关闭结果界面，停留在当前棋局", "Close result and stay in this game")
        )
        self.stay_button.clicked.connect(self._stay)
        self.stay_button.hide()
        side_layout.addWidget(self.stay_button)
        self.new_game_button = QPushButton(tr(language, "新一盘棋", "New game"))
        self.new_game_button.clicked.connect(self._new_game)
        self.new_game_button.hide()
        side_layout.addWidget(self.new_game_button)
        layout.addWidget(side)
        self._update_score()
        if self._engine is not None:
            self._engine.analysis_updated.connect(self._estimate_update)
            self._engine.analysis_finished.connect(self._estimate_update)
            self._engine.failure_reported.connect(self._estimate_failure)
            if confirmed_ownership is None:
                QTimer.singleShot(0, self._request_estimate)

    @property
    def ownership(self) -> tuple[int, ...]:
        return tuple(self._overrides.get(i, v) for i, v in enumerate(self._base_ownership))

    @property
    def dead_points(self) -> frozenset[Point]:
        return self._explicit_dead | inferred_dead(self.state, self.ownership)

    def _edit_point(self, x: int, y: int) -> None:
        if self._closed or not (0 <= x < self.state.size and 0 <= y < self.state.size):
            return
        index = y * self.state.size + x
        brush = self.brush_combo.currentData()
        if brush == "dead":
            group = connected_group(self.state, Point(x, y))
            if not group:
                return
            if group.issubset(self.dead_points):
                self._explicit_dead = self._explicit_dead.difference(group)
                for point in group:
                    self._overrides[point.y * self.state.size + point.x] = (
                        1 if self.state.stone_at(point) is Color.BLACK else -1
                    )
            else:
                self._explicit_dead = self._explicit_dead.union(group)
                for point in group:
                    self._overrides[point.y * self.state.size + point.x] = UNSETTLED
            self._update_score()
            return
        self._overrides[index] = (
            {UNSETTLED: 1, 1: -1, -1: 0, 0: UNSETTLED}[self.ownership[index]]
            if brush is None
            else int(brush)
        )
        self._update_score()

    def _reset_points(self) -> None:
        if not self._closed:
            self._overrides.clear()
            self._explicit_dead = frozenset()
            self._update_score()

    def _update_score(self) -> None:
        self.board.set_ownership([float(v) if v in (-1, 1) else 0.0 for v in self.ownership])
        self.board.set_scoring_assignments(self.ownership)
        self.board.set_scoring_mode(True, self.dead_points, edit_ownership=True)
        issues = scoring_issues(self.state, self.ownership, self._explicit_dead)
        pending = self.ownership.count(UNSETTLED)
        self.board.set_attention_points(issues)
        available = self._has_map or bool(self._overrides)
        supported = self.rules.lower() in {"chinese", "chinese-ogs"}
        self.confirm_button.setEnabled(
            available
            and not pending
            and not self._analysis_pending
            and not self._closed
            and supported
        )
        self.reset_button.setEnabled(bool(self._overrides) and not self._closed)
        if not available:
            self.score_label.setText(
                tr(
                    self.language,
                    "等待领地数据，尚未计分。",
                    "Waiting for ownership; no score yet.",
                )
            )
            return
        try:
            score = count_assignments(
                self.state, self.ownership, komi=self.komi, dead_points=self._explicit_dead
            )
        except ValueError:
            self.confirm_button.setEnabled(False)
            self.score_label.setText(
                tr(
                    self.language,
                    "计分数据或贴目无效，请返回并检查棋局。贴目须为整数或半整数。",
                    "Invalid scoring data or komi; return and check the game. "
                    "Komi must be a finite whole or half point.",
                )
            )
            return
        rules = format_rules_and_komi(self.rules, self.komi, language=self.language)
        result = (
            _score_result(score, self.language)
            if not pending
            else tr(
                self.language,
                "还有待确认点，暂不判胜负。",
                "Resolve the remaining points before scoring.",
            )
        )
        if not supported:
            result = tr(
                self.language,
                "此计分器仅支持中国规则。",
                "This scorer supports Chinese rules only.",
            )
        self.score_label.setText(
            tr(
                self.language,
                f"{rules}\n\n黑方：{score.black_area:g} 子\n白方：{score.white_area:g} 子\n"
                f"共有空点：{score.neutral_points}（已各分一半）\n"
                f"待确认：{pending} 点\n"
                f"死活判断提示：{len(issues) - pending} 点（以手动修改为准）\n"
                f"手动修改：{len(self._overrides)} 点\n\n按当前归属：{result}",
                f"{rules}\n\nBlack area: {score.black_area:g}\n"
                f"White area: {score.white_area:g}\n"
                f"Shared points: {score.neutral_points} (half each included)\n"
                f"Unresolved: {pending}\n"
                f"Group-status notices: {len(issues) - pending} (manual decisions prevail)\n"
                f"Edited points: {len(self._overrides)}\n\n"
                f"From current assignments: {result}",
            )
        )

    def _request_estimate(self) -> None:
        if self._closed or self._engine is None or self._tree is None or self._node_id is None:
            return
        self._request_id = None
        self._analysis_pending = True
        self._update_score()
        self.refresh_button.setEnabled(False)
        self.source_label.setText(
            tr(
                self.language,
                "正在获取当前局面领地；保留手动修改…",
                "Analyzing territory; preserving manual corrections…",
            )
        )
        self._request_id = self._engine.analyze(
            tree=self._tree,
            node_id=self._node_id,
            rules=self.rules,
            komi=self.komi,
            max_visits=self._max_visits,
            human_profile=None,
            include_ownership=True,
            include_ownership_stdev=True,
            purpose="scoring",
        )

    def _estimate_update(self, update: AnalysisUpdate) -> None:
        if (
            self._closed
            or self._request_id is None
            or update.request_id != self._request_id
            or update.node_id != self._node_id
            or update.purpose != "scoring"
        ):
            return
        if not update.is_final:
            return
        points = prepare_proposal(
            self.state, update.payload.get("ownership"), update.payload.get("ownershipStdev")
        )
        if points is None:
            self._estimate_unavailable()
            return
        self._request_id = None
        self._analysis_pending = False
        self._base_ownership = points
        self._has_map = True
        self.refresh_button.setEnabled(True)
        self.source_label.setText(
            tr(
                self.language,
                "数子建议已更新；用户手动修改已保留。",
                "Scoring suggestion updated; manual corrections are preserved.",
            )
        )
        self._update_score()

    def _estimate_unavailable(self) -> None:
        self._request_id = None
        self._analysis_pending = False
        self.refresh_button.setEnabled(True)
        self.source_label.setText(
            tr(
                self.language,
                "领地获取失败；保留当前归属和手动修改，可重试。",
                "Ownership request failed. Assignments and corrections are preserved; "
                "retry is available.",
            )
        )

        self._update_score()

    def _estimate_failure(self, failure: object) -> None:
        if self._closed or self._request_id is None or not isinstance(failure, EngineFailure):
            return
        if failure.request_id in (None, self._request_id):
            self._estimate_unavailable()

    def _stop_estimate(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._engine is not None:
            self._engine.analysis_updated.disconnect(self._estimate_update)
            self._engine.analysis_finished.disconnect(self._estimate_update)
            self._engine.failure_reported.disconnect(self._estimate_failure)
            if self._request_id is not None:
                self._request_id = None
                self._engine.stop_analysis()

    def done(self, result: int) -> None:
        self._stop_estimate()
        super().done(result)

    def _confirm(self) -> None:
        if self._closed or not self.confirm_button.isEnabled():
            return
        self.confirmed_score = score_ownership(
            self.state,
            self.ownership,
            komi=self.komi,
            dead_points=self._explicit_dead,
        )
        self._stop_estimate()
        self._update_score()
        self.board.set_input_enabled(False)
        self.brush_combo.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.setWindowTitle(tr(self.language, "对局结束", "Game over"))
        self.instructions.setText(
            tr(
                self.language,
                "已确认数子结果。关闭结果界面后保存到棋谱库。",
                "Score confirmed. "
                "Close this result to save to the game library.",
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
                "The result is saved in the game library and retained in exported SGF.",
            )
        )
        detail.setWordWrap(True)
        layout.addWidget(detail)
        layout.addStretch(1)
        stay = QPushButton(
            tr(language, "关闭结果界面，停留在当前棋局", "Close result and stay in this game")
        )
        stay.clicked.connect(self.accept)
        layout.addWidget(stay)
        new = QPushButton(tr(language, "新一盘棋", "New game"))
        new.clicked.connect(self._new_game)
        layout.addWidget(new)

    def _new_game(self) -> None:
        self.action = "new"
        self.accept()
