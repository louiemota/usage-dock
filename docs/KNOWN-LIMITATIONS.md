# Known limitations

This page lists the defects and the limits of the current code. Nothing on this page is fixed yet, and no fix has a date. The list was last checked against the code on 2026-11-14.

Each item names the file and the symbol where the behavior lives. The numbered items keep their numbers, so an issue can refer to "limitation 13". To report a new defect, follow [CONTRIBUTING.md](../CONTRIBUTING.md).

## Running Usage Dock on another machine

- **Four path constants point to the author's machine.** `pythonPath` and `scriptPath` in `UsageDock/Sources/UsageDock/UsageStore.swift`, `canonicalApp` in `UsageDock/Sources/UsageDock/UsageDockApp.swift`, and `LIVE` in `scripts/build.sh` are absolute paths. Until you replace them, every reading fails and the build script installs to a path that does not exist on your Mac.
- **The collector is not inside the app bundle.** The app starts an external Python interpreter with `collector.py` by absolute path. If you move or delete either file, every round fails.
- **The build script hides a failed universal build.** `scripts/build.sh` first tries to build for Intel and Apple silicon, discards the error output, and falls back to the architecture of the host. With the Command Line Tools alone, the universal build fails because `xcbuild` is missing, so the binary runs on one architecture. The universal build with a full Xcode install is not verified.
- **The build script uses a fixed staging path.** `scripts/build.sh` deletes and recreates `/private/tmp/UsageDock.app` on every run.
- **The repository has no launch-at-login setup.** The author starts the app with a personal LaunchAgent that is not in the repository.
- **The app is signed ad hoc and is not notarized.** The project has no Apple Developer ID. macOS blocks a copy of the app that was downloaded from someone else.
- **The project has no CI.** Nothing runs the tests on a push or on a pull request.
- **The Swift code has no tests.** `UsageDock/Package.swift` declares no test target. Only the collector has tests, in `tests/test_collector.py`.
- **`scripts/capture-dock.sh` works only on the author's display.** The script captures the whole screen, assumes a 6400 by 3600 pixel display, and writes to `refs/baseline/`, which git ignores. Do not use its output in an issue or a pull request, because a full-screen capture shows every open window.

## Readings that can mislead

1. **Each ring measures a different window.** The Codex ring shows the weekly window (`_codex_details_from_windows`). The Command ring shows spend in the billing period (`fill_command_row`). The Cursor ring shows only the allowance for Cursor's own models (`collect_cursor`). The OpenCode, Devin, and Claude rings show the most used window (`fill_opencode_row`, `fill_devin_row`, `fill_claude_row`). A ring can be green while another window of the same provider is full.
2. **A stale Codex reading looks fresh.** When the collector falls back to the Codex Limits history, `collect_codex_history` marks the reading as stale if it is more than 25 minutes old, and explains the source in `note`. `UsageStore.apply` then sets `stale` to false on every reading that succeeded, and no view displays `note`.
3. **The old number stays after the window resets.** When a reading fails, `UsageStore.apply` keeps the last good reading and fades the ring. The card can show `resetou` next to the old percentage. The usual case is a Claude token that expires while Claude Code is closed.
4. **A reading does not show its age.** A ring fades only after 180 seconds without a good round (`UsageStore.staleAfter`). The time of the last round appears only in the settings card, and that time belongs to the whole round, not to each provider.
5. **A missing value becomes 0%.** If a provider renames or removes a field, several readers fall back to zero and the ring turns green. See `collect_grok`, `collect_cursor`, `fill_opencode_row`, and `fill_devin_row`. `fill_command_row` falls back to a fixed allowance of 70 dollars when it finds no spend and no credits.
6. **The Grok window is always labeled as weekly.** `collect_grok` writes the label `Semanal` for whatever billing period the API returns.
7. **The Command percentage assumes that spend plus remaining credits is the allowance.** `fill_command_row` divides the spend by that sum. The result is right only when the usage summary covers the current billing period exactly. This number was not compared with the Command Code dashboard.

## Refresh and resilience

8. **One slow provider delays the whole round.** `main` in `collector.py` prints the result only after the thread pool closes, and the pool waits for every thread. The app stops the collector after 18 seconds (`UsageStore.runCollector`) and marks every ring as stale. In a test with one provider blocked for 25 seconds, the result arrived after 25.0 seconds, although the other six readings were ready.
9. **A failing collector runs again every 15 seconds.** `UsageStore.pulse` compares the clock with `lastUpdated`, which changes only after a good round. While the collector fails, the app starts it on every pulse, and each run calls every provider.
10. **The app depends on two files outside its bundle.** `UsageStore.pythonPath` and `UsageStore.scriptPath` point to a Python interpreter and to `collector.py`. See the first section of this page.
11. **The Grok reading rewrites the Grok login file.** `grok_access_token` refreshes the token when it expires within 8 minutes, and `persist_grok_slot` writes `~/.grok/auth.json` again. The refresh can race with the Grok CLI, and the new file gets the default permissions instead of the permissions of the old file. Every other provider is read-only.
12. **The app writes no log.** The last collector error appears only in the settings card, cut to 180 characters (`UsageStore.CollectorError`).

