#!/usr/bin/env python3
"""Process Cyclone yearbook PDFs from DGIngest into SHOW's `cyclone` collection on the Mac.

dg-landing cannot reach //storage, so this runs the DART desktop steps (IDs, Azure originals,
Function 3 PDF derivatives, and an append-only core merge) directly from a mounted share.

Metadata comes from the Google Sheet export, whose `originating_system_id` values are
pre-assigned `dg_<epoch>` IDs; each becomes `cyclone_dg_<epoch>`. Rows are matched to PDFs by
year plus any suffix (e.g. 1936 Malteaser). Unmatched sheet rows, unmatched PDFs, and
TIFF-only years are skipped and reported. Dry run by default; pass --apply to do the work.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

SHEET_URL = ("https://docs.google.com/spreadsheets/d/1up8_aZNtBeSUuMcaDiqnRBZS0_Thw6KMGi9iA9QixYM"
             "/export?format=csv&gid=518695227")
COLLECTION = "cyclone"
DEFAULT_SOURCE = Path("/Volumes/DGIngest/Cyclones")
DEFAULT_PROJECT = Path.home() / "DART-projects" / COLLECTION
DEFAULT_LOCATION = "Grinnell (Iowa); Grinnell College"
PDF_EXTS = {".pdf"}
TIFF_EXTS = {".tif", ".tiff"}
YEAR = re.compile(r"(1[89]\d\d|20\d\d)")


def match_key(name: str) -> str | None:
    """'Grinnell_Cyclone_ 1893.pdf', 'Cyclone1893.pdf', and 'Grinnell_Cyclone_1918,pdf' share keys."""
    stem = re.sub(r"[.,](pdf|tiff?)$", "", name.strip(), flags=re.I).replace(" ", "")
    found = YEAR.search(stem)
    if not found:
        return None
    return found.group(1) + stem[found.end():].strip("_-").lower()


def atomic_write(path: Path, content: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}-", delete=False) as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(handle.name, path)


def csv_bytes(columns: list[str], rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


@contextmanager
def staged_pdf(source: Path, hidden: Path, expected_size: int) -> Iterator[Path]:
    """Keep SMB reads out of Azure's parallel upload streams."""
    before = source.stat()
    if before.st_size != expected_size:
        raise RuntimeError(f"Source size changed since planning: {source}")
    required = expected_size + 1024**3
    if shutil.disk_usage(hidden).free < required:
        raise RuntimeError(f"Local staging needs {required} bytes free (PDF plus 1 GiB reserve): {hidden}")
    with tempfile.TemporaryDirectory(prefix="cyclone-stage-", dir=hidden) as directory:
        local = Path(directory) / source.name
        print(f"    staging local copy: {source.name}", flush=True)
        try:
            with source.open("rb") as reader, local.open("wb") as writer:
                shutil.copyfileobj(reader, writer, length=8 * 1024**2)
                writer.flush()
                os.fsync(writer.fileno())
            after = source.stat()
        except OSError as exc:
            raise OSError(
                f"Could not stage {source}; check the DGIngest mount/VPN, then rerun to resume. {exc}"
            ) from exc
        if (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
            raise RuntimeError(f"Source changed while staging: {source}")
        if local.stat().st_size != expected_size:
            raise RuntimeError(f"Incomplete local copy of {source}; not uploading")
        yield local


def load_sheet(raw: str) -> list[list[str]]:
    if raw.startswith("http"):
        with urllib.request.urlopen(raw, timeout=60) as response:
            text = response.read().decode("utf-8-sig")
    else:
        text = Path(raw).read_text(encoding="utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    # The sheet repeats the header 'originating_system_id', so index by position.
    expected = {0: "originating_system_id", 1: "originating_system_id", 2: "dcterms:alternative",
                9: "file_name_1", 12: "dc:creator", 15: "dc:subject", 16: "dcterms:subject.dcterms:LCSH",
                17: "dc:description", 22: "dc:date"}
    header = rows[0]
    for index, name in expected.items():
        if index >= len(header) or header[index].strip() != name:
            raise SystemExit(f"Unexpected sheet layout: column {index} should be {name!r}")
    return [row + [""] * (len(header) - len(row)) for row in rows[1:] if any(cell.strip() for cell in row)]


def sheet_title(row: list[str]) -> str:
    title, alternative = row[1].strip(), row[2].strip()
    # Some rows split 'Grinnell College' / 'Yearbook 1903' across title and alternative title.
    if alternative and not YEAR.search(title):
        title = f"{title} {alternative}"
    return re.sub(r"\s+", " ", title)


def sheet_record(row: list[str], filename: str, location: str) -> dict[str, str]:
    origin = row[0].strip()
    subjects = [s.strip() for s in (row[15], row[16]) if s.strip()]
    return dict(objectid=f"{COLLECTION}_{origin}", parentid="", title=sheet_title(row),
                original_file_name=filename, creator=row[12].strip(), date=row[22].strip(),
                description=row[17].strip(), subject="; ".join(subjects), location=location,
                identifier=origin, type="Text", format="application/pdf", display_template="pdf")


def plan(sheet_rows, source: Path, core_rows, mappings, location: str) -> tuple[list[dict], list[str]]:
    files = sorted(p for p in source.iterdir() if p.is_file() and not p.name.startswith("."))
    skipped: list[str] = []
    pdfs: dict[str, Path] = {}
    tiff_keys: set[str] = set()
    for path in files:
        key = match_key(path.name)
        if path.suffix.lower() in TIFF_EXTS and key:
            tiff_keys.add(YEAR.search(key).group(1))
        elif path.suffix.lower() in PDF_EXTS and key:
            if key in pdfs:
                raise SystemExit(f"Two PDFs share key {key}: {pdfs[key].name}, {path.name}")
            pdfs[key] = path
    for directory in sorted(p for p in source.iterdir() if p.is_dir() and not p.name.startswith(".")):
        names = [p for p in directory.iterdir() if p.is_file()]
        year = YEAR.search(directory.name)
        if year and any(p.suffix.lower() in TIFF_EXTS for p in names) \
                and not any(p.suffix.lower() in PDF_EXTS for p in names):
            tiff_keys.add(year.group(1))
    core_ids = {r.get("objectid", "") for r in core_rows}
    core_names = {r.get("original_file_name", "") for r in core_rows}
    core_years = {r.get("date", "").strip() for r in core_rows}
    used: set[str] = set()
    items: list[dict] = []
    seen_ids: set[str] = set()
    for row in sheet_rows:
        origin = row[0].strip()
        key = match_key(row[9]) or match_key(row[22] + ".pdf")
        year = row[22].strip()
        label = f"{year} ({row[9].strip() or 'no filename'}, {origin})"
        if not re.fullmatch(r"dg_\d+", origin):
            raise SystemExit(f"Sheet row has an invalid originating_system_id: {origin!r}")
        if origin in seen_ids:
            raise SystemExit(f"Duplicate originating_system_id in sheet: {origin}")
        seen_ids.add(origin)
        pdf = pdfs.get(key or "")
        if pdf is None:
            reason = "TIFF pages only, no PDF" if year in tiff_keys else "no matching PDF in source folder"
            skipped.append(f"Sheet row {label}: {reason}")
            continue
        used.add(key)
        objectid = f"{COLLECTION}_{origin}"
        stable = str(Path(*pdf.parts[3:])) if pdf.parts[:2] == ("/", "Volumes") else str(pdf)
        if mappings.get(stable, objectid) != objectid:
            raise SystemExit(f"{stable} is already mapped to {mappings[stable]}, not {objectid}")
        if objectid in core_ids or pdf.name in core_names:
            skipped.append(f"{year} {pdf.name}: already in core ({objectid})")
            continue
        if year in core_years:
            skipped.append(f"{year} {pdf.name}: core already has a {year} yearbook; review manually")
            continue
        items.append(dict(
            key=key, stable=stable, path=str(pdf), size=pdf.stat().st_size,
            record=sheet_record(row, pdf.name, location)))
    for key, pdf in sorted(pdfs.items()):
        if key not in used:
            skipped.append(f"PDF {pdf.name}: no matching sheet row")
    for year in sorted(tiff_keys):
        if not any(i["record"]["date"] == year for i in items):
            message = f"{year}: TIFF pages only, no PDF; skipped"
            if not any(s.startswith(f"Sheet row {year} ") for s in skipped):
                skipped.append(message)
    items.sort(key=lambda i: (i["record"]["date"], i["record"]["original_file_name"]))
    return items, skipped


class Azure:
    def __init__(self, connection: str, objs_path: str) -> None:
        from azure.storage.blob import BlobServiceClient
        from dart_processing import get_derivative_azure_paths

        self.client = BlobServiceClient.from_connection_string(
            connection, connection_timeout=30, read_timeout=600, retry_total=5,
            max_single_put_size=64 * 1024**2, max_block_size=32 * 1024**2)
        smalls, thumbs = get_derivative_azure_paths(objs_path)
        self.paths = {"objs": objs_path.strip("/"), "smalls": smalls, "thumbs": thumbs}

    def blob(self, kind: str, filename: str):
        container, _, prefix = self.paths[kind].partition("/")
        return self.client.get_blob_client(container=container, blob=f"{prefix}/{filename}" if prefix else filename)

    def upload(self, kind: str, source: Path, filename: str, content_type: str) -> str:
        from azure.core.exceptions import ResourceNotFoundError
        from azure.storage.blob import ContentSettings

        blob = self.blob(kind, filename)
        size = source.stat().st_size
        try:
            existing = blob.get_blob_properties(timeout=60).size
        except ResourceNotFoundError:
            existing = None
        if existing is not None:
            if kind == "objs" and existing != size:
                raise RuntimeError(f"Azure blob {filename} exists with {existing} bytes (local {size}); not overwritten")
            print(f"    reuse  {kind}/{filename}", flush=True)
            return blob.url.split("?", 1)[0]
        last = [0]

        def progress(current: int, total: int | None) -> None:
            if total and current - last[0] >= 512 * 1024**2:
                last[0] = current
                print(f"    {filename}: {current / 1024**3:.1f}/{total / 1024**3:.1f} GiB", flush=True)

        with source.open("rb") as handle:
            blob.upload_blob(handle, length=size, overwrite=False, max_concurrency=4, timeout=600,
                             progress_hook=progress, content_settings=ContentSettings(content_type=content_type))
        print(f"    upload {kind}/{filename}", flush=True)
        return blob.url.split("?", 1)[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sheet", default=SHEET_URL, help="Sheet CSV export URL or local CSV path")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT, help="DART working folder for cyclone")
    parser.add_argument("--location", default=DEFAULT_LOCATION)
    parser.add_argument("--only-ids", type=Path, help="Restrict processing to a frozen JSON list of object IDs")
    parser.add_argument("--limit", type=int, help="Process at most N pending yearbooks this run")
    parser.add_argument("--no-merge", action="store_true", help="Upload/derive and write the export CSV only")
    parser.add_argument("--apply", action="store_true", help="Upload to Azure, write IDs, and merge into the core")
    args = parser.parse_args(argv)

    import app as core

    hidden = args.project / ".DART-working-directory"
    settings_path = hidden / core.APP_SETTINGS_FILENAME
    raw_settings = json.loads(settings_path.read_text())
    settings = core.decrypt_sensitive_settings(raw_settings)
    if settings.get("collection-id") != COLLECTION:
        raise SystemExit(f"{settings_path} is not the {COLLECTION} project")
    core_csv = Path(settings["core_metadata_csv"])
    if core.is_protected_core_csv_name(core_csv):
        raise SystemExit("Refusing to merge into collection-template.csv")
    if not args.source.is_dir():
        raise SystemExit(f"Source folder is not mounted: {args.source} (mount smb://storage/MEDIADB/DGIngest)")
    with core_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        core_columns, core_rows = list(reader.fieldnames or []), list(reader)
    mappings = dict(settings.get("file_to_id_map") or {})

    items, skipped = plan(load_sheet(args.sheet), args.source, core_rows, mappings, args.location)
    if args.only_ids:
        selected = json.loads(args.only_ids.read_text())
        if not isinstance(selected, list) or not selected or not all(
                isinstance(value, str) and re.fullmatch(r"cyclone_dg_\d+", value) for value in selected):
            raise SystemExit("The selected ID file must contain a nonempty JSON list of cyclone IDs")
        known = {i["record"]["objectid"] for i in items} | {r["objectid"] for r in core_rows}
        if set(selected) - known:
            raise SystemExit(f"Selected IDs have no eligible source or core row: {sorted(set(selected) - known)}")
        items = [i for i in items if i["record"]["objectid"] in selected]
    ledger_path = hidden / "cyclone_yearbooks_ledger.json"
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    pending = [i for i in items if not ledger.get(i["record"]["objectid"], {}).get("image_thumb")]
    print(f"Core: {core_csv} ({len(core_rows)} rows)")
    print(f"Ready: {len(items)} yearbooks, {sum(i['size'] for i in items) / 1024**3:.1f} GiB "
          f"({len(items) - len(pending)} already uploaded/derived)")
    for item in items:
        r = item["record"]
        print(f"  {r['objectid']}  {r['date']}  {r['original_file_name']}  {r['title']}")
    print(f"Skipped: {len(skipped)}")
    for line in skipped:
        print(f"  - {line}")
    if not args.apply:
        print("\nDry run only. Re-run with --apply to upload, derive, and merge.")
        return 0
    if not items:
        print("Nothing to process.")
        return 0

    connection = os.environ.get("DART_AZURE_CONNECTION_STRING") or settings.get("azure_connection_string", "")
    if not connection.startswith(("DefaultEndpointsProtocol=", "BlobEndpoint=")):
        raise SystemExit("The cyclone project has no usable Azure connection string. Save it in desktop DART "
                         "Function 0 for ~/DART-projects/cyclone, or export DART_AZURE_CONNECTION_STRING.")
    azure = Azure(connection, settings["azure_blob_storage_path"])
    derivatives = hidden / "derivatives_cyclone_yearbooks"
    derivatives.mkdir(mode=0o700, exist_ok=True)

    # Persist durable IDs before any network work, preserving the encrypted credential as stored.
    for item in items:
        mappings[item["stable"]] = item["record"]["objectid"]
    if mappings != raw_settings.get("file_to_id_map"):
        raw_settings["file_to_id_map"] = mappings
        atomic_write(settings_path, (json.dumps(raw_settings, indent=2, ensure_ascii=False) + "\n").encode())

    for count, item in enumerate(pending[: args.limit] if args.limit else pending, 1):
        r, source = item["record"], Path(item["path"])
        state = ledger.setdefault(r["objectid"], {})
        print(f"[{count}/{len(pending)}] {r['date']} {source.name} ({item['size'] / 1024**3:.1f} GiB)", flush=True)
        with staged_pdf(source, hidden, item["size"]) as local:
            if not state.get("object_location"):
                state["object_location"] = azure.upload("objs", local, f"{r['objectid']}.pdf", "application/pdf")
                atomic_write(ledger_path, json.dumps(ledger, indent=2).encode())
            for field, kind, suffix, size in (("image_small", "smalls", "_SMALL", 800), ("image_thumb", "thumbs", "_TN", 400)):
                if state.get(field):
                    continue
                output = derivatives / f"{r['objectid']}{suffix}.jpg"
                if not output.exists():
                    ok, message = core.generate_pdf_derivative(str(local), str(output), size, size, quality=85)
                    if not ok:
                        raise RuntimeError(f"{source.name}: {message}")
                state[field] = azure.upload(kind, output, output.name, "image/jpeg")
                atomic_write(ledger_path, json.dumps(ledger, indent=2).encode())

    done = [i for i in items if ledger.get(i["record"]["objectid"], {}).get("image_thumb")]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rows = [dict(i["record"], **{k: ledger[i["record"]["objectid"]][k]
                                 for k in ("object_location", "image_small", "image_thumb")}) for i in done]
    export = hidden / f"DART_export_cyclone_yearbooks_{stamp}.csv"
    atomic_write(export, csv_bytes(core_columns, rows))
    print(f"\nExport: {export} ({len(rows)} rows)")
    if len(done) < len(items):
        print(f"{len(items) - len(done)} yearbooks still pending; re-run to resume. Core not merged.")
        return 1
    if args.no_merge or not rows:
        return 0

    # Append-only merge; re-read the core so nothing written meanwhile is lost.
    current = core_csv.read_bytes()
    with core_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns, existing = list(reader.fieldnames or []), list(reader)
    if columns != core_columns:
        raise SystemExit("Core CSV header changed during this run; not merged")
    ids = {r["objectid"] for r in existing}
    names = {r.get("original_file_name", "") for r in existing}
    new = [r for r in rows if r["objectid"] not in ids and r["original_file_name"] not in names]
    if not new:
        print("Core already contains every processed yearbook; nothing to merge.")
        return 0
    backup = hidden / f"{core_csv.name}.backup_{stamp}"
    atomic_write(backup, current)
    atomic_write(core_csv, csv_bytes(columns, existing + new))
    summary = dict(merged_at=datetime.now(timezone.utc).isoformat(), core=str(core_csv), backup=str(backup),
                   export=str(export), added=[r["objectid"] for r in new], skipped=skipped)
    atomic_write(hidden / f"cyclone_yearbooks_merge_{stamp}.json", json.dumps(summary, indent=2).encode())
    print(f"Merged {len(new)} rows into {core_csv} (backup: {backup})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
