# Distributing source and a Windows installer (document revision v0.1.4)

English | [简体中文](DISTRIBUTION.md)

This document describes the v1.0.0 source and Windows installer contents and the publication checks to repeat for later versions. See [Third-party notices](../THIRD_PARTY_NOTICES.en.md) for the license inventory.

## What belongs in the source repository

Keep `src/`, `tests/`, `scripts/`, public `docs/`, `licenses/`, launcher scripts, project metadata, and the license files in the root. `docs/setup/` contains public configuration examples; users copy them and fill in their own machine paths.

`.gitignore` excludes:

| Content | Paths or rules |
| --- | --- |
| Games, databases, analysis caches, screenshots, diagnostics, logs | All of `data/`, plus database, log, and SGF filename patterns elsewhere |
| Local engine, models, CUDA/cuDNN, Ollama, downloads, secrets, runtime configuration | All of `runtime/` |
| Python environments and generated build/test files | `.venv/`, `__pycache__/`, tool caches, `build/`, `dist/`, and related patterns |
| Environment secrets, local overrides, editor/agent state | `.env*`, `*.local.json`, and related patterns; `.env.example` remains allowed |
| Early local implementation notes | `docs/PROJECT_PLAN.md` |

Reviewed SGF fixtures under `tests/fixtures/` may remain as test data. The third-party source archive `licenses/sources/sgfmill-1.1.1.tar.gz` is retained for license traceability; archive formats are therefore not ignored wholesale.

## Distinguishing directories named `data`

| Location | Contents and release handling |
| --- | --- |
| Project-root `data/` | Local game databases, logs, environment checks, and other user data; excluded entirely from source and installer. |
| `.venv/Lib/site-packages/**/data/` | Local Python dependency resources or test data; the virtual environment is excluded from source and is not copied wholesale. |
| Installer stage `_internal/cv2/data/` | An OpenCV package resource collected by PyInstaller; it currently contains only `__init__.py` and may be bundled. |
| Any other new `data/` | The build fails pending a source and privacy review. |

The installer builder copies license material only from Git-tracked files under `licenses/` and
fails when extra files appear there. It also checks the staged tree for databases, games, logs,
linked files, common key markers, and local machine paths. These checks guard against accidental
packaging; they do not replace a review of source, binaries, and installed behavior before release.

Ignored files remain on the local machine. `.gitignore` neither deletes them nor controls manual uploads, whole-directory archives, `git add -f`, or files already tracked by Git. It is not a secrets scanner. See the [Git documentation](https://git-scm.com/docs/gitignore).

## Review before each publication

The local `main` repository was initialized on 2026-09-23. The first public version uses one root commit. Before each publication, inspect the worktree:

```powershell
git status --short --untracked-files=all
git check-ignore -v data/recurgo.db runtime/runtime.local.json
git add --dry-run .
```

After staging, inspect `git diff --cached --name-only` and `git diff --cached` for personal game records, screenshots, account information, and downloaded resources. Do not override ignore rules with `git add -f` or zip the entire working directory. If a sensitive file was already committed, adding an ignore rule will not erase it from history; it requires a separate review.

GitHub also supports browser-based file uploads, without local Git. That route does not apply local `.gitignore` rules for you; files must be chosen manually. See [GitHub's upload guide](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository).

## Source, Python package, and installer are different

RecurGO-owned source uses MIT. Original third-party license texts and accompanying notes are in `licenses/`. Python build metadata declares those files, but an independently installed wheel has not been validated as a complete distribution.

Publishing this project's source does not redistribute the developer's whole environment. The source repository excludes the KataGo binary, NVIDIA runtimes, the Ollama program, and models. Users who obtain those resources separately must follow their respective terms.

Each Windows installer must be audited against the files it **actually contains**, including Qt/FFmpeg, KataGo's bundled components, MSVC, OpenCV, NumPy, and models. Applicable copyright and license texts, corresponding source where required, and LGPL rights to replace shared libraries must be provided. The v1.0.0 materials and build manifest document this version's review; they cannot automatically cover future versions.
