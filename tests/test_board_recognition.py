from __future__ import annotations

import cv2
import numpy as np
import pytest

from recurgo.domain import Color, Point
from recurgo.vision import board_recognition as recognition_module
from recurgo.vision import recognize_board


def _synthetic_board(
    *,
    size: int = 19,
    include_stones: bool = True,
    dense: bool = False,
) -> tuple[np.ndarray, tuple[tuple[float, float], ...], dict[Point, Color]]:
    image = np.full((920, 920, 3), (28, 31, 34), dtype=np.uint8)
    cv2.rectangle(image, (45, 45), (875, 875), (72, 164, 218), -1)
    start = 100
    end = 820
    cell = (end - start) / (size - 1)
    for index in range(size):
        coordinate = round(start + index * cell)
        cv2.line(image, (start, coordinate), (end, coordinate), (25, 31, 38), 2)
        cv2.line(image, (coordinate, start), (coordinate, end), (25, 31, 38), 2)
    if dense:
        random = np.random.default_rng(2)
        stones = {}
        for y in range(size):
            for x in range(size):
                if random.random() < 0.50:
                    stones[Point(x, y)] = (
                        Color.BLACK if random.random() < 0.50 else Color.WHITE
                    )
    elif include_stones:
        stones = {
            Point(0, 0): Color.BLACK,
            Point(3, 3): Color.BLACK,
            Point(size // 2, size // 2): Color.WHITE,
            Point(size - 4, size - 4): Color.WHITE,
        }
    else:
        stones = {}
    radius = round(cell * 0.44)
    for point, color in stones.items():
        center = (round(start + point.x * cell), round(start + point.y * cell))
        if color is Color.BLACK:
            cv2.circle(image, center, radius, (12, 14, 16), -1, cv2.LINE_AA)
            cv2.circle(image, center, radius, (0, 0, 0), 2, cv2.LINE_AA)
        else:
            cv2.circle(image, center, radius, (245, 245, 241), -1, cv2.LINE_AA)
            cv2.circle(image, center, radius, (155, 155, 150), 2, cv2.LINE_AA)
    corners = (
        (float(start), float(start)),
        (float(end), float(start)),
        (float(end), float(end)),
        (float(start), float(end)),
    )
    return image, corners, stones


def test_recognition_classifies_stones_from_manually_selected_grid() -> None:
    image, corners, expected = _synthetic_board()

    result = recognize_board(image, board_size=19, corners=corners)  # type: ignore[arg-type]

    assert result.board_size == 19
    assert result.stones == expected
    assert result.warped.shape == (836, 836, 3)


@pytest.mark.parametrize("size", [9, 13, 19])
def test_recognition_auto_detects_a_clean_board(size: int) -> None:
    image, _corners, expected = _synthetic_board(size=size)

    result = recognize_board(image)

    assert result.board_size == size
    assert result.stones == expected


def test_recognition_does_not_subsample_empty_19_line_grid_as_9() -> None:
    image, corners, _expected = _synthetic_board(size=19, include_stones=False)

    result = recognize_board(image)

    assert result.board_size == 19
    assert result.stones == {}
    assert np.asarray(result.corners) == pytest.approx(np.asarray(corners), abs=4.0)


@pytest.mark.parametrize("size", [9, 13, 19])
def test_recognition_detects_dense_board_without_harmonic_subsampling(size: int) -> None:
    image, corners, expected = _synthetic_board(size=size, dense=True)

    result = recognize_board(image)

    assert result.board_size == size
    assert result.stones == expected
    assert np.asarray(result.corners) == pytest.approx(np.asarray(corners), abs=5.0)


def test_clear_low_contrast_white_stone_is_not_reported_as_uncertain() -> None:
    image = np.full((920, 920, 3), (28, 31, 34), dtype=np.uint8)
    cv2.rectangle(image, (45, 45), (875, 875), (124, 206, 244), -1)
    for index in range(19):
        coordinate = 100 + index * 40
        cv2.line(image, (100, coordinate), (820, coordinate), (0, 35, 34), 1)
        cv2.line(image, (coordinate, 100), (coordinate, 820), (0, 35, 34), 1)
    cv2.circle(image, (460, 460), 18, (190, 210, 220), -1, cv2.LINE_AA)
    cv2.circle(image, (460, 460), 18, (155, 160, 165), 2, cv2.LINE_AA)
    corners = ((100.0, 100.0), (820.0, 100.0), (820.0, 820.0), (100.0, 820.0))

    result = recognize_board(image, board_size=19, corners=corners)

    point = Point(9, 9)
    assert result.stones[point] is Color.WHITE
    assert point not in result.uncertain_points


@pytest.mark.parametrize("nested_layout", [False, True])
def test_axis_aligned_fallback_accepts_opencv_hough_layouts(
    monkeypatch: pytest.MonkeyPatch,
    nested_layout: bool,
) -> None:
    edges = np.zeros((260, 260), dtype=np.uint8)
    coordinates = np.linspace(20, 240, 9, dtype=np.int32)
    segments = np.asarray(
        [
            *([x, 10, x, 250] for x in coordinates),
            *([10, y, 250, y] for y in coordinates),
        ],
        dtype=np.int32,
    )
    hough_result = segments.reshape(-1, 1, 4) if nested_layout else segments
    monkeypatch.setattr(
        recognition_module.cv2,
        "HoughLinesP",
        lambda *_args, **_kwargs: hough_result,
    )

    corners = recognition_module._detect_axis_aligned_grid(edges, 1.0)

    assert np.asarray(corners) == pytest.approx(
        np.asarray(((20.0, 20.0), (240.0, 20.0), (240.0, 240.0), (20.0, 240.0))),
        abs=12.0,
    )


@pytest.mark.parametrize("size", [9, 13, 19])
def test_recognition_corrects_perspective_from_manual_grid_corners(size: int) -> None:
    image, corners, expected = _synthetic_board(size=size)
    source = np.asarray(corners, dtype=np.float32)
    destination = np.asarray(
        [(145, 85), (770, 135), (825, 780), (85, 830)],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(source, destination)
    perspective = cv2.warpPerspective(
        image,
        transform,
        (920, 920),
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(28, 31, 34),
    )
    manual = tuple((float(x), float(y)) for x, y in destination)

    result = recognize_board(
        perspective,
        board_size=size,
        corners=manual,  # type: ignore[arg-type]
    )

    assert result.board_size == size
    assert result.stones == expected


def _board_with_touching_coordinates(
    size: int,
) -> tuple[np.ndarray, np.ndarray, dict[Point, Color]]:
    """Synthetic edge stones and nearby labels reproduce the reported contour merge."""
    image, corners, expected = _synthetic_board(size=size, include_stones=False)
    image[np.all(image == (28, 31, 34), axis=2)] = (72, 164, 218)
    cell = 720 / (size - 1)
    radius = round(cell * 0.44)
    expected = {
        Point(x, 0): Color.BLACK if x % 2 else Color.WHITE
        for x in range(size - 7, size - 1)
    }
    expected.update(
        {Point(size - 1, y): Color.WHITE if y % 2 else Color.BLACK for y in range(1, 6)}
    )
    expected[Point(3, 3)] = Color.BLACK
    expected[Point(size // 2, size // 2)] = Color.WHITE
    for point, color in expected.items():
        center = (round(100 + point.x * cell), round(100 + point.y * cell))
        fill = (12, 14, 16) if color is Color.BLACK else (245, 245, 241)
        cv2.circle(image, center, radius, fill, -1, cv2.LINE_AA)
    for index in range(size):
        coordinate = round(100 + index * cell)
        cv2.putText(
            image, chr(65 + index), (coordinate - 7, 100 - radius - 5),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (25, 31, 38), 2, cv2.LINE_AA,
        )
        cv2.putText(
            image, str(size - index), (820 + radius + 5, coordinate + 6),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (25, 31, 38), 2, cv2.LINE_AA,
        )
    return image, np.asarray(corners), expected


@pytest.mark.parametrize("size", [9, 13, 19])
def test_auto_corners_resist_labels_touching_edge_stones(size: int) -> None:
    image, corners, expected = _board_with_touching_coordinates(size)

    result = recognize_board(image)

    assert result.board_size == size
    assert np.asarray(result.corners) == pytest.approx(corners, abs=5.0)
    assert result.stones == expected


@pytest.mark.parametrize("size", [9, 13, 19])
def test_auto_corners_choose_grid_inside_a_larger_panel_frame(size: int) -> None:
    board, corners, expected = _synthetic_board(size=size)
    image = np.full((1200, 1200, 3), (28, 31, 34), dtype=np.uint8)
    image[140:1060, 140:1060] = board
    cv2.rectangle(image, (25, 25), (1175, 1175), (150, 150, 150), 3)

    result = recognize_board(image)

    assert result.board_size == size
    assert np.asarray(result.corners) == pytest.approx(np.asarray(corners) + 140, abs=5.0)
    assert result.stones == expected


@pytest.mark.parametrize("size", [9, 13, 19])
def test_auto_corners_recognize_perspective_grids(size: int) -> None:
    image, corners, expected = _synthetic_board(size=size)
    destination = np.asarray([(110, 100), (810, 110), (830, 820), (90, 830)], np.float32)
    transform = cv2.getPerspectiveTransform(np.asarray(corners, np.float32), destination)
    perspective = cv2.warpPerspective(
        image, transform, (920, 920), borderValue=(28, 31, 34)
    )

    result = recognize_board(perspective)

    assert result.board_size == size
    assert np.asarray(result.corners) == pytest.approx(destination, abs=5.0)
    assert result.stones == expected


def test_auto_corners_do_not_treat_a_plain_frame_as_a_grid() -> None:
    image = np.full((920, 920, 3), (180, 180, 180), dtype=np.uint8)
    cv2.rectangle(image, (80, 80), (840, 840), (20, 20, 20), 3)

    with pytest.raises(recognition_module.RecognitionError):
        recognize_board(image, board_size=19)


def test_repeated_recognition_and_explicit_size_keep_the_same_grid() -> None:
    image, corners, expected = _board_with_touching_coordinates(19)
    original = image.copy()
    for size in (None, 19, None):
        result = recognize_board(image, board_size=size)
        assert result.board_size == 19
        assert np.asarray(result.corners) == pytest.approx(corners, abs=5.0)
        assert result.stones == expected
    assert np.array_equal(image, original)


def test_automatic_corners_still_bridge_small_breaks_in_the_border() -> None:
    image, corners, _expected = _synthetic_board(include_stones=False)
    image[np.all(image == (28, 31, 34), axis=2)] = (72, 164, 218)
    for coordinate in range(180, 800, 80):
        for border in (100, 820):
            cv2.rectangle(
                image, (coordinate - 2, border - 4), (coordinate + 2, border + 4),
                (72, 164, 218), -1,
            )
            cv2.rectangle(
                image, (border - 4, coordinate - 2), (border + 4, coordinate + 2),
                (72, 164, 218), -1,
            )

    result = recognize_board(image)

    assert result.board_size == 19
    assert np.asarray(result.corners) == pytest.approx(np.asarray(corners), abs=5.0)
    assert result.stones == {}


@pytest.mark.parametrize("factor", [0.75, 1.25, 1.75])
def test_labelled_board_corners_stay_aligned_across_image_sizes(factor: float) -> None:
    image, corners, expected = _board_with_touching_coordinates(19)
    resized = cv2.resize(
        image, None, fx=factor, fy=factor,
        interpolation=cv2.INTER_AREA if factor < 1 else cv2.INTER_CUBIC,
    )

    result = recognize_board(resized)

    assert result.board_size == 19
    assert np.asarray(result.corners) / factor == pytest.approx(corners, abs=5.0)
    assert result.stones == expected
