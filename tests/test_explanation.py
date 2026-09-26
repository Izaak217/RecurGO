from __future__ import annotations

from recurgo.domain import BoardState, Color, Point, explain_candidate
from recurgo.domain.coordinates import point_to_gtp


def _payload(
    state: BoardState,
    point: Point,
    *,
    ownership: list[float] | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    move = point_to_gtp(point, state.size)
    info: dict[str, object] = {
        "move": move,
        "order": 0,
        "winrate": 0.61,
        "scoreLead": 3.5,
        "visits": 800,
        "pv": [move, "pass"],
    }
    payload: dict[str, object] = {"moveInfos": [info]}
    if ownership is not None:
        payload["ownership"] = ownership
    return payload, info


def test_explanation_identifies_capture_and_rescue() -> None:
    state = BoardState.from_setup(
        {
            Point(1, 1): Color.WHITE,
            Point(0, 1): Color.BLACK,
            Point(1, 0): Color.BLACK,
            Point(2, 1): Color.BLACK,
        },
        size=5,
        to_play=Color.BLACK,
    )
    payload, info = _payload(state, Point(1, 2))

    explanation = explain_candidate(state, payload, info, rank=1)

    assert any(item.code == "capture" for item in explanation.evidences)
    assert "直接提走 1 颗" in explanation.render()
    assert explanation.confidence_label == "高"


def test_explanation_identifies_connection() -> None:
    state = BoardState.from_setup(
        {Point(0, 1): Color.BLACK, Point(2, 1): Color.BLACK},
        size=5,
        to_play=Color.BLACK,
    )
    payload, info = _payload(state, Point(1, 1))

    explanation = explain_candidate(state, payload, info, rank=1)

    assert any(item.code == "connect" for item in explanation.evidences)
    assert "连接成整体" in explanation.render()


def test_explanation_identifies_atari_rescue() -> None:
    state = BoardState.from_setup(
        {
            Point(1, 1): Color.BLACK,
            Point(0, 1): Color.WHITE,
            Point(1, 0): Color.WHITE,
            Point(2, 1): Color.WHITE,
        },
        size=5,
        to_play=Color.BLACK,
    )
    payload, info = _payload(state, Point(1, 2))

    explanation = explain_candidate(state, payload, info, rank=1)

    assert any(item.code == "rescue" for item in explanation.evidences)
    assert "暂时脱离打吃" in explanation.render()


def test_explanation_uses_ownership_only_as_supported_reduction_evidence() -> None:
    state = BoardState.new(size=5, to_play=Color.BLACK)
    point = Point(2, 2)
    ownership = [0.0] * 25
    ownership[point.y * state.size + point.x] = -0.8
    payload, info = _payload(state, point, ownership=ownership)

    explanation = explain_candidate(state, payload, info, rank=1)

    assert any(item.code == "reduction" for item in explanation.evidences)
    assert "侵消或破空" in explanation.render()


def test_explanation_omits_right_panel_metrics_when_shape_is_unclear() -> None:
    state = BoardState.new(size=5, to_play=Color.BLACK)
    payload, info = _payload(state, Point(2, 2))

    explanation = explain_candidate(state, payload, info, rank=1)
    rendered = explanation.render()

    assert explanation.evidences == ()
    assert "不推断这手棋的具体意图" in rendered
    assert "KataGo 数据：" not in rendered
    assert "黑方胜率约 61.0%" not in rendered
    assert "预计领先 3.5 目" not in rendered
    assert "800 visits" not in rendered
    assert explanation.side_winrate == 61.0
    assert explanation.side_score_lead == 3.5
    assert explanation.visits == 800
    assert "不使用外部语言模型" in rendered
