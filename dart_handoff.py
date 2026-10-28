"""Headless-to-desktop handoff packages.

Headless DART on Linux prepares a package (export CSV + manifest) and stops
before any core metadata merge. Desktop DART pulls the package over SSH and
reviews/merges it in Function 4 against the desktop-held core CSV. Desktop
DART also pushes a read-only core snapshot to the server so headless analysis
can reuse existing identifiers instead of minting duplicates.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable

FORMAT = "DART handoff v1"
HANDOFF_DIR_NAME = "handoff"
MANIFEST_NAME = "manifest.json"
PACKAGE_CSV_NAME = "export.csv"
CORE_SNAPSHOT_NAME = "core-snapshot.csv"
LOCAL_EXPORT_PREFIX = "DART_export_handoff_"
LOCAL_MANIFEST_PREFIX = "DART_handoff_"
SSH_OPTIONS = ("-o", "BatchMode=yes", "-o", "ConnectTimeout=15")
DERIVATIVE_FIELDS = ("image_small", "image_thumb")

Runner = Callable[..., subprocess.CompletedProcess]


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def valid_job_id(value: str) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{32}", value))


def find_id_conflicts(core_rows: Iterable[dict], export_rows: Iterable[dict]) -> list[dict[str, str]]:
    """Records whose filename or objectid already exists in core under a different pairing."""
    by_name, by_id = {}, {}
    for row in core_rows:
        name = str(row.get("original_file_name") or row.get("filename") or "").strip()
        objectid = str(row.get("objectid") or "").strip()
        if name:
            by_name.setdefault(name, objectid)
        if objectid:
            by_id.setdefault(objectid, name)
    conflicts = []
    for row in export_rows:
        name = str(row.get("original_file_name") or row.get("filename") or "").strip()
        objectid = str(row.get("objectid") or "").strip()
        if name in by_name and by_name[name] != objectid:
            conflicts.append(dict(original_file_name=name, export_objectid=objectid, core_objectid=by_name[name]))
        elif objectid in by_id and by_id[objectid] != name:
            conflicts.append(dict(original_file_name=name, export_objectid=objectid,
                                  core_original_file_name=by_id[objectid]))
    return conflicts


def has_server_local_derivatives(rows: Iterable[dict]) -> bool:
    return any(str(row.get(field, "")).startswith("/") for row in rows for field in DERIVATIVE_FIELDS)


def build_manifest(*, job_id: str, collection_id: str, csv_sha256: str, rows: int, core_snapshot: str,
                   core_snapshot_sha256: str, gems_backfill: dict | None, id_conflicts: list,
                   derivatives_local_only: bool, source: str, dart_version: str, created_at: str) -> dict[str, Any]:
    warnings = []
    if id_conflicts:
        warnings.append(f"{len(id_conflicts)} record(s) conflict with identifiers in the core snapshot; "
                        "do not merge them until reviewed.")
    if derivatives_local_only:
        warnings.append("Derivative columns point to server-local files; upload derivatives before publishing.")
    if gems_backfill and gems_backfill.get("unmatched_dart_rows"):
        warnings.append(f"{len(gems_backfill['unmatched_dart_rows'])} record(s) had no GEMS metadata match.")
    return dict(format=FORMAT, job_id=job_id, collection_id=collection_id, csv=PACKAGE_CSV_NAME,
                csv_sha256=csv_sha256, rows=rows, core_snapshot=core_snapshot,
                core_snapshot_sha256=core_snapshot_sha256, gems_backfill=gems_backfill,
                id_conflicts=id_conflicts, derivatives_local_only=derivatives_local_only,
                source=source, dart_version=dart_version, created_at=created_at, warnings=warnings)


def validate_manifest(manifest: Any, *, expected_collection_id: str, job_id: str | None = None) -> dict:
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
        raise ValueError("Not a DART handoff manifest.")
    if not valid_job_id(manifest.get("job_id", "")) or (job_id and manifest["job_id"] != job_id):
        raise ValueError("Handoff manifest has an unexpected job ID.")
    if manifest.get("csv") != PACKAGE_CSV_NAME or not re.fullmatch(r"[0-9a-f]{64}", str(manifest.get("csv_sha256", ""))):
        raise ValueError("Handoff manifest has an invalid CSV reference.")
    if manifest.get("collection_id") != expected_collection_id:
        raise ValueError(f"Handoff collection-id {manifest.get('collection_id')!r} does not match this "
                         f"project's collection-id {expected_collection_id!r}.")
    return manifest


def validate_remote_settings(host: str, project_dir: str) -> tuple[bool, str]:
    host, project_dir = (host or "").strip(), (project_dir or "").strip()
    if not host and not project_dir:
        return True, "Headless DART handoff disabled."
    if not host or not project_dir:
        return False, "Set both headless_host and headless_project_dir, or leave both blank."
    if not re.fullmatch(r"(?:[A-Za-z0-9_][A-Za-z0-9._-]*@)?[A-Za-z0-9][A-Za-z0-9.-]*", host):
        return False, "headless_host must look like user@host or an SSH config alias."
    path = PurePosixPath(project_dir)
    if not path.is_absolute() or ".." in path.parts or any(c in project_dir for c in "\n\r\0"):
        return False, "headless_project_dir must be an absolute Linux path without '..'."
    if project_dir.startswith(("/Volumes/", "//")):
        return False, "headless_project_dir must be the server's Linux path, not a Mac or UNC path."
    return True, f"Headless DART: {host}:{project_dir}"


def _ssh(host: str, command: str, runner: Runner, *, data: bytes | None = None, timeout: float = 300) -> bytes:
    result = runner(["ssh", *SSH_OPTIONS, "--", host, command], input=data, capture_output=True, timeout=timeout)
    if result.returncode != 0:
        detail = (result.stderr or b"").decode(errors="replace").strip()
        raise RuntimeError(f"SSH to {host} failed ({result.returncode}): {detail or 'no error output'}")
    return result.stdout or b""


def _handoff_dir(project_dir: str) -> str:
    return str(PurePosixPath(project_dir) / HANDOFF_DIR_NAME)


def list_remote_packages(host: str, project_dir: str, *, expected_collection_id: str,
                         runner: Runner = subprocess.run) -> list[dict]:
    """Return complete server packages (manifest present), newest first."""
    ok, message = validate_remote_settings(host, project_dir)
    if not ok:
        raise ValueError(message)
    pattern = shlex.quote(_handoff_dir(project_dir)) + "/*/" + MANIFEST_NAME
    output = _ssh(host, f'for f in {pattern}; do [ -f "$f" ] && cat "$f" && printf "\\0"; done; true', runner)
    packages = []
    for chunk in output.split(b"\0"):
        if not chunk.strip():
            continue
        try:
            packages.append(validate_manifest(json.loads(chunk), expected_collection_id=expected_collection_id))
        except (ValueError, json.JSONDecodeError):
            continue
    return sorted(packages, key=lambda item: str(item.get("created_at", "")), reverse=True)


def local_package_paths(dart_working_dir: Path, job_id: str) -> tuple[Path, Path]:
    return (Path(dart_working_dir) / f"{LOCAL_EXPORT_PREFIX}{job_id}.csv",
            Path(dart_working_dir) / f"{LOCAL_MANIFEST_PREFIX}{job_id}_manifest.json")


def _write_atomic(path: Path, content: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def pull_package(host: str, project_dir: str, job_id: str, dart_working_dir: Path, *,
                 expected_collection_id: str, local_core_csv: str = "",
                 runner: Runner = subprocess.run) -> dict[str, Any]:
    """Copy one verified package into the desktop working directory for Function 4."""
    ok, message = validate_remote_settings(host, project_dir)
    if not ok:
        raise ValueError(message)
    if not valid_job_id(job_id):
        raise ValueError("Invalid handoff job ID.")
    package = PurePosixPath(_handoff_dir(project_dir)) / job_id
    manifest_bytes = _ssh(host, "cat " + shlex.quote(str(package / MANIFEST_NAME)), runner)
    manifest = validate_manifest(json.loads(manifest_bytes), expected_collection_id=expected_collection_id,
                                 job_id=job_id)
    csv_bytes = _ssh(host, "cat " + shlex.quote(str(package / PACKAGE_CSV_NAME)), runner)
    if sha256_bytes(csv_bytes) != manifest["csv_sha256"]:
        raise ValueError("Handoff CSV checksum does not match its manifest; nothing was copied.")
    csv_path, manifest_path = local_package_paths(dart_working_dir, job_id)
    if csv_path.exists() and sha256_file(csv_path) != manifest["csv_sha256"]:
        raise ValueError(f"A different local file already exists: {csv_path.name}")
    warnings = list(manifest.get("warnings", []))
    if local_core_csv and Path(local_core_csv).is_file():
        if sha256_file(Path(local_core_csv)) != manifest.get("core_snapshot_sha256"):
            warnings.append("Your core CSV changed since the snapshot this package was prepared against; "
                            "Function 4 will compare against your current core, but re-check identifiers.")
    _write_atomic(csv_path, csv_bytes)
    _write_atomic(manifest_path, manifest_bytes)
    return dict(csv=str(csv_path), manifest=str(manifest_path), rows=manifest.get("rows"), warnings=warnings)


def push_core_snapshot(host: str, project_dir: str, core_csv: str, *, runner: Runner = subprocess.run) -> str:
    """Replace the server's read-only core snapshot atomically; returns its SHA-256."""
    ok, message = validate_remote_settings(host, project_dir)
    if not ok:
        raise ValueError(message)
    content = Path(core_csv).read_bytes()
    project = PurePosixPath(project_dir)
    final = shlex.quote(str(project / CORE_SNAPSHOT_NAME))
    temporary = shlex.quote(str(project / f".{CORE_SNAPSHOT_NAME}.upload"))
    _ssh(host, f"umask 077 && test -d {shlex.quote(str(project))} && cat > {temporary} && mv -f {temporary} {final}",
         runner, data=content)
    return sha256_bytes(content)
