#!/usr/bin/env python3
"""Process only the frozen 15 remaining Cyclone yearbooks, using local PDF staging."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from operations.collections.cyclone_2026.process_cyclone_yearbooks import (
    DEFAULT_PROJECT,
    main as process,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    hidden = DEFAULT_PROJECT / ".DART-working-directory"
    argv = ["--only-ids", str(hidden / "cyclone_remaining_15.json"),
            "--sheet", str(hidden / "cyclone_remaining_metadata.csv")]
    if args.apply:
        argv.append("--apply")
    if args.limit is not None:
        if args.limit <= 0:
            parser.error("--limit must be positive")
        argv.extend(["--limit", str(args.limit)])
    return process(argv)


if __name__ == "__main__":
    sys.exit(main())
