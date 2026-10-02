from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMenu
from pytestqt.qtbot import QtBot

from recurgo.domain import GameTree, Point
from recurgo.engine import PRESETS, AnalysisUpdate, EngineFailure, EngineFailureKind
from recurgo.storage import GameRepository
from recurgo.ui import MainWindow
from recurgo.ui.analysis_settings_dialog import AnalysisSettings, AnalysisSettingsDialog


class SilentAudio:
    def set_muted(self, _muted: bool) -> None:
        return

    def play_move(self, *, captured: bool) -> None:
        return


class RecordingEngine(QObject):
    status_changed = Signal(str)
    failure_reported = Signal(object)
    analysis_updated = Signal(object)
    analysis_finished = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.runtime = SimpleNamespace(engine_version="test", model_sha256="test-model")
        self.queries: list[dict[str, object]] = []
        self.stop_count = 0

    def analyze(self, **kwargs: object) -> str:
        self.queries.append(kwargs)
        return f"request-{len(self.queries)}"

    def stop_analysis(self) -> None:
        self.stop_count += 1

    def shutdown(self) -> None:
        return

    def retry_last_request(self) -> str | None:
        return self.analyze(**self.queries[-1]) if self.queries else None


def _window(
    repository: GameRepository, qtbot: QtBot,
) -> tuple[MainWindow, RecordingEngine]:
    latest = repository.latest_game()
    if latest is None:
        tree = GameTree()
        record = repository.create_game(tree)
    else:
        record, tree = latest
    engine = RecordingEngine()
    window = MainWindow(
        repository, record, tree, engine, audio_feedback=SilentAudio(),
    )
    qtbot.addWidget(window)
    return window, engine


def _payload(winrate: float, *, complete: bool = False) -> dict[str, object]:
    return {
        "rootInfo": {"winrate": winrate, "visits": 800 if complete else 9},
        "moveInfos": [{"move": "D4", "order": 0, "winrate": winrate}],
        "isDuringSearch": not complete,
    }


@pytest.mark.parametrize("realtime,ownership", [(False, True), (True, False), (True, True)])
def test_analysis_controls_survive_close_and_start_the_saved_request(
    qtbot: QtBot, tmp_path: Path, realtime: bool, ownership: bool,
) -> None:
    path = tmp_path / "controls.db"
    window, _engine = _window(GameRepository(path), qtbot)
    window.analysis_checkbox.setChecked(realtime)
    window.ownership_checkbox.setChecked(ownership)
    window.close()

    repository = GameRepository(path)
    reopened, engine = _window(repository, qtbot)
    assert reopened.analysis_checkbox.isChecked() is realtime
    assert reopened.ownership_checkbox.isChecked() is ownership
    qtbot.wait(10)
    assert len(engine.queries) == int(realtime)
    if realtime:
        assert engine.queries[0]["include_ownership"] is ownership
        assert engine.queries[0]["max_visits"] == 800


def test_fair_mode_suppresses_analysis_without_erasing_saved_preferences(
    qtbot: QtBot, tmp_path: Path,
) -> None:
    path = tmp_path / "fair.db"
    window, _engine = _window(GameRepository(path), qtbot)
    window.analysis_checkbox.setChecked(True)
    window.ownership_checkbox.setChecked(True)
    window.mode_combo.setCurrentIndex(window.mode_combo.findData("fair"))
    assert not window.analysis_checkbox.isChecked()
    assert not window.ownership_checkbox.isChecked()
    assert window.repository.load_setting("analysis_controls") == {
        "realtime_enabled": True, "ownership_enabled": True,
    }
    window.close()

    reopened, engine = _window(GameRepository(path), qtbot)
    assert not reopened.analysis_checkbox.isChecked()
    assert not reopened.ownership_checkbox.isChecked()
    assert not reopened.analysis_checkbox.isEnabled()
    reopened.mode_combo.setCurrentIndex(reopened.mode_combo.findData("manual"))
    assert reopened.analysis_checkbox.isChecked()
    assert reopened.ownership_checkbox.isChecked()
    assert engine.queries[-1]["include_ownership"] is True


