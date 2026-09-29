# RecurGO Windows Installation Guide (v1.0.1)

English | [简体中文](INSTALL_WINDOWS.md)

This guide explains installation, dependencies, and first launch. For games, analysis, the library, and preferences, see the [User Manual](USER_GUIDE.en.md). Developers running from source should use the [source setup guide](SOURCE_SETUP.en.md).

## Setup at a glance

1. Install RecurGO and choose an installation directory and optional desktop shortcut.
2. Open **Analysis Environment Check** from the Start Menu.
3. Follow its results to supply any missing NVIDIA driver, CUDA, cuDNN, or Visual C++ runtime. If a component is already installed, try detection before reinstalling it.
4. Select **Save and check** and require a real KataGo analysis result. Then start RecurGO and use the [User Manual](USER_GUIDE.en.md) for daily operation.

## Before downloading

RecurGO v1.0.1 targets Windows 10/11 x64 with an NVIDIA GPU. Computers without an NVIDIA GPU are not yet supported. Other NVIDIA GPUs still need a successful real analysis check using the separate tool below.

Real KataGo analysis has passed on an NVIDIA GeForce RTX 5070 Ti Laptop GPU and an NVIDIA
GeForce RTX 2080 Ti. On the latter GPU, the main application also displayed candidate moves
and win rates. These results do not establish support for every NVIDIA GPU.

The bundled KataGo loads `cudnn64_9.dll`, so this build requires **cuDNN 9.x**; another major version cannot replace it. Auto-detection checks NVIDIA's standard `v9.*` installation folders and their subfolders, as well as `CUDNN_PATH` and `PATH`. For an installation elsewhere without those paths, select the actual DLL in the checker; reinstalling is unnecessary. If several 9.x versions coexist, use the selected folder shown by the tool and require a real KataGo check.

The installer contains RecurGO, the KataGo engine, analysis models, and application runtime components. You do not need to install Python, find KataGo models, or edit engine configuration. Prepare these additional components separately:

| Component | Location | Required? |
| --- | --- | --- |
| NVIDIA GPU driver | Installed in Windows; many NVIDIA systems already have one | Yes |
| CUDA 12.8 runtime and compatible cuDNN 9.x | Install with NVIDIA's official Windows installers, or extract the official ZIP files into the user data directory shown by the check tool | A working version is required; cuDNN 9.8 was verified, and 9.25.1 passed real analysis on an RTX 2080 Ti after manual selection. Check other combinations on the current machine. |
| Microsoft Visual C++ Redistributable x64 | Installed in Windows; an existing compatible version is sufficient | Required to start KataGo |
| Ollama and a language model | Optional, preferably under the user data directory described below | Only for supplemental local AI explanations |

Without Ollama, the board, KataGo analysis, win rates, candidates, review, and built-in immediate rules-based explanations should still work.

## Step 1: Install RecurGO

Download the separate **Windows x64** installer from the project's GitHub **Releases** page. Setup shows a destination page so you can choose another writable application directory. The default is `%LOCALAPPDATA%\Programs\RecurGO` for the current user; Python is not required. Games, settings, and downloaded runtimes remain under `%LOCALAPPDATA%\RecurGO` even if you select another application directory.

Download `SHA256SUMS.txt` from the same Release. In PowerShell, from the installer's folder,
run `Get-FileHash -Algorithm SHA256 -LiteralPath "actual-installer-filename.exe"` and compare
its hash with the entry for that file in `SHA256SUMS.txt`. If they differ, do not run it.
Get both files from the project's GitHub Release page, rather than a modified copy shared
elsewhere.

On setup's **Additional Tasks** page, you can select **Create a desktop shortcut**; it is unchecked by default. The optional RecurGO desktop shortcut uses the project character icon. You can still start the program from the Start Menu without one.

