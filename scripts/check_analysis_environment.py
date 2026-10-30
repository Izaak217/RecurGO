"""Run an on-demand, uncached KataGo analysis to verify this machine's setup."""

from __future__ import annotations

import json
import math
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import TypeGuard

try:
    from PySide6.QtCore import QCoreApplication, QTimer
    from PySide6.QtWidgets import QApplication

    from recurgo.app import data_directory, project_root, writable_analysis_runtime
    from recurgo.domain import GameTree
    from recurgo.domain.coordinates import gtp_to_point
    from recurgo.engine import (
        AnalysisUpdate,
        EngineFailure,
        EngineFailureKind,
        EngineRuntime,
        KataGoEngine,
    )
    from recurgo.engine.driver import (
        check_nvidia_driver,
        check_visual_cpp_runtime,
        windows_file_version,
    )
    from recurgo.engine.environment import (
        dependency_directory,
        environment_config_path,
        load_environment_paths,
        save_environment_paths,
    )
    from recurgo.i18n import Language, localize_error, normalize_language, tr
    from recurgo.ui.runtime_setup_dialog import RuntimeSetupDialog
except ModuleNotFoundError as exc:
    print(
        f"Analysis environment check failed: missing Python module {exc.name}. "
        "Install the project dependencies using the Python environment steps in "
        "docs/SOURCE_SETUP.en.md.",
        flush=True,
    )
    raise SystemExit(2) from exc


def saved_setting(database_path: Path, key: str) -> dict[str, object] | None:
    """Read an application setting without changing its database."""

    if not database_path.is_file():
        return None
    try:
        database_uri = f"{database_path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(database_uri, uri=True) as connection:
            row = connection.execute(
                "SELECT value_json FROM app_settings WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        value = json.loads(str(row[0]))
        return value if isinstance(value, dict) else None
    except (OSError, sqlite3.Error, ValueError):
        return None


def saved_runtime_paths(database_path: Path) -> dict[str, object] | None:
    return saved_setting(database_path, "runtime_paths")


def failure_message(failure: EngineFailure, *, language: Language = "en") -> str:
    """Keep proven missing files separate from possible launch-time causes."""

    details = [
        tr(
            language,
            f"分析环境检查未通过：{failure.message}",
            f"Analysis environment check failed: {localize_error(failure.message, language)}",
        )
    ]
    if failure.stderr_tail.strip():
        details.append(
            tr(
                language,
                f"KataGo 原始错误：\n{failure.stderr_tail.strip()}",
                f"Original KataGo error:\n{failure.stderr_tail.strip()}",
            )
        )
    if failure.kind in (
        EngineFailureKind.PROCESS_ERROR,
        EngineFailureKind.PROCESS_EXITED,
        EngineFailureKind.STARTUP_TIMEOUT,
    ):
        details.append(
            tr(
                language,
                "已检查的文件都已找到，但 KataGo 未能正常启动；"
                "仅凭这一结果无法确定具体缺少哪个驱动或组件。"
                "请检查 NVIDIA 驱动、CUDA/cuDNN 版本是否与安装说明匹配，"
                "并查看上面的原始错误。",
                "The checked files were found, but KataGo did not start. "
                "This result alone cannot identify a missing driver or component. "
                "Check the NVIDIA driver and CUDA/cuDNN versions against the setup guide "
                "and read the original error above.",
            )
        )
    else:
        details.append(
            tr(
                language,
                "请查看上面的错误，并按《安装指南》检查分析环境。",
                "Read the error above and check the analysis environment "
                "against the setup guide.",
            )
        )
    return "\n".join(details)


def validate_probe_result(
    payload: dict[str, object], *, human: bool, board_size: int = 19
) -> None:
    """Check the empty-board probe's usable outputs, not merely process startup."""

    def finite(value: object) -> TypeGuard[int | float]:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )

    if payload.get("isDuringSearch") is not False:
        raise ValueError("The environment probe has not finished")
    moves = payload.get("moveInfos")
    if not isinstance(moves, list) or not moves:
        raise ValueError("KataGo returned no candidate moves")
    best = [item for item in moves if isinstance(item, dict) and item.get("order") == 0]
    if len(best) != 1:
        raise ValueError("KataGo did not return exactly one order=0 candidate")
    for item in moves:
        if not isinstance(item, dict) or not isinstance(item.get("move"), str):
            raise ValueError("Invalid candidate move")
        move = item["move"]
        if not move.strip():
            raise ValueError("Empty candidate coordinate")
        gtp_to_point(move, board_size)
        winrate = item.get("winrate")
        if not finite(winrate) or not 0 <= winrate <= 1:
            raise ValueError("Invalid candidate winrate")
    root = payload.get("rootInfo")
    if not isinstance(root, dict):
        raise ValueError("Missing rootInfo")
    winrate, visits = root.get("winrate"), root.get("visits")
    if not finite(winrate) or not 0 <= winrate <= 1 or not finite(visits) or visits <= 0:
        raise ValueError("Invalid root winrate/visits")
    if not finite(root.get("scoreLead")):
        raise ValueError("Invalid root scoreLead")
    field = "humanPolicy" if human else "policy"
    policy = payload.get(field)
    if not isinstance(policy, list) or len(policy) != board_size * board_size + 1:
        raise ValueError(f"Missing or invalid {field} dimensions")
    # Every point and pass is legal on this empty-board fixture.
    if any(not finite(value) or not 0 <= value <= 1 for value in policy):
        raise ValueError(f"Invalid {field} probabilities")
    if not math.isclose(sum(policy), 1.0, abs_tol=0.02):
        raise ValueError(f"Invalid {field} probability sum")
    if not human:
        ownership = payload.get("ownership")
        if not isinstance(ownership, list) or len(ownership) != board_size * board_size:
            raise ValueError("Missing or invalid ownership dimensions")
        if any(not finite(value) or not -1 <= value <= 1 for value in ownership):
            raise ValueError("Invalid ownership values")


