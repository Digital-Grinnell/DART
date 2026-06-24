#!/usr/bin/env bash
# build_dmg.sh — Build a macOS distributable DMG for DART.
#
# Usage:
#   bash build_dmg.sh          # auto-increments patch version from VERSION file
#   bash build_dmg.sh 2.3.0    # explicit version (updates VERSION file)
#
# Output: DART_v<version>.dmg in the project root
#
# New approach: Creates a DMG with an auto-installer that installs to ~/DART/
# No admin permissions required - installs to user's home directory
# Recipients need: macOS 12+, Python 3

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION_FILE="$ROOT_DIR/VERSION"

# Function to increment patch version (e.g., 2.2.1 -> 2.2.2)
increment_version() {
    local version=$1
    local major minor patch
    
    # Parse version into major.minor.patch
    if [[ $version =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
        major="${BASH_REMATCH[1]}"
        minor="${BASH_REMATCH[2]}"
        patch="${BASH_REMATCH[3]}"
        patch=$((patch + 1))
        echo "${major}.${minor}.${patch}"
    else
        echo "Error: Invalid version format in VERSION file: $version" >&2
        exit 1
    fi
}

# Read current version from VERSION file
if [ ! -f "$VERSION_FILE" ]; then
    echo "Error: VERSION file not found at $VERSION_FILE" >&2
    exit 1
fi

CURRENT_VERSION=$(cat "$VERSION_FILE" | tr -d '[:space:]')

# Determine version to use
if [ $# -eq 0 ]; then
    # No argument provided - auto-increment patch version
    VERSION=$(increment_version "$CURRENT_VERSION")
    echo "Auto-incrementing version: $CURRENT_VERSION → $VERSION"
else
    # User provided explicit version
    VERSION="$1"
    echo "Using provided version: $VERSION"
fi

# Write new version to VERSION file
echo "$VERSION" > "$VERSION_FILE"
echo "Updated VERSION file: $VERSION"

APP_NAME="DART"
DISPLAY_NAME="DART — Digital Asset Routing and Transformation"
DMG_NAME="${APP_NAME}_v${VERSION}.dmg"
DMG_OUT="$ROOT_DIR/$DMG_NAME"

STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT

DMG_CONTENT_DIR="$STAGING/DART_Installer"
SRC_DIR="$DMG_CONTENT_DIR/dart_files"

echo "=== Building $DISPLAY_NAME v$VERSION ==="
echo

# ── 1. Create DMG content directory ───────────────────────────────────────
echo "▶ Creating DMG content structure..."
mkdir -p "$SRC_DIR"

# ── 2. Create auto-installer script ──────────────────────────────────────
echo "▶ Creating installer script..."
cat > "$DMG_CONTENT_DIR/Install DART.command" << 'INSTALLER'
#!/usr/bin/env bash
# DART Auto-Installer — Installs DART to ~/DART/
# No admin permissions required

set -e

APP_NAME="DART"
VERSION="__VERSION__"
INSTALL_DIR="$HOME/DART"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$SCRIPT_DIR/dart_files"

echo "════════════════════════════════════════════════"
echo " DART Installer v${VERSION}"
echo "════════════════════════════════════════════════"
echo

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ ERROR: Python 3 is not installed"
    echo
    echo "Please install Python 3 first:"
    echo "  • Download from: https://python.org/downloads"
    echo "  • Or install via Homebrew: brew install python"
    echo
    read -p "Press Enter to exit..."
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"
echo

# Check if DART is already installed
if [ -d "$INSTALL_DIR" ]; then
    echo "⚠️  DART is already installed at: $INSTALL_DIR"
    echo
    read -p "Overwrite existing installation? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        read -p "Press Enter to exit..."
        exit 0
    fi
    echo "Removing old installation..."
    rm -rf "$INSTALL_DIR"
fi

# Create installation directory
echo "▶ Installing DART to: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# Copy all files
echo "▶ Copying files..."
rsync -a "$SRC_DIR/" "$INSTALL_DIR/"

# Create launcher script
echo "▶ Creating launcher..."
cat > "$INSTALL_DIR/Launch DART.command" << 'LAUNCHER'
#!/usr/bin/env bash
cd "$(dirname "$0")"
bash scripts/run.sh
LAUNCHER
chmod +x "$INSTALL_DIR/Launch DART.command"

# Create desktop alias (optional)
DESKTOP="$HOME/Desktop"
if [ -d "$DESKTOP" ]; then
    echo "▶ Creating desktop shortcut..."
    ln -sf "$INSTALL_DIR/Launch DART.command" "$DESKTOP/Launch DART"
fi

echo
echo "════════════════════════════════════════════════"
echo " ✅ Installation Complete!"
echo "════════════════════════════════════════════════"
echo
echo "DART has been installed to:"
echo "  $INSTALL_DIR"
echo
echo "To launch DART:"
echo "  • Double-click: Launch DART (on your Desktop)"
echo "  • Or navigate to: $INSTALL_DIR"
echo "    and double-click: Launch DART.command"
echo
echo "First launch notes:"
echo "  • A Terminal window will open"
echo "  • Dependencies install automatically (1-2 min)"
echo "  • The DART window opens when ready"
echo "  • Keep Terminal window open while using DART"
echo
echo "════════════════════════════════════════════════"
echo
read -p "Press Enter to finish..."
INSTALLER

# Replace version placeholder
sed -i '' "s/__VERSION__/$VERSION/g" "$DMG_CONTENT_DIR/Install DART.command"
chmod +x "$DMG_CONTENT_DIR/Install DART.command"

# ── 3. Copy project source files ──────────────────────────────────────────
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
    "$ROOT_DIR/" "$SRC_DIR/"

echo "  ✓ $(find "$SRC_DIR" -type f | wc -l | tr -d ' ') files copied"

# ── 4. Fix python_requirements.txt for distribution ──────────────────────
echo "▶ Fixing python_requirements.txt for distribution..."
# Remove the editable install line for common-DG-utilities since we bundle it directly
if [ ! -f "$SRC_DIR/python_requirements.txt" ]; then
    echo "Error: python_requirements.txt not found in staged DMG content at $SRC_DIR" >&2
    exit 1
fi
grep -v "^-e.*common-DG-utilities" "$SRC_DIR/python_requirements.txt" > "$SRC_DIR/python_requirements.txt.tmp"
mv "$SRC_DIR/python_requirements.txt.tmp" "$SRC_DIR/python_requirements.txt"
echo "  ✓ Removed editable common-DG-utilities reference"

# ── 5. Copy common-DG-utilities ──────────────────────────────────────────
echo "▶ Copying common-DG-utilities..."

COMMON_UTILS_SRC="$ROOT_DIR/../common-DG-utilities/common_dg_utilities"
if [ -d "$COMMON_UTILS_SRC" ]; then
    rsync -a \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        "$COMMON_UTILS_SRC" "$SRC_DIR/"
else
    echo "  ⚠️  WARNING: common-DG-utilities not found at $COMMON_UTILS_SRC"
    echo "     The DMG may not function correctly without these utilities."
    echo "     Expected location: $ROOT_DIR/../common-DG-utilities/"
fi

# ── 6. Create README in DMG ───────────────────────────────────────────────
echo "▶ Creating DMG README..."
cat > "$DMG_CONTENT_DIR/README.txt" << 'DMGREADME'
╔════════════════════════════════════════════════════╗
║  DART - Digital Asset Routing and Transformation  ║
╚════════════════════════════════════════════════════╝

INSTALLATION INSTRUCTIONS
═════════════════════════

1. Double-click: "Install DART.command"

2. Follow the prompts in the Terminal window

3. Installation completes in seconds

4. Find "Launch DART" on your Desktop


WHAT IT DOES
════════════

• Installs DART to: ~/DART/
• No admin permissions required
• Includes all dependencies
• Creates desktop shortcut


PREREQUISITES
═════════════

Python 3 must be installed:
  • Download: https://python.org/downloads
  • Or: brew install python


FIRST LAUNCH
════════════

• Terminal window opens automatically
• Dependencies install (first time only, 1-2 min)
• DART application opens when ready
• Keep Terminal open while using DART


SUPPORT
═══════

Repository: https://github.com/Digital-Grinnell/DART
Documentation: See INSTALLATION.md in installed folder

DMGREADME

# ── 7. Create compressed DMG ──────────────────────────────────────────────
echo "▶ Creating DMG (this may take a moment)..."

# Remove any stale output first
rm -f "$DMG_OUT"

hdiutil create \
    -volname "$DISPLAY_NAME" \
    -srcfolder "$DMG_CONTENT_DIR" \
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
echo " ✅ EASY INSTALLATION (no admin required):"
echo "   1. Open $DMG_NAME"
echo "   2. Double-click: 'Install DART.command'"
echo "   3. Follow prompts in Terminal window"
echo "   4. Find 'Launch DART' on your Desktop"
echo
echo " 📍 Installs to: ~/DART/"
echo "    (No Applications folder permissions needed)"
echo
echo " 🔐 Gatekeeper Bypass (unsigned app):"
echo "   • If 'Install DART.command' won't open:"
echo "   • Right-click → Open → click 'Open'"
echo "   • (Only needed once)"
echo
echo " 📦 Prerequisites:"
echo "   • Python 3: https://python.org/downloads"
echo "     Or via Homebrew: brew install python"
echo
echo " 🚀 First Launch:"
echo "   • Terminal opens automatically"
echo "   • Dependencies install (1-2 min, first time only)"
echo "   • DART window opens when ready"
echo "════════════════════════════════════════════════"
