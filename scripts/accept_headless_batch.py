#!/usr/bin/env python3
"""Mac-only, opt-in acceptance of new-record-only headless publishing packages."""
from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dart_handoff


# Runs with managed writer locks; credentials never leave Linux.
REMOTE = r'''
import csv, hashlib, json, sys
from pathlib import Path
from dart_service import JobService
from dart_storage import Storage, absolute, atomic_bytes, load_environment, private
from dart_workflows import ASSETS, digest
request = json.load(sys.stdin)
load_environment("/data/dart/config/dart.env")
storage = Storage.from_environment()
with JobService(storage):
    batch = storage.data / "batches" / request["batch"]
    summary = json.loads((batch / "summary.json").read_text())
    queue = json.loads((batch / "queue.json").read_text())
    if request["action"] == "summary":
        print(json.dumps(dict(summary=summary, queue=queue)))
    else:
        slug = request["collection"]
        record, = [r for r in summary["collections"] if r["collection_id"] == slug]
        entry, = [r for r in queue["collections"] if r["collection_id"] == slug]
        if record["state"] != "succeeded" or not entry.get("allow_uploads"):
            raise ValueError("Requires a succeeded publishing collection")
        job_id = record["job_id"]
        project = storage.projects / slug
        job_dir = storage.jobs / job_id
        job = json.loads((job_dir / "job.json").read_text())
        if job["state"] != "succeeded" or job["kind"] != "prepare" or not job["inputs"]["allow_uploads"]:
            raise ValueError("Publishing job is not succeeded")
        core = storage.managed(str(project / "core-snapshot.csv"))
        if request["action"] == "push":
            content = request["content"].encode("utf-8")
            export = storage.managed(str(project / "handoff" / job_id / "export.csv"))
            if content != export.read_bytes():
                raise ValueError("Only the exact successful publishing export may be pushed")
            expected = request["expected"]
            if digest(core) not in (expected, hashlib.sha256(content).hexdigest()):
                raise ValueError("Server snapshot changed since validation")
            atomic_bytes(core, content)
            print(json.dumps(dict(sha256=digest(core))))
        else:
            settings = json.loads((job_dir / "settings-snapshot.json").read_text())
            source = storage.source(entry["input_dir"], directory=True)
            if settings["collection-id"] != slug or job["inputs"]["input_dir"] != str(source):
                raise ValueError("Source/job collection mismatch")
            paths = []
            for path in sorted(source.rglob("*")):
                if path.is_symlink() or path.resolve(strict=True) != path:
                    raise ValueError("Source aliases require manual review")
                if path.is_file():
                    paths.append(dict(path=str(path), size=path.stat().st_size,
                                      eligible=path.suffix.lower() in ASSETS and not path.name.startswith(".")))
            gems = storage.source(settings["gems_metadata_csv"])
            with gems.open(newline="") as handle:
                reader = csv.DictReader(handle)
                if "original_file_name" not in reader.fieldnames:
                    raise ValueError("GEMS filename column missing")
                names = [row["original_file_name"] for row in reader]
            inventory_path = absolute(request["inventory"])
            if not inventory_path.is_relative_to(storage.config):
                raise ValueError("Inventory must be under private configuration")
            private(inventory_path)
            inventory = json.loads(inventory_path.read_text())
            item, = [r for r in inventory if r["collection_id"] == slug]
            if item["run"] != str(source.parent):
                raise ValueError("Inventory refers to another source run")
            if (not settings["group_compound_objects"] or settings["create_multiple_objects"]
                    or settings["process_OHM_data"]):
                raise ValueError("This acceptance tool requires flat compounds, not nested/OHM data")
            print(json.dumps(dict(
                job_id=job_id, project=str(project), snapshot_sha256=digest(core),
                analysis=json.loads((job_dir / "analysis.json").read_text()),
                source=str(source), files=paths, gems_names=names, inventory=item,
                azure_path=settings["azure_blob_storage_path"])))
'''


