from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction
from pytestqt.qtbot import QtBot

from recurgo.app import writable_analysis_runtime
from recurgo.domain import GameTree
from recurgo.engine import EngineFailure, EngineFailureKind, EngineRuntime
from recurgo.engine import driver as driver_module
from recurgo.engine.environment import (
    environment_config_path,
    load_environment_paths,
    save_environment_paths,
)
from recurgo.storage import GameRepository
from recurgo.ui.main_window import MainWindow
from recurgo.ui.runtime_setup_dialog import RuntimeSetupDialog
from scripts.check_analysis_environment import failure_message, saved_runtime_paths


class SilentAudio:
    def set_muted(self, _muted: bool) -> None:
        return

    def play_move(self, *, captured: bool) -> None:
        return


class ProbeEngine(QObject):
    status_changed = Signal(str)
    failure_reported = Signal(object)
    analysis_updated = Signal(object)
    analysis_finished = Signal(object)

    def __init__(self, root: Path) -> None:
        super().__init__()
        self.runtime = SimpleNamespace(
            engine=root / "katago.exe",
            model=root / "model.bin.gz",
            human_model=root / "human.bin.gz",
            analysis_config=root / "analysis.cfg",
            cuda_bin=root / "cuda",
            cudnn_bin=root / "cudnn",
            engine_version="test",
            model_sha256="test-model",
        )
        self.queries: list[dict[str, object]] = []

    def analyze(self, **kwargs: object) -> str:
        self.queries.append(kwargs)
        return "probe-request"

    def stop_analysis(self) -> None:
        return

    def shutdown(self) -> None:
        return


