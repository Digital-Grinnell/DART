from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image

from dart_cleanup import cleanup_derivatives
from dart_service import JobService
from dart_storage import Storage, atomic_json
from dart_workflows import digest, project_settings, read_csv, write_csv


@unittest.skipUnless(os.name == "posix", "Managed cleanup requires POSIX")
class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.umask = os.umask(0o077)
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.config, self.data = self.root / "config", self.root / "data"
        for path in (self.config, self.data):
            path.mkdir(mode=0o700)
        self.storage = Storage(self.config, self.data)
        self.storage.initialize()
        self.work = self.storage.projects / "collection"
        self.source = self.storage.projects / "source"
        for path in (self.work, self.source):
            path.mkdir(mode=0o700)
        Image.new("RGB", (40, 20), "blue").save(self.source / "sample.jpg")
        self.core = self.work / "core-snapshot.csv"
        columns = ["objectid", "original_file_name", "title", "format", "display_template",
                   "object_location", "image_small", "image_thumb"]
        write_csv(self.core, columns, [])
        self.service = JobService(self.storage)
        self.service.claim("headless")
        self.service.configure("headless", str(self.work), {
            "collection-id": "test", "input_dir": str(self.source), "core_metadata_csv": str(self.core),
            "gems_metadata_csv": "", "azure_blob_storage_path": "/objs/test", "group_compound_objects": False,
            "create_multiple_objects": False, "process_OHM_data": False})
        self.network = patch("socket.socket.connect", side_effect=AssertionError("Tests prohibit real network access"))
        self.network.start()
        self.job_id = self.service.submit("headless", "prepare",
                                          dict(working_dir=str(self.work), input_dir=str(self.source)))
        self.service._thread.join(timeout=15)
        job = self.service.jobs()[0]
        self.assertEqual("succeeded", job["state"], job["message"])
        self.result = copy.deepcopy(job["result"])
        self.directory = Path(self.result["derivatives"]["derivatives"])
        self.files = sorted(self.directory.iterdir())
        self.export = Path(self.result["package"]) / "export.csv"
        self.manifest_path = Path(self.result["manifest"])
        columns, rows = read_csv(self.export)
        self.remote_bytes = {}
        self.blobs = {}
        for path in self.files:
            container = "smalls" if path.name.endswith("_SMALL.jpg") else "thumbs"
            blob = f"test/{path.name}"
            url = f"https://account.blob.core.windows.net/{container}/{blob}"
            self.remote_bytes[blob] = path.read_bytes()
            remote = MagicMock()
            remote.url = url
            remote.get_blob_properties.side_effect = lambda *, timeout, key=blob: SimpleNamespace(
                size=len(self.remote_bytes[key]), etag="verified-etag")
            remote.download_blob.side_effect = lambda *, etag, match_condition, timeout, key=blob: SimpleNamespace(
                chunks=lambda: iter([self.remote_bytes[key]]))
            self.blobs[(container, blob)] = remote
            rows[0]["image_small" if container == "smalls" else "image_thumb"] = url
        write_csv(self.export, columns, rows)
        manifest = json.loads(self.manifest_path.read_text())
        manifest.update(csv_sha256=digest(self.export), derivatives_local_only=False, warnings=[])
        atomic_json(self.manifest_path, manifest)
        self.result["derivatives"]["local_only"] = False
        self.service._update(self.job_id, inputs=dict(job["inputs"], allow_uploads=True), result=self.result)
        self.client = MagicMock()
        self.client.__enter__.return_value = self.client
        self.client.get_blob_client.side_effect = lambda *, container, blob: self.blobs[(container, blob)]
        self.azure = patch("dart_cleanup.BlobServiceClient.from_connection_string", return_value=self.client)
        self.azure.start()
        self.credentials = patch.dict(os.environ, {"DART_AZURE_CONNECTION_STRING": "test-private"})
        self.credentials.start()

    def tearDown(self):
        self.service.close()
        self.credentials.stop()
        self.azure.stop()
        self.network.stop()
        self.temporary.cleanup()
        os.umask(self.umask)

    def cleanup(self, **kwargs):
        return cleanup_derivatives(self.service, self.job_id, **kwargs)

    def test_preview_verifies_all_bytes_but_retains_files_and_records_private_receipt(self):
        receipt = self.cleanup()
        self.assertEqual("preview", receipt["mode"])
        self.assertEqual("succeeded", receipt["state"])
        self.assertEqual(sum(path.stat().st_size for path in self.files), receipt["bytes"])
        self.assertTrue(all(path.exists() for path in self.files))
        self.assertEqual(["verified", "verified"], [row["state"] for row in receipt["files"]])
        self.assertEqual(0, Path(receipt["receipt"]).stat().st_mode & 0o077)
        self.assertNotIn("test-private", Path(receipt["receipt"]).read_text())
        for remote in self.blobs.values():
            self.assertEqual("verified-etag", remote.download_blob.call_args.kwargs["etag"])

    def test_apply_removes_only_verified_derivatives_and_remains_available_below_reserve(self):
        protected = {self.core: self.core.read_bytes(), self.export: self.export.read_bytes(),
                     self.manifest_path: self.manifest_path.read_bytes(),
                     self.source / "sample.jpg": (self.source / "sample.jpg").read_bytes()}
        settings_before = project_settings(self.storage, str(self.work))
        self.storage.min_free_bytes = 10**30
        receipt = self.cleanup(apply=True)
        self.assertEqual(["removed", "removed"], [row["state"] for row in receipt["files"]])
        self.assertEqual([], list(self.directory.iterdir()))
        for path, content in protected.items():
            self.assertEqual(content, path.read_bytes())
        self.assertEqual(settings_before, project_settings(self.storage, str(self.work)))
        self.assertEqual("succeeded", self.service.jobs()[0]["state"])
        again = self.cleanup(apply=True)
        self.assertEqual(0, again["bytes"])

    def test_same_size_wrong_remote_bytes_prevent_all_removal(self):
        key = next(iter(self.remote_bytes))
        self.remote_bytes[key] = b"x" * len(self.remote_bytes[key])
        with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
            self.cleanup(apply=True)
        self.assertTrue(all(path.exists() for path in self.files))
        receipt = json.loads(next((self.storage.jobs / self.job_id).glob("cleanup-*.json")).read_text())
        self.assertEqual("failed", receipt["state"])

    def test_missing_blob_or_changed_etag_prevents_all_removal(self):
        from azure.core.exceptions import ResourceModifiedError, ResourceNotFoundError
        remote = next(iter(self.blobs.values()))
        for error in (ResourceModifiedError("ETag changed"), ResourceNotFoundError("Blob missing")):
            remote.download_blob.side_effect = error
            with self.assertRaises(RuntimeError):
                self.cleanup(apply=True)
            self.assertTrue(all(path.exists() for path in self.files))

    def test_remote_version_change_after_hashing_prevents_all_removal(self):
        remote = next(iter(self.blobs.values()))
        blob = remote.url.split("/smalls/", 1)[1]
        remote.get_blob_properties.side_effect = [
            SimpleNamespace(size=len(self.remote_bytes[blob]), etag="verified-etag"),
            SimpleNamespace(size=len(self.remote_bytes[blob]), etag="new-etag"),
        ]
        with self.assertRaisesRegex(RuntimeError, "changed after hashing"):
            self.cleanup(apply=True)
        self.assertTrue(all(path.exists() for path in self.files))

    def test_local_or_handoff_change_during_verification_prevents_all_removal(self):
        remote = list(self.blobs.values())[-1]

        def download(**_kwargs):
            self.files[0].write_bytes(b"changed")
            blob = remote.url.split("/thumbs/", 1)[-1]
            return SimpleNamespace(chunks=lambda: iter([self.remote_bytes[blob]]))

        remote.download_blob.side_effect = download
        with self.assertRaisesRegex(RuntimeError, "changed during verification"):
            self.cleanup(apply=True)
        self.assertTrue(all(path.exists() for path in self.files))

    def test_rehearsal_unsuccessful_job_and_bad_package_are_rejected(self):
        job = self.service.jobs()[0]
        self.service._update(self.job_id, inputs=dict(job["inputs"], allow_uploads=False))
        with self.assertRaisesRegex(ValueError, "upload consent"):
            self.cleanup(apply=True)
        self.service._update(self.job_id, inputs=job["inputs"], state="failed")
        with self.assertRaises(ValueError):
            self.cleanup(apply=True)
        self.service._update(self.job_id, state="succeeded")
        self.export.write_bytes(self.export.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "unchanged publishing handoff"):
            self.cleanup(apply=True)
        self.assertTrue(all(path.exists() for path in self.files))

    def test_alias_or_unrecognized_file_is_rejected_without_deletion(self):
        extra = self.directory / "unexpected.tmp"
        extra.write_bytes(b"preserve unknown partial output")
        with self.assertRaisesRegex(ValueError, "Unrecognized"):
            self.cleanup(apply=True)
        extra.unlink()
        path = self.files[0]
        original = path.read_bytes()
        path.unlink()
        path.symlink_to(self.source / "sample.jpg")
        with self.assertRaisesRegex(ValueError, "symlinked"):
            self.cleanup(apply=True)
        self.assertTrue(self.files[1].exists())
        self.assertTrue((self.source / "sample.jpg").exists())
        path.unlink()
        path.write_bytes(original)

    def test_wrong_azure_destination_and_missing_credential_are_rejected(self):
        next(iter(self.blobs.values())).url = "https://wrong-account.blob.core.windows.net/smalls/test/wrong.jpg"
        with self.assertRaisesRegex(RuntimeError, "configured Azure destination"):
            self.cleanup(apply=True)
        with patch.dict(os.environ, {"DART_AZURE_CONNECTION_STRING": ""}):
            with self.assertRaisesRegex(RuntimeError, "credential"):
                self.cleanup(apply=True)
        self.assertTrue(all(path.exists() for path in self.files))

    def test_cancelled_cleanup_persists_receipt_and_keeps_files(self):
        self.service._cancel.set()
        with self.assertRaisesRegex(RuntimeError, "Cancellation"):
            self.cleanup(apply=True)
        self.assertTrue(all(path.exists() for path in self.files))

    def test_receipt_write_failure_before_removal_keeps_files(self):
        from dart_storage import atomic_json as original

        def persist(path, value):
            if value["state"] == "verified":
                raise OSError("Receipt unavailable")
            return original(path, value)

        with patch("dart_cleanup.atomic_json", persist):
            with self.assertRaisesRegex(RuntimeError, "Receipt unavailable"):
                self.cleanup(apply=True)
        self.assertTrue(all(path.exists() for path in self.files))

    def test_partial_removal_is_recorded_and_remaining_files_can_be_retried(self):
        original = Path.unlink
        last = self.files[-1]

        def unlink(path, **kwargs):
            if path == last:
                raise OSError("Simulated removal failure")
            return original(path, **kwargs)

        with patch.object(Path, "unlink", unlink):
            with self.assertRaisesRegex(RuntimeError, "removal failure"):
                self.cleanup(apply=True)
        self.assertFalse(self.files[0].exists())
        self.assertTrue(last.exists())
        receipt = json.loads(next((self.storage.jobs / self.job_id).glob("cleanup-*.json")).read_text())
        self.assertEqual(["removed", "removing"], [row["state"] for row in receipt["files"]])
        retried = self.cleanup(apply=True)
        self.assertEqual(1, len(retried["files"]))
        self.assertFalse(last.exists())

    def test_cleanup_cli_requires_no_job_inputs_and_rejects_apply_for_other_modes(self):
        self.service.close()
        env = self.config / "dart.env"
        env.write_text(f"DART_CONFIG_DIR={self.config}\nDART_DATA_DIR={self.data}\nDART_SOURCE_ROOTS=[]\n")
        command = [sys.executable, "-m", "dart_linux", "--env-file", str(env)]
        root = Path(__file__).resolve().parents[1]
        for value in ("0", "-1", "nan", "inf", "1e308"):
            run = subprocess.run([*command, "--list-jobs", "--min-free-gib", value], cwd=root,
                                 capture_output=True, text=True, timeout=30)
            self.assertEqual(2, run.returncode, run.stderr)
        run = subprocess.run([*command, "--list-jobs", "--apply"], cwd=root,
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(2, run.returncode)
        run = subprocess.run([*command, "--cleanup-derivatives", self.job_id], cwd=root,
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(1, run.returncode)
        self.assertIn("credential", run.stderr)
        self.assertTrue(all(path.exists() for path in self.files))
        for path in self.files:
            path.unlink()
        run = subprocess.run([*command, "--cleanup-derivatives", self.job_id], cwd=root,
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(0, run.returncode, run.stderr)
        self.assertEqual("preview", json.loads(run.stdout)["mode"])
        self.assertEqual(0, json.loads(run.stdout)["bytes"])


if __name__ == "__main__":
    unittest.main()
