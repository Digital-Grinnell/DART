"""Finite, offline acceptance checks using retained disposable roots only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
import tempfile
import time
import traceback
from contextlib import contextmanager
from pathlib import Path

from dart_storage import MARKER, Storage, atomic_json, private, redact

REPOSITORY = Path(__file__).resolve().parent
PENDING = [
    "Desktop DART SSH key access, core snapshot push, handoff pull, and Function 4 review on an operator Mac",
    "Native desktop application interaction and existing CLI checks on supported operator machines",
    "Administrator-approved read-only //storage mount and real source-path/identifier review",
    "Real collection content, compound relationships, GEMS backfill, and OHM transcript review",
    "Explicitly authorized Azure uploads and overwrite verification in a disposable approved container/path",
    "Administrator-supervised actual storage outage and recovery",
    "Institutional backup restoration into separate roots",
    "dg-landing installation, headless CLI startup, private root permissions, and operational approval",
    "VS Code Markdown PDF rendering and one-printed-page diagram inspection",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def wait_for(check, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.1)
    raise TimeoutError(f"Check did not finish within {timeout:g} seconds.")


def wait_job(service, job_id: str, timeout: float = 30) -> dict:
    service._thread.join(timeout=timeout)
    require(not service._thread.is_alive(), "Job did not finish before timeout.")
    job = next(job for job in service.jobs() if job["id"] == job_id)
    return job


def environment_file(root: Path, storage: Storage) -> Path:
    path = root / "dart.env"
    path.write_text(f"DART_CONFIG_DIR={storage.config}\nDART_DATA_DIR={storage.data}\n"
                    "DART_SOURCE_ROOTS='[]'\nDART_AZURE_CONNECTION_STRING=\n")
    path.chmod(0o600)
    return path


@contextmanager
def child(command: list[str], env: dict, log: Path):
    with log.open("w") as handle:
        process = subprocess.Popen(command, cwd=REPOSITORY, env=env, stdout=handle, stderr=subprocess.STDOUT)
        try:
            yield process
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def fixture(storage: Storage) -> tuple[Path, Path, Path]:
    from PIL import Image
    from dart_workflows import write_csv

    source = storage.projects / "source"
    work = storage.projects / "collection"
    source.mkdir(mode=0o700)
    work.mkdir(mode=0o700)
    Image.new("RGB", (1200, 600), "blue").save(source / "sample.jpg")
    core = work / "collection.csv"
    write_csv(core, ["objectid", "original_file_name", "title", "parentid", "type",
                     "display_template", "format", "object_location", "image_small", "image_thumb"], [])
    return source, work, core


def configure(service, source: Path, work: Path, core: Path) -> None:
    service.claim("acceptance")
    service.configure("acceptance", str(work), {
        "input_dir": str(source), "core_metadata_csv": str(core), "collection-id": "acceptance",
        "gems_metadata_csv": "", "azure_blob_storage_path": "", "group_compound_objects": False,
        "create_multiple_objects": True, "process_OHM_data": False})


class Runner:
    def __init__(self, root: Path, timeout: float) -> None:
        self.root, self.timeout = root, timeout
        atomic_json(root / "acceptance-root.json", {"purpose": "DART isolated acceptance v1"})
        for name in ("config", "data"):
            (root / name).mkdir(mode=0o700)
        self.storage = Storage(root / "config", root / "data")
        self.storage.initialize()
        self.env_file = environment_file(root, self.storage)
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith(("DART_", "FLET_")) and not any(
                        word in key.upper() for word in ("SECRET", "TOKEN", "PASSWORD", "CONNECTION_STRING", "API_KEY"))}
        self.results = [{"check": name, "status": "PENDING"} for name in
                        ("baseline", "offline_workflows", "lifecycle", "storage_fail_closed", "headless_cli")]

    def report(self) -> None:
        atomic_json(self.root / "report.json", {
            "evidence_root": str(self.root), "automated": self.results,
            "manual": [{"check": name, "status": "PENDING"} for name in PENDING],
            "acceptance": "PENDING: automated checks do not approve deployment or real content",
            "normal_service_modified": False, "live_actions_requested": False,
        })

    def command(self, name: str, arguments: list[str], *, expect_success: bool = True):
        log = self.root / f"{name}.log"
        with log.open("w") as handle:
            result = subprocess.run(arguments, cwd=REPOSITORY, env=self.env, stdout=handle,
                                    stderr=subprocess.STDOUT, timeout=self.timeout)
        require((result.returncode == 0) == expect_success, f"Unexpected exit {result.returncode}; inspect {log}")
        return log

    def baseline(self) -> None:
        atomic_json(self.root / "host.json", dict(platform=platform.platform(), python=sys.version,
                                                executable=sys.executable))
        self.command("revision", ["git", "rev-parse", "HEAD"])
        self.command("worktree", ["git", "--no-pager", "status", "--short"])
        self.command("packages", [sys.executable, "-m", "pip", "freeze"])
        self.command("pip-check", [sys.executable, "-m", "pip", "check"])
        self.command("tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])

    def offline_workflows(self) -> None:
        from dart_service import JobService
        from dart_workflows import digest, read_csv
        source, work, core = fixture(self.storage)
        before, core_before = digest(source / "sample.jpg"), digest(core)
        with JobService(self.storage) as service:
            configure(service, source, work, core)
            def run(kind: str, **inputs):
                job = wait_job(service, service.submit("acceptance", kind,
                               dict(working_dir=str(work), **inputs)), self.timeout)
                require(job["state"] == "succeeded", f"{kind}: {job['message']}")
                return job
            exported = run("export", input_dir=str(source))
            require(exported["result"]["files"] == 1 and exported["result"]["rows"] == 1, "Wrong export counts.")
            derived = run("derivatives", csv_path=exported["result"]["csv"])
            packaged = run("handoff", csv_path=derived["result"]["csv"])
            manifest = json.loads(Path(packaged["result"]["manifest"]).read_text())
            package_csv = Path(packaged["result"]["package"]) / manifest["csv"]
            require(digest(package_csv) == manifest["csv_sha256"], "Package checksum mismatch.")
            require(len(read_csv(package_csv)[1]) == 1, "Package must contain exactly one row.")
            require(digest(core) == core_before, "Headless DART must never write the core snapshot.")
            require(digest(source / "sample.jpg") == before, "Source changed.")
            self.exported_csv = exported["result"]["csv"]
            self.work, self.source = work, source
            atomic_json(self.root / "offline-results.json", {
                "jobs": [job["id"] for job in (exported, derived, packaged)],
                "package": packaged["result"]["package"], "core_unchanged": True,
                "source_sha256_before": before, "source_sha256_after": digest(source / "sample.jpg")})

    def lifecycle(self) -> None:
        from dart_service import JobService
        evidence = {}
        for mode in ("cancel", "interrupt"):
            ready = self.root / f"{mode}-ready.json"
            args = [sys.executable, "-m", "dart_acceptance", "--lifecycle-child", mode,
                    "--root", str(self.root), "--csv", self.exported_csv, "--working", str(self.work)]
            with child(args, self.env, self.root / f"{mode}.log") as process:
                def prepared():
                    require(process.poll() is None, f"Lifecycle child exited; inspect {mode}.log")
                    return ready.exists()
                wait_for(prepared, self.timeout)
                job_id = json.loads(ready.read_text())["id"]
                if mode == "cancel":
                    process.terminate()
                    require(process.wait(timeout=self.timeout) == 0, "Cancellation child did not finish cleanly.")
                else:
                    process.kill()
                    process.wait(timeout=10)
            with JobService(self.storage) as service:
                job = next(job for job in service.jobs() if job["id"] == job_id)
                expected = "cancelled" if mode == "cancel" else "interrupted"
                require(job["state"] == expected, f"Expected {expected}, got {job['state']}")
                partial = list((self.work / ".DART-working-directory" / f"derivatives_{job_id}").glob("*.jpg"))
                require(len(partial) == 2, "Two partial derivatives must be retained.")
                evidence[mode] = dict(id=job_id, state=job["state"], retained_files=[str(p) for p in partial])
        atomic_json(self.root / "lifecycle.json", evidence)

    def storage_fail_closed(self) -> None:
        from dart_service import JobService
        with JobService(self.storage) as service:
            service.claim("acceptance")
            marker = self.storage.data / MARKER
            original = marker.read_bytes()
            marker.unlink()
            try:
                try:
                    service.submit("acceptance", "export",
                                   dict(working_dir=str(self.work), input_dir=str(self.storage.projects / "source")))
                except FileNotFoundError:
                    require(not marker.exists(), "Missing marker was silently recreated.")
                else:
                    raise RuntimeError("Submission succeeded without its storage marker.")
            finally:
                marker.write_bytes(original)
                marker.chmod(0o600)
            self.storage.check()
        atomic_json(self.root / "storage-failure.json", {
            "missing_marker_submission": "blocked", "automatic_recreation": False,
            "actual_mount_outage": "PENDING: administrator supervision required"})

    def headless_cli(self) -> None:
        from dart_service import JobService
        inputs = self.root / "prepare-inputs.json"
        atomic_json(inputs, dict(working_dir=str(self.work), input_dir=str(self.source)))
        command = [sys.executable, "-m", "dart_linux", "--env-file", str(self.env_file)]
        self.command("cli-prepare", [*command, "--job", "prepare", "--inputs", str(inputs)])
        with JobService(self.storage) as service:
            job = service.jobs()[0]
            require(job["kind"] == "prepare" and job["state"] == "succeeded", "CLI prepare job did not succeed.")
            manifest = Path(job["result"]["manifest"])
            require(manifest.is_file(), "CLI prepare did not write a handoff manifest.")
            second = self.command("second-writer", [*command, "--list-jobs"], expect_success=False)
            require("Another DART writer" in second.read_text(), "Second writer did not fail for the expected lock reason.")
        web = self.command("web-removed", [*command, "--list-jobs", "--web"], expect_success=False)
        require("unrecognized arguments: --web" in web.read_text(), "The removed browser mode must be rejected.")
        atomic_json(self.root / "headless-cli.json", dict(prepare_job=job["id"], manifest=str(manifest),
                                                          second_writer="refused", browser_mode="removed"))

    def run(self) -> int:
        self.report()
        for result in self.results:
            print("RUN:", result["check"], flush=True)
            try:
                getattr(self, result["check"])()
            except Exception as exc:
                result.update(status="FAIL", evidence=redact(exc))
                (self.root / "failure.log").write_text(redact(traceback.format_exc()))
                self.report()
                print(f"FAIL: {result['check']}: {redact(exc)}", file=sys.stderr)
                return 1
            result.update(status="PASS", evidence=str(self.root))
            self.report()
            print("PASS:", result["check"], flush=True)
        print("PENDING: manual checks and deployment approval", flush=True)
        return 0


def lifecycle_child(args) -> int:
    from dart_service import JobService
    from dart_workflows import Workflow
    root = Path(args.root).resolve(strict=True)
    private(root, directory=True)
    marker = root / "acceptance-root.json"
    private(marker)
    if not root.name.startswith("dart-acceptance-") or json.loads(marker.read_text()) != {"purpose": "DART isolated acceptance v1"}:
        raise ValueError("Lifecycle checks require an isolated acceptance root, never normal service roots.")
    storage = Storage(root / "config", root / "data")
    original = Workflow.run
    def controlled(workflow, kind, inputs):
        report = workflow.report
        def delayed(message, progress):
            report(message, progress)
            if message.startswith("Derivative rows:"):
                atomic_json(root / f"{args.lifecycle_child}-ready.json", {"id": workflow.job_id})
                while True:
                    workflow.checkpoint()
                    time.sleep(0.05)
        workflow.report = delayed
        return original(workflow, kind, inputs)
    Workflow.run = controlled
    with JobService(storage) as service:
        service.claim("acceptance")
        def stop(_number, _frame):
            service._cancel.set()
        signal.signal(signal.SIGTERM, stop)
        job_id = service.submit("acceptance", "derivatives", dict(working_dir=args.working, csv_path=args.csv))
        job = wait_job(service, job_id, 120)
        return 0 if job["state"] == "cancelled" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-parent", help="Existing private directory; a unique child is retained")
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--lifecycle-child", choices=["cancel", "interrupt"], help=argparse.SUPPRESS)
    parser.add_argument("--root", help=argparse.SUPPRESS)
    parser.add_argument("--csv", help=argparse.SUPPRESS)
    parser.add_argument("--working", help=argparse.SUPPRESS)
    args = parser.parse_args()
    os.umask(0o077)
    if args.lifecycle_child:
        return lifecycle_child(args)
    if not 1 <= args.timeout <= 600:
        parser.error("--timeout must be between 1 and 600 seconds.")
    parent = None
    if args.evidence_parent:
        parent = Path(args.evidence_parent).resolve(strict=True)
        private(parent, directory=True)
    # Never read the normal service env file or use its configuration/data roots.
    root = Path(tempfile.mkdtemp(prefix="dart-acceptance-", dir=parent)).resolve()
    print(f"Evidence: {root}", flush=True)
    return Runner(root, args.timeout).run()


if __name__ == "__main__":
    raise SystemExit(main())
