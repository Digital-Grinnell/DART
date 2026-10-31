import argparse
import fcntl
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.run_headless_pipeline import run


class PipelineTests(unittest.TestCase):
    def test_completed_batch_resumes_without_launch_and_passes_catalog_options(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            args = argparse.Namespace(
                host="host", queue="/data/dart/config/demo.json", inventory="/data/dart/config/inventory.json",
                unit="dart-demo", collections=["demo"], show_root=root, apply=True,
                catalog_group="Batch of 3", catalog_progress="DART Complete, Pending Review of 3",
            )
            response = dict(queue=dict(collections=[dict(collection_id="demo", allow_uploads=True, overwrite=False)]),
                            summary=dict(id="a" * 32, state="succeeded", collections=[]))
            with patch("scripts.run_headless_pipeline.Path.home", return_value=root), \
                    patch("scripts.run_headless_pipeline.status", return_value=response), \
                    patch("scripts.run_headless_pipeline.launch") as launch, \
                    patch("scripts.run_headless_pipeline.subprocess.run",
                          return_value=subprocess.CompletedProcess([], 0)) as command:
                self.assertEqual(run(args), 0)
                launch.assert_not_called()
                argv = command.call_args.args[0]
                self.assertIn("--catalog-status", argv)
                self.assertIn("published", argv)
                self.assertIn("Batch of 3", argv)
                result = json.loads((root / "DART-projects/.DART-working-directory/pipeline-dart-demo.json").read_text())
                self.assertEqual(result["state"], "completed")
                command.return_value = subprocess.CompletedProcess([], 1)
                self.assertEqual(run(args), 1)
                result = json.loads((root / "DART-projects/.DART-working-directory/pipeline-dart-demo.json").read_text())
                self.assertEqual(result["state"], "needs_attention")
                self.assertEqual(result["exit_code"], 1)

    def test_new_pipeline_previews_without_launch_and_apply_runs_to_acceptance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            core = root / "collections/demo/_data/demo_metadata.csv"
            core.parent.mkdir(parents=True)
            core.write_text("objectid,original_file_name\n")
            args = argparse.Namespace(
                host="host", queue="/data/dart/config/demo.json", inventory="/data/dart/config/inventory.json",
                unit="dart-demo", collections=["demo"], show_root=root, apply=False,
                catalog_group="Batch of 3", catalog_progress="Pending Review",
            )
            queue = dict(collections=[dict(collection_id="demo", allow_uploads=True, overwrite=False)])
            initial = dict(queue=queue, summary=None)
            finished = dict(queue=queue, summary=dict(id="b" * 32, state="failed", collections=[]))
            with patch("scripts.run_headless_pipeline.Path.home", return_value=root), \
                    patch("scripts.run_headless_pipeline.status", side_effect=[initial, initial, finished]), \
                    patch("scripts.run_headless_pipeline.dart_handoff._ssh", return_value=b"inactive\n"), \
                    patch("scripts.accept_headless_batch.check_show_config"), \
                    patch("scripts.run_headless_pipeline.launch") as launch, \
                    patch("scripts.run_headless_pipeline.subprocess.run",
                          return_value=subprocess.CompletedProcess([], 0)) as command:
                self.assertEqual(run(args), 0)
                launch.assert_not_called()
                command.assert_not_called()
                args.apply = True
                self.assertEqual(run(args), 1)
                launch.assert_called_once()
                command.assert_called_once()

    def test_oral_history_pipeline_omits_catalog_options(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            args = argparse.Namespace(
                host="host", queue="/data/dart/config/demo.json", inventory="/data/dart/config/inventory.json",
                unit="dart-demo", collections=["demo"], show_root=root, apply=True,
                catalog_group=None, catalog_progress=None,
            )
            response = dict(queue=dict(collections=[dict(collection_id="demo", allow_uploads=True, overwrite=False)]),
                            summary=dict(id="c" * 32, state="succeeded", collections=[]))
            with patch("scripts.run_headless_pipeline.Path.home", return_value=root), \
                    patch("scripts.run_headless_pipeline.status", return_value=response), \
                    patch("scripts.run_headless_pipeline.launch") as launch, \
                    patch("scripts.run_headless_pipeline.subprocess.run",
                          return_value=subprocess.CompletedProcess([], 0)) as command:
                self.assertEqual(run(args), 0)
                launch.assert_not_called()
                self.assertNotIn("--catalog-status", command.call_args.args[0])

    def test_existing_active_service_is_monitored_without_duplicate_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            core = root / "collections/demo/_data/demo_metadata.csv"
            core.parent.mkdir(parents=True)
            core.write_text("objectid,original_file_name\n")
            args = argparse.Namespace(
                host="host", queue="/data/dart/config/demo.json", inventory="/data/dart/config/inventory.json",
                unit="dart-demo", collections=["demo"], show_root=root, apply=True,
                catalog_group=None, catalog_progress=None,
            )
            queue = dict(collections=[dict(collection_id="demo", allow_uploads=True, overwrite=False)])
            with patch("scripts.run_headless_pipeline.Path.home", return_value=root), \
                    patch("scripts.run_headless_pipeline.status", side_effect=[
                        dict(queue=queue, summary=None),
                        dict(queue=queue, summary=dict(id="d" * 32, state="succeeded", collections=[])),
                    ]), \
                    patch("scripts.run_headless_pipeline.dart_handoff._ssh", return_value=b"active\n"), \
                    patch("scripts.accept_headless_batch.check_show_config"), \
                    patch("scripts.run_headless_pipeline.launch") as launch, \
                    patch("scripts.run_headless_pipeline.subprocess.run",
                          return_value=subprocess.CompletedProcess([], 0)):
                self.assertEqual(run(args), 0)
                launch.assert_not_called()

    def test_two_oral_history_pipelines_cannot_overlap(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            work = root / "DART-projects/.DART-working-directory"
            work.mkdir(parents=True)
            args = argparse.Namespace(unit="dart-demo", oral_history_plan="plan")
            with (work / "oral-history-pipelines.lock").open("a") as lock, \
                    patch("scripts.run_headless_pipeline.Path.home", return_value=root):
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaisesRegex(RuntimeError, "sequentially"):
                    run(args)

    def test_queue_mismatch_stops_before_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            args = argparse.Namespace(host="host", queue="queue", unit="dart-demo", collections=["demo"], apply=True)
            with patch("scripts.run_headless_pipeline.Path.home", return_value=root), \
                    patch("scripts.run_headless_pipeline.status", return_value=dict(
                        queue=dict(collections=[dict(collection_id="other")]), summary=None)), \
                    patch("scripts.run_headless_pipeline.launch") as launch:
                with self.assertRaises(ValueError):
                    run(args)
                launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
