#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="Trinity"
BUILD_DIR="$PROJECT_DIR/.build/release"
BUNDLE_DIR="$PROJECT_DIR/dist"
APP_BUNDLE="$BUNDLE_DIR/$APP_NAME.app"
ICON_SOURCE_DIR="$PROJECT_DIR/.build/icon-assets"
ICONSET_DIR="$ICON_SOURCE_DIR/AppIcon.iconset"
ICON_PNG="$ICON_SOURCE_DIR/app-icon-1024.png"
ICON_ICNS="$ICON_SOURCE_DIR/$APP_NAME.icns"

cd "$PROJECT_DIR"
swift build -c release > /dev/null

rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"
swift Scripts/generate_app_icon.swift "$ICON_PNG"

for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$ICON_PNG" --out "$ICONSET_DIR/icon_${size}x${size}.png" >/dev/null
  retina_size=$((size * 2))
  sips -z "$retina_size" "$retina_size" "$ICON_PNG" --out "$ICONSET_DIR/icon_${size}x${size}@2x.png" >/dev/null
done

iconutil -c icns "$ICONSET_DIR" -o "$ICON_ICNS"

rm -rf "$APP_BUNDLE"
mkdir -p "$APP_BUNDLE/Contents/MacOS" "$APP_BUNDLE/Contents/Resources"

cp "$BUILD_DIR/$APP_NAME" "$APP_BUNDLE/Contents/MacOS/$APP_NAME"
chmod +x "$APP_BUNDLE/Contents/MacOS/$APP_NAME"
cp "$PROJECT_DIR/Info.plist" "$APP_BUNDLE/Contents/Info.plist"
cp "$ICON_ICNS" "$APP_BUNDLE/Contents/Resources/"
echo -n "APPL????" > "$APP_BUNDLE/Contents/PkgInfo"

codesign --force --deep --sign - "$APP_BUNDLE" >/dev/null 2>&1 || true

echo "$APP_BUNDLE"
