# Usage Dock

HUD de cota na borda direita do macOS Sequoia (15). Cinco anéis — Codex, OpenCode Go, Command Code GOAT, Cursor, SuperGrok — soldados no bezel.

A casca (pílula com scoop, peek em D-tab, hover com disco branco) é da mesma família do [Codenotch](https://github.com/vinzdg/codenotch) do Vinz ([@hivinz_](https://x.com/hivinz_)), agora MIT. Não é um clone: o Codenotch é macOS 26, quatro bordas, notch de hardware e “o agente ainda está trabalhando?”. Aqui o alvo é Sequoia, cinco anéis incluindo Command Code, e o dock **não** recolhe no clique do editor.

Ver `refs/SPEC.md` para o que está travado e `refs/CODENOTCH.md` para o que o binário mostrava antes do source.

## O que lê

| Anel | Fonte |
|---|---|
| Codex | CLI ao vivo, senão histórico do Codex Limits |
| OpenCode | Go plan (`OPENCODE_GO_API_KEY` ou `~/.local/share/opencode/auth.json`) |
| Command | `~/.commandcode/auth.json`, `GET /alpha/*` — o mesmo caminho do app Command Code |
| Cursor | sessão do editor em `state.vscdb` |
| Grok | pool SuperGrok via OAuth em `~/.grok/auth.json` |

## Build

```sh
USAGE_DOCK_OUTPUT=/Users/imac/Documents/usage-dock/UsageDock.app scripts/build.sh
pkill -x UsageDock; open UsageDock.app
```

O coletor é `collector.py`, chamado a cada 30s pelo app.
