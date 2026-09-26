"""Verify a real user move -> KataGo Human SL move -> autosave UI cycle."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from recurgo.domain import Color, GameTree  # noqa: E402
from recurgo.engine import EngineRuntime, KataGoEngine  # noqa: E402
from recurgo.storage import GameRepository  # noqa: E402
from recurgo.ui import MainWindow  # noqa: E402


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    database_path = root / "data" / "integration_probe.db"
    repository = GameRepository(database_path)
    tree = GameTree()
    record = repository.create_game(tree, name="真实AI对战链路测试", mode="assisted")
    application = QApplication(sys.argv)
    application.setFont(QFont("Microsoft YaHei UI", 10))
    engine = KataGoEngine(EngineRuntime.load(root))
    window = MainWindow(repository, record, tree, engine)
    window.mode_combo.setCurrentText("辅助对战")
    window.difficulty_combo.setCurrentText("中级")
    window.analysis_checkbox.setChecked(True)
    window.show()
    result_code = 2
    elapsed_ticks = 0

    def poll() -> None:
        nonlocal result_code, elapsed_ticks
        elapsed_ticks += 1
        state = window.tree.current.state
        first_candidate = window.candidate_table.item(0, 0)
        analysis_visible = (
            first_candidate is not None
            and first_candidate.text() != "—"
            and window.candidate_table.rowCount() >= 5
            and "分析完成" in window.engine_status.text()
        )
        if state.move_number == 2 and state.to_play is Color.BLACK and analysis_visible:
            reloaded_record, reloaded_tree = repository.load_game(record.id)
            snapshot_count = int(
                repository.connection.execute(
                    "SELECT COUNT(*) FROM analysis_snapshots WHERE game_id = ?",
                    (record.id,),
                ).fetchone()[0]
            )
            artifact_dir = root / "artifacts"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            screenshot_path = artifact_dir / "ui_battle_probe.png"
            screenshot_saved = window.grab().save(str(screenshot_path))
            valid = (
                reloaded_record.mode == "assisted"
                and reloaded_tree.current.state.move_number == 2
                and snapshot_count >= 1
                and screenshot_saved
                and "黑贴3¾子" in window.game_info.text()
            )
            print(
                "battle-cycle",
                f"moves={state.move_number}",
                f"to_play={state.to_play.short_name}",
                f"saved={valid}",
                f"snapshots={snapshot_count}",
                f"candidate={first_candidate.text()}",
                f"rules={window.game_info.text().splitlines()[-2]}",
                f"screenshot={screenshot_path}",
            )
            result_code = 0 if valid else 3
            timer.stop()
            window.close()
            application.quit()
        elif elapsed_ticks >= 300:
            print("timeout waiting for AI move", window.engine_status.text())
            result_code = 4
            timer.stop()
            window.close()
            application.quit()

    timer = QTimer()
    timer.setInterval(100)
    timer.timeout.connect(poll)
    timer.start()
    QTimer.singleShot(0, lambda: window._play_point(3, 3))
    application.exec()
    return result_code


if __name__ == "__main__":
    raise SystemExit(main())
