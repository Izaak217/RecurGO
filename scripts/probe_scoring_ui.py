"""Render and verify the completed Chinese scoring UI."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from recurgo.domain import BoardState, Color, Point  # noqa: E402
from recurgo.ui.scoring_dialog import ScoringDialog  # noqa: E402


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    state = BoardState.from_setup(
        {
            Point(0, 0): Color.BLACK,
            Point(1, 0): Color.BLACK,
            Point(0, 1): Color.BLACK,
            Point(1, 1): Color.WHITE,
            Point(17, 17): Color.WHITE,
            Point(18, 17): Color.WHITE,
            Point(17, 18): Color.WHITE,
        }
    )
    application = QApplication(sys.argv)
    application.setFont(QFont("Microsoft YaHei UI", 10))
    dialog = ScoringDialog(
        state,
        rules="chinese",
        komi=7.5,
        last_move=Point(17, 18),
    )
    result_code = 2

    def verify() -> None:
        nonlocal result_code
        dialog._toggle_dead_group(1, 1)
        dialog._confirm()
        artifact_dir = root / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = artifact_dir / "scoring_dialog_probe.png"
        saved = dialog.grab().save(str(screenshot_path))
        valid = (
            dialog.confirmed_score is not None
            and not dialog.stay_button.isHidden()
            and not dialog.new_game_button.isHidden()
            and saved
        )
        result_text = dialog.confirmed_score.display_result if dialog.confirmed_score else None
        print(
            "scoring-ui",
            f"result={result_text}",
            f"saved={saved}",
            f"screenshot={screenshot_path}",
        )
        result_code = 0 if valid else 3
        dialog.close()
        application.quit()

    dialog.show()
    QTimer.singleShot(100, verify)
    application.exec()
    return result_code


if __name__ == "__main__":
    raise SystemExit(main())
