"""OpenCV-based, fully local recognition of stones on Go-board images."""

from __future__ import annotations

import importlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from recurgo.domain import Color, Point

try:
    cv2: Any = importlib.import_module("cv2")
except ImportError:  # pragma: no cover - exercised by the UI fallback
    cv2 = None

ImageArray = NDArray[np.uint8]
Corner = tuple[float, float]


class RecognitionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BoardRecognition:
    board_size: int
    stones: dict[Point, Color]
    confidences: dict[Point, float]
    corners: tuple[Corner, Corner, Corner, Corner]
    warped: ImageArray

    @property
    def uncertain_points(self) -> frozenset[Point]:
        return frozenset(
            point for point, confidence in self.confidences.items() if confidence < 0.72
        )


def opencv_available() -> bool:
    return cv2 is not None


def load_image(path: Path) -> ImageArray:
    _require_opencv()
    try:
        encoded = np.fromfile(path, dtype=np.uint8)
    except OSError as exc:
        raise RecognitionError(f"无法读取图片：{exc}") from exc
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise RecognitionError("图片格式无效或文件已经损坏")
    return np.asarray(image, dtype=np.uint8)


def recognize_board(
    image: ImageArray,
    *,
    board_size: int | None = None,
    corners: tuple[Corner, Corner, Corner, Corner] | None = None,
) -> BoardRecognition:
    """Recognize a 9x9, 13x13, or 19x19 board from a BGR image."""
    _require_opencv()
    if image.ndim != 3 or image.shape[2] not in (3, 4):
        raise RecognitionError("识别输入必须是彩色图片")
    if min(image.shape[:2]) < 160:
        raise RecognitionError("图片分辨率过低，棋盘短边至少需要 160 像素")
    if board_size is not None and board_size not in (9, 13, 19):
        raise RecognitionError("仅支持 9 路、13 路和 19 路棋盘")
    bgr = image[:, :, :3].copy()

    manual_corners = corners is not None
    ordered = _order_corners(corners) if corners is not None else _detect_board_corners(bgr)
    rough = _warp_to_square(bgr, ordered, extent=760, padding=0)
    size, x_range, y_range = _detect_grid(rough, board_size)
    if not manual_corners:
        ordered = _refine_original_corners(ordered, x_range, y_range, rough.shape[1])
    warped = _warp_to_square(bgr, ordered, extent=760, padding=38)
    stones, confidences = _classify_intersections(warped, size, padding=38)
    return BoardRecognition(size, stones, confidences, ordered, warped)


def _require_opencv() -> None:
    if cv2 is None:
        raise RecognitionError("OpenCV 尚未安装，图片识谱功能暂不可用")


def _order_corners(
    corners: tuple[Corner, Corner, Corner, Corner] | None,
) -> tuple[Corner, Corner, Corner, Corner]:
    if corners is None:
        raise RecognitionError("没有可用的棋盘角点")
    points = np.asarray(list(corners), dtype=np.float32)
    if points.shape != (4, 2):
        raise RecognitionError("棋盘角点必须恰好为四个")
    sums = points.sum(axis=1)
    differences = np.diff(points, axis=1).reshape(-1)
    ordered = np.asarray(
        [
            points[np.argmin(sums)],
            points[np.argmin(differences)],
            points[np.argmax(sums)],
            points[np.argmax(differences)],
        ],
        dtype=np.float32,
    )
    area = abs(float(cv2.contourArea(ordered)))
    if area < 2_500:
        raise RecognitionError("选择的棋盘区域过小或四个角点顺序无效")
    return _array_to_corners(ordered)


def _array_to_corners(
    points: NDArray[np.floating[Any]],
) -> tuple[Corner, Corner, Corner, Corner]:
    return (
        (float(points[0, 0]), float(points[0, 1])),
        (float(points[1, 0]), float(points[1, 1])),
        (float(points[2, 0]), float(points[2, 1])),
        (float(points[3, 0]), float(points[3, 1])),
    )


