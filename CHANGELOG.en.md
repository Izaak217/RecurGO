# Changelog

English | [简体中文](CHANGELOG.md)

## v1.0.1 — 2026-10-01

Testing v1.0.0 revealed that some areas were counted as neutral when ending a game, producing results that differed noticeably from KataGo’s territory analysis during play. This update revises the final-scoring workflow and improves score review.

“Finish / Score” now uses the current position’s live KataGo ownership data as its starting point. Users can adjust individual points and mark or restore whole dead groups. The final score follows the assignments confirmed by users.

Under Chinese rules, shared empty points count as half a stone for each side. Unassigned points appear as small hollow squares. A message beside the confirmation button shows how many points remain and how to resolve them. Other conditions, such as missing territory data, also receive an explanation.

The new “Show dead stones” option hides dead stones by default and displays them faintly when enabled, without changing the score. Confirmed assignments, dead-stone markings and results are saved in the game library and can be viewed again later.

Before updating, close RecurGO and back up saved games, then run the new installer.

## v1.0.0 — 2026-09-26

- Aligned the application, build version, and bilingual user documentation with the first formal version number.
- Rewrote the installation guide and user manual for publication; maintainer documents retain release status and outstanding acceptance work.

## v0.2.0.dev30 — 2026-09-26 (release checks and user docs)

- Updated the outdated auto-detection UI test for the checker's current results browser and added bilingual punctuation coverage for local AI failure messages.
- Revised the Windows Installation Guide and User Manual in both languages with installer hash verification, personal-data backup, and uninstall guidance.
- Recorded real KataGo analysis on the NVIDIA GeForce RTX 5070 Ti Laptop GPU and NVIDIA GeForce RTX 2080 Ti, plus displayed candidate moves and win rates on the latter, with the test scope stated explicitly.

## v0.2.0.dev29 — 2026-09-26 (local AI wording)

- Shortened the Chinese and English Ollama settings notice to explain its purpose, model selection, and first-time setup once each.
- Normalized the punctuation between generation errors and the KataGo fallback notice, without changing the underlying error or explanation.

## v0.2.0.dev28 — 2026-09-26 (user docs and checker entry)

- Separated the bilingual Windows Installation Guide and User Manual, updated their Start Menu names, and corrected checker button names in the guide.
- Removed the duplicate Next: run KataGo check button. Save and check keeps the same save-and-analyze path.
- Applied a regular rounded-corner transparency mask to the original desktop-shortcut artwork, keeping the original and intermediate PNGs. Program and installer icons are unchanged.

## v0.2.0.dev27 — 2026-09-26 (optional desktop shortcut icon)

- Used the Go character artwork selected by the project author, kept the original PNG as source artwork, and generated a Windows icon with 16–256 pixel sizes.
- Kept setup's existing desktop-shortcut option unchecked by default. If selected, the desktop shortcut uses this icon. The main program, windows, other shortcuts, and installer keep their previous icons.
- Only the optional desktop shortcut appearance changes; the KataGo engine, models, search settings, and user-data paths are unchanged.

## v0.2.0.dev25 — 2026-09-26 (detect newer cuDNN install layouts)

- Auto-detect folders containing `cudnn64_9.dll` below NVIDIA cuDNN 9.x installations and beneath `CUDNN_PATH`. This fixes a missed DLL in a 9.25.1 installation's deeper folder. The checker and bilingual guides now state the cuDNN 9.x requirement.
- The checker now distinguishes an auto-search miss from a missing installation. Detect again shows the auto-selected paths and presents actions to select an existing DLL or run a real check. Selecting a manual folder immediately refreshes the results using that folder, so an old auto-search miss is no longer shown. Found files still require a real KataGo analysis.
- Updated both installation guides. Engine models, analysis budget, personal data paths, and installer location are unchanged.

## v0.2.0.dev24 — 2026-09-26 (separate EXE and ZIP setup paths)

- The environment checker now separates NVIDIA's EXE system installer from standalone ZIP files. It makes clear that users run an EXE, while only DLLs extracted from ZIP files go into the displayed destination.
- The bilingual installation guides explain that an EXE from the CUDA Toolkit page is expected. Runtime discovery, KataGo models, and search settings are unchanged.

## v0.2.0.dev23 — 2026-09-26 (system CUDA/cuDNN discovery)

