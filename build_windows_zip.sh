#!/usr/bin/env bash
# build_windows_zip.sh — Build a Windows distributable ZIP for DART.
#
# Usage:
#   bash build_windows_zip.sh          # version defaults to 1.0
#   bash build_windows_zip.sh 1.2      # explicit version
#
# Output: DART_v<version>_Windows.zip in the project root
#
# Recipients need: Windows 10/11, Python 3 (from python.org).
# No code-signing is performed.

set -euo pipefail

VERSION="${1:-1.0}"
APP_NAME="DART"
DISPLAY_NAME="DART — Digital Asset Routing and Transformation"
ZIP_NAME="${APP_NAME}_v${VERSION}_Windows.zip"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZIP_OUT="$SCRIPT_DIR/$ZIP_NAME"

STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT

STAGE_DIR="$STAGING/${APP_NAME}_v${VERSION}"

echo "=== Building $DISPLAY_NAME v$VERSION (Windows ZIP) ==="
echo

# ── 1. Create staging directory ────────────────────────────────────────────
echo "▶ Creating staging directory..."
mkdir -p "$STAGE_DIR"

# ── 2. Copy project source files ──────────────────────────────────────────
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
    "$SCRIPT_DIR/" "$STAGE_DIR/"

echo "  ✓ $(find "$STAGE_DIR" -type f | wc -l | tr -d ' ') files copied"

# ── 3. Create the ZIP ──────────────────────────────────────────────────────
echo "▶ Creating ZIP..."
rm -f "$ZIP_OUT"
(cd "$STAGING" && zip -r "$ZIP_OUT" "${APP_NAME}_v${VERSION}" -x "*.DS_Store")

echo
echo "✅ ZIP created: $ZIP_OUT"
echo "   Size: $(du -sh "$ZIP_OUT" | cut -f1)"
echo
echo "────────────────────────────────────────────────"
echo " Distribution notes for Windows recipients"
echo "────────────────────────────────────────────────"
echo " Prerequisites (one-time, if not already installed):"
echo "   • Python 3:  https://www.python.org/downloads/"
echo "     ⚠️  During install, check \"Add Python to PATH\""
echo
echo " Installation:"
echo "   1. Extract DART_v${VERSION}_Windows.zip to a convenient folder"
echo "   2. Open the extracted ${APP_NAME}_v${VERSION} folder"
echo
echo " First launch:"
echo "   • Double-click run.bat"
echo "   • A console window opens and installs dependencies automatically"
echo "     (first run only — may take a few minutes)"
echo "   • The DART window opens when setup is complete"
echo "   • Leave the console window open while using DART"
echo "────────────────────────────────────────────────"
