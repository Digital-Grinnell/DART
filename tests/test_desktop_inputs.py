import csv
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import app


class DesktopInputsTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        for folder in ("first", "second"):
            directory = self.inputs / folder
            directory.mkdir()
            (directory / f"{folder}.jpg").write_bytes(b"fixture")
        self.core = self.root / "core.csv"
        self.core.write_text("objectid,original_file_name,parentid,title,type,filepath\n")
        self.stack.enter_context(patch.object(app, "PERSISTENCE_FILE", self.root / "persistent.json"))
        self.stack.enter_context(patch.object(app, "setup_desktop_logging"))
        self.stack.enter_context(patch.object(app, "setup_working_dir_logging"))
        self.settings = dict(app.DEFAULT_APP_SETTINGS, core_metadata_csv=str(self.core),
                             **{"collection-id": "test", "create_multiple_objects": False})
        self.stack.enter_context(patch.object(app, "load_app_settings",
                                            side_effect=lambda _: (self.settings, "")))
        self.stack.enter_context(patch.object(app, "save_app_settings", return_value=(True, "saved")))
        preferences = app.PersistentStorage()
        preferences.set_ui_state("last_input_dir", str(self.inputs))
        preferences.set_ui_state("last_output_dir", str(self.root))

    def start_page(self, initially_unavailable=False):
        page = Mock(spec=app.ft.Page)
        page.window = SimpleNamespace()
        page.session = SimpleNamespace(generated_ids=set())
        page.overlay = []
        page.controls = []
        page.theme = None
        page.dark_theme = None
        page.add.side_effect = lambda *controls: page.controls.extend(controls)
        original_exists = Path.exists

        def exists(path):
            return False if initially_unavailable and path == self.inputs else original_exists(path)

        with patch.object(Path, "exists", exists):
            app.main(page)
        return page

    def walk(self, controls):
        for control in controls:
            yield control
            yield from self.walk(control._get_children())

    def execute(self, page, function):
        selector = next(control for control in self.walk(page.controls)
                        if isinstance(control, app.ft.Dropdown)
                        and control.label == "Select Function to Execute")
        selector.on_change(SimpleNamespace(control=SimpleNamespace(value=function)))

    def test_analysis_retries_saved_inputs_after_volume_becomes_available(self):
        page = self.start_page(initially_unavailable=True)
        with patch.object(app, "shared_group_objects_by_source_directory",
                          wraps=app.shared_group_objects_by_source_directory) as group:
            self.execute(page, "function_1_list_files")
        self.assertEqual(1, group.call_count)
        self.assertEqual(self.inputs, group.call_args.args[4])
        self.assertEqual(2, len(group.call_args.args[0]))
        self.assertEqual("Function 1: Analyze Digital Assets", page.overlay[-1].title.value)

    def test_export_retries_saved_inputs_after_volume_becomes_available(self):
        page = self.start_page(initially_unavailable=True)
        self.execute(page, "function_2_export_csv")
        exports = list((self.root / ".DART-working-directory").glob("DART_export_*.csv"))
        self.assertEqual(1, len(exports))
        with exports[0].open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        parents = [row for row in rows if row["type"] == "compound"]
        children = [row for row in rows if row["type"] == "child"]
        self.assertEqual(2, len(parents))
        self.assertEqual(2, len(children))
        self.assertEqual({row["objectid"] for row in parents}, {row["parentid"] for row in children})

    def test_missing_inputs_reports_configured_path_not_missing_selection(self):
        page = self.start_page()
        unavailable = self.root / "not-mounted"
        field = next(control for control in self.walk(page.controls)
                     if isinstance(control, app.ft.TextField) and control.label == "Inputs Folder")
        field.value = str(unavailable)
        for function in ("function_1_list_files", "function_2_export_csv"):
            with self.subTest(function=function):
                self.execute(page, function)
                texts = [control.value for control in self.walk(page.controls)
                         if isinstance(control, app.ft.Text)]
                self.assertIn(f"Error: Inputs Folder is unavailable or not a directory: {unavailable}", texts)

    def test_selected_file_export_does_not_require_inputs_folder(self):
        preferences = app.PersistentStorage()
        preferences.set_ui_state("last_input_dir", "")
        preferences.set_ui_state("last_file", str(self.inputs / "first" / "first.jpg"))
        self.settings["group_by_source_directory"] = False
        self.settings["group_compound_objects"] = False
        page = self.start_page()
        self.execute(page, "function_2_export_csv")
        export = next((self.root / ".DART-working-directory").glob("DART_export_*.csv"))
        with export.open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(["first.jpg"], [row["original_file_name"] for row in rows])

    def test_non_directory_and_access_errors_are_reported(self):
        page = self.start_page()
        field = next(control for control in self.walk(page.controls)
                     if isinstance(control, app.ft.TextField) and control.label == "Inputs Folder")
        field.value = str(self.core)
        self.execute(page, "function_1_list_files")
        texts = [control.value for control in self.walk(page.controls)
                 if isinstance(control, app.ft.Text)]
        self.assertIn(f"Error: Inputs Folder is unavailable or not a directory: {self.core}", texts)
        field.value = str(self.inputs)
        original_is_dir = Path.is_dir

        def is_dir(path):
            if path == self.inputs:
                raise PermissionError("Access denied")
            return original_is_dir(path)

        with patch.object(Path, "is_dir", is_dir):
            self.execute(page, "function_1_list_files")
        texts = [control.value for control in self.walk(page.controls)
                 if isinstance(control, app.ft.Text)]
        self.assertIn(f"Error: Cannot access Inputs Folder {self.inputs}: Access denied", texts)


if __name__ == "__main__":
    unittest.main()
