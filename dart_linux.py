"""Explicit Linux/browser and managed headless entry point; desktop stays app.py."""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import threading

from dart_storage import Storage, load_environment, redact


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, help="Existing owner-only private environment file")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--web", action="store_true")
    modes.add_argument("--initialize-storage", action="store_true", help="Initialize existing explicitly approved roots")
    modes.add_argument("--job", choices=["analyze", "export", "derivatives", "compare", "merge"])
    parser.add_argument("--inputs", help="Private JSON file of explicit job inputs for managed headless mode")
    parser.add_argument("--port", type=int, default=8560)
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
        if args.web:
            from dart_web import launch
            launch(storage, port=args.port)
            return 0
        if not args.inputs:
            parser.error("--job requires --inputs")
        from dart_storage import absolute, private
        input_path = absolute(args.inputs)
        private(input_path)
        inputs = json.loads(input_path.read_text())
        if not isinstance(inputs, dict):
            raise ValueError("Job inputs must be a JSON object.")
        with JobService(storage) as service:
            service.claim("headless")
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
