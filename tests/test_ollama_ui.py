from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtTest import QSignalSpy
from pytestqt.qtbot import QtBot

from recurgo.domain import GameTree
from recurgo.engine import PRESETS, AnalysisUpdate, KataGoEngine
from recurgo.llm.ollama import OllamaClient
from recurgo.llm.settings import OllamaSettings
from recurgo.storage import GameRepository
from recurgo.ui.i18n import Language
from recurgo.ui.main_window import MainWindow
from recurgo.ui.ollama_dialog import OllamaSettingsDialog


class FakeOllama(QObject):
    models_ready = Signal(str, object)
    explanation_partial = Signal(str, str)
    explanation_ready = Signal(str, str)
    request_failed = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self.generations: list[tuple[str, str, list[dict[str, str]]]] = []
        self.model_queries: list[str] = []
        self.cancelled: list[str | None] = []
        self.shutdown_count = 0
        self._counter = 0

    def _request_id(self) -> str:
        self._counter += 1
        return f"ollama-{self._counter}"

    def generate(self, base_url: str, model: str, messages: list[dict[str, str]]) -> str:
        self.generations.append((base_url, model, deepcopy(messages)))
        return self._request_id()

    def list_models(self, base_url: str) -> str:
        OllamaSettings(base_url=base_url)
        self.model_queries.append(base_url)
        return self._request_id()

    def cancel(self, request_id: str | None = None) -> None:
        self.cancelled.append(request_id)

    def shutdown(self) -> None:
        self.shutdown_count += 1


class SilentAudio:
    def set_muted(self, _muted: bool) -> None:
        return

    def play_move(self, *, captured: bool) -> None:
        return


class BusyEngine:
    def __init__(self) -> None:
        self.state = "ready"
        self.active_request_id: str | None = None
        self.queries: list[dict[str, object]] = []
        self.runtime = SimpleNamespace(engine_version="test", model_sha256="test-model")

    def stop_analysis(self) -> None:
        self.state = "ready"
        self.active_request_id = None

    def analyze(self, **query: object) -> str:
        self.queries.append(query)
        self.state = "analyzing"
        self.active_request_id = "engine-next"
        return self.active_request_id

    def shutdown(self) -> None:
        self.stop_analysis()


def _payload() -> dict[str, object]:
    return {
        "id": "katago-snapshot-1",
        "isDuringSearch": False,
        "rootInfo": {"winrate": 0.55, "scoreLead": 1.0, "visits": 800},
        "moveInfos": [
            {
                "move": "D4",
                "order": 0,
                "winrate": 0.55,
                "scoreLead": 1.0,
                "visits": 600,
                "pv": ["D4", "Q16"],
            },
            {
                "move": "Q16",
                "order": 1,
                "winrate": 0.548,
                "scoreLead": 0.95,
                "visits": 200,
                "pv": ["Q16", "D4"],
            },
        ],
    }


@pytest.fixture
def ui(qtbot: QtBot, tmp_path: Path) -> tuple[MainWindow, FakeOllama, GameRepository]:
    repository = GameRepository(tmp_path / "ollama-ui.db")
    repository.save_setting("appearance_audio", {"language": "zh"})
    repository.save_setting("ollama", OllamaSettings(enabled=True).to_mapping())
    tree = GameTree()
    record = repository.create_game(tree)
    client = FakeOllama()
    window = MainWindow(
        repository,
        record,
        tree,
        audio_feedback=SilentAudio(),
        ollama_client=cast(OllamaClient, client),
    )
    qtbot.addWidget(window)
    return window, client, repository