def test_partial_points_survive_moves_and_restart_with_realtime_off(
    qtbot: QtBot, tmp_path: Path,
) -> None:
    path = tmp_path / "partial.db"
    window, engine = _window(GameRepository(path), qtbot)
    window.analysis_checkbox.setChecked(True)
    for index, point in enumerate((Point(3, 3), Point(15, 15), None)):
        engine.analysis_updated.emit(AnalysisUpdate(
            window._active_realtime_request_id or "test", window.tree.current_id,
            "realtime", _payload(0.3 + index / 10),
        ))
        if point is not None:
            window._play_point(point.x, point.y)
    assert window._current_winrate_series() == ([0, 1, 2], [30.0, 40.0, 50.0])
    assert window.repository.analysis_snapshots_for_game(window.record.id) == {}
    window.analysis_checkbox.setChecked(False)
    window.close()

    reopened, engine = _window(GameRepository(path), qtbot)
    assert not reopened.analysis_checkbox.isChecked()
    assert reopened._current_winrate_series() == ([0, 1, 2], [30.0, 40.0, 50.0])
    x, y = reopened.winrate_curve.getData()
    assert list(x) == [0, 1, 2]
    assert list(y) == [30.0, 40.0, 50.0]
    assert reopened.repository.analysis_snapshots_for_game(reopened.record.id) == {}
    reopened._start_full_game_analysis()
    assert reopened._full_analysis_completed == 0
    assert reopened._full_analysis_total == 3
    assert engine.queries[-1]["node_id"] == reopened.tree.root_id
    assert engine.queries[-1]["max_visits"] == 800


def test_cached_completed_payload_cannot_overwrite_newer_saved_chart_point(
    qtbot: QtBot, tmp_path: Path,
) -> None:
    path = tmp_path / "newer-point.db"
    window, engine = _window(GameRepository(path), qtbot)
    node_id = window.tree.current_id
    complete = _payload(0.6, complete=True)
    engine.analysis_finished.emit(AnalysisUpdate("complete", node_id, "realtime", complete))
    engine.analysis_updated.emit(AnalysisUpdate("partial", node_id, "realtime", _payload(0.4)))
    window.close()
    reopened, _engine = _window(GameRepository(path), qtbot)
    assert reopened._current_winrate_series() == ([0], [40.0])
    assert reopened._analysis_payload_by_node[node_id] == complete
    assert reopened._displayed_analysis_payload == complete


def _save_analysis(repository: GameRepository, game_id: str, node_id: str) -> None:
    repository.save_analysis_snapshot(
        game_id=game_id, node_id=node_id, cache_key="full-game-800",
        engine_version="test", model_hash="test-model", parameters={},
        result=_payload(0.5, complete=True),
    )
    repository.save_winrate_point(
        game_id=game_id, node_id=node_id, max_visits=800,
        black_winrate=50.0, search_visits=9, is_complete=False,
    )


