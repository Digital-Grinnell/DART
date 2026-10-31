#!/usr/bin/env python3
"""Prepare approved non-OHM transcript sidecars, then run a managed batch."""
from __future__ import annotations

import argparse
import csv
import hashlib
from html import unescape
from html.parser import HTMLParser
import io
import json
import logging
import os
from pathlib import Path
import re
import signal
import sys
import threading
import time
from urllib.request import urlopen
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MAX_BYTES = 20 * 1024**2


class CueText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self.parts.append("\n")


def cue_milliseconds(value: str) -> int:
    match = re.fullmatch(r"(?:(\d{2,}):)?(\d{2,}):([0-5]\d)\.(\d{3})", value)
    if not match:
        raise ValueError(f"Invalid WebVTT timestamp: {value!r}")
    hours, minutes, seconds, milliseconds = (int(part or 0) for part in match.groups())
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds


def convert_vtt(content: bytes) -> tuple[bytes, int, list[str]]:
    """Keep cue order/text; floor start milliseconds for SHOW's second-resolution seeking."""
    if len(content) > MAX_BYTES:
        raise ValueError("VTT exceeds 20 MiB")
    text = content.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if not re.fullmatch(r"WEBVTT(?:[ \t].*)?", lines[0]):
        raise ValueError("Missing WEBVTT header")
    blocks = re.split(r"\n[ \t]*\n", text.strip())
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["timestamp", "speaker", "words"])
    count = 0
    notices = []
    previous_start = -1
    for block in blocks[1:]:
        cue = block.splitlines()
        if not cue:
            continue
        if cue[0] in {"STYLE", "REGION"} or re.match(r"NOTE(?:[ \t]|$)", cue[0]):
            continue
        timing = 0 if "-->" in cue[0] else 1
        if timing >= len(cue):
            raise ValueError("Cue has no timing line")
        match = re.fullmatch(r"(\S+)[ \t]+-->[ \t]+(\S+)(?:[ \t]+.*)?", cue[timing])
        if not match:
            raise ValueError("Invalid WebVTT cue timing")
        start = cue_milliseconds(match.group(1))
        try:
            end = cue_milliseconds(match.group(2))
        except ValueError:
            end = None
            notices.append(f"Cue {count + 1}: invalid source end; only the valid start is used by SHOW")
        if end is not None and end <= start:
            notices.append(f"Cue {count + 1}: source end is not after start; start/text preserved")
        if start < previous_start:
            notices.append(f"Cue {count + 1}: source starts out of order; order preserved")
        previous_start = start
        payload = "\n".join(cue[timing + 1:])
        speakers = list(dict.fromkeys(unescape(name.strip()) for name in
                                     re.findall(r"<v(?:\.[^\s>]+)*[ \t]+([^>]+)>", payload)))
        payload = re.sub(r"<(?:\d{2,}:)?[0-5]\d:[0-5]\d\.\d{3}>", "", payload)
        parsed = CueText()
        parsed.feed(payload)
        parsed.close()
        words = "".join(parsed.parts).strip()
        if not words:
            notices.append(f"Cue {count + 1}: empty source cue omitted")
            continue
        seconds = start // 1000
        timestamp = f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"
        writer.writerow([timestamp, "; ".join(speakers), words])
        count += 1
    if not count:
        raise ValueError("VTT contains no cues")
    result = output.getvalue().encode("utf-8")
    if len(result) > MAX_BYTES:
        raise ValueError("Converted CSV exceeds SHOW's 20 MiB limit")
    return result, count, notices


def transcript_plan(source: Path, rows: list[dict[str, str]]) -> tuple[list[dict], list[dict]]:
    names: dict[str, list[dict]] = {}
    for row in rows:
        names.setdefault(row["original_file_name"], []).append(row)
    plans, exceptions = [], []
    for directory, subdirs, filenames in os.walk(source, followlinks=False):
        subdirs.sort()
        folder = Path(directory)
        if any((folder / name).is_symlink() for name in [*subdirs, *filenames]):
            raise ValueError(f"Source contains symlinks: {folder}")
        audio = sorted(name for name in filenames if Path(name).suffix.lower() == ".mp3")
        transcripts = sorted(name for name in filenames if Path(name).suffix.lower() == ".vtt")
        if not transcripts:
            continue
        if len(audio) != 1 or len(transcripts) != 1:
            exceptions.append(dict(folder=str(folder.relative_to(source)), audio=audio,
                                   transcripts=transcripts, reason="Not exactly one MP3 and one VTT"))
            continue
        if len(names.get(audio[0], [])) != 1:
            exceptions.append(dict(folder=str(folder.relative_to(source)), audio=audio,
                                   transcripts=transcripts, reason="Audio filename has no unique GEMS row"))
            continue
        vtt = folder / transcripts[0]
        try:
            data, cues, notices = convert_vtt(vtt.read_bytes())
        except (ValueError, UnicodeError) as exc:
            exceptions.append(dict(folder=str(folder.relative_to(source)), audio=audio,
                                   transcripts=transcripts, reason=f"Conversion failed: {exc}"))
            continue
        plans.append(dict(audio=audio[0], source=str(vtt), content=data, cues=cues,
                          notices=notices,
                          source_sha256=hashlib.sha256(vtt.read_bytes()).hexdigest()))
    return plans, exceptions


