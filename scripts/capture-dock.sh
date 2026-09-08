#!/bin/zsh
# Captura a faixa direita do iMac (3200x1800 pt). Rerrode depois de cada mudança visual.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/refs/baseline"
mkdir -p "$OUT"
STAMP="${1:-$(date +%Y%m%d-%H%M%S)}"
FULL="$OUT/ours-${STAMP}-full.png"
STRIP="$OUT/ours-${STAMP}-right.png"
screencapture -x "$FULL"
# 5K scaled 2x: 6400x3600. Faixa direita de 400 pt lógicos = 800 px: cobre pílula (66)
# + gap (12) + popout (240) com folga, então hover/gear também aparecem no recorte.
sips -c 3600 800 "$FULL" --cropOffset 0 5600 --out "$STRIP" >/dev/null
echo "$STRIP"
echo "full $FULL"
