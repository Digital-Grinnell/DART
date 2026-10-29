"""Sequential prepare jobs with private, durable batch evidence."""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

import app
from dart_service import JobService, now
from dart_storage import LowDiskSpace, absolute, atomic_bytes, atomic_json, private, redact
from dart_workflows import FLAGS, project_settings, read_csv

ENTRY_KEYS = {"collection_id", "input_dir", "setup", "allow_uploads", "overwrite", "backfill", "derivatives"}
SETUP_KEYS = {"core_template", "gems_metadata_csv", "azure_blob_storage_path", *FLAGS}


def validate_queue(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    if set(inputs) != {"collections"} or not isinstance(inputs["collections"], list) or not inputs["collections"]:
        raise ValueError("Batch inputs require a nonempty collections list and no other top-level keys.")
    seen = set()
    for entry in inputs["collections"]:
        if not isinstance(entry, dict) or set(entry) - ENTRY_KEYS:
            raise ValueError("Each collection must be an object containing only documented batch keys.")
        collection = entry.get("collection_id")
        if not isinstance(collection, str):
            raise ValueError("Each collection requires a collection_id string.")
        valid, normalized, error = app.validate_collection_id(collection)
        if not valid or collection != normalized or collection == "collection-template":
            raise ValueError(error or "Use a canonical collection ID, not the reserved collection-template slug.")
        if collection in seen:
            raise ValueError(f"Duplicate batch collection: {collection}")
        seen.add(collection)
        if not isinstance(entry.get("input_dir"), str) or not entry["input_dir"]:
            raise ValueError(f"{collection}: input_dir is required.")
        for flag in ("allow_uploads", "overwrite", "backfill", "derivatives"):
            if flag in entry and type(entry[flag]) is not bool:
                raise ValueError(f"{collection}: {flag} must be a boolean.")
        if entry.get("overwrite") and not entry.get("allow_uploads"):
            raise ValueError(f"{collection}: overwrite requires explicit upload approval.")
        if "setup" in entry:
            setup = entry["setup"]
            if not isinstance(setup, dict) or set(setup) - SETUP_KEYS:
                raise ValueError(f"{collection}: setup contains unexpected keys.")
            if not isinstance(setup.get("core_template"), str) or not setup["core_template"]:
                raise ValueError(f"{collection}: setup requires core_template.")
            for flag in FLAGS:
                if flag in setup and type(setup[flag]) is not bool:
                    raise ValueError(f"{collection}: {flag} must be a boolean.")
            for field in ("gems_metadata_csv", "azure_blob_storage_path"):
                if field in setup and not isinstance(setup[field], str):
                    raise ValueError(f"{collection}: {field} must be a string.")
    return inputs["collections"]


def prepare_project(service: JobService, entry: dict[str, Any]) -> Path:
    storage = service.storage
    storage.check()
    work = storage.projects / entry["collection_id"]
    if work.is_symlink():
        raise ValueError(f"Batch projects must not be symlinks: {work}")
    if "setup" not in entry:
        storage.working(str(work))
        settings = project_settings(storage, str(work))
        if settings["collection-id"] != entry["collection_id"]:
            raise ValueError("Saved collection-id does not match the batch entry.")
        return work

    setup = entry["setup"]
    template = absolute(setup["core_template"])
    if not any(template.is_relative_to(root) for root in (storage.config, storage.projects)):
        raise ValueError("Stage core_template under the private configuration or projects root.")
    private(template)
    template_bytes = template.read_bytes()
    _, rows = read_csv(template, metadata=True)
    if rows:
        raise ValueError("Automatic new-collection setup requires a header-only template, not an existing core.")
    valid, error = app.validate_core_metadata_csv(str(template))
    if not valid:
        raise ValueError(error)
    source = storage.source(entry["input_dir"], directory=True)
    if work.is_relative_to(source) or source.is_relative_to(work):
        raise ValueError("Automatic setup requires separate source and project trees.")
    work.mkdir(mode=0o700, exist_ok=True)
    storage.working(str(work))
    snapshot = work / "core-snapshot.csv"
    values = {
        "collection-id": entry["collection_id"],
        "input_dir": str(source),
        "core_metadata_csv": str(snapshot),
        "gems_metadata_csv": setup.get("gems_metadata_csv", ""),
        "azure_blob_storage_path": setup.get("azure_blob_storage_path", ""),
        "group_compound_objects": setup.get("group_compound_objects", True),
        "create_multiple_objects": setup.get("create_multiple_objects", False),
        "process_OHM_data": setup.get("process_OHM_data", False),
    }
    settings_path = work / ".DART-working-directory" / app.APP_SETTINGS_FILENAME
    if settings_path.exists() or settings_path.is_symlink():
        settings = project_settings(storage, str(work))
        if any(settings[key] != value for key, value in values.items() if key != "input_dir"):
            raise ValueError("Existing settings differ from setup; omit setup to reuse the configured project.")
        storage.managed(str(snapshot))
        # A later desktop snapshot must never be replaced by the original empty template.
        return work
    if snapshot.exists() or snapshot.is_symlink():
        storage.managed(str(snapshot))
        if snapshot.read_bytes() != template_bytes:
            raise ValueError("Existing snapshot differs from the template; configure this project explicitly.")
    else:
        atomic_bytes(snapshot, template_bytes)
    service.configure("headless", str(work), values)
    return work


def run_batch(service: JobService, inputs: dict[str, Any], interrupted: threading.Event) -> int:
    entries = validate_queue(inputs)
    storage = service.storage
    service.require_operator("headless")
    batches = storage.data / "batches"
    if batches.is_symlink():
        raise ValueError("Batch evidence directory must not be a symlink.")
    batches.mkdir(mode=0o700, exist_ok=True)
    private(batches, directory=True)
    directory = batches / uuid.uuid4().hex
    directory.mkdir(mode=0o700)
    summary_path = directory / "summary.json"
    summary: dict[str, Any] = {
        "id": directory.name, "state": "running", "created_at": now(),
        "min_free_bytes": storage.min_free_bytes,
        "collections": [dict(collection_id=entry["collection_id"],
                             working_dir=str(storage.projects / entry["collection_id"]),
                             state="pending") for entry in entries],
    }
    atomic_json(directory / "queue.json", inputs)

    def persist() -> None:
        storage.check()
        summary["updated_at"] = now()
        atomic_json(summary_path, summary)

    persist()
    print(f"Batch: {directory.name}\nSummary: {summary_path}", flush=True)
    low_space = False
    for entry, record in zip(entries, summary["collections"]):
        if interrupted.is_set():
            break
        try:
            storage.require_space()
        except LowDiskSpace as exc:
            summary["message"] = redact(exc)
            low_space = True
            break
        record.update(state="running", started_at=now())
        persist()
        job_id = None
        try:
            work = prepare_project(service, entry)
            job_inputs = {key: value for key, value in entry.items() if key not in {"collection_id", "setup"}}
            job_inputs["working_dir"] = str(work)
            if interrupted.is_set():
                record.update(state="cancelled", message="Cancelled before job submission.")
            else:
                job_id = service.submit("headless", "prepare", job_inputs)
                record["job_id"] = job_id
        except LowDiskSpace as exc:
            record.update(state="pending", message=redact(exc), stop_reason="low_space")
            low_space = True
        except (OSError, ValueError, RuntimeError) as exc:
            record.update(state="failed", message=redact(exc))
        if job_id is not None:
            persist()
            if interrupted.is_set():
                service._cancel.set()
            worker = service._thread
            if worker is None:
                raise RuntimeError("Submitted job has no worker.")
            worker.join()
            job = next(job for job in service.jobs() if job["id"] == job_id)
            record.update({key: job[key] for key in ("state", "message", "result", "log")})
            if job.get("stop_reason") == "low_space":
                record["stop_reason"] = "low_space"
                low_space = True
        record["finished_at"] = now()
        persist()
        print(json.dumps(record), flush=True)
        if service.storage_error:
            raise RuntimeError(service.storage_error)
        if low_space:
            summary["message"] = record["message"]
            break
    summary["state"] = ("blocked" if low_space else "cancelled" if interrupted.is_set() else
                        "succeeded" if all(row["state"] == "succeeded" for row in summary["collections"]) else "failed")
    if low_space:
        summary["stop_reason"] = "low_space"
    summary["finished_at"] = now()
    persist()
    if low_space:
        print(summary["message"], flush=True)
    print(f"Batch {summary['state']}. Summary: {summary_path}", flush=True)
    return 75 if low_space else 130 if interrupted.is_set() else (0 if summary["state"] == "succeeded" else 1)
