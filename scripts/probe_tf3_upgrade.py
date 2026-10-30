"""v1.1.0.dev1: isolated, synthetic real-engine upgrade evidence (not an Elo test)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke-only", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        parser.error("output must be a new directory inside this project")
    output.mkdir(parents=True)
    runtime = json.loads((ROOT / "runtime/runtime.local.json").read_text("utf-8"))
    config = (ROOT / "runtime/configs/analysis.cfg").read_text("utf-8")
    config = "\n".join(line for line in config.splitlines() if not line.startswith("logDir"))
    config = config.replace("requireMaxBoardSize = true", "requireMaxBoardSize = false")
    config += f"\nlogDir = {output.as_posix()}/logs\nhomeDataDir = {output.as_posix()}/home\n"
    config_path = output / "analysis.cfg"
    config_path.write_text(config, encoding="utf-8")
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join(
        [str(ROOT / runtime["cudnnBin"]), runtime["cudaBin"], env.get("PATH", "")]
    )
    env["CUDA_CACHE_PATH"] = str(output / "cuda-cache")
    env["TEMP"] = env["TMP"] = str(output)
    command = [
        str(args.engine.resolve()),
        "analysis",
        "-config",
        str(config_path),
        "-model",
        str(args.model.resolve()),
        "-human-model",
        str(ROOT / runtime["humanModel"]),
        "-quit-without-waiting",
    ]
    events: queue.Queue[tuple[str, str]] = queue.Queue()
    process = subprocess.Popen(
        command,
        cwd=output,
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
    assert process.stdout is not None and process.stderr is not None

    def reader(stream: Any, name: str) -> None:
        for line in stream:
            events.put((name, line.rstrip()))

    for stream, name in ((process.stdout, "stdout"), (process.stderr, "stderr")):
        threading.Thread(target=reader, args=(stream, name), daemon=True).start()
    stderr: list[str] = []
    results: list[dict[str, Any]] = []

    def request(payload: dict[str, Any]) -> dict[str, Any]:
        start = time.monotonic()
        process.stdin.write(json.dumps(payload) + "\n")
        process.stdin.flush()
        while time.monotonic() - start < 240:
            try:
                source, line = events.get(timeout=0.2)
            except queue.Empty:
                if process.poll() is not None:
                    raise RuntimeError("engine exited: " + "\n".join(stderr[-20:])) from None
                continue
            if source == "stderr":
                stderr.append(line)
                if "Async bot thread failed" in line:
                    raise RuntimeError(line)
                continue
            response = json.loads(line)
            if response.get("id") != payload["id"]:
                continue
            if "error" in response:
                raise RuntimeError(str(response))
            if response.get("isDuringSearch") is True:
                continue
            results.append(
                {
                    "request": payload,
                    "response": response,
                    "seconds": round(time.monotonic() - start, 3),
                }
            )
            (output / "results.json").write_text(json.dumps(results, indent=2), "utf-8")
            print(payload["id"], round(time.monotonic() - start, 2), "s", flush=True)
            return response
        raise TimeoutError(payload["id"])

    def analyze(name: str, size: int, visits: int, **extra: Any) -> dict[str, Any]:
        payload = {
            "id": name,
            "moves": [],
            "initialPlayer": "B",
            "rules": "chinese",
            "komi": 7.5,
            "boardXSize": size,
            "boardYSize": size,
            "maxVisits": visits,
            "analysisPVLen": 12,
            "includePolicy": True,
            "includeOwnership": True,
        }
        payload.update(extra)
        response = request(payload)
        moves = response.get("moveInfos", [])
        assert moves and any(move.get("order") == 0 for move in moves), response
        assert len(response.get("ownership", [])) == size * size, response
        assert len(response.get("policy", [])) == size * size + 1, response
        assert 0 <= response["rootInfo"]["winrate"] <= 1, response
        return response

    try:
        request({"id": "version", "action": "query_version"})
        request({"id": "models", "action": "query_models"})
        for size in (9, 13, 19):
            response = analyze(
                f"human-{size}", size, 80, overrideSettings={"humanSLProfile": "rank_1d"}
            )
            assert len(response.get("humanPolicy", [])) == size * size + 1
            assert abs(sum(max(0, x) for x in response["humanPolicy"]) - 1) < 0.01
        if not args.smoke_only:
            capture = [["W", p] for p in ("D4", "E4", "F4", "D5", "E5", "F5")]
            capture += [
                ["B", p] for p in ("C4", "C5", "D3", "E3", "F3", "D6", "E6", "F6", "G4")
            ]
            cases = [
                ("capture", 9, {"initialStones": capture}),
                ("equivalent-opening", 19, {}),
                (
                    "balanced-opening",
                    19,
                    {"moves": [["B", "D4"], ["W", "Q16"], ["B", "Q4"], ["W", "D16"]]},
                ),
            ]
            for name, size, extra in cases:
                for repeat in range(3):
                    request({"id": f"clear-{name}-{repeat}", "action": "clear_cache"})
                    analyze(f"{name}-800-{repeat}", size, 800, **extra)
                request({"id": f"clear-{name}-ref", "action": "clear_cache"})
                analyze(f"{name}-6400-reference", size, 6400, **extra)
        return 0
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=15)
        (output / "stderr.txt").write_text("\n".join(stderr), "utf-8")
        metadata = {
            "engine": str(args.engine),
            "model": str(args.model),
            "engine_sha256": hashlib.sha256(args.engine.read_bytes()).hexdigest(),
            "model_sha256": hashlib.sha256(args.model.read_bytes()).hexdigest(),
            "note": "Synthetic integration/stability evidence, not an Elo or universal "
            "strength guarantee.",
        }
        (output / "metadata.json").write_text(json.dumps(metadata, indent=2), "utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
