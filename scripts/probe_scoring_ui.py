"""v1.0.1.dev1: render dense scoring fixtures; these are UI, not accuracy, tests."""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from recurgo.domain import BoardState, Color, Point  # noqa: E402
from recurgo.i18n import Language  # noqa: E402
from recurgo.ui.board_widget import BoardWidget  # noqa: E402
from recurgo.ui.scoring_dialog import ScoringDialog  # noqa: E402


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = root / "build" / f"scoring-ui-dev1-{stamp}-{uuid4().hex[:8]}"
    output.mkdir(parents=True, exist_ok=False)
    # Dense visual fixture includes living and dead stones plus low-magnitude ownership.
    stones = {}
    raw = []
    for y in range(19):
        for x in range(19):
            side = 1 if x < 9 + (y % 5 - 2) else -1
            raw.append(side * (0.12 if (x + y) % 3 == 0 else 0.97))
            if (x * 7 + y * 11) % 5 < 3:
                color = Color.BLACK if side == 1 else Color.WHITE
                if (x + y * 3) % 17 == 0:
                    color = color.opponent
                stones[Point(x, y)] = color
    state = BoardState.from_setup(stones)
    application = QApplication(sys.argv)
    application.setStyle("Fusion")
    palette = application.palette()
    for role, value in (
        (QPalette.ColorRole.Window, "#202020"),
        (QPalette.ColorRole.WindowText, "#f0f0f0"),
        (QPalette.ColorRole.Base, "#292929"),
        (QPalette.ColorRole.Text, "#f0f0f0"),
        (QPalette.ColorRole.Button, "#393939"),
        (QPalette.ColorRole.ButtonText, "#f0f0f0"),
    ):
        palette.setColor(role, QColor(value))
    application.setPalette(palette)
    for name in ("msyh.ttc", "segoeui.ttf"):
        QFontDatabase.addApplicationFont(str(Path(os.environ["WINDIR"]) / "Fonts" / name))
    application.setFont(QFont("Microsoft YaHei UI", 10))
    live = BoardWidget()
    live.resize(800, 800)
    live.set_position(state, None)
    live.set_ownership(raw)
    live.show()
    application.processEvents()
    assert live.grab().save(str(output / "live-territory.png"))
    live.close()
    for language in ("zh", "en"):
        render_language(application, output, state, raw, language)
    print(f"Scoring UI: {output}", flush=True)
    return 0


def render_language(
    application: QApplication,
    output: Path,
    state: BoardState,
    raw: list[float],
    language: Language,
) -> None:
    dialog = ScoringDialog(
        state,
        rules="chinese",
        komi=7.5,
        last_move=None,
        initial_ownership=raw,
        language=language,
    )
    dialog.resize(1320, 900)
    dialog.show()
    application.processEvents()
    original_owners = dialog.ownership
    original_label = dialog.score_label.text()
    for shown in (False, True):
        dialog.show_dead_checkbox.setChecked(shown)
        application.processEvents()
        name = f"{language}-dead-{'shown' if shown else 'hidden'}.png"
        assert dialog.grab().save(str(output / name))
        assert dialog.ownership == original_owners
        assert dialog.score_label.text() == original_label
    dialog.brush_combo.setCurrentIndex(4)
    dialog._edit_point(8, 8)
    dialog._edit_point(9, 8)
    dialog.brush_combo.setCurrentIndex(3)
    dialog._edit_point(10, 8)
    application.processEvents()
    assert dialog.grab().save(str(output / f"{language}-manual-marks.png"))
    assert not dialog.confirm_button.isEnabled()
    dialog._reset_points()
    dialog._confirm()
    assert dialog.confirmed_score is not None
    application.processEvents()
    assert dialog.grab().save(str(output / f"{language}-confirmed.png"))
    for shown in (False, True):
        dialog.show_dead_checkbox.setChecked(shown)
        assert dialog.ownership == original_owners
    dialog.close()


if __name__ == "__main__":
    raise SystemExit(main())
