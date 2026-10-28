from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
import shlex
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

import app
import dart_handoff
import dart_processing
from dart_service import ACTIVE, JobService, RedactedFormatter
from dart_storage import MARKER, Storage, atomic_json, load_environment, redact
from dart_workflows import read_csv, write_csv

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix", "Managed headless Linux storage requires POSIX")
class ManagedTests(unittest.TestCase):
    def setUp(self):
        self.previous_umask = os.umask(0o077)
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.config, self.data = self.root / "config", self.root / "data"
        for path in (self.config, self.data):
            path.mkdir(mode=0o700)
        self.storage = Storage(self.config, self.data)
        self.storage.initialize()
        self.work = self.storage.projects / "collection"
        self.work.mkdir(mode=0o700)
        self.source = self.storage.projects / "sources"
        self.source.mkdir(mode=0o700)
        Image.new("RGB", (1200, 600), "blue").save(self.source / "sample.jpg")
        self.core = self.work / "collection.csv"
        self.columns = ["objectid", "original_file_name", "parentid", "type", "title", "format",
                        "display_template", "object_location", "image_small", "image_thumb"]
        write_csv(self.core, self.columns, [])
        self.service = JobService(self.storage)
        self.service.claim("operator")
        self.values = {"input_dir": str(self.source), "core_metadata_csv": str(self.core),
                       "gems_metadata_csv": "", "collection-id": "test", "azure_blob_storage_path": "",
                       "group_compound_objects": False, "create_multiple_objects": True, "process_OHM_data": False}
        self.service.configure("operator", str(self.work), self.values)
        # Default tests fail closed on all real network access, including accidental Azure calls.
        self.network = patch("socket.socket.connect", side_effect=AssertionError("Offline tests prohibit network access"))
        self.network.start()
        self.credentials = patch.dict(os.environ, {"DART_AZURE_CONNECTION_STRING": ""})
        self.credentials.start()

    def tearDown(self):
        self.service.close()
        self.credentials.stop()
        self.network.stop()
        self.temporary.cleanup()
        os.umask(self.previous_umask)

    def run_job(self, kind, **values):
        inputs = dict(working_dir=str(self.work), **values)
        job_id = self.service.submit("operator", kind, inputs)
        self.service._thread.join(timeout=15)
        self.assertFalse(self.service._thread.is_alive(), "Job did not finish in 15 seconds")
        return next(job for job in self.service.jobs() if job["id"] == job_id)

    def success(self, kind, **values):
        job = self.run_job(kind, **values)
        self.assertEqual("succeeded", job["state"], job["message"])
        return job

    def export(self):
        return self.success("export", input_dir=str(self.source))

    def test_export_ids_and_history_survive_reopen_and_tab_close(self):
        job = self.export()
        columns, rows = read_csv(Path(job["result"]["csv"]))
        self.assertEqual(1, len(rows))
        self.assertEqual("sample.jpg", rows[0]["original_file_name"])
        self.assertTrue(rows[0]["objectid"].startswith("test_dg_"))
        self.assertEqual("image/jpeg", rows[0]["format"])
        self.assertEqual("", rows[0]["object_location"])
        original_id = rows[0]["objectid"]
        self.assertIn("filepath", columns)
        self.service.release("operator")
        self.service.close()
        self.service = JobService(self.storage)
        self.service.claim("operator")
        again = self.export()
        self.assertEqual(original_id, read_csv(Path(again["result"]["csv"]))[1][0]["objectid"])
        self.assertEqual(2, len(self.service.jobs()))
        self.assertIn("Completed", self.service.log_tail(job["id"]))
        for path in self.data.rglob("*"):
            if path.is_file():
                self.assertEqual(0, path.stat().st_mode & 0o077, str(path))

    def package(self, **values):
        job = self.success("handoff", **values)
        manifest = json.loads(Path(job["result"]["manifest"]).read_text())
        return job, manifest, Path(job["result"]["package"]) / manifest["csv"]

    def test_local_derivatives_and_handoff_package_never_write_core(self):
        core_before = self.core.read_bytes()
        exported = self.export()
        job = self.success("derivatives", csv_path=exported["result"]["csv"])
        self.assertTrue(job["result"]["local_only"])
        _, rows = read_csv(Path(job["result"]["csv"]))
        for key, maximum in (("image_small", 800), ("image_thumb", 400)):
            with Image.open(rows[0][key]) as image:
                self.assertLessEqual(max(image.size), maximum)
                self.assertEqual(maximum, max(image.size))
                self.assertEqual("RGB", image.mode)
        packaged, manifest, package_csv = self.package(csv_path=job["result"]["csv"])
        self.assertEqual(dart_handoff.FORMAT, manifest["format"])
        self.assertEqual(packaged["id"], manifest["job_id"])
        self.assertEqual("test", manifest["collection_id"])
        self.assertEqual(hashlib.sha256(package_csv.read_bytes()).hexdigest(), manifest["csv_sha256"])
        self.assertEqual(hashlib.sha256(core_before).hexdigest(), manifest["core_snapshot_sha256"])
        self.assertTrue(manifest["derivatives_local_only"])
        self.assertIsNone(manifest["gems_backfill"])
        columns, packaged_rows = read_csv(package_csv)
        self.assertNotIn("filepath", columns)
        self.assertEqual(rows[0]["objectid"], packaged_rows[0]["objectid"])
        self.assertEqual(core_before, self.core.read_bytes())
        self.assertTrue((self.source / "sample.jpg").exists())
        self.assertEqual(0o700, Path(packaged["result"]["package"]).stat().st_mode & 0o777)

    def test_prepare_exports_derives_and_packages_in_one_job(self):
        job = self.success("prepare", input_dir=str(self.source))
        manifest = json.loads(Path(job["result"]["manifest"]).read_text())
        self.assertEqual(1, manifest["rows"])
        self.assertTrue(job["result"]["derivatives"]["images"])
        rows = read_csv(Path(job["result"]["package"]) / "export.csv")[1]
        self.assertTrue(rows[0]["image_small"])
        skipped = self.success("prepare", input_dir=str(self.source), derivatives=False)
        self.assertIsNone(skipped["result"]["derivatives"])

    def test_removed_compare_and_merge_jobs_are_rejected(self):
        for kind in ("compare", "merge"):
            with self.assertRaisesRegex(ValueError, "Unknown workflow"):
                self.service.submit("operator", kind, dict(working_dir=str(self.work)))

    def test_core_snapshot_ids_are_reused_and_conflicts_reported(self):
        write_csv(self.core, self.columns, [dict(objectid="test_dg_100", original_file_name="sample.jpg")])
        exported = self.export()
        self.assertEqual("test_dg_100", read_csv(Path(exported["result"]["csv"]))[1][0]["objectid"])
        _, manifest, _ = self.package(csv_path=exported["result"]["csv"])
        self.assertEqual([], manifest["id_conflicts"])
        write_csv(self.core, self.columns, [dict(objectid="test_dg_200", original_file_name="sample.jpg")])
        _, manifest, _ = self.package(csv_path=exported["result"]["csv"])
        self.assertEqual([dict(original_file_name="sample.jpg", export_objectid="test_dg_100",
                               core_objectid="test_dg_200")], manifest["id_conflicts"])
        self.assertIn("conflict", manifest["warnings"][0])

    def test_ambiguous_core_snapshot_names_are_not_reused(self):
        write_csv(self.core, self.columns, [dict(objectid="test_dg_1", original_file_name="sample.jpg"),
                                            dict(objectid="test_dg_2", original_file_name="sample.jpg")])
        rows = read_csv(Path(self.export()["result"]["csv"]))[1]
        self.assertNotIn(rows[0]["objectid"], {"test_dg_1", "test_dg_2"})

    def test_compound_derivatives_choose_first_image_after_audio(self):
        (self.source / "sample.jpg").unlink()
        (self.source / "instrument-01.mp3").write_bytes(b"audio")
        Image.new("RGB", (1200, 600), "blue").save(self.source / "instrument-02.jpg")
        Image.new("RGB", (1200, 600), "red").save(self.source / "instrument-03.jpg")
        self.values.update(group_compound_objects=True, create_multiple_objects=False)
        self.service.configure("operator", str(self.work), self.values)
        exported = self.export()
        derived = self.success("derivatives", csv_path=exported["result"]["csv"])
        _, rows = read_csv(Path(derived["result"]["csv"]))
        parent = next(row for row in rows if row["type"] == "compound")
        image = next(row for row in rows if row["original_file_name"] == "instrument-02.jpg")
        self.assertEqual("_instrument-01.mp3", parent["original_file_name"])
        for field in ("image_small", "image_thumb"):
            self.assertTrue(parent[field])
            self.assertEqual(image[field], parent[field])
        self.assertEqual(4, derived["result"]["images"])

    def test_compound_derivative_selection_stays_within_family(self):
        parent = dict(objectid="parent", original_file_name="_01.mp3")
        other = dict(objectid="other", original_file_name="_01.mp3")
        rows = [
            parent, other,
            dict(objectid="audio", parentid="parent", original_file_name="01.mp3"),
            dict(objectid="wrong", parentid="other", original_file_name="02.jpg"),
            dict(objectid="nested", parentid="parent", original_file_name="_02.jpg"),
            dict(objectid="image", parentid="nested", original_file_name="02.jpg"),
            dict(objectid="later", parentid="parent", original_file_name="03.jpg"),
        ]
        self.assertIs(rows[5], dart_processing.select_compound_derivative_child(parent, rows))
        rows.pop(5)
        self.assertIs(rows[-1], dart_processing.select_compound_derivative_child(parent, rows))
        rows.pop()
        self.assertIsNone(dart_processing.select_compound_derivative_child(parent, rows))
        rows[-1]["parentid"] = "nested"
        self.assertIsNone(dart_processing.select_compound_derivative_child(parent, rows))

    def test_compound_derivatives_prefer_images_and_keep_pdf_only_fallback(self):
        for suffix in ("jpg", "pdf"):
            with self.subTest(suffix=suffix):
                parent = dict(objectid="parent", original_file_name=f"_01.{suffix}")
                first = dict(objectid="first", parentid="parent", original_file_name=f"01.{suffix}")
                later = dict(objectid="later", parentid="parent", original_file_name="02.jpg")
                expected = first if suffix == "jpg" else later
                self.assertIs(expected, dart_processing.select_compound_derivative_child(parent, [parent, first, later]))
                self.assertIs(first, dart_processing.select_compound_derivative_child(parent, [parent, first]))

    def test_handoff_preserves_newlines_order_and_metadata(self):
        columns = self.columns + ["description", "_dcterms:description"]
        write_csv(self.core, columns, [])
        new = self.work / "new.csv"
        write_csv(new, columns, [
            dict(objectid="parent", original_file_name="_instrument-01.jpg", type="compound",
                 description="Z first\r\nsecond\rthird\nfourth"),
            dict(objectid="image", original_file_name="instrument-01.jpg", parentid="parent",
                 description="Z image\r\ncaption"),
            dict(objectid="audio", original_file_name="instrument-02.mp3", parentid="parent",
                 description="A audio\rnotes", **{"_dcterms:description": "one\r\ntwo"}),
        ])
        _, manifest, package_csv = self.package(csv_path=str(new))
        self.assertEqual(read_csv(new), read_csv(package_csv))
        self.assertFalse(manifest["derivatives_local_only"])

    def test_replaced_core_header_is_revalidated_at_submission(self):
        self.core.write_text("wrong,header\n")
        with self.assertRaisesRegex(ValueError, "Missing required fields"):
            self.service.submit("operator", "export", dict(working_dir=str(self.work), input_dir=str(self.source)))
        self.assertEqual([], self.service.jobs())

    def test_reserved_core_template_can_be_the_snapshot_and_stays_unchanged(self):
        template = self.work / "collection-template.csv"
        template.write_bytes(self.core.read_bytes())
        template.chmod(0o600)
        self.values["core_metadata_csv"] = str(template)
        self.service.configure("operator", str(self.work), self.values)
        before = template.read_bytes()
        self.success("prepare", input_dir=str(self.source))
        self.assertEqual(before, template.read_bytes())

    def test_duplicate_filename_handoff_is_explicit_failure(self):
        exported = self.export()
        columns, rows = read_csv(Path(exported["result"]["csv"]))
        write_csv(Path(exported["result"]["csv"]), columns, rows * 2)
        failed = self.run_job("handoff", csv_path=exported["result"]["csv"])
        self.assertEqual("failed", failed["state"])
        self.assertIn("duplicate", failed["message"])
        self.assertFalse((self.work / "handoff" / failed["id"] / "manifest.json").exists())

    def test_compounds_flat_and_nested_reuse_existing_maps(self):
        (self.source / "sample.jpg").rename(self.source / "item_01.jpg")
        Image.new("RGB", (10, 10)).save(self.source / "item_02.jpg")
        self.values["group_compound_objects"] = True
        self.service.configure("operator", str(self.work), self.values)
        exported = self.export()
        _, nested = read_csv(Path(exported["result"]["csv"]))
        self.assertEqual(4, len(nested))
        self.assertEqual(["compound", "multiple", "child", "child"], [row["type"] for row in nested])
        self.assertEqual("_item_01.jpg", nested[0]["original_file_name"])
        self.assertEqual(nested[0]["objectid"], nested[1]["parentid"])
        child_ids = {r["original_file_name"]: r["objectid"] for r in nested if r["type"] == "child"}
        self.values["create_multiple_objects"] = False
        self.service.configure("operator", str(self.work), self.values)
        flat = read_csv(Path(self.export()["result"]["csv"]))[1]
        self.assertEqual(3, len(flat))
        for row in flat[1:]:
            self.assertEqual(flat[0]["objectid"], row["parentid"])
            self.assertEqual(child_ids[row["original_file_name"]], row["objectid"])

    def test_server_gems_backfill_defaults_on_and_keeps_ids(self):
        exported = self.export()
        gems = self.source / "metadata.csv"
        write_csv(gems, self.columns, [dict(objectid="gems_id", original_file_name="sample.jpg", title="GEMS title")])
        with self.assertRaisesRegex(ValueError, "no gems_metadata_csv"):
            self.service.submit("operator", "handoff", dict(working_dir=str(self.work),
                                                            csv_path=exported["result"]["csv"], backfill=True))
        self.values["gems_metadata_csv"] = str(gems)
        self.service.configure("operator", str(self.work), self.values)
        job, manifest, package_csv = self.package(csv_path=exported["result"]["csv"])
        self.assertTrue(job["inputs"]["backfill"])
        row = read_csv(package_csv)[1][0]
        self.assertEqual("GEMS title", row["title"])
        self.assertTrue(row["objectid"].startswith("test_dg_"))
        self.assertEqual(1, manifest["gems_backfill"]["matched_rows"])
        self.assertTrue((package_csv.parent / "gems-backfill.json").is_file())
        _, manifest, package_csv = self.package(csv_path=exported["result"]["csv"], backfill=False)
        self.assertIsNone(manifest["gems_backfill"])
        self.assertEqual("", read_csv(package_csv)[1][0]["title"])

    def test_collection_id_is_durable_once_ids_exist(self):
        self.export()
        with self.assertRaisesRegex(ValueError, "durable"):
            self.service.configure("operator", str(self.work), dict(self.values, **{"collection-id": "changed"}))
        self.assertFalse((self.work / ".DART-working-directory" / "web-form.json").exists())

    def test_writer_lock_cannot_be_bypassed_by_another_config_root(self):
        other = self.root / "other-config"
        other.mkdir(mode=0o700)
        alternate = Storage(other, self.data)
        alternate.initialize()
        with self.assertRaisesRegex(RuntimeError, "Another DART writer"):
            JobService(alternate)

    def test_same_roots_second_process_is_rejected(self):
        command = [sys.executable, "-c",
                   "from pathlib import Path; from dart_storage import Storage; from dart_service import JobService; "
                   "JobService(Storage(Path(__import__('sys').argv[1]),Path(__import__('sys').argv[2])))",
                   str(self.config), str(self.data)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Another DART writer", result.stderr)

    def test_queued_running_and_cancelling_jobs_become_interrupted(self):
        self.service.close()
        for state in ACTIVE:
            job_id = {"queued": "a", "running": "b", "cancelling": "c"}[state] * 32
            directory = self.storage.jobs / job_id
            directory.mkdir(mode=0o700)
            atomic_json(directory / "job.json", dict(id=job_id, state=state, created_at="earlier", inputs={}, result={}))
        self.service = JobService(self.storage)
        self.assertEqual({"interrupted"}, {job["state"] for job in self.service.jobs()})
        self.assertIsNone(self.service._thread)

    def test_cancellation_survives_tab_close_and_blocks_concurrent_job(self):
        entered, release = threading.Event(), threading.Event()
        def controlled(workflow, kind, inputs):
            entered.set()
            self.assertTrue(release.wait(5))
            workflow.checkpoint()
            return {}
        with patch("dart_service.Workflow.run", controlled):
            try:
                job_id = self.service.submit("operator", "analyze",
                                             dict(working_dir=str(self.work), input_dir=str(self.source)))
                self.assertTrue(entered.wait(5))
                self.assertFalse(self.service.claim("other"))
                with self.assertRaisesRegex(ValueError, "already running"):
                    self.service.submit("operator", "analyze", {})
                self.service.release("operator")
                self.assertEqual("running", self.service.jobs()[0]["state"])
                self.assertTrue(self.service.claim("replacement"))
                self.service.cancel("replacement")
            finally:
                release.set()
                self.service._thread.join(timeout=5)
        self.assertEqual("cancelled", next(j for j in self.service.jobs() if j["id"] == job_id)["state"])

    def test_missing_marker_blocks_writes_without_recreating_it(self):
        marker = self.data / MARKER
        marker.unlink()
        with self.assertRaises(FileNotFoundError):
            self.service.submit("operator", "export", dict(working_dir=str(self.work), input_dir=str(self.source)))
        self.assertFalse(marker.exists())
        self.assertEqual([], list(self.storage.jobs.iterdir()))

    def test_storage_failure_mid_job_is_not_reported_successful(self):
        def unavailable(workflow, kind, inputs):
            (self.data / MARKER).unlink()
            workflow.checkpoint()
            return {"wrong": "success"}
        with patch("dart_service.Workflow.run", unavailable):
            job = self.run_job("export", input_dir=str(self.source))
        self.assertEqual("interrupted", job["state"])
        self.assertTrue(self.service.storage_error)
        self.assertNotEqual("succeeded", json.loads((Path(job["directory"]) / "job.json").read_text())["state"])

    def test_paths_and_symlink_escapes_fail_closed(self):
        for raw in ("", "relative", "/Volumes/storage/objects", "//storage/objects"):
            with self.assertRaises(ValueError):
                self.storage.source(raw)
        link = self.work / "escape"
        link.symlink_to(self.root)
        with self.assertRaises(ValueError):
            self.storage.managed(str(link / "config" / MARKER))
        with self.assertRaises(ValueError):
            self.storage.source(str(self.config / MARKER))

    def test_unavailable_source_mount_is_not_an_empty_local_fallback(self):
        self.storage.sources = ((self.source, self.root),)
        with self.assertRaisesRegex(OSError, "mount is unavailable"):
            self.storage.check()

    def test_source_permissions_and_work_source_overlap_are_validated(self):
        values = dict(self.values, input_dir=str(self.storage.projects))
        with self.assertRaisesRegex(ValueError, "inside the source"):
            self.service.configure("operator", str(self.work), values)

    def test_explicit_upload_optin_required_even_if_credentials_present(self):
        with patch.dict(os.environ, {"DART_AZURE_CONNECTION_STRING": "AccountName=private;AccountKey=secret"}):
            with patch("app.BlobServiceClient.from_connection_string", side_effect=AssertionError("Must stay offline")):
                self.export()
        with self.assertRaisesRegex(ValueError, "explicit"):
            self.service.submit("operator", "export", dict(working_dir=str(self.work), input_dir=str(self.source), overwrite=True))

    def test_failed_upload_remains_failed_and_ids_are_retained(self):
        self.values["azure_blob_storage_path"] = "assets/objs/test"
        self.service.configure("operator", str(self.work), self.values)
        with patch.dict(os.environ, {"DART_AZURE_CONNECTION_STRING": "secret"}):
            with patch("app.BlobServiceClient.from_connection_string", side_effect=RuntimeError("secret upload failed")):
                job = self.run_job("export", input_dir=str(self.source), allow_uploads=True)
        self.assertEqual("failed", job["state"])
        self.assertNotIn("secret", job["message"])
        settings = json.loads((self.work / ".DART-working-directory" / "dart_settings.json").read_text())
        self.assertEqual(1, len(settings["file_to_id_map"]))
        self.assertNotIn("secret", self.service.log_tail(job["id"]))

    def test_ohm_transcripts_use_existing_ids_and_private_local_copies(self):
        directory = self.source / "OHM-data" / "Person_dg_123"
        directory.mkdir(mode=0o700, parents=True)
        (directory / "dg_123.mp3").write_bytes(b"offline audio fixture")
        transcript = directory / "dg_123.csv"
        transcript.write_text("start,end,text\n0,1,Hello\n")
        transcript.chmod(0o644)  # A read-only source's original mode must not leak to the private copy.
        (directory / "dg_123_transcript.json").write_text('{"segments":[{"speaker":"Interviewer"}]}')
        self.values["process_OHM_data"] = True
        self.service.configure("operator", str(self.work), self.values)
        exported = self.export()
        _, rows = read_csv(Path(exported["result"]["csv"]))
        self.assertEqual(1, len(rows))
        self.assertEqual(("test_dg_123", "transcript", "Interviewer"),
                         (rows[0]["objectid"], rows[0]["type"], rows[0]["interviewer"]))
        copied = self.work / "_data" / "transcripts" / "test_dg_123.csv"
        self.assertEqual(transcript.read_bytes(), copied.read_bytes())
        self.assertEqual(0o600, copied.stat().st_mode & 0o777)
        self.assertEqual(0o644, transcript.stat().st_mode & 0o777)
        self.assertEqual("test_dg_123.csv", rows[0]["object_transcript"])

    def test_pdf_tiff_and_nonimage_derivative_paths(self):
        (self.source / "sample.jpg").unlink()
        Image.new("RGB", (1000, 500), "red").save(self.source / "scan.tiff")
        document = app.fitz.open()
        document.new_page(width=720, height=360)
        document.save(self.source / "document.pdf")
        document.close()
        (self.source / "audio.mp3").write_bytes(b"offline fixture")
        exported = self.export()
        derived = self.success("derivatives", csv_path=exported["result"]["csv"])
        self.assertEqual(4, derived["result"]["images"])
        self.assertEqual(4, len(list(Path(derived["result"]["derivatives"]).iterdir())))
        rows = read_csv(Path(derived["result"]["csv"]))[1]
        for row in rows:
            if row["original_file_name"] == "audio.mp3":
                self.assertEqual("", row["image_small"])
            else:
                self.assertTrue(Path(row["image_small"]).is_relative_to(Path(derived["result"]["derivatives"])))

    def test_native_application_refuses_managed_working_roots_only(self):
        with self.assertRaisesRegex(ValueError, "managed headless DART storage"):
            app.get_dart_working_dir(str(self.work))
        native = self.root / "native"
        native.mkdir()
        self.assertEqual(native / ".DART-working-directory", app.get_dart_working_dir(str(native)))

    def test_job_snapshot_excludes_credentials_and_contains_effective_settings(self):
        job = self.export()
        snapshot = json.loads(Path(job["settings_snapshot"]).read_text())
        self.assertEqual("test", snapshot["collection-id"])
        self.assertEqual(str(self.core), snapshot["core_metadata_csv"])
        self.assertNotIn("azure_connection_string", snapshot)

    def test_real_managed_headless_entry_point_configures_and_prepares(self):
        env_file = self.root / "dart.env"
        env_file.write_text(f"DART_CONFIG_DIR={self.config}\nDART_DATA_DIR={self.data}\n"
                            "DART_SOURCE_ROOTS='[]'\nDART_AZURE_CONNECTION_STRING=\n")
        settings = self.root / "settings.json"
        atomic_json(settings, dict(self.values, working_dir=str(self.work), **{"collection-id": "test"}))
        inputs = self.root / "inputs.json"
        atomic_json(inputs, dict(working_dir=str(self.work), input_dir=str(self.source),
                                 allow_uploads=False, overwrite=False))
        self.service.close()
        command = [sys.executable, "-m", "dart_linux", "--env-file", str(env_file)]
        def run(*arguments):
            return subprocess.run([*command, *arguments], cwd=ROOT, capture_output=True, text=True, timeout=30)
        result = run("--configure", "--inputs", str(settings))
        self.assertEqual(0, result.returncode, result.stderr)
        result = run("--job", "prepare", "--inputs", str(inputs))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Evidence:", result.stdout)
        listed = run("--list-jobs")
        self.assertEqual(0, listed.returncode, listed.stderr)
        self.assertEqual("prepare", json.loads(listed.stdout)[0]["kind"])
        removed = run("--list-jobs", "--web")
        self.assertNotEqual(0, removed.returncode)
        self.assertIn("unrecognized arguments: --web", removed.stderr)
        self.service = JobService(self.storage)
        self.service.claim("operator")
        job = self.service.jobs()[0]
        self.assertEqual("succeeded", job["state"])
        self.assertTrue(Path(job["result"]["manifest"]).is_file())


class FakeSSH:
    """Simulates `ssh host command` against a local directory standing in for the server."""
    def __init__(self, files=None, returncode=0):
        self.files, self.calls, self.returncode = dict(files or {}), [], returncode

    def __call__(self, argv, input=None, capture_output=True, timeout=None):
        self.calls.append((argv, input))
        command = argv[-1]
        if self.returncode:
            return SimpleNamespace(returncode=self.returncode, stdout=b"", stderr=b"Permission denied (publickey)")
        if command.startswith("for f in "):
            output = b"".join(content + b"\0" for path, content in sorted(self.files.items())
                              if path.endswith("/manifest.json"))
            return SimpleNamespace(returncode=0, stdout=output, stderr=b"")
        if command.startswith("cat "):
            path = command[4:].strip("'")
            if path not in self.files:
                return SimpleNamespace(returncode=1, stdout=b"", stderr=b"No such file")
            return SimpleNamespace(returncode=0, stdout=self.files[path], stderr=b"")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")


class HandoffTests(unittest.TestCase):
    host, project = "sysadmin@dg-landing", "/data/dart/data/projects/test"
    job_id = "a" * 32

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.local = Path(self.temporary.name)
        self.csv = b"objectid,original_file_name\r\ntest_dg_1,one.jpg\r\n"
        self.core = self.local / "core.csv"
        self.core.write_bytes(b"objectid,original_file_name\r\n")
        self.manifest = dart_handoff.build_manifest(
            job_id=self.job_id, collection_id="test", csv_sha256=hashlib.sha256(self.csv).hexdigest(), rows=1,
            core_snapshot="/server/core-snapshot.csv", core_snapshot_sha256=dart_handoff.sha256_file(self.core),
            gems_backfill=None, id_conflicts=[], derivatives_local_only=False, source="/server/x.csv",
            dart_version="test", created_at="2026-10-28T00:00:00+00:00")
        base = f"{self.project}/handoff/{self.job_id}"
        self.ssh = FakeSSH({f"{base}/manifest.json": json.dumps(self.manifest).encode(), f"{base}/export.csv": self.csv})

    def tearDown(self):
        self.temporary.cleanup()

    def pull(self, **values):
        return dart_handoff.pull_package(self.host, self.project, self.job_id, self.local,
                                         expected_collection_id=values.pop("collection", "test"),
                                         local_core_csv=str(self.core), runner=self.ssh, **values)

    def test_remote_settings_validation(self):
        self.assertTrue(dart_handoff.validate_remote_settings("", "")[0])
        self.assertTrue(dart_handoff.validate_remote_settings(self.host, self.project)[0])
        self.assertTrue(dart_handoff.validate_remote_settings("dg-landing", self.project)[0])
        for host, project in ((self.host, ""), ("", self.project), ("-oProxyCommand=x", self.project), ("-o@host", self.project),
                              (self.host, "relative/path"), (self.host, "/data/../etc"),
                              (self.host, "/Volumes/share"), ("a b@host", self.project)):
            with self.subTest(host=host, project=project):
                self.assertFalse(dart_handoff.validate_remote_settings(host, project)[0])

    def test_list_returns_only_matching_collection_packages(self):
        other = dict(self.manifest, job_id="b" * 32, collection_id="other")
        self.ssh.files[f"{self.project}/handoff/{'b' * 32}/manifest.json"] = json.dumps(other).encode()
        self.ssh.files[f"{self.project}/handoff/{'c' * 32}/manifest.json"] = b"not json"
        packages = dart_handoff.list_remote_packages(self.host, self.project, expected_collection_id="test",
                                                     runner=self.ssh)
        self.assertEqual([self.job_id], [package["job_id"] for package in packages])
        argv = self.ssh.calls[0][0]
        self.assertEqual(["ssh", "-o", "BatchMode=yes"], argv[:3])
        self.assertEqual("--", argv[-3])
        self.assertEqual(self.host, argv[-2])

    def test_pull_verifies_checksum_and_writes_function_4_export(self):
        result = self.pull()
        csv_path = Path(result["csv"])
        self.assertEqual(f"DART_export_handoff_{self.job_id}.csv", csv_path.name)
        self.assertTrue(csv_path.name.startswith("DART_export_"))
        self.assertEqual(self.csv, csv_path.read_bytes())
        self.assertEqual(self.manifest, json.loads(Path(result["manifest"]).read_text()))
        self.assertEqual([], result["warnings"])
        self.core.write_bytes(self.core.read_bytes() + b"test_dg_9,new.jpg\r\n")
        self.assertIn("core CSV changed", self.pull()["warnings"][0])

    def test_pull_refuses_bad_checksum_wrong_collection_and_local_clobber(self):
        self.ssh.files[f"{self.project}/handoff/{self.job_id}/export.csv"] = self.csv + b"x"
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.pull()
        self.assertEqual([], list(self.local.glob("DART_export_*")))
        self.ssh.files[f"{self.project}/handoff/{self.job_id}/export.csv"] = self.csv
        with self.assertRaisesRegex(ValueError, "collection-id"):
            self.pull(collection="other")
        dart_handoff.local_package_paths(self.local, self.job_id)[0].write_bytes(b"edited locally")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.pull()
        with self.assertRaisesRegex(ValueError, "job ID"):
            dart_handoff.pull_package(self.host, self.project, "../../etc", self.local,
                                      expected_collection_id="test", runner=self.ssh)

    def test_ssh_failure_is_reported(self):
        with self.assertRaisesRegex(RuntimeError, "publickey"):
            dart_handoff.list_remote_packages(self.host, self.project, expected_collection_id="test",
                                              runner=FakeSSH(returncode=255))

    def test_push_core_snapshot_streams_bytes_with_quoted_atomic_replace(self):
        project = "/data/dart/data/projects/it's here"
        digest = dart_handoff.push_core_snapshot(self.host, project, str(self.core), runner=self.ssh)
        argv, data = self.ssh.calls[-1]
        self.assertEqual(self.core.read_bytes(), data)
        self.assertEqual(dart_handoff.sha256_file(self.core), digest)
        self.assertIn("umask 077", argv[-1])
        self.assertIn("mv -f", argv[-1])
        self.assertIn(shlex.quote(f"{project}/core-snapshot.csv"), argv[-1])


@unittest.skipUnless(os.name == "posix", "Managed headless Linux storage requires POSIX")
class PureTests(unittest.TestCase):
    def test_shared_comparison_preserves_newline_only_changes_and_ignores_filepath(self):
        old = [dict(objectid="one", original_file_name="one.jpg",
                    title="line\r\nbreak", filepath="/old/one.jpg")]
        new = [dict(old[0], title="line\nbreak", filepath="/new/one.jpg")]
        changes = dart_processing.compare_metadata_rows(old, new)
        self.assertEqual([], changes["added"])
        self.assertEqual([], changes["removed"])
        self.assertEqual([{"key": ["one.jpg"],
                           "fields": {"title": {"from": "line\r\nbreak", "to": "line\nbreak"}}}],
                         changes["changed"])
        self.assertEqual("/old/one.jpg", old[0]["filepath"])
        self.assertEqual("/new/one.jpg", new[0]["filepath"])
        new[0]["title"] = old[0]["title"]
        self.assertEqual([], dart_processing.compare_metadata_rows(old, new)["changed"])

    def test_existing_helper_cli_entry_points_still_offer_help(self):
        for name in ("rename_metadata_field.py", "organize_compound_folders.py",
                     "migrate_legacy_working_files.py", "merge_alma_csv_into_destination.py"):
            with self.subTest(script=name):
                result = subprocess.run([sys.executable, str(ROOT / "scripts" / name), "--help"],
                                        cwd=ROOT, capture_output=True, text=True, timeout=15)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("usage:", result.stdout.lower())

    def test_explicit_roots_and_private_environment_file(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve()
            env = root / "dart.env"
            env.write_text("DART_DATA_DIR=/from-file\nDART_AZURE_CONNECTION_STRING=\n")
            env.chmod(0o600)
            with patch.dict(os.environ, {"DART_CONFIG_DIR": "", "DART_AZURE_CONNECTION_STRING": "inherited"}):
                load_environment(str(env))
                self.assertEqual("", os.environ["DART_AZURE_CONNECTION_STRING"])
                self.assertEqual("/from-file", os.environ["DART_DATA_DIR"])
                with self.assertRaises(ValueError):
                    Storage.from_environment()
            env.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "Owner-only"):
                load_environment(str(env))

    def test_atomic_failure_preserves_previous_file_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            atomic_json(path, {"old": True})
            with patch("dart_storage.os.replace", side_effect=OSError("storage failed")):
                with self.assertRaises(OSError):
                    atomic_json(path, {"new": True})
            self.assertEqual({"old": True}, json.loads(path.read_text()))
            self.assertEqual([path], list(path.parent.iterdir()))

    def test_redacts_connection_keys_signed_urls_and_tracebacks(self):
        with patch.dict(os.environ, {"DART_AZURE_CONNECTION_STRING": "full-private-connection"}):
            value = redact("full-private-connection AccountKey=abc; https://private/a?sv=1&sig=xyz")
            for secret in ("full-private-connection", "abc", "sig=xyz"):
                self.assertNotIn(secret, value)
            record = logging.LogRecord("test", logging.ERROR, "", 0, "https://host/file?sig=xyz", (), None)
            self.assertNotIn("xyz", RedactedFormatter().format(record))

    def test_importing_workflow_does_not_create_home_storage(self):
        with tempfile.TemporaryDirectory() as home:
            result = subprocess.run([sys.executable, "-c", "import dart_workflows"], cwd=ROOT,
                                    env=dict(os.environ, HOME=home), capture_output=True, text=True, timeout=15)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse((Path(home) / "DART-data").exists())

    def test_shared_compound_algorithm_matches_original_desktop_algorithm(self):
        # Compare ASTs to the pre-extraction baseline, not a hand-written approximation.
        after = ast.parse(Path(dart_processing.__file__).read_text()).body
        after = next(node for node in after if isinstance(node, ast.FunctionDef) and node.name == "analyze_compound_objects")
        # Python 3.13 omits empty AST fields by default; keep them so the fingerprint is version-independent.
        options = {"show_empty": True} if sys.version_info >= (3, 13) else {}
        fingerprint = hashlib.sha256(ast.dump(ast.Module(body=after.body[1:], type_ignores=[]), **options).encode()).hexdigest()
        # Original processing body at 95d07cd, excluding docstring indentation.
        self.assertEqual("7db6f8ccce5312ebd99c3bdf08acf1012233e0587607901b9536c08398bf5dd0", fingerprint)

    def test_shared_export_rows_preserve_legacy_and_ohm_shapes(self):
        columns, rows = dart_processing.build_export_rows(
            ["objectid", "filename", "title", "parentid", "display_template", "format", "originating_system_id"],
            [dict(objectid="dg_2", filename="sample_01.jpg", filepath="/approved/sample_01.jpg", parentid="dg_1", type="child")],
            [dict(objectid="dg_1", first_child_filename="sample_01.jpg", type="compound", display_text_base="Sample")])
        self.assertEqual(["objectid", "original_file_name", "filepath"], columns[:3])
        self.assertEqual("_sample_01.jpg", rows[0]["original_file_name"])
        self.assertEqual("", rows[0]["filepath"])
        self.assertEqual("compound_object", rows[0]["display_template"])
        self.assertEqual("image/jpeg", rows[1]["format"])
        columns, rows = dart_processing.build_export_rows(
            ["objectid", "original_file_name", "transcript"], [
                dict(objectid="test_dg_3", filename="dg_3.mp3", object_transcript="test_dg_3.csv",
                     type="transcript", title="Interview", interviewee="Person")], [], True)
        self.assertIn("object_transcript", columns)
        self.assertEqual("test_dg_3.csv", rows[0]["transcript"])
        self.assertEqual("Interview", rows[0]["title"])

    def test_azure_derivative_paths_preserve_existing_desktop_semantics(self):
        for value in ("objs/collection", "container/objs/collection", "/myobjs/objs/group/", "objs"):
            parts = value.strip().strip("/").split("/", 1)
            container, base = parts[0], parts[1] if len(parts) == 2 else ""
            expected = tuple(container.replace("objs", target) + ("/" + base if base else "")
                             for target in ("smalls", "thumbs"))
            self.assertEqual(expected, dart_processing.get_derivative_azure_paths(value))


if __name__ == "__main__":
    unittest.main()
