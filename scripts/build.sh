#!/bin/zsh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/UsageDock"
swift build --disable-sandbox -c release --arch x86_64 --arch arm64 2>/dev/null \
  || swift build --disable-sandbox -c release
BIN="$(swift build --disable-sandbox -c release --show-bin-path)/UsageDock"
STAGE=/private/tmp/UsageDock.app
LIVE=/Users/imac/Applications/UsageDock.app
OUTPUT_APP="${USAGE_DOCK_OUTPUT:-}"
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
mkdir -p "$(dirname "$LIVE")"
ditto "$STAGE" "$LIVE"
xattr -cr "$LIVE" 2>/dev/null || true
codesign --verify --deep "$LIVE"
if [[ -n "$OUTPUT_APP" && "$OUTPUT_APP" != "$LIVE" ]]; then
  mkdir -p "$(dirname "$OUTPUT_APP")"
  ditto "$STAGE" "$OUTPUT_APP"
  xattr -cr "$OUTPUT_APP" 2>/dev/null || true
fi
echo "built $LIVE"
