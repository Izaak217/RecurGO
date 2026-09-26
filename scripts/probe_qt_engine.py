"""Exercise the Qt KataGo service against the real local CUDA runtime."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QTimer

from recurgo.domain import GameTree
from recurgo.engine import AnalysisUpdate, EngineRuntime, KataGoEngine


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    application = QCoreApplication(sys.argv)
    engine = KataGoEngine(EngineRuntime.load(root))
    tree = GameTree()
    incremental_count = 0
    result_code = 2

    def on_update(update: AnalysisUpdate) -> None:
        nonlocal incremental_count
        incremental_count += 1
        move_infos = update.payload.get("moveInfos")
        if isinstance(move_infos, list) and move_infos:
            first = move_infos[0]
            if isinstance(first, dict):
                print(
                    "update",
                    incremental_count,
                    first.get("move"),
                    first.get("visits"),
                    first.get("winrate"),
                )

    def on_finished(update: AnalysisUpdate) -> None:
        nonlocal result_code
        root_info = update.payload.get("rootInfo")
        move_infos = update.payload.get("moveInfos")
        valid = (
            isinstance(root_info, dict)
            and isinstance(move_infos, list)
            and len(move_infos) > 0
            and incremental_count >= 1
        )
        print(
            "finished",
            f"updates={incremental_count}",
            f"visits={root_info.get('visits') if isinstance(root_info, dict) else None}",
            f"candidates={len(move_infos) if isinstance(move_infos, list) else 0}",
        )
        result_code = 0 if valid else 3
        engine.shutdown()
        application.quit()

    def on_error(message: str) -> None:
        nonlocal result_code
        print("engine-error", message)
        result_code = 4
        engine.shutdown()
        application.quit()

    def on_timeout() -> None:
        nonlocal result_code
        print("timeout waiting for Qt engine result")
        result_code = 5
        engine.shutdown()
        application.quit()

    engine.analysis_updated.connect(on_update)
    engine.analysis_finished.connect(on_finished)
    engine.engine_error.connect(on_error)
    QTimer.singleShot(30_000, on_timeout)
    engine.analyze(
        tree=tree,
        node_id=tree.current_id,
        rules="chinese",
        komi=7.5,
        max_visits=100,
        human_profile="rank_3k",
    )
    application.exec()
    return result_code


if __name__ == "__main__":
    raise SystemExit(main())
