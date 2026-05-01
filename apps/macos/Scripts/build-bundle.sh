#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="Trinity"
BUILD_DIR="$PROJECT_DIR/.build/release"
BUNDLE_DIR="$PROJECT_DIR/dist"
APP_BUNDLE="$BUNDLE_DIR/$APP_NAME.app"

cd "$PROJECT_DIR"
swift build -c release > /dev/null

rm -rf "$APP_BUNDLE"
mkdir -p "$APP_BUNDLE/Contents/MacOS" "$APP_BUNDLE/Contents/Resources"

cp "$BUILD_DIR/$APP_NAME" "$APP_BUNDLE/Contents/MacOS/$APP_NAME"
chmod +x "$APP_BUNDLE/Contents/MacOS/$APP_NAME"
cp "$PROJECT_DIR/Info.plist" "$APP_BUNDLE/Contents/Info.plist"
echo -n "APPL????" > "$APP_BUNDLE/Contents/PkgInfo"

codesign --force --deep --sign - "$APP_BUNDLE" >/dev/null 2>&1 || true

echo "$APP_BUNDLE"
