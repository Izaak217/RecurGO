from __future__ import annotations

import pytest

from recurgo.domain import (
    Color,
    GameTree,
    Point,
    black_winrate,
    build_move_reviews,
    summarize_reviews,
)
from recurgo.domain.review import black_score_lead


def test_review_converts_current_player_values_and_grades_each_mover() -> None:
    tree = GameTree()
    black_move, _created = tree.play(Point(3, 3))
    white_move, _created = tree.play(Point(15, 15))
    line = [tree.root_id, black_move.id, white_move.id]
    payloads: dict[str, dict[str, object]] = {
        tree.root_id: {
            "rootInfo": {"winrate": 0.60, "scoreLead": 4.0},
            "moveInfos": [{"move": "Q16"}, {"move": "D16"}, {"move": "D4"}],
        },
        black_move.id: {
            "rootInfo": {"winrate": 0.50, "scoreLead": 0.0},
            "moveInfos": [{"move": "C3"}, {"move": "Q4"}],
        },
        white_move.id: {
            "rootInfo": {"winrate": 0.55, "scoreLead": 2.0},
            "moveInfos": [{"move": "Q10"}],
        },
    }

    assert black_winrate(tree, tree.root_id, payloads[tree.root_id]) == 60.0
    assert black_winrate(tree, black_move.id, payloads[black_move.id]) == 50.0

    reviews = build_move_reviews(tree, line, payloads)

    assert reviews[0].color is Color.BLACK
    assert reviews[0].move == "D16"
    assert reviews[0].winrate_loss == 10.0
    assert reviews[0].grade == "坏手"
    assert not reviews[0].matches_best
    assert reviews[0].matches_top_three

    assert reviews[1].color is Color.WHITE
    assert reviews[1].move == "Q4"
    assert reviews[1].winrate_loss == pytest.approx(5.0)
    assert reviews[1].grade == "疑问手"
    assert not reviews[1].matches_best

    summary = summarize_reviews(reviews)
    assert summary.black.best_match_rate == 0.0
    assert summary.black.top_three_match_rate == 100.0
    assert summary.white.top_three_match_rate == 100.0
    assert summary.grade_counts["坏手"] == 1
    assert summary.grade_counts["疑问手"] == 1
    assert summary.black.grade_counts["坏手"] == 1
    assert summary.white.grade_counts["疑问手"] == 1
    assert summary.black.average_winrate_loss == 10.0
    assert summary.black.average_score_loss == 4.0
    assert summary.white.average_winrate_loss == pytest.approx(5.0)
    assert summary.white.average_score_loss == 2.0


def test_black_perspective_values_are_not_flipped_when_white_is_to_play() -> None:
    tree = GameTree()
    black_move, _created = tree.play(Point(3, 3))
    payload: dict[str, object] = {
        "rootInfo": {
            "winrate": 0.343,
            "scoreLead": -1.25,
        }
    }

    assert tree.nodes[black_move.id].state.to_play is Color.WHITE
    assert black_winrate(tree, black_move.id, payload) == pytest.approx(34.3)
    assert black_score_lead(tree, black_move.id, payload) == -1.25
