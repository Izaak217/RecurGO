from __future__ import annotations

import pytest

from recurgo.domain.coordinates import (
    Point,
    gtp_to_point,
    point_to_gtp,
    point_to_sgf,
    sgf_to_point,
)


@pytest.mark.parametrize(
    ("point", "gtp"),
    [
        (Point(0, 18), "A1"),
        (Point(3, 15), "D4"),
        (Point(8, 9), "J10"),
        (Point(18, 0), "T19"),
        (None, "pass"),
    ],
)
def test_gtp_round_trip(point: Point | None, gtp: str) -> None:
    assert point_to_gtp(point) == gtp
    assert gtp_to_point(gtp) == point


@pytest.mark.parametrize(
    ("point", "sgf"),
    [
        (Point(0, 0), "aa"),
        (Point(18, 18), "ss"),
        (Point(3, 15), "dp"),
        (None, ""),
    ],
)
def test_sgf_round_trip(point: Point | None, sgf: str) -> None:
    assert point_to_sgf(point) == sgf
    assert sgf_to_point(sgf) == point


def test_gtp_skips_column_i() -> None:
    assert point_to_gtp(Point(8, 18)) == "J1"
    with pytest.raises(ValueError):
        gtp_to_point("I1")
