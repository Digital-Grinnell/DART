"""Durable single-operator, single-worker job service."""
from __future__ import annotations

import copy
import json
import logging
import os
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import app
from dart_storage import Storage, atomic_json, private, redact
from dart_workflows import FLAGS, KINDS, Cancelled, Workflow, project_settings, save_settings

ACTIVE = {"queued", "running", "cancelling"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RedactedFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


class JobService:
    def __init__(self, storage: Storage) -> None:
        if os.name != "posix":
            raise RuntimeError("Managed headless operation requires POSIX. Use desktop mode on Windows.")
        import fcntl

        self.storage = storage
        storage.check()
        self._locks = []
        try:
            # Both roots are locked: aliases or a different configuration root cannot bypass the data lock.
            for root in sorted((storage.config, storage.data)):
                path = root / ".dart-service.lock"
                if path.is_symlink():
                    raise ValueError(f"Lock must not be a symlink: {path}")
                descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
                handle = os.fdopen(descriptor, "a")
                try:
                    private(path)
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except Exception:
                    handle.close()
                    raise RuntimeError(f"Another DART writer owns this root, or the lock is unsafe: {root}") from None
                self._locks.append(handle)
            self._mutex = threading.RLock()
            self._cancel = threading.Event()
            self._thread: threading.Thread | None = None
            self._operator: str | None = None
            self._active: str | None = None
            self._closing = False
            self.storage_error = ""
            self._jobs: dict[str, dict[str, Any]] = {}
            for directory in sorted(storage.jobs.iterdir()):
                if not directory.is_dir() or directory.is_symlink() or not valid_job_id(directory.name):
                    raise ValueError(f"Unexpected job-store entry: {directory}")
                path = directory / "job.json"
                private(path)
                job = json.loads(path.read_text())
                if not isinstance(job, dict) or job.get("id") != directory.name or job.get("state") not in ACTIVE | {"failed", "succeeded", "cancelled", "interrupted"}:
                    raise ValueError(f"Invalid job history: {path}")
                if job["state"] in ACTIVE:
                    job.update(state="interrupted", finished_at=now(), updated_at=now(),
                               message="Service stopped before completion. Review partial outputs; no automatic resume.")
                    atomic_json(path, job)
                self._jobs[job["id"]] = job
        except Exception:
            for handle in reversed(self._locks):
                handle.close()
            raise

    def claim(self, session: str) -> bool:
        with self._mutex:
            if self._operator not in (None, session):
                return False
            self._operator = session
            return True

    def release(self, session: str) -> None:
        with self._mutex:
            if self._operator == session:
                self._operator = None

    def require_operator(self, session: str) -> None:
        if self._operator != session:
            raise ValueError("Another DART operator session is active. Wait for it to finish.")
        if self._closing:
            raise RuntimeError("The service is shutting down.")
        if self.storage_error:
            raise OSError(self.storage_error)
        self.storage.check()

    def jobs(self) -> list[dict[str, Any]]:
        with self._mutex:
            return copy.deepcopy(sorted(self._jobs.values(), key=lambda job: job["created_at"], reverse=True))

    def configure(self, session: str, working: str, values: dict[str, Any]) -> None:
        with self._mutex:
            self.require_operator(session)
            if self._active:
                raise ValueError("Wait for the active job before changing settings.")
            save_settings(self.storage, working, values)

    def validate(self, kind: str, inputs: dict[str, Any]) -> dict[str, Any]:
        if kind not in KINDS:
            raise ValueError(f"Unknown workflow: {kind}")
        allowed = {"working_dir", "input_dir", "csv_path", "allow_uploads", "overwrite", "backfill", "derivatives"}
        if set(inputs) - allowed:
            raise ValueError("Unexpected job input keys.")
        values = dict(inputs)
        values["working_dir"] = str(self.storage.working(str(values.get("working_dir", ""))))
        settings = project_settings(self.storage, values["working_dir"])
        if not settings["collection-id"]:
            raise ValueError("Save this collection's settings before submitting jobs.")
        if kind in {"analyze", "export", "handoff", "prepare"}:
            path = self.storage.managed(str(settings["core_metadata_csv"]))
            valid, error = app.validate_core_metadata_csv(str(path))
            if not valid:
                raise ValueError(error)
        # GEMS backfill happens on the server by default whenever the project names a GEMS CSV.
        values.setdefault("backfill", bool(settings["gems_metadata_csv"]))
        values.setdefault("derivatives", True)
        for flag in ("allow_uploads", "overwrite", "backfill", "derivatives"):
            values.setdefault(flag, False)
            if type(values[flag]) is not bool:
                raise ValueError(f"{flag} must be a boolean.")
        if values["overwrite"] and not values["allow_uploads"]:
            raise ValueError("Overwrite requires explicit per-job upload consent.")
        if values["allow_uploads"]:
            if kind not in {"export", "derivatives", "prepare"}:
                raise ValueError("Uploads are only permitted for export, derivative, and prepare jobs.")
            if not os.environ.get("DART_AZURE_CONNECTION_STRING") or not settings["azure_blob_storage_path"]:
                raise ValueError("Uploads require an Azure path and a credential in the private environment file.")
        if values["backfill"] and kind in {"handoff", "prepare"} and not settings["gems_metadata_csv"]:
            raise ValueError("GEMS backfill requested, but this project has no gems_metadata_csv.")
        if kind in {"analyze", "export", "prepare"}:
            values["input_dir"] = str(self.storage.source(str(values.get("input_dir", "")), directory=True))
            if Path(values["working_dir"]).is_relative_to(values["input_dir"]):
                raise ValueError("The working directory must not be inside the source scan tree.")
        if kind in {"derivatives", "handoff"}:
            values["csv_path"] = str(self.storage.managed(str(values.get("csv_path", ""))))
        # Do not persist irrelevant fields (including a previous job's write consent).
        keys = {"working_dir"}
        keys |= {"input_dir"} if kind in {"analyze", "export", "prepare"} else set()
        keys |= {"csv_path"} if kind in {"derivatives", "handoff"} else set()
        keys |= {"allow_uploads", "overwrite"} if kind in {"export", "derivatives", "prepare"} else set()
        keys |= {"backfill"} if kind in {"handoff", "prepare"} else set()
        keys |= {"derivatives"} if kind == "prepare" else set()
        return {key: values[key] for key in keys}

    def submit(self, session: str, kind: str, inputs: dict[str, Any]) -> str:
        with self._mutex:
            self.require_operator(session)
            if self._active is not None:
                raise ValueError("A job is already running; wait for it to stop.")
            values = self.validate(kind, inputs)
            job_id = uuid.uuid4().hex
            directory = self.storage.jobs / job_id
            directory.mkdir(mode=0o700)
            settings = project_settings(self.storage, values["working_dir"])
            snapshot = directory / "settings-snapshot.json"
            atomic_json(snapshot, {key: settings[key] for key in
                                   (*FLAGS, "collection-id", "core_metadata_csv", "gems_metadata_csv",
                                    "azure_blob_storage_path", "file_to_id_map")})
            job = dict(id=job_id, kind=kind, state="queued", inputs=values, created_at=now(),
                       updated_at=now(), message="Queued", progress=0, result={},
                       directory=str(directory), log=str(directory / "job.log"),
                       settings_snapshot=str(snapshot))
            atomic_json(directory / "job.json", job)
            self._jobs[job_id] = job
            self._active = job_id
            self._cancel.clear()
            self._thread = threading.Thread(target=self._run, args=(job_id,), name=f"dart-{job_id}", daemon=False)
            try:
                self._thread.start()
            except RuntimeError as exc:
                self._active = None
                self._update(job_id, state="failed", message=str(exc), finished_at=now())
                raise
            return job_id

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._mutex:
            self.storage.check()
            if "message" in changes:
                changes["message"] = redact(changes["message"])
            updated = dict(self._jobs[job_id], **changes, updated_at=now())
            atomic_json(self.storage.jobs / job_id / "job.json", updated)
            self._jobs[job_id] = updated

    def _checkpoint(self) -> None:
        if self._cancel.is_set():
            raise Cancelled("Cancellation requested. Partial outputs are retained for review.")
        self.storage.check()

    def _run(self, job_id: str) -> None:
        job_dir = self.storage.jobs / job_id
        handler = None
        try:
            self._checkpoint()
            log_path = job_dir / "job.log"
            descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            handler = logging.StreamHandler(os.fdopen(descriptor, "a"))
            handler.setFormatter(RedactedFormatter("%(asctime)s %(levelname)s %(message)s"))
            worker_id = threading.get_ident()
            handler.addFilter(lambda record: record.thread == worker_id)
            root_logger = logging.getLogger()
            root_logger.addHandler(handler)
            self._update(job_id, state="running", message="Starting", started_at=now())

            def report(message: str, progress: float | None) -> None:
                self._checkpoint()
                handler.emit(logging.LogRecord("dart.job", logging.INFO, "", 0, message, (), None))
                changes: dict[str, Any] = {"message": message}
                if progress is not None:
                    changes["progress"] = progress
                changes["result"] = dict(workflow.results)
                self._update(job_id, **changes)

            workflow = Workflow(self.storage, job_dir, job_id, self._checkpoint, report)
            job = self._jobs[job_id]
            result = workflow.run(job["kind"], job["inputs"])
            # A committed export/package is successful even if cancellation arrives after its final atomic commit.
            self._update(job_id, state="succeeded", message="Completed", result=result, progress=1, finished_at=now())
            handler.emit(logging.LogRecord("dart.job", logging.INFO, "", 0, "Completed", (), None))
        except Exception as exc:
            state = "cancelled" if isinstance(exc, Cancelled) else "failed"
            message = redact(exc)
            if handler is not None:
                handler.emit(logging.LogRecord("dart.job", logging.ERROR, "", 0,
                                              redact(traceback.format_exc()), (), None))
            try:
                self._update(job_id, state=state, message=message, finished_at=now(),
                             result=dict(workflow.results) if "workflow" in locals() else {})
            except (OSError, ValueError) as storage_exc:
                with self._mutex:
                    self.storage_error = redact(f"Job state could not be persisted; stop and inspect storage: {storage_exc}")
                    self._jobs[job_id].update(state="interrupted", message=self.storage_error)
                logging.getLogger(__name__).error("%s", self.storage_error)
        finally:
            if handler is not None:
                logging.getLogger().removeHandler(handler)
                handler.flush()
                handler.stream.close()
                handler.close()
            with self._mutex:
                self._active = None

    def cancel(self, session: str) -> None:
        with self._mutex:
            # Allow cancellation even when storage is unavailable.
            if self._operator != session:
                raise ValueError("Only the active operator can cancel.")
            if self._active is None:
                raise ValueError("No active job to cancel.")
            self._cancel.set()
            self._update(self._active, state="cancelling", message="Waiting for the current file/network operation to stop.")

    def log_tail(self, job_id: str) -> str:
        self.storage.check()
        if job_id not in self._jobs:
            raise ValueError("Unknown job.")
        path = self.storage.jobs / job_id / "job.log"
        if not path.exists():
            return "No job log yet."
        private(path)
        with path.open("rb") as handle:
            handle.seek(max(0, path.stat().st_size - 32768))
            return redact(handle.read(32768).decode(errors="replace"))

    def close(self) -> None:
        with self._mutex:
            self._closing = True
            self._cancel.set()
        if self._thread is not None:
            self._thread.join()
        for handle in reversed(self._locks):
            handle.close()
        self._locks.clear()

    def __enter__(self) -> JobService:
        return self

    def __exit__(self, *_args) -> None:
        self.close()


def valid_job_id(value: str) -> bool:
    return len(value) == 32 and all(char in "0123456789abcdef" for char in value)