class ReviewRequired(ValueError):
    """A collection cannot safely be accepted without human review."""


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def atomic(path: Path, content: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def table(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
    columns = reader.fieldnames
    if not columns or len(columns) != len(set(columns)):
        raise ReviewRequired("Missing or duplicate CSV columns")
    rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ReviewRequired("Malformed CSV row shape")
    return columns, rows


def validate(content: bytes, manifest: dict, evidence: dict, slug: str) -> dict:
    """Prove row shape, families, source coverage, and explicit exclusions."""
    from dart_processing import get_derivative_azure_paths

    columns, rows = table(content)
    required = {"objectid", "original_file_name", "parentid", "title", "object_location",
                "image_small", "image_thumb"}
    if not required.issubset(columns) or not rows or len(rows) != manifest["rows"]:
        raise ReviewRequired("Missing required columns or package row-count mismatch")
    if manifest.get("warnings") or manifest.get("id_conflicts") or manifest.get("derivatives_local_only") is not False:
        raise ReviewRequired("Package warnings, ID conflicts, or nonpublishing derivatives")
    stats = manifest.get("gems_backfill")
    if (not stats or stats.get("unmatched_dart_rows") or stats.get("gems_duplicate_names")
            or stats.get("matched_rows") != len(rows) or stats.get("gems_rows") != len(evidence["gems_names"])):
        raise ReviewRequired("Incomplete or ambiguous GEMS backfill")
    ids, names = [r["objectid"] for r in rows], [r["original_file_name"] for r in rows]
    if (len(set(ids)) != len(ids) or len(set(names)) != len(names)
            or any(not re.fullmatch(re.escape(slug) + r"_dg_\d+", value) for value in ids)
            or any(not name or Path(name).name != name or "\\" in name for name in names)):
        raise ReviewRequired("Missing/duplicate/unsafe IDs or filenames")
    by_id = {r["objectid"]: r for r in rows}
    analysis = evidence["analysis"]
    objects = {o["objectid"]: o for o in analysis["objects"]}
    parents = {p["objectid"]: p for p in analysis["parents"]}
    if (len(objects) != len(analysis["objects"]) or len(parents) != len(analysis["parents"])
            or set(objects) & set(parents) or set(by_id) != set(objects) | set(parents)):
        raise ReviewRequired("Export IDs differ from analyzed objects/parents")
    source = Path(evidence["source"])
    inventory = evidence["inventory"]
    physical = {f["path"] for f in evidence["files"] if f["eligible"]}
    excluded = {str(Path(f["path"]).relative_to(source)) for f in evidence["files"] if not f["eligible"]}
    if (len(physical) != sum(f["eligible"] for f in evidence["files"])
            or inventory["source_files"] != len(evidence["files"])
            or inventory["source_bytes"] != sum(f["size"] for f in evidence["files"])
            or excluded != set(inventory["excluded_files"]) or inventory["eligible_assets"] != len(objects)
            or physical != {o["filepath"] for o in objects.values()}
            or any(f["size"] <= 0 for f in evidence["files"] if f["eligible"])):
        raise ReviewRequired("Current sources differ from approved inventory/analysis")
    missing = set(evidence["gems_names"]) - set(names)
    unexplained = missing - {Path(name).name for name in excluded}
    if unexplained:
        raise ReviewRequired("Unexplained GEMS records absent from export: " + ", ".join(sorted(unexplained)))
    if not all(evidence["gems_names"]) or len(set(evidence["gems_names"])) != len(evidence["gems_names"]):
        raise ReviewRequired("Missing/duplicate GEMS filename keys")
    for row in rows:
        if not row["title"].strip():
            raise ReviewRequired("Blank title")
        parent = row["parentid"]
        if parent:
            if parent not in parents or parent == row["objectid"] or row["objectid"] in parents:
                raise ReviewRequired("Invalid or nested parent link for flat-compound batch")
        if row["objectid"] in objects:
            obj = objects[row["objectid"]]
            if (row["original_file_name"] != Path(obj["filepath"]).name
                    or parent != (obj.get("parentid") or "")
                    or row["original_file_name"].startswith("_")):
                raise ReviewRequired("Physical object filename/parent differs from analysis")
            url = urlsplit(row["object_location"])
            expected = "/" + evidence["azure_path"].strip("/") + "/" + row["objectid"] + Path(obj["filepath"]).suffix
            if (url.scheme != "https" or not url.netloc.endswith(".blob.core.windows.net")
                    or url.path != expected or url.query or url.fragment):
                raise ReviewRequired("Original Azure URL does not match configured destination")
        elif not row["original_file_name"].startswith("_") or row["object_location"]:
            raise ReviewRequired("Invalid generated parent")
        for field in ("image_small", "image_thumb"):
            value = row[field]
            if value:
                url = urlsplit(value)
                if url.scheme != "https" or not url.netloc.endswith(".blob.core.windows.net") or url.query or url.fragment:
                    raise ReviewRequired("Nonpublishing derivative URL")
    accounts = {urlsplit(r["object_location"]).netloc for r in rows if r["objectid"] in objects}
    if len(accounts) != 1:
        raise ReviewRequired("Inconsistent original Azure accounts")
    account = next(iter(accounts))
    for parent_id in parents:
        children = [r for r in rows if r["parentid"] == parent_id]
        if len(children) != parents[parent_id]["child_count"] or not children:
            raise ReviewRequired("Compound child count mismatch")
    for row in rows:
        for field, destination, suffix in zip(
                ("image_small", "image_thumb"), get_derivative_azure_paths(evidence["azure_path"]),
                ("_SMALL.jpg", "_TN.jpg")):
            if not row[field]:
                if row["objectid"] in objects and Path(objects[row["objectid"]]["filepath"]).suffix.lower() in {
                    ".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".gif", ".bmp", ".webp",
                }:
                    raise ReviewRequired("Missing expected image/PDF derivative")
                continue
            choices = [row["objectid"]] if row["objectid"] in objects else [
                child["objectid"] for child in rows if child["parentid"] == row["objectid"]]
            expected = {f"https://{account}/{destination.strip('/')}/{oid}{suffix}" for oid in choices}
            if row[field] not in expected:
                raise ReviewRequired("Derivative URL does not match object/family destination")
    return dict(rows=len(rows), assets=len(objects), parents=len(parents),
                excluded_files=sorted(excluded), excluded_gems_names=sorted(missing),
                ignored_gems_columns=stats.get("ignored_gems_columns", []))


def accept_core(core: Path, content: bytes, manifest: dict, work: Path) -> str:
    """Back up and replace only a matching header-only core; exact retries are safe."""
    if core.is_symlink() or core.name == "collection-template.csv":
        raise ReviewRequired("Protected/aliased core")
    before = core.read_bytes()
    if before == content:
        return "already_identical"
    columns, rows = table(before)
    new_columns, _ = table(content)
    if rows or columns != new_columns or sha(before) != manifest["core_snapshot_sha256"]:
        raise ReviewRequired("Core is populated, schema differs, or preparation snapshot is stale")
    backup = work / f"core-before-{sha(before)}.csv"
    if backup.exists() and backup.read_bytes() != before:
        raise ReviewRequired("Backup collision")
    atomic(backup, before)
    if core.read_bytes() != before:
        raise ReviewRequired("Core changed before write")
    atomic(core, content)
    if core.read_bytes() != content:
        raise RuntimeError("Core write verification failed")
    return "written"


def remote(host: str, request: dict) -> dict:
    command = "cd /home/sysadmin/GitHub/DART && .venv/bin/python -c " + shlex.quote(REMOTE)
    data = dart_handoff._ssh(host, command, subprocess.run, data=json.dumps(request).encode())
    return json.loads(data)


def check_show_config(show: Path, slug: str) -> None:
    config = show / "collections" / slug / "_config.yml"
    result = subprocess.run(
        ["ruby", "-ryaml", "-rjson", "-e", "puts JSON.generate(YAML.load_file(ARGV.fetch(0)))", str(config)],
        check=True, capture_output=True, text=True,
    )
    values = json.loads(result.stdout)
    if values.get("baseurl") != "/" + slug or values.get("metadata") != slug + "_metadata":
        raise ReviewRequired("SHOW overlay baseurl/metadata do not match the selected core")


def update_catalog(path: Path, slug: str, values: dict[str, str], work: Path, *,
                   apply: bool) -> str:
    """Change only approved cells, retaining unrelated rows byte for byte."""
    if path.resolve(strict=True) != path:
        raise ReviewRequired("Catalog path is aliased")
    before = path.read_bytes()
    text = before.decode("utf-8-sig")
    lines = text.splitlines(keepends=True)
    reader = csv.reader(io.StringIO(text, newline=""))
    header = next(reader)
    if len(set(header)) != len(header) or not {"objectid", *values}.issubset(header):
        raise ReviewRequired("Catalog columns missing or duplicated")
    end = reader.line_num
    chunks = ["".join(lines[:end])]
    matches = 0
    for row in reader:
        start, end = end, reader.line_num
        if len(row) != len(header):
            raise ReviewRequired("Malformed catalog row")
        if row[header.index("objectid")] == slug:
            matches += 1
            for key, value in values.items():
                row[header.index(key)] = value
            buffer = io.StringIO(newline="")
            csv.writer(buffer, lineterminator="\r\n" if lines[end - 1].endswith("\r\n") else "\n").writerow(row)
            chunks.append(buffer.getvalue())
        else:
            chunks.append("".join(lines[start:end]))
    if matches != 1:
        raise ReviewRequired("Catalog requires exactly one row for this collection")
    after = "".join(chunks).encode("utf-8")
    if before.startswith(b"\xef\xbb\xbf"):
        after = b"\xef\xbb\xbf" + after
    if not apply:
        return "validated"
    if before == after:
        return "already_identical"
    backup = work / f"catalog-before-{sha(before)}.csv"
    if backup.exists() and backup.read_bytes() != before:
        raise ReviewRequired("Catalog backup collision")
    atomic(backup, before)
    if path.read_bytes() != before:
        raise ReviewRequired("Catalog changed before write")
    atomic(path, after)
    if path.read_bytes() != after:
        raise RuntimeError("Catalog write verification failed")
    return "written"


def run(args: argparse.Namespace) -> int:
    show = args.show_root.resolve(strict=True)
    root = args.working_root.expanduser()
    root.mkdir(parents=True, exist_ok=True)
    state = root / ".DART-working-directory" / f"accept-{args.batch_id}"
    state.mkdir(parents=True, exist_ok=True)
    with (root / ".DART-working-directory" / "accept-headless.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        batch = remote(args.host, dict(action="summary", batch=args.batch_id))
        if batch["summary"]["id"] != args.batch_id or batch["summary"]["state"] == "running":
            raise ReviewRequired("Batch identity mismatch or batch still running")
        atomic(state / "batch-evidence.json", json.dumps(batch, indent=2).encode())
        entries = batch["queue"]["collections"]
        slugs = [e["collection_id"] for e in entries]
        if len(set(slugs)) != len(slugs):
            raise ReviewRequired("Duplicate queue collections")
        if (state / "summary.json").exists():
            atomic(state / f"previous-{uuid.uuid4().hex}.json", (state / "summary.json").read_bytes())
        report: dict = dict(batch_id=args.batch_id, apply=args.apply, build=args.build, collections=[])
        def persist() -> None:
            atomic(state / "summary.json", json.dumps(report, indent=2).encode())

        for entry in entries:
            slug = entry["collection_id"]
            result = dict(collection=slug, stage="preflight", state="running")
            report["collections"].append(result)
            try:
                if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", slug) or slug == "collection-template":
                    raise ReviewRequired("Unsafe collection slug")
                if not entry.get("allow_uploads") or entry.get("overwrite"):
                    raise ReviewRequired("Requires approved non-overwriting publishing queue")
                work = root / slug / ".DART-working-directory"
                work.mkdir(parents=True, exist_ok=True)
                core = show / "collections" / slug / "_data" / f"{slug}_metadata.csv"
                if core.resolve(strict=True) != core or core.name == "collection-template.csv":
                    raise ReviewRequired("Core path is aliased/reserved")
                evidence = remote(args.host, dict(action="evidence", batch=args.batch_id,
                                  collection=slug, inventory=args.inventory))
                atomic(work / f"accept-evidence-{args.batch_id}.json", json.dumps(evidence, indent=2).encode())
                pulled = dart_handoff.pull_package(
                    args.host, evidence["project"], evidence["job_id"], work,
                    expected_collection_id=slug,
                )
                content = Path(pulled["csv"]).read_bytes()
                manifest = json.loads(Path(pulled["manifest"]).read_text())
                result.update(job_id=evidence["job_id"], core=str(core),
                              validation=validate(content, manifest, evidence, slug))
                before = core.read_bytes()
                columns, rows = table(before)
                if before != content and (rows or columns != table(content)[0]
                                           or sha(before) != manifest["core_snapshot_sha256"]):
                    raise ReviewRequired("Core is not the unchanged header-only preparation snapshot")
                if evidence["snapshot_sha256"] not in (manifest["core_snapshot_sha256"], sha(content)):
                    raise ReviewRequired("Linux core snapshot changed since preparation")
                if args.build:
                    check_show_config(show, slug)
                catalog_values = {
                    "status": args.catalog_status,
                    "collection_group": args.catalog_group,
                    "progress status": args.catalog_progress,
                } if args.catalog_status is not None else {}
                if catalog_values:
                    update_catalog(show / "_data/digital_collections.csv", slug, catalog_values, work, apply=False)
                if not args.apply:
                    result.update(state="ready", stage="preview")
                else:
                    result["stage"] = "core_write"
                    persist()
                    result["core_write"] = accept_core(core, content, manifest, work)
                    result["stage"] = "snapshot_push"
                    persist()
                    if core.read_bytes() != content:
                        raise ReviewRequired("Core changed after acceptance; snapshot not pushed")
                    pushed = remote(args.host, dict(
                        action="push", batch=args.batch_id, collection=slug,
                        expected=evidence["snapshot_sha256"], content=content.decode("utf-8"),
                    ))
                    if pushed["sha256"] != sha(content):
                        raise RuntimeError("Pushed snapshot checksum mismatch")
                    result["snapshot_sha256"] = pushed["sha256"]
                    if catalog_values:
                        result["stage"] = "catalog_update"
                        persist()
                        result["catalog_update"] = update_catalog(
                            show / "_data/digital_collections.csv", slug, catalog_values, work, apply=True,
                        )
                        result["catalog_values"] = catalog_values
                    if args.build:
                        result["stage"] = "show_build"
                        log = work / f"accept-build-{args.batch_id}.log"
                        result["build_log"] = str(log)
                        persist()
                        with log.open("w") as handle:
                            subprocess.run(["rake", f"collection:build[{slug}]"], cwd=show,
                                           stdout=handle, stderr=subprocess.STDOUT, check=True,
                                           env={**os.environ, "SKIP_PAGEFIND": "false"})
                        if not all((show / "_site" / slug / name).is_file()
                                   for name in ("index.html", "browse.html")):
                            raise RuntimeError("SHOW build did not produce expected pages")
                    if core.read_bytes() != content:
                        raise ReviewRequired("Core changed during follow-up; inspect snapshot/build")
                    result.update(state="succeeded", stage="complete")
            except ReviewRequired as exc:
                result.update(state="review_required", message=str(exc))
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                result.update(state="failed", message=str(exc))
            result["finished_at"] = datetime.now(timezone.utc).isoformat()
            atomic(state / "summary.json", json.dumps(report, indent=2).encode())
            print(json.dumps(result), flush=True)
        print(f"Summary: {state / 'summary.json'}", flush=True)
        return int(any(r["state"] not in {"ready", "succeeded"} for r in report["collections"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--host", default="sysadmin@dg-landing")
    parser.add_argument("--show-root", type=Path, default=Path.home() / "GitHub/SHOW")
    parser.add_argument("--working-root", type=Path, default=Path.home() / "DART-projects")
    parser.add_argument("--inventory", default="/data/dart/config/overnight-20261029-inventory.json")
    parser.add_argument("--apply", action="store_true", help="Back up/write empty cores and push snapshots")
    parser.add_argument("--build", action="store_true", help="With --apply, build each accepted SHOW collection")
    parser.add_argument("--catalog-status", choices=["published", "draft"])
    parser.add_argument("--catalog-group")
    parser.add_argument("--catalog-progress")
    args = parser.parse_args()
    if not dart_handoff.valid_job_id(args.batch_id):
        parser.error("Use an exact 32-character batch ID")
    valid, message = dart_handoff.validate_remote_settings(args.host, "/data/dart/data/projects")
    if not valid:
        parser.error(message)
    if args.build and not args.apply:
        parser.error("--build requires --apply")
    catalog = (args.catalog_status, args.catalog_group, args.catalog_progress)
    if any(value is not None for value in catalog) and not all(value is not None for value in catalog):
        parser.error("Supply all three --catalog-status, --catalog-group, --catalog-progress options or none")
    os.umask(0o077)
    try:
        return run(args)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