def upload_transcript(client, slug: str, filename: str, content: bytes) -> str:
    from azure.storage.blob import ContentSettings

    blob = client.get_blob_client(container="transcripts", blob=f"{slug}/{filename}")
    if blob.exists(timeout=30):
        if blob.download_blob(timeout=30).readall() != content:
            raise ValueError(f"Existing transcript differs: {slug}/{filename}; never overwritten")
    else:
        blob.upload_blob(content, overwrite=False, timeout=30,
                         content_settings=ContentSettings(content_type="text/csv; charset=utf-8"))
    url = blob.url.split("?", 1)[0]
    with urlopen(url, timeout=60) as response:
        public = response.read(MAX_BYTES + 1)
    if public != content:
        raise ValueError(f"Public transcript verification failed: {slug}/{filename}")
    return url


def prepare_collection(client, entry: dict, inventory: dict) -> dict:
    from dart_storage import atomic_bytes, atomic_json
    from dart_workflows import ASSETS, read_csv

    source = Path(entry["input_dir"])
    files = sorted(path for path in source.rglob("*") if path.is_file())
    if (len(files) != inventory["source_files"]
            or sum(path.stat().st_size for path in files) != inventory["source_bytes"]
            or any(hashlib.sha256(path.read_bytes()).hexdigest() != inventory["input_sha256"][str(path)]
                   for path in [source.parent / "collection_metadata.csv",
                                *[p for p in files if p.suffix.lower() == ".vtt"]])):
        raise ValueError("Source inventory or metadata/transcript fingerprints changed")
    if sorted(str(path.relative_to(source)) for path in files
              if path.suffix.lower() not in ASSETS or path.name.startswith(".")) != inventory["excluded_files"]:
        raise ValueError("Unsupported-file inventory changed")
    metadata = source.parent / "collection_metadata.csv"
    columns, rows = read_csv(metadata)
    plans, exceptions = transcript_plan(source, rows)
    destination = Path(entry["setup"]["gems_metadata_csv"])
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if "object_transcript" not in columns:
        columns.append("object_transcript")
    by_name = {row["original_file_name"]: row for row in rows}
    by_id = {row["objectid"]: row for row in rows}
    parent_audio: dict[str, list[str]] = {}
    for row in rows:
        if Path(row["original_file_name"]).suffix.lower() == ".mp3" and row.get("parentid"):
            parent_audio.setdefault(row["parentid"], []).append(row["original_file_name"])
    report = dict(collection=entry["collection_id"], transcripts=[], exceptions=exceptions)
    for plan in plans:
        name = Path(plan["audio"]).stem + "_transcript.csv"
        url = upload_transcript(client, entry["collection_id"], name, plan["content"])
        row = by_name[plan["audio"]]
        if row.get("object_transcript") and row["object_transcript"] != url:
            raise ValueError("Existing GEMS transcript reference differs; review before replacing")
        row["object_transcript"] = url
        parent = row.get("parentid", "")
        if parent in by_id and parent_audio[parent] == [plan["audio"]]:
            if by_id[parent].get("object_transcript") not in (None, "", url):
                raise ValueError("Existing parent transcript differs")
            by_id[parent]["object_transcript"] = url
        atomic_bytes(destination.parent / name, plan["content"])
        report["transcripts"].append({k: v for k, v in plan.items() if k != "content"} | dict(url=url))
        print(f"{entry['collection_id']}: verified transcript for {plan['audio']} ({plan['cues']} cues)", flush=True)
        for notice in plan["notices"]:
            print(f"WARNING [{entry['collection_id']}/{plan['audio']}]: {notice}", flush=True)
    for exception in exceptions:
        print(f"WARNING [{entry['collection_id']}]: {json.dumps(exception)}", flush=True)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    data = output.getvalue().encode("utf-8")
    if destination.exists() and destination.read_bytes() != data:
        raise ValueError("Prepared GEMS sidecar differs from previous preparation")
    atomic_bytes(destination, data)
    atomic_json(destination.parent / "transcript-report.json", report)
    return report


