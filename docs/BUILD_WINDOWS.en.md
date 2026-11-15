# Windows installer build guide (v1.2.0)

English | [简体中文](BUILD_WINDOWS.md)

This is for maintainers building local installer candidates. The same v1.2.0 source snapshot produces TF3 and B28 Windows x64 installers with the same application features; users install one. GitHub's source ZIP/TAR files are automatic snapshots of the tag, not a separate application to maintain. Building and hashing are local and do not upload to GitHub.

## Inputs

- Windows 10/11 x64, Python 3.13, and the project's `.venv` with pinned dependencies including the `dev` group, as described in the [source setup guide](SOURCE_SETUP.en.md).
- `ISCC.exe` from the [official Inno Setup page](https://jrsoftware.org/isdl.php). The script invokes the compiler; Inno Setup itself is not committed or bundled for users.
- The default TF3 build uses the project's existing KataGo 1.18.2 CUDA engine, TF3 main model, Human SL model, and `runtime/runtime.local.json`, as described in the [source setup guide](SOURCE_SETUP.en.md). Binaries and models remain outside Git.
- For B28, provide a separate source root inside the project containing `runtime/bundle.json` or `runtime/runtime.local.json`, plus `runtime/engine/` and `runtime/models/`. Use the previously released combination of KataGo 1.16.5 and `kata1-b28c512nbt-s13255194368-d5935380940.bin.gz`, with the same Human SL model as TF3. The root must be a real project-local directory, not a link outside the project, and separate from the default TF3 `runtime/`.
- Runtime asset locks record each variant's paths, complete engine file set, and model SHA-256 allowlist: TF3 uses `packaging/asset_lock.json`; B28 uses `packaging/asset_lock.b28.json`. Paths, the complete file set, and hashes must agree. A mismatch stops the build. Review license, source, hashes, and behavior before explicitly updating the corresponding lock for a new upstream version.
- Local Git must be available. The builder copies only tracked `licenses/` files and stops if that directory contains extras.
- The selected desktop-shortcut artwork is kept at `assets/recurgo-icon-artwork.png`. A version with only the four corners geometrically clipped to transparency is at `assets/recurgo-icon-artwork-rounded.png`; the multi-size Windows icon is at `src/recurgo/assets/recurgo.ico`. The build copies only the ICO into the installation directory for the optional desktop shortcut. Neither PNG is installed, and the program and installer retain their existing icons.
- The local Inno Setup 7 compiler displays “Non-commercial use only.” Its [official commercial-license Q&A](https://jrsoftware.org/isorder.php) considers commercial use and revenue, and says purchase is not strictly required. The message alone does not establish a block on this personal open-source release.

## Build

From the project root:

```powershell
.\.venv\Scripts\python.exe scripts\build_windows_release.py --iscc "C:\path\to\ISCC.exe"
```

Omitting `--variant` defaults to `tf3`. To generate both packages, provide a B28 source root inside the project; the path names the directory containing `runtime/`, not `runtime/` itself:

```powershell
.\.venv\Scripts\python.exe scripts\build_windows_release.py --variant all --b28-source-root "build\b28-source" --iscc "C:\path\to\ISCC.exe"
```

`--variant b28` builds only B28 and also requires `--b28-source-root`; `--variant tf3` builds only TF3. `all` freezes the application once and stages each runtime separately. It does not modify the existing TF3 `runtime/` or the B28 source files.

Both packages use the current project's `runtime/configs/analysis.cfg`, changing only the log location in staging to a relative path. The older configuration in the B28 source root is not packaged. Current search settings, `requireMaxBoardSize=false`, and 9/13/19-board support remain intact.

Each run creates a new `build/release-.../` directory without overwriting earlier artifacts. `stage/TF3/RecurGO/` and `stage/B28/RecurGO/` contain the installation trees. The corresponding `file-manifest-TF3.json` and `file-manifest-B28.json` record every staged file's size and SHA-256. Only selected variants are staged. `output/` contains their installers and one combined `SHA256SUMS.txt`:

- `RecurGO-1.2.0-TF3-Windows-x64-Setup.exe`
- `RecurGO-1.2.0-B28-Windows-x64-Setup.exe`

Git ignores `build/`.

The candidate includes RecurGO and Python/Qt runtime components, KataGo, both models, analysis configuration, a separate environment checker, optional Ollama launch and model download entry points, bilingual guides, and license materials. It excludes developer games/databases, CUDA/cuDNN, the Ollama program, and language models. Users obtain the NVIDIA driver and CUDA/cuDNN from NVIDIA; optional Ollama comes from its official source.

User data and user-supplied libraries live under `%LOCALAPPDATA%\RecurGO`; the default application location is `%LOCALAPPDATA%\Programs\RecurGO`. Setup always shows the destination page. The installer's KataGo engine directory does not copy developer-machine Microsoft Visual C++ DLLs. The independent checker examines the system runtime and links to Microsoft. Binary components brought in by upstream Python, Qt, and NumPy packages still require redistribution review against the actual manifest.

Both packages share one AppId, default application directory, and user data directory. Close RecurGO and install the other package over the existing directory to switch without uninstalling. There are no `InstallDelete` cleanup rules; existing models, DLLs, and user files are not proactively removed. The selected package updates its bundled application, engine, and runtime manifest. Games, preferences, and saved analysis remain; analysis sources are kept separate and results need not match. Building the installer does not run it or modify directories outside the project.

## Versioning and publication

The current formal version is **v1.2.0**. Keep `pyproject.toml`, `src/recurgo/__init__.py`, the installer filename, Git tag, and GitHub Release title consistent. Rebuild from final source; renaming a development installer does not make a formal release. The complete release text requires explicit user approval before publication or edits to public content. See the [v1.0.1 verification record](RELEASE_1.0.1.md) for behavior, validation limits, and publication steps.

Compiling an installer only establishes that an installation file was produced. For both variants of each version, separately check installation, switching in both directions, independent checks, real KataGo analysis, play, games, review, both languages, and optional Ollama. Review source and installer privacy, third-party licenses, LGPL corresponding source, and shared-library replacement; this does not establish compatibility with every device. The [first-release design record](RELEASE_TARGET.en.md) describes the acceptance scope. Do not upload all of `build/`; attach both installers and the combined checksum file to the GitHub Release for the same version.
