from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QPoint, QPointF
from PySide6.QtTest import QTest
from pytestqt.qtbot import QtBot

from recurgo.domain import (
    BoardState,
    Color,
    GameTree,
    MoveReview,
    Point,
    summarize_reviews,
)
from recurgo.engine import AnalysisUpdate
from recurgo.storage import GameRepository
from recurgo.ui import MainWindow
from recurgo.ui.preferences import AppPreferences


class FakeAudio:
    def __init__(self) -> None:
        self.muted = False
        self.moves: list[bool] = []

    def set_muted(self, muted: bool) -> None:
        self.muted = muted

    def play_move(self, *, captured: bool) -> None:
        self.moves.append(captured)


class FakeBatchEngine:
    def __init__(self) -> None:
        self.queries: list[dict[str, object]] = []
        self.stop_count = 0
        self.runtime = SimpleNamespace(
            engine_version="test",
            model_sha256="test-model",
        )

    def stop_analysis(self) -> None:
        self.stop_count += 1

    def analyze(self, **kwargs: object) -> str:
        self.queries.append(kwargs)
        return f"request-{len(self.queries)}"

    def shutdown(self) -> None:
        return


def _chinese_repository(path: Path) -> GameRepository:
    repository = GameRepository(path)
    repository.save_setting("appearance_audio", {"language": "zh"})
    return repository


