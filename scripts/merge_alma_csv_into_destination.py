#!/usr/bin/env python3
"""
Standalone Alma-to-destination CSV merge utility for DART workflows.

What it does:
- Loads mapping settings from DG_to_CB_mapping_template.json (or --context file)
- Prompts user to pick source (Alma) and destination CSV files
- Matches source[match_column] to destination[original_file_name]
- Creates a timestamped backup of destination CSV before writing
- Preserves destination row order
- Applies mapped updates with data-loss protection (does not overwrite
  non-empty destination values with empty source values)

Usage:
    python3 scripts/merge_alma_csv_into_destination.py
    python3 scripts/merge_alma_csv_into_destination.py --context /path/to/context.json
    python3 scripts/merge_alma_csv_into_destination.py --source alma.csv --destination core.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

CSV_DEST_MATCH_COLUMN = "original_file_name"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge Alma source CSV data into a destination CSV using DART mapping rules.",
    )
    parser.add_argument(
        "--context",
        help="Path to mapping context JSON file (default: ./DG_to_CB_mapping_template.json)",
    )
    parser.add_argument(
        "--source",
        help="Optional Alma source CSV path. If omitted, a file picker opens.",
    )
    parser.add_argument(
        "--destination",
        help="Optional destination CSV path. If omitted, a file picker opens.",
    )
    return parser.parse_args()


def choose_file(title: str) -> Path:
    # First choice: Flet picker (consistent with DART UI stack).
    try:
        import flet as ft

        selected_path = ""

        def pick_with_flet(page: ft.Page) -> None:
            nonlocal selected_path

            page.title = title
            page.window.width = 520
            page.window.height = 120
            page.window.always_on_top = True

            def on_result(e: ft.FilePickerResultEvent) -> None:
                nonlocal selected_path
                if e.files and len(e.files) > 0 and e.files[0].path:
                    selected_path = e.files[0].path
                page.window.close()

            picker = ft.FilePicker(on_result=on_result)
            page.overlay.append(picker)
            page.update()
            picker.pick_files(
                allow_multiple=False,
                dialog_title=title,
                allowed_extensions=["csv"],
            )

        ft.app(target=pick_with_flet)

        if selected_path:
            return Path(selected_path).expanduser().resolve()

        raise SystemExit(f"Cancelled: {title}")
    except Exception:
        pass

    # Second choice: tkinter picker.
    try:
        from tkinter import Tk, filedialog

        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askopenfilename(
            title=title,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        root.destroy()

        if selected:
            return Path(selected).expanduser().resolve()

        raise SystemExit(f"Cancelled: {title}")
    except Exception:
        pass

    # Final fallback: terminal path prompt.
    try:
        entered = input(f"{title} (enter path): ").strip()
        if not entered:
            raise SystemExit(f"Cancelled: {title}")
        return Path(entered).expanduser().resolve()
    except KeyboardInterrupt as exc:
        raise SystemExit(f"Cancelled: {title}") from exc


def load_context(context_path: Path) -> dict:
    import json

    if not context_path.exists():
        raise SystemExit(f"Context file not found: {context_path}")

    with open(context_path, "r", encoding="utf-8") as f:
        try:
            context = json.load(f)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in context file {context_path}: {exc}") from exc

    if "field_mapping" not in context or not isinstance(context["field_mapping"], dict):
        raise SystemExit("Context JSON missing required object: field_mapping")

    if "match_column" not in context or not str(context["match_column"]).strip():
        raise SystemExit("Context JSON missing required value: match_column")

    return context


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise SystemExit(f"CSV file not found: {path}")

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if not fieldnames:
        raise SystemExit(f"CSV has no header row: {path}")

    return fieldnames, rows


def normalize_key(value: str) -> str:
    # Normalize only for comparisons; original CSV values remain unchanged.
    return str(value or "").strip().lower()


def normalize_source_value(value: str) -> str:
    # Alma source values can use pipe separators; convert to semicolon style.
    text = str(value or "")
    text = text.replace(" | ", "; ")
    text = text.replace(" |", ";")
    text = text.replace("|", ";")
    return text


def validate_unique_keys(rows: list[dict[str, str]], key_column: str, label: str) -> None:
    seen: dict[str, int] = {}
    duplicates: list[str] = []

    for row in rows:
        key = normalize_key(row.get(key_column, ""))
        if not key:
            continue
        seen[key] = seen.get(key, 0) + 1
        if seen[key] == 2:
            duplicates.append(key)

    if duplicates:
        preview = ", ".join(duplicates[:10])
        raise SystemExit(
            f"{label} has duplicate values in key column '{key_column}': {preview}"
        )


def ensure_destination_columns(
    destination_fieldnames: list[str],
    destination_rows: list[dict[str, str]],
    mapped_target_columns: list[str],
) -> list[str]:
    missing = [c for c in mapped_target_columns if c not in destination_fieldnames]
    if not missing:
        return destination_fieldnames

    destination_fieldnames = list(destination_fieldnames)
    destination_fieldnames.extend(missing)

    for row in destination_rows:
        for col in missing:
            row.setdefault(col, "")

    print(f"[INFO] Added {len(missing)} destination columns: {', '.join(missing)}")
    return destination_fieldnames


def merge_rows(
    source_rows: list[dict[str, str]],
    destination_rows: list[dict[str, str]],
    match_column: str,
    field_mapping: dict[str, str],
) -> dict[str, int]:
    destination_by_key = {
        normalize_key(row.get(CSV_DEST_MATCH_COLUMN, "")): row
        for row in destination_rows
        if normalize_key(row.get(CSV_DEST_MATCH_COLUMN, ""))
    }

    stats = {
        "source_rows": len(source_rows),
        "matched_rows": 0,
        "unmatched_source_rows": 0,
        "field_updates": 0,
        "data_loss_skips": 0,
    }

    for src in source_rows:
        source_key = normalize_key(src.get(match_column, ""))
        if not source_key:
            continue

        dest = destination_by_key.get(source_key)
        if not dest:
            stats["unmatched_source_rows"] += 1
            continue

        stats["matched_rows"] += 1

        for source_col, target_col in field_mapping.items():
            if not str(target_col).strip():
                continue

            target_col = str(target_col).strip()

            # Key column is identifier only; never overwrite it.
            if target_col == CSV_DEST_MATCH_COLUMN:
                continue

            src_val = normalize_source_value(src.get(source_col, ""))
            dst_val = str(dest.get(target_col, ""))

            src_norm = src_val.strip()
            dst_norm = dst_val.strip()

            # DART-style data-loss protection: do not replace non-empty destination
            # values with empty source values.
            if dst_norm and not src_norm:
                stats["data_loss_skips"] += 1
                continue

            if src_norm != dst_norm:
                dest[target_col] = src_val
                stats["field_updates"] += 1

    return stats


def make_backup(destination_csv: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{destination_csv.name}.backup_{timestamp}"
    dart_working_dir = destination_csv.parent / ".DART-working-directory"
    dart_working_dir.mkdir(parents=True, exist_ok=True)
    backup_path = dart_working_dir / backup_name
    shutil.copy2(destination_csv, backup_path)
    return backup_path


def write_csv_atomically(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    fd, temp_path = tempfile.mkstemp(suffix=".csv", dir=path.parent, text=True)
    temp_file = Path(temp_path)

    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        temp_file.replace(path)
    except Exception:
        if temp_file.exists():
            temp_file.unlink()
        raise


def main() -> int:
    args = parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    context_path = (
        Path(args.context).expanduser().resolve()
        if args.context
        else repo_root / "DG_to_CB_mapping_template.json"
    )

    context = load_context(context_path)
    field_mapping = context["field_mapping"]
    match_column = str(context["match_column"]).strip()

    source_csv = (
        Path(args.source).expanduser().resolve() if args.source else choose_file("Select Alma source CSV")
    )
    destination_csv = (
        Path(args.destination).expanduser().resolve()
        if args.destination
        else choose_file("Select destination CSV to merge into")
    )

    source_fieldnames, source_rows = read_csv(source_csv)
    destination_fieldnames, destination_rows = read_csv(destination_csv)

    if match_column not in source_fieldnames:
        raise SystemExit(
            f"Source CSV is missing match_column '{match_column}' from context file."
        )

    if CSV_DEST_MATCH_COLUMN not in destination_fieldnames:
        raise SystemExit(
            f"Destination CSV must include '{CSV_DEST_MATCH_COLUMN}' for matching."
        )

    validate_unique_keys(destination_rows, CSV_DEST_MATCH_COLUMN, "Destination CSV")
    validate_unique_keys(source_rows, match_column, "Source CSV")

    mapped_target_columns = sorted({str(v).strip() for v in field_mapping.values() if str(v).strip()})
    destination_fieldnames = ensure_destination_columns(
        destination_fieldnames,
        destination_rows,
        mapped_target_columns,
    )

    backup_path = make_backup(destination_csv)
    print(f"[INFO] Created backup: {backup_path}")

    stats = merge_rows(source_rows, destination_rows, match_column, field_mapping)

    write_csv_atomically(destination_csv, destination_fieldnames, destination_rows)

    print("\nMerge complete")
    print(f"  Context file:           {context_path}")
    print(f"  Source CSV:             {source_csv}")
    print(f"  Destination CSV:        {destination_csv}")
    print(f"  Match columns:          source[{match_column}] -> destination[{CSV_DEST_MATCH_COLUMN}]")
    print(f"  Source rows read:       {stats['source_rows']}")
    print(f"  Matched rows:           {stats['matched_rows']}")
    print(f"  Unmatched source rows:  {stats['unmatched_source_rows']}")
    print(f"  Field updates applied:  {stats['field_updates']}")
    print(f"  Data-loss skips:        {stats['data_loss_skips']}")
    print(f"  Backup file:            {backup_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
