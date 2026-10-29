from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from dotenv import dotenv_values

from dart_storage import Storage
from scripts.recover_headless_project import main, recover, replacement_environment

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix", "Recovery uses POSIX storage and locks")
class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ)
        self.environment.start()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(self.environment.stop)
        self.root = Path(self.temporary.name).resolve()
        self.config, self.data, self.source, self.other = [
            self.root / name for name in ("config", "data", "source's run", "other")
        ]
        for path in (self.config, self.data, self.source, self.other):
            path.mkdir(mode=0o700)
        Storage(self.config, self.data).initialize()
        for path in (self.config, self.data):
            lock = path / ".dart-service.lock"
            lock.touch(mode=0o600)
        self.work = self.data / "projects/test"
        self.work.mkdir(mode=0o700)
        (self.source / "objects").mkdir(mode=0o700)
        self.gems = self.source / "collection_metadata.csv"
        self.gems.write_text("original_file_name,title\n")
        self.snapshot = self.work / "core-snapshot.csv"
        self.snapshot.write_text(
            "objectid,original_file_name,parentid,type,display_template,title,"
            "object_location,image_small,image_thumb\n"
        )
        self.snapshot.chmod(0o600)
        self.env = self.config / "dart.env"
        self.prior_sources = [{"path": str(self.other), "mount": "/"}]
        self.env.write_text(
            f"# Keep this comment\nDART_CONFIG_DIR={self.config}\nDART_DATA_DIR={self.data}\n"
            f"DART_SOURCE_ROOTS='{json.dumps(self.prior_sources)}'\n"
            "DART_AZURE_CONNECTION_STRING='private-test-value'\n"
        )
        self.env.chmod(0o600)
        self.inputs = self.config / "settings-test.json"
        self.inputs.write_text(json.dumps({
            "working_dir": str(self.work), "input_dir": str(self.source / "objects"),
            "collection-id": "test", "core_metadata_csv": str(self.snapshot),
            "gems_metadata_csv": str(self.gems), "azure_blob_storage_path": "/objs/test",
            "group_compound_objects": True, "create_multiple_objects": False,
            "process_OHM_data": False,
        }))
        self.inputs.chmod(0o600)
        self.args = argparse.Namespace(
            env_file=str(self.env), inputs=str(self.inputs), collection_id="test",
            source_root=str(self.source), source_mount="/", repo=str(ROOT), apply=False,
        )

    def contents(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def run_recovery(self):
        output = io.StringIO()
        with redirect_stdout(output):
            recover(self.args)
        self.assertNotIn("private-test-value", output.getvalue())
        return output.getvalue()

    def test_preview_changes_nothing(self):
        before = self.contents()
        with patch("scripts.recover_headless_project.subprocess.run") as run:
            output = self.run_recovery()
            run.assert_not_called()
        self.assertIn("PREVIEW ONLY", output)
        self.assertEqual(before, self.contents())

    def test_apply_configures_only_preserves_sources_and_is_repeatable(self):
        before_env, before_snapshot = self.env.read_bytes(), self.snapshot.read_bytes()
        self.args.apply = True
        real_run = subprocess.run
        with patch("scripts.recover_headless_project.subprocess.run", wraps=real_run) as run:
            self.assertIn("RECOVERED", self.run_recovery())
            command = run.call_args.args[0]
            self.assertIn("--configure", command)
            self.assertNotIn("--job", command)
        values = dotenv_values(self.env, interpolate=False)
        self.assertEqual([*self.prior_sources, {"path": str(self.source), "mount": "/"}],
                         json.loads(values["DART_SOURCE_ROOTS"]))
        self.assertEqual("private-test-value", values["DART_AZURE_CONNECTION_STRING"])
        self.assertTrue(self.env.read_text().startswith("# Keep this comment\n"))
        backups = list((self.work / ".DART-working-directory/recovery").iterdir())
        self.assertEqual(1, len(backups))
        self.assertEqual(before_env, backups[0].read_bytes())
        self.assertEqual(0o600, backups[0].stat().st_mode & 0o777)
        self.assertEqual(0o600, self.env.stat().st_mode & 0o777)
        self.assertEqual(before_snapshot, self.snapshot.read_bytes())
        self.assertEqual([], list((self.data / "jobs").iterdir()))
        after = self.contents()
        self.assertIn("already covered", self.run_recovery())
        self.assertEqual(after, self.contents())

    def test_apply_refuses_ids_without_changing_files(self):
        hidden = self.work / ".DART-working-directory"
        hidden.mkdir(mode=0o700)
        settings = hidden / "dart_settings.json"
        settings.write_text(json.dumps({"file_to_id_map": {"file.jpg": "test_dg_1"}}))
        settings.chmod(0o600)
        self.args.apply = True
        before = self.contents()
        with self.assertRaisesRegex(ValueError, "Recovery refused"):
            self.run_recovery()
        self.assertEqual(before, self.contents())

    def test_apply_refuses_job_evidence_without_changing_files(self):
        directory = self.data / "jobs" / ("a" * 32)
        directory.mkdir(mode=0o700)
        job = directory / "job.json"
        job.write_text(json.dumps({"id": directory.name, "state": "failed",
                                   "kind": "prepare", "inputs": {"working_dir": str(self.work)}}))
        job.chmod(0o600)
        self.args.apply = True
        before = self.contents()
        with self.assertRaisesRegex(ValueError, "Recovery refused"):
            self.run_recovery()
        self.assertEqual(before, self.contents())

    def test_apply_refuses_another_collections_stale_active_job(self):
        directory = self.data / "jobs" / ("a" * 32)
        directory.mkdir(mode=0o700)
        job = directory / "job.json"
        job.write_text(json.dumps({"state": "running", "inputs": {"working_dir": "/other"}}))
        job.chmod(0o600)
        self.args.apply = True
        before = self.contents()
        with self.assertRaisesRegex(ValueError, "Recovery refused"):
            self.run_recovery()
        self.assertEqual(before, self.contents())

    def test_apply_refuses_live_writer(self):
        import fcntl
        self.args.apply = True
        before = self.contents()
        with (self.data / ".dart-service.lock").open("rb") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, "writer is active"):
                self.run_recovery()
        self.assertEqual(before, self.contents())

    def test_apply_refuses_sources_outside_approved_run(self):
        self.args.source_root = str(self.other)
        self.args.apply = True
        before = self.contents()
        with self.assertRaisesRegex(ValueError, "input_dir must exist beneath"):
            self.run_recovery()
        self.assertEqual(before, self.contents())

    def test_environment_replacement_rejects_duplicate_and_multiline_values(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            replacement_environment("DART_SOURCE_ROOTS='[]'\nDART_SOURCE_ROOTS='[]'\n", [])
        with self.assertRaisesRegex(ValueError, "other private"):
            replacement_environment("DART_SOURCE_ROOTS='[\n]'\n", [])

    def test_mac_forwarding_quotes_paths_and_requires_explicit_apply(self):
        argv = ["recover", "test", "--host", "sysadmin@example.test",
                "--repo", str(ROOT), "--env-file", str(self.env), "--inputs", str(self.inputs),
                "--source-root", str(self.source), "--source-mount", "/"]
        for apply in (False, True):
            with self.subTest(apply=apply), patch.object(sys, "argv", argv + (["--apply"] if apply else [])):
                with patch("scripts.recover_headless_project.subprocess.run",
                           return_value=subprocess.CompletedProcess([], 0)) as run:
                    self.assertEqual(0, main())
                command = run.call_args.args[0]
                self.assertEqual("ssh", command[0])
                remote = shlex.split(command[-1])
                self.assertIn(str(self.source), remote)
                self.assertEqual(apply, "--apply" in remote)
                self.assertNotIn("--host", remote)
                self.assertIn(b"def recover", run.call_args.kwargs["input"])


if __name__ == "__main__":
    unittest.main()
