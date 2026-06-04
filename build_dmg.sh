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
# Now includes read-only filesystem detection.
cat > "$MACOS_DIR/$APP_NAME" << 'LAUNCHER'
#!/usr/bin/env bash
SRC="$(cd "$(dirname "$0")/../Resources/src" && pwd)"

# Check if running from a read-only volume (like a mounted DMG)
if [ ! -w "$SRC" ]; then
    osascript -e 'display dialog "⚠️ DART cannot run from a read-only volume.\n\n📋 Installation Required:\n\n1. Copy DART.app to your Applications folder\n   (or Desktop, or any writable location)\n\n2. Eject the DMG\n\n3. Run DART from the copied location\n\nDo not run directly from the mounted DMG!" buttons {"OK"} default button 1 with icon caution with title "DART Installation Required"'
    exit 1
fi

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
echo "════════════════════════════════════════════════"
echo " 📋 Distribution Instructions for Recipients"
echo "════════════════════════════════════════════════"
echo
echo " ⚠️  CRITICAL: Do NOT run directly from the DMG!"
echo "     The DMG is read-only and will cause errors."
echo
echo " ✅ Correct Installation (required):"
echo "   1. Open $DMG_NAME"
echo "   2. DRAG DART.app to your Applications folder"
echo "   3. Eject the DMG"
echo "   4. Run DART.app from Applications"
echo
echo " 🔐 First Launch (Gatekeeper for unsigned apps):"
echo "   • Right-click DART.app → Open → click 'Open'"
echo "   • Subsequent launches: normal double-click"
echo
echo " 📦 Prerequisites (one-time setup if not installed):"
echo "   • Python 3: https://python.org/downloads"
echo "     Or via Homebrew: brew install python"
echo
echo " 🚀 What happens on first launch:"
echo "   • Terminal window opens automatically"
echo "   • Python virtual environment created"
echo "   • Dependencies install (1-2 minutes)"
echo "   • DART window opens when ready"
echo "   • Terminal can be minimized during use"
echo "════════════════════════════════════════════════"
