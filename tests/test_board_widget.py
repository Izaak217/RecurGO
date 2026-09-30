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


def test_hidden_dead_stones_remain_clickable_and_visibility_changes_only_pixels(
    qtbot: QtBot,
) -> None:
    widget = BoardWidget()
    widget.resize(620, 620)
    point = Point(2, 2)
    state = BoardState.from_setup({point: Color.BLACK}, size=5)
    widget.set_position(state, None)
    widget.set_scoring_mode(True, frozenset({point}), edit_ownership=True)
    qtbot.addWidget(widget)
    widget.show()
    hidden = widget.grab().toImage()
    with qtbot.waitSignal(widget.score_point_clicked) as clicked:
        qtbot.mouseClick(widget, Qt.MouseButton.LeftButton, pos=_screen_point(widget, point))
    assert clicked.args == [2, 2]
    widget.set_show_dead_stones(True)
    shown = widget.grab().toImage()
    assert hidden != shown
    widget.set_show_dead_stones(False)
    assert widget.grab().toImage() == hidden
    assert widget._state == state


def test_live_and_review_marker_centers_agree_at_the_display_cutoff(qtbot: QtBot) -> None:
    from recurgo.domain.score_review import live_assignments

    widget = BoardWidget()
    widget.resize(620, 620)
    widget.set_position(BoardState.new(size=5), None)
    values = [0.08, -0.08, 0.3, -0.3, 0.0] * 5
    widget.set_ownership(values)
    qtbot.addWidget(widget)
    widget.show()
    live = widget.grab().toImage()
    owners = live_assignments(values, 5)
    assert owners is not None
    widget.set_ownership([float(v) if v in (-1, 1) else 0.0 for v in owners])
    widget.set_scoring_mode(True, edit_ownership=True)
    widget.set_scoring_assignments(owners)
    review = widget.grab().toImage()
    for index, owner in enumerate(owners):
        if owner == 2:
            continue
        center = _screen_point(widget, Point(index % 5, index // 5))
        assert live.pixelColor(center) == review.pixelColor(center)
