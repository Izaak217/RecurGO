"""v1.0.1 revision: conservative shape evidence for the first scoring suggestion.

Unconditional life uses the Benson fixed-point criterion (two vital regions).
Only empty vital regions are included here; this deliberately leaves many living
shapes unproved. Mutual life is restricted to two-liberty pairs where every local
first move permits immediate, non-ko capture. Neither procedure is a general
life-and-death solver. This module never processes users' point corrections.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .board import EMPTY, BoardState, Color, IllegalMove
from .coordinates import Point
from .scoring import connected_group


@dataclass(frozen=True)
class Chain:
    color: Color
    points: frozenset[Point]
    liberties: frozenset[Point]


@dataclass(frozen=True)
class EmptyRegion:
    points: frozenset[Point]
    borders: frozenset[int]


def neighbors(point: Point, size: int) -> tuple[Point, ...]:
    return tuple(
        Point(x, y)
        for x, y in ((point.x - 1, point.y), (point.x + 1, point.y),
                     (point.x, point.y - 1), (point.x, point.y + 1))
        if 0 <= x < size and 0 <= y < size
    )


def board_regions(state: BoardState) -> tuple[list[Chain], list[EmptyRegion]]:
    chains: list[Chain] = []
    ids: dict[Point, int] = {}
    empty: set[Point] = set()
    for y in range(state.size):
        for x in range(state.size):
            point = Point(x, y)
            color = state.stone_at(point)
            if color is None:
                empty.add(point)
            elif point not in ids:
                group = connected_group(state, point)
                liberties = frozenset(
                    n for p in group for n in neighbors(p, state.size)
                    if state.stone_at(n) is None
                )
                ids.update((p, len(chains)) for p in group)
                chains.append(Chain(color, group, liberties))
    regions: list[EmptyRegion] = []
    while empty:
        start = min(empty, key=lambda p: (p.y, p.x))
        pending = [start]
        points: set[Point] = set()
        borders: set[int] = set()
        while pending:
            point = pending.pop()
            if point not in empty:
                continue
            empty.remove(point)
            points.add(point)
            for other in neighbors(point, state.size):
                if other in empty:
                    pending.append(other)
                elif other in ids:
                    borders.add(ids[other])
        regions.append(EmptyRegion(frozenset(points), frozenset(borders)))
    return chains, regions


def _benson(chains: list[Chain], regions: list[EmptyRegion]) -> set[int]:
    alive: set[int] = set()
    for color in Color:
        remaining = {i for i, chain in enumerate(chains) if chain.color is color}
        while remaining:
            enclosed = [r for r in regions if r.borders and r.borders <= remaining]
            survivors = {
                i for i in remaining
                if sum(r.points <= chains[i].liberties for r in enclosed) >= 2
            }
            if survivors == remaining:
                break
            remaining = survivors
        alive.update(remaining)
    return alive


def _loses_after_local_move(state: BoardState, chain: Chain, point: Point) -> bool:
    """Reject captures, ko, escapes and snapback; prove only immediate local loss."""
    try:
        played = replace(state, to_play=chain.color).play(point)
    except IllegalMove:
        return False
    if (played.black_captures, played.white_captures) != (
        state.black_captures, state.white_captures
    ):
        return False
    group = connected_group(played, point)
    liberties = {
        n for p in group for n in neighbors(p, state.size)
        if played.stone_at(n) is None
    }
    if len(liberties) != 1:
        return False
    reply = next(iter(liberties))
    try:
        captured = played.play(reply)
    except IllegalMove:
        return False
    if captured.ko_point is not None or any(captured.stone_at(p) is not None for p in group):
        return False
    capturing_group = connected_group(captured, reply)
    escape_liberties = {
        n for p in capturing_group for n in neighbors(p, state.size)
        if captured.stone_at(n) is None
    }
    return len(escape_liberties) >= 2


def shape_ownership(state: BoardState) -> dict[Point, int]:
    """Return only structurally supported stones, vital eyes and shared liberties."""
    chains, regions = board_regions(state)
    alive = _benson(chains, regions)
    result = {
        point: 1 if chains[i].color is Color.BLACK else -1
        for i in alive for point in chains[i].points
    }
    ids = {p: i for i, c in enumerate(chains) for p in c.points}
    # A narrowly verified two-liberty mutual-life pair, not every mixed boundary.
    for i, first in enumerate(chains):
        if len(first.liberties) != 2 or i in alive:
            continue
        for j in range(i + 1, len(chains)):
            second = chains[j]
            common = first.liberties & second.liberties
            if (second.color is first.color or len(second.liberties) != 2
                    or not common or j in alive
                    or state.ko_point in first.liberties | second.liberties):
                continue
            adjacent = {
                ids[n] for c in (first, second) for p in c.points
                for n in neighbors(p, state.size) if n in ids
            }
            if not adjacent <= alive | {i, j}:
                continue
            # Private liberties must be real single-point eyes, not outside routes.
            if any(
                any(ids.get(n) != k for n in neighbors(p, state.size))
                for k, c in ((i, first), (j, second)) for p in c.liberties - common
            ):
                continue
            if not all(_loses_after_local_move(state, c, p)
                       for c in (first, second) for p in c.liberties):
                continue
            for c in (first, second):
                owner = 1 if c.color is Color.BLACK else -1
                result.update((p, owner) for p in c.points | (c.liberties - common))
            result.update((p, 0) for p in common)
    for region in regions:
        if not region.borders:
            continue
        colors = {chains[i].color for i in region.borders}
        if (len(colors) == 1 and region.borders <= alive
                and any(region.points <= chains[i].liberties for i in region.borders)):
            owner = 1 if next(iter(colors)) is Color.BLACK else -1
            result.update((p, owner) for p in region.points)
        elif state.is_game_over and region.borders <= alive:
            # After two passes, genuinely shared liberties can be split. Large
            # open regions merely touching both sides do not satisfy this test.
            for point in region.points:
                adjacent_colors = {
                    state.stone_at(n) for n in neighbors(point, state.size)
                    if state.stone_at(n) is not None
                }
                if adjacent_colors == {Color.BLACK, Color.WHITE}:
                    result[point] = 0
    if state.ko_point is not None:
        result.pop(state.ko_point, None)
    return result


def suggested_eye_ownership(state: BoardState, owners: tuple[int, ...]) -> dict[Point, int]:
    """Fill small vital regions conditional on AI-suggested whole-group status.

    Removing an AI-predicted dead group is only a proposal; no game state changes.
    Large enclosed spaces can contain invasions, so enclosing live stones alone
    never cause those spaces to be filled automatically.
    """
    chains, _ = board_regions(state)
    stones = list(state.stones)
    for chain in chains:
        opposite = -1 if chain.color is Color.BLACK else 1
        if all(owners[p.y * state.size + p.x] == opposite for p in chain.points):
            for point in chain.points:
                stones[point.y * state.size + point.x] = EMPTY
    working = replace(state, stones=tuple(stones))
    remaining, regions = board_regions(working)
    result: dict[Point, int] = {}
    for region in regions:
        colors = {remaining[i].color for i in region.borders}
        if len(colors) != 1:
            continue
        owner = 1 if next(iter(colors)) is Color.BLACK else -1
        if (all(owners[p.y * state.size + p.x] == owner
                for i in region.borders for p in remaining[i].points)
                and any(region.points <= remaining[i].liberties for i in region.borders)):
            result.update((p, owner) for p in region.points)
    return result
