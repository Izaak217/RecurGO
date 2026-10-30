"""Resolve and validate the machine-local KataGo runtime manifest."""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

CUDA_REQUIRED_LIBRARIES = (
    "cublas64_12.dll",
    "cudart64_12.dll",
    "nvrtc64_120_0.dll",
    "nvrtc-builtins64_128.dll",
)


def _cudnn_bin_layouts(bin_dir: Path) -> list[Path]:
    """Find cuDNN 9 DLL folders below a known installation root."""

    candidates = [bin_dir]
    try:
        if bin_dir.is_dir():
            candidates.extend(
                sorted(
                    {path.parent for path in bin_dir.rglob("cudnn64_9.dll") if path.is_file()}
                )
            )
    except OSError:
        pass
    return candidates


def _installed_cudnn_bins(program_files: Path) -> list[Path]:
    """Find NVIDIA's versioned cuDNN installations without a machine-wide scan."""

    install_root = program_files / "NVIDIA" / "CUDNN"
    preferred = install_root / "v9.8" / "bin"
    candidates = [preferred]
    try:
        versions = sorted(
            install_root.glob("v9.*"),
            key=lambda path: (path.name.casefold() != "v9.8", path.name.casefold()),
        )
        for version in versions:
            if not version.is_dir():
                continue
            candidates.extend(
                path for path in _cudnn_bin_layouts(version / "bin") if path != preferred
            )
    except OSError:
        pass
    return candidates


