from recurgo.domain import BoardState, Color, Point, explain_candidate


def test_reference_variation_explains_visible_capture_without_claiming_it_is_forced() -> None:
    state = BoardState.from_setup(
        {
            Point(1, 1): Color.BLACK,
            Point(0, 1): Color.WHITE,
            Point(1, 0): Color.WHITE,
            Point(2, 1): Color.WHITE,
        },
        size=5,
    )
    info = {"move": "E1", "pv": ["E1", "B3", "pass"]}
    explanation = explain_candidate(state, {"moveInfos": [info]}, info, rank=1)
    assert explanation.variation_notes == ("第 2 手白方在 B3 提走 1 子",)
    assert "只是搜索参考变化" in explanation.render()
    assert state.stone_at(Point(1, 1)) is Color.BLACK


def test_illegal_reference_line_stops_before_later_capture_claim() -> None:
    state = BoardState.from_setup(
        {
            Point(1, 1): Color.BLACK,
            Point(0, 1): Color.WHITE,
            Point(1, 0): Color.WHITE,
            Point(2, 1): Color.WHITE,
        },
        size=5,
    )
    for pv in (["E1", "A4", "pass", "B3"], ["D1", "B3"], ["E1", "Q16", "B3"]):
        info = {"move": "E1", "pv": pv}
        explanation = explain_candidate(state, {"moveInfos": [info]}, info, rank=1)
        assert explanation.variation_notes == ()


def test_two_passes_end_reference_replay() -> None:
    state = BoardState.new(5)
    info = {"move": "pass", "pv": ["pass", "pass", "A1"]}
    explanation = explain_candidate(state, {"moveInfos": [info]}, info, rank=1)
    assert explanation.variation_notes == ()


def test_extending_in_atari_is_not_reported_as_rescue() -> None:
    state = BoardState.from_setup(
        {
            Point(1, 1): Color.BLACK,
            Point(0, 1): Color.WHITE,
            Point(1, 0): Color.WHITE,
            Point(2, 1): Color.WHITE,
            Point(0, 2): Color.WHITE,
            Point(2, 2): Color.WHITE,
        },
        size=5,
    )
    info = {"move": "B3", "pv": ["B3", "B2"]}
    explanation = explain_candidate(state, {"moveInfos": [info]}, info, rank=1)
    assert not any(item.code == "rescue" for item in explanation.evidences)
    assert "尚未解除打吃" in explanation.render()
    assert explanation.variation_notes == ("第 2 手白方在 B2 提走 2 子",)