If a compatible Visual C++ runtime is absent, install the **x64** package from [Microsoft's official page](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist). The installer's KataGo engine directory does not separately copy Microsoft runtime DLLs from the development machine; the check tool inspects the system runtime.

GitHub's **Source code (zip)** and **Source code (tar.gz)** are automatically generated source archives for reading or developing the code. They are not installers. General users should choose the separately attached Windows installer.

## Step 2: Check the GPU driver

Open **Analysis Environment Check** from the Start Menu, or run `check_analysis_environment.cmd` in the installation directory. This entry opens the configuration window and reports whether the NVIDIA driver can be found and initialized. `RecurGO-Environment-Check.exe` is a command-line component used by the launcher, not the normal user entry point.

- Driver ready: continue; no driver reinstall is needed.
- Driver unavailable: install the correct driver for your GPU from the [official NVIDIA driver page](https://www.nvidia.com/en-us/drivers/). Restart Windows if the installer asks, then rerun the check.
- No NVIDIA GPU: computers without one are not yet supported.

The driver is installed in Windows, not placed in RecurGO's project folder. The main application has no driver or CUDA settings page; those operations belong in the separate tool.

## Step 3: Prepare CUDA and cuDNN

Choose one of these methods. **An EXE from the CUDA Toolkit page is expected:** run the installer. The fixed directories below are only for standalone ZIP files; do not place the EXE there.

1. **System installation:** Get the Windows x64 installers from NVIDIA's official [CUDA Toolkit 12.8 page](https://developer.nvidia.com/cuda-12-8-0-download-archive) and [cuDNN 9.8 page](https://developer.nvidia.com/cudnn-9-8-0-download-archive). Install CUDA 12.8 and cuDNN 9.8 for CUDA 12. The cuDNN installer does not replace the CUDA runtime or cuBLAS. Reopen the checker afterward. It searches NVIDIA's versioned directories, CUDA-version and architecture folders below `bin`, relevant environment variables, and `PATH`. Failure to auto-detect does not prove the libraries are uninstalled. Choose **Choose manually** and select the CUDA folder containing both `cublas64_12.dll` and `cudart64_12.dll`, plus the cuDNN folder actually containing `cudnn64_9.dll`. The latter can be deeper than `bin`, for example `bin\12.9\x64`.
2. **Standalone ZIP files:** In the separate tool, select **Open ZIP destination**. It creates and opens the runtime-library location. The tool displays both full target paths; use the paths it shows. Relative to the `%LOCALAPPDATA%\RecurGO` user data directory, the layout is:

```text
cuda_deps\nvidia\cuda\bin\    CUDA 12.8 runtime DLLs
cuda_deps\nvidia\cudnn\bin\   cuDNN 9.8 DLLs
```

For the ZIP method:

1. Download the **Windows x86_64, 12.8** archive from NVIDIA's [CUDA Runtime ZIP directory](https://developer.download.nvidia.com/compute/cuda/redist/cuda_cudart/windows-x86_64/) and the matching archive from the [cuBLAS ZIP directory](https://developer.download.nvidia.com/compute/cuda/redist/libcublas/windows-x86_64/). Extract both, then place the DLLs from their `bin` directories in the CUDA `bin` directory shown above.
2. Download the **cuDNN 9.8 for CUDA 12, Windows x86_64** ZIP from the [official NVIDIA archive](https://developer.nvidia.com/cudnn-9-8-0-download-archive). Extract it, then place the DLLs from its `bin` directory in the cuDNN `bin` directory above.

For the ZIP method, place extracted DLLs there, not unextracted ZIP files. With official installers, there is no need to copy DLLs into the fixed directories. Do not copy DLLs from another computer's system directories. Finding paths and DLL files does not establish compatibility: select **Save and check** and require a real KataGo analysis result.

The project has verified cuDNN 9.8. On the test machine with an NVIDIA GeForce RTX 2080 Ti, real KataGo analysis also passed after cuDNN 9.25.1 was selected manually. NVIDIA's [cuDNN 9.25.1 support matrix](https://docs.nvidia.com/deeplearning/cudnn/backend/v9.25.1/reference/support-matrix.html) lists CUDA 12.8 for its **CUDA 12.x** build. The 9.25.1 installer may place `cudnn64_9.dll` in a deeper folder such as `C:\Program Files\NVIDIA\CUDNN\v9.25\bin\12.9\x64`. The `12.9` part denotes the installed component's CUDA-version folder; finding a DLL alone does not establish compatibility with a local CUDA 12.8 installation. Let the checker find that exact folder, or choose it manually, then require a successful KataGo analysis on the current machine. That 9.25.1 test does not accept every installation method or machine.

## Step 4: Run a real check

In the separate tool, choose **Auto-detect (recommended)** and select **Detect again** after adding files. Detected CUDA and cuDNN folders appear in the path fields, and the results show which folders were selected. If several versions are installed, check the folder shown in the results; switch to manual mode to choose another. If auto-search does not find a component you already installed, select **CUDA installed? Select its DLL…** or **cuDNN installed? Select its DLL…** as appropriate. The tool switches to manual mode and immediately rechecks that folder. Browsing or entering a folder manually also updates the results, so an old auto-search miss does not remain on screen. Once both components' DLLs are found, select **Save and check**. An installation in a custom directory without `CUDNN_PATH` or `PATH` may require one manual selection.

The test must actually start KataGo and analyze a test position. Only a successful analysis means the analysis environment is ready. If it fails, inspect whether the tool reports a driver problem, a missing DLL, or an engine-start failure. Finding DLLs alone is not evidence that analysis works.

Run this check at first installation or after changing the GPU, driver, CUDA, or cuDNN. It is not needed on every main-program launch. If you change paths while RecurGO is open, close and reopen the main program before retrying analysis.

## Step 5: First launch

After the KataGo check succeeds, start RecurGO from the Start Menu or the optional desktop shortcut. Create a game and enable **Real-time analysis** to confirm that candidate moves and win rates appear on the right. The [User Manual](USER_GUIDE.en.md) covers play, analysis, the library, and analysis visits.

## Optional: use Ollama for supplemental explanations

Ollama is not included in the installer and is unnecessary for the preceding features. If you want it, the project-local setup is:

1. Download the Windows AMD64 CLI ZIP from the [official Ollama v0.34.3 release](https://github.com/ollama/ollama/releases/tag/v0.34.3). Extract its complete contents to `%LOCALAPPDATA%\RecurGO\ollama\v0.34.3\`; do not copy only `ollama.exe`.
2. Use the bundled **Start Optional Ollama** shortcut, then the **Download Ollama Model** shortcut to obtain `qwen3:4b-instruct-2507-q4_K_M`. The model is stored under `%LOCALAPPDATA%\RecurGO\ollama\models\`. Downloading it requires network access; wait until it finishes.
3. In RecurGO, open **Local AI Explanation Settings**, enable the feature, select **Detect local models**, choose the downloaded model, and save.

If no model is detected, check that Ollama is running and the model finished downloading. You may instead install Ollama through its [official Windows instructions](https://docs.ollama.com/windows); that installation manages its own files and models outside the directory above. Language-model explanations may be wrong. KataGo remains the authority for moves and win rates.

## Troubleshooting

| Symptom | Check first |
| --- | --- |
| No candidates after opening a board | Is Real-time analysis enabled? Run the separate Analysis Environment Check to see whether KataGo completes a real test. |
| Auto-detection does not find `cudart64_12.dll`, `cublas64_12.dll`, or `cudnn64_9.dll` | If you used NVIDIA installers, reopen the checker and manually choose the folders actually containing those DLLs, possibly beneath CUDA-version and `x64` folders below `bin`; do not download again. For ZIP files, confirm the extracted DLLs are in the displayed folders. A failed automatic search does not prove the libraries are uninstalled. |
| DLLs are found but analysis still fails | Read KataGo's original error from the tool, then check driver, CUDA/cuDNN versions, and GPU availability. |
| KataGo reports missing `msvcp140.dll` or `vcruntime140.dll` | Install Visual C++ Redistributable x64 from the Microsoft page above, then rerun the check tool. |
| Local AI gives no answer | Check Ollama service, completed model download, and model selection in Local AI Explanation Settings. KataGo analysis can still run without it. |

When reporting a problem, include the error text, Windows version, and GPU model after checking for private paths. Games, personal databases, and caches are local data. Do not upload entire data folders or private SGF files to a public issue.