def run(plan_path: str) -> int:
    from azure.core.exceptions import AzureError
    from azure.storage.blob import BlobServiceClient
    from dotenv import dotenv_values
    from dart_batch import run_batch, validate_queue
    from dart_linux import read_private_json
    from dart_service import JobService, RedactedFormatter
    from dart_storage import Storage, atomic_bytes, atomic_json, load_environment, private, redact

    os.umask(0o077)
    plan = read_private_json(plan_path)
    queue = read_private_json(plan["queue"])
    inventory_path = Path(plan["inventory"])
    private(inventory_path)
    inventory = {item["collection_id"]: item for item in json.loads(inventory_path.read_text())}
    validate_queue(queue)
    if set(inventory) != {entry["collection_id"] for entry in queue["collections"]}:
        raise ValueError("Inventory and queue collection sets differ")
    load_environment("/data/dart/config/dart.env")
    console = logging.StreamHandler()
    console.setFormatter(RedactedFormatter("%(levelname)s %(message)s"))
    logging.basicConfig(level=logging.WARNING, handlers=[console], force=True)
    storage = Storage.from_environment()
    for root in (storage.config, storage.data):
        lock_path = root / ".dart-service.lock"
        if lock_path.exists() or lock_path.is_symlink():
            private(lock_path)
    deadline = time.monotonic() + 24 * 60 * 60
    while True:
        try:
            service = JobService(storage)
            break
        except RuntimeError as exc:
            if not str(exc).startswith("Another DART writer owns this root, or the lock is unsafe:"):
                raise
            storage.check()
            if time.monotonic() >= deadline:
                raise RuntimeError("24-hour writer wait expired; inspect the active job") from exc
            print("Waiting for the active DART writer; no source, settings, or media changes yet.", flush=True)
            time.sleep(30)
    with service:
        service.claim("headless")
        storage.require_space()
        for directory in (storage.data / "batches").glob("*/queue.json"):
            if json.loads(directory.read_text()) == queue:
                raise ValueError("This queue already has batch evidence; resume Mac acceptance instead of rerunning")
        env = storage.config / "dart.env"
        original = env.read_bytes()
        values = dotenv_values(env, interpolate=False)
        roots = json.loads(values["DART_SOURCE_ROOTS"])
        for entry in queue["collections"]:
            run_path = str(Path(entry["input_dir"]).parent)
            approval = dict(path=run_path, mount="/data")
            if approval not in roots:
                roots.append(approval)
        lines = original.decode("utf-8").splitlines(keepends=True)
        indices = [i for i, line in enumerate(lines) if re.match(r"^\s*(?:export\s+)?DART_SOURCE_ROOTS\s*=", line)]
        if len(indices) != 1:
            raise ValueError("Environment requires exactly one single-line source allowlist")
        lines[indices[0]] = "DART_SOURCE_ROOTS='" + json.dumps(roots) + "'\n"
        changed = "".join(lines).encode()
        from dotenv import dotenv_values as parse_env
        proposed = parse_env(stream=io.StringIO(changed.decode()), interpolate=False)
        if {k: v for k, v in values.items() if k != "DART_SOURCE_ROOTS"} != {
                k: v for k, v in proposed.items() if k != "DART_SOURCE_ROOTS"}:
            raise ValueError("Unrelated environment values would change")
        backup = env.with_name(f"dart.env.before-{plan['name']}")
        if not backup.exists():
            atomic_bytes(backup, original)
        if env.read_bytes() != original:
            raise ValueError("Environment changed during allowlist update")
        atomic_bytes(env, changed)
        load_environment(str(env))
        service.storage = Storage.from_environment()
        if (service.storage.config, service.storage.data) != (storage.config, storage.data):
            raise ValueError("Managed storage roots changed")
        client = BlobServiceClient.from_connection_string(os.environ["DART_AZURE_CONNECTION_STRING"])
        reports = []
        for entry in queue["collections"]:
            try:
                service.storage.source(entry["input_dir"], directory=True)
                reports.append(prepare_collection(client, entry, inventory[entry["collection_id"]]))
            except (OSError, ValueError, RuntimeError, AzureError, URLError) as exc:
                reports.append(dict(collection=entry["collection_id"], error=redact(exc)))
                print(f"ERROR [{entry['collection_id']}]: transcript preparation failed: {redact(exc)}", flush=True)
        unavailable = plan.get("unavailable", [])
        for slug in unavailable:
            print(f"UNAVAILABLE [{slug}]: no approved GEMS source; not processed", flush=True)
        atomic_json(Path(plan["report"]), dict(collections=reports, unavailable=unavailable))
        failed = {r["collection"] for r in reports if "error" in r}
        if failed:
            # Missing prepared metadata makes normal batch setup record a per-collection failure.
            for entry in queue["collections"]:
                if entry["collection_id"] in failed:
                    destination = Path(entry["setup"]["gems_metadata_csv"])
                    if destination.exists():
                        raise RuntimeError("Failed transcript preparation has an existing sidecar; inspect before running")
        interrupted = threading.Event()

        def stop(_number, _frame) -> None:
            interrupted.set()
            service._cancel.set()

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)
        return run_batch(service, queue, interrupted)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    args = parser.parse_args()
    try:
        raise SystemExit(run(args.plan))
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        from dart_storage import redact
        print(f"ERROR: {redact(exc)}", file=sys.stderr, flush=True)
        raise SystemExit(1)
