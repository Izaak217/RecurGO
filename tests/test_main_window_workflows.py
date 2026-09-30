from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pytest import MonkeyPatch
from pytestqt.qtbot import QtBot

import recurgo.ui.main_window as main_window_module
from recurgo.domain import Color, GameTree, Point
from recurgo.engine import AnalysisUpdate, EngineFailure, EngineFailureKind
from recurgo.storage import GameRepository
from recurgo.ui import MainWindow
from recurgo.ui.image_import_dialog import ImagePositionOptions
from recurgo.ui.new_game_dialog import NewGameDialog, NewGameOptions
from recurgo.ui.scoring_dialog import ScoringDialog


def test_scoring_uses_current_live_map_without_engine_query_and_saves_manual_edits(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    window, repository = _window(tmp_path, qtbot)
    engine = FakeEngine()
    window.engine = engine
    current_id = window.tree.current_id
    window._ownership_by_node[current_id] = [0.12] * 180 + [-0.12] * 180 + [0.0]
    window._active_realtime_request_id = "before-review"

    def review(dialog: ScoringDialog) -> int:
        assert dialog.ownership == (1,) * 180 + (-1,) * 180 + (2,)
        window._request_analysis()
        window._request_ai_move()
        late = AnalysisUpdate(
            "before-review", current_id, "realtime", {"ownership": [-1.0] * 361}
        )
        window._analysis_update(late)
        window._analysis_finished(late)
        assert not engine.queries
        assert dialog.ownership[0] == 1
        dialog.brush_combo.setCurrentIndex(3)
        dialog._edit_point(18, 18)
        dialog._confirm()
        dialog._stay()
        return 1

    monkeypatch.setattr(ScoringDialog, "exec", review)
    window._open_scoring()
    saved = repository.load_scoring(window.record.id)
    assert saved == (current_id, (1,) * 180 + (-1,) * 180 + (0,), frozenset())
    assert window.record.result == "W+3.75"
    assert "before-review" in window._ignored_analysis_requests
    assert window._scoring_dialog is None

    def reopen(dialog: ScoringDialog) -> int:
        assert dialog.ownership[-1] == 0
        assert dialog.confirmed_score is not None
        assert not dialog.brush_combo.isEnabled()
        dialog.show_dead_checkbox.setChecked(True)
        dialog._stay()
        return 1

    monkeypatch.setattr(ScoringDialog, "exec", reopen)
    window._open_scoring()
    assert not engine.queries


def test_cancel_scoring_leaves_game_and_cache_unchanged_and_reopens_cleanly(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    window, repository = _window(tmp_path, qtbot)
    current_id = window.tree.current_id
    window._ownership_by_node[current_id] = [0.3] * 361

    def cancel(dialog: ScoringDialog) -> int:
        assert dialog.ownership == (1,) * 361
        dialog.brush_combo.setCurrentIndex(2)
        dialog._edit_point(0, 0)
        dialog.reject()
        return 0

    monkeypatch.setattr(ScoringDialog, "exec", cancel)
    for _ in range(2):
        window._open_scoring()
        assert window.record.status == "in_progress"
        assert repository.load_scoring(window.record.id) is None
        assert window._ownership_by_node[current_id] == [0.3] * 361


def test_scoring_never_borrows_ownership_from_a_different_node(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    window, repository = _window(tmp_path, qtbot)
    window._ownership_by_node[window.tree.current_id] = [1.0] * 361
    node, _ = window.tree.play(Point(3, 3))
    repository.save_node(window.record.id, node)

    def check(dialog: ScoringDialog) -> int:
        assert dialog.ownership == (2,) * 361
        assert not dialog.confirm_button.isEnabled()
        dialog.reject()
        return 0

    monkeypatch.setattr(ScoringDialog, "exec", check)
    window._open_scoring()


def test_confirmed_review_is_discarded_if_position_changes_during_modal(
    qtbot: QtBot, tmp_path: Path, monkeypatch: MonkeyPatch,
) -> None:
    window, repository = _window(tmp_path, qtbot)
    window._ownership_by_node[window.tree.current_id] = [1.0] * 361

    def change_position(dialog: ScoringDialog) -> int:
        dialog._confirm()
        node, _ = window.tree.play(Point(3, 3))
        repository.save_node(window.record.id, node)
        dialog._stay()
        return 1

    monkeypatch.setattr(ScoringDialog, "exec", change_position)
    window._open_scoring()
    assert window.record.status == "in_progress"
    assert repository.load_scoring(window.record.id) is None


class FakeAudio:
    def set_muted(self, _muted: bool) -> None:
        return

    def play_move(self, *, captured: bool) -> None:
        del captured


class FakeEngine:
    def __init__(self) -> None:
        self.queries: list[dict[str, object]] = []
        self.stop_count = 0
        self.cancel_count = 0
        self.retry_count = 0
        self.restart_count = 0
        self.runtime = SimpleNamespace(
            engine_version="test",
            model_sha256="test-model",
        )

    def analyze(self, **kwargs: object) -> str:
        self.queries.append(kwargs)
        return f"request-{len(self.queries)}"

    def stop_analysis(self) -> None:
        self.stop_count += 1

    def cancel_analysis(self) -> bool:
        self.cancel_count += 1
        return True

    def retry_last_request(self) -> str | None:
        self.retry_count += 1
        return "retry-request"

    def restart(self) -> None:
        self.restart_count += 1

    def shutdown(self) -> None:
        return


def _window(tmp_path: Path, qtbot: QtBot) -> tuple[MainWindow, GameRepository]:
    repository = GameRepository(tmp_path / "workflow.db")
    repository.save_setting("appearance_audio", {"language": "zh"})
    tree = GameTree()
    record = repository.create_game(tree)
    window = MainWindow(repository, record, tree, audio_feedback=FakeAudio())
    qtbot.addWidget(window)
    return window, repository


def _fake_library_type(selected_game_id: str) -> type[object]:
    dialog_code = main_window_module.GameLibraryDialog.DialogCode

    class FakeLibraryDialog:
        DialogCode = dialog_code

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.metadata_updates: dict[str, tuple[str, str, str]] = {}
            self.selected_game_id = selected_game_id

        def exec(self) -> object:
            return self.DialogCode.Accepted

    return FakeLibraryDialog


def test_new_game_entry_uses_integrated_dialog_and_persists_all_options(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    window, repository = _window(tmp_path, qtbot)
    options = NewGameOptions(
        name="训练棋局",
        black_player="黑方棋手",
        white_player="白方棋手",
        mode="assisted",
        human_color="white",
        difficulty="高级",
    )
    monkeypatch.setattr(
        NewGameDialog,
        "exec",
        lambda _dialog: NewGameDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(NewGameDialog, "options", lambda _dialog: options)

    window._new_game()

    loaded, _tree = repository.load_game(window.record.id)
    assert loaded.name == "训练棋局"
    assert loaded.black_player == "黑方棋手"
    assert loaded.white_player == "白方棋手"
    assert loaded.mode == "assisted"
    assert loaded.human_color == "white"
    assert loaded.difficulty == "高级"
    assert window.difficulty_combo.currentText() == "高级"


def test_image_import_creates_a_persisted_static_position(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    window, repository = _window(tmp_path, qtbot)
    original_game_id = window.record.id
    dialog_code = main_window_module.ImageImportDialog.DialogCode

    class FakeImageImportDialog:
        DialogCode = dialog_code

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return

        def exec(self) -> object:
            return self.DialogCode.Accepted

        def options(self) -> ImagePositionOptions:
            return ImagePositionOptions(
                19,
                {Point(3, 3): Color.BLACK, Point(15, 15): Color.WHITE},
                Color.WHITE,
            )

    monkeypatch.setattr(main_window_module, "ImageImportDialog", FakeImageImportDialog)

    window._import_image_position()

    assert window.record.id != original_game_id
    assert window.record.mode == "manual"
    assert window.tree.root.state.to_play is Color.WHITE
    assert window.tree.root.state.stone_at(Point(3, 3)) is Color.BLACK
    assert window.tree.root.state.stone_at(Point(15, 15)) is Color.WHITE

    loaded, loaded_tree = repository.load_game(window.record.id)
    assert loaded.board_size == 19
    assert loaded_tree.root.state.to_play is Color.WHITE
    assert repository.load_game(original_game_id)[0].id == original_game_id


def test_difficulty_change_is_persisted_immediately(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    window, repository = _window(tmp_path, qtbot)

    window.difficulty_combo.setCurrentText("顶级")

    loaded, _tree = repository.load_game(window.record.id)
    assert window.record.difficulty == "顶级"
    assert loaded.difficulty == "顶级"


def test_unfinished_battle_can_continue_and_restores_saved_settings(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    window, repository = _window(tmp_path, qtbot)
    target_tree = GameTree()
    target = repository.create_game(
        target_tree,
        name="待续棋局",
        mode="assisted",
        human_color="white",
        difficulty="顶级",
    )
    engine = FakeEngine()
    window.engine = engine  # type: ignore[assignment]
    monkeypatch.setattr(
        main_window_module,
        "GameLibraryDialog",
        _fake_library_type(target.id),
    )
    monkeypatch.setattr(
        window,
        "_choose_unfinished_game_action",
        lambda _record: "continue",
    )

    window._open_library()

    assert window.record.id == target.id
    assert not window._review_mode_active
    assert window.difficulty_combo.currentText() == "顶级"
    assert window.human_color_combo.currentText() == "我执白"
    assert engine.queries[-1]["purpose"] == "ai_move"


def test_cancelling_unfinished_battle_switch_keeps_current_game_running(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    window, repository = _window(tmp_path, qtbot)
    original_id = window.record.id
    target = repository.create_game(GameTree(), mode="assisted")
    engine = FakeEngine()
    window.engine = engine  # type: ignore[assignment]
    monkeypatch.setattr(
        main_window_module,
        "GameLibraryDialog",
        _fake_library_type(target.id),
    )
    monkeypatch.setattr(
        window,
        "_choose_unfinished_game_action",
        lambda _record: "cancel",
    )

    window._open_library()

    assert window.record.id == original_id
    assert engine.stop_count == 0


def test_sgf_menu_uses_atomic_repository_import(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    window, repository = _window(tmp_path, qtbot)
    source = tmp_path / "atomic.sgf"
    source.write_text(
        "(;GM[1]FF[4]CA[UTF-8]SZ[19]GN[原子导入];B[pd];W[dd])",
        encoding="utf-8",
    )
    calls: list[str] = []
    atomic_import = repository.import_game_tree

    def import_game_tree(*args: object, **kwargs: object) -> object:
        calls.append(str(kwargs["name"]))
        return atomic_import(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(repository, "import_game_tree", import_game_tree)
    monkeypatch.setattr(
        repository,
        "create_game",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("legacy non-atomic import path used")
        ),
    )
    monkeypatch.setattr(
        main_window_module.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(source), "Smart Game Format (*.sgf)"),
    )

    window._import_sgf()

    assert calls == ["原子导入"]
    assert window.record.name == "原子导入"
    assert window.tree.current.state.move_number == 2


def test_ownership_and_local_explanation_are_connected_to_analysis_payload(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    window, _repository = _window(tmp_path, qtbot)
    engine = FakeEngine()
    window.engine = engine  # type: ignore[assignment]
    for checkbox in (window.analysis_checkbox, window.ownership_checkbox):
        checkbox.blockSignals(True)
        checkbox.setChecked(True)
        checkbox.blockSignals(False)
    ownership = [0.0] * (19 * 19)
    ownership[0] = -1.0
    ownership[-1] = 1.0
    payload: dict[str, object] = {
        "rootInfo": {"winrate": 0.55, "scoreLead": 1.2},
        "moveInfos": [
            {
                "move": "D4",
                "order": 0,
                "winrate": 0.56,
                "scoreLead": 1.5,
                "visits": 200,
                "pv": ["D4", "Q16"],
            }
        ],
        "ownership": ownership,
    }

    window._display_analysis_payload(window.tree.current_id, payload)

    assert window.board_widget.ownership is not None
    assert window.board_widget.ownership[0] == -1.0
    assert "棋理判断" in window.explanation.toPlainText()
    assert "不使用外部语言模型" in window.explanation.toPlainText()
    assert "将在后续" not in window.explanation.toPlainText()

    window.ownership_checkbox.setChecked(False)
    assert window.board_widget.ownership is None


def test_analysis_display_uses_dynamic_recommendation_count(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    window, _repository = _window(tmp_path, qtbot)
    payload: dict[str, object] = {
        "rootInfo": {"winrate": 0.44, "scoreLead": 0.7},
        "moveInfos": [
            {
                "move": "N5",
                "order": 0,
                "winrate": 0.442,
                "scoreLead": 0.7,
                "visits": 540,
            },
            {
                "move": "P2",
                "order": 1,
                "winrate": 0.429,
                "scoreLead": 0.8,
                "visits": 340,
            },
            {
                "move": "M3",
                "order": 2,
                "winrate": 0.332,
                "scoreLead": 3.3,
                "visits": 70,
            },
        ],
    }

    window._display_analysis_payload(window.tree.current_id, payload)

    assert window.candidate_table.rowCount() == 2
    assert [str(info["move"]) for info in window._candidate_payloads] == ["N5", "P2"]
    assert len(window.board_widget._candidates) == 2


def test_engine_failure_exposes_retry_close_and_writes_diagnostics(
    qtbot: QtBot,
    tmp_path: Path,
) -> None:
    window, repository = _window(tmp_path, qtbot)
    engine = FakeEngine()
    window.engine = engine  # type: ignore[assignment]
    failure = EngineFailure(
        kind=EngineFailureKind.ANALYSIS_STALLED,
        message="分析无响应",
        recoverable=True,
        request_id="request-1",
        node_id=window.tree.current_id,
        purpose="realtime",
        stderr_tail="diagnostic-tail",
    )

    window._engine_failure(failure)

    assert not window.engine_retry_button.isHidden()
    assert not window.engine_close_analysis_button.isHidden()
    log_path = repository.database_path.parent / "katago_engine_diagnostics.log"
    assert "diagnostic-tail" in log_path.read_text(encoding="utf-8")

    window._retry_engine_analysis()
    assert engine.retry_count == 1
    assert window.engine_retry_button.isHidden()

    window._engine_failure(failure)
    window._close_failed_analysis()
    assert engine.cancel_count == 1
    assert not window.analysis_checkbox.isChecked()
    assert "棋谱仍可浏览" in window.engine_status.text()
