"""Chinese area scoring with explicit dead-stone confirmation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .board import EMPTY, BoardState, Color
from .coordinates import Point


@dataclass(frozen=True, slots=True)
class ChineseScore:
    black_area: int
    white_area: int
    neutral_points: int
    dead_black: int
    dead_white: int
    komi: float

    @property
    def black_lead_points(self) -> float:
        return self.black_area - self.white_area - self.komi

    @property
    def winner(self) -> Color | None:
        if self.black_lead_points > 0:
            return Color.BLACK
        if self.black_lead_points < 0:
            return Color.WHITE
        return None

    @property
    def winning_margin_stones(self) -> float:
        return abs(self.black_lead_points) / 2.0

    @property
    def display_result(self) -> str:
        if self.winner is None:
            return "和棋"
        winner_name = "黑" if self.winner is Color.BLACK else "白"
        return f"{winner_name}胜{format_stones(self.winning_margin_stones)}子"

    @property
    def sgf_result(self) -> str:
        if self.winner is None:
            return "0"
        winner_name = "B" if self.winner is Color.BLACK else "W"
        return f"{winner_name}+{self.winning_margin_stones:g}"


def score_chinese(
    state: BoardState,
    dead_points: Iterable[Point],
    *,
    komi: float,
) -> ChineseScore:
    dead = frozenset(dead_points)
    dead_black = 0
    dead_white = 0
    for point in dead:
        color = state.stone_at(point)
        if color is Color.BLACK:
            dead_black += 1
        elif color is Color.WHITE:
            dead_white += 1
    ownership = chinese_area_ownership(state, dead)
    black_area = sum(value > 0 for value in ownership)
    white_area = sum(value < 0 for value in ownership)
    neutral_points = sum(value == 0 for value in ownership)

    return ChineseScore(
        black_area=black_area,
        white_area=white_area,
        neutral_points=neutral_points,
        dead_black=dead_black,
        dead_white=dead_white,
        komi=komi,
    )


def chinese_area_ownership(
    state: BoardState,
    dead_points: Iterable[Point],
) -> tuple[float, ...]:
    """Return the exact Black, White, or neutral ownership used for scoring.

    The sign intentionally matches KataGo's ownership response: ``+1`` is
    Black, ``-1`` is White, and ``0`` is neutral. Living stones count as area;
    confirmed dead stones are removed before empty regions are classified.
    """

    stones = list(state.stones)
    for point in frozenset(dead_points):
        stones[point.y * state.size + point.x] = EMPTY

    ownership = [0.0] * len(stones)
    for index, value in enumerate(stones):
        if value == int(Color.BLACK):
            ownership[index] = 1.0
        elif value == int(Color.WHITE):
            ownership[index] = -1.0

    visited: set[int] = set()
    for start, value in enumerate(stones):
        if value != EMPTY or start in visited:
            continue
        region, bordering = _empty_region(stones, state.size, start)
        visited.update(region)
        if bordering == {Color.BLACK}:
            owner = 1.0
        elif bordering == {Color.WHITE}:
            owner = -1.0
        else:
            owner = 0.0
        for index in region:
            ownership[index] = owner
    return tuple(ownership)


def connected_group(state: BoardState, point: Point) -> frozenset[Point]:
    color = state.stone_at(point)
    if color is None:
        return frozenset()
    group: set[Point] = set()
    pending = [point]
    while pending:
        current = pending.pop()
        if current in group:
            continue
        group.add(current)
        for neighbor in _neighbors(current, state.size):
            if neighbor not in group and state.stone_at(neighbor) is color:
                pending.append(neighbor)
    return frozenset(group)


def format_stones(value: float) -> str:
    quarter_count = round(value * 4)
    if abs(value * 4 - quarter_count) > 1e-7:
        return f"{value:g}"
    integer, remainder = divmod(quarter_count, 4)
    fractions = {0: "", 1: "¼", 2: "½", 3: "¾"}
    return f"{integer if integer else ''}{fractions[remainder]}" or "0"


def display_sgf_result(result: str) -> str:
    normalized = result.strip().upper()
    if normalized in {"", "?"}:
        return "结果未定"
    if normalized in {"0", "DRAW"}:
        return "和棋"
    if "+" not in normalized:
        return result
    winner, margin = normalized.split("+", 1)
    winner_name = "黑" if winner == "B" else "白" if winner == "W" else winner
    if margin in {"R", "RESIGN"}:
        return f"{winner_name}中盘胜"
    try:
        numeric_margin = float(margin)
    except ValueError:
        return result
    return f"{winner_name}胜{format_stones(numeric_margin)}子"


def _empty_region(
    stones: list[int],
    size: int,
    start: int,
) -> tuple[set[int], set[Color]]:
    region: set[int] = set()
    bordering: set[Color] = set()
    pending = [start]
    while pending:
        current = pending.pop()
        if current in region:
            continue
        region.add(current)
        point = Point(current % size, current // size)
        for neighbor in _neighbors(point, size):
            index = neighbor.y * size + neighbor.x
            value = stones[index]
            if value == EMPTY and index not in region:
                pending.append(index)
            elif value != EMPTY:
                bordering.add(Color(value))
    return region, bordering


def _neighbors(point: Point, size: int) -> Iterable[Point]:
    if point.x > 0:
        yield Point(point.x - 1, point.y)
    if point.x + 1 < size:
        yield Point(point.x + 1, point.y)
    if point.y > 0:
        yield Point(point.x, point.y - 1)
    if point.y + 1 < size:
        yield Point(point.x, point.y + 1)
