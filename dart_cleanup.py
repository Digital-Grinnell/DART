"""Verify Azure copies before explicitly removing one publishing job's derivatives."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any

from azure.core import MatchConditions
from azure.core.exceptions import AzureError
from azure.storage.blob import BlobServiceClient

from dart_handoff import validate_manifest
from dart_processing import get_derivative_azure_paths
from dart_service import JobService, now, valid_job_id
from dart_storage import atomic_json, private, redact
from dart_workflows import Cancelled, digest, read_csv, re_safe_id


def unaliased(path: Path) -> Path:
    if path.resolve(strict=True) != path:
        raise ValueError(f"Cleanup refuses aliased or symlinked paths: {path}")
    private(path, directory=path.is_dir())
    return path


def cleanup_derivatives(service: JobService, job_id: str, *, apply: bool = False) -> dict[str, Any]:
    service.require_operator("headless")
    if service._active is not None:
        raise ValueError("Wait for the active job before cleanup.")
    if not valid_job_id(job_id):
        raise ValueError("Select an exact DART job ID for cleanup.")
    job = next((job for job in service.jobs() if job["id"] == job_id), None)
    if job is None or job["state"] != "succeeded" or job["kind"] != "prepare" or not job["inputs"].get("allow_uploads"):
        raise ValueError("Cleanup requires a succeeded prepare job with explicit upload consent.")
    storage = service.storage
    work = unaliased(storage.working(job["inputs"]["working_dir"]))
    job_dir = unaliased(storage.jobs / job_id)
    snapshot = unaliased(job_dir / "settings-snapshot.json")
    settings = json.loads(snapshot.read_text())
    package = unaliased(work / "handoff" / job_id)
    manifest_path = unaliased(package / "manifest.json")
    manifest = validate_manifest(json.loads(manifest_path.read_text()),
                                 expected_collection_id=settings["collection-id"], job_id=job_id)
    export = unaliased(package / "export.csv")
    if digest(export) != manifest["csv_sha256"] or manifest.get("derivatives_local_only") is not False:
        raise ValueError("Cleanup requires an unchanged publishing handoff with remote derivative URLs.")
    derived = job["result"].get("derivatives")
    directory = work / ".DART-working-directory" / f"derivatives_{job_id}"
    if not isinstance(derived, dict) or derived.get("local_only") is not False or derived.get("derivatives") != str(directory):
        raise ValueError("Job does not identify a publishing derivative directory.")
    unaliased(directory)
    _, rows = read_csv(export, metadata=True)
    destinations = get_derivative_azure_paths(settings["azure_blob_storage_path"])
    references: dict[str, tuple[str, str, str]] = {}
    for row in rows:
        if row.get("original_file_name", "").startswith("_"):
            continue
        object_id = row["objectid"]
        if not re_safe_id(object_id):
            raise ValueError("Unsafe object ID in publishing handoff.")
        for field, suffix, destination in zip(("image_small", "image_thumb"), ("_SMALL", "_TN"), destinations):
            url = row.get(field, "")
            if not url:
                continue
            name = f"{object_id}{suffix}.jpg"
            if name in references:
                raise ValueError(f"Duplicate derivative reference: {name}")
            parts = destination.strip("/").split("/", 1)
            blob = (parts[1] + "/" if len(parts) == 2 else "") + name
            references[name] = (parts[0], blob, url)
    candidates = []
    for path in sorted(directory.iterdir()):
        unaliased(path)
        if not path.is_file() or path.name not in references:
            raise ValueError(f"Unrecognized derivative directory entry; nothing removed: {path}")
        candidates.append(path)
    receipt: dict[str, Any] = dict(job_id=job_id, created_at=now(), mode="apply" if apply else "preview",
                                   state="verifying", files=[], bytes=0)
    receipt_path = job_dir / f"cleanup-{uuid.uuid4().hex}.json"
    receipt["receipt"] = str(receipt_path)
    atomic_json(receipt_path, receipt)
    try:
        if candidates:
            connection = os.environ.get("DART_AZURE_CONNECTION_STRING", "")
            if not connection:
                raise ValueError("Azure verification requires a credential in the private environment file.")
            with BlobServiceClient.from_connection_string(
                    connection, connection_timeout=10, read_timeout=30, retry_total=2) as client:
                # Verify every candidate before deleting any file.
                for path in candidates:
                    service._checkpoint_cancel_only()
                    storage.check()
                    container, blob, url = references[path.name]
                    remote = client.get_blob_client(container=container, blob=blob)
                    if url != remote.url.split("?", 1)[0] or not url.startswith("https://"):
                        raise ValueError(f"Derivative URL does not match the configured Azure destination: {path.name}")
                    info = path.stat()
                    local_hash = digest(path)
                    properties = remote.get_blob_properties(timeout=30)
                    if properties.size != info.st_size:
                        raise ValueError(f"Azure size mismatch; nothing removed: {path.name}")
                    remote_hash = hashlib.sha256()
                    downloaded = 0
                    stream = remote.download_blob(etag=properties.etag, match_condition=MatchConditions.IfNotModified,
                                                  timeout=30)
                    for chunk in stream.chunks():
                        service._checkpoint_cancel_only()
                        storage.check()
                        downloaded += len(chunk)
                        remote_hash.update(chunk)
                    if downloaded != info.st_size or remote_hash.hexdigest() != local_hash:
                        raise ValueError(f"Azure SHA-256 mismatch; nothing removed: {path.name}")
                    receipt["files"].append(dict(path=str(path), size=info.st_size, sha256=local_hash,
                                                 device=info.st_dev, inode=info.st_ino,
                                                 url=url, etag=properties.etag, state="verified"))
                    receipt["bytes"] += info.st_size
        receipt["state"] = "verified"
        atomic_json(receipt_path, receipt)
        if apply:
            # Recheck handoff and all local files before the first unlink.
            if digest(unaliased(export)) != manifest["csv_sha256"]:
                raise ValueError("Handoff changed during verification; nothing removed.")
            for record in receipt["files"]:
                path = unaliased(Path(record["path"]))
                info = path.stat()
                if (info.st_dev, info.st_ino, info.st_size, digest(path)) != (
                        record["device"], record["inode"], record["size"], record["sha256"]):
                    raise ValueError(f"Local file changed during verification; nothing removed: {path}")
            if receipt["files"]:
                with BlobServiceClient.from_connection_string(
                        connection, connection_timeout=10, read_timeout=30, retry_total=2) as client:
                    for record in receipt["files"]:
                        container, blob, _ = references[Path(record["path"]).name]
                        properties = client.get_blob_client(container=container, blob=blob).get_blob_properties(timeout=30)
                        if properties.etag != record["etag"] or properties.size != record["size"]:
                            raise ValueError("Azure copy changed after hashing; nothing removed.")
            for record in receipt["files"]:
                service._checkpoint_cancel_only()
                storage.check()
                path = unaliased(Path(record["path"]))
                if digest(path) != record["sha256"]:
                    raise ValueError(f"Local derivative changed before removal: {path}")
                record["state"] = "removing"
                atomic_json(receipt_path, receipt)
                path.unlink()
                record["state"] = "removed"
                atomic_json(receipt_path, receipt)
        receipt.update(state="succeeded", finished_at=now())
        atomic_json(receipt_path, receipt)
        return receipt
    except (OSError, ValueError, RuntimeError, AzureError, Cancelled) as exc:
        receipt.update(state="failed", message=redact(exc), finished_at=now())
        atomic_json(receipt_path, receipt)
        raise RuntimeError(f"Derivative cleanup stopped: {redact(exc)}. Evidence: {receipt_path}") from None
