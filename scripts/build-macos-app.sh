#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/dist/Heka.app"
CONTENTS="$APP/Contents"
RESOURCES="$CONTENTS/Resources"
ICONSET="$ROOT/dist/Heka.iconset"
LOCAL_DATA="$HOME/Library/Application Support/Heka"

rm -rf "$APP"
mkdir -p "$CONTENTS/MacOS" "$RESOURCES/heka"
cp "$ROOT/desktop/Info.plist" "$CONTENTS/Info.plist"
cp "$ROOT/server.py" "$RESOURCES/heka/"
cp -R "$ROOT/heka" "$RESOURCES/heka/"
cp -R "$ROOT/web" "$RESOURCES/heka/"
cp "$ROOT/.env.example" "$RESOURCES/heka/"

# Keep personal data and credentials outside the app package so the generated
# Heka.app can be safely shared. Existing local data is copied only once.
mkdir -p "$LOCAL_DATA"
if [ -f "$ROOT/heka.db" ] && [ ! -f "$LOCAL_DATA/heka.db" ]; then cp "$ROOT/heka.db" "$LOCAL_DATA/heka.db"; fi
if [ -f "$ROOT/.env" ] && [ ! -f "$LOCAL_DATA/.env" ]; then cp "$ROOT/.env" "$LOCAL_DATA/.env"; fi

# Quick Look can hang on some macOS releases. A missing custom .icns only
# affects the Finder icon, never startup, so keep packaging reliable first.
if [ "${HEKA_BUILD_ICON:-0}" = "1" ]; then
  mkdir -p "$ICONSET"
  ICON_RENDER_DIR="$(mktemp -d)"
  /usr/bin/qlmanage -t -s 1024 -o "$ICON_RENDER_DIR" "$ROOT/desktop/HekaIcon.svg" >/dev/null 2>&1
  ICON_SOURCE="$ICON_RENDER_DIR/HekaIcon.svg.png"
  for spec in "16 icon_16x16" "32 icon_16x16@2x" "32 icon_32x32" "64 icon_32x32@2x" "128 icon_128x128" "256 icon_128x128@2x" "256 icon_256x256" "512 icon_256x256@2x" "512 icon_512x512" "1024 icon_512x512@2x"; do
    set -- $spec
    /usr/bin/sips -z "$1" "$1" "$ICON_SOURCE" --out "$ICONSET/$2.png" >/dev/null
  done
  /usr/bin/iconutil -c icns "$ICONSET" -o "$RESOURCES/Heka.icns"
  rm -rf "$ICON_RENDER_DIR"
fi

if clang -fobjc-arc -framework Cocoa -framework WebKit "$ROOT/desktop/HekaApp.m" -o "$CONTENTS/MacOS/Heka"; then
  echo "Built native window launcher."
else
  # A local browser launcher keeps Heka usable when Xcode / Command Line Tools
  # are temporarily out of sync. It uses the same app data directory.
  cp "$ROOT/desktop/HekaLauncher.sh" "$CONTENTS/MacOS/Heka"
  chmod +x "$CONTENTS/MacOS/Heka"
  echo "Built browser launcher fallback (Swift toolchain unavailable)."
fi
echo "Built: $APP"
