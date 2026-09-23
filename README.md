# Usage Dock

HUD de cota na borda direita do macOS Sequoia (15). Cinco anéis — Codex, OpenCode Go, Command Code GOAT, Cursor, SuperGrok — soldados no bezel.

A casca (pílula com scoop, peek em D-tab, hover com disco branco) é da mesma família do [Codenotch](https://github.com/vinzdg/codenotch) do Vinz ([@hivinz_](https://x.com/hivinz_)), agora MIT. Não é um clone: o Codenotch é macOS 26, quatro bordas, notch de hardware e “o agente ainda está trabalhando?”. Aqui o alvo é Sequoia, cinco anéis incluindo Command Code, e o dock **não** recolhe no clique do editor.

Ver `refs/SPEC.md` para o que está travado e `refs/CODENOTCH.md` para o que o binário mostrava antes do source.

## O que lê

| Anel | Fonte |
|---|---|
| Codex | CLI ao vivo, senão histórico do Codex Limits |
| OpenCode | Go plan (`~/.local/share/opencode/auth.json` — login no OpenCode; não usa o .env do Hermes) |
| Command | `~/.commandcode/auth.json`, `GET /alpha/*` — o mesmo caminho do app Command Code |
| Cursor | sessão do editor em `state.vscdb` |
| Grok | pool SuperGrok via OAuth em `~/.grok/auth.json` |

## Build

```sh
scripts/build.sh
pkill -x UsageDock; open /Users/imac/Applications/UsageDock.app
```

O live é `/Users/imac/Applications/UsageDock.app` — fora do File Provider. O login abre essa cópia. `Documents/usage-dock/UsageDock.app` é só checkout; depois de reboot o iCloud às vezes devolvia uma build velha.

O coletor é `collector.py`. O app pede números a cada 60s com o HUD em uso e a cada 5 min idle (Codenotch 1.13); acordar da máquina força um refresh. Sem login ou assinatura, o anel sai sozinho da fila (Ajustes → Vigiar para voltar). A última leitura boa fica em `~/Library/Application Support/UsageDock/`, então o reboot não zera os anéis.
