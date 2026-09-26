"""Clipboard/file workflow for recognizing and correcting a static Go position."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from recurgo.domain import BoardState, Color, Point
from recurgo.i18n import Language, localize_error, tr
from recurgo.vision import BoardRecognition, RecognitionError, load_image, recognize_board

from .board_widget import BoardWidget
from .i18n import localize_dialog_buttons

ImageArray = NDArray[np.uint8]
Corner = tuple[float, float]


@dataclass(frozen=True, slots=True)
class ImagePositionOptions:
    board_size: int
    stones: dict[Point, Color]
    to_play: Color


class _ImageCanvas(QWidget):
    corners_changed = Signal()

    def __init__(self, parent: QWidget | None = None, *, language: Language = "en") -> None:
        super().__init__(parent)
        self.language = language
        self._image = QImage()
        self._corners: list[Corner] = []
        self._selecting = False
        self.setMinimumSize(480, 480)

    @property
    def corners(self) -> tuple[Corner, Corner, Corner, Corner] | None:
        if len(self._corners) != 4:
            return None
        return (self._corners[0], self._corners[1], self._corners[2], self._corners[3])

    def set_image(self, image: QImage) -> None:
        self._image = image
        self._corners.clear()
        self._selecting = False
        self.update()

    def set_corners(self, corners: tuple[Corner, Corner, Corner, Corner]) -> None:
        self._corners = list(corners)
        self._selecting = False
        self.update()

    def begin_corner_selection(self) -> None:
        self._corners.clear()
        self._selecting = True
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt API name
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#151719"))
        target = self._image_rect()
        if self._image.isNull() or target.isEmpty():
            painter.setPen(QColor("#aeb6bf"))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                tr(self.language, "请粘贴或选择棋盘图片", "Paste or choose a board image"),
            )
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(target, self._image)
        if not self._corners:
            return
        points = [self._image_to_widget(point, target) for point in self._corners]
        painter.setPen(QPen(QColor("#35d07f"), 2.5))
        if len(points) > 1:
            for first, second in zip(points, points[1:], strict=False):
                painter.drawLine(first, second)
        if len(points) == 4:
            painter.drawLine(points[-1], points[0])
        painter.setBrush(QColor("#ff9f1c"))
        for index, point in enumerate(points, start=1):
            painter.drawEllipse(point, 6.0, 6.0)
            painter.drawText(point + QPointF(8.0, -8.0), str(index))

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API name
        if (
            event.button() != Qt.MouseButton.LeftButton
            or not self._selecting
            or self._image.isNull()
        ):
            return
        target = self._image_rect()
        if not target.contains(event.position()):
            return
        self._corners.append(self._widget_to_image(event.position(), target))
        if len(self._corners) == 4:
            self._selecting = False
        self.corners_changed.emit()
        self.update()

    def _image_rect(self) -> QRectF:
        if self._image.isNull():
            return QRectF()
        scale = min(self.width() / self._image.width(), self.height() / self._image.height())
        width = self._image.width() * scale
        height = self._image.height() * scale
        return QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)

    def _widget_to_image(self, point: QPointF, target: QRectF) -> Corner:
        x = (point.x() - target.left()) * self._image.width() / target.width()
        y = (point.y() - target.top()) * self._image.height() / target.height()
        return float(x), float(y)

    def _image_to_widget(self, point: Corner, target: QRectF) -> QPointF:
        return QPointF(
            target.left() + point[0] * target.width() / self._image.width(),
            target.top() + point[1] * target.height() / self._image.height(),
        )


class ImageImportDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, *, language: Language = "en") -> None:
        super().__init__(parent)
        self.language = language
        self.setWindowTitle(self._tr("从图片识别棋局", "Recognize a game from an image"))
        self.resize(1220, 760)
        self._source_image = QImage()
        self._source_bgr: ImageArray | None = None
        self._recognition: BoardRecognition | None = None
        self._stones: dict[Point, Color] = {}
        self._attention: frozenset[Point] = frozenset()
        self._manual_selection = False

        root = QVBoxLayout(self)
        controls = QHBoxLayout()
        paste = QPushButton(self._tr("从剪贴板粘贴", "Paste from clipboard"))
        paste.clicked.connect(self._paste_clipboard)
        upload = QPushButton(self._tr("选择图片…", "Choose image…"))
        upload.clicked.connect(self._choose_file)
        rotate_left = QPushButton(self._tr("左旋", "Rotate left"))
        rotate_left.clicked.connect(lambda: self._transform_image("left"))
        rotate_right = QPushButton(self._tr("右旋", "Rotate right"))
        rotate_right.clicked.connect(lambda: self._transform_image("right"))
        mirror = QPushButton(self._tr("镜像", "Mirror"))
        mirror.clicked.connect(lambda: self._transform_image("mirror"))
        manual = QPushButton(self._tr("手选四角", "Select four corners"))
        manual.clicked.connect(self._begin_manual_corners)
        self.size_combo = QComboBox()
        self.size_combo.addItem(self._tr("自动判断路数", "Detect board size"), None)
        for size in (19, 13, 9):
            self.size_combo.addItem(self._tr(f"{size} 路", f"{size}×{size}"), size)
        recognize = QPushButton(self._tr("开始识别", "Recognize"))
        recognize.clicked.connect(self._recognize)
        for button in (paste, upload, rotate_left, rotate_right, mirror, manual):
            controls.addWidget(button)
        controls.addStretch(1)
        controls.addWidget(QLabel(self._tr("棋盘大小", "Board size")))
        controls.addWidget(self.size_combo)
        controls.addWidget(recognize)
        root.addLayout(controls)

        content = QHBoxLayout()
        source_column = QVBoxLayout()
        source_column.addWidget(
            QLabel(
                self._tr(
                    "原图（手选四角时请依次点击四个最外侧网格交点）",
                    "Source image (select the four outermost grid intersections)",
                )
            )
        )
        self.canvas = _ImageCanvas(language=language)
        self.canvas.corners_changed.connect(self._corners_changed)
        source_column.addWidget(self.canvas, 1)
        self.source_status = QLabel(self._tr("尚未载入图片", "No image loaded"))
        self.source_status.setWordWrap(True)
        source_column.addWidget(self.source_status)
        content.addLayout(source_column, 1)

        result_column = QVBoxLayout()
        result_column.addWidget(
            QLabel(
                self._tr(
                    "识别结果（点击交叉点：空 → 黑 → 白 → 空）",
                    "Result (click an intersection: empty → Black → White → empty)",
                )
            )
        )
        self.result_board = BoardWidget()
        self.result_board.setMinimumSize(480, 480)
        self.result_board.point_clicked.connect(self._cycle_point)
        result_column.addWidget(self.result_board, 1)
        self.result_status = QLabel(
            self._tr(
                "识别完成后，可在这里人工校正棋子。橙色圆圈表示低置信度点。",
                "After recognition, correct stones here. Orange circles mark uncertain points.",
            )
        )
        self.result_status.setWordWrap(True)
        result_column.addWidget(self.result_status)
        content.addLayout(result_column, 1)
        root.addLayout(content, 1)

        player_row = QHBoxLayout()
        player_row.addWidget(QLabel(self._tr("识别确认后，当前轮到：", "Next to play:")))
        self.black_to_play = QRadioButton(self._tr("黑方落子", "Black"))
        self.white_to_play = QRadioButton(self._tr("白方落子", "White"))
        self.player_group = QButtonGroup(self)
        self.player_group.addButton(self.black_to_play)
        self.player_group.addButton(self.white_to_play)
        self.player_group.buttonToggled.connect(self._update_accept_enabled)
        player_row.addWidget(self.black_to_play)
        player_row.addWidget(self.white_to_play)
        player_row.addStretch(1)
        root.addLayout(player_row)

        note = QLabel(
            self._tr(
                "图片只能恢复当前静态局面，无法推断历史手顺、既往提子数或劫争历史；创建后将从此局面开始保存和分析。",
                "An image recovers only the current position. It cannot reveal move history, earlier captures, or ko history. Saving and analysis start from this position.",
            )
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #d6a84f;")
        root.addWidget(note)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        localize_dialog_buttons(self.buttons, language)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            self._tr("创建识别局面", "Create position")
        )
        self.buttons.accepted.connect(self._accept_if_ready)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)
        self._update_accept_enabled()

    def _tr(self, chinese: str, english: str) -> str:
        return tr(self.language, chinese, english)

    def options(self) -> ImagePositionOptions:
        if self._recognition is None:
            raise RuntimeError("No recognized position")
        if self.black_to_play.isChecked():
            to_play = Color.BLACK
        elif self.white_to_play.isChecked():
            to_play = Color.WHITE
        else:
            raise RuntimeError("Side to play has not been selected")
        return ImagePositionOptions(self._recognition.board_size, dict(self._stones), to_play)

    def _choose_file(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            self._tr("选择棋盘图片", "Choose board image"),
            "",
            self._tr(
                "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp);;所有文件 (*)",
                "Image files (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*)",
            ),
        )
        if not selected:
            return
        try:
            bgr = load_image(Path(selected))
        except RecognitionError as exc:
            QMessageBox.warning(
                self,
                self._tr("图片读取失败", "Could not read image"),
                localize_error(str(exc), self.language),
            )
            return
        image = QImage(selected)
        if image.isNull():
            QMessageBox.warning(
                self,
                self._tr("图片读取失败", "Could not read image"),
                self._tr("Qt 无法显示该图片", "Qt cannot display this image"),
            )
            return
        self._set_source(image, bgr, Path(selected).name)

    def _paste_clipboard(self) -> None:
        image = QApplication.clipboard().image()
        if image.isNull():
            QMessageBox.information(
                self,
                self._tr("剪贴板没有图片", "No image on clipboard"),
                self._tr("请先复制一张棋盘图片。", "Copy a board image first."),
            )
            return
        self._set_source(
            image, _qimage_to_bgr(image), self._tr("剪贴板图片", "Clipboard image")
        )

    def _set_source(self, image: QImage, bgr: ImageArray, label: str) -> None:
        self._source_image = image.convertToFormat(QImage.Format.Format_RGBA8888)
        self._source_bgr = bgr
        self._recognition = None
        self._stones.clear()
        self._attention = frozenset()
        self._manual_selection = False
        self.canvas.set_image(self._source_image)
        self.result_board.set_position(BoardState.new(), None)
        self.result_board.set_attention_points(frozenset())
        self.source_status.setText(
            self._tr(
                f"已载入：{label} · {image.width()}×{image.height()}；可直接识别，失败时再手选四个外沿网格交点。",
                f"Loaded: {label} · {image.width()}×{image.height()}. Try recognition first; select the four outer grid corners if it fails.",
            )
        )
        self.result_status.setText(self._tr("等待识别", "Waiting for recognition"))
        self._update_accept_enabled()

    def _transform_image(self, operation: str) -> None:
        source = self._source_bgr
        if source is None:
            return
        if operation == "left":
            transformed = cv2.rotate(source, cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif operation == "right":
            transformed = cv2.rotate(source, cv2.ROTATE_90_CLOCKWISE)
        else:
            transformed = cv2.flip(source, 1)
        bgr = np.asarray(transformed, dtype=np.uint8)
        self._source_image = _bgr_to_qimage(bgr)
        self._set_source(self._source_image, bgr, self._tr("已变换图片", "Transformed image"))

    def _begin_manual_corners(self) -> None:
        if self._source_bgr is None:
            QMessageBox.information(
                self,
                self._tr("尚未载入图片", "No image loaded"),
                self._tr("请先粘贴或选择图片。", "Paste or choose an image first."),
            )
            return
        self._manual_selection = True
        self.canvas.begin_corner_selection()
        self.source_status.setText(
            self._tr(
                "请依次点击棋盘四个最外侧网格交点；顺序不影响识别。",
                "Click the four outermost grid intersections; the order does not matter.",
            )
        )

    def _corners_changed(self) -> None:
        count = 0 if self.canvas.corners is None else 4
        if count == 4:
            self.source_status.setText(
                self._tr(
                    "四个角点已选择，点击“开始识别”。",
                    "Four corners selected. Click Recognize.",
                )
            )

    def _recognize(self) -> None:
        if self._source_bgr is None:
            QMessageBox.information(
                self,
                self._tr("尚未载入图片", "No image loaded"),
                self._tr("请先粘贴或选择图片。", "Paste or choose an image first."),
            )
            return
        corners = self.canvas.corners if self._manual_selection else None
        if self._manual_selection and corners is None:
            QMessageBox.information(
                self,
                self._tr("角点尚未完成", "Corners incomplete"),
                self._tr(
                    "请在原图上选择四个网格角点。",
                    "Select four grid corners in the source image.",
                ),
            )
            return
        board_size_value = self.size_combo.currentData()
        board_size = int(board_size_value) if isinstance(board_size_value, int) else None
        try:
            recognition = recognize_board(
                self._source_bgr,
                board_size=board_size,
                corners=corners,
            )
        except RecognitionError as exc:
            self.result_status.setText(
                self._tr(
                    "识别未完成；请按提示校准棋盘。",
                    "Recognition incomplete; calibrate the board as instructed.",
                )
            )
            QMessageBox.warning(
                self,
                self._tr("识别未完成", "Recognition incomplete"),
                self._tr(
                    f"{exc}\n\n可以选择棋盘路数，再点击“手选四角”进行校准。",
                    f"{localize_error(str(exc), self.language)}\n\nChoose the board size, then select four corners to calibrate.",
                ),
            )
            return
        except Exception as exc:
            self.result_status.setText(
                self._tr(
                    "识别器发生内部错误，未更改当前局面。",
                    "Recognizer error; the current game was not changed.",
                )
            )
            QMessageBox.warning(
                self,
                self._tr("识别器错误", "Recognizer error"),
                self._tr(
                    f"图片识别器遇到未预期错误：{type(exc).__name__}: {exc}\n\n请重试，或选择棋盘路数后使用“手选四角”。",
                    f"Unexpected error: {type(exc).__name__}: {exc}\n\nRetry or choose a board size and select four corners.",
                ),
            )
            return
        self._recognition = recognition
        self._stones = dict(recognition.stones)
        self._attention = recognition.uncertain_points
        self._manual_selection = False
        self.canvas.set_corners(recognition.corners)
        self._refresh_result_board()
        black = sum(color is Color.BLACK for color in self._stones.values())
        white = sum(color is Color.WHITE for color in self._stones.values())
        self.source_status.setText(
            self._tr(
                f"已定位 {recognition.board_size} 路棋盘",
                f"Located {recognition.board_size}×{recognition.board_size} board",
            )
        )
        self.result_status.setText(
            self._tr(
                f"识别到黑棋 {black} 颗、白棋 {white} 颗；低置信度点 {len(self._attention)} 个。请校正后选择当前落子方。",
                f"Found {black} Black and {white} White stones; {len(self._attention)} uncertain points. Correct them, then choose the next player.",
            )
        )
        self._update_accept_enabled()

    def _cycle_point(self, x: int, y: int) -> None:
        if self._recognition is None:
            return
        point = Point(x, y)
        current = self._stones.get(point)
        if current is None:
            self._stones[point] = Color.BLACK
        elif current is Color.BLACK:
            self._stones[point] = Color.WHITE
        else:
            self._stones.pop(point)
        self._attention = frozenset(value for value in self._attention if value != point)
        self._refresh_result_board()

    def _refresh_result_board(self) -> None:
        if self._recognition is None:
            return
        to_play = Color.WHITE if self.white_to_play.isChecked() else Color.BLACK
        state = BoardState.from_setup(
            self._stones,
            size=self._recognition.board_size,
            to_play=to_play,
        )
        self.result_board.set_position(state, None)
        self.result_board.set_attention_points(self._attention)

    def _update_accept_enabled(
        self,
        _button: object | None = None,
        _checked: bool = False,
    ) -> None:
        ready = self._recognition is not None and (
            self.black_to_play.isChecked() or self.white_to_play.isChecked()
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ready)
        if ready:
            self._refresh_result_board()

    def _accept_if_ready(self) -> None:
        if self._recognition is None:
            return
        if not (self.black_to_play.isChecked() or self.white_to_play.isChecked()):
            QMessageBox.information(
                self,
                self._tr("请选择落子方", "Choose next player"),
                self._tr(
                    "请确认当前轮到黑方还是白方落子。",
                    "Confirm whether Black or White plays next.",
                ),
            )
            return
        self.accept()


def _qimage_to_bgr(image: QImage) -> ImageArray:
    converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
    array = np.frombuffer(converted.bits(), dtype=np.uint8).reshape(
        converted.height(),
        converted.width(),
        4,
    )
    return np.asarray(cv2.cvtColor(array, cv2.COLOR_RGBA2BGR), dtype=np.uint8)


def _bgr_to_qimage(image: ImageArray) -> QImage:
    rgb = np.asarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), dtype=np.uint8)
    height, width = rgb.shape[:2]
    return QImage(rgb.data, width, height, width * 3, QImage.Format.Format_RGB888).copy()
