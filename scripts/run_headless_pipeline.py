#!/usr/bin/env python3
"""Start/resume a staged Linux batch, then run approved Mac acceptance and builds."""
from __future__ import annotations

import argparse
import fcntl
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dart_handoff
from scripts.accept_headless_batch import atomic, sha


STATUS = r'''
import json, sys
from pathlib import Path
request = json.load(sys.stdin)
queue = json.loads(Path(request["queue"]).read_text())
matches = []
for path in Path("/data/dart/data/batches").glob("*/queue.json"):
    if json.loads(path.read_text()) == queue:
        matches.append(json.loads(path.with_name("summary.json").read_text()))
if len(matches) > 1:
    raise ValueError("Multiple batches match; select/review exact evidence manually")
print(json.dumps(dict(queue=queue, summary=matches[0] if matches else None)))
'''


def status(host: str, queue: str) -> dict:
    command = "cd /home/sysadmin/GitHub/DART && .venv/bin/python -c " + shlex.quote(STATUS)
    return json.loads(dart_handoff._ssh(
        host, command, subprocess.run, data=json.dumps(dict(queue=queue)).encode(),
    ))


def launch(host: str, unit: str, queue: str) -> None:
    command = shlex.join([
        "sudo", "systemd-run", "--unit=" + unit,
        "--uid=sysadmin", "--gid=sysadmin", "--working-directory=/home/sysadmin/GitHub/DART",
        "--property=UMask=0077", "--property=TimeoutStopSec=infinity",
        "--setenv=PYTHONUNBUFFERED=1",
        "/home/sysadmin/GitHub/DART/.venv/bin/python", "-m", "dart_linux",
        "--env-file", "/data/dart/config/dart.env", "--batch", "--inputs", queue, "--min-free-gib", "50",
    ])
    # A TTY permits the initial sudo prompt; subsequent monitoring is noninteractive.
    subprocess.run(["ssh", "-t", *dart_handoff.SSH_OPTIONS, "--", host, command], check=True)


def run(args: argparse.Namespace) -> int:
    work = Path.home() / "DART-projects/.DART-working-directory"
    work.mkdir(parents=True, exist_ok=True)
    record_path = work / f"pipeline-{args.unit}.json"
    with (work / f"pipeline-{args.unit}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        initial = status(args.host, args.queue)
        queue_hash = sha(json.dumps(initial["queue"], sort_keys=True).encode())
        entries = initial["queue"].get("collections", [])
        if ([entry.get("collection_id") for entry in entries] != args.collections
                or any(not entry.get("allow_uploads") or entry.get("overwrite") for entry in entries)):
            raise ValueError("Staged queue does not match the approved collections/upload flags")
        # Refuse to start a new Linux job when the authoritative cores are populated.
        if initial["summary"] is None:
            from scripts.accept_headless_batch import check_show_config, table
            for slug in args.collections:
                core = args.show_root / "collections" / slug / "_data" / f"{slug}_metadata.csv"
                if core.resolve(strict=True) != core or table(core.read_bytes())[1]:
                    raise ValueError(f"{slug}: core is not an unaliased header-only CSV")
                check_show_config(args.show_root, slug)
        if not args.apply:
            print(json.dumps(dict(state="preview", collections=args.collections,
                                  existing_batch=initial["summary"], queue=args.queue), indent=2))
            return 0
        if record_path.exists():
            saved = json.loads(record_path.read_text())
            if saved["queue_sha256"] != queue_hash:
                raise ValueError("Staged queue changed since this pipeline was started")
        record = dict(unit=args.unit, queue=args.queue, queue_sha256=queue_hash, state="preparing")
        atomic(record_path, json.dumps(record, indent=2).encode())
        if initial["summary"] is None:
            print("Starting Linux publishing batch. Authorize sudo now if prompted.", flush=True)
            launch(args.host, args.unit, args.queue)
        deadline = time.monotonic() + 24 * 60 * 60
        summary = initial["summary"]
        while summary is None or summary["state"] == "running":
            if time.monotonic() >= deadline:
                raise RuntimeError("24-hour monitoring limit reached; inspect Linux service before retrying")
            current = status(args.host, args.queue)
            if sha(json.dumps(current["queue"], sort_keys=True).encode()) != queue_hash:
                raise ValueError("Queue changed during execution")
            summary = current["summary"]
            if summary:
                record.update(state="linux_" + summary["state"], batch_id=summary["id"])
                atomic(record_path, json.dumps(record, indent=2).encode())
                counts = {state: sum(r["state"] == state for r in summary["collections"])
                          for state in ("succeeded", "failed", "pending", "running")}
                print(f"Linux batch {summary['id']}: {summary['state']} {counts}", flush=True)
            if summary is None or summary["state"] == "running":
                # Detect dead services instead of waiting indefinitely on stale evidence.
                active = dart_handoff._ssh(
                    args.host, "systemctl show " + shlex.quote(args.unit) +
                    " -p ActiveState --value", subprocess.run,
                ).decode().strip()
                if active not in {"active", "activating", "deactivating"}:
                    # The service can finish between reading summary and ActiveState.
                    latest = status(args.host, args.queue)["summary"]
                    if latest is None or latest["state"] == "running":
                        raise RuntimeError(f"Linux service is {active}; inspect its journal and partial evidence")
                    summary = latest
                    break
                time.sleep(20)
        if not dart_handoff.valid_job_id(summary["id"]):
            raise ValueError("Unexpected batch ID")
        record.update(state="mac_acceptance", batch_id=summary["id"])
        atomic(record_path, json.dumps(record, indent=2).encode())
        print("Linux batch finished. Accepting eligible cores, updating catalog, building locally.", flush=True)
        command = [
            sys.executable, "-u", str(Path(__file__).with_name("accept_headless_batch.py")),
            "--batch-id", summary["id"], "--host", args.host,
            "--inventory", args.inventory, "--show-root", str(args.show_root),
            "--apply", "--build", "--catalog-status", "published",
            "--catalog-group", args.catalog_group, "--catalog-progress", args.catalog_progress,
        ]
        completed = subprocess.run(command)
        code = completed.returncode or int(summary["state"] != "succeeded")
        record.update(state="completed" if code == 0 else "needs_attention", exit_code=code,
                      acceptance_summary=str(work / f"accept-{summary['id']}/summary.json"))
        atomic(record_path, json.dumps(record, indent=2).encode())
        print(f"Pipeline result: {record_path}", flush=True)
        return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="sysadmin@dg-landing")
    parser.add_argument("--queue", required=True)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--unit", required=True)
    parser.add_argument("--collections", nargs="+", required=True)
    parser.add_argument("--show-root", type=Path, default=Path.home() / "GitHub/SHOW")
    parser.add_argument("--catalog-group", required=True)
    parser.add_argument("--catalog-progress", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"dart-[a-z0-9-]+", args.unit):
        parser.error("Use a dart-prefixed systemd unit name containing lowercase letters, digits, hyphens")
    for path in (args.queue, args.inventory):
        if not re.fullmatch(r"/data/dart/config/[a-zA-Z0-9_.-]+", path):
            parser.error("Queue/inventory must be named files under /data/dart/config")
    if (len(set(args.collections)) != len(args.collections)
            or any(not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", slug) for slug in args.collections)):
        parser.error("Collections must be unique canonical slugs")
    valid, message = dart_handoff.validate_remote_settings(args.host, "/data/dart/data/projects")
    if not valid:
        parser.error(message)
    try:
        return run(args)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}. Linux may still be running; rerun this same command to inspect/resume, not a new queue.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
