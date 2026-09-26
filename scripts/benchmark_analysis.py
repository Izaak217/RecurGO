"""Measure local KataGo JSON-analysis latency at several visit budgets."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import threading
import time
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNTIME_FILE = ROOT / "runtime" / "runtime.local.json"


def _resolved(value: str) -> pathlib.Path:
    path = pathlib.Path(value)
    return path if path.is_absolute() else ROOT / path


def _drain(stream: Any) -> None:
    for _line in iter(stream.readline, ""):
        pass


def main() -> int:
    runtime = json.loads(RUNTIME_FILE.read_text(encoding="utf-8"))
    engine = _resolved(runtime["engine"])
    model = _resolved(runtime["model"])
    config = _resolved(runtime["analysisConfig"])
    cudnn_bin = _resolved(runtime["cudnnBin"])
    cuda_bin = pathlib.Path(runtime["cudaBin"])

    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(cudnn_bin), str(cuda_bin), env.get("PATH", "")])
    started_at = time.perf_counter()
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
    threading.Thread(target=_drain, args=(process.stderr,), daemon=True).start()

    test_cases = [
        (100, []),
        (
            400,
            [["B", "D4"], ["W", "Q16"], ["B", "Q4"], ["W", "D16"]],
        ),
        (
            800,
            [
                ["B", "D4"],
                ["W", "Q16"],
                ["B", "Q4"],
                ["W", "D16"],
                ["B", "Q10"],
                ["W", "D10"],
                ["B", "K4"],
                ["W", "K16"],
            ],
        ),
        (
            1600,
            [
                ["B", "D4"],
                ["W", "Q16"],
                ["B", "Q4"],
                ["W", "D16"],
                ["B", "Q10"],
                ["W", "D10"],
                ["B", "K4"],
                ["W", "K16"],
                ["B", "C6"],
                ["W", "R14"],
                ["B", "R6"],
                ["W", "C14"],
            ],
        ),
    ]
    results: list[dict[str, Any]] = []
    first_result_at: float | None = None

    try:
        for index, (visits, moves) in enumerate(test_cases):
            query_id = f"benchmark-{visits}"
            request = {
                "id": query_id,
                "moves": moves,
                "rules": "chinese",
                "komi": 7.5,
                "boardXSize": 19,
                "boardYSize": 19,
                "maxVisits": visits,
                "analysisPVLen": 8,
                "includePolicy": False,
                "includeOwnership": False,
            }
            sent_at = time.perf_counter()
            process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
            process.stdin.flush()
            while True:
                line = process.stdout.readline()
                if not line:
                    raise RuntimeError(
                        f"KataGo exited before completing {query_id}: {process.poll()}"
                    )
                payload = json.loads(line)
                if payload.get("id") != query_id:
                    continue
                if payload.get("isDuringSearch") is not False:
                    continue
                finished_at = time.perf_counter()
                if index == 0:
                    first_result_at = finished_at
                root = payload.get("rootInfo") or {}
                move_infos = payload.get("moveInfos") or []
                results.append(
                    {
                        "requested_visits": visits,
                        "actual_root_visits": root.get("visits"),
                        "latency_seconds": round(finished_at - sent_at, 3),
                        "top_move": move_infos[0].get("move") if move_infos else None,
                    }
                )
                break
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=10)

    summary = {
        "process_start_to_first_result_seconds": (
            round(first_result_at - started_at, 3) if first_result_at else None
        ),
        "cases": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
