# Local portable Ollama service (RecurGO v1.0.0)

English | [简体中文](OLLAMA_LOCAL.md)

Installer users should first read the optional Ollama section of the
[Windows installation guide](INSTALL_WINDOWS.en.md). The launch entries are in the Start Menu,
and Ollama files and models belong under `%LOCALAPPDATA%\RecurGO\ollama`. The project-relative
paths and `run_recurgo_with_ollama.cmd` steps below are primarily for source mode.

The project script manages an isolated Ollama CLI service inside the project. The client and UI are integrated and have passed automated checks against a simulated service. The official program was checked and started; the local API version was 0.34.3. The selected model's SHA-256 was checked and the model imported successfully. One short response from the local API was verified. Full-game explanation time, output quality, and VRAM sharing with KataGo have not been accepted and still require a user-run check.

## Use in the interface

After preparing the program and model, run `run_recurgo_with_ollama.cmd`. In the toolbar, open Local AI Explanation Settings, enable local explanations, detect and select a model, and save. In a narrow window, use **Menu → Analysis → Local AI explanation settings** instead. This optional setting is off by default and stored in the local database. If the main program is already open, start the Ollama service separately with `start_optional_ollama.cmd`. It calls the same `scripts/ollama_local.ps1` and uses the fixed directories and isolation described below.

English is the default. To use Simplified Chinese, select it under Preferences → Language / 语言 and choose OK. The interface switches immediately, and new requests use the selected language for the system prompt and rule evidence. Confirm the actual model's language from a live response; the prompt alone cannot guarantee it.

When KataGo data arrives, a rules-based explanation updates immediately. Once the full search has stabilized, the program automatically requests a supplemental model explanation and displays streamed text. Changing the candidate, position, or game cancels the old request so a reply cannot be shown for another move. Cancel stops the current supplement; Generate again requests another. Fair play does not show analysis explanations.

New KataGo searches and full-game review have priority; model requests are cancelled or wait. Each completed generation requests that the model unload to reduce resident VRAM, so the next request may need to load it again. Immediate rules-based explanations never wait for Ollama.

The client accepts only local HTTP addresses and rejects recognizable cloud models using their names and metadata returned by the local service. This cannot prove that an untrusted local service or third-party model will not forward requests. Connect only to an Ollama service you trust and use a local model from a checked source. The prompt includes the board, candidate, reference variation, and rule evidence; it omits player names, SGF comments, and local paths. Model text can be inaccurate. It cannot change KataGo's ranking or establish life and death, ladders, or inevitable results.

## Files and data locations

- Executable: `runtime/ollama/v0.34.3/ollama.exe`, extracted from the checked official Windows AMD64 CLI ZIP.
- Models: `runtime/ollama/models/`.
- Keys and user configuration: `runtime/ollama/profile/.ollama/`; application data is under that profile's `AppData/`.
- Temporary files, logs, and CUDA cache: `runtime/ollama/tmp/`, `logs/`, and `cuda-cache/`.
- Service record: `runtime/ollama/service.json`, containing PID, process start time, executable path, and network mode.

These directories contain local data and third-party assets. Do not add them to a source commit or open-source package. The script refuses project-local directory junctions or symbolic links that would redirect its writes elsewhere.

Each child process temporarily sets `USERPROFILE`, `LOCALAPPDATA`, `APPDATA`, `TEMP`, `TMP`, `TMPDIR`, `CUDA_CACHE_PATH`, and `OLLAMA_MODELS`; the calling process's environment is restored afterwards. It does not modify `HOME`, `CODEX_HOME`, or persistent user/system environment variables. It does not install a Windows service or startup item.

## Commands

Run from the project directory in Windows PowerShell 5.1 or PowerShell 7:

```powershell
.\scripts\ollama_local.ps1 -Action Status
.\scripts\ollama_local.ps1 -Action Start
.\scripts\ollama_local.ps1 -Action Pull
.\scripts\ollama_local.ps1 -Action Stop
```

`Start` runs `ollama serve` in the background, listening only on `127.0.0.1:11434`. Stdout and stderr go to separate new log files with timestamps and random identifiers. Ending the launch script does not stop the service; use `Stop` when needed. `Status` is read-only and does not create runtime directories.

