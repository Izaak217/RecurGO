"""Immutable Go board state with captures, suicide, ko, and positional superko."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum

from .coordinates import Point

EMPTY = 0


class Color(IntEnum):
    BLACK = 1
    WHITE = 2

    @property
    def opponent(self) -> Color:
        return Color.WHITE if self is Color.BLACK else Color.BLACK

    @property
    def short_name(self) -> str:
        return "B" if self is Color.BLACK else "W"


class IllegalMove(ValueError):
    """Base class for illegal moves."""


class OutOfBounds(IllegalMove):
    pass


class OccupiedPoint(IllegalMove):
    pass


class SuicideMove(IllegalMove):
    pass


class SuperkoViolation(IllegalMove):
    pass


@dataclass(frozen=True, slots=True)
class BoardState:
    size: int
    stones: tuple[int, ...]
    to_play: Color
    ko_point: Point | None
    black_captures: int
    white_captures: int
    move_number: int
    consecutive_passes: int
    position_history: frozenset[str]

    @classmethod
    def new(cls, size: int = 19, to_play: Color = Color.BLACK) -> BoardState:
        if not (2 <= size <= 25):
            raise ValueError("Board size must be between 2 and 25")
        stones = (EMPTY,) * (size * size)
        return cls(
            size=size,
            stones=stones,
            to_play=to_play,
            ko_point=None,
            black_captures=0,
            white_captures=0,
            move_number=0,
            consecutive_passes=0,
            position_history=frozenset({_position_hash(stones)}),
        )

    @classmethod
    def from_setup(
        cls,
        stones: dict[Point, Color],
        *,
        size: int = 19,
        to_play: Color = Color.BLACK,
    ) -> BoardState:
        raw = [EMPTY] * (size * size)
        for point, color in stones.items():
            if not (0 <= point.x < size and 0 <= point.y < size):
                raise OutOfBounds(point)
            raw[point.y * size + point.x] = int(color)
        immutable = tuple(raw)
        return cls(
            size=size,
            stones=immutable,
            to_play=to_play,
            ko_point=None,
            black_captures=0,
            white_captures=0,
            move_number=0,
            consecutive_passes=0,
            position_history=frozenset({_position_hash(immutable)}),
        )

    @property
    def is_game_over(self) -> bool:
        return self.consecutive_passes >= 2

    @property
    def position_hash(self) -> str:
        return _position_hash(self.stones)

    def stone_at(self, point: Point) -> Color | None:
        index = self._index(point)
        value = self.stones[index]
        return None if value == EMPTY else Color(value)

    def play(self, point: Point | None) -> BoardState:
        if point is None:
            return BoardState(
                size=self.size,
                stones=self.stones,
                to_play=self.to_play.opponent,
                ko_point=None,
                black_captures=self.black_captures,
                white_captures=self.white_captures,
                move_number=self.move_number + 1,
                consecutive_passes=self.consecutive_passes + 1,
                position_history=self.position_history,
            )

        index = self._index(point)
        if self.stones[index] != EMPTY:
            raise OccupiedPoint(f"{point} is occupied")

        updated = list(self.stones)
        updated[index] = int(self.to_play)
        captured: set[int] = set()
        inspected_opponent: set[int] = set()

        for neighbor in self._neighbor_indices(index):
            if updated[neighbor] != int(self.to_play.opponent):
                continue
            if neighbor in inspected_opponent:
                continue
            group, liberties = self._group_and_liberties(updated, neighbor)
            inspected_opponent.update(group)
            if not liberties:
                captured.update(group)

        for captured_index in captured:
            updated[captured_index] = EMPTY

        own_group, own_liberties = self._group_and_liberties(updated, index)
        if not own_liberties:
            raise SuicideMove(f"{point} has no liberties")

        immutable = tuple(updated)
        new_hash = _position_hash(immutable)
        if new_hash in self.position_history:
            raise SuperkoViolation(f"{point} repeats an earlier position")

        captured_count = len(captured)
        black_captures = self.black_captures
        white_captures = self.white_captures
        if self.to_play is Color.BLACK:
            black_captures += captured_count
        else:
            white_captures += captured_count

        ko_point: Point | None = None
        if captured_count == 1 and len(own_group) == 1 and len(own_liberties) == 1:
            captured_index = next(iter(captured))
            ko_point = Point(captured_index % self.size, captured_index // self.size)

        return BoardState(
            size=self.size,
            stones=immutable,
            to_play=self.to_play.opponent,
            ko_point=ko_point,
            black_captures=black_captures,
            white_captures=white_captures,
            move_number=self.move_number + 1,
            consecutive_passes=0,
            position_history=self.position_history | {new_hash},
        )

    def _index(self, point: Point) -> int:
        if not (0 <= point.x < self.size and 0 <= point.y < self.size):
            raise OutOfBounds(f"{point} is outside the board")
        return point.y * self.size + point.x

    def _neighbor_indices(self, index: int) -> Iterable[int]:
        x = index % self.size
        y = index // self.size
        if x > 0:
            yield index - 1
        if x + 1 < self.size:
            yield index + 1
        if y > 0:
            yield index - self.size
        if y + 1 < self.size:
            yield index + self.size

    def _group_and_liberties(self, stones: list[int], start: int) -> tuple[set[int], set[int]]:
        color = stones[start]
        group: set[int] = set()
        liberties: set[int] = set()
        pending = [start]
        while pending:
            current = pending.pop()
            if current in group:
                continue
            group.add(current)
            for neighbor in self._neighbor_indices(current):
                value = stones[neighbor]
                if value == EMPTY:
                    liberties.add(neighbor)
                elif value == color and neighbor not in group:
                    pending.append(neighbor)
        return group, liberties


def _position_hash(stones: tuple[int, ...]) -> str:
    return hashlib.blake2b(bytes(stones), digest_size=16).hexdigest()
