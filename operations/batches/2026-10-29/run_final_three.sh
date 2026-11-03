#!/usr/bin/env bash
# Run on the Mac; keep this foreground process and VPN connected overnight.
set -euo pipefail
if [[ $(uname -s) != Darwin ]]; then
  printf 'ERROR: Run this on the Mac, not dg-landing.\n' >&2
  exit 1
fi
repo=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo"
if [[ ! -x .venv/bin/python ]]; then
  printf 'ERROR: Missing interpreter: %s/.venv/bin/python\n' "$repo" >&2
  exit 1
fi
printf 'Final three: vaf, coins, geology. Azure uploads ON; overwrite OFF; reserve 50 GiB.\n'
printf 'Then: eligible core acceptance, snapshot pushes, catalog updates, local SHOW builds.\n'
printf 'No deployment or cleanup. Quit DART and avoid concurrent SHOW edits/builds.\n'
printf 'Keep this terminal open, Mac powered/lid open, and VPN connected.\n'
exec caffeinate -i .venv/bin/python -u -m scripts.run_headless_pipeline \
  --queue /data/dart/config/final-three-20261029.json \
  --inventory /data/dart/config/final-three-20261029-inventory.json \
  --unit dart-final-three-20261029 \
  --collections vaf coins geology \
  --catalog-group 'Batch of 3' \
  --catalog-progress 'DART Complete, Pending Review of 3' \
  --apply
