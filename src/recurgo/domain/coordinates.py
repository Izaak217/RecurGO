"""Coordinate conversion shared by the board, SGF, UI, and KataGo protocol."""

from __future__ import annotations

from dataclasses import dataclass

GTP_COLUMNS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"
SGF_COLUMNS = "abcdefghijklmnopqrstuvwxyz"


@dataclass(frozen=True, order=True, slots=True)
class Point:
    """Zero-based point with y=0 at the top edge of the displayed board."""

    x: int
    y: int


def point_to_gtp(point: Point | None, board_size: int = 19) -> str:
    if point is None:
        return "pass"
    _validate_point(point, board_size)
    return f"{GTP_COLUMNS[point.x]}{board_size - point.y}"


def gtp_to_point(value: str, board_size: int = 19) -> Point | None:
    normalized = value.strip().upper()
    if normalized in {"PASS", ""}:
        return None
    if len(normalized) < 2:
        raise ValueError(f"Invalid GTP coordinate: {value!r}")
    column = normalized[0]
    if column not in GTP_COLUMNS[:board_size]:
        raise ValueError(f"Invalid GTP column: {column!r}")
    try:
        row = int(normalized[1:])
    except ValueError as exc:
        raise ValueError(f"Invalid GTP row: {value!r}") from exc
    point = Point(GTP_COLUMNS.index(column), board_size - row)
    _validate_point(point, board_size)
    return point


def point_to_sgf(point: Point | None, board_size: int = 19) -> str:
    if point is None:
        return ""
    _validate_point(point, board_size)
    return SGF_COLUMNS[point.x] + SGF_COLUMNS[point.y]


def sgf_to_point(value: str, board_size: int = 19) -> Point | None:
    normalized = value.strip().lower()
    if normalized == "":
        return None
    if len(normalized) != 2:
        raise ValueError(f"Invalid SGF coordinate: {value!r}")
    point = Point(
        SGF_COLUMNS.index(normalized[0]),
        SGF_COLUMNS.index(normalized[1]),
    )
    _validate_point(point, board_size)
    return point


def _validate_point(point: Point, board_size: int) -> None:
    if not (0 <= point.x < board_size and 0 <= point.y < board_size):
        raise ValueError(f"Point {point} is outside a {board_size}x{board_size} board")
