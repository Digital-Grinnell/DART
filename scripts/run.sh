#!/usr/bin/env bash
# DART - Digital Asset Routing and Transformation - Quick Launch Script
# Sets up a Python virtual environment and launches the Flet app.

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
    cd "$ROOT_DIR"

echo "=== DART — Digital Asset Routing and Transformation ==="
echo

# Check if running from a read-only volume
    if [ ! -w "$ROOT_DIR" ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "❌ ERROR: Cannot run from a read-only location"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    echo "It looks like you're running DART from a mounted DMG or"
    echo "other read-only volume. DART needs to create files and"
    echo "cannot run from this location."
    echo
    echo "📋 Installation Required:"
    echo
    echo "   1. Copy DART.app to your Applications folder"
    echo "      (or Desktop, or any writable location)"
    echo
    echo "   2. Eject the DMG"
    echo
    echo "   3. Run DART from the copied location"
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    echo "Press any key to close this window..."
    read -n 1 -s
    exit 1
fi

PYTHON_CMD="python3"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv .venv
    echo "✓ Virtual environment created"
    echo
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
echo "✓ Virtual environment activated"
echo

# Install / upgrade dependencies
echo "Installing dependencies..."
.venv/bin/python -m pip install --upgrade pip --quiet
.venv/bin/python -m pip install -r python_requirements.txt --quiet
echo "✓ Dependencies installed"
echo

# Launch the app
echo "Launching DART..."
echo
.venv/bin/python app.py