Before stopping the service and its child processes, `Stop` checks PID, actual executable path, and process start time, avoiding another Ollama installation. If another process holds the port, `Start` reports the conflict without taking over the port or stopping that process. PID records may be updated; old records, models, and logs are not deleted.

The default model is `qwen3:4b-instruct-2507-q4_K_M`. Use `-Model` for another confirmed full tag. `Pull` uses this project's running service. Its progress comes from Ollama's CLI; the wrapper cannot independently observe the entire download byte stream.

## Direct connection and explicit proxy

The service and CLI use a direct connection by default: the child process clears `HTTP_PROXY`, `HTTPS_PROXY`, and `ALL_PROXY`, and sets `NO_PROXY=*`. Local API checks always bypass a proxy.

Only after a direct connection fails or is unusually slow should an existing valid `HTTP_PROXY` or `HTTPS_PROXY` in the current PowerShell process be used explicitly:

```powershell
.\scripts\ollama_local.ps1 -Action Stop
.\scripts\ollama_local.ps1 -Action Start -UseProxy
.\scripts\ollama_local.ps1 -Action Pull -UseProxy
```

The `serve` process performs model downloads. Adding `-UseProxy` to `Pull` alone cannot change a service that was started without it; the script checks that both modes match and does not restart the service automatically. Proxy addresses are not written to the state file. Proxy-mode `NO_PROXY` still includes `127.0.0.1`, `localhost`, and `::1`. To restore a direct connection, run `Stop`, then `Start` without `-UseProxy`.

## Model, API, and verification limits

The recommended tag was confirmed in the official registry. Its model and auxiliary layers total about **2.326 GB**, it uses Q4_K_M quantization, and its license is Apache-2.0. `qwen3:4b-instruct-2507` alone is not an available tag. The bare `qwen3:4b` currently points to a Thinking model and is not used as this default.

- Manifest SHA-256: `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`.
- Model blob SHA-256: `85e4a5b7b8ef0e48af0e8658f5aaab9c2324c76c1641493f4d1e25fce54b18b9`.
- [Ollama model tag](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M).
- [Official Qwen model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507): this variant supports non-thinking mode only.

The service sets `OLLAMA_NO_CLOUD=1`, `OLLAMA_NOHISTORY=1`, and `OLLAMA_DEBUG_LOG_REQUESTS=false`, and limits simultaneously loaded models and parallel requests to one each. Downloading a model still requires the network; disabling cloud features does not disable model downloads. `OLLAMA_NOPRUNE=1` prevents automatic blob pruning at startup.

After downloading, `scripts/probe_ollama.py` can check the real KataGo → automatic local explanation flow. It writes a report under a new `data/verification/ollama-*` directory and does not use the personal game database. Time to first text and completion are measured from the client request, including model checks and generation but excluding KataGo search and UI waiting. Rule calculation time is not full UI latency. Only a successful API response, a complete reply in the UI, and a check of input facts can establish local generation acceptance.

Download size is not VRAM use. Do not reduce KataGo visits, switch to a weaker analysis model, or change the top-recommendation rule to free resources for Ollama.

The script redirects known application data and CUDA JIT cache paths. Environment isolation is not a filesystem sandbox and cannot prove Windows or the GPU driver writes no additional system records.

## Upstream references

- [Ollama v0.34.3](https://github.com/ollama/ollama/releases/tag/v0.34.3), [Windows CLI instructions](https://docs.ollama.com/windows).
- Official ZIP SHA-256: `306ce9e81e3491d147f558e60d7a389499f244d10f71859c6e4e899241d1b4ae`; [checksum file](https://github.com/ollama/ollama/releases/download/v0.34.3/sha256sum.txt).
- [Key initialization on serve](https://github.com/ollama/ollama/blob/v0.34.3/cmd/cmd.go#L2101), [model and environment settings](https://github.com/ollama/ollama/blob/v0.34.3/envconfig/config.go#L111), [service log initialization](https://github.com/ollama/ollama/blob/v0.34.3/server/routes.go#L1969).
- [Chat API](https://docs.ollama.com/api/chat), [CUDA cache environment variable](https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/environment-variables.html).