def _detect_board_corners(image: ImageArray) -> tuple[Corner, Corner, Corner, Corner]:
    height, width = image.shape[:2]
    scale = min(1.0, 1400.0 / max(height, width))
    working = (
        cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if scale < 1.0
        else image
    )
    gray = cv2.cvtColor(working, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 45, 135)
    edges = cv2.morphologyEx(
        edges,
        cv2.MORPH_CLOSE,
        np.ones((5, 5), dtype=np.uint8),
        iterations=2,
    )
    contours, _hierarchy = cv2.findContours(
        edges,
        cv2.RETR_LIST,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    image_area = float(working.shape[0] * working.shape[1])
    candidates: list[tuple[float, NDArray[np.float32]]] = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < image_area * 0.12:
            continue
        perimeter = float(cv2.arcLength(contour, True))
        polygon = cv2.approxPolyDP(contour, 0.025 * perimeter, True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon):
            continue
        raw = polygon.reshape(4, 2).astype(np.float32)
        ordered = np.asarray(_order_corners(_array_to_corners(raw)), dtype=np.float32)
        top = np.linalg.norm(ordered[1] - ordered[0])
        bottom = np.linalg.norm(ordered[2] - ordered[3])
        left = np.linalg.norm(ordered[3] - ordered[0])
        right = np.linalg.norm(ordered[2] - ordered[1])
        horizontal = max(1.0, float((top + bottom) / 2.0))
        vertical = max(1.0, float((left + right) / 2.0))
        aspect_score = min(horizontal, vertical) / max(horizontal, vertical)
        if aspect_score < 0.48:
            continue
        coverage = area / image_area
        border_penalty = 0.35 if coverage > 0.94 else 0.0
        candidates.append((coverage * aspect_score - border_penalty, ordered))
    if not candidates:
        return _detect_axis_aligned_grid(edges, scale)
    points = max(candidates, key=lambda item: item[0])[1] / scale
    return _order_corners(_array_to_corners(points))


def _detect_axis_aligned_grid(
    edges: ImageArray,
    scale: float,
) -> tuple[Corner, Corner, Corner, Corner]:
    height, width = edges.shape
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180.0,
        threshold=max(45, min(height, width) // 10),
        minLineLength=min(height, width) * 0.36,
        maxLineGap=min(height, width) * 0.035,
    )
    if lines is None:
        raise RecognitionError("未能自动定位棋盘，请手动点击棋盘的四个角")
    raw_lines = np.asarray(lines, dtype=np.float32)
    if raw_lines.size % 4 != 0:
        raise RecognitionError("直线检测结果格式异常，请手动点击棋盘的四个角")
    # OpenCV 4 commonly returns (N, 1, 4), while OpenCV 5 may return
    # (N, 4). Normalising both layouts avoids treating a coordinate as a line.
    segments = raw_lines.reshape(-1, 4)
    vertical: list[float] = []
    horizontal: list[float] = []
    for raw in segments:
        x1, y1, x2, y2 = map(float, raw)
        angle = abs(math.degrees(math.atan2(y2 - y1, x2 - x1)))
        if angle < 18 or angle > 162:
            horizontal.append((y1 + y2) / 2.0)
        elif 72 < angle < 108:
            vertical.append((x1 + x2) / 2.0)
    if len(vertical) < 5 or len(horizontal) < 5:
        raise RecognitionError("未能自动定位完整网格，请手动点击棋盘的四个角")
    x0, x1 = np.percentile(vertical, (4, 96))
    y0, y1 = np.percentile(horizontal, (4, 96))
    if (x1 - x0) * (y1 - y0) < width * height * 0.10:
        raise RecognitionError("检测到的棋盘区域过小，请手动选择四个角")
    return _order_corners(
        (
            (float(x0 / scale), float(y0 / scale)),
            (float(x1 / scale), float(y0 / scale)),
            (float(x1 / scale), float(y1 / scale)),
            (float(x0 / scale), float(y1 / scale)),
        )
    )


def _warp_to_square(
    image: ImageArray,
    corners: tuple[Corner, Corner, Corner, Corner],
    *,
    extent: int,
    padding: int,
) -> ImageArray:
    source = np.asarray(corners, dtype=np.float32)
    target = np.asarray(
        [
            (padding, padding),
            (padding + extent, padding),
            (padding + extent, padding + extent),
            (padding, padding + extent),
        ],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(source, target)
    side = extent + padding * 2
    return np.asarray(
        cv2.warpPerspective(
            image,
            transform,
            (side, side),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        ),
        dtype=np.uint8,
    )


def _detect_grid(
    square: ImageArray,
    requested_size: int | None,
) -> tuple[int, tuple[float, float], tuple[float, float]]:
    gray = cv2.cvtColor(square, cv2.COLOR_BGR2GRAY)
    stone_centers = _detect_stone_centers(square)
    block_size = max(15, (min(gray.shape) // 28) | 1)
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block_size,
        5,
    )
    length = max(20, min(gray.shape) // 7)
    vertical_mask = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, length)),
    )
    horizontal_mask = cv2.morphologyEx(
        binary,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (length, 1)),
    )
    vertical_projection = vertical_mask.mean(axis=0)
    horizontal_projection = horizontal_mask.mean(axis=1)
    sizes = (requested_size,) if requested_size is not None else (19, 13, 9)
    results: list[tuple[float, int, tuple[float, float], tuple[float, float]]] = []
    for size in sizes:
        x_score, x_range = _fit_regular_lines(
            vertical_projection,
            size,
            stone_centers[:, 0],
        )
        y_score, y_range = _fit_regular_lines(
            horizontal_projection,
            size,
            stone_centers[:, 1],
        )
        results.append(((x_score + y_score) / 2.0, size, x_range, y_range))
    score, size, x_range, y_range = max(results, key=lambda item: item[0])
    if score < 8.0:
        if requested_size is None:
            raise RecognitionError("网格线不够清晰，请手动选择棋盘四角并指定路数")
        return size, (0.0, float(square.shape[1] - 1)), (
            0.0,
            float(square.shape[0] - 1),
        )
    return size, x_range, y_range