@dataclass(frozen=True, slots=True)
class EngineRuntime:
    project_root: Path
    engine: Path
    model: Path
    human_model: Path
    analysis_config: Path
    cuda_bin: Path
    cudnn_bin: Path
    engine_version: str
    model_sha256: str
    engine_sha256: str = ""
    human_model_sha256: str = ""
    backend: str = "cuda"
    required_cuda_libraries: tuple[str, ...] = CUDA_REQUIRED_LIBRARIES

    @classmethod
    def load(
        cls,
        project_root: Path,
        *,
        path_overrides: Mapping[str, object] | None = None,
        local_dependencies_root: Path | None = None,
        validate: bool = True,
    ) -> EngineRuntime:
        manifest_path = project_root / "runtime" / "runtime.local.json"
        if not manifest_path.is_file():
            manifest_path = project_root / "runtime" / "bundle.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(
                "缺少 KataGo 运行清单：runtime/runtime.local.json 或 "
                "runtime/bundle.json。请按《安装指南》或《源码启动说明》补齐 KataGo 文件。"
            )
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        libraries = payload.get("requiredCudaLibraries", list(CUDA_REQUIRED_LIBRARIES))
        if (
            not isinstance(libraries, list)
            or not libraries
            or any(not isinstance(name, str) or Path(name).name != name for name in libraries)
        ):
            raise ValueError("Invalid requiredCudaLibraries in runtime manifest")
        cuda_libraries = tuple(libraries)

        def resolve(value: str) -> Path:
            path = Path(value)
            return path if path.is_absolute() else project_root / path

        def dependency_dir(
            key: str, required_files: tuple[str, ...], candidates: list[Path]
        ) -> Path:
            override = (path_overrides or {}).get(key)
            if isinstance(override, str) and override.strip():
                return resolve(override.strip())
            configured = payload.get(key)
            if isinstance(configured, str) and configured.strip():
                candidates.insert(2, resolve(configured.strip()))
            for entry in os.environ.get("PATH", "").split(os.pathsep):
                if entry:
                    candidates.append(Path(entry))
            for candidate in candidates:
                if all((candidate / name).is_file() for name in required_files):
                    return candidate
            return candidates[0] if candidates else project_root / "runtime" / key

        program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        dependencies_root = (
            local_dependencies_root
            if local_dependencies_root is not None
            else project_root / "runtime" / "cuda_deps"
        )
        legacy_dependencies_root = project_root / "runtime" / "cuda_deps"
        cuda_root = os.environ.get("CUDA_PATH_V12_8") or os.environ.get("CUDA_PATH")
        cuda_candidates = [
            dependencies_root / "nvidia" / "cuda" / "bin",
            legacy_dependencies_root / "nvidia" / "cuda" / "bin",
        ]
        if cuda_root:
            cuda_candidates.extend((Path(cuda_root) / "bin", Path(cuda_root)))
        cuda_candidates.append(
            program_files / "NVIDIA GPU Computing Toolkit" / "CUDA" / "v12.8" / "bin"
        )
        cudnn_root = os.environ.get("CUDNN_PATH")
        cudnn_candidates = [
            dependencies_root / "nvidia" / "cudnn" / "bin",
            legacy_dependencies_root / "nvidia" / "cudnn" / "bin",
        ]
        if cudnn_root:
            configured_root = Path(cudnn_root)
            cudnn_candidates.extend(_cudnn_bin_layouts(configured_root))
        cudnn_candidates.extend(_installed_cudnn_bins(program_files))

        runtime = cls(
            project_root=project_root,
            engine=resolve(payload["engine"]),
            model=resolve(payload["model"]),
            human_model=resolve(payload["humanModel"]),
            analysis_config=resolve(payload["analysisConfig"]),
            cuda_bin=dependency_dir("cudaBin", cuda_libraries, cuda_candidates),
            cudnn_bin=dependency_dir("cudnnBin", ("cudnn64_9.dll",), cudnn_candidates),
            engine_version=str(payload["engineVersion"]),
            model_sha256=str(payload["modelSha256"]),
            engine_sha256=str(payload.get("engineSha256", "")),
            human_model_sha256=str(payload.get("humanModelSha256", "")),
            backend=str(payload.get("backend", "cuda")),
            required_cuda_libraries=cuda_libraries,
        )
        if validate:
            runtime.validate()
        return runtime

    def process_environment(self) -> dict[str, str]:
        """Use the same child-only DLL search path for identity and analysis checks."""

        environment = os.environ.copy()
        environment["PATH"] = (
            f"{self.cudnn_bin}{os.pathsep}{self.cuda_bin}{os.pathsep}"
            + environment.get("PATH", "")
        )
        return environment

    def verify_artifact_hashes(self) -> None:
        """v1.1.0.dev1: verify cache provenance without starting any process or GPU."""
        for path, expected in (
            (self.engine, self.engine_sha256),
            (self.model, self.model_sha256),
            (self.human_model, self.human_model_sha256),
        ):
            if re.fullmatch(r"[0-9a-fA-F]{64}", expected) is None:
                raise ValueError(f"Missing or invalid SHA-256 in runtime manifest: {path.name}")
            digest = sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != expected.lower():
                raise ValueError(f"Runtime SHA-256 mismatch: {path}")

    def verify_identity(self) -> str:
        """Verify release files and executable version for the standalone checker."""
        self.verify_artifact_hashes()
        completed = subprocess.run(
            [str(self.engine), "version"],
            cwd=self.project_root,
            env=self.process_environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
        output = (completed.stdout + "\n" + completed.stderr).strip()
        if completed.returncode != 0:
            raise ValueError(f"KataGo version check failed ({completed.returncode}):\n{output}")
        version = re.search(r"(?m)^KataGo v([^\s]+)\s*$", output)
        backend = re.search(r"(?mi)^Using (.+) backend\s*$", output)
        if version is None or version.group(1) != self.engine_version:
            raise ValueError(f"KataGo version differs from runtime manifest:\n{output}")
        if backend is None or backend.group(1).casefold() != self.backend.casefold():
            raise ValueError(f"KataGo backend differs from runtime manifest:\n{output}")
        return output

    def validate(self) -> None:
        issues: list[str] = []
        for label, path in (
            ("KataGo 引擎", self.engine),
            ("KataGo 分析模型", self.model),
            ("KataGo Human SL 模型", self.human_model),
            ("KataGo 分析配置", self.analysis_config),
        ):
            if not path.is_file():
                issues.append(f"{label}文件：{path}")
        for label, directory, libraries in (
            ("CUDA", self.cuda_bin, self.required_cuda_libraries),
            ("cuDNN", self.cudnn_bin, ("cudnn64_9.dll",)),
        ):
            if not directory.is_dir():
                issues.append(f"{label} bin 文件夹：{directory}")
                continue
            for library in libraries:
                path = directory / library
                if not path.is_file():
                    issues.append(f"{label} 运行库 {library}：{path}")
        if issues:
            formatted = "\n".join(f"- {issue}" for issue in issues)
            raise FileNotFoundError(
                "分析环境缺少以下项目：\n"
                f"{formatted}\n"
                "请按《安装指南》或《源码启动说明》补齐；"
                "CUDA/cuDNN 路径可在独立检测工具中指定。"
            )
