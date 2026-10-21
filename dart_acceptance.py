"""Finite, offline acceptance checks using retained disposable roots only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import signal
import socket
import subprocess
import sys
import tempfile
import time
import traceback
from contextlib import ExitStack, contextmanager
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from dart_storage import MARKER, Storage, atomic_json, private, redact

REPOSITORY = Path(__file__).resolve().parent
PENDING = [
    "Firefox-on-Mac SSH tunnel, operator handoff, copy/paste, reconnect, and action-local error usability",
    "Native desktop application interaction and existing CLI checks on supported operator machines",
    "Administrator-approved read-only //storage mount and real source-path/identifier review",
    "Real collection content, compound relationships, GEMS backfill, and OHM transcript review",
    "Explicitly authorized Azure uploads and overwrite verification in a disposable approved container/path",
    "Administrator-supervised actual storage outage and recovery",
    "Institutional backup restoration into separate roots",
    "dg-landing installation, HTTP startup, private root permissions, and operational approval",
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
    def __init__(self, root: Path, port: int, timeout: float) -> None:
        self.root, self.port, self.timeout = root, port, timeout
        atomic_json(root / "acceptance-root.json", {"purpose": "DART isolated acceptance v1"})
        for name in ("config", "data"):
            (root / name).mkdir(mode=0o700)
        self.storage = Storage(root / "config", root / "data")
        self.storage.initialize()
        self.env_file = environment_file(root, self.storage)
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith(("DART_", "FLET_")) and not any(
                        word in key.upper() for word in ("SECRET", "TOKEN", "PASSWORD", "CONNECTION_STRING", "API_KEY"))}
        self.env.update(FLET_SERVER_IP="127.0.0.1", FLET_SERVER_PORT=str(port))
        self.results = [{"check": name, "status": "PENDING"} for name in
                        ("baseline", "offline_workflows", "lifecycle", "storage_fail_closed", "web_http")]

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
                                                executable=sys.executable, port=self.port))
        self.command("revision", ["git", "rev-parse", "HEAD"])
        self.command("worktree", ["git", "--no-pager", "status", "--short"])
        self.command("packages", [sys.executable, "-m", "pip", "freeze"])
        self.command("pip-check", [sys.executable, "-m", "pip", "check"])
        self.command("tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])

    def offline_workflows(self) -> None:
        from dart_service import JobService
        from dart_workflows import digest, read_csv
        source, work, core = fixture(self.storage)
        before = digest(source / "sample.jpg")
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
            compared = run("compare", csv_path=derived["result"]["csv"])
            merged = run("merge", comparison=compared["result"]["comparison"], confirm_merge=True,
                         selected_added=[0], selected_fields=[])
            require(len(read_csv(core)[1]) == 1, "Core must contain exactly one merged row.")
            require(Path(merged["result"]["backup"]).exists(), "Merge backup missing.")
            require(digest(source / "sample.jpg") == before, "Source changed.")
            self.exported_csv = exported["result"]["csv"]
            self.work = work
            atomic_json(self.root / "offline-results.json", {
                "jobs": [job["id"] for job in (exported, derived, compared, merged)],
                "core": str(core), "source_sha256_before": before, "source_sha256_after": digest(source / "sample.jpg")})

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

    def web_http(self) -> None:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", self.port))
        command = [sys.executable, "-m", "dart_linux", "--env-file", str(self.env_file),
                   "--web", "--port", str(self.port)]
        opener = build_opener(ProxyHandler({}))
        with child(command, self.env, self.root / "web.log") as process:
            def ready():
                require(process.poll() is None, f"Web startup exited; inspect {self.root / 'web.log'}")
                try:
                    with opener.open(f"http://127.0.0.1:{self.port}/", timeout=1) as response:
                        content = response.read()
                        if response.status == 200 and b"flutter" in content.lower():
                            (self.root / "http-response.html").write_bytes(content)
                            return True
                except (URLError, TimeoutError, ConnectionError):
                    return False
                return False
            wait_for(ready, self.timeout)
            second = self.command("second-writer", command, expect_success=False)
            require("Another DART writer" in second.read_text(), "Second writer did not fail for the expected lock reason.")
            # Ensure application code and private state aren't served as static files.
            for path in ("app.py", "dart.env", ".git/config"):
                try:
                    with opener.open(f"http://127.0.0.1:{self.port}/{path}", timeout=3) as response:
                        content = response.read()
                        require(b"DART_CONFIG_DIR=" not in content and b"import flet" not in content,
                                f"Private resource exposed: {path}")
                except URLError:
                    pass
            self.web_controls()
            atomic_json(self.root / "http.json", dict(url=f"http://127.0.0.1:{self.port}/",
                                                    status=200, flutter_bootstrap=True, second_writer="refused"))
        require(process.poll() is not None, "Temporary web process is still running.")

    def web_controls(self) -> None:
        """Exercise the actual Flet transport without pretending to review Firefox."""
        first = FletClient(self.port, self.timeout)
        second = None
        try:
            first.until(lambda: first.find("elevatedbutton", text="Export CSV") is not None)
            export = first.find("elevatedbutton", text="Export CSV")
            first.click(export["i"])
            first.until(lambda: any("absolute Linux server path" in control.get("value", "")
                                    for control in first.controls.values()))
            work = first.find("textfield", label="Working Project (Existing Private Server Directory)")
            first.send("updateControlProps", {"props": [{"i": work["i"], "value": str(self.work)}]})
            first.click(first.find("elevatedbutton", text="Load This Project's Settings")["i"])
            first.until(lambda: first.find("textfield", label="Collection-ID (Collection-Specific; Required)").get("value") == "acceptance")
            old_ids = {path.name for path in self.storage.jobs.iterdir()}
            first.click(export["i"])
            first.until(lambda: any("| succeeded: Completed" in control.get("value", "")
                                    for control in first.controls.values()))
            new_ids = {path.name for path in self.storage.jobs.iterdir()} - old_ids
            require(len(new_ids) == 1, "Transport export must submit exactly one job.")
            job_id = new_ids.pop()
            job = json.loads((self.storage.jobs / job_id / "job.json").read_text())
            require(job["state"] == "succeeded" and job["kind"] == "export", "Web transport job did not succeed.")
            second = FletClient(self.port, self.timeout)
            second.until(lambda: any("Read-Only: Another Browser" in control.get("value", "")
                                     for control in second.controls.values()))
            first.close()
            second.until(lambda: any(control.get("value") == "Active Operator"
                                     for control in second.controls.values()))
            atomic_json(self.root / "web-controls.json", {
                "transport": "real Flet websocket", "action_local_validation": "PASS",
                "load_project_settings": "PASS", "export_job": job_id,
                "second_session_read_only": "PASS", "disconnect_handoff": "PASS",
                "firefox_visual_usability": "PENDING"})
        finally:
            first.close()
            if second is not None:
                second.close()

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


class FletClient:
    """Small protocol probe for the pinned Flet 0.25.2 runtime."""
    def __init__(self, port: int, timeout: float) -> None:
        from websockets.sync.client import connect
        self._stack = ExitStack()
        self.connection = self._stack.enter_context(
            connect(f"ws://127.0.0.1:{port}/ws", open_timeout=10, close_timeout=5))
        self.controls: dict[str, dict] = {}
        self.timeout = timeout
        self.send("registerWebClient", dict(
            pageName="", pageRoute="/", pageWidth="1200", pageHeight="900", windowWidth="",
            windowHeight="", windowTop="", windowLeft="", isPWA="false", isWeb="true",
            isDebug="false", platform="linux", platformBrightness="light", media="{}", sessionId=""))

    def send(self, action: str, payload) -> None:
        self.connection.send(json.dumps(dict(action=action, payload=payload)))

    def click(self, control_id: str) -> None:
        self.send("pageEventFromWeb", dict(eventTarget=control_id, eventName="click", eventData=""))

    def find(self, kind: str, **properties):
        return next((control for control in self.controls.values() if control.get("t") == kind
                     and all(control.get(key) == value for key, value in properties.items())), None)

    def apply(self, message: dict) -> None:
        action, payload = message["action"], message["payload"]
        if action == "pageControlsBatch":
            for child_message in payload:
                self.apply(child_message)
        elif action == "registerWebClient":
            require(not payload.get("error"), f"Web session error: {payload.get('error')}")
            self.controls.update(payload["session"]["controls"])
        elif action == "addPageControls":
            self.controls.update({control["i"]: control for control in payload["controls"]})
        elif action == "updateControlProps":
            for props in payload["props"]:
                self.controls.setdefault(props["i"], {}).update(props)
        elif action == "removeControl":
            for control_id in payload["ids"]:
                self.controls.pop(control_id, None)
        elif action == "sessionCrashed":
            raise RuntimeError(f"Web session crashed: {payload}")

    def until(self, check) -> None:
        deadline = time.monotonic() + self.timeout
        while not check():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Flet transport did not produce the expected UI state.")
            self.apply(json.loads(self.connection.recv(timeout=remaining)))

    def close(self) -> None:
        self._stack.close()


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
    parser.add_argument("--port", type=int, default=8561)
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--lifecycle-child", choices=["cancel", "interrupt"], help=argparse.SUPPRESS)
    parser.add_argument("--root", help=argparse.SUPPRESS)
    parser.add_argument("--csv", help=argparse.SUPPRESS)
    parser.add_argument("--working", help=argparse.SUPPRESS)
    args = parser.parse_args()
    os.umask(0o077)
    if args.lifecycle_child:
        return lifecycle_child(args)
    if args.port in {8550, 8551, 8560} or not 1024 <= args.port <= 65535:
        parser.error("Acceptance must use its own unprivileged port, not 8550, 8551, or normal DART 8560.")
    if not 1 <= args.timeout <= 600:
        parser.error("--timeout must be between 1 and 600 seconds.")
    parent = None
    if args.evidence_parent:
        parent = Path(args.evidence_parent).resolve(strict=True)
        private(parent, directory=True)
    # Never read the normal service env file or use its configuration/data roots.
    root = Path(tempfile.mkdtemp(prefix="dart-acceptance-", dir=parent)).resolve()
    print(f"Evidence: {root}", flush=True)
    return Runner(root, args.port, args.timeout).run()


if __name__ == "__main__":
    raise SystemExit(main())
