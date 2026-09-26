"""Long-lived asynchronous KataGo JSON-analysis process for the Qt application."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from uuid import uuid4

from PySide6.QtCore import (
    QByteArray,
    QObject,
    QProcess,
    QProcessEnvironment,
    QTimer,
    Signal,
)

from recurgo.domain.board import Color
from recurgo.domain.coordinates import Point, point_to_gtp
from recurgo.domain.game_tree import GameTree

from .runtime import EngineRuntime


@dataclass(frozen=True, slots=True)
class AnalysisUpdate:
    request_id: str
    node_id: str
    purpose: str
    payload: dict[str, object]

    @property
    def is_final(self) -> bool:
        return self.payload.get("isDuringSearch") is False


class EngineState(StrEnum):
    """Observable lifecycle state of the long-lived KataGo process."""

    STOPPED = "stopped"
    STARTING = "starting"
    LOADING = "loading"
    READY = "ready"
    ANALYZING = "analyzing"
    STOPPING = "stopping"
    FAILED = "failed"


class EngineFailureKind(StrEnum):
    """Stable failure categories for UI retry/cancel decisions."""

    STARTUP_TIMEOUT = "startup_timeout"
    ANALYSIS_STALLED = "analysis_stalled"
    PROCESS_EXITED = "process_exited"
    PROCESS_ERROR = "process_error"
    PROTOCOL_ERROR = "protocol_error"
    REQUEST_REJECTED = "request_rejected"


@dataclass(frozen=True, slots=True)
class EngineFailure:
    """Structured diagnostics emitted in addition to the legacy text error."""

    kind: EngineFailureKind
    message: str
    recoverable: bool
    request_id: str | None = None
    node_id: str | None = None
    purpose: str | None = None
    stderr_tail: str = ""


class KataGoEngine(QObject):
    status_changed = Signal(str)
    state_changed = Signal(object)
    analysis_updated = Signal(object)
    analysis_finished = Signal(object)
    analysis_cancelled = Signal(str)
    engine_error = Signal(str)
    failure_reported = Signal(object)

    def __init__(
        self,
        runtime: EngineRuntime,
        parent: QObject | None = None,
        *,
        startup_timeout_ms: int = 120_000,
        analysis_stall_timeout_ms: int = 30_000,
    ) -> None:
        super().__init__(parent)
        if startup_timeout_ms < 0:
            raise ValueError("startup_timeout_ms must be non-negative")
        if analysis_stall_timeout_ms < 0:
            raise ValueError("analysis_stall_timeout_ms must be non-negative")
        self.runtime = runtime
        self.startup_timeout_ms = startup_timeout_ms
        self.analysis_stall_timeout_ms = analysis_stall_timeout_ms
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(runtime.project_root))
        environment = QProcessEnvironment.systemEnvironment()
        current_path = environment.value("PATH")
        environment.insert("PATH", f"{runtime.cudnn_bin};{runtime.cuda_bin};{current_path}")
        self.process.setProcessEnvironment(environment)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.started.connect(self._on_process_started)
        self.process.finished.connect(self._on_process_finished)
        self.process.errorOccurred.connect(self._on_process_error)

        self._startup_timer = QTimer(self)
        self._startup_timer.setSingleShot(True)
        self._startup_timer.timeout.connect(self._on_startup_timeout)
        self._analysis_stall_timer = QTimer(self)
        self._analysis_stall_timer.setSingleShot(True)
        self._analysis_stall_timer.timeout.connect(self._on_analysis_stall_timeout)

        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._stderr_lines: deque[str] = deque(maxlen=20)
        self._state = EngineState.STOPPED
        self._ready = False
        self._current_request_id: str | None = None
        self._current_node_id: str | None = None
        self._current_purpose: str | None = None
        self._pending_query: dict[str, object] | None = None
        self._pending_node_id: str | None = None
        self._pending_purpose: str | None = None
        self._last_query: dict[str, object] | None = None
        self._last_node_id: str | None = None
        self._last_purpose: str | None = None
        self._terminate_ids: set[str] = set()
        self._shutdown_requested = False
        self._restart_requested = False
        self._process_failure_reported = False

    @property
    def is_running(self) -> bool:
        return self.process.state() != QProcess.ProcessState.NotRunning

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def state(self) -> EngineState:
        return self._state

    @property
    def active_request_id(self) -> str | None:
        return self._current_request_id

    @property
    def can_retry(self) -> bool:
        return self._last_query is not None

    @property
    def stderr_tail(self) -> str:
        return "\n".join(self._stderr_lines)

    def start(self) -> None:
        if self.is_running:
            return
        self._shutdown_requested = False
        self._process_failure_reported = False
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._stderr_lines.clear()
        self._ready = False
        self._set_state(EngineState.STARTING)
        self.status_changed.emit("KataGo：正在加载模型…")
        arguments = [
            "analysis",
            "-config",
            str(self.runtime.analysis_config),
            "-model",
            str(self.runtime.model),
            "-human-model",
            str(self.runtime.human_model),
            "-quit-without-waiting",
        ]
        self._arm_startup_timer()
        self.process.start(str(self.runtime.engine), arguments)

    def analyze(
        self,
        *,
        tree: GameTree,
        node_id: str,
        rules: str,
        komi: float,
        max_visits: int = 800,
        human_profile: str | None = "rank_3k",
        include_ownership: bool = False,
        purpose: str = "realtime",
    ) -> str:
        self.stop_analysis()
        request_id = f"analysis-{uuid4()}"
        moves: list[list[str]] = []
        for node in tree.path_to(node_id)[1:]:
            if node.move is None:
                continue
            moves.append(
                [
                    node.move.color.short_name,
                    point_to_gtp(node.move.point, node.state.size),
                ]
            )
        state = tree.nodes[node_id].state
        initial_stones: list[list[str]] = []
        root_state = tree.root.state
        for y in range(root_state.size):
            for x in range(root_state.size):
                point = Point(x, y)
                color = root_state.stone_at(point)
                if color is not None:
                    initial_stones.append(
                        [
                            "B" if color is Color.BLACK else "W",
                            point_to_gtp(point, root_state.size),
                        ]
                    )
        override_settings: dict[str, object] = {
            "ignorePreRootHistory": False,
        }
        if human_profile is not None:
            override_settings["humanSLProfile"] = human_profile
        query: dict[str, object] = {
            "id": request_id,
            "moves": moves,
            "initialPlayer": tree.root.state.to_play.short_name,
            "rules": rules,
            "komi": komi,
            "boardXSize": state.size,
            "boardYSize": state.size,
            "maxVisits": max_visits,
            "analysisPVLen": 12,
            "includePolicy": True,
            "includeOwnership": include_ownership,
            "reportDuringSearchEvery": 0.4,
            "overrideSettings": override_settings,
        }
        if initial_stones:
            query["initialStones"] = initial_stones
        self._pending_query = query
        self._pending_node_id = node_id
        self._pending_purpose = purpose
        self._remember_query(query, node_id, purpose)
        if not self.is_running:
            self.start()
        elif self._ready:
            self._send_pending_query()
        elif self._state is EngineState.FAILED:
            self.restart()
        return request_id

    def stop_analysis(self) -> None:
        self.cancel_analysis()

    def cancel_analysis(self) -> bool:
        """Cancel the active or queued query without stopping the KataGo process."""

        cancelled_ids = self._cancel_query(send_terminate=True)
        for request_id in cancelled_ids:
            self.analysis_cancelled.emit(request_id)
        if cancelled_ids and self._ready:
            self._set_state(EngineState.READY)
            self.status_changed.emit("KataGo：分析已取消")
        elif cancelled_ids and self.is_running:
            self._set_state(EngineState.LOADING)
        return bool(cancelled_ids)

    def retry_last_request(self) -> str | None:
        """Queue a fresh copy of the last analysis request and return its new ID."""

        if (
            self._last_query is None
            or self._last_node_id is None
            or self._last_purpose is None
        ):
            return None
        self._cancel_query(send_terminate=True)
        query = dict(self._last_query)
        request_id = f"analysis-{uuid4()}"
        query["id"] = request_id
        self._pending_query = query
        self._pending_node_id = self._last_node_id
        self._pending_purpose = self._last_purpose
        self._remember_query(query, self._last_node_id, self._last_purpose)
        if self._ready and self.is_running:
            self._send_pending_query()
        elif self.is_running:
            if self._state is EngineState.FAILED:
                self.restart()
        else:
            self.start()
        return request_id

    def restart(self) -> None:
        """Restart KataGo while preserving a queued request for retry."""

        self._startup_timer.stop()
        self._analysis_stall_timer.stop()
        self._ready = False
        if self.is_running:
            self._restart_requested = True
            self._process_failure_reported = True
            self._set_state(EngineState.STOPPING)
            self.status_changed.emit("KataGo：正在重新启动…")
            self.process.kill()
            return
        self.start()

    def _cancel_query(self, *, send_terminate: bool) -> list[str]:
        self._analysis_stall_timer.stop()
        cancelled_ids: list[str] = []
        if self._current_request_id is not None and self.is_running:
            if send_terminate:
                action_id = f"terminate-{uuid4()}"
                self._terminate_ids.add(action_id)
                self._write_json(
                    {
                        "id": action_id,
                        "action": "terminate",
                        "terminateId": self._current_request_id,
                    }
                )
            cancelled_ids.append(self._current_request_id)
        if self._pending_query is not None:
            pending_id = str(self._pending_query.get("id", ""))
            if pending_id and pending_id not in cancelled_ids:
                cancelled_ids.append(pending_id)
        self._current_request_id = None
        self._current_node_id = None
        self._current_purpose = None
        self._pending_query = None
        self._pending_node_id = None
        self._pending_purpose = None
        return cancelled_ids

    def shutdown(self) -> None:
        self._shutdown_requested = True
        self._restart_requested = False
        self._startup_timer.stop()
        self._cancel_query(send_terminate=True)
        if not self.is_running:
            self._set_state(EngineState.STOPPED)
            return
        self._set_state(EngineState.STOPPING)
        self._write_json({"id": f"terminate-all-{uuid4()}", "action": "terminate_all"})
        self.process.closeWriteChannel()
        if not self.process.waitForFinished(3000):
            self.process.terminate()
            if not self.process.waitForFinished(3000):
                self.process.kill()
                self.process.waitForFinished(1000)

    def _send_pending_query(self) -> None:
        if (
            self._pending_query is None
            or self._pending_node_id is None
            or self._pending_purpose is None
        ):
            return
        self._current_request_id = str(self._pending_query["id"])
        self._current_node_id = self._pending_node_id
        self._current_purpose = self._pending_purpose
        query = self._pending_query
        self._pending_query = None
        self._pending_node_id = None
        self._pending_purpose = None
        self._write_json(query)
        self._arm_analysis_stall_timer()
        self._set_state(EngineState.ANALYZING)
        self.status_changed.emit("KataGo：正在分析当前局面")

    def _remember_query(
        self,
        query: dict[str, object],
        node_id: str,
        purpose: str,
    ) -> None:
        self._last_query = dict(query)
        self._last_node_id = node_id
        self._last_purpose = purpose

    def _set_state(self, state: EngineState) -> None:
        if state is self._state:
            return
        self._state = state
        self.state_changed.emit(state)

    def _arm_startup_timer(self) -> None:
        self._startup_timer.stop()
        if self.startup_timeout_ms > 0:
            self._startup_timer.start(self.startup_timeout_ms)

    def _arm_analysis_stall_timer(self) -> None:
        self._analysis_stall_timer.stop()
        if self.analysis_stall_timeout_ms > 0:
            self._analysis_stall_timer.start(self.analysis_stall_timeout_ms)

    def _report_failure(
        self,
        kind: EngineFailureKind,
        message: str,
        *,
        recoverable: bool,
        request_id: str | None = None,
        node_id: str | None = None,
        purpose: str | None = None,
    ) -> None:
        failure = EngineFailure(
            kind=kind,
            message=message,
            recoverable=recoverable,
            request_id=request_id,
            node_id=node_id,
            purpose=purpose,
            stderr_tail=self.stderr_tail,
        )
        self.failure_reported.emit(failure)
        self.engine_error.emit(message)

    def _write_json(self, payload: dict[str, object]) -> None:
        line = json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n"
        self.process.write(QByteArray(line.encode("utf-8")))

    def _read_stdout(self) -> None:
        self._stdout_buffer += bytes(self.process.readAllStandardOutput().data()).decode(
            "utf-8", errors="replace"
        )
        while "\n" in self._stdout_buffer:
            line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                self._report_failure(
                    EngineFailureKind.PROTOCOL_ERROR,
                    f"KataGo返回了无法解析的数据：{line[:200]}",
                    recoverable=True,
                    request_id=self._current_request_id,
                    node_id=self._current_node_id,
                    purpose=self._current_purpose,
                )
                continue
            response_id = str(payload.get("id", ""))
            if response_id in self._terminate_ids:
                self._terminate_ids.discard(response_id)
                continue
            if (
                response_id != self._current_request_id
                or self._current_node_id is None
                or self._current_purpose is None
            ):
                continue
            self._arm_analysis_stall_timer()
            error = payload.get("error", payload.get("errorMessage"))
            if error is not None:
                field = payload.get("field")
                field_text = f"（字段：{field}）" if field else ""
                request_id = self._current_request_id
                node_id = self._current_node_id
                purpose = self._current_purpose
                self._analysis_stall_timer.stop()
                self._current_request_id = None
                self._current_node_id = None
                self._current_purpose = None
                self._set_state(EngineState.READY)
                self._report_failure(
                    EngineFailureKind.REQUEST_REJECTED,
                    f"分析请求被拒绝{field_text}：{error}",
                    recoverable=True,
                    request_id=request_id,
                    node_id=node_id,
                    purpose=purpose,
                )
                continue
            update = AnalysisUpdate(
                request_id=response_id,
                node_id=self._current_node_id,
                purpose=self._current_purpose,
                payload=payload,
            )
            self.analysis_updated.emit(update)
            if update.is_final:
                self._analysis_stall_timer.stop()
                self._current_request_id = None
                self._current_node_id = None
                self._current_purpose = None
                self._set_state(EngineState.READY)
                self.status_changed.emit("KataGo：分析完成")
                self.analysis_finished.emit(update)

    def _read_stderr(self) -> None:
        self._stderr_buffer += bytes(self.process.readAllStandardError().data()).decode(
            "utf-8", errors="replace"
        )
        while "\n" in self._stderr_buffer:
            line, self._stderr_buffer = self._stderr_buffer.split("\n", 1)
            stripped = line.strip()
            if not stripped:
                continue
            self._stderr_lines.append(stripped)
            if "Started, ready to begin handling requests" in stripped:
                if self._state in (EngineState.FAILED, EngineState.STOPPING):
                    continue
                self._startup_timer.stop()
                self._ready = True
                self._set_state(EngineState.READY)
                self.status_changed.emit("KataGo：已就绪")
                self._send_pending_query()
            elif stripped.upper().startswith("ERROR"):
                self._report_failure(
                    EngineFailureKind.PROCESS_ERROR,
                    stripped,
                    recoverable=True,
                    request_id=self._current_request_id,
                    node_id=self._current_node_id,
                    purpose=self._current_purpose,
                )

    def _on_process_started(self) -> None:
        self._set_state(EngineState.LOADING)
        self.status_changed.emit("KataGo：进程已启动，正在加载模型…")

    def _on_process_finished(self, exit_code: int, _status: object) -> None:
        self._startup_timer.stop()
        self._analysis_stall_timer.stop()
        request_id = self._current_request_id
        node_id = self._current_node_id
        purpose = self._current_purpose
        self._ready = False
        self._current_request_id = None
        self._current_node_id = None
        self._current_purpose = None
        if self._restart_requested:
            self._restart_requested = False
            self._process_failure_reported = False
            self._set_state(EngineState.STOPPED)
            self.start()
        elif self._shutdown_requested:
            self._set_state(EngineState.STOPPED)
            self.status_changed.emit("KataGo：已停止")
        elif not self._process_failure_reported:
            self._process_failure_reported = True
            self._set_state(EngineState.FAILED)
            self._report_failure(
                EngineFailureKind.PROCESS_EXITED,
                f"KataGo意外退出，代码：{exit_code}。可以重试启动或关闭分析。",
                recoverable=True,
                request_id=request_id,
                node_id=node_id,
                purpose=purpose,
            )

    def _on_process_error(self, error: QProcess.ProcessError) -> None:
        if self._shutdown_requested or self._restart_requested:
            return
        fatal = error in (
            QProcess.ProcessError.FailedToStart,
            QProcess.ProcessError.Crashed,
        )
        if fatal and self._process_failure_reported:
            return
        request_id = self._current_request_id
        node_id = self._current_node_id
        purpose = self._current_purpose
        if fatal:
            self._startup_timer.stop()
            self._analysis_stall_timer.stop()
            self._ready = False
            self._current_request_id = None
            self._current_node_id = None
            self._current_purpose = None
            self._process_failure_reported = True
            self._set_state(EngineState.FAILED)
        message = self.process.errorString() or "未知进程错误"
        self._report_failure(
            EngineFailureKind.PROCESS_ERROR,
            f"KataGo进程错误：{message}",
            recoverable=True,
            request_id=request_id,
            node_id=node_id,
            purpose=purpose,
        )

    def _on_startup_timeout(self) -> None:
        if self._ready or self._state not in (EngineState.STARTING, EngineState.LOADING):
            return
        self._ready = False
        self._process_failure_reported = True
        self._set_state(EngineState.FAILED)
        self.status_changed.emit("KataGo：启动超时")
        self._report_failure(
            EngineFailureKind.STARTUP_TIMEOUT,
            "KataGo启动或模型加载超时。请检查显卡、模型和配置后重试。",
            recoverable=True,
            request_id=(
                str(self._pending_query.get("id", "")) if self._pending_query else None
            ),
            node_id=self._pending_node_id,
            purpose=self._pending_purpose,
        )
        if self.is_running:
            self.process.kill()

    def _on_analysis_stall_timeout(self) -> None:
        if self._current_request_id is None:
            return
        request_id = self._current_request_id
        node_id = self._current_node_id
        purpose = self._current_purpose
        if self.is_running:
            action_id = f"terminate-{uuid4()}"
            self._terminate_ids.add(action_id)
            self._write_json(
                {
                    "id": action_id,
                    "action": "terminate",
                    "terminateId": request_id,
                }
            )
        self._current_request_id = None
        self._current_node_id = None
        self._current_purpose = None
        if self._ready:
            self._set_state(EngineState.READY)
        self.status_changed.emit("KataGo：分析长时间无响应")
        self._report_failure(
            EngineFailureKind.ANALYSIS_STALLED,
            "KataGo分析长时间没有返回数据，已停止本次请求。可以重试或关闭分析。",
            recoverable=True,
            request_id=request_id,
            node_id=node_id,
            purpose=purpose,
        )
