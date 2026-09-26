"""Pure Go-domain logic with no UI or engine dependencies."""

from .board import (
    BoardState,
    Color,
    IllegalMove,
    OccupiedPoint,
    OutOfBounds,
    SuicideMove,
    SuperkoViolation,
)
from .coordinates import Point
from .explanation import CandidateExplanation, ExplanationEvidence, explain_candidate
from .game_tree import GameNode, GameTree, Move
from .recommendations import (
    RECOMMENDATION_TIERS,
    RecommendationTier,
    select_recommended_candidates,
)
from .review import (
    MoveReview,
    ReviewSummary,
    SideReviewSummary,
    black_winrate,
    build_move_reviews,
    summarize_reviews,
)
from .scoring import (
    ChineseScore,
    chinese_area_ownership,
    connected_group,
    display_sgf_result,
    format_stones,
    score_chinese,
)

__all__ = [
    "BoardState",
    "CandidateExplanation",
    "Color",
    "ChineseScore",
    "GameNode",
    "GameTree",
    "ExplanationEvidence",
    "IllegalMove",
    "Move",
    "MoveReview",
    "OccupiedPoint",
    "OutOfBounds",
    "Point",
    "ReviewSummary",
    "RECOMMENDATION_TIERS",
    "RecommendationTier",
    "SideReviewSummary",
    "SuicideMove",
    "SuperkoViolation",
    "chinese_area_ownership",
    "connected_group",
    "black_winrate",
    "build_move_reviews",
    "display_sgf_result",
    "explain_candidate",
    "format_stones",
    "score_chinese",
    "select_recommended_candidates",
    "summarize_reviews",
]
