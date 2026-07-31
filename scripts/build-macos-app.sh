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

mkdir -p "$ICONSET"
ICON_RENDERER="$ROOT/dist/.render-heka-icon"
ICON_PACKER="$ROOT/dist/.pack-heka-icon"
clang -fobjc-arc -framework Cocoa "$ROOT/desktop/IconRenderer.m" -o "$ICON_RENDERER"
clang -fobjc-arc -framework Foundation "$ROOT/desktop/PackIcon.m" -o "$ICON_PACKER"
for spec in "16 icon_16x16" "32 icon_16x16@2x" "32 icon_32x32" "64 icon_32x32@2x" "128 icon_128x128" "256 icon_128x128@2x" "256 icon_256x256" "512 icon_256x256@2x" "512 icon_512x512" "1024 icon_512x512@2x"; do
  set -- $spec
  "$ICON_RENDERER" "$ICONSET/$2.png" "$1"
done
"$ICON_PACKER" "$RESOURCES/Heka.icns" \
  icp4 "$ICONSET/icon_16x16.png" \
  icp5 "$ICONSET/icon_32x32.png" \
  icp6 "$ICONSET/icon_32x32@2x.png" \
  ic07 "$ICONSET/icon_128x128.png" \
  ic08 "$ICONSET/icon_256x256.png" \
  ic09 "$ICONSET/icon_512x512.png" \
  ic10 "$ICONSET/icon_512x512@2x.png"
rm -f "$ICON_RENDERER" "$ICON_PACKER"

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
