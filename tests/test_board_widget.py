from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from pytestqt.qtbot import QtBot

from recurgo.domain import BoardState, Color, Point
from recurgo.ui.board_widget import BoardWidget
from recurgo.ui.preferences import AppPreferences


def _screen_point(widget: BoardWidget, point: Point) -> QPoint:
    origin_x, origin_y, cell = widget._geometry()
    return QPoint(
        round(origin_x + point.x * cell),
        round(origin_y + point.y * cell),
    )


def _move_mouse(widget: BoardWidget, point: QPoint) -> None:
    position = QPointF(point)
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        position,
        position,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mouseMoveEvent(event)


def test_hover_preview_tracks_only_legal_enabled_points(qtbot: QtBot) -> None:
    widget = BoardWidget()
    widget.resize(620, 620)
    qtbot.addWidget(widget)
    widget.show()

    _move_mouse(widget, _screen_point(widget, Point(3, 3)))
    assert widget.hover_point == Point(3, 3)

    occupied = BoardState.new().play(Point(3, 3))
    widget.set_position(occupied, Point(3, 3))
    _move_mouse(widget, _screen_point(widget, Point(3, 3)))
    assert widget.hover_point is None

    widget.set_input_enabled(False)
    _move_mouse(widget, _screen_point(widget, Point(4, 4)))
    assert widget.hover_point is None


def test_ownership_map_is_validated_clamped_and_cleared_on_position_change(
    qtbot: QtBot,
) -> None:
    widget = BoardWidget()
    widget.set_position(BoardState.new(size=5), None)
    qtbot.addWidget(widget)

    values = [0.0] * 25
    values[0] = -2.0
    values[-1] = 1.5
    widget.set_ownership(values)

    assert widget.ownership is not None
    assert widget.ownership[0] == -1.0
    assert widget.ownership[-1] == 1.0

    widget.set_ownership([0.0])
    assert widget.ownership is None

    widget.set_ownership(values)
    widget.set_position(BoardState.new(size=5), None)
    assert widget.ownership is None


def test_ownership_uses_monochrome_square_markers_visible_over_stones(
    qtbot: QtBot,
) -> None:
    state = BoardState.from_setup({Point(1, 1): Color.BLACK}, size=5)
    widget = BoardWidget()
    widget.resize(620, 620)
    widget.set_position(state, None)
    values = [0.0] * 25
    values[1 * state.size + 1] = -1.0
    values[3 * state.size + 3] = 1.0
    widget.set_ownership(values)
    qtbot.addWidget(widget)
    widget.show()
    qtbot.wait(20)

    image = widget.grab().toImage()
    white_marker = _screen_point(widget, Point(1, 1))
    black_marker = _screen_point(widget, Point(3, 3))

    assert image.pixelColor(white_marker).name() == "#f8f8f4"
    assert image.pixelColor(black_marker).name() == "#050607"


def test_builtin_board_and_stone_styles_are_applied(qtbot: QtBot) -> None:
    state = BoardState.from_setup({Point(3, 3): Color.BLACK}, size=9)
    widget = BoardWidget()
    widget.resize(620, 620)
    widget.set_position(state, None)
    widget.set_preferences(AppPreferences(board_theme="dark", stone_style="flat"))
    qtbot.addWidget(widget)
    widget.show()
    qtbot.wait(20)

    image = widget.grab().toImage()
    stone_center = _screen_point(widget, Point(3, 3))

    assert image.pixelColor(stone_center).name() == "#111315"
