"""Build a local Windows installer candidate from an explicit, reviewed file list."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
APP_ICON = ROOT / "src" / "recurgo" / "assets" / "recurgo.ico"
RELEASE_CUDA_LIBRARIES = (
    "cublas64_12.dll",
    "cudart64_12.dll",
    "nvrtc64_120_0.dll",
    "nvrtc-builtins64_128.dll",
)
B28_CUDA_LIBRARIES = ("cublas64_12.dll", "cudart64_12.dll")
ENGINE_FILES = {
    "tf3": (
        "katago.exe", "libcrypto-3-x64.dll", "libssl-3-x64.dll", "z.dll",
        "zip.dll", "bz2.dll", "cacert.pem", "README.txt",
    ),
    "b28": (
        "katago.exe", "libcrypto-3-x64.dll", "libssl-3-x64.dll", "libz.dll",
        "libzip.dll", "cacert.pem", "README.txt",
    ),
}
BLOCKED_OPTIONAL_RUNTIME_NAMES = frozenset(
    {
        "qt6virtualkeyboard.dll",
        "qtvirtualkeyboardplugin.dll",
        "opencv_videoio_ffmpeg500_64.dll",
        "ffmpegmediaplugin.dll",
        "avcodec-61.dll",
        "avformat-61.dll",
        "avutil-59.dll",
        "swresample-5.dll",
        "swscale-8.dll",
        "qpdf.dll",
        "qt6pdf.dll",
    }
)


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def required_file(path: Path) -> Path:
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def copy_file(source: Path, destination: Path) -> None:
    required_file(source)
    if (
        source.is_symlink()
        or os.path.isjunction(source)
        or not source.resolve().is_relative_to(ROOT)
    ):
        raise ValueError(f"Linked release input is not allowed: {source}")
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def run(command: list[str], *, env: dict[str, str]) -> None:
    print("Running:", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def prepare_environment(release_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    windows_root = Path(env.get("SystemRoot", r"C:\Windows")).resolve()
    approved_path = (
        ROOT / ".venv" / "Scripts",
        Path(sys.base_prefix),
        Path(sys.base_prefix) / "Scripts",
        windows_root / "System32",
        windows_root,
    )
    if any(not directory.is_dir() for directory in approved_path):
        raise ValueError("An approved release-build PATH directory is missing")
    env["PATH"] = os.pathsep.join(str(directory) for directory in approved_path)
    for name in (
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONUSERBASE",
        "QT_PLUGIN_PATH",
        "QT_QPA_PLATFORM_PLUGIN_PATH",
    ):
        env.pop(name, None)
    env["PYTHONNOUSERSITE"] = "1"
    for name, relative in (
        ("TEMP", "tmp"),
        ("TMP", "tmp"),
        ("PYINSTALLER_CONFIG_DIR", "pyinstaller-config"),
    ):
        directory = release_root / relative
        directory.mkdir(parents=True, exist_ok=True)
        env[name] = str(directory)
    return env


def verify_collected_sources(toc_path: Path, *, release_root: Path) -> None:
    """Reject PyInstaller binaries/data copied from ambient developer tools."""
    analysis = ast.literal_eval(required_file(toc_path).read_text(encoding="utf-8"))
    if not isinstance(analysis, tuple) or len(analysis) <= 18:
        raise ValueError("Unexpected PyInstaller analysis format")
    approved_roots = tuple(
        path.resolve()
        for path in (
            ROOT / ".venv",
            Path(sys.base_prefix),
            ROOT / "src",
            ROOT / "scripts",
            release_root / "pyinstaller-work",
        )
    )
    for index in (15, 18):  # PyInstaller Analysis BINARY and DATA sections.
        records = analysis[index]
        if not isinstance(records, list):
            raise ValueError("Unexpected PyInstaller dependency list")
        for record in records:
            if not isinstance(record, tuple) or len(record) != 3:
                raise ValueError("Unexpected PyInstaller dependency record")
            destination, source_name, _kind = record
            if not isinstance(destination, str) or not isinstance(source_name, str):
                raise ValueError("Unexpected PyInstaller dependency path")
            destination_path = Path(destination)
            if (
                destination_path.is_absolute()
                or ".." in destination_path.parts
                or destination_path.drive
            ):
                raise ValueError(f"Unsafe frozen destination: {destination}")
            source = Path(source_name)
            if not source.is_absolute() or not source.is_file():
                raise ValueError(f"Missing or relative frozen input: {source_name}")
            resolved = source.resolve()
            if not any(resolved.is_relative_to(root) for root in approved_roots):
                raise ValueError(f"Unapproved frozen input: {destination} from {source_name}")


def freeze_entry(
    entry: Path,
    name: str,
    *,
    one_file: bool,
    console: bool,
    release_root: Path,
    env: dict[str, str],
) -> Path:
    dist_path = release_root / "frozen"
    work_path = release_root / "pyinstaller-work" / name
    spec_path = release_root / "pyinstaller-spec"
    spec_path.mkdir(parents=True, exist_ok=True)
    spec_file = spec_path / f"{name}.spec"
    # PyInstaller hooks collect optional keyboard, video, and PDF plugins.
    # RecurGO uses Qt audio output and OpenCV still-image processing only.
    analysis = (
        f"a = Analysis([{str(entry)!r}], pathex=[{str(ROOT / 'src')!r}], "
        "binaries=[], datas=[], hiddenimports=[], hookspath=[], "
        "hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False, optimize=0)\n"
        f"blocked = set({sorted(BLOCKED_OPTIONAL_RUNTIME_NAMES)!r})\n"
        "a.binaries = [item for item in a.binaries "
        "if item[0].replace('\\\\', '/').split('/')[-1].lower() not in blocked]\n"
        "a.datas = [item for item in a.datas "
        "if item[0].replace('\\\\', '/').split('/')[-1].lower() not in blocked]\n"
        "pyz = PYZ(a.pure)\n"
    )
    if one_file:
        build = (
            f"exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name={name!r}, "
            f"console={console!r}, upx=False)\n"
        )
    else:
        build = (
            f"exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name={name!r}, "
            f"console={console!r}, upx=False, contents_directory='_internal')\n"
            f"coll = COLLECT(exe, a.binaries, a.datas, name={name!r}, upx=False)\n"
        )
    spec_file.write_text(
        "# -*- mode: python ; coding: utf-8 -*-\n" + analysis + build, encoding="utf-8"
    )
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--distpath",
        str(dist_path),
        "--workpath",
        str(work_path),
        str(spec_file),
    ]
    run(command, env=env)
    verify_collected_sources(
        work_path / name / "Analysis-00.toc", release_root=release_root
    )
    output = dist_path / (f"{name}.exe" if one_file else name)
    if not output.exists():
        raise FileNotFoundError(output)
    return output


def reviewed_runtime_paths(asset_lock: dict[str, object]) -> dict[str, str]:
    """v1.1.0.dev1: resolve the explicit release lock without accepting arbitrary paths."""
    if asset_lock.get("schemaVersion") != 2:
        raise ValueError("Unsupported tracked asset lock schema")
    paths = asset_lock.get("runtimePaths")
    if not isinstance(paths, dict) or set(paths) != {
        "engine", "model", "humanModel", "analysisConfig"
    }:
        raise ValueError("The tracked asset lock must define all runtime paths")
    for key, value in paths.items():
        pattern = {
            "engine": r"runtime/engine/katago\.exe",
            "analysisConfig": r"runtime/configs/analysis\.cfg",
            "model": r"runtime/models/[A-Za-z0-9][A-Za-z0-9_.-]*\.bin\.gz",
            "humanModel": r"runtime/models/[A-Za-z0-9][A-Za-z0-9_.-]*\.bin\.gz",
        }[key]
        if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
            raise ValueError(f"Unsafe tracked runtime path for {key}: {value!r}")
    if paths["model"].lower() == paths["humanModel"].lower():
        raise ValueError("Main and Human SL model paths must be distinct")
    return dict(paths)


def reviewed_project_input(path: Path) -> Path:
    """v1.2.0: reject outside inputs and links in every source-path component."""
    path = path if path.is_absolute() else ROOT / path
    if ".." in path.parts or not path.is_relative_to(ROOT):
        raise ValueError(f"Release input must stay inside the project: {path}")
    for part in (path, *path.parents):
        if part.is_symlink() or os.path.isjunction(part):
            raise ValueError(f"Linked release input is not allowed: {path}")
        if part == ROOT:
            break
    if not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError(f"Release input resolves outside the project: {path}")
    return path


def prepare_runtime(
    stage: Path, *, variant: str = "tf3", source_root: Path | None = None,
) -> None:
    """Build one reviewed runtime without changing the active source runtime."""
    if variant not in ENGINE_FILES:
        raise ValueError(f"Unknown release variant: {variant}")
    if variant == "b28" and source_root is None:
        raise ValueError("B28 requires an explicit --b28-source-root")
    source_root = reviewed_project_input(source_root or ROOT)
    if not source_root.is_dir():
        raise FileNotFoundError(source_root)
    manifest_path = source_root / "runtime" / "runtime.local.json"
    if variant == "b28" and not manifest_path.is_file():
        manifest_path = source_root / "runtime" / "bundle.json"
    local_manifest = json.loads(
        required_file(reviewed_project_input(manifest_path)).read_text(encoding="utf-8")
    )
    lock_name = "asset_lock.json" if variant == "tf3" else "asset_lock.b28.json"
    asset_lock = json.loads(
        required_file(reviewed_project_input(ROOT / "packaging" / lock_name)).read_text(
            encoding="utf-8"
        )
    )
    manifest_keys = ("engine", "model", "humanModel", "analysisConfig")
    expected_paths = reviewed_runtime_paths(asset_lock)
    for key in manifest_keys:
        if local_manifest.get(key) != expected_paths[key]:
            raise ValueError(f"Unexpected runtime manifest {key}: {local_manifest.get(key)!r}")
    if local_manifest.get("engineVersion") != asset_lock.get("engineVersion"):
        raise ValueError("KataGo engine version differs from the tracked asset lock")
    # Historical B28 bundles predate explicit engine/Human SL hashes and backend.
    # Missing metadata may be reconstructed only from the reviewed lock, after
    # verifying every actual asset. Present metadata must never disagree.
    legacy_bundle = variant == "b28" and manifest_path.name == "bundle.json"
    if local_manifest.get("backend", "cuda" if legacy_bundle else None) != "cuda":
        raise ValueError("The reviewed Windows runtime requires the CUDA backend")
    required_libraries = RELEASE_CUDA_LIBRARIES if variant == "tf3" else B28_CUDA_LIBRARIES
    cuda_libraries = local_manifest.get(
        "requiredCudaLibraries", list(required_libraries) if legacy_bundle else None
    )
    if (
        not isinstance(cuda_libraries, list)
        or not all(isinstance(name, str) for name in cuda_libraries)
        or len(cuda_libraries) != len(required_libraries)
        or set(cuda_libraries) != set(required_libraries)
    ):
        raise ValueError(f"The {variant.upper()} runtime requires its reviewed CUDA DLL list")
    for key in ("engineGitRevision", "engineArchiveSha256"):
        value = asset_lock.get(key)
        if value is not None and local_manifest.get(
            key, value if legacy_bundle else None
        ) != value:
            raise ValueError(f"Runtime {key} differs from the tracked asset lock")
    approved_engine_names = {
        "runtime/engine/" + name for name in ENGINE_FILES[variant]
    }
    engine_files = asset_lock.get("engineFiles")
    if (
        not isinstance(engine_files, list)
        or not all(isinstance(path, str) for path in engine_files)
        or len(engine_files) != len(approved_engine_names)
        or set(engine_files) != approved_engine_names
    ):
        raise ValueError("The tracked engine list must contain exactly the approved files")
    expected_asset_names = approved_engine_names | {
        expected_paths["model"], expected_paths["humanModel"]
    }
    locked_files = asset_lock.get("files")
    if not isinstance(locked_files, dict) or set(locked_files) != expected_asset_names:
        raise ValueError("The tracked asset lock must contain exactly the approved files")
    for relative, expected_hash in locked_files.items():
        if (
            not isinstance(expected_hash, str)
            or re.fullmatch(r"[a-fA-F0-9]{64}", expected_hash) is None
        ):
            raise ValueError(f"Invalid tracked asset SHA-256: {relative}")
        source = required_file(reviewed_project_input(source_root / relative))
        actual_hash = file_hash(source)
        if actual_hash.lower() != str(expected_hash).lower():
            raise ValueError(f"Tracked asset SHA-256 mismatch: {relative}")
        print(f"Verified {relative}: {actual_hash}", flush=True)
    for key, checksum_key in (
        ("engine", "engineSha256"),
        ("model", "modelSha256"),
        ("humanModel", "humanModelSha256"),
    ):
        source = source_root / expected_paths[key]
        actual = locked_files[expected_paths[key]]  # Actual content was verified above.
        expected = local_manifest.get(checksum_key, actual if legacy_bundle else "")
        if actual.lower() != str(expected).lower():
            raise ValueError(f"SHA-256 mismatch for {source.name}")
        print(f"Verified {source.name}: {actual}", flush=True)

    # Both variants retain the current search configuration and 9/13/19 support.
    config = required_file(reviewed_project_input(
        ROOT / expected_paths["analysisConfig"]
    )).read_text(encoding="utf-8")
    config, count = re.subn(r"(?m)^logDir\s*=.*$", "logDir = logs/katago", config, count=1)
    if count != 1:
        raise ValueError("Expected exactly one KataGo logDir entry")
    for relative in sorted(expected_asset_names):
        copy_file(source_root / relative, stage / relative)
    config_path = stage / expected_paths["analysisConfig"]
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config, encoding="utf-8")

    bundle: dict[str, object] = {key: expected_paths[key] for key in manifest_keys}
    bundle.update(
        engineVersion=str(local_manifest["engineVersion"]),
        engineSha256=locked_files[expected_paths["engine"]],
        modelSha256=locked_files[expected_paths["model"]],
        humanModelSha256=locked_files[expected_paths["humanModel"]],
        backend="cuda",
        requiredCudaLibraries=list(required_libraries),
        releaseVariant=variant,
    )
    for key in ("engineGitRevision", "engineArchiveSha256"):
        value = asset_lock.get(key)
        if value is not None:
            bundle[key] = value
    (stage / "runtime" / "bundle.json").write_text(
        json.dumps(bundle, indent=2) + "\n", encoding="utf-8"
    )
    (stage / "runtime" / "release-info.txt").write_text(
        f"RecurGO runtime: {variant.upper()}\n"
        f"KataGo: {bundle['engineVersion']}\n"
        f"Main model: {Path(expected_paths['model']).name}\n",
        encoding="utf-8",
    )


def copy_tracked_licenses(stage: Path) -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "licenses"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    tracked_paths = {Path(os.fsdecode(name)) for name in tracked.split(b"\0") if name}
    actual_paths = {
        path.relative_to(ROOT) for path in (ROOT / "licenses").rglob("*") if path.is_file()
    }
    if any(
        path.is_symlink() or os.path.isjunction(path) for path in (ROOT / "licenses").rglob("*")
    ):
        raise ValueError("Linked license file or directory is not allowed")
    if not tracked_paths or tracked_paths != actual_paths:
        raise ValueError("License files differ from the reviewed Git file list")
    for relative in sorted(tracked_paths):
        copy_file(ROOT / relative, stage / relative)


def prepare_documents(stage: Path) -> None:
    for filename in (
        "LICENSE",
        "SECURITY.md",
        "SECURITY.en.md",
        "THIRD_PARTY_NOTICES.md",
        "THIRD_PARTY_NOTICES.en.md",
    ):
        copy_file(ROOT / filename, stage / filename)
    copy_file(ROOT / "packaging" / "INSTALLER_NOTICE.txt", stage / "INSTALLER_NOTICE.txt")
    for filename in (
        "USER_GUIDE.md",
        "USER_GUIDE.en.md",
        "INSTALL_WINDOWS.md",
        "INSTALL_WINDOWS.en.md",
        "SOURCE_SETUP.md",
        "SOURCE_SETUP.en.md",
        "OLLAMA_LOCAL.md",
        "OLLAMA_LOCAL.en.md",
    ):
        copy_file(ROOT / "docs" / filename, stage / "docs" / filename)
    copy_tracked_licenses(stage)
    write_installer_license(stage)
    copy_file(ROOT / "scripts" / "ollama_local.ps1", stage / "scripts" / "ollama_local.ps1")
    for source_name, target_name in (
        ("check_analysis_environment_installed.cmd", "check_analysis_environment.cmd"),
        ("start_optional_ollama_installed.cmd", "start_optional_ollama.cmd"),
        ("download_ollama_model_installed.cmd", "download_ollama_model.cmd"),
    ):
        copy_file(ROOT / "packaging" / source_name, stage / target_name)


def write_installer_license(stage: Path) -> None:
    """Present both project and bundled Microsoft runtime terms for acceptance."""
    project_license = required_file(stage / "LICENSE").read_text(encoding="utf-8")
    runtime_license = required_file(
        stage / "licenses" / "microsoft" / "Visual-Cpp-Runtime-2015-2022-License-EN.txt"
    ).read_text(encoding="utf-8")
    destination = stage / "INSTALLER_LICENSE.txt"
    if destination.exists():
        raise FileExistsError(destination)
    destination.write_text(
        "RecurGO installation terms / RecurGO 安装许可条款\n\n"
        "RecurGO's own code and documentation use the MIT License below. Microsoft Visual C++ "
        "runtime files included with this installer have separate Microsoft terms. Accepting "
        "this page means accepting both sets of terms for their respective components. "
        "The Microsoft terms do not change the MIT license for RecurGO-owned code.\n\n"
        "RecurGO 自有代码和文档适用下方 MIT 许可。安装包中的 Microsoft Visual C++ 运行库文件"
        "另有微软条款。接受本页表示分别接受适用于各自组件的两套条款；微软条款不改变 "
        "RecurGO 自有代码的 MIT 许可。\n\n"
        "=== RecurGO MIT License ===\n\n"
        + project_license.rstrip()
        + "\n\n=== Microsoft Visual C++ Runtime License (official English text) ===\n\n"
        + runtime_license,
        encoding="utf-8-sig",
    )


def verify_stage(stage: Path) -> None:
    forbidden_runtime_roots = {("runtime", "cuda_deps"), ("runtime", "ollama")}
    forbidden_names = {"runtime.local.json", *BLOCKED_OPTIONAL_RUNTIME_NAMES}
    binary_extensions = {".dll", ".exe", ".gz", ".ico", ".png", ".pyd", ".qm", ".zip"}
    secret_markers = re.compile(
        r"gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
    )
    for path in stage.rglob("*"):
        if path.is_symlink() or os.path.isjunction(path):
            raise ValueError(
                f"Linked file or directory entered stage: {path.relative_to(stage)}"
            )
        if not path.is_file():
            continue
        relative = path.relative_to(stage)
        lowered = [part.lower() for part in relative.parts]
        if lowered[0] in {"data", ".venv"} or tuple(lowered[:2]) in forbidden_runtime_roots:
            raise ValueError(f"Private or user-supplied directory entered stage: {relative}")
        if "data" in lowered and tuple(lowered) != (
            "_internal",
            "cv2",
            "data",
            "__init__.py",
        ):
            raise ValueError(f"Unreviewed data directory entered stage: {relative}")
        if path.name.lower() in forbidden_names:
            raise ValueError(f"Forbidden file entered stage: {relative}")
        if re.search(
            r"\.(?:db|sqlite|sqlite3)(?:-(?:wal|shm))?$", path.name, re.I
        ) or path.suffix.lower() in {".sgf", ".log", ".env"}:
            raise ValueError(f"Personal data type entered stage: {relative}")
        if relative.parts[:2] == ("runtime", "engine") and path.name.lower().startswith(
            ("msvcp", "vcruntime")
        ):
            raise ValueError(
                f"Developer-machine Microsoft DLL entered engine stage: {relative}"
            )
        if path.suffix.lower() not in binary_extensions:
            if path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError(f"Unreviewed large staged file: {relative}")
            body = path.read_text(encoding="utf-8", errors="ignore")
            normalized = body.replace("\\", "/").lower()
            if ROOT.as_posix().lower() in normalized or re.search(
                r"[a-z]:/users/[^/\s]+/", normalized
            ):
                raise ValueError(f"Developer-machine path entered stage text: {relative}")
            if secret_markers.search(body):
                raise ValueError(f"Secret marker entered stage text: {relative}")


def write_manifest(stage: Path, release_root: Path, *, variant: str) -> None:
    records = []
    for path in sorted(stage.rglob("*")):
        if path.is_file():
            records.append(
                {
                    "path": path.relative_to(stage).as_posix(),
                    "sizeBytes": path.stat().st_size,
                    "sha256": file_hash(path),
                }
            )
    (release_root / f"file-manifest-{variant.upper()}.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Recorded {len(records)} staged files", flush=True)


def prepare_stages(
    main_folder: Path,
    checker: Path,
    *,
    sources: dict[str, Path],
    release_root: Path,
) -> dict[str, Path]:
    """v1.2.0: copy one frozen application into isolated, audited runtime stages."""
    stages = {}
    for variant, source_root in sources.items():
        stage = release_root / "stage" / variant.upper() / "RecurGO"
        shutil.copytree(main_folder, stage)
        copy_file(checker, stage / checker.name)
        prepare_runtime(stage, variant=variant, source_root=source_root)
        prepare_documents(stage)
        copy_file(APP_ICON, stage / "assets" / "recurgo.ico")
        verify_stage(stage)
        write_manifest(stage, release_root, variant=variant)
        stages[variant] = stage
    return stages


def compile_installers(
    stages: dict[str, Path],
    *,
    version: str,
    release_root: Path,
    iscc: Path,
    env: dict[str, str],
) -> list[Path]:
    output_dir = release_root / "output"
    output_dir.mkdir(parents=True, exist_ok=False)
    expected = []
    for variant, stage in stages.items():
        installer = output_dir / f"RecurGO-{version}-{variant.upper()}-Windows-x64-Setup.exe"
        run(
            [
                str(iscc),
                f"/DBuildSourceDir={stage}",
                f"/DAppVersion={version}",
                f"/DReleaseVariant={variant.upper()}",
                f"/O{output_dir}",
                str(ROOT / "packaging" / "RecurGO.iss"),
            ],
            env=env,
        )
        required_file(installer)
        expected.append(installer)
    installers = set(output_dir.glob("*.exe"))
    if installers != set(expected):
        raise ValueError("Installer output differs from the selected release variants")
    checksums = []
    for installer in expected:
        checksum = file_hash(installer)
        checksums.append(f"{checksum}  {installer.name}\n")
        print(f"Installer: {installer}", flush=True)
        print(f"Size: {installer.stat().st_size / (1024 * 1024):.2f} MB", flush=True)
        print(f"SHA-256: {checksum}", flush=True)
    (output_dir / "SHA256SUMS.txt").write_text("".join(checksums), encoding="utf-8")
    return expected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iscc", required=True, type=Path, help="Local Inno Setup ISCC.exe")
    parser.add_argument("--variant", choices=("tf3", "b28", "all"), default="tf3")
    parser.add_argument(
        "--b28-source-root", type=Path,
        help="Project-local root containing the reviewed B28 runtime/ assets and manifest",
    )
    args = parser.parse_args()
    variants = ("tf3", "b28") if args.variant == "all" else (args.variant,)
    if "b28" in variants and args.b28_source_root is None:
        parser.error("--b28-source-root is required for --variant b28 or all")
    if "b28" not in variants and args.b28_source_root is not None:
        parser.error("--b28-source-root requires --variant b28 or all")
    sources = {
        variant: reviewed_project_input(args.b28_source_root if variant == "b28" else ROOT)
        for variant in variants
    }
    for source_root in sources.values():
        if not source_root.is_dir():
            raise FileNotFoundError(source_root)
    if sys.platform != "win32":
        raise SystemExit("Windows is required to build this installer")
    if not args.iscc.is_file():
        raise FileNotFoundError(args.iscc)
    if not (ROOT / ".venv" / "Scripts" / "python.exe").samefile(sys.executable):
        raise SystemExit("Run with the project's .venv Python")

    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    release_root = ROOT / "build" / f"release-{version}-{stamp}-{uuid4().hex[:8]}"
    release_root.mkdir(parents=True, exist_ok=False)
    env = prepare_environment(release_root)

    main_folder = freeze_entry(
        ROOT / "src" / "recurgo" / "app.py",
        "RecurGO",
        one_file=False,
        console=False,
        release_root=release_root,
        env=env,
    )
    checker = freeze_entry(
        ROOT / "scripts" / "check_analysis_environment.py",
        "RecurGO-Environment-Check",
        one_file=True,
        console=True,
        release_root=release_root,
        env=env,
    )
    stages = prepare_stages(main_folder, checker, sources=sources, release_root=release_root)
    compile_installers(
        stages, version=version, release_root=release_root, iscc=args.iscc, env=env
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
