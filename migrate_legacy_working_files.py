#!/usr/bin/env python3
"""
One-time helper to migrate legacy DART-generated artifacts into
.DART-working-directory for older projects.

Default mode is DRY RUN (no changes). Use --apply to move files.

What this migrates:
- root-level dart_settings.json
- root-level DART_* artifacts
- root-level csvdiff_* artifacts
- recursive *.backup_* files outside .DART-working-directory
- root-level DART_*.html and csvdiff_*.html (legacy report patterns)

Notes:
- This intentionally does NOT move arbitrary *.html files.
- Files are moved into .DART-working-directory/legacy-migrated/
  with relative paths preserved.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Iterable, List, Tuple

ROOT_PATTERNS = [
    "dart_settings.json",
    "DART_*",
    "csvdiff_*",
    "DART_*.html",
    "csvdiff_*.html",
]

EXCLUDED_PARTS = {
    ".DART-working-directory",
    ".git",
    "__pycache__",
    ".venv",
    "logfiles",
}


def is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_PARTS for part in path.parts)


def unique_target(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def collect_candidates(working_dir: Path) -> List[Path]:
    candidates: List[Path] = []

    # Root-level legacy artifacts.
    for pattern in ROOT_PATTERNS:
        for p in working_dir.glob(pattern):
            if p.is_file() and not is_excluded(p):
                candidates.append(p)

    # Legacy backup artifacts may be nested (e.g., _data/*.backup_*).
    for p in working_dir.rglob("*.backup_*"):
        if p.is_file() and not is_excluded(p):
            candidates.append(p)

    # Dedupe while preserving order.
    seen = set()
    unique: List[Path] = []
    for p in candidates:
        rp = str(p.resolve())
        if rp not in seen:
            seen.add(rp)
            unique.append(p)

    return unique


def build_moves(working_dir: Path, files: Iterable[Path]) -> List[Tuple[Path, Path]]:
    dart_dir = working_dir / ".DART-working-directory"
    migration_root = dart_dir / "legacy-migrated"

    moves: List[Tuple[Path, Path]] = []
    for src in files:
        rel = src.relative_to(working_dir)
        dest = unique_target(migration_root / rel)
        moves.append((src, dest))

    return moves


def apply_moves(moves: Iterable[Tuple[Path, Path]], dry_run: bool) -> int:
    moved = 0
    for src, dst in moves:
        print(f"MOVE {src} -> {dst}")
        if dry_run:
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        moved += 1

    return moved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate legacy DART artifacts into .DART-working-directory",
    )
    parser.add_argument(
        "working_dir",
        nargs="?",
        default=".",
        help="Working folder to scan (default: current directory)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry run)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    working_dir = Path(args.working_dir).expanduser().resolve()

    if not working_dir.exists() or not working_dir.is_dir():
        print(f"Error: directory not found: {working_dir}")
        return 1

    dry_run = not args.apply

    print("=" * 72)
    print("Legacy DART Artifact Migration")
    print("=" * 72)
    print(f"Working folder: {working_dir}")
    print(f"Mode: {'DRY RUN' if dry_run else 'APPLY'}")
    print()

    files = collect_candidates(working_dir)
    if not files:
        print("No legacy artifacts found outside .DART-working-directory.")
        return 0

    moves = build_moves(working_dir, files)
    moved = apply_moves(moves, dry_run)

    print()
    print("-" * 72)
    if dry_run:
        print(f"Dry run complete. {len(moves)} file(s) would be moved.")
        print("Re-run with --apply to perform the migration.")
    else:
        print(f"Migration complete. {moved} file(s) moved.")
    print("Destination root: .DART-working-directory/legacy-migrated/")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