def test_undo_removes_descendants_analysis_and_points_but_retains_siblings(
    qtbot: QtBot, tmp_path: Path,
) -> None:
    path = tmp_path / "undo.db"
    repository = GameRepository(path)
    tree = GameTree()
    record = repository.create_game(tree)
    first, _ = tree.play(Point(3, 3))
    second, _ = tree.play(Point(15, 15))
    third, _ = tree.play(Point(3, 15))
    tree.go_to(first.id)
    sibling, _ = tree.play(Point(15, 3))
    for node in (first, second, third, sibling):
        repository.save_node(record.id, node)
    for node_id in tree.nodes:
        _save_analysis(repository, record.id, node_id)
    repository.set_current(record.id, second.id)
    window, engine = _window(repository, qtbot)
    window._ownership_by_node[second.id] = [0.2] * 361
    window._active_realtime_request_id = "deleted-request"
    window._undo()

    remaining = {tree.root_id, first.id, sibling.id}
    assert set(window.tree.nodes) == remaining
    assert window.tree.current_id == first.id
    assert window.tree.nodes[first.id].children == [sibling.id]
    assert set(window._analysis_payload_by_node) == remaining
    assert set(window._analysis_by_node) == remaining
    assert second.id not in window._ownership_by_node
    for purpose in ("realtime", "full_game", "ai_move"):
        late = AnalysisUpdate("deleted-request", second.id, purpose, _payload(0.9))
        engine.analysis_updated.emit(late)
        engine.analysis_finished.emit(late)
    assert set(repository.analysis_snapshots_for_game(record.id)) == remaining
    assert set(repository.winrate_points_for_game(record.id, max_visits=800)) == remaining
    window._play_point(15, 15)
    new_id = window.tree.current_id
    assert new_id != second.id
    assert new_id not in window._analysis_by_node
    window.close()

    reopened, _engine = _window(GameRepository(path), qtbot)
    assert second.id not in reopened.tree.nodes
    assert third.id not in reopened.tree.nodes
    assert reopened.tree.current_id == new_id
    assert new_id not in reopened._analysis_by_node


def test_consecutive_undo_stops_at_root_and_replay_creates_a_fresh_node(
    qtbot: QtBot, tmp_path: Path,
) -> None:
    window, _engine = _window(GameRepository(tmp_path / "repeat.db"), qtbot)
    window._play_point(3, 3)
    deleted_id = window.tree.current_id
    window._play_point(15, 15)
    for _ in range(4):
        window._undo()
    assert len(window.tree.nodes) == 1
    assert window.tree.current_id == window.tree.root_id
    window._play_point(3, 3)
    assert window.tree.current_id != deleted_id


@pytest.mark.parametrize("ai_has_replied", [False, True])
def test_battle_undo_removes_the_human_move_and_its_ai_reply(
    qtbot: QtBot, tmp_path: Path, ai_has_replied: bool,
) -> None:
    repository = GameRepository(tmp_path / "battle.db")
    tree = GameTree()
    record = repository.create_game(tree, mode="assisted", human_color="black")
    human, _ = tree.play(Point(3, 3))
    repository.save_node(record.id, human)
    if ai_has_replied:
        ai, _ = tree.play(Point(15, 15))
        repository.save_node(record.id, ai)
    window, _engine = _window(repository, qtbot)
    window._review_mode_active = False
    window._startup_resume_pending = False
    window._undo()
    assert set(window.tree.nodes) == {tree.root_id}
    assert set(repository.load_game(record.id)[1].nodes) == {tree.root_id}


def test_review_previous_next_and_undo_browse_without_deleting(
    qtbot: QtBot, tmp_path: Path,
) -> None:
    repository = GameRepository(tmp_path / "review.db")
    tree = GameTree()
    record = repository.create_game(tree)
    first, _ = tree.play(Point(3, 3))
    repository.save_node(record.id, first)
    second, _ = tree.play(Point(15, 15))
    repository.save_node(record.id, second)
    for node_id in tree.nodes:
        _save_analysis(repository, record.id, node_id)
    window, _engine = _window(repository, qtbot)
    window._review_mode_active = True
    window._undo()
    assert window.tree.current_id == first.id
    window._navigate_next()
    assert window.tree.current_id == second.id
    window._navigate_previous()
    assert window.tree.current_id == first.id
    assert set(repository.load_game(record.id)[1].nodes) == set(tree.nodes)
    assert len(repository.analysis_snapshots_for_game(record.id)) == 3
    assert len(repository.winrate_points_for_game(record.id, max_visits=800)) == 3


