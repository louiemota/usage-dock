# Security policy

Usage Dock reads the login files of other tools and calls provider APIs with the tokens in those files. A defect in that code can expose a credential, so the project treats those reports as private.

## Supported versions

Usage Dock has no tagged release. Security fixes go to the `main` branch only.

## Report a vulnerability

Do not open a public issue for a vulnerability.

1. Open the [private report form](https://github.com/louiemota/usage-dock/security/advisories/new) of this repository. The same form is under **Security**, then **Report a vulnerability**.
2. Describe what an attacker can do and the steps that reproduce the problem.
3. Add the commit hash that you tested, your macOS version, and the provider involved.

Do not include a real token, an API key, or the content of a login file. Replace each secret with a placeholder such as `REDACTED`.

If the form is not available, open an issue that asks for a private channel. Do not describe the vulnerability in that issue.

The project has one maintainer and no guaranteed response time.

## What counts as a vulnerability

These reports are in scope.

- The collector or the app exposes a token, an API key, or a login file. The places to check are the collector output, `~/Library/Application Support/UsageDock/last-providers.json`, the user defaults of `com.louiemota.usagedock`, and `~/.cache/usage-dock/codex-profile.json`.
- The collector sends a credential to a host other than the provider that owns it.
- The collector damages a login file. The Grok reading is the only code that writes one, in `persist_grok_slot`.
- A crafted provider response or a crafted local file makes the collector or the app run code.

These reports are out of scope.

- A vulnerability in a provider's API or in a provider's tool. Report it to that provider.
- An item that [docs/KNOWN-LIMITATIONS.md](docs/KNOWN-LIMITATIONS.md) already lists, unless you found a way to exploit it.

Usage Dock reads files that any process of the same macOS user can already read. A process that runs as that user does not need Usage Dock to reach those files.

## How Usage Dock handles credentials

The privacy section of the [README](README.md#privacy) lists every file that the collector reads, every host that it calls, and every file that it writes.
