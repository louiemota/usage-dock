# Third-party notices

Usage Dock is under the MIT License, in [LICENSE](LICENSE). This file records the material in the repository that comes from other people: code that derives from another project and the logos of other companies.

## Codenotch

Two files derive from [Codenotch](https://github.com/vinzdg/codenotch), by Vinz.

| File | Relation to Codenotch |
|---|---|
| `UsageDock/Sources/UsageDock/CoupledShell.swift` | `SideNotchShape` follows the shape of the same name in Codenotch, `Sources/Notch/SideNotchShape.swift`. The path in this repository draws the trailing edge only |
| `UsageDock/Sources/UsageDock/UsagePace.swift` | `UsagePace` is a port of the Codenotch type of the same name, with labels in Brazilian Portuguese |

Codenotch is distributed under the MIT License. The copyright notice and the permission notice follow, as the license requires.

```text
MIT License

Copyright (c) 2026 Vinz

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

The license text above was copied from the `LICENSE` file of the Codenotch repository on 2026-11-14.

Other parts of Usage Dock follow the behavior of Codenotch without declaring copied code. The code comments name those parts. They include the refresh cadence, keeping the last good reading, the hover delays, the color of the shell, and the layout of the Codex statistics.

## Logos and names

The app displays the logos of the providers that it reads.

| File | Logo |
|---|---|
| `UsageDock/Sources/UsageDock/LogoAssets.swift` | Codex, embedded as a PNG |
| `UsageDock/Sources/UsageDock/Resources/claude.svg` | Claude |
| `UsageDock/Sources/UsageDock/Resources/commandcode.svg` | Command Code |
| `UsageDock/Sources/UsageDock/Resources/cursor-mark.svg` | Cursor |
| `UsageDock/Sources/UsageDock/Resources/devin.svg` | Devin |
| `UsageDock/Sources/UsageDock/Resources/opencode.svg` | OpenCode |
| `UsageDock/Sources/UsageDock/Resources/xai.svg` | xAI, used for the Grok ring |

The names and the logos are trademarks of their owners. Usage Dock uses them only to identify each provider, and it is not affiliated with or endorsed by any of them. The MIT License of Usage Dock does not cover the names or the logos.

The repository does not record where each logo file came from. A comment in `LogoAssets.swift` states that `xai.svg` is CC0. That statement was not checked against a source.
