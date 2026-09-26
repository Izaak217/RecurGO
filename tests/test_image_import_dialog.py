from __future__ import annotations

import cv2
import numpy as np
import pytest
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QDialogButtonBox
from pytestqt.qtbot import QtBot

from recurgo.domain import Color, Point
from recurgo.ui import image_import_dialog as image_import_module
from recurgo.ui.image_import_dialog import ImageImportDialog, _bgr_to_qimage, _ImageCanvas


def _board_image() -> tuple[np.ndarray, tuple[tuple[float, float], ...]]:
    image = np.full((820, 820, 3), (70, 160, 215), dtype=np.uint8)
    start, end = 50, 770
    cell = (end - start) / 18
    for index in range(19):
        coordinate = round(start + index * cell)
        cv2.line(image, (start, coordinate), (end, coordinate), (24, 28, 34), 2)
        cv2.line(image, (coordinate, start), (coordinate, end), (24, 28, 34), 2)
    for point, fill in (
        (Point(3, 3), (10, 12, 14)),
        (Point(15, 15), (245, 245, 240)),
    ):
        center = (round(start + point.x * cell), round(start + point.y * cell))
        cv2.circle(image, center, round(cell * 0.44), fill, -1, cv2.LINE_AA)
    corners = (
        (float(start), float(start)),
        (float(end), float(start)),
        (float(end), float(end)),
        (float(start), float(end)),
    )
    return image, corners


def test_image_import_requires_correction_and_explicit_side_to_play(
    qtbot: QtBot,
) -> None:
    image, corners = _board_image()
    dialog = ImageImportDialog()
    qtbot.addWidget(dialog)
    dialog._set_source(_bgr_to_qimage(image), image, "测试图片")
    dialog.size_combo.setCurrentIndex(dialog.size_combo.findData(19))
    dialog.canvas.set_corners(corners)  # type: ignore[arg-type]
    dialog._manual_selection = True

    dialog._recognize()

    assert dialog._recognition is not None
    assert dialog._stones == {
        Point(3, 3): Color.BLACK,
        Point(15, 15): Color.WHITE,
    }
    ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok.isEnabled()

    dialog.black_to_play.setChecked(True)
    assert ok.isEnabled()
    assert dialog.options().to_play is Color.BLACK

    dialog._cycle_point(3, 3)
    assert dialog.options().stones[Point(3, 3)] is Color.WHITE
    dialog._cycle_point(3, 3)
    assert Point(3, 3) not in dialog.options().stones


def test_image_import_reports_unexpected_recognizer_errors(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image, _corners = _board_image()
    dialog = ImageImportDialog(language="zh")
    qtbot.addWidget(dialog)
    dialog._set_source(_bgr_to_qimage(image), image, "测试图片")
    warnings: list[tuple[str, str]] = []

    def fail_recognition(*_args: object, **_kwargs: object) -> None:
        raise TypeError("unexpected layout")

    monkeypatch.setattr(image_import_module, "recognize_board", fail_recognition)
    monkeypatch.setattr(
        image_import_module.QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )

    dialog._recognize()

    assert dialog._recognition is None
    assert dialog.result_status.text() == "识别器发生内部错误，未更改当前局面。"
    assert warnings and warnings[0][0] == "识别器错误"


def test_source_preview_preserves_thin_grid_lines_when_scaled_down(qtbot: QtBot) -> None:
    source_size = 955
    preview_size = 537
    source = QImage(source_size, source_size, QImage.Format.Format_RGB888)
    source.fill(QColor("white"))
    source_painter = QPainter(source)
    source_painter.setPen(QColor("black"))
    grid_lines = [round(27 + index * (901 / 18)) for index in range(19)]
    for y in grid_lines:
        source_painter.drawLine(27, y, 928, y)
    source_painter.end()

    canvas = _ImageCanvas()
    qtbot.addWidget(canvas)
    canvas.setFixedSize(preview_size, preview_size)
    canvas.set_image(source)

    rendered = QImage(preview_size, preview_size, QImage.Format.Format_RGB888)
    rendered.fill(QColor("white"))
    canvas.render(rendered)

    pixels = np.frombuffer(rendered.bits(), dtype=np.uint8).reshape(
        rendered.height(), rendered.bytesPerLine()
    )
    rgb = pixels[:, : rendered.width() * 3].reshape(
        rendered.height(), rendered.width(), 3
    )
    for source_y in grid_lines:
        preview_y = source_y * preview_size / source_size
        low = max(0, int(np.floor(preview_y)) - 2)
        high = min(preview_size, int(np.ceil(preview_y)) + 3)
        darkest_row = float(rgb[low:high, 60:480].mean(axis=(1, 2)).min())
        assert darkest_row < 245.0
