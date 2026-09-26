from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pytest import MonkeyPatch
from pytestqt.qtbot import QtBot

from recurgo.domain import GameTree
from recurgo.engine import AnalysisUpdate
from recurgo.storage import GameRepository
from recurgo.ui.analysis_settings_dialog import AnalysisSettings, AnalysisSettingsDialog
from recurgo.ui.main_window import MainWindow


class SilentAudio:
    def set_muted(self, _muted: bool) -> None:
        return

    def play_move(self, *, captured: bool) -> None:
        return


class FakeEngine:
    def __init__(self) -> None:
        self.queries: list[dict[str, object]] = []
        self.stop_count = 0
        self.runtime = SimpleNamespace(engine_version="test", model_sha256="test-model")

    def analyze(self, **kwargs: object) -> str:
        self.queries.append(kwargs)
        return f"request-{len(self.queries)}"

    def stop_analysis(self) -> None:
        self.stop_count += 1

    def shutdown(self) -> None:
        return


def test_analysis_setting_persists_and_cannot_reuse_other_budget_cache(
    qtbot: QtBot, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    repository = GameRepository(tmp_path / "analysis.db")
    tree = GameTree()
    record = repository.create_game(tree)
    repository.save_setting("analysis", {"visits": 800})
    old_payload = {"rootInfo": {"winrate": 0.6}, "moveInfos": [{"move": "D4"}]}
    repository.save_analysis_snapshot(
        game_id=record.id,
        node_id=tree.root_id,
        cache_key="realtime-800-0",
        engine_version="test",
        model_hash="test-model",
        parameters={"maxVisits": 800},
        result=old_payload,
    )
    window = MainWindow(repository, record, tree, audio_feedback=SilentAudio())
    qtbot.addWidget(window)
    engine = FakeEngine()
    window.engine = engine  # type: ignore[assignment]
    window.analysis_checkbox.setChecked(True)
    assert window.analysis_settings.visits == 800
    assert window._analysis_payload_by_node[tree.root_id] == old_payload

    monkeypatch.setattr(
        AnalysisSettingsDialog,
        "exec",
        lambda _dialog: AnalysisSettingsDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        AnalysisSettingsDialog,
        "settings",
        lambda _dialog: AnalysisSettings(1200),
    )
    window._open_analysis_settings()

    assert repository.load_setting("analysis") == {"visits": 1200}
    assert window.analysis_settings.visits == 1200
    assert window._analysis_payload_by_node == {}
    assert engine.queries[-1]["max_visits"] == 1200
    assert engine.stop_count >= 1
    assert repository.analysis_snapshots_for_game(
        record.id, cache_keys=("realtime-800-0",)
    ) == {tree.root_id: old_payload}

    current_payload = {"rootInfo": {"winrate": 0.58}, "moveInfos": [{"move": "Q16"}]}
    current_id = window._active_realtime_request_id
    assert current_id is not None
    window._analysis_finished(
        AnalysisUpdate(current_id, tree.root_id, "realtime", current_payload)
    )
    assert repository.analysis_snapshots_for_game(
        record.id, cache_keys=("realtime-1200-0",)
    ) == {tree.root_id: current_payload}

    reopened_repository = GameRepository(repository.database_path)
    reopened = MainWindow(reopened_repository, record, tree, audio_feedback=SilentAudio())
    qtbot.addWidget(reopened)
    assert reopened.analysis_settings.visits == 1200
    assert reopened._analysis_payload_by_node[tree.root_id] == current_payload


def test_analysis_setting_discards_late_result_and_isolates_review_budget(
    qtbot: QtBot, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    repository = GameRepository(tmp_path / "switch.db")
    tree = GameTree()
    record = repository.create_game(tree)
    window = MainWindow(repository, record, tree, audio_feedback=SilentAudio())
    qtbot.addWidget(window)
    engine = FakeEngine()
    window.engine = engine  # type: ignore[assignment]
    window.analysis_checkbox.setChecked(True)
    old_id = window._active_realtime_request_id
    assert old_id == "request-1"
    monkeypatch.setattr(
        AnalysisSettingsDialog,
        "exec",
        lambda _dialog: AnalysisSettingsDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        AnalysisSettingsDialog,
        "settings",
        lambda _dialog: AnalysisSettings(801),
    )
    window._open_analysis_settings()
    late_payload = {"rootInfo": {"winrate": 0.9}, "moveInfos": [{"move": "D4"}]}
    window._analysis_finished(
        AnalysisUpdate(old_id, tree.root_id, "realtime", late_payload)
    )
    assert repository.analysis_snapshots_for_game(record.id) == {}
    assert engine.queries[-1]["max_visits"] == 801

    window._start_full_game_analysis()
    assert engine.queries[-1]["max_visits"] == 801
    assert window._full_analysis_visits == 801


def test_settings_validation_and_exact_cache_selection(tmp_path: Path) -> None:
    assert AnalysisSettings.from_mapping({"visits": 900}) == AnalysisSettings(900)
    assert AnalysisSettings.from_mapping({"visits": True}) == AnalysisSettings()
    assert AnalysisSettings.from_mapping({"visits": 0}) == AnalysisSettings()

    repository = GameRepository(tmp_path / "cache.db")
    tree = GameTree()
    record = repository.create_game(tree)
    for budget in (800, 8000):
        repository.save_analysis_snapshot(
            game_id=record.id,
            node_id=tree.root_id,
            cache_key=f"full-game-{budget}",
            engine_version="test",
            model_hash="test-model",
            parameters={"maxVisits": budget},
            result={"rootInfo": {"visits": budget}},
        )
    assert repository.analysis_snapshots_for_game(
        record.id, cache_keys=("full-game-800",)
    ) == {tree.root_id: {"rootInfo": {"visits": 800}}}