- Auto-detect versioned NVIDIA cuDNN 9.x system installations and their immediate bin subdirectories. `CUDA_PATH` and `CUDNN_PATH` may now point directly to bin folders.
- The checker lists missing DLLs, matching official downloads, and extracted ZIP destinations separately for CUDA and cuDNN; existing system installations can be selected manually.
- Installation guides cover both NVIDIA system installers and standalone ZIP files, and clarify that cuDNN does not replace CUDA Runtime/cuBLAS. A real KataGo analysis still determines compatibility; models and search settings are unchanged.

## v0.2.0.dev22 — 2026-09-26 (installation directory selection)

- Always show the application installation directory page; keep the existing default and use a prior installation directory as the initial choice when available.
- The supported environment-check entry remains the Start Menu's Analysis Environment Check shortcut or `check_analysis_environment.cmd` in the installation directory. Running the checker EXE directly retains its command-line behavior.
- The application directory remains separate from `%LOCALAPPDATA%\RecurGO` user data. KataGo models and search settings are unchanged.

## v0.2.0.dev21 — 2026-09-26 (update publishing account)

- Updated RecurGO-owned copyright attribution and the public profile to izaak (GitHub: izaak217). The security contact remains izaak.zhang@outlook.com.
- Synchronized the local installer candidate's license and guides. Application behavior, KataGo search, models, and user-data paths are unchanged.

## v0.2.0.dev20 — 2026-09-25 (installer terms and runtime review)

- The installer license page now presents the project's MIT license and the official Microsoft Visual C++ runtime terms for their respective components. The original Microsoft text, official source, and hashes are retained. The 11 runtime DLLs supplied by upstream packages are unchanged.
- Verified Microsoft's individual Community usage terms and Inno Setup's statement that a paid license is not strictly required. Updated the release checklist so personal identity and the compiler message are not treated as established blocks.
- KataGo search, UI, data paths, and NVIDIA / KataGo / NumPy / Qt binary dependencies are unchanged.

## v0.2.0.dev19 — 2026-09-25 (review bundled Qt notices)

- Preserved original attribution records, related license texts, and a source index from five official Qt 6.11.1 archives matching the modules retained by the installer. Source metadata can also describe components absent from the installed binaries; the installed file manifest remains authoritative.
- Added an explicit Qt / PySide6 LGPLv3 notice before installation and pointed to license, source, and shared-library replacement information. The UI, KataGo search, and user-data paths are unchanged.

## v0.2.0.dev18 — 2026-09-25 (centralized bundled notices)

- Matched retained Qt graphics and image plugins in the installer candidate to Mesa, JPEG, TIFF, and WebP license and copyright materials from the fixed Qt 6.11.1 official source archives, kept together under `licenses/qt/third_party/`.
- Kept the existing installer notice and third-party index. The UI, KataGo search, and user-data paths are unchanged. Installation and distribution acceptance remain pending.

## v0.2.0.dev17 — 2026-09-25 (exclude unused bundled plugins)

- Compare actual Qt and OpenCV calls with common Windows package license practice. Exclude unused Qt PDF, Qt FFmpeg media, and OpenCV video plugins while retaining Qt audio output and still-image recognition.
- Reject these components if they re-enter the installation tree and update third-party notices. KataGo models, search budgets, user-data paths, and Git upload state are unchanged.

## v0.2.0.dev16 — 2026-09-25 (build-source isolation)

- Found that the dev15 installer inadvertently collected Poppler/libheif runtime libraries outside the project from the terminal `PATH`; that candidate must not be published.
- Give PyInstaller only explicit Python and Windows paths, then check the source of every collected binary and data file; abort on unapproved paths.
- Keep KataGo models, search budgets, and application data paths unchanged. Installation and third-party distribution checks remain pending after the rebuild.

## v0.2.0.dev15 — 2026-09-24 (local release security review)

- Copy installer license files only from the Git-tracked list; stop the build if extra files appear in that directory.
- Extend the staged-file audit to distinguish OpenCV's own `data` from private data, and reject databases, games, logs, linked files, and common key or machine-path markers.
- Review upstream download links in both languages. Publication, third-party licensing, and clean Windows installation acceptance remain pending.

## v0.2.0.dev14 — 2026-09-24 (local installer preparation)

