import copy
import argparse
import csv
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.accept_headless_batch import ReviewRequired, accept_core, run, sha, table, validate


def content(rows):
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=[
        "objectid", "original_file_name", "parentid", "title",
        "object_location", "image_small", "image_thumb",
    ])
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode()


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(
            objectid="demo_dg_123", original_file_name="test.pdf", parentid="", title="Test",
            object_location="https://digitalgrinnell.blob.core.windows.net/objs/demo/demo_dg_123.pdf",
            image_small="https://digitalgrinnell.blob.core.windows.net/smalls/demo/demo_dg_123_SMALL.jpg",
            image_thumb="https://digitalgrinnell.blob.core.windows.net/thumbs/demo/demo_dg_123_TN.jpg",
        )
        self.manifest = dict(rows=1, warnings=[], id_conflicts=[], derivatives_local_only=False,
                             core_snapshot_sha256=sha(content([])),
                             gems_backfill=dict(matched_rows=1, gems_rows=1,
                                                unmatched_dart_rows=[], gems_duplicate_names=[]))
        self.evidence = dict(
            source="/data/run/objects", azure_path="/objs/demo", gems_names=["test.pdf"],
            inventory=dict(source_files=1, source_bytes=50, eligible_assets=1, excluded_files=[]),
            files=[dict(path="/data/run/objects/test.pdf", size=50, eligible=True)],
            analysis=dict(objects=[dict(objectid="demo_dg_123", filepath="/data/run/objects/test.pdf",
                                       parentid=None)], parents=[]),
        )

    def validate(self, rows=None):
        return validate(content(rows or [self.row]), self.manifest, self.evidence, "demo")

    def test_exact_new_records_pass(self):
        self.assertEqual(self.validate()["rows"], 1)

    def test_documented_unsupported_file_allowed(self):
        self.evidence["files"].append(dict(path="/data/run/objects/extra.bin", size=2, eligible=False))
        self.evidence["inventory"].update(source_files=2, source_bytes=52, excluded_files=["extra.bin"])
        self.evidence["gems_names"].append("extra.bin")
        self.manifest["gems_backfill"]["gems_rows"] = 2
        self.assertEqual(self.validate()["excluded_gems_names"], ["extra.bin"])

    def test_missing_gems_parent_blocks(self):
        self.evidence["gems_names"].append("_missing.pdf")
        self.manifest["gems_backfill"]["gems_rows"] = 2
        with self.assertRaisesRegex(ReviewRequired, "Unexplained"):
            self.validate()

    def test_changed_inventory_blocks(self):
        self.evidence["files"][0]["size"] = 51
        with self.assertRaisesRegex(ReviewRequired, "inventory"):
            self.validate()

    def test_warnings_unmatched_and_duplicate_ids_block(self):
        for change in (
            {"warnings": ["review"]}, {"id_conflicts": [{"objectid": "demo_dg_123"}]},
            {"derivatives_local_only": True},
            {"gems_backfill": dict(matched_rows=1, gems_rows=1, unmatched_dart_rows=["test.pdf"])},
        ):
            with self.subTest(change=change):
                manifest = copy.deepcopy(self.manifest)
                manifest.update(change)
                with self.assertRaises(ReviewRequired):
                    validate(content([self.row]), manifest, self.evidence, "demo")
        self.manifest["rows"] = 2
        self.manifest["gems_backfill"]["matched_rows"] = 2
        with self.assertRaisesRegex(ReviewRequired, "duplicate"):
            self.validate([self.row, self.row])

    def test_invalid_families_names_and_urls_block(self):
        for change in (
            {"parentid": "absent"}, {"objectid": "other_dg_123"},
            {"original_file_name": "../test.pdf"}, {"title": ""},
            {"object_location": "/local/file.pdf"}, {"image_thumb": ""},
            {"image_small": "https://digitalgrinnell.blob.core.windows.net/smalls/other/id.jpg"},
        ):
            with self.subTest(change=change), self.assertRaises(ReviewRequired):
                self.validate([dict(self.row, **change)])

    def test_unknown_analysis_id_blocks(self):
        self.evidence["analysis"]["objects"][0]["objectid"] = "demo_dg_124"
        with self.assertRaisesRegex(ReviewRequired, "analyzed"):
            self.validate()

    def test_malformed_csv_blocks(self):
        with self.assertRaises(ReviewRequired):
            table(b"a,a\n1,2\n")
        with self.assertRaises(ReviewRequired):
            table(b"a,b\n1,2,3\n")

    def test_backup_write_and_identical_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            core = root / "demo.csv"
            before, after = content([]), content([self.row])
            core.write_bytes(before)
            self.assertEqual(accept_core(core, after, self.manifest, root), "written")
            self.assertEqual(core.read_bytes(), after)
            self.assertEqual((root / f"core-before-{sha(before)}.csv").read_bytes(), before)
            self.assertEqual(accept_core(core, after, self.manifest, root), "already_identical")

    def test_populated_or_stale_core_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            core = root / "demo.csv"
            for before in (content([dict(self.row, title="Existing")]), content([]) + b"\n"):
                core.write_bytes(before)
                with self.assertRaises(ReviewRequired):
                    accept_core(core, content([self.row]), self.manifest, root)
                self.assertEqual(core.read_bytes(), before)

    def test_concurrent_core_edit_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            core = root / "demo.csv"
            core.write_bytes(content([]))
            original = Path.read_bytes
            reads = 0

            def read(path):
                nonlocal reads
                if path == core:
                    reads += 1
                    if reads == 2:
                        core.write_bytes(b"edited")
                return original(path)

            with patch.object(Path, "read_bytes", read), self.assertRaisesRegex(ReviewRequired, "changed"):
                accept_core(core, content([self.row]), self.manifest, root)
            self.assertEqual(core.read_bytes(), b"edited")

    def test_batch_writes_pushes_builds_and_recovers_build_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            show, work = root / "show", root / "work"
            core = show / "collections/demo/_data/demo_metadata.csv"
            core.parent.mkdir(parents=True)
            core.write_bytes(content([]))
            after = content([self.row])
            self.manifest["csv_sha256"] = sha(after)
            self.evidence.update(job_id="a" * 32, project="/data/dart/data/projects/demo",
                                 snapshot_sha256=self.manifest["core_snapshot_sha256"])
            args = argparse.Namespace(show_root=show, working_root=work, batch_id="b" * 32,
                                      host="host", inventory="/inventory.json", apply=True, build=True)
            pushes = []

            def remote(_host, request):
                if request["action"] == "summary":
                    return dict(summary=dict(id=args.batch_id, state="succeeded"),
                                queue=dict(collections=[dict(collection_id="demo", allow_uploads=True,
                                                             overwrite=False)]))
                if request["action"] == "evidence":
                    return self.evidence
                pushes.append(request)
                self.evidence["snapshot_sha256"] = sha(request["content"].encode())
                return dict(sha256=self.evidence["snapshot_sha256"])

            def pull(_host, _project, _job, directory, **_kwargs):
                export, manifest = directory / "export.csv", directory / "manifest.json"
                export.write_bytes(after)
                manifest.write_text(json.dumps(self.manifest))
                return dict(csv=str(export), manifest=str(manifest))

            def build(*_args, **_kwargs):
                site = show / "_site/demo"
                site.mkdir(parents=True)
                for name in ("index.html", "browse.html"):
                    (site / name).write_text("built")

            with patch("scripts.accept_headless_batch.remote", side_effect=remote), \
                    patch("scripts.accept_headless_batch.dart_handoff.pull_package", side_effect=pull), \
                    patch("scripts.accept_headless_batch.check_show_config"), \
                    patch("scripts.accept_headless_batch.subprocess.run") as runner:
                args.apply = args.build = False
                self.assertEqual(run(args), 0)
                self.assertEqual(core.read_bytes(), content([]))
                self.assertEqual(pushes, [])
                runner.assert_not_called()
                args.apply = args.build = True
                # The core and snapshot persist if the later build fails.
                runner.side_effect = subprocess.CalledProcessError(1, ["rake"])
                self.assertEqual(run(args), 1)
                self.assertEqual(core.read_bytes(), after)
                runner.side_effect = build
                self.assertEqual(run(args), 0)
                summary = json.loads((work / ".DART-working-directory" /
                                      f"accept-{args.batch_id}/summary.json").read_text())
                self.assertEqual(summary["collections"][0]["core_write"], "already_identical")
                self.assertEqual(summary["collections"][0]["state"], "succeeded")
                self.assertEqual(len(pushes), 2)


if __name__ == "__main__":
    unittest.main()
