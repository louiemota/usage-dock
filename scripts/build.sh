#!/bin/zsh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/UsageDock"
swift build --disable-sandbox -c release --arch x86_64 --arch arm64 2>/dev/null \
  || swift build --disable-sandbox -c release
BIN="$(swift build --disable-sandbox -c release --show-bin-path)/UsageDock"
STAGE=/private/tmp/UsageDock.app
OUTPUT_APP="${USAGE_DOCK_OUTPUT:-/Users/imac/Applications/UsageDock.app}"
rm -rf "$STAGE"
mkdir -p "$STAGE/Contents/MacOS" "$STAGE/Contents/Resources"
cp "$BIN" "$STAGE/Contents/MacOS/UsageDock"
cp "$ROOT/UsageDock/Info.plist" "$STAGE/Contents/Info.plist"
if [[ -d "$ROOT/UsageDock/Sources/UsageDock/Resources" ]]; then
  cp "$ROOT/UsageDock/Sources/UsageDock/Resources/"*.svg "$STAGE/Contents/Resources/" 2>/dev/null || true
fi
BIN_DIR="$(dirname "$BIN")"
# no SPM resource bundles — logos are copied from Sources/UsageDock/Resources above
xattr -cr "$STAGE"
codesign --force --deep --sign - "$STAGE"
mkdir -p "$(dirname "$OUTPUT_APP")"
ditto "$STAGE" "$OUTPUT_APP"
# Documents fica sob File Provider e o destino ganha xattr com.apple.fileprovider na hora,
# o que faz `codesign --deep` no destino falhar com "detritus". A assinatura vem do stage;
# aqui só verificamos.
xattr -cr "$OUTPUT_APP" 2>/dev/null || true
codesign --verify --deep "$OUTPUT_APP"
echo "built $OUTPUT_APP"
