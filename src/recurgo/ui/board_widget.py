"""Interactive, scalable Go board widget."""

from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from recurgo.domain.board import BoardState, Color, IllegalMove
from recurgo.domain.coordinates import GTP_COLUMNS, Point

from .preferences import BOARD_THEMES, STONE_STYLES, AppPreferences


class BoardWidget(QWidget):
    point_clicked = Signal(int, int)
    score_point_clicked = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = BoardState.new()
        self._last_move: Point | None = None
        self._candidates: list[tuple[Point, int, float]] = []
        self._ownership: tuple[float, ...] | None = None
        self._hover_point: Point | None = None
        self._input_enabled = True
        self._scoring_mode = False
        self._dead_points: frozenset[Point] = frozenset()
        self._attention_points: frozenset[Point] = frozenset()
        self._preferences = AppPreferences()
        self._board_texture = QPixmap()
        self.setMouseTracking(True)
        self.setMinimumSize(520, 520)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self) -> QSize:
        return QSize(720, 720)

    def set_position(self, state: BoardState, last_move: Point | None) -> None:
        self._state = state
        self._last_move = last_move
        # A position change invalidates the previous node's ownership map. The
        # caller may immediately provide a cached map for the new node.
        self._ownership = None
        self._hover_point = None
        self.update()

    def set_preferences(self, preferences: AppPreferences) -> None:
        self._preferences = preferences
        self._board_texture = QPixmap(preferences.custom_board_path)
        self.update()

    @property
    def hover_point(self) -> Point | None:
        return self._hover_point

    @property
    def input_enabled(self) -> bool:
        return self._input_enabled

    def set_input_enabled(self, enabled: bool) -> None:
        self._input_enabled = enabled
        if not enabled:
            self._hover_point = None
        self.update()

    def set_scoring_mode(
        self,
        enabled: bool,
        dead_points: frozenset[Point] = frozenset(),
    ) -> None:
        self._scoring_mode = enabled
        self._dead_points = dead_points
        self._hover_point = None
        self.update()

    def set_candidates(self, candidates: list[tuple[Point, int, float]]) -> None:
        self._candidates = candidates
        self.update()

    def set_attention_points(self, points: frozenset[Point]) -> None:
        self._attention_points = points
        self.update()

    @property
    def ownership(self) -> tuple[float, ...] | None:
        return self._ownership

    def set_ownership(self, values: list[float] | None) -> None:
        """Set KataGo's board ownership map, or clear it with ``None``.

        KataGo reports values in [-1, 1], with positive values favouring
        Black and negative values favouring White. Invalid or incomplete maps
        are rejected so an old/misaligned overlay can never be drawn.
        """
        expected = self._state.size * self._state.size
        if values is None or len(values) != expected:
            self._ownership = None
        else:
            normalized: list[float] = []
            for value in values:
                number = float(value)
                if not math.isfinite(number):
                    self._ownership = None
                    self.update()
                    return
                normalized.append(max(-1.0, min(1.0, number)))
            self._ownership = tuple(normalized)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        origin_x, origin_y, cell = self._geometry()
        board_extent = cell * (self._state.size - 1)
        padding = cell * 0.58
        board_rect = QRectF(
            origin_x - padding,
            origin_y - padding,
            board_extent + padding * 2,
            board_extent + padding * 2,
        )
        theme = BOARD_THEMES[self._preferences.board_theme]
        if self._board_texture.isNull():
            wood = QLinearGradient(board_rect.topLeft(), board_rect.bottomRight())
            wood.setColorAt(0.0, QColor(theme.background))
            wood.setColorAt(1.0, QColor(theme.background_dark))
            painter.fillRect(board_rect, wood)
        else:
            painter.drawPixmap(board_rect.toRect(), self._board_texture)
            tint = QColor(theme.background)
            tint.setAlpha(36)
            painter.fillRect(board_rect, tint)

        painter.setPen(QPen(QColor(theme.line), max(1.0, cell * 0.025)))
        for index in range(self._state.size):
            offset = index * cell
            painter.drawLine(
                QPointF(origin_x, origin_y + offset),
                QPointF(origin_x + board_extent, origin_y + offset),
            )
            painter.drawLine(
                QPointF(origin_x + offset, origin_y),
                QPointF(origin_x + offset, origin_y + board_extent),
            )

        self._draw_star_points(painter, origin_x, origin_y, cell)
        self._draw_coordinates(painter, origin_x, origin_y, cell)
        self._draw_hover_preview(painter, origin_x, origin_y, cell)
        self._draw_stones(painter, origin_x, origin_y, cell)
        self._draw_attention_points(painter, origin_x, origin_y, cell)
        # Ownership markers must remain visible on top of stones so predicted
        # dead groups can be recognised, matching conventional Go counting UIs.
        self._draw_ownership(painter, origin_x, origin_y, cell)
        self._draw_candidates(painter, origin_x, origin_y, cell)
        self._draw_dead_stones(painter, origin_x, origin_y, cell)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or not self._input_enabled:
            return
        point = self._point_at(event.position())
        if point is None:
            return
        if self._scoring_mode:
            if self._state.stone_at(point) is not None:
                self.score_point_clicked.emit(point.x, point.y)
            return
        self.point_clicked.emit(point.x, point.y)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        point = self._point_at(event.position())
        if self._scoring_mode or (point is not None and not self._is_legal_preview(point)):
            point = None
        if point != self._hover_point:
            self._hover_point = point
            self.update()

    def leaveEvent(self, event: QEvent) -> None:
        del event
        if self._hover_point is not None:
            self._hover_point = None
            self.update()

    def _point_at(self, position: QPointF) -> Point | None:
        if not self._input_enabled:
            return None
        origin_x, origin_y, cell = self._geometry()
        x = round((position.x() - origin_x) / cell)
        y = round((position.y() - origin_y) / cell)
        if not (0 <= x < self._state.size and 0 <= y < self._state.size):
            return None
        center_x = origin_x + x * cell
        center_y = origin_y + y * cell
        distance = ((position.x() - center_x) ** 2 + (position.y() - center_y) ** 2) ** 0.5
        return Point(x, y) if distance <= cell * 0.48 else None

    def _is_legal_preview(self, point: Point) -> bool:
        if not self._input_enabled or self._state.is_game_over:
            return False
        try:
            self._state.play(point)
        except IllegalMove:
            return False
        return True

    def _geometry(self) -> tuple[float, float, float]:
        margin = 42.0
        usable = max(1.0, min(self.width(), self.height()) - margin * 2)
        cell = usable / (self._state.size - 1)
        extent = cell * (self._state.size - 1)
        return (self.width() - extent) / 2, (self.height() - extent) / 2, cell

    def _draw_star_points(
        self, painter: QPainter, origin_x: float, origin_y: float, cell: float
    ) -> None:
        if self._state.size == 19:
            indices = (3, 9, 15)
        elif self._state.size == 13:
            indices = (3, 6, 9)
        elif self._state.size == 9:
            indices = (2, 4, 6)
        else:
            return
        theme = BOARD_THEMES[self._preferences.board_theme]
        painter.setBrush(QColor(theme.star))
        painter.setPen(Qt.PenStyle.NoPen)
        radius = max(2.4, cell * 0.105)
        for x in indices:
            for y in indices:
                painter.drawEllipse(
                    QPointF(origin_x + x * cell, origin_y + y * cell),
                    radius,
                    radius,
                )

    def _draw_coordinates(
        self, painter: QPainter, origin_x: float, origin_y: float, cell: float
    ) -> None:
        font = QFont(self.font())
        font.setPointSizeF(max(7.0, cell * 0.22))
        painter.setFont(font)
        theme = BOARD_THEMES[self._preferences.board_theme]
        painter.setPen(QColor(theme.coordinate))
        for index in range(self._state.size):
            x = origin_x + index * cell
            y = origin_y + index * cell
            painter.drawText(
                QRectF(x - cell / 2, origin_y - cell * 1.15, cell, cell * 0.5),
                Qt.AlignmentFlag.AlignCenter,
                GTP_COLUMNS[index],
            )
            painter.drawText(
                QRectF(origin_x - cell * 1.1, y - cell / 2, cell * 0.5, cell),
                Qt.AlignmentFlag.AlignCenter,
                str(self._state.size - index),
            )

    def _draw_stones(
        self, painter: QPainter, origin_x: float, origin_y: float, cell: float
    ) -> None:
        radius = cell * 0.45
        for y in range(self._state.size):
            for x in range(self._state.size):
                point = Point(x, y)
                color = self._state.stone_at(point)
                if color is None:
                    continue
                center = QPointF(origin_x + x * cell, origin_y + y * cell)
                brush, outline = self._stone_brush(color, center, radius)
                painter.setBrush(brush)
                painter.setPen(QPen(outline, max(1.0, cell * 0.025)))
                painter.drawEllipse(center, radius, radius)

                if self._last_move == point:
                    marker = QColor("#f0c419") if color is Color.BLACK else QColor("#d22f27")
                    painter.setBrush(marker)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(center, max(2.5, cell * 0.11), max(2.5, cell * 0.11))

    def _draw_ownership(
        self, painter: QPainter, origin_x: float, origin_y: float, cell: float
    ) -> None:
        values = self._ownership
        if values is None:
            return
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        extent = max(5.0, cell * 0.30)
        for index, ownership in enumerate(values):
            strength = abs(ownership)
            if strength < 0.08:
                continue
            x = index % self._state.size
            y = index // self._state.size
            center = QPointF(origin_x + x * cell, origin_y + y * cell)
            # KataGo uses positive values for Black and negative values for
            # White. Small monochrome squares keep the board readable and also
            # work for final counting, unlike a full-cell red/blue heat map.
            marker = QColor("#050607" if ownership > 0 else "#f8f8f4")
            outline = QColor("#f8f8f4" if ownership > 0 else "#151719")
            painter.setBrush(marker)
            painter.setPen(QPen(outline, max(0.8, cell * 0.035)))
            painter.drawRect(
                QRectF(
                    center.x() - extent / 2,
                    center.y() - extent / 2,
                    extent,
                    extent,
                )
            )
        painter.restore()

    def _draw_attention_points(
        self,
        painter: QPainter,
        origin_x: float,
        origin_y: float,
        cell: float,
    ) -> None:
        if not self._attention_points:
            return
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#ff9f1c"), max(2.0, cell * 0.075)))
        radius = cell * 0.48
        for point in self._attention_points:
            center = QPointF(origin_x + point.x * cell, origin_y + point.y * cell)
            painter.drawEllipse(center, radius, radius)
        painter.restore()

    def _draw_hover_preview(
        self, painter: QPainter, origin_x: float, origin_y: float, cell: float
    ) -> None:
        point = self._hover_point
        if point is None:
            return
        center = QPointF(origin_x + point.x * cell, origin_y + point.y * cell)
        radius = cell * 0.45
        painter.save()
        painter.setOpacity(0.42)
        brush, outline = self._stone_brush(self._state.to_play, center, radius)
        painter.setBrush(brush)
        painter.setPen(QPen(outline, max(1.0, cell * 0.025)))
        painter.drawEllipse(center, radius, radius)
        painter.restore()

    def _stone_brush(
        self,
        color: Color,
        center: QPointF,
        radius: float,
    ) -> tuple[QBrush, QColor]:
        rendering = STONE_STYLES[self._preferences.stone_style].rendering
        if rendering == "flat":
            fill = QColor("#111315" if color is Color.BLACK else "#f2f1eb")
            outline = QColor("#000000" if color is Color.BLACK else "#aaa9a3")
            return QBrush(fill), outline

        gradient = QRadialGradient(
            center - QPointF(radius * 0.30, radius * 0.30),
            radius * 1.35,
        )
        if rendering == "matte":
            colors = (
                ("#45484c", "#17191b", "#050607", "#050607")
                if color is Color.BLACK
                else ("#faf9f3", "#deddd6", "#b8b7b0", "#999891")
            )
            gradient.setColorAt(0.0, QColor(colors[0]))
            gradient.setColorAt(0.62, QColor(colors[1]))
            gradient.setColorAt(1.0, QColor(colors[2]))
            return QBrush(gradient), QColor(colors[3])
        if rendering == "jade":
            colors = (
                ("#56716a", "#182f2c", "#071513", "#06100f")
                if color is Color.BLACK
                else ("#fffef1", "#e8e4c9", "#b8b38e", "#9f9a78")
            )
            gradient.setColorAt(0.0, QColor(colors[0]))
            gradient.setColorAt(0.52, QColor(colors[1]))
            gradient.setColorAt(1.0, QColor(colors[2]))
            return QBrush(gradient), QColor(colors[3])

        if color is Color.BLACK:
            gradient.setColorAt(0.0, QColor("#5b6067"))
            gradient.setColorAt(0.45, QColor("#24272b"))
            gradient.setColorAt(1.0, QColor("#050607"))
            outline = QColor("#000000")
        else:
            gradient.setColorAt(0.0, QColor("#ffffff"))
            gradient.setColorAt(0.7, QColor("#e5e6e3"))
            gradient.setColorAt(1.0, QColor("#b9bab7"))
            outline = QColor("#a7a8a5")
        return QBrush(gradient), outline

    def _draw_dead_stones(
        self, painter: QPainter, origin_x: float, origin_y: float, cell: float
    ) -> None:
        if not self._scoring_mode:
            return
        painter.save()
        painter.setPen(QPen(QColor("#e13f3f"), max(2.0, cell * 0.09)))
        offset = cell * 0.25
        for point in self._dead_points:
            center = QPointF(origin_x + point.x * cell, origin_y + point.y * cell)
            painter.drawLine(
                QPointF(center.x() - offset, center.y() - offset),
                QPointF(center.x() + offset, center.y() + offset),
            )
            painter.drawLine(
                QPointF(center.x() - offset, center.y() + offset),
                QPointF(center.x() + offset, center.y() - offset),
            )
        painter.restore()

    def _draw_candidates(
        self, painter: QPainter, origin_x: float, origin_y: float, cell: float
    ) -> None:
        for point, rank, winrate in self._candidates:
            if self._state.stone_at(point) is not None:
                continue
            center = QPointF(origin_x + point.x * cell, origin_y + point.y * cell)
            color = QColor("#21c86b" if rank == 1 else "#43a8ff")
            color.setAlpha(205 if rank == 1 else 165)
            painter.setBrush(color)
            painter.setPen(QPen(QColor("#ecfff3"), max(1.0, cell * 0.035)))
            painter.drawEllipse(center, cell * 0.38, cell * 0.38)
            font = QFont(self.font())
            font.setBold(True)
            font.setPointSizeF(max(6.5, cell * 0.18))
            painter.setFont(font)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                QRectF(
                    center.x() - cell * 0.38,
                    center.y() - cell * 0.28,
                    cell * 0.76,
                    cell * 0.3,
                ),
                Qt.AlignmentFlag.AlignCenter,
                str(rank),
            )
            painter.drawText(
                QRectF(
                    center.x() - cell * 0.4,
                    center.y(),
                    cell * 0.8,
                    cell * 0.25,
                ),
                Qt.AlignmentFlag.AlignCenter,
                f"{winrate:.0f}%",
            )
