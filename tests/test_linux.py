from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
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
import dart_processing
from dart_service import ACTIVE, JobService, RedactedFormatter
from dart_storage import MARKER, Storage, atomic_json, load_environment, redact
from dart_workflows import read_csv, write_csv

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix", "Managed Linux/browser storage requires POSIX")
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

    def test_local_derivatives_and_compare_selective_merge(self):
        exported = self.export()
        job = self.success("derivatives", csv_path=exported["result"]["csv"])
        self.assertTrue(job["result"]["local_only"])
        _, rows = read_csv(Path(job["result"]["csv"]))
        for key, maximum in (("image_small", 800), ("image_thumb", 400)):
            with Image.open(rows[0][key]) as image:
                self.assertLessEqual(max(image.size), maximum)
                self.assertEqual(maximum, max(image.size))
                self.assertEqual("RGB", image.mode)
        compared = self.success("compare", csv_path=job["result"]["csv"])
        self.assertEqual(1, compared["result"]["added"])
        merged = self.success("merge", comparison=compared["result"]["comparison"],
                              confirm_merge=True, selected_added=[0], selected_fields=[])
        self.assertTrue(Path(merged["result"]["backup"]).is_file())
        self.assertEqual(rows[0]["objectid"], read_csv(self.core)[1][0]["objectid"])
        self.assertFalse(merged["result"]["source_retirement"])
        self.assertTrue((self.source / "sample.jpg").exists())
        self.assertNotIn("filepath", read_csv(self.core)[0])

    def test_selective_changes_keep_titles_blanks_ids_and_missing_records(self):
        write_csv(self.core, self.columns, [
            dict(objectid="test_dg_1", original_file_name="one.jpg", title="Keep", format="old"),
            dict(objectid="test_dg_2", original_file_name="missing.jpg", title="Retained")])
        new = self.work / "new.csv"
        write_csv(new, self.columns, [dict(objectid="test_dg_999", original_file_name="one.jpg", title="", format="image/jpeg")])
        compared = self.success("compare", csv_path=str(new))
        plan = compared["result"]["comparison"]
        denied = self.run_job("merge", comparison=plan, confirm_merge=True,
                              selected_added=[], selected_fields=[[0, "objectid"]])
        self.assertEqual("failed", denied["state"])
        merged = self.success("merge", comparison=plan, confirm_merge=True,
                              selected_added=[], selected_fields=[[0, "format"]])
        rows = read_csv(self.core)[1]
        self.assertEqual(2, len(rows))
        self.assertEqual(("test_dg_1", "Keep", "image/jpeg"), (rows[0]["objectid"], rows[0]["title"], rows[0]["format"]))
        self.assertEqual("Retained", rows[1]["title"])

    def test_core_change_after_comparison_refuses_merge(self):
        exported = self.export()
        compared = self.success("compare", csv_path=exported["result"]["csv"])
        before = self.core.read_bytes() + b"\n"
        self.core.write_bytes(before)
        failed = self.run_job("merge", comparison=compared["result"]["comparison"],
                              confirm_merge=True, selected_added=[0], selected_fields=[])
        self.assertEqual("failed", failed["state"])
        self.assertIn("changed since comparison", failed["message"])
        self.assertEqual(before, self.core.read_bytes())

    def test_replaced_core_header_is_revalidated_at_submission(self):
        self.core.write_text("wrong,header\n")
        with self.assertRaisesRegex(ValueError, "Missing required fields"):
            self.service.submit("operator", "export", dict(working_dir=str(self.work), input_dir=str(self.source)))
        self.assertEqual([], self.service.jobs())

    def test_reserved_core_can_template_export_but_never_merge(self):
        template = self.work / "collection-template.csv"
        template.write_bytes(self.core.read_bytes())
        template.chmod(0o600)
        self.values["core_metadata_csv"] = str(template)
        self.service.configure("operator", str(self.work), self.values)
        exported = self.export()
        compared = self.success("compare", csv_path=exported["result"]["csv"])
        failed = self.run_job("merge", comparison=compared["result"]["comparison"],
                              confirm_merge=True, selected_added=[0], selected_fields=[])
        self.assertEqual("failed", failed["state"])
        self.assertIn("reserved", failed["message"])
        self.assertEqual([], read_csv(template)[1])

    def test_duplicate_filename_compare_is_explicit_failure(self):
        exported = self.export()
        columns, rows = read_csv(Path(exported["result"]["csv"]))
        write_csv(Path(exported["result"]["csv"]), columns, rows * 2)
        failed = self.run_job("compare", csv_path=exported["result"]["csv"])
        self.assertEqual("failed", failed["state"])
        self.assertIn("duplicate", failed["message"])

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

    def test_gems_backfill_does_not_replace_ids_or_nonempty_metadata(self):
        exported = self.export()
        gems = self.source / "metadata.csv"
        write_csv(gems, self.columns, [dict(objectid="gems_id", original_file_name="sample.jpg", title="GEMS title")])
        self.values["gems_metadata_csv"] = str(gems)
        self.service.configure("operator", str(self.work), self.values)
        compared = self.success("compare", csv_path=exported["result"]["csv"], backfill=True)
        plan = json.loads(Path(compared["result"]["comparison"]).read_text())
        self.assertEqual("GEMS title", plan["changes"]["added"][0]["title"])
        self.assertTrue(plan["changes"]["added"][0]["objectid"].startswith("test_dg_"))

    def test_settings_defaults_do_not_leak_collection_values_or_credentials(self):
        self.service.configure("operator", str(self.work), self.values, remember_defaults=True)
        saved = json.loads((self.config / "browser-defaults.json").read_text())
        self.assertEqual({"group_compound_objects", "create_multiple_objects", "process_OHM_data"}, set(saved))
        self.assertNotIn("azure_connection_string", self.service.load_form(str(self.work)))
        self.export()
        with self.assertRaisesRegex(ValueError, "durable"):
            self.service.configure("operator", str(self.work), dict(self.values, **{"collection-id": "changed"}))

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
        with self.assertRaisesRegex(ValueError, "managed DART browser storage"):
            app.get_dart_working_dir(str(self.work))
        native = self.root / "native"
        native.mkdir()
        self.assertEqual(native / ".DART-working-directory", app.get_dart_working_dir(str(native)))

    def test_browser_actions_validate_locally_load_settings_and_submit(self):
        from dart_web import main
        import flet as ft

        class Page:
            session_id = "operator"
            route = "/"
            def __init__(self):
                self.controls = []
            def add(self, *controls):
                self.controls.extend(controls)
            def update(self):
                pass
            def run_task(self, function):
                return SimpleNamespace(cancel=lambda: None)
            def go(self, route):
                self.route = route
                self.on_route_change(None)

        page = Page()
        main(page, self.service)
        def control(kind, **attributes):
            return next(item for item in page.controls if isinstance(item, kind) and
                        all(getattr(item, key) == value for key, value in attributes.items()))
        export = control(ft.ElevatedButton, text="Export CSV")
        export.on_click(None)
        notice = page.controls[page.controls.index(export) + 1]
        self.assertIn("absolute", notice.value)
        control(ft.TextField, label="Working Project (Existing Private Server Directory)").value = str(self.work)
        control(ft.ElevatedButton, text="Load This Project's Settings").on_click(None)
        self.assertEqual("test", control(ft.TextField, label="Collection-ID (Collection-Specific; Required)").value)
        export.on_click(None)
        self.service._thread.join(timeout=10)
        self.assertEqual("succeeded", self.service.jobs()[0]["state"])
        self.assertIn("/jobs/", page.route)
        self.assertFalse(control(ft.Checkbox, label="Authorize Azure Uploads For This Next Job").value)

    def test_job_snapshot_excludes_credentials_and_contains_effective_settings(self):
        job = self.export()
        snapshot = json.loads(Path(job["settings_snapshot"]).read_text())
        self.assertEqual("test", snapshot["collection-id"])
        self.assertEqual(str(self.core), snapshot["core_metadata_csv"])
        self.assertNotIn("azure_connection_string", snapshot)

    def test_real_managed_headless_entry_point_persists_success(self):
        env_file = self.root / "dart.env"
        env_file.write_text(f"DART_CONFIG_DIR={self.config}\nDART_DATA_DIR={self.data}\n"
                            "DART_SOURCE_ROOTS='[]'\nDART_AZURE_CONNECTION_STRING=\n")
        inputs = self.root / "inputs.json"
        atomic_json(inputs, dict(working_dir=str(self.work), input_dir=str(self.source),
                                 allow_uploads=False, overwrite=False))
        self.service.close()
        result = subprocess.run([sys.executable, "-m", "dart_linux", "--env-file", str(env_file),
                                 "--job", "export", "--inputs", str(inputs)],
                                cwd=ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("Evidence:", result.stdout)
        self.service = JobService(self.storage)
        self.service.claim("operator")
        self.assertEqual("succeeded", self.service.jobs()[0]["state"])


@unittest.skipUnless(os.name == "posix", "Managed Linux/browser storage requires POSIX")
class PureTests(unittest.TestCase):
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
        fingerprint = hashlib.sha256(ast.dump(ast.Module(body=after.body[1:], type_ignores=[])).encode()).hexdigest()
        # Original processing body at 95d07cd, excluding docstring indentation.
        self.assertEqual("3f5a613e25f7f88ae694c4bf2010d67abc39272c54b8a4b8b19f4c7a56850cc1", fingerprint)

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
