"""Headless Linux entry point: prepares handoff packages for desktop DART review/merge.

The desktop entry point stays app.py. Headless DART never compares or merges
into a core CSV; desktop DART pulls packages over SSH for Function 4.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import threading

from dart_storage import Storage, load_environment, redact

JOB_KINDS = ["analyze", "export", "derivatives", "handoff", "prepare"]


def read_private_json(raw: str) -> dict:
    from dart_storage import absolute, private
    path = absolute(raw)
    private(path)
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("Inputs must be a JSON object.")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", required=True, help="Existing owner-only private environment file")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--initialize-storage", action="store_true", help="Initialize existing explicitly approved roots")
    modes.add_argument("--configure", action="store_true",
                       help="Save collection settings from --inputs (working_dir plus settings fields)")
    modes.add_argument("--job", choices=JOB_KINDS, help="Run one headless job from --inputs")
    modes.add_argument("--list-jobs", action="store_true", help="Print job history as JSON")
    parser.add_argument("--inputs", help="Private JSON file of explicit inputs for --configure or --job")
    args = parser.parse_args()
    if os.name != "posix":
        parser.error("Managed mode requires POSIX; use app.py for Windows desktop operation.")
    os.umask(0o077)
    try:
        load_environment(args.env_file)
        storage = Storage.from_environment()
        if args.initialize_storage:
            storage.initialize()
            print(f"Initialized DART storage: {storage.config} | {storage.data}")
            return 0
        storage.check()
        from dart_service import JobService, RedactedFormatter
        console = logging.StreamHandler()
        console.setFormatter(RedactedFormatter("%(levelname)s %(message)s"))
        logging.basicConfig(level=logging.WARNING, handlers=[console], force=True)
        if args.list_jobs:
            with JobService(storage) as service:
                print(json.dumps([{key: job.get(key) for key in ("id", "kind", "state", "created_at", "message", "result")}
                                  for job in service.jobs()], indent=2))
            return 0
        if not args.inputs:
            parser.error("--configure and --job require --inputs")
        inputs = read_private_json(args.inputs)
        with JobService(storage) as service:
            service.claim("headless")
            if args.configure:
                from dart_workflows import FLAGS, FORM_FIELDS
                unknown = set(inputs) - {"working_dir", *FLAGS, *FORM_FIELDS}
                if unknown:
                    raise ValueError(f"Unexpected settings keys: {sorted(unknown)}")
                service.configure("headless", str(inputs.pop("working_dir", "")), inputs)
                print("Saved collection settings.")
                return 0
            interrupted = threading.Event()

            def stop(_number, _frame) -> None:
                interrupted.set()
                service._cancel.set()

            signal.signal(signal.SIGINT, stop)
            signal.signal(signal.SIGTERM, stop)
            job_id = service.submit("headless", args.job, inputs)
            if interrupted.is_set():
                service._cancel.set()
            print(f"Job: {job_id}\nEvidence: {storage.jobs / job_id}", flush=True)
            service._thread.join()
            job = next(job for job in service.jobs() if job["id"] == job_id)
            print(json.dumps(job, indent=2))
            return 0 if job["state"] == "succeeded" else (130 if interrupted.is_set() else 1)
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(f"DART startup/job error: {redact(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