- Added a local Windows x64 installer build from the same source version, staging KataGo, the main and Human SL models, bilingual guides, and third-party license materials.
- Installed builds place user data, user-supplied CUDA/cuDNN libraries, and optional Ollama files in the current user's data directory; source-mode paths remain unchanged.
- The separate analysis environment tool now checks the system Visual C++ runtime and links to Microsoft, while real KataGo analysis remains the final check.
- The build excludes unused Qt Virtual Keyboard files and does not copy the developer's Microsoft runtime DLLs into KataGo's engine directory. Publication, third-party binary license review, and clean Windows installation acceptance remain pending.

## v0.2.0.dev13 — 2026-09-24 (local source preview)

- Removed the fixed second toolbar row. Mode, difficulty, play-as color, real-time analysis, and ownership return to the original main toolbar.
- In a narrow window, the white-backed overflow button opens the controls that no longer fit. The Menu fallback remains.
- Control state, immediate language switching, KataGo analysis, and game data are unchanged.
- Added bilingual source-preview user guides and draft release notes; the installer remains a draft.

## v0.2.0.dev12 — 2026-09-24 (local source preview)

- Moved mode, difficulty, play-as color, real-time analysis, and ownership controls to a second toolbar row.
- Kept the existing Menu entry and gave the toolbar's rightmost overflow button a white background so it stands out in a narrow window.
- Control behavior, state synchronization, KataGo search, and game data are unchanged.

## v0.2.0.dev11 — 2026-09-24 (local source preview)

- Added a persistent Menu entry so game, play, analysis, and settings controls remain discoverable in a narrow window.
- Reused toolbar actions and routed mode, difficulty, color, real-time analysis, and ownership through their existing controls, with synchronized disabled states and English/Chinese labels.
- KataGo models, search budgets, candidate ranking, and game storage remain unchanged.

## v0.2.0.dev10 — 2026-09-24 (local source preview)

- Saving a language preference now updates the main window, review charts, and current rules explanation immediately without a restart.
- Switching cancels an Ollama request in the previous language and uses existing analysis data for the new explanation without restarting KataGo search.
- Game and player names keep their original text. Modes, difficulty, candidate ranking, and search budgets are unchanged.

## v0.2.0.dev9 — 2026-09-24 (local source preview)

- English is now the default on a fresh installation. A saved Simplified Chinese choice stays Chinese.
- Older settings without a language field now use English, and Restore defaults selects English.
- The standalone environment checker uses English when no language choice is saved. Games, models, and search settings are unchanged.

## v0.2.0.dev8 — 2026-09-24 (local source preview)

- Added a persisted Simplified Chinese / English preference. Restart the main application to apply it.
- Added English display text to the main window, game library, image recognition, scoring, review plots, and standalone environment checker. Stored game mode, difficulty, and review grade values remain compatible with existing games.
- Added English deterministic Go explanations and selected a Chinese or English prompt for optional Ollama. KataGo search, models, visit budgets, and best-candidate ranking were not changed.
- Added paired Chinese and English README, source setup, contribution, distribution, third-party notice, and release-draft documents. Static syntax and Git content checks were completed; live English UI and model-output acceptance remain pending.

## v0.2.0.dev7 — 2026-09-23 (local feature preview)

- Unified the project name as RecurGO and renamed the Python package to `recurgo`, updating imports, tests, launchers, installation metadata, window title, SGF application marker, and documentation.
- Preserved the original names and credits for KataGo, models, and third-party licenses; analysis algorithms, models, and search budgets did not change.
- The new version stores local games and settings in `recurgo.db`. The previous database remains untouched and is not migrated automatically.

## v0.2.0.dev6 — 2026-09-23 (local feature preview)

- Added explicit automatic/manual modes in the independent environment tool, showing CUDA/cuDNN paths and missing DLLs; checked whether the Windows NVIDIA driver initializes and detects a CUDA GPU.
- Preferred user-supplied libraries under `runtime/cuda_deps/nvidia/{cuda,cudnn}/bin` before the existing manifest, system installation, and `PATH`. The main program only reads saved paths and has no new environment settings page.
- Optional Ollama kept the existing `runtime/ollama/` layout and service script.

## v0.2.0.dev5 — 2026-09-23 (local feature preview)

- Removed the newly added main-program Analysis Environment button, path editing, and startup file precheck.
- Assigned CUDA/cuDNN selection, local configuration saving, and a real KataGo test to the independent tool. The main program reads that file to start the engine. Older paths in the database may be prefilled when opening the tool for the first time.

