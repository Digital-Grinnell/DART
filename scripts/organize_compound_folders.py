#!/usr/bin/env python3
"""
Reorganize a flat folder of GEMS/Alma migration files into per-compound
subfolders, applying DART's compound filename rules (see GEMS_FILENAME_RULES.md).

Why: DART creates exactly ONE compound object per folder. A flat export like

    objects/grinnell_21716-01.tiff
    objects/grinnell_21716-02.jpg
    objects/grinnell_21717-01.tiff
    ...

lumps every Alma compound under a single untitled folder-level compound.
This script moves each compound's files into their own subfolder:

    objects/grinnell_21716/grinnell_21716-01.tiff
    objects/grinnell_21716/grinnell_21716-02.jpg
    objects/grinnell_21717/grinnell_21717-01.tiff
    ...

Grouping rules mirror app.py's analyze_compound_objects():
- Numbered files: base = everything before the trailing number
  (regex ^(.+?)[\\s_\\-]*(\\d+)$ on the file stem).
- Unnumbered files: attached when the stem starts with a known numbered
  base followed by a separator (space, underscore, hyphen).
- Only bases shared by 2+ files become folders; everything else is left
  in place and reported.

Dry-run by default. Pass --apply to actually move files.

Usage:
    python3 scripts/organize_compound_folders.py /path/to/objects
    python3 scripts/organize_compound_folders.py /path/to/objects --apply
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ASSET_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp", ".webp",
    ".pdf",
    ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm",
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma",
    ".zip", ".tar", ".gz", ".7z", ".rar", ".bz2",
}

NUMBERED_RE = re.compile(r"^(.+?)[\s_\-]*(\d+)$")
SEPARATORS = (" ", "_", "-")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reorganize flat GEMS/Alma export files into per-compound subfolders (dry-run by default).",
    )
    parser.add_argument("folder", help="Flat folder containing the exported asset files")
    parser.add_argument("--apply", action="store_true", help="Actually move files (default is dry-run)")
    return parser.parse_args()


def normalized_base(stem: str) -> str | None:
    """Return the normalized (lowercase) base prefix for a numbered file stem, else None."""
    match = NUMBERED_RE.match(stem)
    if not match:
        return None
    return match.group(1).strip().lower()


def main() -> int:
    args = parse_args()
    source = Path(args.folder).expanduser().resolve()
    if not source.is_dir():
        print(f"Error: not a folder: {source}")
        return 1

    files = sorted(
        p for p in source.glob("*")
        if p.is_file() and p.suffix.lower() in ASSET_EXTENSIONS
    )
    if not files:
        print(f"No supported asset files found directly inside {source}")
        return 1

    # Pass 1: learn numbered bases (keep first-seen original case for folder names)
    numbered_bases: dict[str, str] = {}  # normalized -> display name
    file_bases: dict[Path, str] = {}     # file -> normalized base
    unnumbered: list[Path] = []

    for path in files:
        base = normalized_base(path.stem)
        if base is None:
            unnumbered.append(path)
            continue
        file_bases[path] = base
        if base not in numbered_bases:
            # Display name from the stem, original case, trailing separators stripped
            display = NUMBERED_RE.match(path.stem).group(1).strip().rstrip(" _-")
            numbered_bases[base] = display

    # Pass 2: attach unnumbered files that start with a known numbered base + separator
    still_unassigned: list[Path] = []
    for path in unnumbered:
        stem_lower = path.stem.strip().lower()
        best_match = None
        for base in numbered_bases:
            if stem_lower.startswith(base):
                remainder = stem_lower[len(base):]
                if not remainder or remainder[0] in SEPARATORS:
                    if best_match is None or len(base) > len(best_match):
                        best_match = base
        if best_match:
            file_bases[path] = best_match
        else:
            still_unassigned.append(path)

    # Group files by base; only bases with 2+ files become compound folders
    groups: dict[str, list[Path]] = {}
    for path, base in file_bases.items():
        groups.setdefault(base, []).append(path)

    movable = {base: paths for base, paths in groups.items() if len(base) >= 3 and len(paths) >= 2}
    skipped_groups = {base: paths for base, paths in groups.items() if base not in movable}

    print(f"Source folder: {source}")
    print(f"Asset files found: {len(files)}")
    print(f"Compound folders to create: {len(movable)}")
    print()

    moves: list[tuple[Path, Path]] = []
    errors = 0
    for base in sorted(movable):
        folder_name = numbered_bases.get(base, base)
        target_dir = source / folder_name
        for path in sorted(movable[base]):
            target = target_dir / path.name
            if target.exists():
                print(f"  ERROR: target already exists, skipping: {target}")
                errors += 1
                continue
            moves.append((path, target))
            print(f"  {path.name}  ->  {folder_name}/")

    if skipped_groups:
        print()
        print("Left in place (no 2+ file group, or base shorter than 3 chars):")
        for base in sorted(skipped_groups):
            for path in sorted(skipped_groups[base]):
                print(f"  {path.name}  (base '{base}')")
    if still_unassigned:
        print()
        print("Left in place (no matching numbered base):")
        for path in still_unassigned:
            print(f"  {path.name}")

    print()
    if not args.apply:
        print(f"DRY RUN: {len(moves)} file(s) would move. Re-run with --apply to execute.")
        return 0

    for path, target in moves:
        target.parent.mkdir(parents=True, exist_ok=True)
        path.rename(target)
    print(f"Moved {len(moves)} file(s) into {len(movable)} compound folder(s).")
    if errors:
        print(f"{errors} file(s) skipped due to existing targets.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
