"""Interactive Chinese-rules scoring dialog with dead-group confirmation."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from recurgo.domain import (
    BoardState,
    ChineseScore,
    Color,
    Point,
    chinese_area_ownership,
    connected_group,
    score_chinese,
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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.state = state
        self.language = language
        self.rules = rules
        self.komi = komi
        self.dead_points: frozenset[Point] = frozenset()
        self.confirmed_score: ChineseScore | None = None
        self.action = "continue"
        self.setWindowTitle(
            tr(language, "结束对局 · 中国规则数子", "Finish game · Chinese area scoring")
        )
        self.resize(1040, 760)

        layout = QHBoxLayout(self)
        self.board = BoardWidget()
        self.board.setMinimumSize(640, 640)
        self.board.set_position(state, last_move)
        self.board.set_input_enabled(True)
        self.board.set_scoring_mode(True, self.dead_points)
        self.board.score_point_clicked.connect(self._toggle_dead_group)
        layout.addWidget(self.board, 1)

        side = QFrame()
        side.setMinimumWidth(310)
        side_layout = QVBoxLayout(side)
        title = QLabel(tr(language, "确认死子并数子", "Mark dead stones and score"))
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        side_layout.addWidget(title)
        self.instructions = QLabel(
            tr(
                language,
                "点击棋盘上的棋块，可将整块棋标记为死子；再次点击可以恢复。确认双方死子后再结束对局。",
                "Click a group to mark it dead; click again to restore it. Confirm both sides' dead stones before ending the game.",
            )
        )
        self.instructions.setWordWrap(True)
        self.instructions.setStyleSheet(
            "padding: 10px; background: #30363d; border-radius: 6px;"
        )
        side_layout.addWidget(self.instructions)
        self.score_label = QLabel()
        self.score_label.setWordWrap(True)
        self.score_label.setStyleSheet("font-size: 16px; padding: 12px;")
        side_layout.addWidget(self.score_label)
        side_layout.addStretch(1)

        self.confirm_button = QPushButton(
            tr(language, "确认结果并结束对局", "Confirm score and finish game")
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

    def _toggle_dead_group(self, x: int, y: int) -> None:
        point = Point(x, y)
        group = connected_group(self.state, point)
        if not group:
            return
        if group.issubset(self.dead_points):
            self.dead_points = self.dead_points.difference(group)
        else:
            self.dead_points = self.dead_points.union(group)
        self.board.set_scoring_mode(True, self.dead_points)
        self._update_score()

    def _update_score(self) -> None:
        score = score_chinese(self.state, self.dead_points, komi=self.komi)
        self.board.set_ownership(list(chinese_area_ownership(self.state, self.dead_points)))
        rules = format_rules_and_komi(self.rules, self.komi, language=self.language)
        result = _score_result(score, self.language)
        self.score_label.setText(
            tr(
                self.language,
                f"{rules}\n\n黑方总子数：{score.black_area}\n白方总子数：{score.white_area}\n中立点（单官）：{score.neutral_points}\n已标记黑死子：{score.dead_black}\n已标记白死子：{score.dead_white}\n\n当前结果：{result}",
                f"{rules}\n\nBlack area: {score.black_area}\nWhite area: {score.white_area}\nNeutral points: {score.neutral_points}\nDead Black stones: {score.dead_black}\nDead White stones: {score.dead_white}\n\nCurrent result: {result}",
            )
        )

    def _confirm(self) -> None:
        self.confirmed_score = score_chinese(
            self.state,
            self.dead_points,
            komi=self.komi,
        )
        self.setWindowTitle(tr(self.language, "对局结束", "Game over"))
        result = _score_result(self.confirmed_score, self.language)
        self.instructions.setText(
            tr(
                self.language,
                f"数子完成：{result}\n\n结果确认后会自动保存到棋谱库和导出的 SGF。",
                f"Scoring complete: {result}\n\nThe result is saved in the game library and exported SGF.",
            )
        )
        self.board.set_input_enabled(False)
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
                "The result was saved in the game library and will be retained in exported SGF.",
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
