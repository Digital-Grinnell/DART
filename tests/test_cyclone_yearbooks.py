import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.process_cyclone_yearbooks import main, sheet_record, staged_pdf
from scripts.finalize_cyclone_completed import completed_records


class StagedPdfTests(unittest.TestCase):
    def test_local_copy_survives_source_removal_and_is_cleaned(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "Cyclone2004.pdf"
            hidden = Path(root) / ".DART-working-directory"
            hidden.mkdir()
            content = b"PDF data" * 100
            source.write_bytes(content)
            with staged_pdf(source, hidden, len(content)) as local:
                self.assertTrue(local.is_relative_to(hidden))
                source.unlink()
                self.assertEqual(local.read_bytes(), content)
            self.assertFalse(local.exists())
            self.assertEqual(list(hidden.iterdir()), [])

    def test_read_failure_never_yields_and_cleans_partial_copy(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "Cyclone2004.pdf"
            hidden = Path(root) / ".DART-working-directory"
            hidden.mkdir()
            source.write_bytes(b"PDF")

            def failing_copy(reader, writer, length):
                writer.write(b"P")
                raise OSError(5, "Input/output error")

            with patch("scripts.process_cyclone_yearbooks.shutil.copyfileobj", side_effect=failing_copy):
                with self.assertRaisesRegex(OSError, "check the DGIngest mount/VPN"):
                    with staged_pdf(source, hidden, 3):
                        self.fail("Incomplete PDF must not reach the uploader")
            self.assertEqual(list(hidden.iterdir()), [])

    def test_low_disk_space_stops_before_copying(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "Cyclone2004.pdf"
            source.write_bytes(b"PDF")
            with patch("scripts.process_cyclone_yearbooks.shutil.disk_usage",
                       return_value=SimpleNamespace(free=1024**3)):
                with self.assertRaisesRegex(RuntimeError, "Local staging needs"):
                    with staged_pdf(source, Path(root), 3):
                        self.fail("Insufficient space must stop staging")

    def test_changed_source_size_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "Cyclone2004.pdf"
            source.write_bytes(b"changed")
            with self.assertRaisesRegex(RuntimeError, "Source size changed"):
                with staged_pdf(source, Path(root), 3):
                    self.fail("Changed source must not reach the uploader")

    def test_upload_error_cleans_local_copy(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "Cyclone2004.pdf"
            hidden = Path(root) / ".DART-working-directory"
            hidden.mkdir()
            source.write_bytes(b"PDF")
            with self.assertRaisesRegex(RuntimeError, "upload failed"):
                with staged_pdf(source, hidden, 3):
                    raise RuntimeError("upload failed")
            self.assertEqual(list(hidden.iterdir()), [])


class CompletedRecordsTests(unittest.TestCase):
    def test_completed_and_remaining_ids_are_disjoint_and_preserve_names(self):
        sheet, mappings, ledger = [], {}, {}
        for index in range(89):
            row = [""] * 54
            row[0], row[1], row[9], row[22] = (
                f"dg_{1000 + index}", f"Yearbook {1900 + index}",
                f"Grinnell_Cyclone_{1900 + index}.pdf", str(1900 + index))
            sheet.append(row)
            objectid = f"cyclone_{row[0]}"
            mappings[f"Cyclones/Cyclone{1900 + index}.pdf"] = objectid
            if index < 74:
                ledger[objectid] = dict(object_location="original", image_small="small", image_thumb="thumb")
        rows, remaining = completed_records(sheet, mappings, ledger)
        self.assertEqual(len(rows), 74)
        self.assertEqual(len(remaining), 15)
        self.assertFalse({row["objectid"] for row in rows} & set(remaining))
        self.assertEqual(rows[0]["original_file_name"], "Cyclone1900.pdf")
        self.assertEqual(rows[0]["identifier"], "dg_1000")
        self.assertEqual(rows[0]["type"], "Text")
        ledger.pop(next(iter(ledger)))
        with self.assertRaisesRegex(ValueError, "exactly 74"):
            completed_records(sheet, mappings, ledger)


class RemainingRunTests(unittest.TestCase):
    def test_selected_pdf_is_staged_uploaded_merged_and_not_repeated(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source, project = root / "source", root / "project"
            source.mkdir()
            hidden = project / ".DART-working-directory"
            hidden.mkdir(parents=True)
            sheet = []
            for index, year in enumerate((2004, 2005)):
                row = [""] * 54
                row[0], row[1], row[9], row[22] = (
                    f"dg_{1000 + index}", f"Yearbook {year}", f"Cyclone{year}.pdf", str(year))
                (source / row[9]).write_bytes(b"PDF")
                sheet.append(row)
            core = root / "core.csv"
            columns = list(sheet_record(sheet[0], sheet[0][9], "")) + [
                "object_location", "image_small", "image_thumb"]
            with core.open("w") as handle:
                csv.writer(handle).writerow(columns)
            settings = {"collection-id": "cyclone", "core_metadata_csv": str(core),
                        "file_to_id_map": {}, "azure_connection_string": "DefaultEndpointsProtocol=fake",
                        "azure_blob_storage_path": "/objs/cyclone"}
            (hidden / "dart_settings.json").write_text(json.dumps(settings))
            selection = hidden / "ids.json"
            selection.write_text(json.dumps(["cyclone_dg_1000"]))
            calls = []

            class FakeAzure:
                def __init__(self, *args):
                    pass

                def upload(self, kind, path, name, content_type):
                    self_path = Path(path)
                    if kind == "objs":
                        assert self_path.is_relative_to(hidden)
                        assert self_path.read_bytes() == b"PDF"
                    calls.append((kind, name))
                    return f"https://example.test/{kind}/{name}"

            def derivative(source, output, *args, **kwargs):
                Path(output).write_bytes(b"JPEG")
                return True, "created"

            fake_core = SimpleNamespace(
                APP_SETTINGS_FILENAME="dart_settings.json", decrypt_sensitive_settings=lambda value: value,
                is_protected_core_csv_name=lambda path: False, generate_pdf_derivative=derivative)
            argv = ["--source", str(source), "--project", str(project), "--only-ids", str(selection), "--apply"]
            with patch.dict("sys.modules", {"app": fake_core}), \
                    patch("scripts.process_cyclone_yearbooks.load_sheet", return_value=sheet), \
                    patch("scripts.process_cyclone_yearbooks.Azure", FakeAzure), \
                    patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(main(argv), 0)
                self.assertEqual(main(argv), 0)
            self.assertEqual(len(calls), 3)
            with core.open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["objectid"] for row in rows], ["cyclone_dg_1000"])
            self.assertEqual(list(hidden.glob("cyclone-stage-*")), [])
            saved = json.loads((hidden / "dart_settings.json").read_text())
            self.assertEqual(len(saved["file_to_id_map"]), 1)


if __name__ == "__main__":
    unittest.main()
