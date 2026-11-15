"""v1.2.0.dev1: report export must work without an engine and respect fair play."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

import recurgo.ui.main_window as main_window_module
from recurgo.domain import BoardState, GameTree, Point
from recurgo.storage import GameRepository
from recurgo.ui import MainWindow
from recurgo.ui.report_export_dialog import ReportExportDialog


class SilentAudio:
    def set_muted(self, _muted: bool) -> None:
        pass

    def play_move(self, *, captured: bool) -> None:
        pass


def report_window(tmp_path: Path, qtbot: QtBot, *, mode: str = "manual") -> MainWindow:
    repository = GameRepository(tmp_path / "reports.db")
    tree = GameTree(BoardState.new(9))
    record = repository.create_game(tree, name="离线复盘", mode=mode)
    root_id = tree.root_id
    node, _created = tree.play(Point(3, 3))
    repository.save_node(record.id, node)
    repository.register_analysis_source(
        "report-test-source",
        engine_version="test-engine",
        model_hash="test-model",
        config_hash="test-config",
    )
    for node_id, move, winrate in ((root_id, "D6", 0.55), (node.id, "E5", 0.53)):
        repository.save_analysis_snapshot(
            game_id=record.id,
            node_id=node_id,
            cache_key="full-game-800",
            analysis_identity="report-test-source",
            engine_version="test-engine",
            model_hash="test-model",
            parameters={"maxVisits": 800, "configSha256": "test-config"},
            result={
                "isDuringSearch": False,
                "rootInfo": {"winrate": winrate, "scoreLead": 1.5, "visits": 800},
                "moveInfos": [{
                    "move": move, "order": 0, "visits": 700,
                    "winrate": winrate, "scoreLead": 1.5, "pv": [move],
                }],
            },
        )
    window = MainWindow(repository, record, tree, engine=None, audio_feedback=SilentAudio())
    qtbot.addWidget(window)
    return window


def accept_report(monkeypatch: pytest.MonkeyPatch, destination: Path | None) -> None:
    monkeypatch.setattr(ReportExportDialog, "exec", lambda _self: 1)
    monkeypatch.setattr(
        main_window_module.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(destination) if destination else "", "HTML (*.html)"),
    )


def test_report_export_without_engine_is_read_only_and_repeatable(
    tmp_path: Path, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = report_window(tmp_path, qtbot)
    before = list(window.repository.connection.iterdump())
    current = window.tree.current_id
    for index in range(2):
        destination = tmp_path / f"离线报告-{index}.html"
        accept_report(monkeypatch, destination)
        window._export_analysis_report()
        html = destination.read_text(encoding="utf-8")
        assert "<!doctype html>" in html.lower()
        assert "report-test-source" in html
        assert window.tree.root_id in html
    assert window.engine is None
    assert window.tree.current_id == current
    assert list(window.repository.connection.iterdump()) == before


def test_report_cancel_does_not_open_destination_dialog(
    tmp_path: Path, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = report_window(tmp_path, qtbot)
    monkeypatch.setattr(ReportExportDialog, "exec", lambda _self: 0)
    monkeypatch.setattr(
        main_window_module.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: pytest.fail("Cancelled report must not ask for a file"),
    )
    before = list(window.repository.connection.iterdump())
    window._export_analysis_report()
    assert list(window.repository.connection.iterdump()) == before


def test_report_file_cancel_and_write_failure_leave_game_unchanged(
    tmp_path: Path, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = report_window(tmp_path, qtbot)
    before = list(window.repository.connection.iterdump())
    accept_report(monkeypatch, None)
    window._export_analysis_report()
    destination = tmp_path / "directory.html"
    destination.mkdir()
    errors: list[str] = []
    monkeypatch.setattr(
        main_window_module.QMessageBox, "warning",
        lambda _parent, _title, message: errors.append(message),
    )
    accept_report(monkeypatch, destination)
    window._export_analysis_report()
    assert errors
    assert destination.is_dir()
    assert list(window.repository.connection.iterdump()) == before


def test_fair_play_blocks_report_export_even_when_called_directly(
    tmp_path: Path, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = report_window(tmp_path, qtbot, mode="fair")
    assert not window.report_export_action.isEnabled()
    monkeypatch.setattr(
        main_window_module, "list_report_sources",
        lambda *_args: pytest.fail("Fair-play data must not reach the exporter"),
    )
    window._export_analysis_report()


def test_report_rechecks_fair_mode_after_native_file_dialog(
    tmp_path: Path, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = report_window(tmp_path, qtbot)
    destination = tmp_path / "must-not-export.html"
    monkeypatch.setattr(ReportExportDialog, "exec", lambda _self: 1)

    def choose(*_args: object, **_kwargs: object) -> tuple[str, str]:
        window.mode_combo.setCurrentIndex(window.mode_combo.findData("fair"))
        return str(destination), "HTML (*.html)"

    monkeypatch.setattr(main_window_module.QFileDialog, "getSaveFileName", choose)
    window._export_analysis_report()
    assert not destination.exists()


def test_report_suffix_replacement_declined_preserves_existing_file(
    tmp_path: Path, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = report_window(tmp_path, qtbot)
    selected = tmp_path / "existing.txt"
    destination = selected.with_suffix(".html")
    destination.write_text("original report", encoding="utf-8")
    before = list(window.repository.connection.iterdump())
    prompts: list[str] = []

    def decline(_parent: object, _title: str, message: str, *_args: object) -> int:
        prompts.append(message)
        return main_window_module.QMessageBox.StandardButton.No

    monkeypatch.setattr(main_window_module.QMessageBox, "question", decline)
    accept_report(monkeypatch, selected)
    window._export_analysis_report()
    assert len(prompts) == 1
    assert str(destination) in prompts[0]
    assert destination.read_text(encoding="utf-8") == "original report"
    assert not selected.exists()
    assert list(window.repository.connection.iterdump()) == before


def test_report_suffix_replacement_confirmed_reads_current_game(
    tmp_path: Path, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = report_window(tmp_path, qtbot)
    selected = tmp_path / "existing.txt"
    destination = selected.with_suffix(".html")
    destination.write_text("original report", encoding="utf-8")
    created: list[str] = []

    def confirm(*_args: object) -> int:
        # A modal dialog can process a move before the export is confirmed.
        node, _ = window.tree.play(Point(4, 4))
        window.repository.save_node(window.record.id, node)
        created.append(node.id)
        return main_window_module.QMessageBox.StandardButton.Yes

    monkeypatch.setattr(main_window_module.QMessageBox, "question", confirm)
    accept_report(monkeypatch, selected)
    window._export_analysis_report()
    html = destination.read_text(encoding="utf-8")
    assert "<!doctype html>" in html.lower()
    assert len(created) == 1
    assert created[0] in html
    assert not selected.exists()


def test_report_rechecks_fair_mode_after_suffix_overwrite_confirmation(
    tmp_path: Path, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = report_window(tmp_path, qtbot)
    selected = tmp_path / "existing.txt"
    destination = selected.with_suffix(".html")
    destination.write_text("original report", encoding="utf-8")

    def switch_mode(*_args: object) -> int:
        window.mode_combo.setCurrentIndex(window.mode_combo.findData("fair"))
        return main_window_module.QMessageBox.StandardButton.Yes

    monkeypatch.setattr(main_window_module.QMessageBox, "question", switch_mode)
    accept_report(monkeypatch, selected)
    window._export_analysis_report()
    assert destination.read_text(encoding="utf-8") == "original report"
    assert not selected.exists()


def test_empty_analysis_gives_instructions_without_starting_engine(
    tmp_path: Path, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = GameRepository(tmp_path / "empty.db")
    tree = GameTree()
    record = repository.create_game(tree)
    window = MainWindow(repository, record, tree, audio_feedback=SilentAudio())
    qtbot.addWidget(window)
    notices: list[str] = []
    monkeypatch.setattr(
        main_window_module.QMessageBox, "information",
        lambda _parent, _title, text: notices.append(text),
    )
    window._export_analysis_report()
    assert notices
    assert window.engine is None
