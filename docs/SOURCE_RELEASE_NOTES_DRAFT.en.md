# v0.2.0.dev13 Source Preview Release Notes (Withdrawn Draft)

English | [简体中文](SOURCE_RELEASE_NOTES_DRAFT.md)

> This earlier draft for a separate source-preview release is withdrawn. Do not use it for
> a GitHub release. The first public version uses source and a Windows installer
> under the same version number; use the formal Release for downloads.

RecurGO is a local Go study, play, and review application powered by KataGo. The earlier
proposed release was a **source preview** for people willing to prepare Python, KataGo, and GPU runtime
dependencies themselves. It is not a ready-to-run installer.

## Available in this preview

- New 19×19 games, manual study, and fair or assisted local AI play as either color.
- KataGo candidate moves, win rate, score lead, human preference, area estimate, and rules-based explanation.
- Full-game analysis that can be stopped and resumed, with win-rate trend, move quality,
  problem moves, match rate, and overview views.
- Local game library with automatic saving, SGF import/export, and local recognition of a
  static position from an image.
- English by default, optional Simplified Chinese, and immediate interface switching after
  saving a language preference.
- Optional local Ollama text that does not change KataGo moves or numerical analysis.
- A white-backed native overflow button for toolbar items that do not fit in a narrow window,
  plus the Menu / 菜单 fallback.

See the [user guide](USER_GUIDE.en.md) for use, [source setup](SOURCE_SETUP.en.md) for
dependencies and startup, and [distribution guidance](DISTRIBUTION.en.md) for licensing and
source contents.

## Current limits

- The verified development setup is Windows x64, Python 3.13, and KataGo v1.16.5 with a
  CUDA 12.8 backend. Other hardware and a complete clean-machine setup still need acceptance.
- The source package excludes the KataGo executable, main and Human SL models, CUDA/cuDNN,
  Ollama, machine configuration, personal games, logs, and caches. Users obtain required
  dependencies separately by following the source setup guide.
- A Windows installer has not been accepted or published. GitHub's automatically generated
  Source code ZIP is not an installer.
- Optional model text can be wrong; reliable adherence to the selected language needs a
  real output check.

For ordinary issues, include reproduction steps and system/GPU information after removing
private games, database contents, local paths in logs, and other personal data. Report
vulnerabilities privately under the [security policy](../SECURITY.en.md).
