from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from recurgo.engine import (
    EngineFailure,
    EngineFailureKind,
    EngineRuntime,
    EngineState,
    KataGoEngine,
)


def _runtime(tmp_path: Path) -> EngineRuntime:
    return EngineRuntime(
        project_root=tmp_path,
        engine=tmp_path / "katago.exe",
        model=tmp_path / "model.bin.gz",
        human_model=tmp_path / "human.bin.gz",
        analysis_config=tmp_path / "analysis.cfg",
        cuda_bin=tmp_path,
        cudnn_bin=tmp_path,
        engine_version="test",
        model_sha256="test-model",
    )


def test_analysis_protocol_error_is_reported_and_request_is_cleared(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    engine = KataGoEngine(_runtime(tmp_path))
    engine._current_request_id = "analysis-test"
    engine._current_node_id = "node-test"
    engine._current_purpose = "full_game"
    engine._stdout_buffer = json.dumps(
        {
            "id": "analysis-test",
            "field": "komi",
            "error": "Must be between -150 and 150",
        }
    ) + "\n"

    with qtbot.waitSignal(engine.engine_error, timeout=1000) as blocker:
        engine._read_stdout()

    assert blocker.args == ["分析请求被拒绝（字段：komi）：Must be between -150 and 150"]
    assert engine._current_request_id is None
    assert engine._current_node_id is None
    assert engine._current_purpose is None


@pytest.mark.parametrize(
    "keyword",
    ["startup_timeout_ms", "analysis_stall_timeout_ms"],
)
def test_negative_timeout_is_rejected(tmp_path: Path, keyword: str) -> None:
    arguments = {keyword: -1}
    with pytest.raises(ValueError):
        KataGoEngine(_runtime(tmp_path), **arguments)  # type: ignore[arg-type]


def test_startup_timeout_reports_structured_recoverable_failure(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    engine = KataGoEngine(_runtime(tmp_path))
    engine._set_state(EngineState.LOADING)
    engine._stderr_lines.append("Loading model from model.bin.gz")

    with qtbot.waitSignal(engine.failure_reported, timeout=1000) as blocker:
        engine._on_startup_timeout()

    failure = blocker.args[0]
    assert isinstance(failure, EngineFailure)
    assert failure.kind is EngineFailureKind.STARTUP_TIMEOUT
    assert failure.recoverable is True
    assert failure.stderr_tail == "Loading model from model.bin.gz"
    assert engine.state is EngineState.FAILED
    assert engine.is_ready is False


def test_startup_watchdog_emits_without_manual_timeout_callback(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    engine = KataGoEngine(_runtime(tmp_path), startup_timeout_ms=10)
    engine._set_state(EngineState.LOADING)

    with qtbot.waitSignal(engine.failure_reported, timeout=1000) as blocker:
        engine._arm_startup_timer()

    failure = blocker.args[0]
    assert isinstance(failure, EngineFailure)
    assert failure.kind is EngineFailureKind.STARTUP_TIMEOUT


def test_analysis_stall_clears_only_active_request_and_preserves_retry(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    engine = KataGoEngine(_runtime(tmp_path))
    engine._ready = True
    engine._set_state(EngineState.ANALYZING)
    engine._current_request_id = "analysis-stalled"
    engine._current_node_id = "node-19"
    engine._current_purpose = "full_game"
    engine._last_query = {"id": "analysis-stalled", "moves": []}
    engine._last_node_id = "node-19"
    engine._last_purpose = "full_game"

    with qtbot.waitSignal(engine.failure_reported, timeout=1000) as blocker:
        engine._on_analysis_stall_timeout()

    failure = blocker.args[0]
    assert isinstance(failure, EngineFailure)
    assert failure.kind is EngineFailureKind.ANALYSIS_STALLED
    assert failure.request_id == "analysis-stalled"
    assert failure.node_id == "node-19"
    assert failure.purpose == "full_game"
    assert engine.active_request_id is None
    assert engine.state is EngineState.READY
    assert engine.can_retry is True


def test_analysis_watchdog_emits_without_manual_timeout_callback(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    engine = KataGoEngine(_runtime(tmp_path), analysis_stall_timeout_ms=10)
    engine._ready = True
    engine._set_state(EngineState.ANALYZING)
    engine._current_request_id = "analysis-watchdog"
    engine._current_node_id = "node-watchdog"
    engine._current_purpose = "realtime"

    with qtbot.waitSignal(engine.failure_reported, timeout=1000) as blocker:
        engine._arm_analysis_stall_timer()

    failure = blocker.args[0]
    assert isinstance(failure, EngineFailure)
    assert failure.kind is EngineFailureKind.ANALYSIS_STALLED


def test_matching_search_update_rearms_stall_timer(tmp_path: Path) -> None:
    engine = KataGoEngine(_runtime(tmp_path), analysis_stall_timeout_ms=5_000)
    engine._current_request_id = "analysis-live"
    engine._current_node_id = "node-live"
    engine._current_purpose = "realtime"
    engine._stdout_buffer = json.dumps(
        {
            "id": "analysis-live",
            "isDuringSearch": True,
            "moveInfos": [],
        }
    ) + "\n"

    engine._read_stdout()

    assert engine._analysis_stall_timer.isActive() is True
    assert engine._analysis_stall_timer.remainingTime() > 0
    engine._analysis_stall_timer.stop()


def test_retry_last_request_uses_new_id_and_queues_fresh_copy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = KataGoEngine(_runtime(tmp_path))
    original_query: dict[str, object] = {
        "id": "analysis-old",
        "moves": [["B", "D4"]],
    }
    engine._last_query = original_query
    engine._last_node_id = "node-old"
    engine._last_purpose = "realtime"
    starts: list[bool] = []

    def replacement() -> None:
        starts.append(True)

    monkeypatch.setattr(engine, "start", replacement)

    request_id = engine.retry_last_request()

    assert request_id is not None
    assert request_id != "analysis-old"
    assert engine._pending_query is not None
    assert engine._pending_query["id"] == request_id
    assert engine._pending_node_id == "node-old"
    assert engine._pending_purpose == "realtime"
    assert original_query["id"] == "analysis-old"
    assert starts == [True]


def test_cancel_queued_analysis_emits_id_and_keeps_process_available(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    engine = KataGoEngine(_runtime(tmp_path))
    engine._pending_query = {"id": "analysis-queued"}
    engine._pending_node_id = "node-queued"
    engine._pending_purpose = "realtime"

    with qtbot.waitSignal(engine.analysis_cancelled, timeout=1000) as blocker:
        cancelled = engine.cancel_analysis()

    assert cancelled is True
    assert blocker.args == ["analysis-queued"]
    assert engine._pending_query is None
    assert engine.state is EngineState.STOPPED


def test_even_zero_exit_is_reported_when_shutdown_was_not_requested(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    engine = KataGoEngine(_runtime(tmp_path))
    engine._set_state(EngineState.READY)

    with qtbot.waitSignal(engine.failure_reported, timeout=1000) as blocker:
        engine._on_process_finished(0, object())

    failure = blocker.args[0]
    assert isinstance(failure, EngineFailure)
    assert failure.kind is EngineFailureKind.PROCESS_EXITED
    assert engine.state is EngineState.FAILED


def test_intentional_shutdown_exit_is_not_reported(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    engine = KataGoEngine(_runtime(tmp_path))
    engine._shutdown_requested = True
    failures: list[EngineFailure] = []
    engine.failure_reported.connect(failures.append)

    engine._on_process_finished(0, object())
    qtbot.wait(10)

    assert failures == []
    assert engine.state is EngineState.STOPPED