def _detect_stone_centers(square: ImageArray) -> NDArray[np.float64]:
    """Find reliable stone-like blobs to support grid fitting on dense boards."""
    gray = cv2.cvtColor(square, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(square, cv2.COLOR_BGR2HSV)
    board_luma = float(np.median(gray))
    board_saturation = float(np.median(hsv[:, :, 1]))
    black_limit = min(115.0, board_luma - 45.0)
    white_saturation_limit = max(60.0, board_saturation * 0.60)
    masks = (
        np.asarray(gray < black_limit, dtype=np.uint8) * 255,
        np.asarray(
            (gray > board_luma + 15.0) & (hsv[:, :, 1] < white_saturation_limit),
            dtype=np.uint8,
        )
        * 255,
    )

    scale = min(gray.shape) / 760.0
    kernel_size = max(3, round(min(gray.shape) / 110.0) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    minimum_area = 180.0 * scale * scale
    maximum_area = 2_200.0 * scale * scale
    minimum_diameter = 14.0 * scale
    maximum_diameter = 60.0 * scale
    centers: list[tuple[float, float]] = []
    for mask in masks:
        opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        component_count, _labels, stats, component_centers = cv2.connectedComponentsWithStats(
            opened,
            8,
        )
        for index in range(1, component_count):
            _x, _y, width, height, area = map(float, stats[index])
            if not minimum_area <= area <= maximum_area:
                continue
            if not (
                minimum_diameter <= width <= maximum_diameter
                and minimum_diameter <= height <= maximum_diameter
            ):
                continue
            if min(width, height) / max(width, height) < 0.65:
                continue
            center_x, center_y = component_centers[index]
            centers.append((float(center_x), float(center_y)))
    return np.asarray(centers, dtype=np.float64).reshape(-1, 2)


def _fit_regular_lines(
    projection: NDArray[np.float64],
    count: int,
    feature_positions: NDArray[np.float64] | None = None,
) -> tuple[float, tuple[float, float]]:
    length = len(projection)
    smoothed = np.convolve(projection, np.ones(3) / 3.0, mode="same")
    best_score = -math.inf
    best_range = (0.0, float(length - 1))
    for start in np.linspace(0.0, length * 0.16, 17):
        for end in np.linspace(length * 0.84, length - 1.0, 17):
            spacing = (end - start) / (count - 1)
            if spacing < 8.0:
                continue

            positions = np.linspace(start, end, count)

            def response_at(position: float) -> float:
                center = int(round(position))
                low = max(0, center - 2)
                high = min(length, center + 3)
                return float(smoothed[low:high].max(initial=0.0))

            line_responses = [response_at(float(position)) for position in positions]
            line_score = float(np.percentile(line_responses, 35)) * 0.55 + float(
                np.mean(line_responses)
            ) * 0.45

            # A 19x19 grid can otherwise look like a very strong 9x9 grid when
            # every other line is sampled. Real grid lines halfway between the
            # candidate lines are therefore evidence of harmonic aliasing.
            midpoints = (positions[:-1] + positions[1:]) / 2.0
            midpoint_responses = [response_at(float(position)) for position in midpoints]
            alias_score = float(np.percentile(midpoint_responses, 35)) * 0.55 + float(
                np.mean(midpoint_responses)
            ) * 0.45
            coverage = max(0.0, min(1.0, (end - start) / max(1.0, length - 1.0)))
            score = (line_score - alias_score * 0.65) * (0.75 + coverage * 0.25)
            opposite_margin = float(length - 1) - end
            margin_imbalance = abs(start - opposite_margin) / max(1.0, float(length))
            score -= margin_imbalance * 50.0
            if feature_positions is not None and len(feature_positions) >= 4:
                normalized = (feature_positions - start) / spacing
                nearest = np.rint(normalized)
                residual = np.abs(normalized - nearest)
                inside = (nearest >= 0.0) & (nearest < count)
                alignment = float(
                    np.mean(np.exp(-np.square(residual / 0.20)) * inside)
                )
                reliability = min(1.0, len(feature_positions) / 12.0)
                score += alignment * reliability * 22.0
            if score > best_score:
                best_score = score
                best_range = (float(start), float(end))
    return float(best_score), best_range


def _refine_original_corners(
    original: tuple[Corner, Corner, Corner, Corner],
    x_range: tuple[float, float],
    y_range: tuple[float, float],
    side: int,
) -> tuple[Corner, Corner, Corner, Corner]:
    source = np.asarray(original, dtype=np.float32)
    target = np.asarray(
        [(0, 0), (side - 1, 0), (side - 1, side - 1), (0, side - 1)],
        dtype=np.float32,
    )
    inverse = cv2.getPerspectiveTransform(target, source)
    x0, x1 = x_range
    y0, y1 = y_range
    refined_square = np.asarray([[(x0, y0), (x1, y0), (x1, y1), (x0, y1)]], dtype=np.float32)
    refined = cv2.perspectiveTransform(refined_square, inverse)[0]
    return _order_corners(_array_to_corners(refined))


def _classify_intersections(
    warped: ImageArray,
    board_size: int,
    *,
    padding: int,
) -> tuple[dict[Point, Color], dict[Point, float]]:
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(warped, cv2.COLOR_BGR2HSV)
    extent = warped.shape[0] - padding * 2
    cell = extent / (board_size - 1)

    background_samples: list[float] = []
    saturation_samples: list[float] = []
    sample_radius = max(2, round(cell * 0.09))
    for y in range(board_size - 1):
        for x in range(board_size - 1):
            cx = round(padding + (x + 0.5) * cell)
            cy = round(padding + (y + 0.5) * cell)
            rows = slice(cy - sample_radius, cy + sample_radius + 1)
            columns = slice(cx - sample_radius, cx + sample_radius + 1)
            background_samples.append(float(np.median(gray[rows, columns])))
            saturation_samples.append(float(np.median(hsv[rows, columns, 1])))
    board_luma = float(np.median(background_samples))
    board_saturation = float(np.median(saturation_samples))

    stones: dict[Point, Color] = {}
    confidences: dict[Point, float] = {}
    radius = max(4, round(cell * 0.34))
    yy, xx = np.ogrid[-radius : radius + 1, -radius : radius + 1]
    circle = xx * xx + yy * yy <= radius * radius
    for y in range(board_size):
        for x in range(board_size):
            cx = round(padding + x * cell)
            cy = round(padding + y * cell)
            gray_patch = gray[cy - radius : cy + radius + 1, cx - radius : cx + radius + 1]
            saturation_patch = hsv[
                cy - radius : cy + radius + 1,
                cx - radius : cx + radius + 1,
                1,
            ]
            if gray_patch.shape != circle.shape:
                continue
            luminance = gray_patch[circle]
            saturation = saturation_patch[circle]
            median_luma = float(np.median(luminance))
            median_saturation = float(np.median(saturation))
            dark_fraction = float(np.mean(luminance < board_luma - 28.0))
            light_fraction = float(np.mean(luminance > board_luma + 24.0))
            black_score = max(0.0, (board_luma - median_luma) / 46.0) + dark_fraction
            white_score = (
                max(0.0, (median_luma - board_luma) / 38.0)
                + light_fraction * 0.85
                + max(0.0, (board_saturation - median_saturation) / 110.0)
            )
            point = Point(x, y)
            if black_score >= 0.72 and black_score > white_score + 0.18:
                stones[point] = Color.BLACK
                confidence = min(
                    1.0,
                    0.68
                    + max(0.0, black_score - 0.72) * 0.22
                    + max(0.0, black_score - white_score - 0.18) * 0.22,
                )
            elif white_score >= 0.68 and white_score > black_score + 0.16:
                stones[point] = Color.WHITE
                confidence = min(
                    1.0,
                    0.68
                    + max(0.0, white_score - 0.68) * 0.22
                    + max(0.0, white_score - black_score - 0.16) * 0.22,
                )
            else:
                distance = max(black_score / 0.72, white_score / 0.68)
                confidence = max(0.45, min(1.0, 1.0 - distance * 0.46))
            confidences[point] = confidence
    return stones, confidences
