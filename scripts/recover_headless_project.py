#!/usr/bin/env python3
"""Preview or repair an early headless setup failure without resetting IDs."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


def replacement_environment(content: str, sources: list[dict[str, str]]) -> str:
    from dotenv import dotenv_values

    encoded = json.dumps(sources, ensure_ascii=True)
    quoted = "'" + encoded.replace("\\", "\\\\").replace("'", "\\'") + "'"
    lines = content.splitlines(keepends=True)
    positions = [i for i, line in enumerate(lines)
                 if re.match(r"^\s*(?:export\s+)?DART_SOURCE_ROOTS\s*=", line)]
    if len(positions) != 1:
        raise ValueError("Expected exactly one single-line DART_SOURCE_ROOTS assignment.")
    lines[positions[0]] = f"DART_SOURCE_ROOTS={quoted}\n"
    updated = "".join(lines)
    before = dict(dotenv_values(stream=io.StringIO(content), interpolate=False))
    after = dict(dotenv_values(stream=io.StringIO(updated), interpolate=False))
    if after.pop("DART_SOURCE_ROOTS", None) != encoded:
        raise ValueError("Cannot safely serialize the source allowlist.")
    before.pop("DART_SOURCE_ROOTS", None)
    if before != after:
        raise ValueError("Refusing to change other private environment values.")
    return updated


def recover(args: argparse.Namespace) -> None:
    import fcntl
    from dart_storage import Storage, absolute, atomic_bytes, load_environment, private

    env = absolute(args.env_file)
    load_environment(str(env))
    storage = Storage.from_environment()
    for path in (storage.projects, storage.jobs):
        private(path, directory=True)
        if path.is_symlink():
            raise ValueError("Managed directories must not be symlinks.")
    inputs_path = absolute(args.inputs)
    private(inputs_path)
    inputs = json.loads(inputs_path.read_text())
    if not isinstance(inputs, dict):
        raise ValueError("Settings inputs must be a JSON object.")
    if inputs.get("collection-id") != args.collection_id:
        raise ValueError("Input collection-id does not match the requested collection.")
    work = absolute(str(inputs.get("working_dir", "")))
    private(work, directory=True)
    if work.parent != storage.projects or work.name != args.collection_id:
        raise ValueError("Expected an existing projects/COLLECTION-ID directory.")
    root = absolute(args.source_root)
    mount = absolute(args.source_mount)
    if not root.is_dir() or not os.path.ismount(mount) or not root.is_relative_to(mount):
        raise ValueError("Source root must be a directory under the verified mount.")
    if root == mount:
        raise ValueError("Approve a collection run, not an entire mount.")
    if any(root.is_relative_to(p) or p.is_relative_to(root) for p in (storage.config, storage.data)):
        raise ValueError("External source root must not overlap DART managed roots.")
    for key, directory in (("input_dir", True), ("gems_metadata_csv", False)):
        path = absolute(str(inputs.get(key, "")))
        if not path.is_relative_to(root) or not (path.is_dir() if directory else path.is_file()):
            raise ValueError(f"{key} must exist beneath the proposed source root.")
        if path != Path(inputs[key]):
            raise ValueError(f"{key} is an alias; review its canonical path first.")
        print(f"{key}: {path}", flush=True)

    snapshot = absolute(str(inputs.get("core_metadata_csv", "")))
    private(snapshot)
    if not snapshot.is_relative_to(work):
        raise ValueError("Core snapshot must be inside this Linux project.")
    with snapshot.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not {"objectid", "original_file_name"}.issubset(reader.fieldnames or []):
            raise ValueError("Core snapshot lacks required identity columns.")
        rows = sum(1 for _ in reader)
    print(f"Collection: {args.collection_id}\nProject: {work}", flush=True)
    print(f"Core snapshot rows: {rows}; SHA-256: {hashlib.sha256(snapshot.read_bytes()).hexdigest()}",
          flush=True)

    with ExitStack() as stack:
        for directory in sorted((storage.config, storage.data)):
            lock = directory / ".dart-service.lock"
            if lock.is_symlink():
                raise ValueError("Refusing a symlinked service lock.")
            if not lock.exists():
                if args.apply:
                    raise ValueError("Service lock is missing; inspect storage readiness before recovery.")
                print(f"No service lock: {directory}", flush=True)
                continue
            private(lock)
            handle = stack.enter_context(lock.open("rb"))
            mode = fcntl.LOCK_EX if args.apply else fcntl.LOCK_SH
            try:
                fcntl.flock(handle, mode | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError("A DART writer is active; wait for it to finish.") from None
        hidden = work / ".DART-working-directory"
        if hidden.is_symlink():
            raise ValueError("Working directory must not be a symlink.")
        if hidden.exists():
            private(hidden, directory=True)
        settings = hidden / "dart_settings.json"
        mappings = {}
        saved = {}
        if settings.exists() or settings.is_symlink():
            private(settings)
            saved = json.loads(settings.read_text())
            if not isinstance(saved, dict) or not isinstance(saved.get("file_to_id_map", {}), dict):
                raise ValueError("Invalid saved project settings.")
            mappings = saved.get("file_to_id_map", {})
        print(f"Saved Linux settings: {settings.exists()}; assigned ID mappings: {len(mappings)}",
              flush=True)
        project_jobs = []
        active_jobs = []
        for path in sorted(storage.jobs.glob("*/job.json")):
            private(path)
            job = json.loads(path.read_text())
            if not isinstance(job, dict) or not isinstance(job.get("inputs"), dict):
                raise ValueError("Invalid job history; inspect it before recovery.")
            if job.get("state") in {"queued", "running", "cancelling"}:
                active_jobs.append(path.parent.name)
            if job["inputs"].get("working_dir") == str(work):
                project_jobs.append({"id": job.get("id"), "state": job.get("state"),
                                     "kind": job.get("kind")})
        print(f"Recorded collection jobs: {json.dumps(project_jobs)}", flush=True)
        entry = {"path": str(root), "mount": str(mount)}
        sources = json.loads(os.environ.get("DART_SOURCE_ROOTS", "[]"))
        covered = any(root.is_relative_to(path) and mount == m for path, m in storage.sources)
        print(f"Allowlist action: {'already covered' if covered else 'append ' + json.dumps(entry)}",
              flush=True)
        blockers = []
        if mappings or project_jobs or (work / "handoff").exists():
            blockers.append("Project has IDs, jobs, or handoff evidence; needs job-specific review, not setup recovery.")
        if active_jobs:
            blockers.append("Active or stale-active job records exist; inspect before running configuration.")
        for key in ("collection-id", "group_compound_objects", "create_multiple_objects", "process_OHM_data"):
            if saved and saved.get(key) != inputs.get(key):
                blockers.append(f"Existing {key} differs; recovery will not change collection identity/grouping.")
        for message in blockers:
            print(f"BLOCKED: {message}", flush=True)
        if not args.apply:
            print("PREVIEW ONLY: no files changed. No job, upload, or merge was started.", flush=True)
            return
        if blockers:
            raise ValueError("Recovery refused; preserve this evidence and review the reported blockers.")
        if not covered:
            content = env.read_text()
            updated = replacement_environment(content, [*sources, entry])
            hidden.mkdir(mode=0o700, exist_ok=True)
            recovery = hidden / "recovery"
            recovery.mkdir(mode=0o700, exist_ok=True)
            if recovery.is_symlink():
                raise ValueError("Recovery backup directory must not be a symlink.")
            private(recovery, directory=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = recovery / f"dart.env.before-{stamp}"
            descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            if env.read_text() != content:
                raise ValueError("Environment changed during recovery; inspect before retrying.")
            atomic_bytes(env, updated.encode())
            print(f"Private environment backup: {backup} (contains secrets; do not share)", flush=True)
            print("Appended collection source approval; other environment values preserved.", flush=True)

    # Configuration takes its own service locks; never hold these across the subprocess.
    result = subprocess.run(
        [sys.executable, "-B", "-m", "dart_linux", "--env-file", str(env),
         "--configure", "--inputs", str(inputs_path)],
        cwd=args.repo, check=False,
    )
    if result.returncode:
        raise RuntimeError("Configuration failed. Source approval/backup remain in place; no job was started.")
    value = json.loads(settings.read_text())
    if value.get("collection-id") != args.collection_id or value.get("file_to_id_map", {}) != mappings:
        raise RuntimeError("Post-configuration identity verification failed; stop and inspect.")
    print("RECOVERED: settings saved; ID map unchanged. No prepare job, upload, or merge was started.",
          flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("collection_id")
    parser.add_argument("--host", help="Run from the Mac over SSH; omit only when already on Linux")
    parser.add_argument("--repo", required=True, help="Existing Linux DART checkout")
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--inputs", required=True, help="Existing settings JSON, not prepare/job JSON")
    parser.add_argument("--source-root", required=True, help="Explicitly approved collection run")
    parser.add_argument("--source-mount", required=True, help="Verified Linux mount point")
    parser.add_argument("--apply", action="store_true", help="Back up env, approve source, configure only")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9_-]+", args.collection_id) or args.collection_id == "collection-template":
        parser.error("Use a valid, non-reserved collection ID.")
    try:
        if args.host:
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from dart_handoff import SSH_OPTIONS, validate_remote_settings

            valid, message = validate_remote_settings(args.host, args.repo)
            if not valid:
                raise ValueError(message)
            command = [str(Path(args.repo) / ".venv/bin/python"), "-B", "-", args.collection_id]
            for name in ("repo", "env_file", "inputs", "source_root", "source_mount"):
                command.extend(["--" + name.replace("_", "-"), getattr(args, name)])
            if args.apply:
                command.append("--apply")
            result = subprocess.run(
                ["ssh", *SSH_OPTIONS, "--", args.host, shlex.join(command)],
                input=Path(__file__).read_bytes(), timeout=300, check=False,
            )
            if result.returncode:
                raise RuntimeError(f"Remote recovery exited with status {result.returncode}; inspect the output above.")
        else:
            sys.path.insert(0, str(Path(args.repo).resolve()))
            recover(args)
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.TimeoutExpired) as exc:
        # Do not echo parser exceptions that might contain private environment content.
        if isinstance(exc, (json.JSONDecodeError, UnicodeError)):
            detail = "Invalid JSON or text encoding; inspect the private input locally."
        elif isinstance(exc, subprocess.TimeoutExpired):
            detail = "SSH recovery timed out; inspect actual state before retrying."
        else:
            detail = str(exc)
        print(f"Recovery error: {detail}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
