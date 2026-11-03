import csv
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from operations.batches.oral_histories_2026_10_30.prepare_oral_history_batch import (
    convert_vtt,
    prepare_collection,
    run,
    transcript_plan,
    upload_transcript,
)


VTT = b"WEBVTT\n\n1\n00:00:01.900 --> 00:00:03.000 align:start\n<v Interviewer>Hello &amp; welcome.\nSecond line.</v>\n"


class OralHistoryTests(unittest.TestCase):
    def test_cues_preserve_text_voice_and_second_resolution(self):
        data, count, notices = convert_vtt(VTT)
        rows = list(csv.DictReader(io.StringIO(data.decode(), newline="")))
        self.assertEqual(count, 1)
        self.assertEqual(notices, [])
        self.assertEqual(rows, [dict(timestamp="00:00:01", speaker="Interviewer",
                                    words="Hello & welcome.\nSecond line.")])

    def test_comments_styles_and_inline_timestamps(self):
        content = (b"WEBVTT\n\nNOTE comment\nignored\n\nSTYLE\n::cue {color:red}\n\n"
                   b"00:02.000 --> 00:03.000\n<b>A</b><00:02.500> B\n")
        data, count, notices = convert_vtt(content)
        self.assertEqual(count, 1)
        self.assertIn(b"00:00:02,,A B", data)

    def test_invalid_or_empty_input_is_explicit(self):
        for content in (
            b"not VTT", b"WEBVTT\n\n", b"WEBVTT\n\n00:00.abc --> 00:01.000\nbad",
            b"WEBVTT\n\n00:01.000 --> 00:02.000\n<v Person></v>",
        ):
            with self.subTest(content=content), self.assertRaises(ValueError):
                convert_vtt(content)

    def test_source_timing_anomalies_are_retained_with_explicit_notices(self):
        data, count, notices = convert_vtt(
            b"WEBVTT\n\n00:00.000 --> 00:00.000\ntitle\n\n"
            b"60:21.159 --> 60:22.000\nlater\n\n00:01.000 --> 00:02.000\nearlier\n"
        )
        self.assertEqual(count, 3)
        self.assertEqual(len(notices), 2)
        self.assertIn(b"01:00:21,,later", data)
        self.assertLess(data.index(b"later"), data.index(b"earlier"))

    def test_empty_lead_cue_and_invalid_unused_end_do_not_discard_transcript(self):
        data, count, notices = convert_vtt(
            b"WEBVTT\n\n00:00.000 --> 00:00.000\n\n16:10.259 --> 00:00.-10\nwords\n"
        )
        self.assertEqual(count, 1)
        self.assertIn(b"00:16:10,,words", data)
        self.assertTrue(any("empty source cue omitted" in notice for notice in notices))
        self.assertTrue(any("invalid source end" in notice for notice in notices))

    def test_pairing_uses_only_unique_singleton_folders_and_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            for name in ("single", "double", "orphan", "unknown"):
                (source / name).mkdir()
            (source / "single/a.mp3").write_bytes(b"audio")
            (source / "single/a.vtt").write_bytes(VTT)
            (source / "double/b.mp3").write_bytes(b"audio")
            (source / "double/c.mp3").write_bytes(b"audio")
            (source / "double/b.vtt").write_bytes(VTT)
            (source / "orphan/d.vtt").write_bytes(VTT)
            (source / "unknown/e.mp3").write_bytes(b"audio")
            (source / "unknown/e.vtt").write_bytes(VTT)
            plans, exceptions = transcript_plan(source, [dict(original_file_name="a.mp3")])
            self.assertEqual([p["audio"] for p in plans], ["a.mp3"])
            self.assertEqual(len(exceptions), 3)
            plans, exceptions = transcript_plan(source, [
                dict(original_file_name="a.mp3"), dict(original_file_name="a.mp3"),
            ])
            self.assertEqual(plans, [])
            self.assertEqual(len(exceptions), 4)

    def test_existing_different_transcript_is_never_overwritten(self):
        from unittest.mock import Mock
        client = Mock()
        blob = client.get_blob_client.return_value
        blob.exists.return_value = True
        blob.download_blob.return_value.readall.return_value = b"different"
        with self.assertRaisesRegex(ValueError, "never overwritten"):
            upload_transcript(client, "demo", "a.csv", b"expected")
        blob.upload_blob.assert_not_called()

    def test_upload_and_anonymous_verification(self):
        from unittest.mock import Mock
        client = Mock()
        blob = client.get_blob_client.return_value
        blob.exists.return_value = False
        blob.url = "https://example.blob.core.windows.net/transcripts/demo/a.csv"
        with patch("operations.batches.oral_histories_2026_10_30."
                   "prepare_oral_history_batch.urlopen") as public:
            public.return_value.__enter__.return_value.read.return_value = b"expected"
            self.assertEqual(upload_transcript(client, "demo", "a.csv", b"expected"), blob.url)
        self.assertFalse(blob.upload_blob.call_args.kwargs["overwrite"])
        with patch("operations.batches.oral_histories_2026_10_30."
                   "prepare_oral_history_batch.urlopen") as public:
            public.return_value.__enter__.return_value.read.return_value = b"wrong"
            with self.assertRaisesRegex(ValueError, "Public transcript verification failed"):
                upload_transcript(client, "demo", "a.csv", b"expected")

    def test_prepared_sidecar_preserves_source_and_links_audio_and_single_audio_parent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "run/objects/item"
            source.mkdir(parents=True)
            (source / "a.mp3").write_bytes(b"audio")
            (source / "a.vtt").write_bytes(VTT)
            metadata = root / "run/collection_metadata.csv"
            original = ("objectid,original_file_name,parentid,title\n"
                        "parent,_a.mp3,,Parent\nchild,a.mp3,parent,Child\n").encode()
            metadata.write_bytes(original)
            objects = source.parent
            destination = root / "prepared/collection_metadata.csv"
            entry = dict(collection_id="demo", input_dir=str(objects),
                         setup=dict(gems_metadata_csv=str(destination)))
            inventory = dict(
                source_files=2, source_bytes=5 + len(VTT), excluded_files=["item/a.vtt"],
                input_sha256={str(metadata): hashlib.sha256(original).hexdigest(),
                              str(source / "a.vtt"): hashlib.sha256(VTT).hexdigest()},
            )
            url = "https://example.blob.core.windows.net/transcripts/demo/a_transcript.csv"
            with patch("operations.batches.oral_histories_2026_10_30."
                       "prepare_oral_history_batch.upload_transcript",
                       return_value=url):
                result = prepare_collection(None, entry, inventory)
            self.assertEqual(len(result["transcripts"]), 1)
            self.assertEqual(metadata.read_bytes(), original)
            with destination.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["object_transcript"] for row in rows], [url, url])
            self.assertEqual([row["objectid"] for row in rows], ["parent", "child"])
            (source / "a.vtt").write_bytes(VTT + b"changed")
            with self.assertRaisesRegex(ValueError, "fingerprints changed"):
                prepare_collection(None, entry, inventory)

    def test_wrapper_preserves_environment_and_continues_other_collections_after_transcript_failure(self):
        from dart_storage import Storage, atomic_json
        old_umask = os.umask(0o077)
        try:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                config, data = root / "config", root / "data"
                config.mkdir(mode=0o700)
                data.mkdir(mode=0o700)
                storage = Storage(config, data)
                storage.initialize()
                env = config / "dart.env"
                env.write_text("DART_SOURCE_ROOTS='[]'\nDART_AZURE_CONNECTION_STRING='test-only-value'\n")
                entries = []
                for slug in ("broken", "good"):
                    source = storage.projects / f"{slug}-source/objects"
                    source.mkdir(mode=0o700, parents=True)
                    entries.append(dict(
                        collection_id=slug, input_dir=str(source),
                        setup=dict(core_template=str(config / "template.csv"),
                                   gems_metadata_csv=str(storage.projects / f"prepared/{slug}/metadata.csv")),
                        allow_uploads=True, overwrite=False,
                    ))
                queue, inventory, plan, report = (config / name for name in
                                                   ("queue.json", "inventory.json", "plan.json", "report.json"))
                atomic_json(queue, dict(collections=entries))
                atomic_json(inventory, [dict(collection_id=slug) for slug in ("broken", "good")])
                atomic_json(plan, dict(queue=str(queue), inventory=str(inventory), report=str(report),
                                       name="test-oral", unavailable=["alumni-2020s"]))
                with patch("dart_storage.load_environment"), \
                        patch("dart_storage.Storage.from_environment", return_value=storage), \
                        patch.dict(os.environ, {"DART_AZURE_CONNECTION_STRING": "test-only-value"}), \
                        patch("azure.storage.blob.BlobServiceClient.from_connection_string"), \
                        patch("operations.batches.oral_histories_2026_10_30."
                              "prepare_oral_history_batch.prepare_collection",
                              side_effect=[ValueError("test upload failure"), dict(collection="good")]), \
                        patch("dart_batch.run_batch", return_value=1) as batch, \
                        patch("operations.batches.oral_histories_2026_10_30."
                              "prepare_oral_history_batch.signal.signal"):
                    self.assertEqual(run(str(plan)), 1)
                batch.assert_called_once()
                self.assertEqual([e["collection_id"] for e in batch.call_args.args[1]["collections"]],
                                 ["broken", "good"])
                results = json.loads(report.read_text())
                self.assertEqual(results["collections"][0]["error"], "test upload failure")
                self.assertEqual(results["collections"][1]["collection"], "good")
                self.assertEqual(results["unavailable"], ["alumni-2020s"])
                self.assertIn("DART_AZURE_CONNECTION_STRING='test-only-value'\n", env.read_text())
                self.assertEqual((config / "dart.env.before-test-oral").stat().st_mode & 0o077, 0)
        finally:
            os.umask(old_umask)


if __name__ == "__main__":
    unittest.main()