## v0.2.0.dev4 — 2026-09-23 (local feature preview)

- Fixed the independent check launcher: Windows `cmd` misparsed a Chinese message and never ran the check. Launcher text became ASCII; Python diagnostics remain in Chinese in this version.

## v0.2.0.dev3 — 2026-09-23 (local feature preview)

- The independent checker lists missing KataGo engine, models, configuration, CUDA/cuDNN directories, and specific library files together. The source checker also reports a missing Python environment or module. When all files exist but the engine fails to start, it shows KataGo's original error instead of guessing a cause.

## v0.2.0.dev2 — 2026-09-23 (local feature preview)

- Moved the real KataGo environment analysis test to `check_analysis_environment.cmd`; normal main-program startup no longer runs a test position. The check runs on demand, uses CUDA/cuDNN paths saved by the main program at that time, and reports success only after a valid candidate without writing a game or analysis cache.
- The Analysis Environment window and installation instructions pointed to the independent tool; visits, Ollama guidance, board, and recommendation behavior remained.

## v0.2.0.dev1 — 2026-09-23 (local feature preview)

- Added Analysis Settings to the toolbar. Visits default to 800, can be changed and persisted, and apply to real-time analysis, full-game review, and their caches. Strongest play has a separate unaffected budget.
- Changing visits stops the old analysis and separates old caches so delayed results cannot be saved as if computed with the new budget.
- Local AI Explanation Settings points users to installation and model-download instructions.
- Added an Analysis Environment entry at that version for local CUDA/cuDNN paths and a one-time KataGo probe. Source mode kept `data/`; a future frozen program was planned to use writable per-user data.
- This was a feature preview, with no installer built or uploaded and no local games or runtime directory included.

## v0.1.5 — 2026-09-23

- Reverted the day's new automatic blue selection in the candidate table, preservation of a clicked candidate during incremental refresh, and hiding old candidates when an incomplete analysis message arrived. The earlier display behavior was restored.
- Stale local AI requests still cancel. Removal of duplicate figures from the left explanation and scroll-position handling remained.
- KataGo search, candidate ordering, and right-hand win rate, score lead, and visits calculations did not change.

## v0.1.4 — 2026-09-23

- Removed win-rate, score-lead, and visits figures from the upper explanation because the right-hand panel already shows them. Updated the insufficient-local-evidence message.
- An incremental update for the same candidate no longer rewrites unchanged explanation text; when the text changes, reading position is preserved.
- Values remain available to internal analysis and local AI context. KataGo search, candidate ordering, the right-hand panel, and Ollama flow did not change.

## v0.1.3 — 2026-09-23

- Fixed a false Ollama 0.34.3 rejection when `/api/show` listed thinking capability without listing an off value. The local API accepted `think: false` for the selected model and returned non-thinking text.
- Double-click launchers reuse a healthy project-local Ollama service, including its current proxy mode.
- Corrected the real-flow probe to enable real-time analysis, which is normally off.
- Checked the local model's SHA-256 and imported it through Ollama. Full-game explanation remains for the user to test.
- KataGo budgets, model, and candidate ordering did not change.

## v0.1.2 — 2026-09-23

- Added optional local Ollama explanations alongside immediate rule-based explanations, with automatic requests, streaming, and separate settings.
- Changing position or candidate cancels stale output. KataGo searches and full-game review have priority, and fair play remains isolated from analysis.
- Added visible captures in reference variations and corrected wording that had claimed a move saved a group even though the group remained in atari.
- Added a project-local portable Ollama service script and a real-flow probe; model download and generation acceptance were still in progress at that version.
- Added `.gitignore`, source setup examples, and publication-scope guidance while continuing third-party license source records.
- KataGo search parameters, analysis model, and candidate ordering did not change. Nothing was pushed to GitHub and no portable package was released.

## v0.1.1 — 2026-09-23

- Added MIT licensing and project license metadata for RecurGO-owned code and docs.
- Added third-party component inventory, original license texts, versions, and source records.
- Added Qt corresponding-source and shared-library replacement information and NVIDIA runtime distribution notes.
- Declared license files in Python package metadata for build artifacts.
- Only licensing, documentation, and version metadata changed; application behavior, playing-strength parameters, and personal data did not.
