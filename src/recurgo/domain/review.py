"""Whole-game review metrics derived from saved KataGo analysis snapshots."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .board import Color
from .coordinates import point_to_gtp
from .game_tree import GameTree


@dataclass(frozen=True, slots=True)
class MoveReview:
    node_id: str
    move_number: int
    color: Color
    move: str
    best_move: str
    top_three: tuple[str, ...]
    black_winrate_before: float | None
    black_winrate_after: float | None
    winrate_loss: float | None
    score_loss: float | None
    matches_best: bool
    matches_top_three: bool
    grade: str


@dataclass(frozen=True, slots=True)
class SideReviewSummary:
    analyzed_moves: int
    best_matches: int
    top_three_matches: int
    grade_counts: dict[str, int]
    average_winrate_loss: float
    average_score_loss: float

    @property
    def best_match_rate(self) -> float:
        return _percentage(self.best_matches, self.analyzed_moves)

    @property
    def top_three_match_rate(self) -> float:
        return _percentage(self.top_three_matches, self.analyzed_moves)


@dataclass(frozen=True, slots=True)
class ReviewSummary:
    black: SideReviewSummary
    white: SideReviewSummary
    grade_counts: dict[str, int]


def black_winrate(
    tree: GameTree,
    node_id: str,
    payload: dict[str, object],
) -> float | None:
    """Read the black winrate percentage from BLACK-perspective engine output."""
    root = payload.get("rootInfo")
    if not isinstance(root, dict):
        return None
    raw = _as_number(root.get("winrate"))
    if raw is None:
        return None
    return raw * 100.0


def black_score_lead(
    tree: GameTree,
    node_id: str,
    payload: dict[str, object],
) -> float | None:
    """Read black's point lead from BLACK-perspective engine output."""
    root = payload.get("rootInfo")
    if not isinstance(root, dict):
        return None
    raw = _as_number(root.get("scoreLead", root.get("scoreMean")))
    if raw is None:
        return None
    return raw


def build_move_reviews(
    tree: GameTree,
    line_node_ids: list[str],
    payloads: dict[str, dict[str, object]],
) -> list[MoveReview]:
    reviews: list[MoveReview] = []
    for parent_id, node_id in zip(line_node_ids, line_node_ids[1:], strict=False):
        node = tree.nodes[node_id]
        if node.move is None:
            continue
        parent_payload = payloads.get(parent_id)
        child_payload = payloads.get(node_id)
        if parent_payload is None:
            continue

        candidate_moves = _candidate_moves(parent_payload)
        actual_move = point_to_gtp(node.move.point, node.state.size)
        normalized_actual = actual_move.upper()
        best_move = candidate_moves[0] if candidate_moves else "—"
        top_three = tuple(candidate_moves[:3])
        matches_best = bool(candidate_moves) and normalized_actual == best_move.upper()
        matches_top_three = any(
            normalized_actual == candidate.upper() for candidate in top_three
        )

        before = black_winrate(tree, parent_id, parent_payload)
        after = (
            None
            if child_payload is None
            else black_winrate(tree, node_id, child_payload)
        )
        before_score = black_score_lead(tree, parent_id, parent_payload)
        after_score = (
            None
            if child_payload is None
            else black_score_lead(tree, node_id, child_payload)
        )
        loss = _mover_loss(node.move.color, before, after)
        score_loss = _mover_loss(node.move.color, before_score, after_score)
        grade = grade_move(loss, matches_best=matches_best)
        reviews.append(
            MoveReview(
                node_id=node_id,
                move_number=node.state.move_number,
                color=node.move.color,
                move=actual_move,
                best_move=best_move,
                top_three=top_three,
                black_winrate_before=before,
                black_winrate_after=after,
                winrate_loss=loss,
                score_loss=score_loss,
                matches_best=matches_best,
                matches_top_three=matches_top_three,
                grade=grade,
            )
        )
    return reviews


def summarize_reviews(reviews: list[MoveReview]) -> ReviewSummary:
    grade_counts = {
        "好手": 0,
        "正常": 0,
        "疑问手": 0,
        "坏手": 0,
        "严重失误": 0,
    }
    sides: dict[Color, list[MoveReview]] = {
        Color.BLACK: [],
        Color.WHITE: [],
    }
    for review in reviews:
        sides[review.color].append(review)
        grade_counts[review.grade] = grade_counts.get(review.grade, 0) + 1

    def side_summary(color: Color) -> SideReviewSummary:
        values = sides[color]
        side_grades = {
            grade: sum(review.grade == grade for review in values)
            for grade in grade_counts
        }
        return SideReviewSummary(
            analyzed_moves=len(values),
            best_matches=sum(review.matches_best for review in values),
            top_three_matches=sum(review.matches_top_three for review in values),
            grade_counts=side_grades,
            average_winrate_loss=_average(
                review.winrate_loss
                for review in values
                if review.winrate_loss is not None
            ),
            average_score_loss=_average(
                review.score_loss
                for review in values
                if review.score_loss is not None
            ),
        )

    return ReviewSummary(
        black=side_summary(Color.BLACK),
        white=side_summary(Color.WHITE),
        grade_counts=grade_counts,
    )


def grade_move(winrate_loss: float | None, *, matches_best: bool) -> str:
    """Apply transparent, review-oriented thresholds to mover winrate loss."""
    if matches_best or winrate_loss is not None and winrate_loss <= 1.5:
        return "好手"
    if winrate_loss is None or winrate_loss <= 3.0:
        return "正常"
    if winrate_loss <= 7.0:
        return "疑问手"
    if winrate_loss <= 15.0:
        return "坏手"
    return "严重失误"


def _candidate_moves(payload: dict[str, object]) -> list[str]:
    raw_infos = payload.get("moveInfos")
    if not isinstance(raw_infos, list):
        return []
    infos = [raw_info for raw_info in raw_infos if isinstance(raw_info, dict)]
    infos.sort(
        key=lambda info: (
            int(info["order"])
            if isinstance(info.get("order"), (int, float))
            else len(infos)
        )
    )
    moves: list[str] = []
    for raw_info in infos:
        move = raw_info.get("move")
        if isinstance(move, str):
            moves.append(move)
    return moves


def _mover_loss(
    color: Color,
    before_black_value: float | None,
    after_black_value: float | None,
) -> float | None:
    if before_black_value is None or after_black_value is None:
        return None
    raw_loss = (
        before_black_value - after_black_value
        if color is Color.BLACK
        else after_black_value - before_black_value
    )
    return max(0.0, raw_loss)


def _as_number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _percentage(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator * 100.0


def _average(values: Iterable[float]) -> float:
    numbers = list(values)
    return 0.0 if not numbers else sum(numbers) / len(numbers)
