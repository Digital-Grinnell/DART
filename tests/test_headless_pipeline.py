import argparse
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
