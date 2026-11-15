# Changelog

This file records the notable changes to Usage Dock. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Usage Dock has no tagged release and no published binary. The sections below follow the commit history. The version number comes from `CFBundleShortVersionString` in `UsageDock/Info.plist`, and the build number comes from `CFBundleVersion`.

## Unreleased

### Added

- Documentation for users, contributors, and AI agents: `README.md` in English, `README.pt-BR.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `THIRD_PARTY_NOTICES.md`, `AGENTS.md`, `llms.txt`, `docs/ARCHITECTURE.md`, `docs/ADDING-A-PROVIDER.md`, `docs/KNOWN-LIMITATIONS.md`, and this changelog.
- Issue forms for bug reports and feature requests, and a pull request template.
- The MIT License, in `LICENSE`.

### Changed

- The README was rewritten in English. The Portuguese version is `README.pt-BR.md`.
- The pace calculation and the number formats have a new implementation, in `WindowPace.swift`. The card shows the same text as before.
- Git ignores `refs/baseline/`, the folder of local screenshots.

## 0.1.0 - 2026-09-23

Build 47.

### Added

- Claude ring. The collector reads the Claude Code login from the macOS Keychain and shows the 5-hour and weekly windows.
- Devin ring, with the daily and weekly quotas.
- Pace in each card. The pace compares the percent used with the share of the window that has passed.
- Token statistics and a 30-day bar chart in the Codex card.
- A Codex reading over HTTP, which the collector tries before the Codex CLI.
- A provider with no login, a cancelled plan, or a full quota leaves the dock. The settings card lists those providers under `Fora da fila`, each with a `Vigiar` button.
- The app saves the last good readings and restores them at launch. A reading that is more than 3 minutes old fades.
- The app refreshes when the Mac wakes.
- A time limit for each provider in the collector.
- The `USAGE_DOCK_SKIP` environment variable.
- At launch, the app quits other running copies, and hands over to the installed copy when that copy has a higher build number.
- `UsageDock/Info.plist` in the repository.
- 35 collector tests, for a total of 47.

### Changed

- The app refreshes every 60 seconds while the dock is in use and every 5 minutes when it is idle. Before, the app refreshed every 30 seconds.
- The collector reads the OpenCode Go key only from the OpenCode login file. It no longer reads `OPENCODE_GO_API_KEY`.

## First snapshot - 2026-09-08

The first commit has no version number, because `Info.plist` was not in the repository yet.

### Added

- The dock on the right screen edge, with five rings: Codex, OpenCode Go, Command Code, Cursor, and Grok.
- A card for each ring. The card opens on hover, stays pinned after a click, and shows the plan name.
- A settings card behind the gear, and a context menu.
- Collapse to a tab, drag, and snap to the right screen edge.
- The Python collector, which reads the five providers in parallel, with 12 tests.
- `scripts/build.sh` and `scripts/capture-dock.sh`.
