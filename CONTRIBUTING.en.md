# Contributing to RecurGO

English | [简体中文](CONTRIBUTING.md)

Thank you for helping improve RecurGO. The first public version is planned to include both source and a Windows x64 installer. See the [English README](README.en.md) for verified behavior and pending acceptance work.

## Reporting an issue

First check the [source setup guide](docs/SOURCE_SETUP.en.md) and existing issues. Include the RecurGO version, Windows version, GPU model, KataGo backend, steps to reproduce, expected behavior, and actual behavior. For analysis problems, distinguish between “the files were found,” “the engine started,” and “a valid candidate was returned.”

Do not upload the full `data/` or `runtime/` directory, logs, databases, screenshots, or private SGF files to a public issue. If a position is needed, remove player names, comments, and other personal information and keep only the smallest reproducible example. Check error text for local absolute paths before sharing it.

Report vulnerabilities privately under the [security policy](SECURITY.en.md), without posting details in a public issue.

## Submitting changes

1. Set up Python 3.13 using the [source setup guide](docs/SOURCE_SETUP.en.md). Do not commit `.venv/`, `runtime/`, `data/`, or personal configuration.
2. Describe the behavior changed, relevant call chain, and possible effect on existing behavior. Keep the change small enough to review while covering all dependent logic.
3. Run checks relevant to your change and report the commands and results. Changes to asynchronous engine work, cancellation, restart, caches, or user-data locations should cover the relevant edge cases.
4. Changes to search quality for analysis, recommendations, full-game review, or Strongest play need comparison with a higher-visits reference, including a unique-solution position, several near-equal solutions, and a position near a win-rate reversal. The first recommended move must still be a legal candidate with `order = 0` in the current KataGo analysis.
5. Before adding third-party code, models, or binaries, record their source, version, checksum, and license obligations. Do not add locally downloaded runtime assets to the source repository.

RecurGO-owned code uses the root [MIT license](LICENSE). Third-party components retain their own terms; see [Third-party notices](THIRD_PARTY_NOTICES.en.md).