def test_failed_undo_rolls_back_storage_and_keeps_the_live_tree(
    qtbot: QtBot, tmp_path: Path,
) -> None:
    repository = GameRepository(tmp_path / "rollback.db")
    window, _engine = _window(repository, qtbot)
    window._play_point(3, 3)
    current_id = window.tree.current_id
    _save_analysis(repository, window.record.id, current_id)
    with repository.connection:
        repository.connection.execute(
            "CREATE TRIGGER block_undo BEFORE DELETE ON game_nodes BEGIN "
            "SELECT RAISE(ABORT, 'blocked for rollback test'); END"
        )
    window._undo()
    assert window.tree.current_id == current_id
    assert len(window.tree.nodes) == 2
    assert repository.load_game(window.record.id)[1].current_id == current_id
    assert current_id in repository.analysis_snapshots_for_game(window.record.id)
    assert current_id in repository.winrate_points_for_game(window.record.id, max_visits=800)
    assert "blocked for rollback test" in window.statusBar().currentMessage()


def test_undo_during_full_game_analysis_cannot_delete_positions(
    qtbot: QtBot, tmp_path: Path,
) -> None:
    window, _engine = _window(GameRepository(tmp_path / "full-game.db"), qtbot)
    window._play_point(3, 3)
    node_id = window.tree.current_id
    window._start_full_game_analysis()
    assert not window.undo_action.isEnabled()
    window._undo()
    assert window.tree.current_id == node_id
    assert len(window.tree.nodes) == 2
    window._stop_full_game_analysis(request_realtime=False)
    assert window.undo_action.isEnabled()


def test_toolbar_keeps_original_order_and_settings_in_menu(
    qtbot: QtBot, tmp_path: Path,
) -> None:
    window, _engine = _window(GameRepository(tmp_path / "toolbar.db"), qtbot)
    actions = window.game_toolbar.actions()
    toolbar_texts = {action.text() for action in actions}
    assert not toolbar_texts.intersection({
        "Redo", "Preferences", "Analysis settings", "Local AI explanation settings",
    })
    assert [action.text() for action in actions if action.text()] == [
        "New game", "Game library", "Undo", "Pass", "Finish / Score", "Resign", "Mute",
        "Import SGF", "Recognize image", "Export SGF", "Analyze full game",
    ]
    widget_actions = {window.game_toolbar.widgetForAction(action): action for action in actions}
    full_analysis_index = actions.index(window.full_analysis_action)
    control_indices = [
        actions.index(widget_actions[control])
        for control in (window.mode_combo, window.difficulty_combo, window.human_color_combo,
                        window.analysis_checkbox, window.ownership_checkbox)
    ]
    assert full_analysis_index < control_indices[0]
    assert control_indices == sorted(control_indices)
    assert sum(action.isSeparator() for action in actions) == 1

    menus = window.findChildren(QMenu)
    menu_texts = {action.text() for menu in menus for action in menu.actions()}
    assert {"Preferences", "Analysis settings", "Local AI explanation settings"} <= menu_texts
    assert "Redo" not in menu_texts
    assert window.next_move_button.text() == "Next"
    assert window.previous_move_button.text() == "Previous"


def _finish_latest(
    engine: RecordingEngine, winrate: float = 0.6, **extras: object,
) -> AnalysisUpdate:
    query = engine.queries[-1]
    payload = _payload(winrate, complete=True)
    payload.update(extras)
    update = AnalysisUpdate(
        f"request-{len(engine.queries)}", str(query["node_id"]), str(query["purpose"]), payload,
    )
    engine.analysis_updated.emit(update)
    engine.analysis_finished.emit(update)
    return update


def _drain_backfill(window: MainWindow, engine: RecordingEngine) -> None:
    for _ in range(10):
        if window._active_backfill_request_id is None:
            return
        assert engine.queries[-1]["purpose"] == "winrate_backfill"
        assert engine.queries[-1]["max_visits"] == window.analysis_settings.visits
        _finish_latest(engine)
    pytest.fail("The backfill queue did not finish")


