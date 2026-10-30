"""Release packaging must fail closed on private or unreviewed inputs."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import build_windows_release as release


def test_installer_removes_only_the_three_obsolete_engine_assets() -> None:
    script = (release.ROOT / "packaging" / "RecurGO.iss").read_text(encoding="utf-8")
    section = script.split("[InstallDelete]", 1)[1].split("[", 1)[0]
    directives = {
        line.strip() for line in section.splitlines()
        if line.strip() and not line.lstrip().startswith(";")
    }
    assert directives == {
        'Type: files; Name: "{app}\\runtime\\engine\\libz.dll"',
        'Type: files; Name: "{app}\\runtime\\engine\\libzip.dll"',
        'Type: files; Name: "{app}\\runtime\\models\\'
        'kata1-b28c512nbt-s13255194368-d5935380940.bin.gz"',
    }


@pytest.fixture
def runtime_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, dict]:
    """Synthetic v1.1.0.dev1 inputs; never use the user's installed runtime."""
    project = tmp_path / "project"
    paths = {
        "engine": "runtime/engine/katago.exe",
        "model": "runtime/models/kata1-tf3-fixture.bin.gz",
        "humanModel": "runtime/models/human-fixture.bin.gz",
        "analysisConfig": "runtime/configs/analysis.cfg",
    }
    engine_files = [
        "runtime/engine/" + name for name in (
            "katago.exe", "libcrypto-3-x64.dll", "libssl-3-x64.dll", "z.dll",
            "zip.dll", "bz2.dll", "cacert.pem", "README.txt",
        )
    ]
    hashes = {}
    for relative in engine_files + [paths["model"], paths["humanModel"]]:
        source = project / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(("synthetic " + relative).encode())
        hashes[relative] = release.file_hash(source)
    config = project / paths["analysisConfig"]
    config.parent.mkdir(parents=True)
    config.write_text("logDir = private-machine-path\nmaxVisits = 800\n", encoding="utf-8")
    lock = {
        "schemaVersion": 2,
        "engineVersion": "1.18.2",
        "engineGitRevision": "a" * 40,
        "engineArchiveSha256": "b" * 64,
        "runtimePaths": paths,
        "engineFiles": engine_files,
        "files": hashes,
    }
    manifest = {
        **paths,
        "engineVersion": lock["engineVersion"],
        "engineGitRevision": lock["engineGitRevision"],
        "engineArchiveSha256": lock["engineArchiveSha256"],
        "engineSha256": hashes[paths["engine"]],
        "modelSha256": hashes[paths["model"]],
        "humanModelSha256": hashes[paths["humanModel"]],
        "backend": "cuda",
        "requiredCudaLibraries": list(release.RELEASE_CUDA_LIBRARIES),
    }
    (project / "packaging").mkdir()
    (project / "packaging" / "asset_lock.json").write_text(json.dumps(lock), encoding="utf-8")
    (project / "runtime" / "runtime.local.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    monkeypatch.setattr(release, "ROOT", project)
    monkeypatch.setattr(release, "SOURCE_RUNTIME", project / "runtime")
    return project, lock


def test_runtime_bundle_uses_reviewed_models_and_engine_identity(runtime_inputs) -> None:
    project, lock = runtime_inputs
    # An unrelated model must not be picked up by a directory glob.
    (project / "runtime/models/old-model.bin.gz").write_bytes(b"old synthetic model")
    release.prepare_runtime(project / "stage")
    bundle = json.loads((project / "stage/runtime/bundle.json").read_text())
    assert bundle["model"] == lock["runtimePaths"]["model"]
    assert bundle["engineSha256"] == lock["files"]["runtime/engine/katago.exe"]
    assert bundle["engineGitRevision"] == lock["engineGitRevision"]
    assert bundle["backend"] == "cuda"
    assert bundle["requiredCudaLibraries"] == list(release.RELEASE_CUDA_LIBRARIES)
    assert not (project / "stage/runtime/models/old-model.bin.gz").exists()
    assert "logDir = logs/katago" in (
        project / "stage/runtime/configs/analysis.cfg"
    ).read_text()


@pytest.mark.parametrize("failure", ["hash", "manifest", "extra", "duplicate", "revision"])
def test_runtime_bundle_rejects_mismatched_inputs_before_copy(runtime_inputs, failure) -> None:
    project, lock = runtime_inputs
    manifest_path = project / "runtime/runtime.local.json"
    manifest = json.loads(manifest_path.read_text())
    if failure == "hash":
        (project / lock["runtimePaths"]["model"]).write_bytes(b"tampered")
    elif failure == "manifest":
        manifest["model"] = "runtime/models/unreviewed.bin.gz"
    elif failure == "extra":
        lock["files"]["runtime/engine/private.txt"] = "c" * 64
    elif failure == "duplicate":
        lock["engineFiles"].append(lock["engineFiles"][0])
    else:
        manifest["engineGitRevision"] = "c" * 40
    (project / "packaging/asset_lock.json").write_text(json.dumps(lock), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        release.prepare_runtime(project / "stage")
    assert not (project / "stage").exists()


@pytest.mark.parametrize("path", [
    "../private.bin.gz", "C:/private.bin.gz", "runtime/models/../private.bin.gz",
    "runtime/models/nested/private.bin.gz", "runtime/models/private.db",
])
def test_runtime_paths_reject_unsafe_model_paths(runtime_inputs, path) -> None:
    _project, lock = runtime_inputs
    lock["runtimePaths"]["model"] = path
    with pytest.raises(ValueError, match="Unsafe tracked runtime path"):
        release.reviewed_runtime_paths(lock)


@pytest.mark.parametrize("key,value", [
    ("engineSha256", "c" * 64),
    ("engineSha256", None),
    ("backend", "opencl"),
    ("backend", None),
    ("requiredCudaLibraries", None),
    ("requiredCudaLibraries", ["cublas64_12.dll", "cudart64_12.dll"]),
    ("requiredCudaLibraries", list(release.RELEASE_CUDA_LIBRARIES) + ["extra.dll"]),
    ("requiredCudaLibraries", ["cublas64_12.dll"] * 4),
    ("requiredCudaLibraries", ["cublas64_12.dll", "cudart64_12.dll", "../nvrtc.dll", 12]),
])
def test_runtime_bundle_rejects_engine_identity_or_cuda_dependency_drift(
    runtime_inputs, key, value
) -> None:
    project, _lock = runtime_inputs
    manifest_path = project / "runtime/runtime.local.json"
    manifest = json.loads(manifest_path.read_text())
    if value is None:
        manifest.pop(key)
    else:
        manifest[key] = value
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        release.prepare_runtime(project / "stage")
    assert not (project / "stage").exists()


@pytest.mark.parametrize(
    "relative,body",
    [
        ("data/game.db", "private game"),
        ("_internal/example/data/game.txt", "private game"),
        ("_internal/cv2/data/private.txt", "private game"),
        ("runtime/engine/session.db-wal", "private game"),
        ("docs/game.sgf", "(;GM[1])"),
        ("docs/token.txt", "github_pat_" + "a" * 25),
        ("docs/key.pem", "-----BEGIN PRIVATE KEY-----"),
        ("docs/path.txt", "C:/Users/person/Documents/private.txt"),
        ("licenses/qt/COPYING", "C:/Users/person/Documents/private.txt"),
        ("licenses/qt/license.rst", "-----BEGIN PRIVATE KEY-----"),
        ("_internal/numpy-2.5.1.dist-info/RECORD", "C:/Users/person/private.txt"),
        ("_internal/pyqtgraph/colors/secret.csv", "github_pat_" + "b" * 25),
    ],
)
def test_stage_rejects_private_material(tmp_path: Path, relative: str, body: str) -> None:
    stage = tmp_path / "stage"
    target = stage / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    with pytest.raises(ValueError):
        release.verify_stage(stage)


def test_stage_accepts_reviewed_opencv_data(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    target = stage / "_internal" / "cv2" / "data" / "__init__.py"
    target.parent.mkdir(parents=True)
    target.write_text("", encoding="utf-8")
    release.verify_stage(stage)


@pytest.mark.parametrize("filename", sorted(release.BLOCKED_OPTIONAL_RUNTIME_NAMES))
def test_stage_rejects_unused_optional_runtime(
    tmp_path: Path, filename: str
) -> None:
    stage = tmp_path / "stage"
    target = stage / "_internal" / "PySide6" / filename
    target.parent.mkdir(parents=True)
    target.write_bytes(b"optional binary")
    with pytest.raises(ValueError, match="Forbidden file entered stage"):
        release.verify_stage(stage)


def test_license_copy_rejects_untracked_extra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    licenses = tmp_path / "licenses"
    licenses.mkdir()
    (licenses / "allowed.txt").write_text("license", encoding="utf-8")
    (licenses / "private.txt").write_text("private", encoding="utf-8")
    monkeypatch.setattr(release, "ROOT", tmp_path)
    monkeypatch.setattr(
        release.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, b"licenses/allowed.txt\0"
        ),
    )
    with pytest.raises(ValueError, match="License files differ"):
        release.copy_tracked_licenses(tmp_path / "stage")


def test_license_copy_uses_tracked_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    licenses = tmp_path / "licenses"
    licenses.mkdir()
    (licenses / "allowed.txt").write_text("license", encoding="utf-8")
    monkeypatch.setattr(release, "ROOT", tmp_path)
    monkeypatch.setattr(
        release.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, b"licenses/allowed.txt\0"
        ),
    )
    release.copy_tracked_licenses(tmp_path / "stage")
    assert (tmp_path / "stage" / "licenses" / "allowed.txt").read_text() == "license"


def test_installer_license_keeps_project_and_runtime_terms_separate(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    runtime = (
        stage / "licenses" / "microsoft" / "Visual-Cpp-Runtime-2015-2022-License-EN.txt"
    )
    runtime.parent.mkdir(parents=True)
    (stage / "LICENSE").write_text("MIT project terms", encoding="utf-8")
    runtime.write_text("Microsoft runtime terms", encoding="utf-8")

    release.write_installer_license(stage)

    combined = (stage / "INSTALLER_LICENSE.txt").read_text(encoding="utf-8-sig")
    assert "MIT project terms" in combined
    assert "Microsoft runtime terms" in combined
    assert combined.index("MIT project terms") < combined.index("Microsoft runtime terms")
    assert (stage / "LICENSE").read_text(encoding="utf-8") == "MIT project terms"
    with pytest.raises(FileExistsError):
        release.write_installer_license(stage)


def test_release_environment_removes_ambient_binary_and_python_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    python = tmp_path / "python"
    windows = tmp_path / "windows"
    for directory in (
        project / ".venv" / "Scripts",
        python / "Scripts",
        windows / "System32",
    ):
        directory.mkdir(parents=True)
    monkeypatch.setattr(release, "ROOT", project)
    monkeypatch.setattr(release.sys, "base_prefix", str(python))
    monkeypatch.setenv("SystemRoot", str(windows))
    monkeypatch.setenv("PATH", str(tmp_path / "untrusted"))
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "untrusted"))
    monkeypatch.setenv("QT_PLUGIN_PATH", str(tmp_path / "untrusted"))

    env = release.prepare_environment(project / "build" / "candidate")

    assert str(tmp_path / "untrusted") not in env["PATH"]
    assert "PYTHONPATH" not in env
    assert "QT_PLUGIN_PATH" not in env
    assert env["PYTHONNOUSERSITE"] == "1"
    assert str(project / ".venv" / "Scripts") in env["PATH"]


@pytest.mark.parametrize("outside", [False, True])
def test_frozen_dependency_sources_have_to_be_approved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outside: bool
) -> None:
    project = tmp_path / "project"
    allowed = project / ".venv" / "Lib" / "site-packages" / "safe.dll"
    unapproved = tmp_path / "unapproved" / "other.dll"
    source = unapproved if outside else allowed
    source.parent.mkdir(parents=True)
    source.write_bytes(b"binary")
    toc = tmp_path / "Analysis-00.toc"
    sections: list[object] = [None] * 20
    sections[15] = [("copied.dll", str(source), "BINARY")]
    sections[18] = []
    toc.write_text(repr(tuple(sections)), encoding="utf-8")
    monkeypatch.setattr(release, "ROOT", project)
    if outside:
        with pytest.raises(ValueError, match="Unapproved frozen input"):
            release.verify_collected_sources(toc, release_root=project / "build")
    else:
        release.verify_collected_sources(toc, release_root=project / "build")
