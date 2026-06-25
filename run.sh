#!/usr/bin/env bash
# Compatibility launcher: keep legacy ./run.sh entry point working.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/scripts/run.sh" "$@"