def test_window_restores_and_persists_appearance_audio_preferences(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    repository = _chinese_repository(tmp_path / "preferences.db")
    repository.save_setting(
        "appearance_audio",
        AppPreferences(
            board_theme="dark",
            stone_style="flat",
            placement_sound="crisp",
            capture_sound="soft",
            volume=61,
            muted=True,
        ).to_mapping(),
    )
    tree = GameTree()
    record = repository.create_game(tree)
    audio = FakeAudio()
    window = MainWindow(repository, record, tree, audio_feedback=audio)
    qtbot.addWidget(window)

    assert window.preferences.board_theme == "dark"
    assert window.preferences.stone_style == "flat"
    assert window.board_widget._preferences.board_theme == "dark"
    assert audio.muted is True
    assert window.mute_action.isChecked()

    window.mute_action.setChecked(False)
    saved = repository.load_setting("appearance_audio")
    assert saved is not None
    assert saved["muted"] is False


def _move_mouse_to_plot(
    qtbot: QtBot,
    plot: object,
    view_position: QPointF,
) -> None:
    """Move the real Qt test cursor to a position expressed in plot coordinates."""

    scene_position = plot.plotItem.vb.mapViewToScene(view_position)
    viewport_position = plot.mapFromScene(scene_position)
    _move_mouse_to_widget(qtbot, plot.viewport(), viewport_position)


def _move_mouse_to_widget(qtbot: QtBot, widget: object, position: QPoint) -> None:
    """Use QWindow mouse events; PySide 6.11's QWidget overload drops them on Windows."""

    top_level = widget.window()
    window_position = widget.mapTo(top_level, position)
    window_handle = top_level.windowHandle()
    assert window_handle is not None
    QTest.mouseMove(window_handle, window_position)
    qtbot.wait(20)


def _tooltip_is_inside_plot(plot: object, tooltip: object) -> bool:
    tooltip_bounds = tooltip.mapRectToScene(tooltip.boundingRect())
    plot_bounds = plot.plotItem.vb.sceneBoundingRect().adjusted(2.0, 2.0, -2.0, -2.0)
    return plot_bounds.contains(tooltip_bounds)


def test_main_window_places_and_autosaves_move(qtbot: QtBot, tmp_path: Path) -> None:
    repository = _chinese_repository(tmp_path / "ui.db")
    tree = GameTree()
    record = repository.create_game(tree)
    audio = FakeAudio()
    window = MainWindow(repository, record, tree, audio_feedback=audio)
    qtbot.addWidget(window)
    window.show()

    window._play_point(3, 3)
    assert window.tree.current.state.move_number == 1
    assert window.tree.current.state.stone_at(Point(3, 3)) is not None

    loaded_record, loaded_tree = repository.load_game(record.id)
    assert loaded_record.id == record.id
    assert loaded_tree.current.state.move_number == 1
    assert audio.moves == [False]


def test_capture_uses_capture_audio_and_mute_control(qtbot: QtBot, tmp_path: Path) -> None:
    state = BoardState.from_setup(
        {
            Point(1, 1): Color.WHITE,
            Point(0, 1): Color.BLACK,
            Point(1, 0): Color.BLACK,
            Point(2, 1): Color.BLACK,
        },
        size=5,
        to_play=Color.BLACK,
    )
    repository = _chinese_repository(tmp_path / "capture.db")
    tree = GameTree(state)
    record = repository.create_game(tree)
    audio = FakeAudio()
    window = MainWindow(repository, record, tree, audio_feedback=audio)
    qtbot.addWidget(window)

    window._play_point(1, 2)
    window.mute_action.setChecked(True)

    assert audio.moves == [True]
    assert audio.muted


def test_winrate_chart_immediately_follows_current_variation_path(
    qtbot: QtBot, tmp_path: Path
) -> None:
    repository = _chinese_repository(tmp_path / "chart.db")
    tree = GameTree()
    record = repository.create_game(tree)
    nodes = [tree.root]
    for point in (
        Point(3, 3),
        Point(15, 15),
        Point(3, 15),
        Point(15, 3),
        Point(9, 9),
    ):
        node, _created = tree.play(point)
        repository.save_node(record.id, node)
        nodes.append(node)
    window = MainWindow(
        repository,
        record,
        tree,
        audio_feedback=FakeAudio(),
    )
    qtbot.addWidget(window)
    window._analysis_by_node = {node.id: 40.0 + node.state.move_number for node in nodes}
    window._refresh()
    assert window._current_winrate_series()[0] == [0, 1, 2, 3, 4, 5]

    tree.go_to(nodes[3].id)
    window._refresh()

    assert window._current_winrate_series()[0] == [0, 1, 2, 3]
    assert nodes[5].id in window._analysis_by_node

    branch, _created = tree.play(Point(10, 10))
    window._analysis_by_node[branch.id] = 61.0
    window._refresh()
    assert window._current_winrate_series()[0] == [0, 1, 2, 3, 4]
    assert window._current_winrate_series()[1][-1] == 61.0
    assert window._nearest_winrate(3.7) == (4, 61.0)


def test_review_navigation_can_jump_to_each_move_and_persists_position(
    qtbot: QtBot, tmp_path: Path
) -> None:
    repository = _chinese_repository(tmp_path / "navigation.db")
    tree = GameTree()
    record = repository.create_game(tree)
    nodes = [tree.root]
    for point in (Point(3, 3), Point(15, 15), Point(3, 15)):
        node, _created = tree.play(point)
        repository.save_node(record.id, node)
        nodes.append(node)
    window = MainWindow(repository, record, tree, audio_feedback=FakeAudio())
    qtbot.addWidget(window)

    window._navigate_review(1)

    assert window.tree.current.id == nodes[1].id
    assert window.navigation_label.text() == "第 1 / 3 手"
    _loaded_record, loaded_tree = repository.load_game(record.id)
    assert loaded_tree.current.id == nodes[1].id

    window._navigate_last()
    assert window.tree.current.id == nodes[3].id


def test_full_game_analysis_queues_every_position_and_persists_results(
    qtbot: QtBot, tmp_path: Path
) -> None:
    repository = _chinese_repository(tmp_path / "full-review.db")
    tree = GameTree()
    record = repository.create_game(tree)
    move, _created = tree.play(Point(3, 3))
    repository.save_node(record.id, move)
    window = MainWindow(repository, record, tree, audio_feedback=FakeAudio())
    qtbot.addWidget(window)
    engine = FakeBatchEngine()
    window.engine = engine  # type: ignore[assignment]

    window._start_full_game_analysis()

    assert window._full_analysis_active
    assert engine.queries[0]["node_id"] == tree.root_id
    window._analysis_update(
        AnalysisUpdate(
            "root",
            tree.root_id,
            "full_game",
            {"rootInfo": {"visits": 200}},
        )
    )
    assert window.full_analysis_progress.value() == 200
    assert "200/800 visits" in window.full_analysis_progress.format()
    root_payload: dict[str, object] = {
        "rootInfo": {"winrate": 0.55, "scoreLead": 1.0},
        "moveInfos": [{"move": "D16"}],
    }
    window._analysis_finished(
        AnalysisUpdate("root", tree.root_id, "full_game", root_payload)
    )
    assert engine.queries[1]["node_id"] == move.id
    move_payload: dict[str, object] = {
        "rootInfo": {"winrate": 0.48, "scoreLead": -0.5},
        "moveInfos": [{"move": "Q16"}],
    }
    window._analysis_finished(
        AnalysisUpdate("move", move.id, "full_game", move_payload)
    )

    assert not window._full_analysis_active
    saved = repository.analysis_snapshots_for_game(
        record.id,
        cache_prefix="full-game-800",
    )
    assert saved == {
        tree.root_id: root_payload,
        move.id: move_payload,
    }


def test_review_panel_has_zoom_tabs_and_no_persistent_move_cursor(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    repository = _chinese_repository(tmp_path / "review-panel.db")
    tree = GameTree()
    record = repository.create_game(tree)
    window = MainWindow(repository, record, tree, audio_feedback=FakeAudio())
    qtbot.addWidget(window)

    assert window.review_tabs.count() == 5
    assert [
        window.review_tabs.tabText(index)
        for index in range(window.review_tabs.count())
    ] == ["胜率走势", "着法质量", "问题手", "吻合度", "概览"]
    assert window.winrate_horizontal_zoom.currentText() == "1×"
    assert window.winrate_vertical_zoom.currentText() == "1×"
    assert not window.winrate_cursor.isVisible()
    assert not hasattr(window, "review_position_cursor")


def test_match_view_uses_two_side_timeline_and_summary_card(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    repository = _chinese_repository(tmp_path / "match-view.db")
    tree = GameTree()
    record = repository.create_game(tree)
    window = MainWindow(repository, record, tree, audio_feedback=FakeAudio())
    qtbot.addWidget(window)
    reviews = [
        MoveReview(
            node_id=f"node-{move_number}",
            move_number=move_number,
            color=Color.BLACK if move_number % 2 else Color.WHITE,
            move="D4",
            best_move="D4",
            top_three=("D4", "Q16", "Q4"),
            black_winrate_before=50.0,
            black_winrate_after=50.0,
            winrate_loss=0.5 if move_number <= 4 else 4.0,
            score_loss=0.2,
            matches_best=move_number in {1, 3, 6},
            matches_top_three=move_number != 4,
            grade="好手" if move_number in {1, 2, 3, 5, 6} else "疑问手",
        )
        for move_number in range(1, 7)
    ]

    window._populate_match_plot(summarize_reviews(reviews), reviews)

    assert len(window.match_scatter.points()) == 6
    assert len(window._match_graphics) >= 5
    graphic_count = len(window._match_graphics)
    assert "黑方" in window.match_black_summary.text()
    assert "白方" in window.match_white_summary.text()
    assert "一选" in window.match_black_summary.text()
    assert "前三" in window.match_black_summary.text()
    assert "好手" in window.match_white_summary.text()
    assert window._good_streaks(
        [review for review in reviews if review.color is Color.BLACK]
    )
    assert "黄色" not in window.match_details.text()
    assert "疑似AI" not in window.match_details.text()
    assert all(type(item).__name__ != "TextItem" for item in window._match_graphics)
    assert all(point.brush().color().alpha() == 0 for point in window.match_scatter.points())

    window.review_tabs.setCurrentIndex(3)
    window.resize(1400, 900)
    window.show()
    qtbot.wait(50)

    # Track selection uses the pointer's Y coordinate before finding the nearest move.
    # At x=3.8 white's move 4 is closer, but the black track must still resolve move 3.
    _move_mouse_to_plot(qtbot, window.match_plot, QPointF(3.8, 1.60))
    qtbot.waitUntil(window.match_cursor.isVisible)
    assert "第 3 手" in window.match_tooltip.toPlainText()
    assert "黑方" in window.match_tooltip.toPlainText()
    assert "D4" in window.match_tooltip.toPlainText()

    # Conversely, the white track at x=3.2 must resolve white's move 4.
    _move_mouse_to_plot(qtbot, window.match_plot, QPointF(3.2, 0.40))
    qtbot.waitUntil(lambda: "第 4 手" in window.match_tooltip.toPlainText())
    assert "白方" in window.match_tooltip.toPlainText()

    # Tooltips remain inside the plot when the user zooms to the first/last move.
    window.match_plot.setXRange(1, 6, padding=0)
    qtbot.wait(20)
    _move_mouse_to_plot(qtbot, window.match_plot, QPointF(1.0, 1.60))
    qtbot.waitUntil(lambda: "第 1 手" in window.match_tooltip.toPlainText())
    assert _tooltip_is_inside_plot(window.match_plot, window.match_tooltip)
    _move_mouse_to_plot(qtbot, window.match_plot, QPointF(6.0, 0.40))
    qtbot.waitUntil(lambda: "第 6 手" in window.match_tooltip.toPlainText())
    assert _tooltip_is_inside_plot(window.match_plot, window.match_tooltip)

    # Moving outside the data ViewBox hides both transient hover items.
    _move_mouse_to_widget(qtbot, window.match_plot.viewport(), QPoint(1, 1))
    qtbot.waitUntil(lambda: not window.match_tooltip.isVisible())
    assert not window.match_cursor.isVisible()

    # In-memory screenshot acceptance verifies the strict red/blue/green visual palette.
    image = window.review_tabs.currentWidget().grab().toImage()
    rendered_colors = {
        image.pixelColor(x, y).name()
        for x in range(0, image.width(), 2)
        for y in range(0, image.height(), 2)
    }
    assert {"#ff5964", "#5aa5fa", "#7ed321"} <= rendered_colors

    window._populate_match_plot(summarize_reviews(reviews), reviews)
    assert len(window._match_graphics) == graphic_count


def test_problem_view_real_mouse_hover_shows_move_and_losses(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    repository = _chinese_repository(tmp_path / "problem-hover.db")
    tree = GameTree()
    record = repository.create_game(tree)
    window = MainWindow(repository, record, tree, audio_feedback=FakeAudio())
    qtbot.addWidget(window)
    reviews = [
        MoveReview(
            node_id="black-problem",
            move_number=1,
            color=Color.BLACK,
            move="D4",
            best_move="Q16",
            top_three=("Q16", "Q4", "D16"),
            black_winrate_before=50.0,
            black_winrate_after=42.5,
            winrate_loss=7.5,
            score_loss=3.2,
            matches_best=False,
            matches_top_three=False,
            grade="坏手",
        ),
        MoveReview(
            node_id="white-problem",
            move_number=2,
            color=Color.WHITE,
            move="Q16",
            best_move="D16",
            top_three=("D16", "Q4", "D4"),
            black_winrate_before=42.5,
            black_winrate_after=55.0,
            winrate_loss=12.5,
            score_loss=5.6,
            matches_best=False,
            matches_top_three=False,
            grade="严重失误",
        ),
    ]
    window._populate_problem_plot(reviews)
    window.review_tabs.setCurrentIndex(2)
    window.resize(1400, 900)
    window.show()
    qtbot.wait(50)

    window.problem_plot.setXRange(1, 2, padding=0)
    qtbot.wait(20)
    _move_mouse_to_plot(qtbot, window.problem_plot, QPointF(1.0, 2.0))
    qtbot.waitUntil(window.problem_cursor.isVisible)
    tooltip_text = window.problem_tooltip.toPlainText()
    assert "第 1 手" in tooltip_text
    assert "黑方" in tooltip_text
    assert "落点 D4" in tooltip_text
    assert "等级：坏手" in tooltip_text
    assert "胜率损失：7.5%" in tooltip_text
    assert "目差损失：3.2目" in tooltip_text
    assert _tooltip_is_inside_plot(window.problem_plot, window.problem_tooltip)

    _move_mouse_to_plot(qtbot, window.problem_plot, QPointF(2.0, -3.0))
    qtbot.waitUntil(lambda: "第 2 手" in window.problem_tooltip.toPlainText())
    assert "白方" in window.problem_tooltip.toPlainText()
    assert "严重失误" in window.problem_tooltip.toPlainText()
    assert _tooltip_is_inside_plot(window.problem_plot, window.problem_tooltip)

    _move_mouse_to_widget(qtbot, window.problem_plot.viewport(), QPoint(1, 1))
    qtbot.waitUntil(lambda: not window.problem_tooltip.isVisible())
    assert not window.problem_cursor.isVisible()


def test_human_can_play_white_and_ai_opens_as_black(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    repository = _chinese_repository(tmp_path / "white-player.db")
    tree = GameTree()
    record = repository.create_game(tree, mode="assisted", human_color="white")
    window = MainWindow(repository, record, tree, audio_feedback=FakeAudio())
    qtbot.addWidget(window)
    engine = FakeBatchEngine()
    window.engine = engine  # type: ignore[assignment]
    window._review_mode_active = False  # explicit "继续对弈" choice

    window._request_analysis()

    assert engine.queries[-1]["purpose"] == "ai_move"
    assert engine.queries[-1]["node_id"] == tree.root_id
    assert not window.board_widget.input_enabled

    window._analysis_finished(
        AnalysisUpdate(
            "black-opening",
            tree.root_id,
            "ai_move",
            {
                "rootInfo": {"winrate": 0.5},
                "moveInfos": [{"move": "D16", "order": 0}],
            },
        )
    )

    assert window.tree.current.move is not None
    assert window.tree.current.move.color is Color.BLACK
    assert window.tree.current.state.to_play is Color.WHITE
    assert window.board_widget.input_enabled


def test_finishing_game_disables_play_and_persists_result(qtbot: QtBot, tmp_path: Path) -> None:
    repository = _chinese_repository(tmp_path / "finish.db")
    tree = GameTree()
    record = repository.create_game(tree)
    window = MainWindow(
        repository,
        record,
        tree,
        audio_feedback=FakeAudio(),
    )
    qtbot.addWidget(window)

    window._finish_game("B+1.25")
    reloaded, _tree = repository.load_game(record.id)

    assert window.record.status == "completed"
    assert not window.board_widget.input_enabled
    assert reloaded.result == "B+1.25"
    assert "黑胜1¼子" in window.game_info.text()
