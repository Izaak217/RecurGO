# First public Windows installer target (pre-release design record)

English | [简体中文](RELEASE_TARGET.md)

This document preserves the initial design target and acceptance checklist; it does not claim that every item below has been verified on every machine. The first public version is **v1.0.0**; the earlier `v0.2.0.dev30` build was only for internal testing. For current installation steps, verified scope, and downloads, use the [Windows Installation Guide](INSTALL_WINDOWS.en.md), [User Manual](USER_GUIDE.en.md), and matching Release.

## What users should receive

GitHub should host a public source repository and, under a Release with the same version number, a separate Windows x64 installer. GitHub-generated `Source code (zip/tar.gz)` files are snapshots of that version's source. They are not a second application and do not replace the installer. The installer should be built from the same source and include required application runtime components, the KataGo engine, two fixed models, analysis configuration, instructions, and applicable license materials.

The source repository should not include models, runtime libraries, or the developer's `runtime/` directory. Those fixed assets belong only in a separately audited installer. The developer's games, databases, caches, logs, secrets, and machine-specific paths must be absent from both source and installer. Build from a clean release directory, not by zipping the current development directory.

## Intended behavior after installation

1. The user installs and starts RecurGO without installing Python or Qt or locating KataGo models.
2. The main application reads paths saved by a separate environment tool; it has no environment settings page or independent precheck.
3. A separate Analysis Environment Check tool is bundled. It checks the Windows NVIDIA driver and KataGo's direct Visual C++ runtime dependencies, then first searches the user-supplied libraries under `%LOCALAPPDATA%/RecurGO/cuda_deps/nvidia/{cuda,cudnn}/bin`. Users may select other CUDA/cuDNN locations. They run the tool after first setup or an environment change. It must actually start the bundled KataGo and analyze a test position, reporting analysis ready only after receiving a valid candidate. Missing dependencies should be listed with official source links. Daily application launches need no repeat test.
4. Existing board, play, real-time analysis, game library, SGF import/export, and full-game review remain available. The main KataGo model, Human SL model, and recommendation ranking rules remain unchanged. Packaging should not redesign existing displays such as the candidate table.
5. The Analysis Settings toolbar entry shows visits per position, initially 800. Users may save another value for subsequent real-time analysis and full-game review. Historical caches are separated by visits; old results must not be presented as if computed under the new budget. Lower visits must be described as potentially insufficient. Strongest play retains its separate search budget.
6. Games, analysis caches, and personal settings are written to a writable per-user Windows data directory, not the installation directory. Updating the application should not overwrite personal data; the application must not upload it to GitHub.
7. Ollama stays off by default and is not bundled. Users who want supplemental language-model explanations may obtain an official CLI ZIP and place it under the user data directory's `ollama/` path, or use the official installer. Ollama manages its models. Users then enable the existing local AI explanation setting. Immediate rules-based explanations and all KataGo features remain available without Ollama.

## Initial support boundary

The target is **Windows x64 with an NVIDIA CUDA 12.8 backend**. End-to-end operation has been verified with an NVIDIA GeForce RTX 5070 Ti Laptop GPU and approximately 12 GB of VRAM. On a separate machine with an NVIDIA GeForce RTX 2080 Ti, the independent tool passed a real KataGo analysis and the application displayed candidate moves and win rates. The remaining features have not all been accepted on the RTX 2080 Ti, and these two GPU results do not establish support for every NVIDIA GPU. AMD, Intel, CPU, and other KataGo backends are outside the initially verified scope. Users obtain NVIDIA drivers and CUDA/cuDNN from official sources appropriate to their machines; they are not included in this project's installer. The runtime-library directory is under the current user's writable data directory and can be opened from the separate tool. Users need not edit the application installation directory.

The 800-visit default is a current project default, not a universal Strongest standard. Search-quality changes still need project benchmarks. Installer and portability work must not weaken the main model or put a non-best candidate in the first recommendation position.

## Acceptance work before release

- Build a real Windows installer and settle executable layout, asset paths, local dependency discovery, and the user data directory.
- Implement and test basic startup, independent environment detection, and visits settings, including nonstandard paths, cancellation, restart, and cache separation.
- On a clean Windows environment, verify installation, real KataGo analysis, play, SGF, full-game review, and optional Ollama.
- Audit each included third-party component and model against its license obligations; provide required notices and access to corresponding source.
- Review staged source and installer contents separately for private data, then check installer size, checksum, and the GitHub Release file-size limit in effect at publication time.

The earlier v0.2.0.dev30 development build is not a separate public release. The first public version provides v1.0.0 source and a Windows installer under the same version number; validation across other machines and workflows remains ongoing.
