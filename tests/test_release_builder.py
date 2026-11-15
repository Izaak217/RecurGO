"""Release packaging must fail closed on private or unreviewed inputs."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import build_windows_release as release


def test_variants_share_installation_without_deleting_existing_assets() -> None:
    script = (release.ROOT / "packaging" / "RecurGO.iss").read_text(encoding="utf-8")
    assert "[InstallDelete]" not in script
    assert "AppId={{D68E0D17-61C0-4F1D-9AD0-73377206F1EA}" in script
    assert "DefaultDirName={localappdata}\\Programs\\RecurGO" in script
    assert "AppVerName=RecurGO {#AppVersion} ({#ReleaseVariant})" in script
    assert "RecurGO-{#AppVersion}-{#ReleaseVariant}-Windows-x64-Setup" in script


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
    config.write_text(
        "logDir = private-machine-path\nmaxVisits = 800\nrequireMaxBoardSize = false\n",
        encoding="utf-8",
    )
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
    return project, lock


@pytest.fixture
def dual_runtime_inputs(runtime_inputs) -> tuple[Path, Path, dict, dict]:
    project, tf3_lock = runtime_inputs
    source = project / "historical-b28"
    paths = {
        **tf3_lock["runtimePaths"],
        "model": "runtime/models/kata1-b28-fixture.bin.gz",
    }
    engine_files = ["runtime/engine/" + name for name in release.ENGINE_FILES["b28"]]
    hashes = {}
    for relative in engine_files + [paths["model"], paths["humanModel"]]:
        asset = source / relative
        asset.parent.mkdir(parents=True, exist_ok=True)
        body = (
            (project / relative).read_bytes() if relative == paths["humanModel"]
            else ("historical B28 " + relative).encode()
        )
        asset.write_bytes(body)
        hashes[relative] = release.file_hash(asset)
    old_config = source / paths["analysisConfig"]
    old_config.parent.mkdir(parents=True)
    old_config.write_text(
        "logDir = old-path\nmaxVisits = 100\nrequireMaxBoardSize = true\n",
        encoding="utf-8",
    )
    lock = {
        "schemaVersion": 2,
        "engineVersion": "1.16.5",
        "engineGitRevision": "c" * 40,
        "runtimePaths": paths,
        "engineFiles": engine_files,
        "files": hashes,
    }
    (project / "packaging/asset_lock.b28.json").write_text(json.dumps(lock), encoding="utf-8")
    # Match v1.0.2: no engine hash, backend, revision or explicit CUDA DLL list.
    manifest = {
        **paths,
        "engineVersion": lock["engineVersion"],
        "modelSha256": hashes[paths["model"]],
        "humanModelSha256": hashes[paths["humanModel"]],
    }
    (source / "runtime/bundle.json").write_text(json.dumps(manifest), encoding="utf-8")
    return project, source, tf3_lock, lock


def test_b28_legacy_bundle_gets_verified_identity_and_current_config(
    dual_runtime_inputs,
) -> None:
    project, source, _tf3_lock, lock = dual_runtime_inputs
    manifest_before = (project / "runtime/runtime.local.json").read_bytes()
    source_before = (source / "runtime/bundle.json").read_bytes()
    stage = project / "stage-b28"
    release.prepare_runtime(stage, variant="b28", source_root=source)
    bundle = json.loads((stage / "runtime/bundle.json").read_text())
    assert bundle["releaseVariant"] == "b28"
    assert bundle["engineVersion"] == "1.16.5"
    assert bundle["engineGitRevision"] == lock["engineGitRevision"]
    assert bundle["requiredCudaLibraries"] == list(release.B28_CUDA_LIBRARIES)
    for key, digest in (
        ("engine", "engineSha256"), ("model", "modelSha256"),
        ("humanModel", "humanModelSha256"),
    ):
        assert bundle[digest] == release.file_hash(stage / lock["runtimePaths"][key])
    assert (stage / "runtime/configs/analysis.cfg").read_text() == (
        "logDir = logs/katago\nmaxVisits = 800\nrequireMaxBoardSize = false\n"
    )
    assert "B28" in (stage / "runtime/release-info.txt").read_text()
    assert (project / "runtime/runtime.local.json").read_bytes() == manifest_before
    assert (source / "runtime/bundle.json").read_bytes() == source_before


@pytest.mark.parametrize("failure", [
    "asset", "engine_hash", "model_path", "engine_version", "backend", "cuda", "revision",
    "extra_engine", "extra_asset",
])
def test_b28_rejects_inconsistent_historical_inputs_before_copy(
    dual_runtime_inputs, failure,
) -> None:
    project, source, _tf3_lock, lock = dual_runtime_inputs
    manifest_path = source / "runtime/bundle.json"
    manifest = json.loads(manifest_path.read_text())
    if failure == "asset":
        (source / lock["runtimePaths"]["model"]).write_bytes(b"different model")
    elif failure == "engine_hash":
        manifest["engineSha256"] = "d" * 64
    elif failure == "model_path":
        manifest["model"] = "runtime/models/kata1-tf3-fixture.bin.gz"
    elif failure == "engine_version":
        manifest["engineVersion"] = "1.18.2"
    elif failure == "backend":
        manifest["backend"] = "opencl"
    elif failure == "cuda":
        manifest["requiredCudaLibraries"] = list(release.RELEASE_CUDA_LIBRARIES)
    elif failure == "revision":
        manifest["engineGitRevision"] = "d" * 40
    elif failure == "extra_engine":
        lock["engineFiles"].append("runtime/engine/z.dll")
    else:
        lock["files"]["runtime/engine/private.txt"] = "d" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    (project / "packaging/asset_lock.b28.json").write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(ValueError):
        release.prepare_runtime(project / "stage", variant="b28", source_root=source)
    assert not (project / "stage").exists()


def test_b28_requires_explicit_project_local_source(runtime_inputs) -> None:
    project, _lock = runtime_inputs
    with pytest.raises(ValueError, match="explicit"):
        release.prepare_runtime(project / "stage", variant="b28")
    with pytest.raises(ValueError, match="inside the project"):
        release.prepare_runtime(project / "stage", variant="b28", source_root=project.parent)
    with pytest.raises(ValueError, match="inside the project"):
        release.reviewed_project_input(project / ".." / "other")
    assert not (project / "stage").exists()


def test_source_link_ancestors_are_rejected(dual_runtime_inputs, monkeypatch) -> None:
    project, source, _tf3_lock, _lock = dual_runtime_inputs
    real_isjunction = release.os.path.isjunction
    monkeypatch.setattr(
        release.os.path, "isjunction", lambda path: path == source or real_isjunction(path)
    )
    with pytest.raises(ValueError, match="Linked release input"):
        release.prepare_runtime(project / "stage", variant="b28", source_root=source)
    assert not (project / "stage").exists()


def test_linked_asset_directory_is_rejected(dual_runtime_inputs, monkeypatch) -> None:
    project, source, _tf3_lock, _lock = dual_runtime_inputs
    real_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path, "is_symlink",
        lambda path: path == source / "runtime/models" or real_is_symlink(path),
    )
    with pytest.raises(ValueError, match="Linked release input"):
        release.prepare_runtime(project / "stage", variant="b28", source_root=source)
    assert not (project / "stage").exists()


@pytest.fixture
def frozen_inputs(dual_runtime_inputs, monkeypatch):
    project, source, tf3_lock, b28_lock = dual_runtime_inputs
    main_folder = project / "frozen/RecurGO"
    main_folder.mkdir(parents=True)
    (main_folder / "RecurGO.exe").write_bytes(b"same frozen application")
    checker = project / "frozen/RecurGO-Environment-Check.exe"
    checker.write_bytes(b"same frozen checker")
    icon = project / "source-icon.ico"
    icon.write_bytes(b"icon")
    monkeypatch.setattr(release, "APP_ICON", icon)
    monkeypatch.setattr(
        release, "prepare_documents", lambda stage: (stage / "NOTICE.txt").write_text(
            "same reviewed documentation", encoding="utf-8"
        )
    )
    return project, source, tf3_lock, b28_lock, main_folder, checker


def test_all_freezes_once_and_produces_isolated_stages_and_combined_checksums(
    frozen_inputs, monkeypatch,
) -> None:
    project, source, tf3_lock, b28_lock, main_folder, checker = frozen_inputs
    python = project / ".venv/Scripts/python.exe"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"python")
    iscc = project / "ISCC.exe"
    iscc.write_bytes(b"compiler")
    (project / "pyproject.toml").write_text('[project]\nversion = "1.2.0"\n')
    monkeypatch.setattr(release.sys, "executable", str(python))
    monkeypatch.setattr(release.sys, "platform", "win32")
    monkeypatch.setattr(release.sys, "argv", [
        "builder", "--iscc", str(iscc), "--variant", "all",
        "--b28-source-root", str(source),
    ])
    monkeypatch.setattr(release, "prepare_environment", lambda _root: {})
    freeze_calls = []

    def freeze(entry, name, **kwargs):
        freeze_calls.append((name, kwargs["one_file"]))
        return main_folder if name == "RecurGO" else checker

    def compile_fake(command, *, env):
        variant = next(part.split("=", 1)[1] for part in command if part.startswith(
            "/DReleaseVariant="
        ))
        output = Path(next(part[2:] for part in command if part.startswith("/O")))
        (output / f"RecurGO-1.2.0-{variant}-Windows-x64-Setup.exe").write_bytes(
            variant.encode()
        )

    monkeypatch.setattr(release, "freeze_entry", freeze)
    monkeypatch.setattr(release, "run", compile_fake)
    assert release.main() == 0
    assert freeze_calls == [("RecurGO", False), ("RecurGO-Environment-Check", True)]
    builds = list((project / "build").iterdir())
    assert len(builds) == 1
    build = builds[0]
    for variant, lock, other_lock in (("TF3", tf3_lock, b28_lock), ("B28", b28_lock, tf3_lock)):
        stage = build / "stage" / variant / "RecurGO"
        assert (stage / "RecurGO.exe").read_bytes() == b"same frozen application"
        assert (stage / checker.name).read_bytes() == checker.read_bytes()
        assert (stage / "NOTICE.txt").is_file()
        bundle = json.loads((stage / "runtime/bundle.json").read_text())
        assert bundle["releaseVariant"] == variant.lower()
        assert bundle["engineSha256"] == lock["files"]["runtime/engine/katago.exe"]
        assert (stage / lock["runtimePaths"]["model"]).is_file()
        assert not (stage / other_lock["runtimePaths"]["model"]).exists()
        assert not (stage / "runtime/runtime.local.json").exists()
        manifest = json.loads((build / f"file-manifest-{variant}.json").read_text())
        assert any(item["path"] == "runtime/release-info.txt" for item in manifest)
        for item in manifest:
            assert release.file_hash(stage / item["path"]) == item["sha256"]
    assert (build / "stage/TF3/RecurGO/runtime/configs/analysis.cfg").read_bytes() == (
        build / "stage/B28/RecurGO/runtime/configs/analysis.cfg"
    ).read_bytes()
    checksum_lines = (build / "output/SHA256SUMS.txt").read_text().splitlines()
    assert len(checksum_lines) == 2
    for line in checksum_lines:
        digest, name = line.split("  ")
        assert digest == release.file_hash(build / "output" / name)


def test_each_variant_stage_is_privacy_checked(frozen_inputs) -> None:
    project, source, _tf3, _b28, main_folder, checker = frozen_inputs
    (main_folder / "private.sgf").write_text("(;GM[1])")
    for variant, asset_root in (("tf3", project), ("b28", source)):
        with pytest.raises(ValueError):
            release.prepare_stages(
                main_folder, checker, sources={variant: asset_root},
                release_root=project / ("build-" + variant),
            )


@pytest.mark.parametrize("variant,args", [
    ("b28", []), ("all", []), ("tf3", ["--b28-source-root", "."]),
])
def test_cli_rejects_missing_or_unused_b28_source_before_build(
    variant, args, monkeypatch,
) -> None:
    monkeypatch.setattr(
        release.sys, "argv", ["builder", "--iscc", "ISCC.exe", "--variant", variant, *args]
    )
    with pytest.raises(SystemExit) as error:
        release.main()
    assert error.value.code == 2


def test_installer_checksums_are_not_written_for_unexpected_outputs(
    runtime_inputs, monkeypatch,
) -> None:
    project, _lock = runtime_inputs
    build = project / "build"

    def unexpected_output(command, *, env):
        output = build / "output"
        (output / "RecurGO-1.2.0-TF3-Windows-x64-Setup.exe").write_bytes(b"expected")
        (output / "RecurGO-unreviewed-Setup.exe").write_bytes(b"unexpected")

    monkeypatch.setattr(release, "run", unexpected_output)
    with pytest.raises(ValueError, match="differs from the selected"):
        release.compile_installers(
            {"tf3": project / "stage"}, version="1.2.0", release_root=build,
            iscc=project / "ISCC.exe", env={},
        )
    assert not (build / "output/SHA256SUMS.txt").exists()


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
