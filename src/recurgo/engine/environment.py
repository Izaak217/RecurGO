"""Machine-local CUDA/cuDNN paths shared by the standalone checker and app."""

from __future__ import annotations

import json
from pathlib import Path


def environment_config_path(data_root: Path) -> Path:
    return data_root / "analysis_environment.local.json"


def dependency_directory(project_root: Path, *, data_root: Path | None = None) -> Path:
    """Use a writable user directory in installed mode and preserve the source layout."""

    if data_root is not None:
        return data_root / "cuda_deps"
    return project_root / "runtime" / "cuda_deps"


def load_environment_paths(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"环境配置文件无法读取：{path}（{exc}）") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"环境配置文件格式不正确：{path}")
    paths: dict[str, str] = {}
    for key in ("cudaBin", "cudnnBin"):
        value = payload.get(key, "")
        if not isinstance(value, str):
            raise ValueError(f"环境配置文件的 {key} 必须是路径文字：{path}")
        paths[key] = value.strip()
    return paths


def save_environment_paths(path: Path, paths: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: paths.get(key, "").strip() for key in ("cudaBin", "cudnnBin")}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
