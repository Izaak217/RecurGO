"""v1.0.1: real final-position ownership probe; all outputs stay under build/."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from recurgo.app import writable_analysis_runtime  # noqa: E402
from recurgo.domain import BoardState, Color, GameTree, Point  # noqa: E402
from recurgo.engine import AnalysisUpdate, EngineRuntime, KataGoEngine  # noqa: E402
from recurgo.ui.scoring_dialog import ScoringDialog  # noqa: E402


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=root)
    args = parser.parse_args()
    output = root / "build" / "scoring-engine-probe"
    output.mkdir(parents=True, exist_ok=True)
    application = QApplication(sys.argv[:1])
    runtime = EngineRuntime.load(
        args.runtime_root,
        local_dependencies_root=root / "runtime" / "cuda_deps",
    )
    engine = KataGoEngine(writable_analysis_runtime(runtime, output))
    tree = GameTree(
        BoardState.from_setup(
            {
                Point(x, y): Color.BLACK if x < 9 else Color.WHITE
                for y in range(19)
                for x in range(19)
                if x != 9 and (x, y) not in ((0, 0), (0, 2), (18, 0), (18, 2))
            }
        )
    )
    dialog = ScoringDialog(
        tree.current.state,
        rules="chinese",
        komi=7.5,
        last_move=None,
        engine=engine,
        tree=tree,
        max_visits=800,
    )
    code = 2

    def finished(update: AnalysisUpdate) -> None:
        nonlocal code
        if update.purpose != "scoring":
            return
        ownership = update.payload.get("ownership", [])
        visits = update.payload.get("rootInfo", {}).get("visits", 0)
        valid = len(ownership) == 361 and visits >= 800 and dialog._has_map
        result = {
            "valid": valid,
            "visits": visits,
            "points": len(ownership),
            "pending": dialog.ownership.count(2),
            "runtime": str(args.runtime_root),
        }
        (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)
        code = 0 if valid else 3
        dialog.reject()
        engine.shutdown()
        application.quit()

    def failed(message: str) -> None:
        nonlocal code
        print(message, flush=True)
        code = 4
        dialog.reject()
        engine.shutdown()
        application.quit()

    engine.analysis_finished.connect(finished)
    engine.engine_error.connect(failed)
    QTimer.singleShot(180_000, lambda: failed("Scoring probe timed out"))
    application.exec()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
