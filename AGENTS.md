# AGENTS.md

Instructions for AI coding agents that work in this repository. The [README](README.md) describes the project for people.

## What this project is

Usage Dock is a macOS overlay that shows how much of each AI coding subscription the user has consumed. It has two parts.

- `collector.py` is a Python script. It reads the logins that provider tools keep on the Mac, calls each provider's usage API, and prints one JSON object.
- `UsageDock/` is a SwiftUI and AppKit app. It runs the collector, decodes the JSON, and draws one ring per provider on the right edge of the screen.

The provider ids are `codex`, `opencode`, `goat`, `cursor`, `grok`, `devin`, and `claude`. The id `goat` is Command Code.

The project is a personal tool in preparation for open source, under the MIT License. It has no release and no CI.

## Where things are

| Path | Content |
|---|---|
| `collector.py` | Every provider reader, the JSON row builder, and `main` |
| `tests/test_collector.py` | 47 `unittest` tests for the collector |
| `UsageDock/Sources/UsageDock/UsageStore.swift` | App state, refresh schedule, the collector process, the rule that removes rings |
| `UsageDock/Sources/UsageDock/Models.swift` | `DockLayout` with every size, and the `Codable` types of the JSON contract |
| `UsageDock/Sources/UsageDock/OverlayController.swift` | The floating panel, drag, snap, Esc, and click outside |
| `UsageDock/Sources/UsageDock/DockView.swift` | The pill, the rings, the gear, and the menu |
| `UsageDock/Sources/UsageDock/PopoutView.swift` | The card of a provider |
| `UsageDock/Sources/UsageDock/SettingsModal.swift` | The settings card |
| `scripts/build.sh` | Builds, signs, and installs the app |
| `docs/ARCHITECTURE.md` | How a round works, the JSON contract, timing, and state |
| `docs/ADDING-A-PROVIDER.md` | The steps to add a ring |
| `docs/KNOWN-LIMITATIONS.md` | The defects that are already known, numbered |
| `refs/SPEC.md` | The design specification of the dock, in Portuguese |

## Commands

Run the commands from the repository root.

| Goal | Command | Expected result |
|---|---|---|
| Test the collector | `python3 -m unittest discover -s tests` | `Ran 47 tests` and `OK`, in less than one second |
| Run one test class | `python3 -m unittest tests.test_collector.ClaudeRowTests` | `OK` |
| Compile the app | `cd UsageDock && swift build -c release` | `Build complete!` with no warning. The first build takes about two minutes |
| Run one collector round | `USAGE_DOCK_SKIP=grok python3 collector.py` | One JSON object on standard output |

The tests use no network and no credentials. The Swift package has no test target, and the repository has no linter and no formatter.

## Read this before you run anything

These commands change the user's machine or use the user's accounts.

- `scripts/build.sh` overwrites the installed app at the `LIVE` path and recreates `/private/tmp/UsageDock.app`. Do not run it unless the user asks you to install a build.
- A copy of the app that starts quits every other running copy with the bundle identifier `com.louiemota.usagedock`. Do not start the app to test a change while the user's dock runs, unless the user asks.
- `collector.py` calls the real provider APIs with the user's logins. Run it once when you need it, never in a loop.
- Without `USAGE_DOCK_SKIP=grok`, the collector can refresh the Grok token and rewrite `~/.grok/auth.json`.
- `scripts/capture-dock.sh` captures the whole screen, with every open window. Do not run it.
- Four path constants point to the author's machine: `pythonPath` and `scriptPath` in `UsageStore.swift`, `canonicalApp` in `UsageDockApp.swift`, and `LIVE` in `scripts/build.sh`. On another machine, the app cannot run the collector until those constants change.

## Rules for credentials

- Never print, log, store, or commit a token, an API key, or the content of a login file.
- Do not read a login file to inspect it. If you need its shape, read the function that parses it, for example `_codex_auth_credential`.
- The JSON that the collector prints must contain no credential. The app saves that JSON to disk.
- Call only the provider that owns the login. Do not add telemetry, analytics, or any other network destination.
- Do not write to a provider's login file. The Grok refresh in `persist_grok_slot` is a known defect, not a pattern to copy.
- Use invented values in tests and in documents.

## Conventions

Collector:

- Use only the Python standard library. The code has to run on Python 3.9, so keep `from __future__ import annotations` at the top of the file.
- Follow the pattern of three functions: `collect_<provider>` does the I/O, `fill_<provider>_row` builds the row with no network, and `_safe_<provider>` catches exceptions.
- When a value is missing in a provider response, return an error row. Do not fall back to 0%.
- Add a test for every change of a `fill_` function.

App:

- Change sizes in `DockLayout`, in `Models.swift`. The views and the hit testing in `OverlayController.swift` read the same constants.
- If you change what a card draws, update `DockLayout.estimatedPopoutHeight`. The panel size and the hit testing use that estimate.
- `UsageStore` and `OverlayController` run on the main actor.

Text:

- Interface strings and collector messages are in Brazilian Portuguese. The project has no localization layer. Write a new string in the language of the strings around it.
- Do not use em dashes in interface text or in documents.
- Documents are in English, except `README.pt-BR.md` and the files in `refs/`.

## Behavior that must not change by accident

These rules come from `refs/SPEC.md` and from comments in the code.

- A click outside the dock closes the open card. It must not collapse the dock. `dismissIfClickOutside` never calls `setCollapsed(true)`.
- Esc pressed in another app closes cards. It collapses the dock only when the pointer is over the dock.
- The panel keeps its expanded size while the dock is collapsed. A smaller panel clips the animation.
- The gear is not a ring. It has no percentage and no quota arc.
- Do not add the four-edge transform or the hardware-notch merge of Codenotch to `SideNotchShape` unless the maintainer asks. A comment in `CoupledShell.swift` records that those changes alter the approved shape.
- Keep the attribution to Codenotch in `CoupledShell.swift`, in `UsagePace.swift`, and in `THIRD_PARTY_NOTICES.md`.

## Do not

- Do not change `LICENSE`, and do not add license headers to source files. The project is under the MIT License, and `THIRD_PARTY_NOTICES.md` records the material that the license does not cover.
- Do not fix a known limitation as a side effect of another change. Several items in `docs/KNOWN-LIMITATIONS.md` need a product decision from the maintainer.
- Do not commit an edit of the four path constants that points to the current machine.
- Do not commit a screenshot that shows anything except the dock. Git ignores `refs/baseline/` for that reason.
- Do not copy a path that contains a user name into a document, a comment, or a test.
- Do not add a Python dependency or a Swift package dependency without the maintainer's approval.

## Finish a task

1. Run the collector tests.
2. Compile the app if you changed a Swift file.
3. Update the documents that the change makes wrong: `README.md`, `README.pt-BR.md`, `docs/`, `llms.txt`, and this file.
4. Add a line to `CHANGELOG.md` under `Unreleased`.
5. Say in your report which checks you ran and which you could not run. An interface change that nobody opened in the running app is not verified.