def validate_model_metadata(payload: dict[str, object], runtime: EngineRuntime) -> None:
    """Require the live process to report both intended model roles and files."""

    models = payload.get("models")
    if not isinstance(models, list) or len(models) != 2:
        raise ValueError("KataGo did not report both main and Human SL models")
    for expected, human in ((runtime.model, False), (runtime.human_model, True)):
        matches = [
            model
            for model in models
            if isinstance(model, dict)
            and Path(str(model.get("name", "")).replace("\\", "/")).name == expected.name
            and model.get("usesHumanSLProfile") is human
        ]
        if len(matches) != 1:
            raise ValueError(f"Loaded model differs from runtime manifest: {expected.name}")


def main() -> int:
    root = project_root()
    data_root = data_directory()
    dependencies_root = dependency_directory(
        root, data_root=data_root if getattr(sys, "frozen", False) else None
    )
    preference = saved_setting(data_root / "recurgo.db", "appearance_audio") or {}
    language = normalize_language(preference.get("language"))
    config_path = environment_config_path(data_root)
    configure = "--configure" in sys.argv[1:]
    application: QCoreApplication
    if configure:
        application = QApplication([sys.argv[0]])
    try:
        overrides = load_environment_paths(config_path)
    except ValueError as exc:
        if not configure:
            print(
                tr(
                    language,
                    f"分析环境检查未通过：{exc}",
                    f"Analysis environment check failed: {localize_error(str(exc), language)}",
                ),
                flush=True,
            )
            print(
                tr(
                    language,
                    "请双击 check_analysis_environment.cmd 重新填写环境路径。",
                    "Run check_analysis_environment.cmd again to enter the environment paths.",
                ),
                flush=True,
            )
            return 2
        print(
            tr(
                language,
                f"原环境配置无效：{exc}；请重新填写。",
                "Existing environment configuration is invalid: "
                f"{localize_error(str(exc), language)}. Enter the paths again.",
            ),
            flush=True,
        )
        overrides = {}
    if configure:
        if not config_path.is_file():
            previous = saved_runtime_paths(data_root / "recurgo.db")
            if previous:
                overrides = {
                    key: str(previous.get(key) or "") for key in ("cudaBin", "cudnnBin")
                }
        dialog = RuntimeSetupDialog(
            overrides,
            project_root=root,
            dependencies_root=dependencies_root,
            check_system_msvc=bool(getattr(sys, "frozen", False)),
            language=language,
        )
        if dialog.exec() != RuntimeSetupDialog.DialogCode.Accepted:
            print(
                tr(
                    language,
                    "已取消环境检测；未修改环境配置。",
                    "Environment check cancelled; configuration unchanged.",
                ),
                flush=True,
            )
            return 1
        overrides = dialog.paths()
        try:
            save_environment_paths(config_path, overrides)
        except OSError as exc:
            print(
                tr(
                    language,
                    f"环境路径保存失败：{exc}",
                    f"Could not save environment paths: {exc}",
                ),
                flush=True,
            )
            return 2
        print(
            tr(
                language,
                f"环境路径已保存在 {config_path}。重启主程序后生效。",
                f"Environment paths saved to {config_path}. "
                "Restart the main application to apply them.",
            ),
            flush=True,
        )
    driver_ready, driver_message = check_nvidia_driver(language=language)
    print(driver_message, flush=True)
    if not driver_ready:
        return 2
    if getattr(sys, "frozen", False):
        msvc_ready, msvc_message = check_visual_cpp_runtime(language=language)
        print(msvc_message, flush=True)
        if not msvc_ready:
            print(
                "https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist",
                flush=True,
            )
            return 2
    try:
        runtime = EngineRuntime.load(
            root,
            path_overrides=overrides,
            local_dependencies_root=dependencies_root,
        )
        # Also respect RECURGO_DATA_DIR for isolated source-mode checks.
        runtime = writable_analysis_runtime(runtime, data_root)
        print(
            tr(
                language,
                "正在核验引擎及两个模型的 SHA-256 和实际引擎版本…",
                "Verifying engine/model SHA-256 and the actual executable version…",
            ),
            flush=True,
        )
        print(runtime.verify_identity(), flush=True)
        for label, path, digest in (
            ("Engine", runtime.engine, runtime.engine_sha256),
            ("Main model", runtime.model, runtime.model_sha256),
            ("Human SL", runtime.human_model, runtime.human_model_sha256),
        ):
            print(f"{label}: {path}\nSHA-256: {digest}", flush=True)
        for directory, libraries in (
            (runtime.cuda_bin, runtime.required_cuda_libraries),
            (runtime.cudnn_bin, ("cudnn64_9.dll",)),
        ):
            for name in libraries:
                path = directory / name
                print(
                    f"Selected dependency: {path}; file version: "
                    f"{windows_file_version(path) or 'unknown'}",
                    flush=True,
                )
    except (OSError, KeyError, ValueError, subprocess.SubprocessError) as exc:
        print(
            tr(
                language,
                f"分析环境检查未通过：{exc}",
                f"Analysis environment check failed: {localize_error(str(exc), language)}",
            ),
            flush=True,
        )
        print(
            tr(
                language,
                "请重新运行独立检测工具核对路径，并按说明书安装缺少的组件。",
                "Run the checker again to verify paths and install missing components "
                "using the setup guide.",
            )
        )
        return 2

    if not configure:
        application = QCoreApplication(sys.argv)
    engine = KataGoEngine(runtime)
    tree = GameTree()
    result = 3
    completed = False

    def finish(code: int, message: str) -> None:
        nonlocal completed, result
        if completed:
            return
        completed = True
        result = code
        print(message, flush=True)
        engine.shutdown()
        application.quit()

    metadata_actions: set[str] = set()

    def on_metadata(payload: dict[str, object]) -> None:
        if completed:
            return
        action = str(payload.get("action", ""))
        try:
            if action == "query_version":
                if payload.get("version") != runtime.engine_version:
                    raise ValueError("Live KataGo version differs from runtime manifest")
            elif action == "query_models":
                validate_model_metadata(payload, runtime)
            else:
                raise ValueError(f"Unexpected metadata action: {action}")
        except ValueError as exc:
            finish(3, f"Analysis environment check failed: {exc}\n{engine.stderr_tail}")
            return
        print(json.dumps(payload, ensure_ascii=False), flush=True)
        metadata_actions.add(action)
        if metadata_actions == {"query_version", "query_models"}:
            engine.analyze(
                tree=tree,
                node_id=tree.root_id,
                rules="chinese",
                komi=7.5,
                max_visits=20,
                human_profile="rank_1d",
                include_ownership=False,
                purpose="environment_human_check",
            )

    def on_result(update: AnalysisUpdate) -> None:
        if completed or update.purpose not in {"environment_check", "environment_human_check"}:
            return
        human = update.purpose == "environment_human_check"
        try:
            validate_probe_result(update.payload, human=human)
        except ValueError as exc:
            finish(3, f"Analysis environment check failed: {exc}\n{engine.stderr_tail}")
            return
        if not human:
            print(
                tr(
                    language,
                    "主分析探针通过；正在核对实际加载的模型并检测 Human SL…",
                    "Main-analysis probe passed; checking loaded models and Human SL…",
                ),
                flush=True,
            )
            engine.query_metadata()
            return
        finish(
            0,
            tr(
                language,
                "分析环境检查通过：引擎与模型身份、主分析/ownership、"
                "Human SL humanPolicy 均通过。"
                "这是运行检查，不代表完整功能或棋力验收；重启主程序后再进行人工测试。",
                "Analysis environment check passed: engine/model identity, "
                "main analysis/ownership, "
                "and Human SL humanPolicy verified. This is an operational check, not full "
                "feature or playing-strength acceptance. Restart the app for manual testing.",
            ),
        )

    def on_failure(failure: EngineFailure) -> None:
        finish(3, failure_message(failure, language=language))

    status_en = {
        "KataGo：正在加载模型…": "KataGo: loading models…",
        "KataGo：分析已取消": "KataGo: analysis cancelled",
        "KataGo：正在重新启动…": "KataGo: restarting…",
        "KataGo：正在分析当前局面": "KataGo: analyzing current position",
        "KataGo：分析完成": "KataGo: analysis complete",
        "KataGo：已就绪": "KataGo: ready",
        "KataGo：进程已启动，正在加载模型…": "KataGo: process started; loading models…",
        "KataGo：已停止": "KataGo: stopped",
        "KataGo：启动超时": "KataGo: startup timed out",
        "KataGo：分析长时间无响应": "KataGo: analysis stalled",
    }
    engine.status_changed.connect(
        lambda message: print(
            status_en.get(message, message) if language == "en" else message, flush=True
        )
    )
    engine.analysis_finished.connect(on_result)
    engine.metadata_received.connect(on_metadata)
    engine.failure_reported.connect(on_failure)
    QTimer.singleShot(
        150_000,
        lambda: finish(
            4,
            tr(
                language,
                "分析环境检查超时：请查看 KataGo 错误信息与分析环境设置。",
                "Analysis environment check timed out. "
                "Check the KataGo error and environment settings.",
            ),
        ),
    )
    print(
        tr(
            language,
            "正在启动 KataGo，依次检测主分析和 Human SL；结果不会写入棋谱或分析缓存。",
            "Starting KataGo for main-analysis and Human SL probes; "
            "results will not be saved to games or analysis caches.",
        ),
        flush=True,
    )
    engine.analyze(
        tree=tree,
        node_id=tree.root_id,
        rules="chinese",
        komi=7.5,
        max_visits=20,
        human_profile=None,
        include_ownership=True,
        purpose="environment_check",
    )
    application.exec()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
