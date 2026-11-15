# Run from source (v1.2.0)

English | [简体中文](SOURCE_SETUP.md)

For everyday use after configuration, see the [user guide](USER_GUIDE.en.md).

The currently reproducible development setup is **Windows x64 + Python 3.13 + KataGo's CUDA 12.8 backend**. This is not a compatibility guarantee for other hardware. Automatic OpenCL/CPU selection, an initial setup wizard, and a standalone portable package remain unimplemented.

## Python environment

In the extracted or cloned project directory, run:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

This editable installation lets the application find `runtime/` and `data/` relative to the source directory. Dependencies are pinned in `pyproject.toml`. Create `.venv/` locally; it is not part of the Git source.

## Prepare KataGo (TF3 by default)

The v1.2.0 TF3 and B28 installers offer the same application features; installation users can choose one using the [installation guide](INSTALL_WINDOWS.en.md). Source configuration still defaults to TF3. Building B28 does not replace the project's existing `runtime/`. To run B28 from source, use the separate configuration described below.

Get `katago-v1.18.2-cuda12.8-cudnn9.8.0-windows-x64.zip` from the [official KataGo v1.18.2 release](https://github.com/lightvector/KataGo/releases/tag/v1.18.2). Use the standard board build, not `+bs50`, and retain its required runtime libraries and license materials. The setup also needs CUDA 12.8, NVRTC, and cuDNN 9.x. Tests with the earlier engine do not establish TF3 acceptance; require real model loading and analysis on the current machine. Install the NVIDIA driver in Windows. Project-level runtime libraries can be placed in the fixed directories below; do not copy system directories from another computer.

The main application does not run a separate environment precheck. To set CUDA/cuDNN paths and perform a real KataGo test, run `check_analysis_environment.cmd` from the project root.

Get the main model from the [official KataGo network directory](https://katagotraining.org/networks/) and Human SL from the [extra networks directory](https://katagotraining.org/extra_networks/):

- `kata1-tf3-b11c768-s11003M-d5973M-7gres.bin.gz`
- `b18c384nbt-humanv0.bin.gz`

The files and checked SHA-256 hashes are listed in the [model notes](../licenses/models/README.md). The current runtime loader requires both files, even if users only use the Strongest difficulty. TF3 names the main-model family, not the engine version; prepare it together with the v1.18.2 engine.

Suggested layout:

```text
runtime/
  engine/katago.exe             # Keep engine-dependent DLLs alongside it
  models/                      # Both models listed above
  configs/analysis.cfg
  runtime.local.json
  cuda_deps/nvidia/cuda/bin/    # CUDA 12.8 runtime DLLs
  cuda_deps/nvidia/cudnn/bin/   # cuDNN 9.8 runtime DLLs
  ollama/v0.34.3/ollama.exe     # Optional; extracted from official CLI ZIP
data/logs/katago/
```

For a new setup, copy `docs/setup/runtime.example.json` to `runtime/runtime.local.json` and `docs/setup/analysis.example.cfg` to `runtime/configs/analysis.cfg`. Create the target directories first. Compare existing configurations before replacing anything.

The fixed CUDA directory needs matching 12.8 runtime libraries such as `cublas64_12.dll` and `cudart64_12.dll`. Obtain matching releases from NVIDIA's [CUDA Runtime ZIP directory](https://developer.download.nvidia.com/compute/cuda/redist/cuda_cudart/windows-x86_64/) and [cuBLAS ZIP directory](https://developer.download.nvidia.com/compute/cuda/redist/libcublas/windows-x86_64/), extract them, and put their `bin` DLLs in the CUDA `bin` directory shown above. Obtain the Windows 9.8 ZIP for CUDA 12 from the [NVIDIA cuDNN archive](https://developer.nvidia.com/cudnn-archive), extract it, and put its `bin` DLLs in the cuDNN `bin` directory. These are **extracted runtime libraries**, not an installer EXE or an unextracted ZIP. A regular CUDA Toolkit installation following NVIDIA's instructions can also be found by the separate detection tool.

For standalone ZIP setup, also obtain the matching CUDA 12.8 component from NVIDIA's [NVRTC ZIP directory](https://developer.download.nvidia.com/compute/cuda/redist/cuda_nvrtc/windows-x86_64/). Keep its main NVRTC DLL and `nvrtc-builtins` DLL together from the same archive. A complete CUDA Toolkit 12.8 installation normally supplies this component.

Run `check_analysis_environment.cmd`, choose automatic detection, and select Save and Test. The tool checks the NVIDIA driver in Windows, then the fixed directories, existing manifest, system installation, and `PATH`, and finally runs KataGo. If automatic detection fails, choose manual paths to the folders actually containing the required DLLs. Manual paths are saved in a separate local configuration under `data/`; the main program reads them after a restart.

Real-time and full-game analysis visits can be changed from Analysis Settings in the main toolbar or **Menu → Analysis → Analysis settings** in a narrow window. The default is 800 visits. Editing `maxVisits` in the configuration file does not override visits sent by the interface.

The sample analysis settings come from the single NVIDIA GPU baseline already in use; only the log location was changed to a relative path. They are not claimed to suit every computer or define a universal Strongest setting. The application uses its existing search budgets. If video memory is insufficient or the backend does not match, record the error and adjust installation plans rather than reducing search quality as a compatibility fix.

Create `data/logs/katago/` before starting, then run from the project root:

```powershell
.\.venv\Scripts\python.exe scripts\probe_qt_engine.py
.\.venv\Scripts\python.exe -m recurgo.app
```

You may run `check_analysis_environment.cmd` once to configure paths and perform an independent analysis test. It is not needed every time the main program starts. Run it again if you change the GPU driver, CUDA/cuDNN, or models.

If the engine is not configured, the main program displays a startup error; the board and game records still open, which does not mean AI analysis is available. The separate diagnostic tool reports missing items, performs a real analysis, and writes local logs.

## Choose B28 when running from source

B28 uses the previously released combination of **KataGo 1.16.5 + `kata1-b28c512nbt-s13255194368-d5935380940.bin.gz`**. Human SL remains `b18c384nbt-humanv0.bin.gz`. Application features are the same, but analysis results need not match; the current machine must still pass the separate environment check.

Use a separate source working directory to preserve the existing TF3 development setup. Copy the [B28 configuration example](setup/runtime.b28.example.json) to that directory's `runtime/runtime.local.json`, and verify these explicit paths and SHA-256 values. Engine-dependent DLLs alongside the executable must also match the [B28 asset lock](../packaging/asset_lock.b28.json). Replacing only the model or retaining TF3's engine hash is insufficient:

| Path inside the B28 working directory | SHA-256 |
| --- | --- |
| `runtime/engine/katago.exe` | `60275844632567e8ccb2d1fc5080c3205cf0f78fe2b57d12bce07f3a5f167f8e` |
| `runtime/models/kata1-b28c512nbt-s13255194368-d5935380940.bin.gz` | `c5bca453d7b08ea8df6546439325d4dd681e77d975e1da3f7593d771147b73bc` |
| `runtime/models/b18c384nbt-humanv0.bin.gz` | `637746e44f0efe00ad1245a50aa9bbf0716efe364c43965ead97bd6835d84ab5` |

Set `analysisConfig` explicitly to `runtime/configs/analysis.cfg`, using the current project's analysis configuration with `requireMaxBoardSize=false` and 9/13/19-board support. Do not replace the current search configuration with one from an old installer. B28's CUDA list requires `cublas64_12.dll` and `cudart64_12.dll`, plus matching cuDNN 9.x; it does not require the two NVRTC DLLs in TF3's manifest. Then run the environment check and launch commands above. The loader uses explicit manifest paths and hashes; it does not scan for another model or fall back automatically.

If you only need to build a B28 installer, leave the default source runtime manifest unchanged and pass a project-local `--b28-source-root` to the builder; see the [build guide](BUILD_WINDOWS.en.md). Both installers use the current project's `runtime/configs/analysis.cfg`; the older source root supplies only the matching engine, models, and path manifest.

## Optional local language model

Rules-based candidate explanations do not require Ollama. Language-model text only adds an explanation; it cannot change KataGo's move ranking. Prepare Ollama and a model separately as described in the [local AI guide](OLLAMA_LOCAL.en.md).

## Data and publication boundary

By default, game records, analysis caches, and settings live in `data/`. `RECURGO_DATA_DIR` can set another data location. If you put data elsewhere inside the project, also add that location to the ignore rules. Exported SGF files may contain player names and comments.

`.gitignore` excludes all of `runtime/`, `data/`, and `.venv/`. A source release should retain this guide, example configurations, `LICENSE`, `THIRD_PARTY_NOTICES.md`, and `licenses/`. Ignore rules do not govern manual copying or archives made from the whole project directory.
