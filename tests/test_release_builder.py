"""Release packaging must fail closed on private or unreviewed inputs."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import build_windows_release as release


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
