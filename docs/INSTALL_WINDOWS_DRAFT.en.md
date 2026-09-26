# RecurGO Windows installation and usage (superseded draft v0.4)

English | [简体中文](INSTALL_WINDOWS_DRAFT.md)

> **Superseded draft. Do not follow the steps below for installation.** Use the current [Windows installation guide](INSTALL_WINDOWS.en.md), or the [source setup guide](SOURCE_SETUP.en.md) if running from source.

## Before downloading

The first installer is planned for Windows x64 with an NVIDIA GPU. Computers without an NVIDIA GPU are outside this initial target. Other NVIDIA GPUs still need a successful real analysis check using the separate tool below.

The installer is intended to contain RecurGO, the KataGo engine, analysis models, and application runtime components. Users should not need to install Python, find KataGo models, or edit engine configuration. Additional components fall into two groups:

| Component | Location | Required? |
| --- | --- | --- |
| NVIDIA GPU driver | Installed in Windows; many NVIDIA systems already have one | Yes |
| CUDA 12.8 runtime and cuDNN 9.8 | Obtain from NVIDIA; put extracted files in the indicated project directories, or use a compatible system installation | A working version is required |
| Ollama and a language model | Optional, preferably under the indicated project directory | Only for supplemental local AI explanations |

Without Ollama, the board, KataGo analysis, win rates, candidates, review, and built-in immediate rules-based explanations should still work.

## Step 1: Install RecurGO

After release, download the separate **Windows x64** installer from the project's GitHub **Releases** page, run it, and follow the prompts.

GitHub's **Source code (zip)** and **Source code (tar.gz)** are automatically generated source archives for reading or developing the code. They are not installers. General users should choose the separately attached Windows installer.

## Step 2: Check the GPU driver

Open the separate **Analysis Environment Check** tool bundled with the installer. It should report whether the NVIDIA driver can be found and initialized.

- Driver ready: continue; no driver reinstall is needed.
- Driver unavailable: install the correct driver for your GPU from the [official NVIDIA driver page](https://www.nvidia.com/en-us/drivers/). Restart Windows if the installer asks, then rerun the check.
- No NVIDIA GPU: the first Windows installer is not intended for this computer.

The driver is installed in Windows, not placed in RecurGO's project folder. The main application has no driver or CUDA settings page; those operations belong in the separate tool.

## Step 3: Prepare CUDA and cuDNN files

In the separate tool, select **Open fixed directory**. It is intended to create and open the runtime-library location. The tool should display both full target paths; use the paths it shows. Relative to the installation location, the proposed layout is:

```text
runtime\cuda_deps\nvidia\cuda\bin\    CUDA 12.8 runtime DLLs
runtime\cuda_deps\nvidia\cudnn\bin\   cuDNN 9.8 DLLs
```

1. Download the **Windows x86_64, 12.8** archive from NVIDIA's [CUDA Runtime ZIP directory](https://developer.download.nvidia.com/compute/cuda/redist/cuda_cudart/windows-x86_64/) and the matching archive from the [cuBLAS ZIP directory](https://developer.download.nvidia.com/compute/cuda/redist/libcublas/windows-x86_64/). Extract both, then place the DLLs from their `bin` directories in the CUDA `bin` directory shown above.
2. Download the **cuDNN 9.8 for CUDA 12, Windows x86_64** ZIP from the [official NVIDIA archive](https://developer.nvidia.com/cudnn-9-8-0-download-archive). Extract it, then place the DLLs from its `bin` directory in the cuDNN `bin` directory above.

Put the extracted DLLs there, not an unextracted ZIP or a CUDA installer EXE. Do not copy DLLs from another computer's system directories. If a compatible CUDA/cuDNN installation is already present, the check tool should try to find it automatically. For another location, choose **Manual paths** and select the actual `bin` directory for each component.

## Step 4: Run a real check

In the separate tool, choose **Automatic detection (recommended)** and select **Detect again** after adding files. It should show separately what it found for CUDA and cuDNN. Then select **Save and Test**.

The test must actually start KataGo and analyze a test position. Only a successful analysis means the analysis environment is ready. If it fails, inspect whether the tool reports a driver problem, a missing DLL, or an engine-start failure. Finding DLLs alone is not evidence that analysis works.

Run this check at first installation or after changing the GPU, driver, CUDA, or cuDNN. It is not needed on every main-program launch. If you change paths while RecurGO is open, close and reopen the main program before retrying analysis.

## Step 5: Start the program and adjust analysis visits

Start RecurGO, open or create a game, and enable **Real-time analysis** to see KataGo candidate moves, win rates, and explanations. Full-game review can be used when needed.

Visits are configurable through **Analysis Settings** → **Visits per position** → Save. The current default is **800 visits**. Higher values usually take longer; lower values can make the search insufficient. This setting affects subsequent real-time analysis and full-game review, not the separate Strongest play budget. Previously saved results do not become results from the new budget when the setting changes; analyze again if needed.

## Optional: use Ollama for supplemental explanations

Ollama is not planned to be included in the installer and is unnecessary for the preceding features. If you want it, the proposed project-local setup is:

1. Download the Windows AMD64 CLI ZIP from the [official Ollama v0.34.3 release](https://github.com/ollama/ollama/releases/tag/v0.34.3). Extract its complete contents to `runtime\ollama\v0.34.3\` under the installation location; do not copy only `ollama.exe`.
2. Use the planned **Start local Ollama** entry point, then the planned model download entry point to obtain `qwen3:4b-instruct-2507-q4_K_M`. The model should be stored under `runtime\ollama\models\`. Downloading it requires network access; wait until it finishes.
3. In RecurGO, open **Local AI Explanation Settings**, enable the feature, select **Detect local models**, choose the downloaded model, and save.

If no model is detected, check that Ollama is running and the model finished downloading. You may instead install Ollama through its [official Windows instructions](https://docs.ollama.com/windows); that installation manages its own files and models outside the proposed project directory. Language-model explanations may be wrong. KataGo remains the authority for moves and win rates.

## Troubleshooting

| Symptom | Check first |
| --- | --- |
| No candidates after opening a board | Is Real-time analysis enabled? Run the separate Analysis Environment Check to see whether KataGo completes a real test. |
| The check reports `cudart64_12.dll`, `cublas64_12.dll`, or `cudnn64_9.dll` missing | Did you download and extract the matching Windows ZIPs, and place their `bin` DLLs in the paths shown by the tool? |
| DLLs are found but analysis still fails | Read KataGo's original error from the tool, then check driver, CUDA/cuDNN versions, and GPU availability. |
| Local AI gives no answer | Check Ollama service, completed model download, and model selection in Local AI Explanation Settings. KataGo analysis can still run without it. |

When reporting a problem, include the error text, Windows version, and GPU model after checking for private paths. Games, personal databases, and caches are local data. Do not upload entire data folders or private SGF files to a public issue.
