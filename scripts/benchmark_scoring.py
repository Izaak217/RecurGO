"""v1.0.1 revision: compare real first scoring suggestions with labelled shapes.

Outputs stay in a unique build directory. A high-visit prediction is a comparison,
not ground truth: exact test positions have independently specified expected maps.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QTimer  # noqa: E402

from recurgo.app import writable_analysis_runtime  # noqa: E402
from recurgo.domain import BoardState, Color, GameTree, Point  # noqa: E402
from recurgo.domain.scoring_estimate import (  # noqa: E402
    count_assignments,
    ownership_points,
    prepare_proposal,
)
from recurgo.engine import AnalysisUpdate, EngineRuntime, KataGoEngine  # noqa: E402


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=root)
    parser.add_argument("--visits", type=int, nargs="+", default=[800, 3200, 12800])
    args = parser.parse_args()
    output = root / "build" / (
        f"scoring-benchmark-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    )
    output.mkdir(parents=True, exist_ok=False)
    cases = json.loads((root / "tests/fixtures/scoring_cases_19.json").read_text())
    queue = [(case, visits) for case in cases for visits in args.visits]
    application = QCoreApplication(sys.argv[:1])
    runtime = EngineRuntime.load(
        args.runtime_root, local_dependencies_root=root / "runtime/cuda_deps"
    )
    engine = KataGoEngine(writable_analysis_runtime(runtime, output))
    reports: list[dict] = []
    code = 0
    current: dict = {}
    watchdog = QTimer()
    watchdog.setSingleShot(True)

    def fail(message: str) -> None:
        nonlocal code
        code = 1
        print(message, flush=True)
        (output / "error.txt").write_text(message, encoding="utf-8")
        engine.shutdown()
        application.quit()

    def next_case() -> None:
        if not queue:
            (output / "summary.json").write_text(
                json.dumps(reports, indent=2), encoding="utf-8"
            )
            print(f"Results: {output}", flush=True)
            engine.shutdown()
            application.quit()
            return
        case, visits = queue.pop(0)
        state = BoardState.from_setup({
            Point(x, y): Color.BLACK if ch == "X" else Color.WHITE
            for y, row in enumerate(case["board"]) for x, ch in enumerate(row) if ch != "."
        }, size=len(case["board"]))
        tree = GameTree(state)
        for _ in range(case["passes"]):
            tree.play(None)
        current.update(case=case, tree=tree, visits=visits, started=time.perf_counter())
        print(f"Analyzing {case['name']} at {visits} visits", flush=True)
        engine.analyze(
            tree=tree, node_id=tree.current_id, rules="chinese", komi=7.5,
            max_visits=visits, human_profile=None,
            include_ownership=True, include_ownership_stdev=True, purpose="scoring",
        )
        watchdog.start(180_000)

    def finished(update: AnalysisUpdate) -> None:
        watchdog.stop()
        case = current["case"]
        state = current["tree"].current.state
        payload = update.payload
        raw, stdev = payload.get("ownership"), payload.get("ownershipStdev")
        old = ownership_points(raw, state.size)
        revised = prepare_proposal(state, raw, stdev)
        if old is None or revised is None or stdev is None:
            fail(f"Missing or invalid ownership statistics for {case['name']}")
            return
        expected = [{"B": 1, "W": -1, "S": 0, "?": 2}[v]
                    for row in case["expected"] for v in row]

        def metrics(owners: tuple[int, ...]) -> dict:
            exact = all(v != 2 for v in expected)
            score = count_assignments(state, owners, komi=7.5)
            reference = count_assignments(state, expected, komi=7.5)
            return {
                "wrong_assigned": sum(v != e and v != 2
                                      for v, e in zip(owners, expected, strict=True)
                                      if e != 2),
                "unresolved": owners.count(2),
                "wrong_shared": sum(v == 0 and e != 0
                                    for v, e in zip(owners, expected, strict=True)),
                "margin_error_stones": (
                    abs(score.black_lead_points - reference.black_lead_points) / 2
                    if exact and 2 not in owners else None
                ),
            }

        report = {
            "case": case["name"], "visits": current["visits"],
            "actual_visits": payload.get("rootInfo", {}).get("visits"),
            "seconds": round(time.perf_counter() - current["started"], 3),
            "old": metrics(old), "revised": metrics(revised),
        }
        reports.append(report)
        (output / f"{case['name']}-{current['visits']}.json").write_text(
            json.dumps({"report": report, "engine": payload, "revised": revised}, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(report), flush=True)
        QTimer.singleShot(0, next_case)

    engine.analysis_finished.connect(finished)
    engine.engine_error.connect(fail)
    watchdog.timeout.connect(lambda: fail("Scoring benchmark timed out"))
    QTimer.singleShot(0, next_case)
    application.exec()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
