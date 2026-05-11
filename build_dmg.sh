#!/usr/bin/env bash
# build_dmg.sh — Build a macOS distributable DMG for DART.
#
# Usage:
#   bash build_dmg.sh          # version defaults to 1.0
#   bash build_dmg.sh 1.2      # explicit version
#
# Output: DART_v<version>.dmg in the project root
#
# Recipients need: macOS 12+, Python 3
# No code-signing is performed; recipients bypass Gatekeeper with right-click → Open.

set -euo pipefail

VERSION="${1:-1.0}"
APP_NAME="DART"
BUNDLE_ID="com.digitalgrinnell.dart"
DISPLAY_NAME="DART — Digital Asset Routing and Transformation"
DMG_NAME="${APP_NAME}_v${VERSION}.dmg"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DMG_OUT="$SCRIPT_DIR/$DMG_NAME"

STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT

APP_DIR="$STAGING/${APP_NAME}.app"
CONTENTS="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS/MacOS"
SRC_DIR="$CONTENTS/Resources/src"

echo "=== Building $DISPLAY_NAME v$VERSION ==="
echo

# ── 1. App bundle skeleton ─────────────────────────────────────────────────
echo "▶ Creating app bundle structure..."
mkdir -p "$MACOS_DIR" "$SRC_DIR"

# Info.plist
cat > "$CONTENTS/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>${APP_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>${BUNDLE_ID}</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>${DISPLAY_NAME}</string>
    <key>CFBundleVersion</key>
    <string>${VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>${VERSION}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

# ── 2. Launcher script (Contents/MacOS/DART) ─────────────────────────────────
# Opens a Terminal window that runs run.sh from inside the bundle.
# The Terminal window remains visible so users can see setup progress and errors.
cat > "$MACOS_DIR/$APP_NAME" << 'LAUNCHER'
#!/usr/bin/env bash
SRC="$(cd "$(dirname "$0")/../Resources/src" && pwd)"
osascript << APPLESCRIPT
tell application "Terminal"
    activate
    do script "cd '$SRC' && bash run.sh"
end tell
APPLESCRIPT
LAUNCHER
chmod +x "$MACOS_DIR/$APP_NAME"

# ── 3. Copy project source files into the bundle ──────────────────────────
echo "▶ Copying project files..."

rsync -a \
    --exclude='.venv/' \
    --exclude='.git/' \
    --exclude='.env' \
    --exclude='*.dmg' \
    --exclude='*.zip' \
    --exclude='logfiles/' \
    --exclude='*.pyc' \
    --exclude='__pycache__/' \
    "$SCRIPT_DIR/" "$SRC_DIR/"

echo "  ✓ $(find "$SRC_DIR" -type f | wc -l | tr -d ' ') files copied"

# ── 4. Create compressed DMG ──────────────────────────────────────────────
echo "▶ Creating DMG (this may take a moment)..."

# Remove any stale output first
rm -f "$DMG_OUT"

hdiutil create \
    -volname "$DISPLAY_NAME" \
    -srcfolder "$STAGING" \
    -ov \
    -format UDZO \
    "$DMG_OUT"

echo
echo "✅ DMG created: $DMG_OUT"
echo "   Size: $(du -sh "$DMG_OUT" | cut -f1)"
echo
echo "────────────────────────────────────────────────"
echo " Distribution notes for recipients"
echo "────────────────────────────────────────────────"
echo " Prerequisites (one-time, if not already installed):"
echo "   • Python 3:  https://python.org/downloads  (or via Homebrew: brew install python)"
echo
echo " Installation:"
echo "   1. Open $DMG_NAME"
echo "   2. Drag DART.app to your Applications folder (or any convenient location)"
echo "   3. Eject the DMG"
echo
echo " First launch (Gatekeeper — unsigned app):"
echo "   • Right-click DART.app → Open → click Open in the dialog"
echo "   • Subsequent launches can use a normal double-click"
echo
echo " What happens on first launch:"
echo "   • A Terminal window opens and sets up a Python virtual environment"
echo "   • Dependencies install automatically (may take a few minutes)"
echo "   • The DART window opens when setup is complete"
echo "   • The Terminal window can be left open or minimised while using the app"
echo "────────────────────────────────────────────────"
