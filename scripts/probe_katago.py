"""Read-only smoke test for the project's local KataGo analysis runtime."""

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


def _resolved(relative_or_absolute: str) -> pathlib.Path:
    path = pathlib.Path(relative_or_absolute)
    return path if path.is_absolute() else ROOT / path


def _reader(stream: Any, target: queue.Queue[tuple[str, str]], name: str) -> None:
    for line in iter(stream.readline, ""):
        target.put((name, line.rstrip()))


def main() -> int:
    runtime = json.loads(RUNTIME_FILE.read_text(encoding="utf-8"))
    engine = _resolved(runtime["engine"])
    model = _resolved(runtime["model"])
    human_model = _resolved(runtime["humanModel"])
    config = _resolved(runtime["analysisConfig"])
    cudnn_bin = _resolved(runtime["cudnnBin"])
    cuda_bin = pathlib.Path(runtime["cudaBin"])

    missing = [
        str(path)
        for path in (engine, model, human_model, config, cudnn_bin, cuda_bin)
        if not path.exists()
    ]
    if missing:
        print("Missing required runtime paths:", file=sys.stderr)
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(cudnn_bin), str(cuda_bin), env.get("PATH", "")])

    command = [
        str(engine),
        "analysis",
        "-config",
        str(config),
        "-model",
        str(model),
        "-human-model",
        str(human_model),
        "-quit-without-waiting",
    ]
    process = subprocess.Popen(
        command,
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
    stdout_thread = threading.Thread(
        target=_reader, args=(process.stdout, events, "stdout"), daemon=True
    )
    stderr_thread = threading.Thread(
        target=_reader, args=(process.stderr, events, "stderr"), daemon=True
    )
    stdout_thread.start()
    stderr_thread.start()

    request = {
        "id": "smoke-empty-board",
        "moves": [],
        "initialPlayer": "B",
        "rules": "chinese",
        "komi": 7.5,
        "boardXSize": 19,
        "boardYSize": 19,
        "maxVisits": 80,
        "analysisPVLen": 8,
        "includePolicy": True,
        "includeOwnership": True,
        "reportDuringSearchEvery": 0.25,
        "overrideSettings": {"humanSLProfile": "rank_5k", "ignorePreRootHistory": False},
    }

    deadline = time.monotonic() + 180.0
    request_sent = False
    final_result: dict[str, Any] | None = None
    stderr_tail: list[str] = []

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
                if "Started, ready to begin handling requests" in line and not request_sent:
                    process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
                    process.stdin.flush()
                    request_sent = True
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("id") != request["id"]:
                continue
            if payload.get("isDuringSearch") is False:
                final_result = payload
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
        print("KataGo did not return a final analysis result.", file=sys.stderr)
        if stderr_tail:
            print("\n".join(stderr_tail), file=sys.stderr)
        return 1

    move_infos = final_result.get("moveInfos") or []
    root_info = final_result.get("rootInfo") or {}
    ownership = final_result.get("ownership") or []
    policy = final_result.get("policy") or []
    human_policy = final_result.get("humanPolicy") or []
    summary = {
        "engine_started": True,
        "turn_number": final_result.get("turnNumber"),
        "root_visits": root_info.get("visits"),
        "black_winrate": root_info.get("winrate"),
        "black_score_lead": root_info.get("scoreLead"),
        "candidate_count": len(move_infos),
        "top_move": move_infos[0].get("move") if move_infos else None,
        "top_pv": move_infos[0].get("pv") if move_infos else None,
        "ownership_points": len(ownership),
        "policy_points": len(policy),
        "human_policy_points": len(human_policy),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    checks = [
        summary["candidate_count"] > 0,
        bool(summary["top_move"]),
        len(ownership) == 19 * 19,
        len(policy) == 19 * 19 + 1,
        len(human_policy) == 19 * 19 + 1,
    ]
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