def test_regeneration_uses_selected_snapshot_and_prevents_duplicate_request(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, client, _repository = ui
    window._display_analysis_payload(window.tree.current_id, _payload())
    window._candidate_selected(1, 0)
    assert not client.generations
    assert window.candidate_table.item(0, 0).text() == "D4"
    assert window._candidate_explanation is not None
    selected = window._candidate_explanation
    rule_text = window.explanation.toPlainText()
    captured: dict[str, object] = {}

    def build_messages(
        state: object, explanation: object, **parameters: object
    ) -> list[dict[str, str]]:
        captured.update(state=state, explanation=explanation, **parameters)
        return [{"role": "user", "content": "frozen Q16 snapshot"}]

    monkeypatch.setattr("recurgo.ui.main_window.build_ollama_messages", build_messages)
    window._generate_ollama_explanation()
    window._generate_ollama_explanation()
    assert len(client.generations) == 1
    assert captured["state"] is window.tree.current.state
    assert captured["explanation"] is selected
    assert captured["rules"] == window.record.rules
    assert captured["komi"] == window.record.komi
    assert client.generations[0][2] == [{"role": "user", "content": "frozen Q16 snapshot"}]
    assert window.explanation.toPlainText() == rule_text
    assert not window.ollama_generate_button.isEnabled()
    assert window.ollama_cancel_button.isEnabled()


def test_live_refresh_returns_to_first_candidate_without_reordering_candidates(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
) -> None:
    window, client, _repository = ui
    payload = _payload()
    window._display_analysis_payload(window.tree.current_id, payload)
    window._candidate_selected(1, 0)
    window._generate_ollama_explanation()
    old_id = window._ollama_request_id
    refreshed = deepcopy(payload)
    refreshed_infos = cast(list[dict[str, object]], refreshed["moveInfos"])
    refreshed_infos[0]["visits"] = 700
    window._display_analysis_payload(window.tree.current_id, refreshed)
    assert window._candidate_explanation is not None
    assert window._candidate_explanation.move == "D4"
    assert not window.candidate_table.selectionModel().selectedRows()
    assert old_id in client.cancelled

    updated = deepcopy(payload)
    infos = cast(list[dict[str, object]], updated["moveInfos"])
    infos[0]["order"] = 1
    infos[1]["order"] = 0
    window._display_analysis_payload(window.tree.current_id, updated)
    assert window._candidate_explanation is not None
    assert window._candidate_explanation.move == "Q16"
    assert window._candidate_explanation.rank == 1
    assert window.candidate_table.item(0, 0).text() == "Q16"
    assert window.candidate_table.item(1, 0).text() == "D4"
    assert not window.candidate_table.selectionModel().selectedRows()
    assert len(client.generations) == 1
    client.explanation_ready.emit(old_id, "stale ranking")
    assert not window.ollama_explanation.toPlainText()


def test_identical_payload_does_not_cancel_and_result_is_plain_text(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
) -> None:
    window, client, _repository = ui
    payload = _payload()
    window._display_analysis_payload(window.tree.current_id, payload)
    window._generate_ollama_explanation()
    request_id = window._ollama_request_id
    window._display_analysis_payload(window.tree.current_id, deepcopy(payload))
    assert window._ollama_request_id == request_id
    assert not client.cancelled
    client.explanation_ready.emit(request_id, "<b>Literal AI explanation</b>")
    assert window.ollama_explanation.toPlainText() == "<b>Literal AI explanation</b>"
    assert "不使用外部语言模型" not in window.ollama_explanation.toPlainText()
    assert window.ollama_generate_button.isEnabled()
    assert not window.ollama_cancel_button.isEnabled()


def test_live_visits_do_not_reset_rule_explanation_scroll(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
    qtbot: QtBot,
) -> None:
    window, _client, _repository = ui
    window.explanation.setFixedHeight(60)
    window.show()
    qtbot.wait(20)
    payload = _payload()
    window._display_analysis_payload(window.tree.current_id, payload)
    scroll_bar = window.explanation.verticalScrollBar()
    assert scroll_bar.maximum() > 0
    scroll_bar.setValue(scroll_bar.maximum())
    reading_position = scroll_bar.value()
    rendered = window.explanation.toPlainText()
    spy = QSignalSpy(window.explanation.textChanged)

    more_visits = deepcopy(payload)
    more_visits["rootInfo"]["visits"] = 900
    more_visits["moveInfos"][0]["visits"] = 700
    window._display_analysis_payload(window.tree.current_id, more_visits)
    assert window.explanation.toPlainText() == rendered
    assert spy.count() == 0
    assert scroll_bar.value() == reading_position

    new_variation = deepcopy(more_visits)
    new_variation["moveInfos"][0]["pv"] = ["D4", "Q16", "D16", "Q4"]
    window._display_analysis_payload(window.tree.current_id, new_variation)
    assert spy.count() == 1
    assert scroll_bar.value() == min(reading_position, scroll_bar.maximum())

    window._candidate_selected(1, 0)
    assert scroll_bar.value() == 0


def test_switching_away_and_back_to_candidate_rejects_old_response(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
) -> None:
    window, client, _repository = ui
    window._display_analysis_payload(window.tree.current_id, _payload())
    window._generate_ollama_explanation()
    old_id = window._ollama_request_id
    window._candidate_selected(1, 0)
    window._candidate_selected(0, 0)
    window._generate_ollama_explanation()
    current_id = window._ollama_request_id
    client.explanation_ready.emit(old_id, "old D4")
    client.explanation_partial.emit(old_id, "old partial D4")
    assert not window.ollama_explanation.toPlainText()
    client.explanation_ready.emit(current_id, "current D4")
    assert window.ollama_explanation.toPlainText() == "current D4"


@pytest.mark.parametrize("action", ["refresh", "clear", "ownership", "difficulty", "cancel"])
def test_invalidating_actions_cancel_and_ignore_late_signals(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
    action: str,
) -> None:
    window, client, _repository = ui
    window._display_analysis_payload(window.tree.current_id, _payload())
    window._generate_ollama_explanation()
    old_id = window._ollama_request_id
    if action == "refresh":
        window._refresh()
    elif action == "clear":
        window._clear_analysis_display()
    elif action == "ownership":
        window._analysis_option_changed(False)
    elif action == "difficulty":
        window._difficulty_changed(next(iter(PRESETS)))
    else:
        window._cancel_ollama_explanation()
    status = window.ollama_status.text()
    assert old_id in client.cancelled
    client.explanation_ready.emit(old_id, "late completion")
    client.request_failed.emit(old_id, "late failure")
    assert not window.ollama_explanation.toPlainText()
    assert window.ollama_status.text() == status


def test_play_undo_same_node_and_switch_game_reject_old_results(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
) -> None:
    window, client, repository = ui
    initial_node = window.tree.current_id
    window._display_analysis_payload(initial_node, _payload())
    window._generate_ollama_explanation()
    first_id = window._ollama_request_id
    window._play_point(3, 3)
    window._undo()
    assert window.tree.current_id == initial_node
    client.explanation_ready.emit(first_id, "old root")
    assert not window.ollama_explanation.toPlainText()
    window._display_analysis_payload(initial_node, _payload())
    window._generate_ollama_explanation()
    second_id = window._ollama_request_id
    new_tree = GameTree()
    new_record = repository.create_game(new_tree)
    window._apply_loaded_game(new_record, new_tree, review_mode=False)
    client.explanation_ready.emit(second_id, "old game")
    assert not window.ollama_explanation.toPlainText()
    assert not window.ollama_generate_button.isEnabled()


def test_empty_candidate_list_clears_both_explanations(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
) -> None:
    window, client, _repository = ui
    window._display_analysis_payload(window.tree.current_id, _payload())
    window._generate_ollama_explanation()
    old_id = window._ollama_request_id
    window._display_analysis_payload(
        window.tree.current_id, {"rootInfo": {}, "moveInfos": []}
    )
    client.explanation_ready.emit(old_id, "stale")
    assert not window.explanation.toPlainText()
    assert not window.ollama_explanation.toPlainText()
    assert not window.ollama_generate_button.isEnabled()


def test_incomplete_analysis_keeps_previous_candidates_but_cancels_llm(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
) -> None:
    window, client, _repository = ui
    window._display_analysis_payload(window.tree.current_id, _payload())
    previous_rules = window.explanation.toPlainText()
    window._generate_ollama_explanation()
    old_id = window._ollama_request_id
    window._display_analysis_payload(window.tree.current_id, {})
    assert window.candidate_table.item(0, 0).text() == "D4"
    assert window.explanation.toPlainText() == previous_rules
    assert old_id in client.cancelled
    client.explanation_ready.emit(old_id, "stale")
    assert not window.ollama_explanation.toPlainText()


def test_failure_preserves_rules_and_does_not_change_model(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
) -> None:
    window, client, _repository = ui
    window._display_analysis_payload(window.tree.current_id, _payload())
    rules = window.explanation.toPlainText()
    model = window.ollama_settings.model
    window._generate_ollama_explanation()
    client.explanation_partial.emit(window._ollama_request_id, "incomplete explanation")
    client.request_failed.emit(window._ollama_request_id, "本机 Ollama 请求超时。")
    assert window.explanation.toPlainText() == rules
    assert window.ollama_settings.model == model
    assert window.ollama_status.text() == (
        "生成失败：本机 Ollama 请求超时。现有 KataGo 说明仍可使用。"
    )
    assert not window.ollama_explanation.toPlainText()
    assert window.ollama_generate_button.isEnabled()


@pytest.mark.parametrize(
    ("language", "message", "expected"),
    [
        ("zh", "连接中断", "生成失败：连接中断。现有 KataGo 说明仍可使用。"),
        (
            "en",
            "Request timed out.",
            "Generation failed: Request timed out. KataGo explanations remain available.",
        ),
        (
            "en",
            "Request timed out。",
            "Generation failed: Request timed out. KataGo explanations remain available.",
        ),
    ],
)
def test_failure_status_uses_one_sentence_separator(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
    language: str,
    message: str,
    expected: str,
) -> None:
    window, _client, _repository = ui
    window.language = cast(Language, language)
    status = window._ollama_failure_status(message, "生成失败：", "Generation failed: ")
    assert status == expected


def test_fair_mode_cancels_and_cannot_generate_even_with_cached_data(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
) -> None:
    window, client, _repository = ui
    window._display_analysis_payload(window.tree.current_id, _payload())
    window._generate_ollama_explanation()
    old_id = window._ollama_request_id
    window.mode_combo.setCurrentText("公平对战")
    window._display_analysis_payload(window.tree.current_id, _payload())
    window._generate_ollama_explanation()
    client.explanation_ready.emit(old_id, "old explanation")
    assert len(client.generations) == 1
    assert not window.ollama_generate_button.isEnabled()
    assert not window.ollama_explanation.toPlainText()


def test_default_disabled_without_network_requests(qtbot: QtBot, tmp_path: Path) -> None:
    repository = GameRepository(tmp_path / "default.db")
    tree = GameTree()
    record = repository.create_game(tree)
    client = FakeOllama()
    window = MainWindow(repository, record, tree, ollama_client=cast(OllamaClient, client))
    qtbot.addWidget(window)
    window._display_analysis_payload(window.tree.current_id, _payload())
    window._generate_ollama_explanation()
    assert not window.ollama_settings.enabled
    assert not client.generations
    assert not client.model_queries


def test_close_shuts_down_before_late_result(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
) -> None:
    window, client, _repository = ui
    window._display_analysis_payload(window.tree.current_id, _payload())
    window._generate_ollama_explanation()
    old_id = window._ollama_request_id
    window.close()
    client.explanation_ready.emit(old_id, "late after close")
    assert old_id in client.cancelled
    assert client.shutdown_count == 1
    assert not window.ollama_explanation.toPlainText()
    window.close()
    assert client.shutdown_count == 1


def test_settings_cancel_keeps_persisted_values_and_accept_invalidates_request(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, client, repository = ui
    original = window.ollama_settings

    def reject_draft(dialog: OllamaSettingsDialog) -> int:
        dialog.model_combo.setCurrentText("changed-local-model")
        dialog.reject()
        return int(OllamaSettingsDialog.DialogCode.Rejected)

    monkeypatch.setattr(OllamaSettingsDialog, "exec", reject_draft)
    window._open_ollama_settings()
    assert window.ollama_settings == original
    assert repository.load_setting("ollama") == original.to_mapping()

    def accept_draft(dialog: OllamaSettingsDialog) -> int:
        dialog.model_combo.setCurrentText("changed-local-model")
        dialog.accept()
        return int(OllamaSettingsDialog.DialogCode.Accepted)

    window._display_analysis_payload(window.tree.current_id, _payload())
    window._generate_ollama_explanation()
    old_id = window._ollama_request_id
    monkeypatch.setattr(OllamaSettingsDialog, "exec", accept_draft)
    window._open_ollama_settings()
    assert window.ollama_settings.model == "changed-local-model"
    assert repository.load_setting("ollama") == window.ollama_settings.to_mapping()
    assert old_id in client.cancelled
    client.explanation_ready.emit(old_id, "old model")
    assert not window.ollama_explanation.toPlainText()


def test_model_detection_ignores_changed_endpoint_and_cancelled_dialog(qtbot: QtBot) -> None:
    client = FakeOllama()
    initial = OllamaSettings()
    dialog = OllamaSettingsDialog(initial, cast(OllamaClient, client))
    qtbot.addWidget(dialog)
    dialog._detect_models()
    first_id = dialog._list_request_id
    dialog.base_url_edit.setText("http://127.0.0.1:11435")
    client.models_ready.emit(first_id, ["stale-model"])
    assert dialog.model_combo.currentText() == initial.model
    assert first_id in client.cancelled
    dialog._detect_models()
    second_id = dialog._list_request_id
    client.models_ready.emit(second_id, ["available-local-model"])
    assert dialog.model_combo.currentText() == "available-local-model"
    assert dialog.settings() == initial
    dialog._detect_models()
    third_id = dialog._list_request_id
    dialog.reject()
    client.models_ready.emit(third_id, ["late-model"])
    assert third_id in client.cancelled
    assert dialog.model_combo.currentText() == "available-local-model"
    assert dialog.settings() == initial


def test_settings_reject_invalid_remote_endpoint_without_accepting(qtbot: QtBot) -> None:
    client = FakeOllama()
    initial = OllamaSettings()
    dialog = OllamaSettingsDialog(initial, cast(OllamaClient, client))
    qtbot.addWidget(dialog)
    dialog.base_url_edit.setText("http://example.com:11434")
    dialog.accept()
    assert dialog.result() != OllamaSettingsDialog.DialogCode.Accepted
    assert dialog.settings() == initial
    assert dialog.status_label.text()


def test_auto_generation_waits_for_final_and_deduplicates_streaming_result(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
    qtbot: QtBot,
) -> None:
    window, client, _repository = ui
    payload = _payload()
    payload["isDuringSearch"] = True
    window._display_analysis_payload(window.tree.current_id, payload)
    assert window.explanation.toPlainText()
    qtbot.wait(420)
    assert not client.generations
    payload["isDuringSearch"] = False
    window._display_analysis_payload(window.tree.current_id, payload)
    assert not client.generations
    qtbot.waitUntil(lambda: len(client.generations) == 1, timeout=1200)
    request_id = window._ollama_request_id
    client.explanation_partial.emit(request_id, "<b>partial</b>")
    assert window.ollama_explanation.toPlainText() == "<b>partial</b>"
    assert window._ollama_request_id == request_id
    window._display_analysis_payload(window.tree.current_id, deepcopy(payload))
    assert window._ollama_request_id == request_id
    client.explanation_ready.emit(request_id, "completed")
    window._display_analysis_payload(window.tree.current_id, deepcopy(payload))
    qtbot.wait(420)
    assert len(client.generations) == 1
    assert window.ollama_explanation.toPlainText() == "completed"


def test_auto_generation_debounces_candidate_changes(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, client, _repository = ui
    monkeypatch.setattr(
        "recurgo.ui.main_window.build_ollama_messages",
        lambda _state, explanation, **_kwargs: [
            {"role": "user", "content": explanation.move}
        ],
    )
    payload = _payload()
    payload.pop("isDuringSearch")
    window._display_analysis_payload(window.tree.current_id, payload)
    qtbot.wait(200)
    window._candidate_selected(1, 0)
    qtbot.wait(200)
    assert not client.generations
    qtbot.waitUntil(lambda: len(client.generations) == 1, timeout=1200)
    assert client.generations[0][2] == [{"role": "user", "content": "Q16"}]


def test_cancel_pending_auto_suppresses_same_snapshot_but_allows_manual_retry(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
    qtbot: QtBot,
) -> None:
    window, client, _repository = ui
    payload = _payload()
    window._display_analysis_payload(window.tree.current_id, payload)
    assert window.ollama_cancel_button.isEnabled()
    window._cancel_ollama_explanation()
    status = window.ollama_status.text()
    window._display_analysis_payload(window.tree.current_id, deepcopy(payload))
    qtbot.wait(420)
    assert not client.generations
    assert window.ollama_status.text() == status
    window._generate_ollama_explanation()
    assert len(client.generations) == 1


def test_mutating_payload_in_place_cancels_old_stream_and_search_does_not_restart(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
    qtbot: QtBot,
) -> None:
    window, client, _repository = ui
    payload = _payload()
    window._display_analysis_payload(window.tree.current_id, payload)
    window._generate_ollama_explanation()
    request_id = window._ollama_request_id
    payload["isDuringSearch"] = True
    cast(dict[str, object], payload["rootInfo"])["visits"] = 1200
    window._display_analysis_payload(window.tree.current_id, payload)
    client.explanation_partial.emit(request_id, "late intermediate")
    qtbot.wait(420)
    assert request_id in client.cancelled
    assert not window.ollama_explanation.toPlainText()
    assert len(client.generations) == 1


def test_full_game_analysis_defers_llm_until_cancelled(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
    qtbot: QtBot,
) -> None:
    window, client, _repository = ui
    payload = _payload()
    window._full_analysis_active = True
    window._analysis_payload_by_node[window.tree.current_id] = payload
    window._display_analysis_payload(window.tree.current_id, payload)
    window._generate_ollama_explanation()
    qtbot.wait(420)
    assert not client.generations
    assert window.explanation.toPlainText()
    assert not window._ollama_auto_attempted
    window._stop_full_game_analysis(request_realtime=False)
    qtbot.waitUntil(lambda: len(client.generations) == 1, timeout=1200)


@pytest.mark.parametrize(
    ("state", "active_request_id"),
    [("starting", None), ("loading", None), ("analyzing", None), ("ready", "pending")],
)
def test_cached_snapshot_waits_for_pending_katago_then_resumes_automatically(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
    qtbot: QtBot,
    state: str,
    active_request_id: str | None,
) -> None:
    window, client, _repository = ui
    payload = _payload()
    window._display_analysis_payload(window.tree.current_id, payload)
    assert window._ollama_timer.isActive()
    engine = BusyEngine()
    engine.state = state
    engine.active_request_id = active_request_id
    window.engine = cast(KataGoEngine, engine)
    qtbot.wait(420)
    assert not client.generations
    assert not window._ollama_auto_attempted
    assert not window.ollama_generate_button.isEnabled()
    engine.stop_analysis()
    window._analysis_finished(
        AnalysisUpdate("engine-finished", window.tree.current_id, "realtime", payload)
    )
    qtbot.waitUntil(lambda: len(client.generations) == 1, timeout=1200)


def test_new_katago_search_cancels_llm_without_changing_search_budget(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
) -> None:
    window, client, _repository = ui
    window._display_analysis_payload(window.tree.current_id, _payload())
    window._generate_ollama_explanation()
    old_id = window._ollama_request_id
    engine = BusyEngine()
    window.engine = cast(KataGoEngine, engine)
    window.analysis_checkbox.setChecked(True)
    assert old_id in client.cancelled
    assert engine.queries[0]["max_visits"] == 800
    assert engine.queries[0]["purpose"] == "realtime"
    assert engine.active_request_id == "engine-next"


def test_same_completed_snapshot_after_search_restores_controls_without_repeating_llm(
    ui: tuple[MainWindow, FakeOllama, GameRepository],
) -> None:
    window, client, _repository = ui
    payload = _payload()
    window._display_analysis_payload(window.tree.current_id, payload)
    window._generate_ollama_explanation()
    client.explanation_ready.emit(window._ollama_request_id, "completed snapshot explanation")
    engine = BusyEngine()
    window.engine = cast(KataGoEngine, engine)
    window.analysis_checkbox.setChecked(True)
    window._display_analysis_payload(window.tree.current_id, deepcopy(payload))
    assert not window.ollama_generate_button.isEnabled()
    engine.stop_analysis()
    window._analysis_finished(
        AnalysisUpdate("engine-finished", window.tree.current_id, "realtime", payload)
    )
    assert window.ollama_generate_button.isEnabled()
    assert not window._ollama_timer.isActive()
    assert window.ollama_status.text().startswith("生成完成")
    assert window.ollama_explanation.toPlainText() == "completed snapshot explanation"
    assert len(client.generations) == 1
