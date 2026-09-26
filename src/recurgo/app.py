"""Desktop application entry point."""

from __future__ import annotations

import os
import re
import sys
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from platformdirs import user_data_path
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from recurgo.domain import GameTree
from recurgo.engine import EngineRuntime, KataGoEngine
from recurgo.engine.environment import (
    dependency_directory,
    environment_config_path,
    load_environment_paths,
)
from recurgo.storage import GameRepository
from recurgo.ui import MainWindow


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def data_directory() -> Path:
    override = os.environ.get("RECURGO_DATA_DIR")
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        return user_data_path("RecurGO", appauthor=False)
    return project_root() / "data"


def writable_analysis_runtime(runtime: EngineRuntime, data_root: Path) -> EngineRuntime:
    """Place KataGo logs in user data when the application directory is read-only."""

    original = runtime.analysis_config.read_text(encoding="utf-8")
    log_dir = data_root / "logs" / "katago"
    log_dir.mkdir(parents=True, exist_ok=True)
    config, count = re.subn(
        r"(?m)^logDir\s*=.*$",
        f"logDir = {log_dir.as_posix()}",
        original,
        count=1,
    )
    if count != 1:
        raise ValueError("KataGo analysis.cfg 缺少 logDir 设置。")
    config_dir = data_root / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256(config.encode("utf-8")).hexdigest()[:16]
    path = config_dir / f"analysis-{digest}.cfg"
    if not path.exists():
        path.write_text(config, encoding="utf-8")
    return replace(runtime, analysis_config=path)


def build_window() -> MainWindow:
    data_root = data_directory()
    repository = GameRepository(data_root / "recurgo.db")
    root = project_root()
    dependencies_root = dependency_directory(
        root, data_root=data_root if getattr(sys, "frozen", False) else None
    )
    latest = repository.latest_game()
    if latest is None:
        tree = GameTree()
        record = repository.create_game(tree)
    else:
        record, tree = latest
    engine_error: str | None = None
    try:
        runtime = EngineRuntime.load(
            root,
            path_overrides=load_environment_paths(environment_config_path(data_root)),
            local_dependencies_root=dependencies_root,
            validate=False,
        )
        if getattr(sys, "frozen", False):
            runtime = writable_analysis_runtime(runtime, data_root)
        engine = KataGoEngine(runtime)
    except (OSError, KeyError, ValueError) as exc:
        engine = None
        engine_error = str(exc)
    return MainWindow(
        repository,
        record,
        tree,
        engine,
        engine_unavailable_reason=engine_error,
    )


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("RecurGO")
    application.setOrganizationName("RecurGO")
    application.setStyle("Fusion")
    application.setFont(QFont("Microsoft YaHei UI", 10))
    window = build_window()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
