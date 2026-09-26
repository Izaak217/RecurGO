"""Measure real KataGo -> automatic local Ollama explanations in an isolated game."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from recurgo.domain import GameTree, explain_candidate
from recurgo.domain.coordinates import gtp_to_point
from recurgo.engine import EngineRuntime, KataGoEngine
from recurgo.llm.ollama import OllamaClient
from recurgo.llm.settings import OllamaSettings
from recurgo.storage import GameRepository
from recurgo.ui import MainWindow


class TimedClient(OllamaClient):
    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.started: dict[str, float] = {}
        self.first_text: dict[str, float] = {}
        self.prompts: dict[str, list[dict[str, str]]] = {}

    def generate(self, base_url: str, model: str, messages: list[dict[str, str]]) -> str:
        started = perf_counter()
        request_id = super().generate(base_url, model, messages)
        self.started[request_id] = started
        self.prompts[request_id] = messages
        print("generation-started", request_id, flush=True)
        return request_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=OllamaSettings().model)
    parser.add_argument("--base-url", default=OllamaSettings().base_url)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = (
        root
        / "data"
        / "verification"
        / ("ollama-" + datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid4().hex[:6])
    )
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    # The offscreen platform may not discover the Windows font collection.
    if app.platformName() == "offscreen" and "Microsoft YaHei" not in QFontDatabase.families():
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc"
        if font.is_file():
            QFontDatabase.addApplicationFont(str(font))
    app.setFont(QFont("Microsoft YaHei", 10))
    repository = GameRepository(output / "probe.db")
    repository.save_setting(
        "ollama", OllamaSettings(True, args.base_url, args.model).to_mapping()
    )
    repository.save_setting("appearance_audio", {"muted": True})
    tree = GameTree()
    for move in ("D4", "Q16", "D16", "Q4", "C3", "R17", "C17", "R3"):
        tree.play(gtp_to_point(move))
    record = repository.create_game(tree, name="Ollama verification", mode="manual")
    engine = KataGoEngine(EngineRuntime.load(root))
    client = TimedClient(app)
    window = MainWindow(repository, record, tree, engine, ollama_client=client)
    window.show()
    # The application intentionally starts with real-time analysis switched off.
    # Exercise the same opt-in path as a user before expecting an automatic explanation.
    window.analysis_checkbox.setChecked(True)
    report: dict[str, object] = {
        "version": "0.1.2",
        "model": args.model,
        "endpoint": args.base_url,
        "scenario": "19x19 opening; existing application KataGo search budget unchanged",
        "timing_scope": (
            "First text and completion start at client.generate, including show/chat; "
            "excludes KataGo search and automatic debounce. Rule render is a 100-call CPU "
            "mean, not total UI latency. Second sample repeats the same snapshot."
        ),
        "samples": [],
    }
    samples: list[dict[str, object]] = []
    exit_code = 1
    finished = False

    def finish(success: bool, error: str = "") -> None:
        nonlocal finished, exit_code
        if finished:
            return
        finished = True
        exit_code = 0 if success else 1
        report.update({"success": success, "error": error, "samples": samples})
        (output / "result.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False), flush=True)
        print("report-directory", output, flush=True)
        window.close()
        app.quit()

    def partial(request_id: str, text: str) -> None:
        if request_id not in client.first_text and text:
            client.first_text[request_id] = perf_counter() - client.started[request_id]
            print("first-text-seconds", round(client.first_text[request_id], 3), flush=True)

    def complete(request_id: str, text: str) -> None:
        if finished or request_id not in client.started:
            return
        complete_seconds = perf_counter() - client.started[request_id]
        payload = window._displayed_analysis_payload
        if payload is None or not window._candidate_payloads:
            finish(False, "No KataGo snapshot remained after explanation")
            return
        candidate = window._candidate_payloads[0]
        if candidate.get("order") != 0 or window.ollama_explanation.toPlainText() != text:
            finish(False, "UI text or first candidate does not match the expected result")
            return
        original_snapshot = json.loads(client.prompts[request_id][1]["content"])
        if str(candidate["move"]) != original_snapshot["selected_candidate"]["move"]:
            finish(False, "Displayed candidate changed during generation")
            return
        started = perf_counter()
        for _ in range(100):
            explain_candidate(tree.current.state, payload, candidate, rank=1).render()
        rule_ms = (perf_counter() - started) * 1000 / 100
        sample = {
            "number": len(samples) + 1,
            "first_text_seconds": client.first_text.get(request_id),
            "complete_seconds": complete_seconds,
            "immediate_rule_render_mean_ms": rule_ms,
            "candidate": candidate["move"],
            "candidate_order": candidate.get("order"),
            "candidate_visits": candidate.get("visits"),
            "text": text,
        }
        samples.append(sample)
        (output / f"prompt-{len(samples)}.json").write_text(
            json.dumps(client.prompts[request_id], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        window.grab().save(str(output / f"window-{len(samples)}.png"))
        print("generation-completed", len(samples), sample["complete_seconds"], flush=True)
        if len(samples) < 2:
            QTimer.singleShot(500, window._generate_ollama_explanation)
        else:
            finish(True)

    client.explanation_partial.connect(partial)
    client.explanation_ready.connect(complete)
    client.request_failed.connect(lambda _request_id, error: finish(False, error))
    engine.engine_error.connect(lambda error: finish(False, error))
    QTimer.singleShot(360_000, lambda: finish(False, "End-to-end timeout"))
    print("verification-directory", output, flush=True)
    app.exec()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
