from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import dart_batch
from dart_service import JobService
from dart_storage import Storage
from dart_workflows import Cancelled, Workflow, project_settings, read_csv, write_csv

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix", "Managed batch operation requires POSIX")
class BatchTests(unittest.TestCase):
    def setUp(self):
        self.umask = os.umask(0o077)
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.config, self.data = self.root / "config", self.root / "data"
        for path in (self.config, self.data):
            path.mkdir(mode=0o700)
        self.storage = Storage(self.config, self.data)
        self.storage.initialize()
        self.source = self.storage.projects / "source-assets"
        self.source.mkdir(mode=0o700)
        Image.new("RGB", (40, 20), "blue").save(self.source / "sample.jpg")
        self.template = self.config / "template.csv"
        self.columns = ["objectid", "original_file_name", "title", "parentid", "type", "display_template",
                        "format", "object_location", "image_small", "image_thumb"]
        write_csv(self.template, self.columns, [])
        self.service = JobService(self.storage)
        self.service.claim("headless")
        self.stop = threading.Event()
        self.network = patch("socket.socket.connect", side_effect=AssertionError("Batch tests prohibit network access"))
        self.network.start()
        self.credentials = patch.dict(os.environ, {"DART_AZURE_CONNECTION_STRING": ""})
        self.credentials.start()

    def tearDown(self):
        self.service.close()
        self.credentials.stop()
        self.network.stop()
        self.temporary.cleanup()
        os.umask(self.umask)

    def entry(self, collection, **changes):
        return dict(collection_id=collection, input_dir=str(self.source),
                    setup=dict(core_template=str(self.template), group_compound_objects=False,
                               create_multiple_objects=True), **changes)

    def run_batch(self, *entries):
        with redirect_stdout(io.StringIO()):
            return dart_batch.run_batch(self.service, {"collections": list(entries)}, self.stop)

    def summary(self):
        paths = list((self.data / "batches").glob("*/summary.json"))
        return json.loads(max(paths, key=lambda path: path.stat().st_mtime_ns).read_text())

    def test_multiple_collections_produce_independent_packages_and_reuse_ids(self):
        entries = [self.entry("first"), self.entry("second")]
        self.assertEqual(0, self.run_batch(*entries))
        summary = self.summary()
        self.assertEqual("succeeded", summary["state"])
        ids = []
        for record in summary["collections"]:
            self.assertEqual("succeeded", record["state"])
            manifest = json.loads(Path(record["result"]["manifest"]).read_text())
            self.assertEqual(record["collection_id"], manifest["collection_id"])
            self.assertEqual(1, manifest["rows"])
            work = Path(record["working_dir"])
            self.assertEqual(self.template.read_bytes(), (work / "core-snapshot.csv").read_bytes())
            ids.append(read_csv(Path(record["result"]["package"]) / "export.csv")[1][0]["objectid"])
        self.assertNotEqual(*ids)
        self.assertEqual(0, self.run_batch(*entries))
        for previous, record in zip(ids, self.summary()["collections"]):
            self.assertEqual(previous, read_csv(Path(record["result"]["package"]) / "export.csv")[1][0]["objectid"])
        for path in self.data.rglob("*"):
            self.assertEqual(0, path.stat().st_mode & 0o077, str(path))

    def test_setup_and_worker_failures_do_not_prevent_later_collection(self):
        invalid = self.entry("missing")
        invalid["input_dir"] = str(self.root / "missing")
        original = Workflow.run

        def run(workflow, kind, inputs):
            if Path(inputs["working_dir"]).name == "broken":
                raise RuntimeError("Deliberate collection failure")
            return original(workflow, kind, inputs)

        with patch.object(Workflow, "run", run):
            self.assertEqual(1, self.run_batch(invalid, self.entry("broken"), self.entry("good")))
        records = self.summary()["collections"]
        self.assertEqual(["failed", "failed", "succeeded"], [record["state"] for record in records])
        self.assertNotIn("job_id", records[0])
        self.assertIn("Deliberate collection failure", Path(records[1]["log"]).read_text())
        self.assertTrue(Path(records[2]["result"]["manifest"]).exists())

    def test_gems_backfill_and_flat_compounds_remain_collection_scoped(self):
        Image.new("RGB", (40, 20), "red").save(self.source / "sample_02.jpg")
        (self.source / "sample.jpg").rename(self.source / "sample_01.jpg")
        entries = []
        for collection in ("first", "second"):
            gems = self.storage.projects / f"{collection}-gems.csv"
            write_csv(gems, self.columns, [
                dict(objectid="gems-id", original_file_name="_sample_01.jpg", title=f"{collection} title")])
            entry = self.entry(collection)
            entry["setup"] = dict(core_template=str(self.template), gems_metadata_csv=str(gems))
            entries.append(entry)
        self.assertEqual(0, self.run_batch(*entries))
        for record in self.summary()["collections"]:
            rows = read_csv(Path(record["result"]["package"]) / "export.csv")[1]
            self.assertEqual(["compound", "child", "child"], [row["type"] for row in rows])
            self.assertEqual(f"{record['collection_id']} title", rows[0]["title"])
            self.assertTrue(all(row["objectid"].startswith(f"{record['collection_id']}_dg_") for row in rows))
            self.assertTrue(all(row["parentid"] == rows[0]["objectid"] for row in rows[1:]))
            manifest = json.loads(Path(record["result"]["manifest"]).read_text())
            self.assertEqual(1, manifest["gems_backfill"]["matched_rows"])

    def test_summary_write_failure_aborts_instead_of_submitting_next_collection(self):
        original = dart_batch.atomic_json

        def persist(path, value):
            if path.name == "summary.json" and value["collections"][0].get("job_id"):
                raise OSError("Summary disk full")
            return original(path, value)

        with patch.object(dart_batch, "atomic_json", persist):
            with self.assertRaisesRegex(OSError, "Summary disk full"):
                self.run_batch(self.entry("first"), self.entry("second"))
        self.service.close()
        self.assertFalse((self.storage.projects / "second").exists())
        self.assertEqual(1, len(self.service.jobs()))
        self.assertEqual("running", self.summary()["state"])

    def test_existing_settings_and_refreshed_snapshot_are_not_overwritten(self):
        entry = self.entry("existing")
        self.assertEqual(0, self.run_batch(entry))
        work = self.storage.projects / "existing"
        settings_before = project_settings(self.storage, str(work))
        write_csv(work / "core-snapshot.csv", self.columns, [
            dict(objectid="existing_dg_1", original_file_name="other.jpg")])
        snapshot_before = (work / "core-snapshot.csv").read_bytes()
        self.assertEqual(0, self.run_batch(entry))
        self.assertEqual(snapshot_before, (work / "core-snapshot.csv").read_bytes())
        self.assertEqual(settings_before["file_to_id_map"],
                         project_settings(self.storage, str(work))["file_to_id_map"])
        entry.pop("setup")
        self.assertEqual(0, self.run_batch(entry))

    def test_changed_setup_is_rejected_without_changing_settings(self):
        entry = self.entry("existing")
        self.assertEqual(0, self.run_batch(entry))
        work = self.storage.projects / "existing"
        before = project_settings(self.storage, str(work))
        entry["setup"]["group_compound_objects"] = True
        self.assertEqual(1, self.run_batch(entry))
        self.assertIn("Existing settings differ", self.summary()["collections"][0]["message"])
        self.assertEqual(before, project_settings(self.storage, str(work)))

    def test_template_rows_existing_snapshot_and_project_alias_fail_closed(self):
        write_csv(self.template, self.columns, [dict(objectid="dg_1", original_file_name="existing.jpg")])
        self.assertEqual(1, self.run_batch(self.entry("nonempty")))
        self.assertFalse((self.storage.projects / "nonempty").exists())
        write_csv(self.template, self.columns, [])
        work = self.storage.projects / "snapshot"
        work.mkdir(mode=0o700)
        write_csv(work / "core-snapshot.csv", self.columns, [dict(objectid="dg_1", original_file_name="other.jpg")])
        before = (work / "core-snapshot.csv").read_bytes()
        (self.storage.projects / "alias").symlink_to(work, target_is_directory=True)
        self.assertEqual(1, self.run_batch(self.entry("snapshot"), self.entry("alias")))
        self.assertEqual(before, (work / "core-snapshot.csv").read_bytes())
        self.assertFalse((work / ".DART-working-directory").exists())

    def test_invalid_queue_is_rejected_before_any_setup(self):
        for entries in ([], [self.entry("duplicate"), self.entry("duplicate")],
                        [self.entry("../escape")], [self.entry("collection-template")],
                        [self.entry("bad", allow_uploads="yes")], [self.entry("bad", overwrite=True)],
                        [self.entry("bad", unexpected=True)]):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                self.run_batch(*entries)
        self.assertFalse((self.data / "batches").exists())

    def test_upload_consent_is_per_collection_and_requires_credentials(self):
        upload = self.entry("upload", allow_uploads=True)
        upload["setup"]["azure_blob_storage_path"] = "/objs/upload"
        self.assertEqual(1, self.run_batch(upload, self.entry("local")))
        self.assertIn("credential", self.summary()["collections"][0]["message"])
        self.assertEqual("succeeded", self.summary()["collections"][1]["state"])
        received = []

        def run(_workflow, _kind, inputs):
            received.append(inputs)
            return {}

        with patch.dict(os.environ, {"DART_AZURE_CONNECTION_STRING": "test-private"}), patch.object(Workflow, "run", run):
            self.assertEqual(0, self.run_batch(upload, self.entry("local")))
        self.assertEqual([True, False], [inputs["allow_uploads"] for inputs in received])
        self.assertEqual([False, False], [inputs["overwrite"] for inputs in received])

    def test_cancellation_keeps_remaining_collections_pending(self):
        def run(_workflow, _kind, _inputs):
            self.stop.set()
            raise Cancelled("Operator cancelled")

        with patch.object(Workflow, "run", run):
            self.assertEqual(130, self.run_batch(self.entry("first"), self.entry("second")))
        summary = self.summary()
        self.assertEqual("cancelled", summary["state"])
        self.assertEqual(["cancelled", "pending"], [row["state"] for row in summary["collections"]])
        self.assertFalse((self.storage.projects / "second").exists())

    def test_real_cli_creates_projects_and_reports_batch_exit_status(self):
        self.service.close()
        env = self.config / "dart.env"
        env.write_text(f"DART_CONFIG_DIR={self.config}\nDART_DATA_DIR={self.data}\nDART_SOURCE_ROOTS=[]\n")
        queue = self.config / "queue.json"
        queue.write_text(json.dumps({"collections": [self.entry("first"), self.entry("second")]}))
        command = [sys.executable, "-m", "dart_linux", "--env-file", str(env), "--batch", "--inputs", str(queue)]
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(0, completed.returncode, completed.stderr + completed.stdout)
        self.assertIn("Batch succeeded.", completed.stdout)
        self.assertEqual(2, len(self.summary()["collections"]))
        invalid = self.entry("missing")
        invalid["input_dir"] = str(self.root / "unavailable")
        queue.write_text(json.dumps({"collections": [invalid, self.entry("third")]}))
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(1, completed.returncode, completed.stderr + completed.stdout)
        self.assertEqual(["failed", "succeeded"], [row["state"] for row in self.summary()["collections"]])
        queue.chmod(0o644)
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(1, completed.returncode)
        self.assertIn("Owner-only", completed.stderr)


if __name__ == "__main__":
    unittest.main()
