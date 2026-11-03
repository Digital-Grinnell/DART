#!/usr/bin/env python3
"""
Merge OHM-processed Reunion oral histories into SHOW alumni-<decade> cores.

The source is a CollectionBuilder project whose interviews were already
processed by OHM and published to Azure (for example
~/GitHub/gccb-2026-Reunion-OH with ``re26_dg_<epoch>`` objects). Each
interview is routed to ``<show>/collections/alumni-<decade>/`` by the
interviewee's class year.

Durable ``objectid`` values are preserved. The MP3, image derivatives, and
transcript CSV are copied from wherever OHM/DART published them into the
``digitalgrinnell`` storage account under the alumni collection's path:

    objs/<slug>/<objectid>.mp3
    smalls/<slug>/<objectid>_SMALL.jpg, thumbs/<slug>/<objectid>_TN.jpg
    transcripts/<slug>/<objectid>_transcript.csv

and the new SHOW rows reference only those ``digitalgrinnell`` URLs. Copies
never overwrite: an existing blob must match byte-for-byte. Each upload is
re-downloaded anonymously and checked by SHA-256.

Two steps:

1. ``init`` writes a reviewable mapping CSV (class year, collection, names,
   title, description, interviewer, extent) with the evidence used for
   each class year. Review and edit it before merging.
2. ``merge`` validates the mapping, checks source files and destination
   blobs, and prints the plan. Nothing is written unless ``--apply`` is
   given. With ``--apply`` the files for a collection are copied and
   verified first; only then is its core backed up to
   ``~/DART-projects/<slug>/.DART-working-directory/`` and new rows are
   appended without rewriting existing bytes. Objects already present in a
   core are skipped, so reruns are safe.

``--apply`` needs a digitalgrinnell connection string, from either
``--settings <dart_settings.json>`` (decrypted with DART's key) or the
``DART_AZURE_CONNECTION_STRING`` environment variable. Run with DART's venv,
which provides azure-storage-blob and cryptography.

Usage:
    .venv/bin/python operations/collections/reunion_2026/merge_reunion_oral_histories.py init
    .venv/bin/python operations/collections/reunion_2026/merge_reunion_oral_histories.py merge
    .venv/bin/python operations/collections/reunion_2026/merge_reunion_oral_histories.py merge --apply \\
        --settings ~/DART-projects/baumann/.DART-working-directory/dart_settings.json
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

HOME = Path.home()
DEFAULT_SOURCE = HOME / "GitHub" / "gccb-2026-Reunion-OH"
DEFAULT_SHOW_COLLECTIONS = HOME / "GitHub" / "SHOW" / "collections"
DEFAULT_PROJECTS = HOME / "DART-projects"
DEFAULT_EVENT = "Grinnell College Reunion 2026"
RESERVED_CORE = "collection-template"
DEST_ACCOUNT = "digitalgrinnell"
DEST_BASE = f"https://{DEST_ACCOUNT}.blob.core.windows.net"
CONTENT_TYPES = {
    ".mp3": "audio/mpeg",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".csv": "text/csv; charset=utf-8",
}

MAP_FIELDS = [
    "objectid", "include", "collection", "class_year", "first_name", "last_name",
    "title", "description", "creator_personal", "interviewer", "extent",
    "class_year_evidence", "notes",
]

# Student interviewers heard in the Reunion 2026 transcripts. Spellings other
# than Condron come from machine transcription; verify in the mapping file.
KNOWN_INTERVIEWERS = {
    "mariposa": "Condron, Mariposa '27",
    "marioposa": "Condron, Mariposa '27",
    "adrienne": "Gassaway, Adrienne '28",
    "adrian": "Gassaway, Adrienne '28",
    "adriienne": "Gassaway, Adrienne '28",
    "luke": "Grobaugh, Luke '29",
}

YEAR_PATTERNS = [
    re.compile(r"\bclass of '?(\d{4}|\d{2})\b", re.I),
    re.compile(r"\bgraduated (?:from )?(?:Grinnell(?: College)? )?(?:in )?'?(\d{4}|\d{2})\b", re.I),
    re.compile(r"^\s*[A-Z][\w.'-]+(?: [A-Z][\w.'-]+)+,\s*(\d{4})\.?\s*$"),
]
TIMESTAMP_RE = re.compile(r"\A(?:\d+:)?\d{1,2}:[0-5]\d\Z")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def normalize_year(token: str) -> int:
    year = int(token)
    if year < 100:
        year += 2000 if year <= 30 else 1900
    return year


def short_year(year: int) -> str:
    return f"'{year % 100:02d}"


def decade_collection(year: int) -> str:
    return f"alumni-{year // 10 * 10}s"


def split_name(originating_id: str) -> tuple[str, str]:
    stem = originating_id.split("--", 1)[0]
    stem = re.sub(r"_AOH$", "", stem)
    parts = stem.split("_")
    if len(parts) < 2:
        return "", stem
    return " ".join(parts[1:]), parts[0]


def cb_person(value: str) -> str:
    """'Mariposa Condron (Class of 2027)' -> "Condron, Mariposa '27"."""
    match = re.match(r"\s*(.+?)\s+(\S+)\s*\(Class of (\d{4})\)\s*$", value or "")
    if not match:
        return (value or "").strip()
    first, last, year = match.groups()
    return f"{last}, {first} {short_year(int(year))}"


def source_paths(source: Path) -> tuple[Path, Path, Path]:
    metadata = source / "_data" / "metadata.csv"
    transcripts = source / "_data" / "transcripts"
    ohm = next(source.glob("*/OHM-data"), None)
    if not metadata.is_file():
        fail(f"source metadata not found: {metadata}")
    return metadata, transcripts, ohm or source / "OHM-data"


def transcript_rows(transcripts: Path, row: dict[str, str]) -> list[dict[str, str]]:
    name = row.get("object_transcript") or f"{row['objectid']}.csv"
    path = transcripts / name
    if not path.is_file():
        return []
    return read_csv(path)[1]


def guess_interviewer(rows: list[dict[str, str]], first_name: str) -> tuple[str, str]:
    counts = collections.Counter(r.get("speaker", "").strip() for r in rows)
    for speaker, _ in counts.most_common():
        if speaker.lower() in KNOWN_INTERVIEWERS:
            return speaker, KNOWN_INTERVIEWERS[speaker.lower()]
    for speaker, _ in counts.most_common():
        if not speaker or speaker.lower().startswith("speaker"):
            continue
        if first_name and first_name.lower().split()[0] in speaker.lower():
            continue
        return speaker, KNOWN_INTERVIEWERS.get(speaker.lower(), "")
    return "", ""


def guess_class_year(meta: dict[str, str], rows: list[dict[str, str]], interviewer_speaker: str) -> tuple[int | None, str]:
    for field in ("interviewee", "title"):
        match = re.search(r"class of (\d{4})", meta.get(field, ""), re.I)
        if match:
            return int(match.group(1)), f"metadata {field}: {meta[field]}"
    for row in rows[:40]:
        if interviewer_speaker and row.get("speaker", "").strip() == interviewer_speaker:
            continue
        words = row.get("words", "")
        for pattern in YEAR_PATTERNS:
            match = pattern.search(words)
            if match:
                year = normalize_year(match.group(1))
                if 1930 <= year <= 2025:
                    return year, f"transcript {row.get('timestamp', '')} {row.get('speaker', '')}: {words.strip()[:120]}"
    return None, ""


def audio_extent(ohm_dir: Path, row: dict[str, str]) -> str:
    folder = ohm_dir / row.get("originating_system_id", "")
    audio = folder / row.get("original_file_name", "")
    if not audio.is_file() or not shutil.which("ffprobe"):
        return ""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio)],
            capture_output=True, text=True, timeout=60, check=True,
        )
        seconds = round(float(result.stdout.strip()))
    except (subprocess.SubprocessError, ValueError):
        return ""
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes} minutes {seconds} seconds"


def cmd_init(args: argparse.Namespace) -> None:
    mapping = args.mapping or (args.source / "reunion-alumni-merge-map.csv")
    if mapping.exists() and not args.force:
        fail(f"{mapping} already exists; edit it, or rerun init with --force to regenerate")
    metadata, transcripts, ohm_dir = source_paths(args.source)
    _, source_rows = read_csv(metadata)

    out = []
    for meta in source_rows:
        first, last = split_name(meta.get("originating_system_id", ""))
        rows = transcript_rows(transcripts, meta)
        speaker, interviewer_guess = guess_interviewer(rows, first)
        interviewer = cb_person(meta.get("interviewer", "")) or interviewer_guess
        year, evidence = guess_class_year(meta, rows, speaker)
        notes = []
        if year is None:
            notes.append("class year not found; fill in class_year and collection")
        if not interviewer:
            notes.append(f"interviewer speaker '{speaker}' not recognized")
        elif not meta.get("interviewer"):
            notes.append(f"interviewer from transcript speaker '{speaker}'; verify spelling")
        name = f"{first} {last}".strip()
        yy = short_year(year) if year else "'YY"
        out.append({
            "objectid": meta["objectid"],
            "include": "yes",
            "collection": decade_collection(year) if year else "",
            "class_year": str(year or ""),
            "first_name": first,
            "last_name": last,
            "title": f"{name} {yy}",
            "description": f"Alumni oral history interview with {name} {yy}. Recorded during {args.event}.",
            "creator_personal": f"{last}, {first} {yy}",
            "interviewer": interviewer,
            "extent": audio_extent(ohm_dir, meta),
            "class_year_evidence": evidence,
            "notes": "; ".join(notes),
        })

    with mapping.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MAP_FIELDS)
        writer.writeheader()
        writer.writerows(out)
    print(f"Wrote {len(out)} rows to {mapping}")
    for row in out:
        flag = "  <-- review" if row["notes"] else ""
        print(f"  {row['objectid']}  {row['class_year'] or '????'}  {row['collection'] or '-':14}  {row['title']}{flag}")
    print("\nReview class_year, names, title, description, and interviewer before running 'merge'.")


def subject_topic(meta: dict[str, str], first: str, last: str) -> str:
    terms = []
    for term in meta.get("subject", "").split(";"):
        term = term.strip().strip('"').strip()
        if not term:
            continue
        if "AOH" in term and term.endswith("Interviews"):
            term = f"{last}, {first}—Interviews"
        terms.append(term)
    return " | ".join(terms)


def source_transcript_url(meta: dict[str, str]) -> str:
    value = meta.get("object_transcript", "").strip()
    if not value or value.lower().startswith("http"):
        return value
    match = re.match(r"(https?://[^/]+)/objs/([^/]+)/", meta.get("object_location", ""))
    if not match:
        return ""
    return f"{match.group(1)}/transcripts/{match.group(2)}/{value}"


def dest_url(container: str, blob: str) -> str:
    return f"{DEST_BASE}/{container}/{blob}"


def asset_plan(meta: dict[str, str], slug: str) -> tuple[list[tuple[str, str, str, str]], list[str]]:
    """Return (field, source_url, dest_container, dest_blob) for each file to copy."""
    oid = meta["objectid"]
    assets: list[tuple[str, str, str, str]] = []
    problems: list[str] = []
    location = meta.get("object_location", "").strip()
    if not location:
        problems.append("object_location is empty")
    else:
        suffix = Path(urllib.parse.urlparse(location).path).suffix.lower()
        assets.append(("object_location", location, "objs", f"{slug}/{oid}{suffix}"))
    for field, container in (("image_small", "smalls"), ("image_thumb", "thumbs")):
        url = meta.get(field, "").strip()
        if not url:
            continue
        name = Path(urllib.parse.urlparse(url).path).name
        if not name.startswith(oid):
            problems.append(f"{field} file name does not start with {oid}: {url}")
            continue
        assets.append((field, url, container, f"{slug}/{name}"))
    transcript = source_transcript_url(meta)
    if not transcript:
        problems.append("object_transcript is empty")
    else:
        assets.append(("object_transcript", transcript, "transcripts", f"{slug}/{oid}_transcript.csv"))
    return assets, problems


def most_common(rows: list[dict[str, str]], field: str) -> str:
    values = collections.Counter(r.get(field, "") for r in rows if r.get(field, "").strip())
    return values.most_common(1)[0][0] if values else ""


def build_row(meta: dict[str, str], entry: dict[str, str], header: list[str],
              core_rows: list[dict[str, str]], urls: dict[str, str]) -> dict[str, str]:
    first, last = entry["first_name"], entry["last_name"]
    person = entry["creator_personal"]
    values = {
        "objectid": meta["objectid"],
        "title": entry["title"],
        "original_file_name": meta.get("original_file_name", ""),
        "date": entry["class_year"],
        "description": entry["description"],
        "type": "Sound",
        "format": meta.get("format") or "audio/mpeg",
        "display_template": "transcript",
        "image_alt_text": meta.get("image_alt_text", ""),
        "originating_system_id": meta.get("originating_system_id", ""),
        "creator_personal": person,
        "interviewee": person,
        "interviewer": entry["interviewer"],
        "contributor_personal": entry["interviewer"],
        "subject_topic": subject_topic(meta, first, last),
        "extent": entry.get("extent", ""),
        "contributing_institution": most_common(core_rows, "contributing_institution"),
        "publisher": most_common(core_rows, "publisher"),
        "rights": most_common(core_rows, "rights"),
        **urls,
    }
    language = meta.get("language") or "English"
    values["lanugage" if "lanugage" in header else "language"] = language
    return {field: values.get(field, "") for field in header}


def fetch(url: str, head: bool = False) -> tuple[int, bytes]:
    request = urllib.request.Request(url, method="HEAD" if head else "GET")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, b"" if head else response.read()
    except urllib.error.HTTPError as error:
        return error.code, b""
    except (urllib.error.URLError, TimeoutError) as error:
        return 0, str(error).encode()


def transcript_problems(body: bytes, url: str) -> list[str]:
    try:
        table = list(csv.DictReader(io.StringIO(body.decode("utf-8").lstrip("\ufeff"))))
    except (UnicodeDecodeError, csv.Error) as error:
        return [f"transcript unreadable ({error}): {url}"]
    if not table or "words" not in table[0]:
        return [f"transcript lacks a words column: {url}"]
    for number, line in enumerate(table, start=2):
        stamp = (line.get("timestamp") or "").strip().strip("[]")
        if stamp and not TIMESTAMP_RE.match(stamp):
            return [f"transcript row {number} has invalid timestamp '{stamp}': {url}"]
    return []


def preflight(assets: list[tuple[str, str, str, str]]) -> tuple[list[str], list[str]]:
    """Check sources load and destinations are free or already present. No writes."""
    problems, lines = [], []
    for field, source, container, blob in assets:
        if field == "object_transcript":
            status, body = fetch(source)
            if status == 200:
                problems += transcript_problems(body, source)
        else:
            status, _ = fetch(source, head=True)
        if status != 200:
            problems.append(f"source {field} HTTP {status}: {source}")
            continue
        target = dest_url(container, blob)
        dest_status, _ = fetch(target, head=True)
        if dest_status == 200:
            lines.append(f"      exists (will be compared byte-for-byte): {target}")
        elif dest_status == 404:
            lines.append(f"      copy -> {target}")
        else:
            problems.append(f"destination {field} HTTP {dest_status}: {target}")
    return problems, lines


def connection_string(args: argparse.Namespace) -> str:
    if args.settings:
        try:
            from cryptography.fernet import Fernet, InvalidToken
        except ImportError:
            fail("the cryptography package is required; run with ~/GitHub/DART/.venv/bin/python")
        settings = json.loads(args.settings.expanduser().read_text(encoding="utf-8"))
        value = settings.get("azure_connection_string", "")
        key_file = HOME / "DART-data" / "encryption_key"
        if value and key_file.is_file():
            try:
                value = Fernet(key_file.read_bytes()).decrypt(value.encode()).decode()
            except (InvalidToken, ValueError):
                pass
    else:
        value = os.environ.get("DART_AZURE_CONNECTION_STRING", "")
    if not value:
        fail("no Azure connection string: pass --settings <DART dart_settings.json> "
             "or set DART_AZURE_CONNECTION_STRING")
    account = next((p.split("=", 1)[1] for p in value.split(";") if p.startswith("AccountName=")), "")
    if account != DEST_ACCOUNT:
        fail(f"connection string is for storage account '{account or '?'}', not '{DEST_ACCOUNT}'")
    return value


def blob_client_factory(connection: str):
    try:
        from azure.storage.blob import BlobServiceClient, ContentSettings
    except ImportError:
        fail("azure-storage-blob is required; run with ~/GitHub/DART/.venv/bin/python")
    service = BlobServiceClient.from_connection_string(connection, retry_total=3)

    def upload(container: str, blob: str, data: bytes) -> None:
        content_type = CONTENT_TYPES.get(Path(blob).suffix.lower(), "application/octet-stream")
        service.get_blob_client(container=container, blob=blob).upload_blob(
            data, overwrite=False, content_settings=ContentSettings(content_type=content_type))

    return upload


def copy_asset(upload, field: str, source: str, container: str, blob: str) -> str:
    """Copy one public blob to digitalgrinnell without overwriting; return 'copied' or 'present'."""
    target = dest_url(container, blob)
    status, data = fetch(source)
    if status != 200 or not data:
        raise RuntimeError(f"could not download {field} (HTTP {status}): {source}")
    if field == "object_transcript":
        problems = transcript_problems(data, source)
        if problems:
            raise RuntimeError("; ".join(problems))
    digest = hashlib.sha256(data).hexdigest()
    dest_status, existing = fetch(target)
    if dest_status == 200:
        if hashlib.sha256(existing).hexdigest() != digest:
            raise RuntimeError(f"{target} already exists with different content; not overwriting")
        return "present"
    if dest_status != 404:
        raise RuntimeError(f"cannot check {target} (HTTP {dest_status})")
    try:
        upload(container, blob, data)
    except Exception as error:  # Azure SDK errors vary; never echo credentials
        raise RuntimeError(f"upload failed for {target}: {type(error).__name__}") from None
    check_status, uploaded = fetch(target)
    if check_status != 200 or hashlib.sha256(uploaded).hexdigest() != digest:
        raise RuntimeError(f"verification failed for {target} (HTTP {check_status})")
    return "copied"


def cmd_merge(args: argparse.Namespace) -> None:
    mapping = args.mapping or (args.source / "reunion-alumni-merge-map.csv")
    if not mapping.is_file():
        fail(f"mapping not found: {mapping}; run 'init' first")
    metadata, _, _ = source_paths(args.source)
    source = {r["objectid"]: r for r in read_csv(metadata)[1]}
    _, entries = read_csv(mapping)

    errors: list[str] = []
    plan: dict[str, list[tuple[dict[str, str], dict[str, str]]]] = collections.defaultdict(list)
    for entry in entries:
        if entry.get("include", "").strip().lower() not in {"yes", "y", "true", "1"}:
            print(f"skip (include={entry.get('include')!r}): {entry['objectid']}")
            continue
        oid = entry["objectid"]
        meta = source.get(oid)
        slug = entry.get("collection", "").strip()
        year = entry.get("class_year", "").strip()
        if meta is None:
            errors.append(f"{oid}: not in {metadata}")
            continue
        if not year.isdigit():
            errors.append(f"{oid}: class_year is missing")
            continue
        if slug != decade_collection(int(year)):
            errors.append(f"{oid}: class_year {year} does not belong in '{slug}'")
            continue
        if slug == RESERVED_CORE or slug.startswith("_"):
            errors.append(f"{oid}: '{slug}' is reserved")
            continue
        for field in ("title", "first_name", "last_name", "creator_personal"):
            if not entry.get(field, "").strip() or "'YY" in entry.get(field, ""):
                errors.append(f"{oid}: {field} is incomplete")
        plan[slug].append((meta, entry))
    if errors:
        fail("mapping problems:\n  " + "\n  ".join(errors))

    upload = blob_client_factory(connection_string(args)) if args.apply else None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    total_added = copied = present = 0
    for slug in sorted(plan):
        core = args.show_collections / slug / "_data" / f"{slug}_metadata.csv"
        if not core.is_file():
            fail(f"{slug}: core not found at {core}")
        header, core_rows = read_csv(core)
        existing_ids = {r.get("objectid", "") for r in core_rows}
        existing_sources = {r.get("originating_system_id", ""): r.get("objectid", "") for r in core_rows}
        existing_media = {r.get("object_location", ""): r.get("objectid", "") for r in core_rows}

        pending = []
        print(f"\n== {slug} ({len(core_rows)} existing rows) -> {core}")
        for meta, entry in plan[slug]:
            oid = meta["objectid"]
            if oid in existing_ids:
                print(f"  already present, skipped: {oid}")
                continue
            assets, problems = asset_plan(meta, slug)
            urls = {field: dest_url(container, blob) for field, _, container, blob in assets}
            for key, index in ((meta.get("originating_system_id"), existing_sources),
                               (urls.get("object_location"), existing_media)):
                if key and key in index:
                    problems.append(f"duplicates {index[key]} ({key})")
            missing = [f for f in urls if f not in header]
            if missing:
                problems.append(f"core lacks column(s) {', '.join(missing)}")
            if not problems and not args.apply:
                problems, lines = preflight(assets)
            else:
                lines = [f"      copy -> {u}" for u in urls.values()]
            if problems:
                fail(f"{slug}: {oid}:\n  " + "\n  ".join(problems))
            row = build_row(meta, entry, header, core_rows, urls)
            pending.append((row, assets))
            print(f"  + {oid}  {row['title']}")
            print("\n".join(lines))
        if not pending:
            continue
        total_added += len(pending)
        if not args.apply:
            continue

        for row, assets in pending:
            for field, src, container, blob in assets:
                try:
                    result = copy_asset(upload, field, src, container, blob)
                except RuntimeError as error:
                    fail(f"{slug}: {row['objectid']}: {error}\nNo rows were written for {slug}; "
                         "fix the problem and rerun (verified copies are reused).")
                copied += result == "copied"
                present += result == "present"
                print(f"    {result}: {dest_url(container, blob)}")

        new_rows = [row for row, _ in pending]
        working = args.projects / slug / ".DART-working-directory"
        working.mkdir(parents=True, exist_ok=True)
        backup = working / f"{core.name}.backup_{stamp}"
        shutil.copy2(core, backup)
        data = core.read_bytes()
        terminator = "\r\n" if b"\r\n" in data else "\n"
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=header, lineterminator=terminator)
        writer.writerows(new_rows)
        with core.open("ab") as handle:
            if data and not data.endswith(b"\n"):
                handle.write(terminator.encode())
            handle.write(buffer.getvalue().encode("utf-8"))
        if len(read_csv(core)[1]) != len(core_rows) + len(new_rows):
            shutil.copy2(backup, core)
            fail(f"{slug}: row count check failed; restored {core} from {backup}")
        record_note(args.show_collections / slug, new_rows, backup, args)
        print(f"  appended {len(new_rows)} row(s); backup {backup}")

    if args.apply:
        print(f"\nCopied {copied} file(s) to {DEST_ACCOUNT}; {present} already present and verified.")
        print(f"Appended {total_added} row(s) across {len(plan)} collection(s).")
    else:
        print(f"\nWould copy files to {DEST_ACCOUNT} and append {total_added} row(s) "
              f"across {len(plan)} collection(s).")
        if total_added:
            print("Dry run only. Rerun with --apply (and --settings or DART_AZURE_CONNECTION_STRING).")


def record_note(collection_dir: Path, rows: list[dict[str, str]], backup: Path, args: argparse.Namespace) -> None:
    notes = collection_dir / "Collection_Notes.md"
    try:
        backup = Path("~") / backup.relative_to(HOME)
    except ValueError:
        pass
    lines = [
        "",
        f"## {args.event} Oral Histories Merge — {datetime.now():%B %-d, %Y}",
        "",
        f"Appended {len(rows)} OHM-processed interview(s) from `{args.source.name}` with",
        "`operations/collections/reunion_2026/merge_reunion_oral_histories.py`. Object IDs were preserved; MP3s,",
        f"image derivatives, and transcripts were copied to the `{DEST_ACCOUNT}`",
        f"storage account under `{collection_dir.name}/` and verified byte-for-byte.",
        f"Pre-merge backup: `{backup}`.",
        "",
    ]
    lines += [f"- `{r['objectid']}` — {r['title']}" for r in rows]
    with notes.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help=f"OHM CollectionBuilder project (default {DEFAULT_SOURCE})")
    parser.add_argument("--mapping", type=Path, help="mapping CSV (default <source>/reunion-alumni-merge-map.csv)")
    parser.add_argument("--event", default=DEFAULT_EVENT, help=f"event named in descriptions/notes (default '{DEFAULT_EVENT}')")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="write a reviewable mapping CSV")
    init.add_argument("--force", action="store_true", help="overwrite an existing mapping")
    merge = sub.add_parser("merge", help="copy files to digitalgrinnell and append rows to SHOW alumni cores (dry run unless --apply)")
    merge.add_argument("--show-collections", type=Path, default=DEFAULT_SHOW_COLLECTIONS)
    merge.add_argument("--projects", type=Path, default=DEFAULT_PROJECTS, help="DART projects root for backups")
    merge.add_argument("--settings", type=Path, help=f"DART dart_settings.json holding an encrypted {DEST_ACCOUNT} connection string "
                       "(default: DART_AZURE_CONNECTION_STRING environment variable)")
    merge.add_argument("--apply", action="store_true", help="upload files and write the SHOW cores")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.source = args.source.expanduser()
    if args.command == "init":
        cmd_init(args)
    else:
        args.show_collections = args.show_collections.expanduser()
        args.projects = args.projects.expanduser()
        cmd_merge(args)


if __name__ == "__main__":
    main()
