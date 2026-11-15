# Usage Dock. Spec travada 31/08/2026 (revisada 08/09, v40; 23/09, 7 anéis)

Isto é o alvo. Não é o hivinz pixel a pixel. É a mesma família, nos nossos anéis (até 7: Codex, OpenCode, Command, Cursor, Grok, Devin, Claude), uma superfície só. Anel morto (sem assinatura, cancelado, cota 100%) sai do dock; a altura da pílula acompanha `providers.count`.

Revisão 01/09: o texto abaixo foi alinhado ao que está aprovado no ar. Onde a versão de 31/08 se contradizia (vibrancy vs sólida, gap vs track cheia, % branca vs cor da banda, gear no poço vs na coluna), vale o que está escrito agora.

Referência de família, não de clone: o vídeo público do side notch do Vinz, o designer do Codenotch. A mídia dele não fica neste repositório. Uma comparação visual com ela mede família (forma, ritmo, hover), não igualdade de marca ou de 3 anéis.

## O que o nosso dock é

- Uma superfície só: pílula, popout e ajustes no preto do Codenotch. Sem material leite no card e casca carvão no anel.
- Anel com track cheia (sem gap das 6h). O hivinz tem gap; a gente não copia.
- Hover: disco branco + logo escuro, scale curto.
- % branca no idle. 100% vermelho, na % também.

## Estados que têm de existir

1. Peek. D-tab ~14–16 pt de largura, ~46 pt de altura, no meio vertical da pílula expandida. Hover no peek abre. O desenho e o `hitTest` do `MovableRootView` têm de apontar para o mesmo lugar; o `morphingPill` vive num frame com a altura expandida e alinhamento `.center` para isso.
2. Idle acoplado. Pílula com scoop em cima e embaixo. Um anel por provedor vivo (até 7) + % abaixo de cada um. Track do anel visível em 0%. Logo branco no centro, sem quadrado preto, sem invert.
3. Hover no anel. Card à esquerda, caret no anel, fade+slide curto. Chip de plano se existir. Reset à direita. Barra. `N% usado`. Cifra em linha própria se vier no collector.
4. Clique no anel pina o card. Esc ou clique fora fecha o card. O dock **não** recolhe no clique do editor.
5. Gear. Ícone ~22 pt no fim da coluna, dentro do corpo preenchido da pílula, **antes** do scoop inferior, com um arco côncavo (`GearArc`) acima separando da coluna de anéis. Sem % e sem anel de cota. Clique abre o modal de ajustes. Não é um sexto anel e não é overlay fora da `CoupledShell` (isso faz a gear flutuar no vazio e cobrir o % do Grok). O "poço circular" de 31/08 foi testado e descartado.
6. 100%. Anel vermelho `#FF3B4E`, mais grosso, pulso. Texto da % no mesmo vermelho.
7. Recolher. Menu contextual, Ajustes, ou Esc com o card já fechado **e o ponteiro sobre o dock**. Esc no editor fecha card/ajustes, mas não recolhe. Não é clique no desktop.

## Tokens (família hivinz, escala até 7 anéis)

- Largura da pílula 62–68 pt.
- Ícone/anel 42–44 pt.
- Traço do anel ~3 pt, cap round, começo às 12h, sentido horário.
- Track cinza `#383B45` ou equivalente. Sempre um círculo completo. Sem gap das 6h.
- % 11–13 pt, rounded, branca. Só o anel carrega a banda: 0–39 verde, 40–69 amarelo, 70–89 laranja, 90–100 vermelho. Em 100% a % também fica vermelha.
- Espaço entre anéis maior que o espaço anel→%. O hivinz é arejado. Não empilhar.
- Gear ~22 pt, não 40 pt.
- Popout ~228–260 pt. Canto contínuo ~13 pt. Caret no centro do anel (`ringIconCenterY = ringIcon / 2`). Chip de plano no header quando o collector manda `plan`, altura fixa 16 pt para não desalinhar a estimativa de altura do hit-test.
- `gearZone` = ringSpacing + arco (7) + 2 + gear (22) + 2 = 45. Menor clipa 1 pt.

Valores atuais (v38): pílula 66, scoop 20, anel 44, linha 62, spacing 12, top pad 16, bottom pad 12, popout 240, gap 12.

## O que o hivinz faz e a gente não copia

- Três anéis. Nós temos até sete.
- Liquid Glass do macOS 26. Aqui é vibrancy do 15.
- Clique no desktop recolhe. Aqui some o HUD no meio do Cursor. Recolher é explícito.
- Lista de processos do Claude. Só renderizamos `sessions` se o collector mandar.

## Como prova

1. Relançar só o `UsageDock.app` do checkout. Matar qualquer `UsageDock` instalado em outro lugar.
2. `scripts/capture-dock.sh idle` e o mesmo para `hover`, `peek`, `gear`.
3. Comparar a faixa direita com a referência. O anel, o scoop, o card e o poço da gear têm de ser da mesma família. Marca e quantidade de anéis são nossos.

## Proibido até o diff fechar

- Mexer em token “no olho” sem recapturar.
- Reintroduzir PNG invertido no Codex/Grok.
- Dar anel, % ou 40 pt à gear como se fosse um sexto anel.
- Recolher o dock no clique fora ou no Esc vindo de outro app.
- Abrir outro chat pra “dar um jeitinho” no mesmo binário.

## Armadilhas (não regressar)

- `dismissIfClickOutside` não pode chamar `setCollapsed(true)`. Isso viola o estado 4. Fechar card e settings. Não recolher.
- `panelSize` fica no tamanho expandido mesmo no peek. Encolher a janela no collapse corta o spring.
- O ramo `curl == 0` do `SideNotchShape` (peek) usa arcos por tangente, iguais ao ramo com scoop. Arcos por ângulo com `clockwise` invertem no sistema flipado do SwiftUI e o D-tab vira duas meias-luas côncavas.
- `Documents` está sob File Provider: o `.app` ganha `com.apple.fileprovider` xattr e `codesign --deep` no destino falha com "detritus". Assinar no stage e só verificar no destino.
- Traço do anel precisa de inset `ringWidth/2`. Stroke na borda do frame de 42 pt some a trilha em 0%.
- Codex é PNG escuro. A receita que não vira quadrado é invert → `luminanceToAlpha` → invert → `colorMultiply`. Invert sozinho no SVG branco vira blob.
- `scoopPad` entra na altura da shell e no `place` do `OverlayController`. Padding SwiftUI extra em cima disso come o scoop ou desloca a pílula.
- O binário vivo costuma ser o instalado em `~/Applications/UsageDock.app`. Relançar o do checkout depois de matar o outro.
