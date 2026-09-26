"""Verify KataGo incremental reports and cancellation without modifying project data."""

from __future__ import annotations

import json
import os
import pathlib
import queue
import subprocess
import sys
import threading
import time
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNTIME_FILE = ROOT / "runtime" / "runtime.local.json"


def _resolved(value: str) -> pathlib.Path:
    path = pathlib.Path(value)
    return path if path.is_absolute() else ROOT / path


def _reader(stream: Any, target: queue.Queue[tuple[str, str]], name: str) -> None:
    for line in iter(stream.readline, ""):
        target.put((name, line.rstrip()))


def main() -> int:
    runtime = json.loads(RUNTIME_FILE.read_text(encoding="utf-8"))
    engine = _resolved(runtime["engine"])
    model = _resolved(runtime["model"])
    config = _resolved(runtime["analysisConfig"])
    cudnn_bin = _resolved(runtime["cudnnBin"])
    cuda_bin = pathlib.Path(runtime["cudaBin"])

    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(cudnn_bin), str(cuda_bin), env.get("PATH", "")])
    process = subprocess.Popen(
        [
            str(engine),
            "analysis",
            "-config",
            str(config),
            "-model",
            str(model),
            "-quit-without-waiting",
        ],
        cwd=ROOT,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None

    events: queue.Queue[tuple[str, str]] = queue.Queue()
    threading.Thread(
        target=_reader, args=(process.stdout, events, "stdout"), daemon=True
    ).start()
    threading.Thread(
        target=_reader, args=(process.stderr, events, "stderr"), daemon=True
    ).start()

    analysis_id = "smoke-cancel-analysis"
    terminate_id = "smoke-cancel-action"
    query = {
        "id": analysis_id,
        "moves": [],
        "initialPlayer": "B",
        "rules": "chinese",
        "komi": 7.5,
        "boardXSize": 19,
        "boardYSize": 19,
        "maxVisits": 1_000_000,
        "analysisPVLen": 5,
        "reportDuringSearchEvery": 0.2,
    }
    process.stdin.write(json.dumps(query, separators=(",", ":")) + "\n")
    process.stdin.flush()

    during_reports = 0
    terminate_sent = False
    terminate_ack = False
    final_result: dict[str, Any] | None = None
    stderr_tail: list[str] = []
    deadline = time.monotonic() + 180.0

    try:
        while time.monotonic() < deadline:
            if process.poll() is not None and events.empty():
                break
            try:
                source, line = events.get(timeout=0.1)
            except queue.Empty:
                continue
            if source == "stderr":
                stderr_tail.append(line)
                stderr_tail = stderr_tail[-30:]
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            if payload.get("id") == terminate_id:
                terminate_ack = True
                continue
            if payload.get("id") != analysis_id:
                continue
            if payload.get("isDuringSearch") is True:
                during_reports += 1
                if not terminate_sent:
                    action = {
                        "id": terminate_id,
                        "action": "terminate",
                        "terminateId": analysis_id,
                    }
                    process.stdin.write(json.dumps(action, separators=(",", ":")) + "\n")
                    process.stdin.flush()
                    terminate_sent = True
                continue
            if payload.get("isDuringSearch") is False:
                final_result = payload
                if terminate_ack:
                    break
    finally:
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=10)

    if final_result is None:
        print("No final result after cancellation.", file=sys.stderr)
        if stderr_tail:
            print("\n".join(stderr_tail), file=sys.stderr)
        return 1

    visits = (final_result.get("rootInfo") or {}).get("visits", 0)
    summary = {
        "incremental_reports": during_reports,
        "terminate_sent": terminate_sent,
        "terminate_acknowledged": terminate_ack,
        "final_result_received": True,
        "visits_before_cancel": visits,
        "configured_max_visits": query["maxVisits"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    checks = [
        during_reports >= 1,
        terminate_sent,
        terminate_ack,
        0 < visits < query["maxVisits"],
    ]
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
