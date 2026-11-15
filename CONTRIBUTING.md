# Contributing to Usage Dock

Usage Dock is a personal tool that is being prepared for open source. This guide explains how to report a problem, how to set up the project, and what a pull request needs.

Everyone who takes part follows the [code of conduct](CODE_OF_CONDUCT.md).

## Know the status first

- The project has no license yet. The maintainer has not set the terms for outside contributions. Open an issue before you write a large change.
- The project has one maintainer and no release schedule.
- Many defects are already known. Read [docs/KNOWN-LIMITATIONS.md](docs/KNOWN-LIMITATIONS.md) before you report one.

Issues and pull requests are welcome in English or in Portuguese.

## Report a bug

Open an issue with the bug report form. The form asks for the provider, your macOS version, and the steps that reproduce the problem.

Protect your own data when you report.

- Never paste a token, an API key, or the content of a login file.
- Before you paste collector output, check it. The output has usage numbers, plan names, and error messages, which you may prefer to keep private.
- Crop every screenshot to the dock. A full-screen capture shows your other windows.

To report a vulnerability, do not open an issue. Follow [SECURITY.md](SECURITY.md).

## Suggest a feature

Open an issue with the feature request form. Describe the problem before the solution. A request for a new provider is more useful when it says where that provider's tool keeps its login and which request returns the usage.

## Set up the project

You need macOS 14 or later, Swift 5.10 or later, and Python 3.9 or later.

1. Clone the repository and run the collector tests.

   ```sh
   git clone https://github.com/louiemota/usage-dock.git
   cd usage-dock
   python3 -m unittest discover -s tests
   ```

2. Replace the four path constants that the [README](README.md#build-from-source) lists. Without that edit, the app cannot find the collector.
3. Build the app.

   ```sh
   scripts/build.sh
   ```

Do not commit your edits of the four path constants. They point to your machine.

### Rebuild while the app runs

`scripts/build.sh` overwrites the app at the `LIVE` path. Quit the running app before you open the new build.

```sh
pkill -x UsageDock
scripts/build.sh
open "$HOME/Applications/UsageDock.app"
```

When a copy of the app starts, it quits every other running copy that has the same bundle identifier. Do not start a second copy to compare two builds side by side.

### Run the collector alone

The collector does not need the app. It prints one JSON object and exits.

```sh
USAGE_DOCK_SKIP=grok python3 collector.py
```

Each run calls the real provider APIs with your logins. Keep `USAGE_DOCK_SKIP=grok` unless you work on the Grok reading, because that reading can rewrite `~/.grok/auth.json`.

## Make a change

Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) first. To add a provider, follow [docs/ADDING-A-PROVIDER.md](docs/ADDING-A-PROVIDER.md).

The repository has no formatter and no linter configuration. Match the style of the file that you edit.

Rules for the collector, `collector.py`:

- Use only the Python standard library. The collector has to run on Python 3.9.
- Never print or store a credential. The JSON output is saved to disk by the app.
- Call only the provider that owns the login. Do not add telemetry.
- Do not write to a provider's login file.
- Keep the parsing of a provider response in a function that uses no network, so a test can call it. `fill_claude_row` is an example.

Rules for the app, `UsageDock/Sources/UsageDock`:

- The interface strings are in Brazilian Portuguese, and the project has no localization layer. Write a new string in the same language as the strings around it. Do not use em dashes in interface text.
- Keep the attribution comments in `CoupledShell.swift` and `UsagePace.swift`.
- `refs/SPEC.md` is the design specification of the dock, in Portuguese. Its last two sections list the changes that the project forbids and the mistakes that broke the dock before. Read them before you change the layout or the event handling.

## Check your change

Run both commands before you open a pull request.

```sh
python3 -m unittest discover -s tests
```

```sh
cd UsageDock && swift build -c release
```

The tests end with `OK`. The build ends with `Build complete!` and prints no warning. To run one test class, name it.

```sh
python3 -m unittest tests.test_collector.ClaudeRowTests
```

The Swift code has no automated tests. If you change the interface, build the app, use the dock, and describe in the pull request what you checked by hand.

## Open a pull request

1. Create a branch from `main`.
2. Keep one change per pull request.
3. Write the commit summary as a short sentence that says what changed. The history uses Portuguese, and English is also fine.
4. Add a test for every change in the collector.
5. Update the documents that your change makes wrong: the two README files, `docs/`, `AGENTS.md`, `llms.txt`, and `CHANGELOG.md`. If your change fixes a known limitation, mark the item as fixed in `docs/KNOWN-LIMITATIONS.md` and keep its number.
6. Fill in the pull request template.