def test_bundle_runtime_detects_machine_libraries_and_respects_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    for relative in (
        "engine/katago.exe",
        "models/main.bin.gz",
        "models/human.bin.gz",
        "configs/analysis.cfg",
    ):
        path = runtime_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    cuda_bin = tmp_path / "cuda" / "bin"
    cuda_bin.mkdir(parents=True)
    for name in ("cublas64_12.dll", "cudart64_12.dll"):
        (cuda_bin / name).touch()
    cudnn_bin = tmp_path / "cudnn" / "bin"
    cudnn_bin.mkdir(parents=True)
    (cudnn_bin / "cudnn64_9.dll").touch()
    (runtime_dir / "bundle.json").write_text(
        json.dumps(
            {
                "engine": "runtime/engine/katago.exe",
                "model": "runtime/models/main.bin.gz",
                "humanModel": "runtime/models/human.bin.gz",
                "analysisConfig": "runtime/configs/analysis.cfg",
                "engineVersion": "test",
                "modelSha256": "test-model",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CUDA_PATH_V12_8", str(cuda_bin.parent))
    monkeypatch.setenv("CUDNN_PATH", str(cudnn_bin.parent))
    runtime = EngineRuntime.load(tmp_path)
    assert runtime.cuda_bin == cuda_bin
    assert runtime.cudnn_bin == cudnn_bin

    supplied_root = tmp_path / "data" / "dependencies"
    supplied_cuda = supplied_root / "nvidia" / "cuda" / "bin"
    supplied_cudnn = supplied_root / "nvidia" / "cudnn" / "bin"
    supplied_cuda.mkdir(parents=True)
    supplied_cudnn.mkdir(parents=True)
    for name in ("cublas64_12.dll", "cudart64_12.dll"):
        (supplied_cuda / name).touch()
    (supplied_cudnn / "cudnn64_9.dll").touch()
    supplied = EngineRuntime.load(tmp_path, local_dependencies_root=supplied_root)
    assert supplied.cuda_bin == supplied_cuda
    assert supplied.cudnn_bin == supplied_cudnn

    partial_cuda = tmp_path / "partial-cuda"
    partial_cuda.mkdir()
    (partial_cuda / "cublas64_12.dll").touch()
    manifest_path = runtime_dir / "bundle.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["cudaBin"] = str(partial_cuda)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert EngineRuntime.load(tmp_path).cuda_bin == cuda_bin

    with pytest.raises(FileNotFoundError, match="cuDNN bin 文件夹"):
        EngineRuntime.load(tmp_path, path_overrides={"cudnnBin": str(tmp_path / "wrong")})


def test_standalone_dialog_has_explicit_auto_and_manual_modes(
    qtbot: QtBot, tmp_path: Path
) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    cuda_bin = tmp_path / "cuda"
    cudnn_bin = tmp_path / "cudnn"
    cuda_bin.mkdir()
    cudnn_bin.mkdir()
    for name in ("cublas64_12.dll", "cudart64_12.dll"):
        (cuda_bin / name).touch()
    (cudnn_bin / "cudnn64_9.dll").touch()
    (runtime_dir / "bundle.json").write_text(
        json.dumps(
            {
                "engine": "runtime/katago.exe",
                "model": "runtime/main.bin.gz",
                "humanModel": "runtime/human.bin.gz",
                "analysisConfig": "runtime/analysis.cfg",
                "cudaBin": str(cuda_bin),
                "cudnnBin": str(cudnn_bin),
                "engineVersion": "test",
                "modelSha256": "test-model",
            }
        ),
        encoding="utf-8",
    )
    dialog = RuntimeSetupDialog(None, project_root=tmp_path)
    qtbot.addWidget(dialog)
    assert dialog.auto_radio.isChecked()
    assert str(cuda_bin) in dialog.auto_status_browser.toPlainText()
    assert str(cudnn_bin) in dialog.auto_status_browser.toPlainText()
    assert not dialog.cuda_edit.isEnabled()
    dialog.manual_radio.setChecked(True)
    assert dialog.cuda_edit.isEnabled()
    dialog.cuda_edit.setText(str(cuda_bin))
    dialog.cudnn_edit.setText(str(cudnn_bin))
    assert dialog.paths() == {"cudaBin": str(cuda_bin), "cudnnBin": str(cudnn_bin)}
    dialog.auto_radio.setChecked(True)
    assert dialog.paths() == {"cudaBin": "", "cudnnBin": ""}
    dialog.accept()
    assert dialog.result() == dialog.DialogCode.Accepted


def test_runtime_validation_lists_each_missing_component(tmp_path: Path) -> None:
    cuda_bin = tmp_path / "cuda"
    cudnn_bin = tmp_path / "cudnn"
    cuda_bin.mkdir()
    cudnn_bin.mkdir()
    (cuda_bin / "cublas64_12.dll").touch()
    runtime = EngineRuntime(
        project_root=tmp_path,
        engine=tmp_path / "katago.exe",
        model=tmp_path / "main.bin.gz",
        human_model=tmp_path / "human.bin.gz",
        analysis_config=tmp_path / "analysis.cfg",
        cuda_bin=cuda_bin,
        cudnn_bin=cudnn_bin,
        engine_version="test",
        model_sha256="test-model",
    )
    with pytest.raises(FileNotFoundError) as error:
        runtime.validate()
    report = str(error.value)
    for item in (
        "KataGo 引擎",
        "KataGo 分析模型",
        "KataGo Human SL 模型",
        "KataGo 分析配置",
        "cudart64_12.dll",
        "cudnn64_9.dll",
    ):
        assert item in report
    assert "cublas64_12.dll" not in report


def test_main_program_can_load_runtime_without_running_file_preflight(
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    (runtime_dir / "bundle.json").write_text(
        json.dumps(
            {
                "engine": "runtime/engine/katago.exe",
                "model": "runtime/models/main.bin.gz",
                "humanModel": "runtime/models/human.bin.gz",
                "analysisConfig": "runtime/configs/analysis.cfg",
                "engineVersion": "test",
                "modelSha256": "test-model",
            }
        ),
        encoding="utf-8",
    )
    runtime = EngineRuntime.load(tmp_path, validate=False)
    assert runtime.engine == runtime_dir / "engine" / "katago.exe"
    with pytest.raises(FileNotFoundError, match="KataGo 引擎"):
        runtime.validate()


def test_checker_preserves_engine_error_without_guessing_missing_component() -> None:
    report = failure_message(
        EngineFailure(
            kind=EngineFailureKind.PROCESS_ERROR,
            message="KataGo进程错误：进程意外退出",
            recoverable=True,
            stderr_tail="CUDA driver version is insufficient",
        ),
        language="zh",
    )
    assert "CUDA driver version is insufficient" in report
    assert "无法确定具体缺少" in report


@pytest.mark.skipif(sys.platform != "win32", reason="Windows NVIDIA driver API")
def test_driver_check_explains_missing_system_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_driver(_path: str) -> None:
        raise OSError("missing driver")

    monkeypatch.setattr(driver_module.ctypes, "WinDLL", missing_driver)
    ready, message = driver_module.check_nvidia_driver(language="zh")
    assert not ready
    assert "nvcuda.dll" in message
    assert "NVIDIA 官网" in message


def test_startup_does_not_run_an_environment_analysis(
    qtbot: QtBot, tmp_path: Path
) -> None:
    repository = GameRepository(tmp_path / "probe.db")
    tree = GameTree()
    record = repository.create_game(tree)
    engine = ProbeEngine(tmp_path)
    window = MainWindow(
        repository,
        record,
        tree,
        engine=engine,  # type: ignore[arg-type]
        audio_feedback=SilentAudio(),
    )
    qtbot.addWidget(window)
    qtbot.wait(60)
    assert engine.queries == []
    assert repository.load_setting("runtime_health") is None
    assert repository.analysis_snapshots_for_game(record.id) == {}
    assert "分析环境" not in {action.text() for action in window.findChildren(QAction)}


def test_standalone_environment_paths_are_separate_from_game_database(
    tmp_path: Path,
) -> None:
    config_path = environment_config_path(tmp_path)
    assert load_environment_paths(config_path) == {}
    save_environment_paths(
        config_path, {"cudaBin": "C:/cuda/bin", "cudnnBin": "C:/cudnn/bin"}
    )
    assert load_environment_paths(config_path) == {
        "cudaBin": "C:/cuda/bin",
        "cudnnBin": "C:/cudnn/bin",
    }
    repository = GameRepository(tmp_path / "games.db")
    assert repository.load_setting("runtime_paths") is None


def test_standalone_checker_reads_saved_paths_without_changing_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "settings.db"
    assert saved_runtime_paths(database_path) is None
    repository = GameRepository(database_path)
    repository.save_setting(
        "runtime_paths", {"cudaBin": "C:/cuda/bin", "cudnnBin": "C:/cudnn/bin"}
    )
    assert saved_runtime_paths(database_path) == {
        "cudaBin": "C:/cuda/bin",
        "cudnnBin": "C:/cudnn/bin",
    }
    assert repository.load_setting("runtime_paths") == saved_runtime_paths(database_path)


def test_packaged_config_writes_logs_to_user_data_without_touching_source(
    tmp_path: Path,
) -> None:
    source_config = tmp_path / "runtime" / "analysis.cfg"
    source_config.parent.mkdir()
    source_config.write_text("logDir = data/logs/katago\nmaxVisits = 800\n", encoding="utf-8")
    runtime = EngineRuntime(
        project_root=tmp_path,
        engine=tmp_path / "katago.exe",
        model=tmp_path / "model.bin.gz",
        human_model=tmp_path / "human.bin.gz",
        analysis_config=source_config,
        cuda_bin=tmp_path / "cuda",
        cudnn_bin=tmp_path / "cudnn",
        engine_version="test",
        model_sha256="test-model",
    )
    prepared = writable_analysis_runtime(runtime, tmp_path / "user-data")
    assert prepared.analysis_config != source_config
    assert prepared.analysis_config.read_text(encoding="utf-8") == (
        f"logDir = {(tmp_path / 'user-data' / 'logs' / 'katago').as_posix()}\n"
        "maxVisits = 800\n"
    )
    assert source_config.read_text(encoding="utf-8") == (
        "logDir = data/logs/katago\nmaxVisits = 800\n"
    )