## Confusing behavior

13. **A ring disappears when the quota reaches 100%.** `apply_dead` in `collector.py` turns any reading of 99.9% or more into the error `cota esgotada`, and the provider leaves the dock. The settings card does not show when the quota resets. `RingButton` has a style for a full ring, a thicker red ring that pulses, but that style cannot appear at 99.9% or more. Because the Claude ring is the most used window, a full 5-hour window removes Claude for up to 5 hours.
14. **`Vigiar` does not work for a full quota or a cancelled plan.** `UsageStore.restoreWatch` puts the ring back, and the next reading removes it again about one second later.
15. **A free plan is reported as a cancelled subscription.** `apply_dead` treats the plan labels `Free` and `Hobby` as cancelled. A user on a free plan never sees that ring, and the reason in the settings card is wrong.
16. **Esc and clicks misbehave in the transparent part of the window.** The window is 318 points wide and the pill is 66 points wide. `OverlayController.handleEscape` and `OverlayController.dismissIfClickOutside` test the pointer against the whole window. With the pointer in the transparent 252 points and no card open, Esc collapses the dock. A click in the same area does not close an open card.
17. **`Ajustes do sistema…` opens a window that is almost empty.** The SwiftUI `Settings` scene in `UsageDockApp.swift` contains only the color legend.
18. **A long reason is cut to two lines.** In the list `Fora da fila` of `SettingsModal`, a long message loses its end, which is where the instruction is.
19. **The pace text has no explanation.** A card can read `7.8% déficit` with no legend. The number uses a decimal point in a Portuguese interface (`UsagePace.summary`).
20. **The rule that removes a ring depends on pieces of text.** `UNWATCH_HINTS` in `collector.py` and `ProviderUsage.shouldPark` in `Models.swift` hold the same list of substrings. Any error that mentions `auth.json` removes the ring, even when the failure is temporary.

## Polish and accessibility

21. **VoiceOver announces every button as `Usage Dock`.** The label on the pill in `DockView.morphingPill` covers the labels of the rings. No ring exposes its percentage.
22. **Thirteen messages use em dashes.** One message is in `SettingsModal.swift` and twelve are in `collector.py`. The copy style of the project does not use em dashes.
23. **The interface mixes languages and time formats.** The card title reads `Claude Usage` in English while the rest of the card is in Portuguese (`PopoutView`). The time in the settings card follows the system format (`SettingsModal`).
24. **The dock stays above every window.** `OverlayController.show` puts the panel at the status bar level, on every Space, and over full-screen apps. The dock shows over full-screen video and on shared screens. Expanded, it covers 66 points of the right edge, where scroll bars are.
25. **The first position assumes five rings.** `OverlayController.init` computes the first vertical position for five rings. With another number of rings, a new install does not start centered.
26. **The dock can shake when you drag it away from the edge.** `OverlayController.drag` switches the shape of the dock on every pointer move near the edge. A user reported the shake in September 2026. It was not tested again.
27. **The collector does not read the newer OpenCode login store.** `_opencode_go_token` reads only `auth.json`. The README of Codenotch for Windows states that OpenCode 1.18 and later also keeps the login in `opencode.db`. This statement was not checked against the OpenCode documentation.

## Limits of scope

- **macOS only.** The interface uses AppKit and SwiftUI. The collector reads the macOS Keychain and macOS paths.
- **Right edge only.** `NotchEdge` in `CoupledShell.swift` has one case, `trailing`.
- **Brazilian Portuguese only.** The interface strings and the collector messages are fixed in the code. The project has no localization layer.
- **Undocumented APIs.** The collector calls endpoints that the providers do not document, and reads the login files of other apps. A provider can change or block an endpoint at any time.
- **Code that fits only the author's setup.** The Cursor card has a row named `Grokbot`, which is the share of Cursor spend on models whose name contains `grok` (`collect_cursor_grokbot`). The Codex fallback depends on the third-party app Codex Limits.

## Not verified

- The app was tested on one machine, an Intel Mac with macOS 15.7. It was not run on Apple silicon or on macOS 14.
- Multiple displays, full-screen apps, and sleep and wake were read in the code, not tested.
- Nobody checked whether macOS asks for the Accessibility permission on a new install. See the privacy section of the [README](../README.md#privacy).
- The readings of Command, Grok, Devin, and OpenCode were not compared with the dashboards of those providers.
- Memory use over time was not measured. One measurement showed 242 MB after three days of running.
