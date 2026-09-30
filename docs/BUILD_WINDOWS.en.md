# Windows installer build guide (v1.0.1)

English | [简体中文](BUILD_WINDOWS.md)

This is for maintainers building a local installer candidate. One formal version has one public source snapshot and one Windows x64 installer; GitHub's source ZIP/TAR files are automatic snapshots of the tag, not a separate application to maintain. Building and hashing are local and do not upload to GitHub.

## Inputs

- Windows 10/11 x64, Python 3.13, and the project's `.venv` with pinned dependencies including the `dev` group, as described in the [source setup guide](SOURCE_SETUP.en.md).
- `ISCC.exe` from the [official Inno Setup page](https://jrsoftware.org/isdl.php). The script invokes the compiler; Inno Setup itself is not committed or bundled for users.
- KataGo 1.16.5 CUDA engine, main model, Human SL model, and `runtime/runtime.local.json` as described in the [source setup guide](SOURCE_SETUP.en.md). Binaries and models remain outside Git.
- `packaging/asset_lock.json` lists the nine approved assets and their SHA-256 values. A mismatch stops the build. Review license, source, hashes, and behavior before explicitly updating the lock for a new upstream version.
- Local Git must be available. The builder copies only tracked `licenses/` files and stops if that directory contains extras.
- The selected desktop-shortcut artwork is kept at `assets/recurgo-icon-artwork.png`. A version with only the four corners geometrically clipped to transparency is at `assets/recurgo-icon-artwork-rounded.png`; the multi-size Windows icon is at `src/recurgo/assets/recurgo.ico`. The build copies only the ICO into the installation directory for the optional desktop shortcut. Neither PNG is installed, and the program and installer retain their existing icons.
- The local Inno Setup 7 compiler displays “Non-commercial use only.” Its [official commercial-license Q&A](https://jrsoftware.org/isorder.php) considers commercial use and revenue, and says purchase is not strictly required. The message alone does not establish a block on this personal open-source release.

## Build

From the project root:

```powershell
.\.venv\Scripts\python.exe scripts\build_windows_release.py --iscc "C:\path\to\ISCC.exe"
```

Each run creates a new `build/release-.../` directory without overwriting earlier artifacts. `stage/RecurGO/` is the installation file tree; `file-manifest.json` records the size and SHA-256 of every staged file; `output/` contains the installer and `SHA256SUMS.txt`. Git ignores `build/`.

The candidate includes RecurGO and Python/Qt runtime components, KataGo, both models, analysis configuration, a separate environment checker, optional Ollama launch and model download entry points, bilingual guides, and license materials. It excludes developer games/databases, CUDA/cuDNN, the Ollama program, and language models. Users obtain the NVIDIA driver and CUDA/cuDNN from NVIDIA; optional Ollama comes from its official source.

User data and user-supplied libraries live under `%LOCALAPPDATA%\RecurGO`; the default application location is `%LOCALAPPDATA%\Programs\RecurGO`. Setup always shows the destination page. The installer's KataGo engine directory does not copy developer-machine Microsoft Visual C++ DLLs. The independent checker examines the system runtime and links to Microsoft. Binary components brought in by upstream Python, Qt, and NumPy packages still require redistribution review against the actual manifest.

## Versioning and publication

The current formal version is **v1.0.1**. Keep `pyproject.toml`, `src/recurgo/__init__.py`, the installer filename, Git tag, and GitHub Release title consistent. Rebuild from final source; renaming a development installer does not make a formal release. The complete release text requires explicit user approval before publication or edits to public content. See the [v1.0.1 verification record](RELEASE_1.0.1.md) for behavior, validation limits, and publication steps.

Compiling an installer only establishes that an installation file was produced. For each later version, check installation, independent checks, real KataGo analysis, play, games, review, both languages, and optional Ollama, and review source and installer privacy, third-party licenses, LGPL corresponding source, and shared-library replacement. The [first-release design record](RELEASE_TARGET.en.md) describes the acceptance scope. Do not upload all of `build/`; attach the installer and checksum file to the GitHub Release for the same version.