def test_fast_moves_fill_every_requested_position_without_replacing_live_analysis(
    qtbot: QtBot, tmp_path: Path,
) -> None:
    repository = GameRepository(tmp_path / "fast.db")
    window, engine = _window(repository, qtbot)
    window.analysis_checkbox.setChecked(True)
    window.ownership_checkbox.setChecked(True)
    for x, y in ((3, 3), (15, 15), (3, 15)):
        window._play_point(x, y)
    assert window._current_winrate_series() == ([], [])
    assert len(repository.pending_winrate_nodes(window.record.id, max_visits=800)) == 4
    current_id = window.tree.current_id
    current = _finish_latest(engine, ownership=[0.3] * 361)
    assert engine.queries[-1]["purpose"] == "winrate_backfill"
    assert engine.queries[-1]["node_id"] == window.tree.root_id
    assert engine.queries[-1]["include_ownership"] is False
    assert engine.queries[-1]["human_profile"] is None
    live_candidates = window._candidate_payloads.copy()
    live_ownership = window._ownership_by_node[current_id]
    _drain_backfill(window, engine)
    assert window._current_winrate_series()[0] == [0, 1, 2, 3]
    assert repository.pending_winrate_nodes(window.record.id, max_visits=800) == []
    assert window._displayed_analysis_payload == current.payload
    assert window._candidate_payloads == live_candidates
    assert window._ownership_by_node == {current_id: live_ownership}
    assert set(repository.analysis_snapshots_for_game(window.record.id)) == {current_id}


def test_new_move_preempts_backfill_and_late_result_cannot_change_the_chart(
    qtbot: QtBot, tmp_path: Path,
) -> None:
    window, engine = _window(GameRepository(tmp_path / "preempt.db"), qtbot)
    window.analysis_checkbox.setChecked(True)
    window._play_point(3, 3)
    _finish_latest(engine)
    old_id = window._active_backfill_request_id
    root_id = window.tree.root_id
    window._play_point(15, 15)
    assert engine.queries[-1]["purpose"] == "realtime"
    assert window._active_backfill_request_id is None
    late = AnalysisUpdate(old_id or "missing", root_id, "winrate_backfill", _payload(0.9))
    engine.analysis_updated.emit(late)
    engine.analysis_finished.emit(late)
    assert root_id not in window._analysis_by_node
    _finish_latest(engine)
    assert engine.queries[-1]["node_id"] == root_id
    _drain_backfill(window, engine)
    assert window._current_winrate_series()[0] == [0, 1, 2]


def test_enabling_analysis_never_backfills_moves_played_with_analysis_off(
    qtbot: QtBot, tmp_path: Path,
) -> None:
    window, engine = _window(GameRepository(tmp_path / "off-history.db"), qtbot)
    window._play_point(3, 3)
    window._play_point(15, 15)
    assert engine.queries == []
    assert window.repository.pending_winrate_nodes(window.record.id, max_visits=800) == []
    window.analysis_checkbox.setChecked(True)
    assert window.repository.pending_winrate_nodes(window.record.id, max_visits=800) == [
        window.tree.current_id,
    ]
    _finish_latest(engine)
    assert window._active_backfill_request_id is None
    assert window._current_winrate_series()[0] == [2]
    window.analysis_checkbox.setChecked(False)
    window._play_point(3, 15)
    window.analysis_checkbox.setChecked(True)
    _finish_latest(engine)
    assert window._current_winrate_series()[0] == [2, 3]
    assert all(query["purpose"] == "realtime" for query in engine.queries)


def test_saved_backfill_pauses_with_analysis_off_and_resumes_after_restart(
    qtbot: QtBot, tmp_path: Path,
) -> None:
    path = tmp_path / "resume-backfill.db"
    window, engine = _window(GameRepository(path), qtbot)
    window.analysis_checkbox.setChecked(True)
    window._play_point(3, 3)
    window._play_point(15, 15)
    _finish_latest(engine)
    assert window._active_backfill_request_id is not None
    window.analysis_checkbox.setChecked(False)
    window.close()
    reopened, engine = _window(GameRepository(path), qtbot)
    qtbot.wait(10)
    assert not reopened.analysis_checkbox.isChecked()
    assert engine.queries == []
    pending = reopened.repository.pending_winrate_nodes(reopened.record.id, max_visits=800)
    assert len(pending) == 2
    reopened.analysis_checkbox.setChecked(True)
    assert engine.queries[-1]["node_id"] == reopened.tree.current_id
    assert engine.queries[-1]["purpose"] == "realtime"
    _finish_latest(engine)
    _drain_backfill(reopened, engine)
    assert reopened._current_winrate_series()[0] == [0, 1, 2]
    reopened.close()
    final, _engine = _window(GameRepository(path), qtbot)
    assert final._current_winrate_series()[0] == [0, 1, 2]


