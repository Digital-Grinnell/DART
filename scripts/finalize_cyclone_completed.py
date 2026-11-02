#!/usr/bin/env python3
"""Verify and append the 74 completed Cyclone yearbooks; freeze the remaining 15."""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.process_cyclone_yearbooks import (
    Azure, DEFAULT_LOCATION, DEFAULT_PROJECT, SHEET_URL, atomic_write, csv_bytes,
    load_sheet, match_key, sheet_record,
)

FIELDS = ("object_location", "image_small", "image_thumb")


def completed_records(sheet, mappings, ledger):
    by_id = {}
    for row in sheet:
        objectid = f"cyclone_{row[0].strip()}"
        if not re.fullmatch(r"cyclone_dg_\d+", objectid) or objectid in by_id:
            raise ValueError(f"Invalid or duplicate sheet ID: {objectid}")
        by_id[objectid] = row
    names = {}
    for stable, objectid in mappings.items():
        if objectid in names:
            raise ValueError(f"Multiple source mappings for {objectid}")
        names[objectid] = Path(stable).name
    complete = {key for key, value in ledger.items() if all(value.get(field) for field in FIELDS)}
    if len(complete) != 74 or len(names) != 89 or not complete.issubset(names):
        raise ValueError("Expected exactly 74 completed ledger entries and 89 mapped source PDFs")
    rows = []
    for objectid in sorted(names):
        sheet_row = by_id.get(objectid)
        if sheet_row is None or match_key(sheet_row[9]) != match_key(names[objectid]):
            raise ValueError(f"Sheet filename does not match the saved mapping: {objectid}")
        if objectid in complete:
            rows.append(dict(sheet_record(sheet_row, names[objectid], DEFAULT_LOCATION), **ledger[objectid]))
    rows.sort(key=lambda row: (row["date"], row["original_file_name"]))
    return rows, sorted(set(names) - complete)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--sheet", default=SHEET_URL)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    import app as core
    from azure.core import MatchConditions
    from PIL import Image

    hidden = args.project / ".DART-working-directory"
    settings = core.decrypt_sensitive_settings(json.loads((hidden / "dart_settings.json").read_text()))
    if settings.get("collection-id") != "cyclone":
        raise ValueError("Not the cyclone project")
    core_path = Path(settings["core_metadata_csv"])
    if core.is_protected_core_csv_name(core_path):
        raise ValueError("Reserved core CSV name")
    before = core_path.read_bytes()
    reader = csv.DictReader(io.StringIO(before.decode("utf-8-sig")))
    columns, existing = list(reader.fieldnames or []), list(reader)
    sheet = load_sheet(args.sheet)
    ledger = json.loads((hidden / "cyclone_yearbooks_ledger.json").read_text())
    rows, remaining = completed_records(sheet, settings["file_to_id_map"], ledger)
    required = set(rows[0])
    if required - set(columns):
        raise ValueError(f"Core schema would drop fields: {sorted(required - set(columns))}")
    ids = {row["objectid"] for row in existing}
    names = {row["original_file_name"] for row in existing}
    if len(ids) != len(existing) or len(names) != len(existing):
        raise ValueError("Core contains duplicate IDs or filenames")
    for row in rows:
        if row["objectid"] in ids or row["original_file_name"] in names:
            raise ValueError(f"Completed row already exists or conflicts with core: {row['objectid']}")
    print(f"Core: {len(existing)} existing rows; append {len(rows)}; freeze {len(remaining)} remaining", flush=True)
    if not args.apply:
        return 0

    azure = Azure(settings["azure_connection_string"], settings["azure_blob_storage_path"])
    evidence = {}
    for index, row in enumerate(rows, 1):
        checks = {}
        for field, kind, suffix, maximum in (
                ("object_location", "objs", ".pdf", None),
                ("image_small", "smalls", "_SMALL.jpg", 800),
                ("image_thumb", "thumbs", "_TN.jpg", 400)):
            blob = azure.blob(kind, row["objectid"] + suffix)
            if row[field] != blob.url.split("?", 1)[0]:
                raise ValueError(f"Ledger URL differs from expected blob: {row['objectid']} {field}")
            properties = blob.get_blob_properties(timeout=60)
            if properties.size <= 0:
                raise ValueError(f"Empty Azure blob: {blob.blob_name}")
            if maximum is not None:
                if properties.size > 16 * 1024**2:
                    raise ValueError(f"Oversized JPEG: {blob.blob_name}")
                content = blob.download_blob(
                    etag=properties.etag, match_condition=MatchConditions.IfNotModified, timeout=60,
                ).readall()
                with Image.open(io.BytesIO(content)) as image:
                    if image.format != "JPEG" or not (0 < image.width <= maximum and 0 < image.height <= maximum):
                        raise ValueError(f"Invalid JPEG: {blob.blob_name}")
                    image.load()
            checks[field] = dict(size=properties.size, etag=properties.etag)
        evidence[row["objectid"]] = checks
        print(f"Verified {index}/{len(rows)}: {row['date']} {row['original_file_name']}", flush=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = hidden / f"{core_path.name}.backup_{stamp}"
    export = hidden / f"DART_export_cyclone_completed_{stamp}.csv"
    atomic_write(backup, before)
    atomic_write(export, csv_bytes(columns, rows))
    # Save the sheet as positional CSV: its duplicate header must remain intact.
    sheet_header = [""] * len(sheet[0])
    for index, name in {0: "originating_system_id", 1: "originating_system_id",
                        2: "dcterms:alternative", 9: "file_name_1", 12: "dc:creator",
                        15: "dc:subject", 16: "dcterms:subject.dcterms:LCSH",
                        17: "dc:description", 22: "dc:date"}.items():
        sheet_header[index] = name
    buffer = io.StringIO()
    csv.writer(buffer).writerows([sheet_header, *sheet])
    atomic_write(hidden / "cyclone_remaining_metadata.csv", buffer.getvalue().encode())
    atomic_write(hidden / "cyclone_remaining_15.json", json.dumps(remaining, indent=2).encode())
    result = csv_bytes(columns, existing + rows)
    if core_path.read_bytes() != before:
        raise RuntimeError("Core changed during verification; not merged")
    atomic_write(core_path, result)
    if core_path.read_bytes() != result:
        raise RuntimeError("Core readback differs from expected merge")
    atomic_write(hidden / f"cyclone_completed_merge_{stamp}.json", json.dumps(
        dict(backup=str(backup), export=str(export), added=len(rows), final_rows=len(existing + rows),
             azure_verification=evidence, remaining=remaining), indent=2).encode())
    print(f"Merged {len(rows)} yearbooks; core now has {len(existing + rows)} rows. Backup: {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
