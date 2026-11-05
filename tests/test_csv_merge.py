import csv
import io
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import app
from dart_processing import (
    compare_metadata_rows,
    prepare_metadata_additions,
    require_unchanged_core_csv,
)


class CSVComparisonTests(unittest.TestCase):
    def test_shared_columns_only_with_full_additions_and_removals(self):
        old = [
            {"original_file_name": "same.jpg", "title": "Old",
             "WARNING - DO NOT PUBLISH": "review", "filepath": "/old"},
            {"original_file_name": "missing.jpg", "title": "Missing",
             "WARNING - DO NOT PUBLISH": "keep"},
        ]
        new = [
            {"original_file_name": "same.jpg", "title": "New", "iiif_manifest": "manifest"},
            {"original_file_name": "_two.jpg", "title": "Two", "iiif_manifest": "two"},
            {"original_file_name": "two.jpg", "title": "Child", "iiif_manifest": ""},
            {"original_file_name": "_one.jpg", "title": "One", "iiif_manifest": "one"},
            {"original_file_name": "one.jpg", "title": "Child", "iiif_manifest": ""},
        ]
        result = compare_metadata_rows(old, new)
        self.assertEqual([{"key": ["same.jpg"],
                           "fields": {"title": {"from": "Old", "to": "New"}}}], result["changed"])
        self.assertEqual(new[1:], result["added"])
        self.assertEqual(old[1:], result["removed"])
        self.assertEqual("/old", old[0]["filepath"])
        self.assertEqual("manifest", new[0]["iiif_manifest"])

    def test_both_reported_headers_work_when_shared_or_one_sided(self):
        for column in ("WARNING - DO NOT PUBLISH", "iiif_manifest"):
            base = {"original_file_name": "one.jpg", "title": "One"}
            extra = dict(base, **{column: "value"})
            for old, new in ((base, extra), (extra, base), (extra, extra)):
                with self.subTest(column=column, old=old, new=new):
                    self.assertEqual([], compare_metadata_rows([old], [new])["changed"])
            result = compare_metadata_rows([extra], [dict(extra, **{column: "changed"})])
            self.assertEqual({"from": "value", "to": "changed"}, result["changed"][0]["fields"][column])

    def test_empty_files_and_missing_match_key(self):
        row = {"original_file_name": "one.jpg", "title": "One"}
        self.assertEqual([row], compare_metadata_rows([], [row])["added"])
        self.assertEqual([row], compare_metadata_rows([row], [])["removed"])
        self.assertEqual([], compare_metadata_rows([], [])["changed"])
        with self.assertRaises(KeyError):
            compare_metadata_rows([{"title": "Missing key"}], [row])

    def test_additions_require_explicit_schema_choice(self):
        for choice in (None, "", "invalid"):
            with self.subTest(choice=choice), self.assertRaisesRegex(ValueError, "Choose whether"):
                prepare_metadata_additions(["original_file_name"], [], ["iiif_manifest"], choice)

    def test_additions_preserve_core_columns_or_extend_in_export_order(self):
        columns = ["original_file_name", "WARNING - DO NOT PUBLISH", "title"]
        row = {"original_file_name": "one.jpg", "title": "line\r\nbreak",
               "iiif_manifest": "manifest", "extra": "value"}
        for choice in ("keep", "extend"):
            with self.subTest(choice=choice):
                fields, rows = prepare_metadata_additions(columns, [row], ["iiif_manifest", "extra"], choice)
                self.assertEqual(columns + (["iiif_manifest", "extra"] if choice == "extend" else []), fields)
                self.assertEqual("", rows[0]["WARNING - DO NOT PUBLISH"])
                self.assertEqual("line\r\nbreak", rows[0]["title"])
                output = io.StringIO(newline="")
                writer = csv.DictWriter(output, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
                self.assertEqual(rows, list(csv.DictReader(io.StringIO(output.getvalue(), newline=""))))
        self.assertEqual("manifest", row["iiif_manifest"])
        self.assertEqual(3, len(columns))
        with self.assertRaisesRegex(ValueError, "Unreviewed columns"):
            prepare_metadata_additions(columns, [row], [], None)

    def test_core_changes_detected_by_content_not_timestamp(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "core.csv"
            original = b"original_file_name,title\r\none.jpg,One\r\n"
            path.write_bytes(original)
            require_unchanged_core_csv(path, original)
            for changed in (
                original.replace(b"One", b"Two"),
                original.replace(b"title", b"label"),
                original.replace(b"\r\n", b"\n"),
            ):
                path.write_bytes(changed)
                with self.assertRaisesRegex(ValueError, "changed since comparison"):
                    require_unchanged_core_csv(path, original)
                self.assertEqual(changed, path.read_bytes())


class DesktopCSVHandOffTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.core = self.root / "core.csv"
        self.work = self.root / ".DART-working-directory"
        self.work.mkdir()
        self.export = self.work / "DART_export_test.csv"
        self.fields = ["objectid", "original_file_name", "title", "WARNING - DO NOT PUBLISH"]
        self.old = {"objectid": "existing", "original_file_name": "old.jpg",
                    "title": "Keep\r\nthis", "WARNING - DO NOT PUBLISH": "review"}
        self.write_csv(self.core, self.fields, [self.old])
        self.write_csv(self.export, ["objectid", "original_file_name", "title", "iiif_manifest"], [
            {"objectid": "existing", "original_file_name": "old.jpg",
             "title": "Keep\r\nthis", "iiif_manifest": "existing-manifest"},
            {"objectid": "new", "original_file_name": "new.jpg",
             "title": "New", "iiif_manifest": "new-manifest"},
        ])
        self.original = self.core.read_bytes()
        self.page = MagicMock()
        self.page.theme = None
        self.page.dark_theme = None
        self.page.overlay = []
        preferences = MagicMock()
        preferences.get_ui_state.side_effect = lambda key, default="": {
            "last_output_dir": str(self.root), "last_input_dir": "",
        }.get(key, default)
        preferences.get_last_executed_function.return_value = ""
        settings = dict(app.DEFAULT_APP_SETTINGS, core_metadata_csv=str(self.core))
        for target, values in (
            ("PersistentStorage", {"return_value": preferences}),
            ("setup_desktop_logging", {}),
            ("setup_working_dir_logging", {}),
            ("load_app_settings", {"return_value": (settings, "")}),
        ):
            self.stack.enter_context(patch.object(app, target, **values))
        app.main(self.page)
        layout = self.page.add.call_args.args[0]
        self.selector = next(control for control in self.walk(layout)
                             if isinstance(control, app.ft.Dropdown)
                             and control.label == "Select Function to Execute")
        self.open_comparison()

    def open_comparison(self):
        self.selector.on_change(SimpleNamespace(control=SimpleNamespace(value="function_4_compare_merge")))
        self.click("Use Newest")
        self.click("Review & Merge Changes")

    @staticmethod
    def write_csv(path, fields, rows):
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    @classmethod
    def walk(cls, control):
        yield control
        for child in getattr(control, "controls", []) or []:
            yield from cls.walk(child)
        content = getattr(control, "content", None)
        if isinstance(content, app.ft.Control):
            yield from cls.walk(content)

    def click(self, text):
        dialog = self.page.overlay[-1]
        button = next(action for action in dialog.actions if action.text == text)
        button.on_click(None)

    def choose_and_merge(self, choice):
        self.click("Merge Selected Changes")
        dialog = self.page.overlay[-1]
        selector = next(control for control in self.walk(dialog)
                        if isinstance(control, app.ft.Dropdown))
        selector.value = choice
        self.click("Merge Changes")

    def test_keep_core_schema_preserves_old_cells_and_blanks_new_cells(self):
        self.choose_and_merge("keep")
        with self.core.open(newline="") as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(self.fields, reader.fieldnames)
            rows = list(reader)
        self.assertEqual(self.old, rows[0])
        self.assertEqual("", rows[1]["WARNING - DO NOT PUBLISH"])
        self.assertEqual("new", rows[1]["objectid"])
        backups = list(self.work.glob("core.csv.backup_*"))
        self.assertEqual(1, len(backups))
        self.assertEqual(self.original, backups[0].read_bytes())

    def test_extend_schema_imports_only_selected_new_record_values(self):
        self.choose_and_merge("extend")
        with self.core.open(newline="") as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(self.fields + ["iiif_manifest"], reader.fieldnames)
            rows = list(reader)
        self.assertEqual(dict(self.old, iiif_manifest=""), rows[0])
        self.assertEqual("new-manifest", rows[1]["iiif_manifest"])
        self.assertEqual("", rows[1]["WARNING - DO NOT PUBLISH"])

    def test_matching_schema_merges_shared_field_changes_without_a_column_decision(self):
        self.write_csv(self.export, self.fields, [dict(self.old, title="Updated")])
        self.open_comparison()
        title_checkbox = next(control for control in self.walk(self.page.overlay[-1])
                              if isinstance(control, app.ft.Checkbox) and control.label == "")
        self.assertFalse(title_checkbox.value)
        title_checkbox.value = True
        self.choose_and_merge(None)
        with self.core.open(newline="") as stream:
            self.assertEqual([dict(self.old, title="Updated")], list(csv.DictReader(stream)))

    def test_core_only_columns_and_data_loss_protection_survive_merge(self):
        fields = ["objectid", "original_file_name", "title"]
        self.write_csv(self.export, fields, [
            {"objectid": "existing", "original_file_name": "old.jpg", "title": ""},
            {"objectid": "new", "original_file_name": "new.jpg", "title": "New"},
        ])
        self.open_comparison()
        self.choose_and_merge(None)
        with self.core.open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(self.old, rows[0])
        self.assertEqual("", rows[1]["WARNING - DO NOT PUBLISH"])
        self.assertEqual("New", rows[1]["title"])

    def test_no_schema_decision_leaves_confirmation_open_and_core_untouched(self):
        self.choose_and_merge(None)
        self.assertTrue(self.page.overlay[-1].open)
        self.assertEqual(self.original, self.core.read_bytes())
        self.assertEqual([], list(self.work.glob("core.csv.backup_*")))

    def test_changed_core_refuses_merge_without_creating_backup(self):
        changed = self.original.replace(b"review", b"changed")
        self.core.write_bytes(changed)
        self.choose_and_merge("keep")
        self.assertEqual(changed, self.core.read_bytes())
        self.assertEqual([], list(self.work.glob("core.csv.backup_*")))

    def test_core_changed_during_write_is_not_replaced(self):
        changed = self.original.replace(b"review", b"changed")
        original_guard = app.require_unchanged_core_csv
        calls = 0

        def change_before_final_guard(path, compared_bytes):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.core.write_bytes(changed)
            original_guard(path, compared_bytes)

        with patch.object(app, "require_unchanged_core_csv", side_effect=change_before_final_guard):
            self.choose_and_merge("keep")
        self.assertEqual(2, calls)
        self.assertEqual(changed, self.core.read_bytes())
        self.assertEqual([self.core], list(self.root.glob("*.csv")))


if __name__ == "__main__":
    unittest.main()
