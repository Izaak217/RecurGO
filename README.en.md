# RecurGO

English | [简体中文](README.md)

User documentation: [Windows Installation Guide](docs/INSTALL_WINDOWS.en.md) · [User Manual](docs/USER_GUIDE.en.md) · [Run from source](docs/SOURCE_SETUP.en.md) · [Build the installer](docs/BUILD_WINDOWS.en.md).

RecurGO is a local desktop application for Go practice, play, and review powered by KataGo.

The first public version is **v1.0.0**, with source and a Windows x64 installer under the same version number. Real KataGo analysis has passed on Windows x64 with an NVIDIA GeForce RTX 5070 Ti Laptop GPU and an NVIDIA GeForce RTX 2080 Ti; the latter also showed candidate moves and win rates in the application. This does not establish support for every NVIDIA GPU or acceptance of every feature. Selection among GPU backends remains in development. The source repository excludes models, runtimes, personal game records, and caches.

The [Windows installation guide](docs/INSTALL_WINDOWS.en.md) explains installation; the matching GitHub Release provides the installer and checksum file. The application has an analysis visits setting and Ollama setup guidance. CUDA/cuDNN path selection and a real KataGo check live in the separate `check_analysis_environment.cmd` tool. Source mode first looks under `runtime/cuda_deps/nvidia/`; installed mode first looks under `cuda_deps/nvidia/` in the current user's data directory. Both accept manually selected paths. The NVIDIA driver is installed in Windows and checked by that tool. The main application has no environment setup or test entry point.

## Current capabilities

- A KataGo v1.16.5 CUDA environment, the main analysis model, and the Human SL model have been verified on the development machine.
- Real-time analysis and full-game review have a configurable visits setting, initially 800. Cached results from another budget remain available but are not presented as results from the new budget.
- A persistent KataGo JSON analysis process streams updates, supports cancellation, and integrates with the Qt interface.
- Manual study, fair play, and assisted play are available. The human can play either color; when the human chooses white, the AI plays first.
- Five Human SL difficulty levels sample moves from rank-specific human policy. The sixth, Strongest, uses the main model's best searched move.
- Candidate moves, win rate, score lead, human preference, principal variation, and a win-rate plot update during analysis. The plot follows the current variation and moves back after undo.
- The board previews legal moves and plays built-in move and capture sounds. Four board themes and four stone styles are available, along with separate sound selection, volume, and mute. These preferences are stored in the local database.
- Images from the clipboard or a local file can be recognized as static 9×9, 13×13, or 19×19 positions. Users can select four corners, rotate or mirror the image, correct individual intersections, and set the side to play.
- Under Chinese rules the interface displays black's komi as 3¾ stones; the engine uses the equivalent `komi=7.5`.
- Games can end manually, by resignation, or after two passes. Scoring lets users confirm dead groups and saves the result. A finished game can stay open or be followed by a new game; exported SGF retains its `RE` result.
- The win-rate plot supports horizontal and vertical zoom and shows move number and black win rate on hover.
- SQLite saves every move automatically. The game library restores games and can permanently delete a selected game and its analysis cache after confirmation.
- SGF import and export retain variations and comments. Imported and saved games can be reviewed move by move with navigation buttons and a slider.
- Full-game AI analysis can be stopped and resumed. Candidate data is saved as each position completes.
- Review includes overview, win-rate trend, move quality, problem moves, and match-rate views, with whole-game, opening, middle-game, and endgame scopes. Statistics distinguish black from white, and clickable marks jump to the corresponding position.
- English is the default. Select Simplified Chinese or English under Preferences → Language / 语言 and choose OK to apply it immediately. Interface labels, deterministic explanations, and the optional Ollama prompt follow the selected language. Actual model output still needs a live check.
- Mode, difficulty, play-as color, real-time analysis, and ownership controls share the main toolbar with the other actions. In a narrow window, use the white-backed overflow button at the right to open controls that do not fit. **Menu / 菜单** remains a fallback.

Image recognition runs locally through OpenCV and does not upload images. Optional language-model explanations send only the current board and candidate facts to the local Ollama service; they omit player names, SGF comments, and local paths. Image import creates a static root position and does not invent past moves, captured stones, or ko history.

## Run from source

Install Python 3.13, then create an environment and install dependencies from the project directory:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m recurgo.app
```

A fresh clone also needs a KataGo engine, two models, and runtime configuration. Python dependencies alone do not enable AI analysis. Follow the [English source setup guide](docs/SOURCE_SETUP.en.md) for the current CUDA procedure and its limits. Development uses an editable installation; wheel and standalone executable distribution have not been validated.

Local rules provide an immediate evidence-based explanation of a candidate move. Optional Ollama text can be requested automatically, streamed, and cancelled when stale. KataGo keeps priority while it is searching. Ollama is off by default; see the [local AI guide](docs/OLLAMA_LOCAL.en.md) for use and verification status.

To run the existing checks:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\probe_qt_engine.py
.\.venv\Scripts\python.exe scripts\probe_ui_battle.py
```

`.gitignore` excludes local runtime and data directories; see the [English distribution guide](docs/DISTRIBUTION.en.md) for the intended source contents. Contributors can read [Contributing](CONTRIBUTING.en.md).

## License and third-party components

RecurGO-owned code and documentation use the [MIT License](LICENSE), with the copyright holder identified as [izaak (izaak217)](https://github.com/izaak217). The current source version is **v1.0.1**.

KataGo, its models, Qt/PySide6, and other dependencies remain under their respective terms. RecurGO's MIT license does not replace them. See [Third-party notices](THIRD_PARTY_NOTICES.en.md) and the [license sources](licenses/README.md). Distribution must retain the applicable materials; source and packaging obligations are summarized in the [distribution guide](docs/DISTRIBUTION.en.md).

RecurGO is an independent application based on KataGo. It is not an official KataGo, Qt, or NVIDIA product; naming those components does not imply endorsement. License information and source references for the distributed components are listed in the linked notices. See the [change log](CHANGELOG.en.md) for version history.

Please report security issues privately under the [security policy](SECURITY.en.md); do not disclose details in a public issue.