def test_undo_removes_pending_work_and_cannot_resurrect_deleted_winrates(
    qtbot: QtBot, tmp_path: Path,
) -> None:
    window, engine = _window(GameRepository(tmp_path / "undo-pending.db"), qtbot)
    window.analysis_checkbox.setChecked(True)
    window._play_point(3, 3)
    doomed = window.tree.current_id
    window._play_point(15, 15)
    window._undo()
    window._undo()
    pending = window.repository.pending_winrate_nodes(window.record.id, max_visits=800)
    assert doomed not in pending
    late = AnalysisUpdate("cancelled", doomed, "winrate_backfill", _payload(0.8, complete=True))
    engine.analysis_finished.emit(late)
    _finish_latest(engine)
    assert window.repository.pending_winrate_nodes(window.record.id, max_visits=800) == []
    assert window._current_winrate_series()[0] == [0]


def test_backfill_is_scoped_to_the_selected_game_and_preserved_when_switching(
    qtbot: QtBot, tmp_path: Path,
) -> None:
    repository = GameRepository(tmp_path / "switch-backfill.db")
    window, engine = _window(repository, qtbot)
    window.analysis_checkbox.setChecked(True)
    window._play_point(3, 3)
    original_record, original_tree = window.record, window.tree
    _finish_latest(engine)
    old_id = window._active_backfill_request_id
    tree = GameTree()
    record = repository.create_game(tree)
    window._apply_loaded_game(record, tree, review_mode=False)
    window._request_analysis()
    engine.analysis_finished.emit(AnalysisUpdate(
        old_id or "missing", original_tree.root_id, "winrate_backfill", _payload(0.9),
    ))
    _finish_latest(engine)
    assert window._active_backfill_request_id is None
    assert original_tree.root_id not in window._analysis_by_node
    assert repository.pending_winrate_nodes(original_record.id, max_visits=800) == [
        original_tree.root_id,
    ]
    window._apply_loaded_game(original_record, original_tree, review_mode=False)
    window._request_analysis()
    _finish_latest(engine)
    _drain_backfill(window, engine)
    assert window._current_winrate_series()[0] == [0, 1]


def test_ai_moves_take_priority_and_backfill_uses_the_objective_analysis_budget(
    qtbot: QtBot, tmp_path: Path,
) -> None:
    window, engine = _window(GameRepository(tmp_path / "ai-backfill.db"), qtbot)
    window.mode_combo.setCurrentIndex(window.mode_combo.findData("assisted"))
    window.analysis_checkbox.setChecked(True)
    window._play_point(3, 3)
    preset = PRESETS[str(window.difficulty_combo.currentData())]
    assert engine.queries[-1]["purpose"] == "ai_move"
    assert engine.queries[-1]["max_visits"] == preset.max_visits
    _finish_latest(engine, moveInfos=[{"move": "Q16", "order": 0, "winrate": 0.6}])
    assert engine.queries[-1]["purpose"] == "realtime"
    _finish_latest(engine)
    _drain_backfill(window, engine)
    assert window._current_winrate_series()[0] == [0, 1, 2]


