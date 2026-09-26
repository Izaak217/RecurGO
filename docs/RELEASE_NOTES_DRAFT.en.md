# RecurGO v1.0.0 release notes draft

English | [简体中文](RELEASE_NOTES_DRAFT.md)

> Historical release-note draft. Use the v1.0.0 Release for the final text; do not post this draft as the release announcement.

RecurGO is a local Go practice, play, and review application. The first formal release is intended to provide public source and a separate **Windows x64 installer under the same version**. GitHub-generated `Source code (zip/tar.gz)` files are for reading and further development; general users should choose the installer attached to the Release.

## Installer contents

- RecurGO with its Python/Qt runtime components, KataGo 1.16.5 CUDA engine, main and Human SL models, and analysis configuration.
- A separate Analysis Environment Check tool, optional Ollama launch and model download entry points, bilingual [installation guide](INSTALL_WINDOWS.en.md) and [user guide](USER_GUIDE.en.md), and third-party license materials.
- No personal games or databases, NVIDIA driver, CUDA/cuDNN, Ollama program, or language model.

## Initial support and use

The target is Windows 10/11 x64 with the NVIDIA CUDA 12.8 backend. Real KataGo analysis has passed on an NVIDIA GeForce RTX 5070 Ti Laptop GPU and an NVIDIA GeForce RTX 2080 Ti; the application also displayed candidate moves and win rates with the latter GPU. Other GPUs and backends are outside the verified scope, and not all features have been accepted on the RTX 2080 Ti. Users need a suitable NVIDIA driver, CUDA/cuDNN, and a system Visual C++ runtime. The independent checker shows status and official download links, then performs a real KataGo analysis. Optional Ollama provides supplemental language explanations; KataGo remains the source for moves and analysis figures.

RecurGO supports manual study, play, real-time analysis, a game library, SGF import/export, full-game review, and immediate English/Chinese switching. Analysis visits are configurable separately. Packaging does not alter Strongest play, the main model, Human SL, or candidate ranking.

The installer name, size, and SHA-256 are recorded in the formal Release attachment and `SHA256SUMS.txt`. Use GitHub Issues for ordinary feedback and [SECURITY.en.md](../SECURITY.en.md) for private security contact. Do not publish private SGF games, databases, or logs.
