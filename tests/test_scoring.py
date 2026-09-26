from recurgo.domain import (
    BoardState,
    Color,
    Point,
    chinese_area_ownership,
    connected_group,
    display_sgf_result,
    format_stones,
    score_chinese,
)


def test_chinese_scoring_counts_stones_and_surrounded_area() -> None:
    state = BoardState.from_setup(
        {
            Point(1, 1): Color.BLACK,
            Point(2, 1): Color.BLACK,
            Point(3, 1): Color.BLACK,
            Point(1, 2): Color.BLACK,
            Point(3, 2): Color.BLACK,
            Point(1, 3): Color.BLACK,
            Point(2, 3): Color.BLACK,
            Point(3, 3): Color.BLACK,
            Point(0, 0): Color.WHITE,
        },
        size=5,
    )

    score = score_chinese(state, (), komi=7.5)

    assert score.black_area == 9
    assert score.white_area == 1
    assert score.neutral_points == 15
    assert score.display_result == "黑胜¼子"


def test_marked_dead_group_is_removed_before_area_counting() -> None:
    state = BoardState.from_setup(
        {
            Point(0, 0): Color.BLACK,
            Point(1, 0): Color.BLACK,
            Point(0, 1): Color.BLACK,
            Point(1, 1): Color.WHITE,
        },
        size=3,
    )
    dead_group = connected_group(state, Point(1, 1))

    score = score_chinese(state, dead_group, komi=0.0)

    assert dead_group == {Point(1, 1)}
    assert score.dead_white == 1
    assert score.black_area == 9
    assert score.display_result == "黑胜4½子"
    assert score.sgf_result == "B+4.5"


def test_chinese_area_ownership_matches_score_and_marks_confirmed_dead_stones() -> None:
    state = BoardState.from_setup(
        {
            Point(0, 0): Color.BLACK,
            Point(1, 0): Color.BLACK,
            Point(0, 1): Color.BLACK,
            Point(1, 1): Color.WHITE,
        },
        size=3,
    )

    ownership = chinese_area_ownership(state, {Point(1, 1)})
    score = score_chinese(state, {Point(1, 1)}, komi=0.0)

    assert ownership[1 * state.size + 1] == 1.0
    assert sum(value > 0 for value in ownership) == score.black_area
    assert sum(value < 0 for value in ownership) == score.white_area
    assert sum(value == 0 for value in ownership) == score.neutral_points


def test_result_uses_quarter_stone_notation() -> None:
    assert format_stones(0.25) == "¼"
    assert format_stones(1.5) == "1½"
    assert format_stones(3.75) == "3¾"
    assert display_sgf_result("B+1.25") == "黑胜1¼子"
    assert display_sgf_result("W+R") == "白中盘胜"