def test_fair_play_pauses_pending_backfill_without_losing_it(
    qtbot: QtBot, tmp_path: Path,
) -> None:
    window, engine = _window(GameRepository(tmp_path / "fair-backfill.db"), qtbot)
    window.analysis_checkbox.setChecked(True)
    window._play_point(3, 3)
    window._play_point(15, 15)
    window.mode_combo.setCurrentIndex(window.mode_combo.findData("fair"))
    query_count = len(engine.queries)
    window._start_next_winrate_analysis()
    assert len(engine.queries) == query_count
    window.mode_combo.setCurrentIndex(window.mode_combo.findData("manual"))
    assert window.analysis_checkbox.isChecked()
    _finish_latest(engine)
    _drain_backfill(window, engine)
    assert window._current_winrate_series()[0] == [0, 1, 2]


def test_full_game_analysis_completes_pending_jobs_without_duplicate_backfill(
    qtbot: QtBot, tmp_path: Path,
) -> None:
    window, engine = _window(GameRepository(tmp_path / "full-pending.db"), qtbot)
    window.analysis_checkbox.setChecked(True)
    window._play_point(3, 3)
    window._play_point(15, 15)
    window._start_full_game_analysis()
    for _ in range(3):
        assert engine.queries[-1]["purpose"] == "full_game"
        _finish_latest(engine)
    assert not window._full_analysis_active
    assert window._active_backfill_request_id is None
    assert window.repository.pending_winrate_nodes(window.record.id, max_visits=800) == []
    assert window._current_winrate_series()[0] == [0, 1, 2]


def test_budget_change_keeps_old_pending_work_and_rejects_cancelled_backfill(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, engine = _window(GameRepository(tmp_path / "budget-backfill.db"), qtbot)
    window.analysis_checkbox.setChecked(True)
    window._play_point(3, 3)
    _finish_latest(engine)
    old_id = window._active_backfill_request_id
    monkeypatch.setattr(
        AnalysisSettingsDialog, "exec",
        lambda _dialog: AnalysisSettingsDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        AnalysisSettingsDialog, "settings", lambda _dialog: AnalysisSettings(801),
    )
    window._open_analysis_settings()
    engine.analysis_finished.emit(AnalysisUpdate(
        old_id or "missing", window.tree.root_id, "winrate_backfill", _payload(0.9),
    ))
    _finish_latest(engine)
    assert window._active_backfill_request_id is None
    assert window._current_winrate_series()[0] == [1]
    saved_points = window.repository.winrate_points_for_game(window.record.id, max_visits=801)
    assert saved_points.keys() == {window.tree.current_id}
    monkeypatch.setattr(
        AnalysisSettingsDialog, "settings", lambda _dialog: AnalysisSettings(800),
    )
    window._open_analysis_settings()
    _finish_latest(engine)
    _drain_backfill(window, engine)
    assert window._current_winrate_series()[0] == [0, 1]


@pytest.mark.parametrize("invalid_result", [False, True])
def test_failed_backfill_retains_work_and_retry_uses_a_new_request_id(
    qtbot: QtBot, tmp_path: Path, invalid_result: bool,
) -> None:
    window, engine = _window(GameRepository(tmp_path / "failure-backfill.db"), qtbot)
    window.analysis_checkbox.setChecked(True)
    window._play_point(3, 3)
    _finish_latest(engine)
    old_id = window._active_backfill_request_id
    count = len(engine.queries)
    if invalid_result:
        _finish_latest(engine, float("nan"))
    else:
        engine.failure_reported.emit(EngineFailure(
            kind=EngineFailureKind.ANALYSIS_STALLED, message="test stall", recoverable=True,
            request_id=old_id, node_id=window.tree.root_id, purpose="winrate_backfill",
        ))
    assert len(engine.queries) == count
    assert window.repository.pending_winrate_nodes(window.record.id, max_visits=800) == [
        window.tree.root_id,
    ]
    window._retry_engine_analysis()
    assert window._active_backfill_request_id is not None
    assert window._active_backfill_request_id != old_id
    engine.analysis_finished.emit(AnalysisUpdate(
        old_id or "missing", window.tree.root_id, "winrate_backfill", _payload(0.9),
    ))
    _drain_backfill(window, engine)
    assert window.repository.pending_winrate_nodes(window.record.id, max_visits=800) == []
    assert window._current_winrate_series()[0] == [0, 1]
