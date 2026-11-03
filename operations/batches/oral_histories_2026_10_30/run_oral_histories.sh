#!/usr/bin/env bash
# Run one approved oral-history pipeline from the Mac.
set -euo pipefail
if [[ $(uname -s) != Darwin ]]; then
  printf 'ERROR: Run this on the Mac, not dg-landing.\n' >&2
  exit 1
fi
case "${1:-}" in
  1) collections=(alumni-1940s phpp-oral) ;;
  2) collections=(alumni-1950s alumni-1960s alumni-1970s alumni-1980s alumni-1990s alumni-2000s alumni-2010s) ;;
  *) printf 'Usage: bash operations/batches/oral_histories_2026_10_30/run_oral_histories.sh 1|2\n' >&2; exit 1 ;;
esac
part=$1
repo=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo"
printf 'Oral-history batch %s: %s\n' "$part" "${collections[*]}"
printf 'Uploads ON; overwrite OFF; OHM OFF; VTT conversion/linking ON for unambiguous pairs.\n'
printf 'Linux waits for an active DART writer, including Life. No rehearsals or per-collection prompts.\n'
printf 'Then: eligible core acceptance, snapshot pushes, local builds. No catalog changes or deployment.\n'
printf 'Keep this terminal open, Mac plugged in/lid open, and VPN connected. Quit desktop DART.\n'
printf 'Do not run batches 1 and 2 concurrently; run the other command on a later night or after completion.\n'
exec caffeinate -i .venv/bin/python -u -m scripts.run_headless_pipeline \
  --queue "/data/dart/config/oral-history-${part}-20261030.json" \
  --inventory "/data/dart/config/oral-history-${part}-20261030-inventory.json" \
  --oral-history-plan "/data/dart/config/oral-history-${part}-20261030-plan.json" \
  --unit "dart-oral-history-${part}-20261030" \
  --collections "${collections[@]}" \
  --apply
