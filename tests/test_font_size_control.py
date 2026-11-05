import gc
import json
import logging
import tempfile
import unittest
import weakref
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import flet as ft

import app
from font_size_control import FontSizeController


class FontSizeControllerTests(unittest.TestCase):
    def setUp(self):
        self.page = Mock(spec=ft.Page)
        self.page.theme = None
        self.page.dark_theme = None
        self.save = Mock()

    def controller(self, saved="100"):
        return FontSizeController(
            self.page, load_percent=lambda: saved, save_percent=self.save,
        )

    @staticmethod
    def click(controller, text):
        next(control for control in controller.controls.controls
             if isinstance(control, ft.ElevatedButton) and control.text == text).on_click(None)

    def test_scaling_reset_limits_and_no_cumulative_rounding(self):
        fonts = self.controller()
        text = fonts.sized_text("Heading", size=24)
        self.assertIsNone(fonts.sized_text("Themed").size)
        self.click(fonts, "A+")
        self.assertAlmostEqual(26.4, text.size)
        self.save.assert_called_with("110")
        for _ in range(20):
            self.click(fonts, "A-")
        self.assertEqual(75, fonts.percent)
        self.assertTrue(fonts._smaller.disabled)
        self.assertEqual(18, text.size)
        for _ in range(20):
            self.click(fonts, "A+")
        self.assertEqual(200, fonts.percent)
        self.assertTrue(fonts._larger.disabled)
        self.assertEqual(48, text.size)
        self.click(fonts, "Reset")
        for _ in range(20):
            self.click(fonts, "A+")
            self.click(fonts, "A-")
        self.assertEqual(24, text.size)
        self.assertEqual(14, self.page.theme.text_theme.body_medium.size)

    def test_custom_light_and_dark_themes_preserved_without_mutation(self):
        light = ft.Theme(
            font_family="Example",
            color_scheme_seed=ft.Colors.GREEN,
            text_theme=ft.TextTheme(body_medium=ft.TextStyle(
                size=20, letter_spacing=2, color=ft.Colors.RED, italic=True, height=1.6,
            )),
        )
        dark = ft.Theme(text_theme=ft.TextTheme(body_medium=ft.TextStyle(size=18)))
        original = deepcopy(light)
        self.page.theme = light
        self.page.dark_theme = dark
        fonts = self.controller("150")
        self.assertEqual(original, light)
        self.assertEqual(18, dark.text_theme.body_medium.size)
        self.assertEqual(30, self.page.theme.text_theme.body_medium.size)
        self.assertEqual(27, self.page.dark_theme.text_theme.body_medium.size)
        self.assertEqual(3, self.page.theme.text_theme.body_medium.letter_spacing)
        self.assertTrue(self.page.theme.text_theme.body_medium.italic)
        self.assertEqual(ft.Colors.RED, self.page.theme.text_theme.body_medium.color)
        self.assertEqual(1.6, self.page.theme.text_theme.body_medium.height)
        self.assertEqual("Example", self.page.theme.font_family)
        self.click(fonts, "Reset")
        self.assertEqual(20, self.page.theme.text_theme.body_medium.size)

    def test_registration_is_idempotent_and_does_not_retain_closed_dialog_text(self):
        fonts = self.controller("150")
        text = fonts.sized_text("Dialog", size=18)
        fonts.register_text(text)
        self.assertEqual(27, text.size)
        ref = weakref.ref(text)
        del text
        gc.collect()
        self.assertIsNone(ref())
        with self.assertRaisesRegex(ValueError, "explicit Text.size"):
            fonts.register_text(ft.Text("Unsized"))

    def test_explicit_log_text_scales_and_is_released(self):
        fonts = self.controller("150")
        field = fonts.sized_text_field(text_size=11, value="Log", multiline=True, read_only=True)
        self.assertEqual(16.5, field.text_size)
        self.click(fonts, "A+")
        self.assertAlmostEqual(17.6, field.text_size)
        ref = weakref.ref(field)
        del field
        gc.collect()
        self.assertIsNone(ref())

    def test_dropdown_row_height_tracks_scale_without_accumulation(self):
        fonts = self.controller("150")
        dropdown = fonts.sized_dropdown(item_height=64, options=[])
        self.assertEqual(96, dropdown.item_height)
        self.click(fonts, "A+")
        self.assertEqual(102.4, dropdown.item_height)
        self.click(fonts, "Reset")
        self.assertEqual(64, dropdown.item_height)
        ref = weakref.ref(dropdown)
        del dropdown
        gc.collect()
        self.assertIsNone(ref())

    def test_invalid_saved_values_warn_and_fall_back(self):
        for value in (None, True, 100.5, "invalid", "74", "201"):
            with self.subTest(value=value), self.assertLogs("font_size_control", logging.WARNING):
                fonts = self.controller(value)
                self.assertEqual(100, fonts.percent)

    def test_no_op_at_limit_and_save_failure_does_not_change_display(self):
        fonts = self.controller("200")
        self.click(fonts, "A+")
        self.save.assert_not_called()
        self.page.update.assert_not_called()
        self.save.side_effect = OSError("Cannot save preference")
        with self.assertRaisesRegex(OSError, "Cannot save"):
            self.click(fonts, "Reset")
        self.assertEqual(200, fonts.percent)
        self.assertEqual(28, self.page.theme.text_theme.body_medium.size)


class DesktopFontSizeTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        for name, value in {
            "PERSISTENCE_FILE": self.root / "persistent.json",
            "DATA_DIR": self.root,
        }.items():
            self.stack.enter_context(patch.object(app, name, value))
        self.stack.enter_context(patch.object(app, "setup_desktop_logging"))
        self.stack.enter_context(patch.object(app, "setup_working_dir_logging"))
        self.stack.enter_context(patch.object(app, "load_app_settings",
                                            return_value=(dict(app.DEFAULT_APP_SETTINGS), "")))

    def start_page(self):
        page = Mock(spec=ft.Page)
        page.window = SimpleNamespace()
        page.overlay = []
        page.controls = []
        page.theme = None
        page.dark_theme = None
        page.add.side_effect = lambda *controls: page.controls.extend(controls)
        app.main(page)
        return page

    def walk(self, controls):
        for control in controls:
            yield control
            yield from self.walk(control._get_children())

    def find(self, page, kind, **attributes):
        return next(control for control in self.walk(page.controls + page.overlay)
                    if isinstance(control, kind)
                    and all(getattr(control, key) == value for key, value in attributes.items()))

    def click(self, page, text):
        self.find(page, ft.ElevatedButton, text=text).on_click(None)

    def test_all_explicit_text_is_routed_through_font_controller(self):
        import ast

        source = ast.parse(Path(app.__file__).read_text())
        main = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "main")
        unscaled = [node.lineno for node in ast.walk(main)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "ft"
                    and node.func.attr == "Text"]
        self.assertEqual([], unscaled)

    def test_main_window_scales_and_restores_saved_preference(self):
        page = self.start_page()
        title = self.find(page, ft.Text,
                          value=f"DART — Digital Asset Routing and Transformation — v{app.APP_VERSION}")
        self.click(page, "A+")
        self.assertAlmostEqual(26.4, title.size)
        for theme in (page.theme, page.dark_theme):
            self.assertAlmostEqual(15.4, theme.text_theme.body_medium.size)
            self.assertAlmostEqual(15.4, theme.text_theme.label_large.size)
        self.assertEqual("110", app.PersistentStorage().get_ui_state("font_scale_percent"))
        restarted = self.start_page()
        self.find(restarted, ft.Text, value="110%")
        self.click(restarted, "Reset")
        self.assertEqual("100", app.PersistentStorage().get_ui_state("font_scale_percent"))
        self.assertEqual(14, restarted.theme.text_theme.body_medium.size)

    def test_new_dialog_and_dynamic_status_follow_current_scale(self):
        app.PersistentStorage().set_ui_state("last_output_dir", str(self.root))
        app.PersistentStorage().set_ui_state("last_input_dir", str(self.root))
        page = self.start_page()
        self.click(page, "A+")
        selector = self.find(page, ft.Dropdown, label="Select Function to Execute")
        selector.on_change(SimpleNamespace(control=SimpleNamespace(value="function_0_app_settings")))
        settings_text = self.find(page, ft.Text, value="Edit app settings and save them to the working folder.")
        self.assertAlmostEqual(14.3, settings_text.size)
        self.click(page, "A+")
        self.assertAlmostEqual(15.6, settings_text.size)
        selector.on_change(SimpleNamespace(control=SimpleNamespace(value="function_9_system_info")))
        self.assertTrue(page.overlay[-1].open)
        status = self.find(page, ft.Text, value="Displayed system information")
        self.assertAlmostEqual(16.8, status.size)
        self.click(page, "A+")
        self.assertAlmostEqual(18.2, status.size)
        saved = json.loads(app.PERSISTENCE_FILE.read_text())
        self.assertEqual(str(self.root), saved["ui_state"]["last_output_dir"])
        self.assertEqual(str(self.root), saved["ui_state"]["last_input_dir"])
        self.assertEqual("130", saved["ui_state"]["font_scale_percent"])
        self.assertEqual(1, saved["function_usage"]["App Settings"]["count"])

    def test_functions_selector_fits_layout_scales_options_and_resets_after_execution(self):
        page = self.start_page()
        selector = self.find(page, ft.Dropdown, label="Select Function to Execute")
        self.assertIsNone(selector.width)
        self.assertTrue(selector.expand)
        self.assertTrue(selector.options_fill_horizontally)
        for _ in range(10):
            self.click(page, "A+")
        self.assertEqual(128, selector.item_height)
        for option in selector.options:
            self.assertEqual(32, option.content.size)
            self.assertEqual(2, option.content.max_lines)
            self.assertEqual(ft.TextOverflow.ELLIPSIS, option.content.overflow)
            self.assertEqual(option.text, option.content.tooltip)
        selector.value = "function_9_system_info"
        selector.on_change(SimpleNamespace(control=selector))
        self.assertEqual("", selector.value)
        self.assertTrue(page.overlay[-1].open)
        for option in selector.options:
            self.assertEqual(32, option.content.size)
        selector.value = "function_9_system_info"
        selector.on_change(SimpleNamespace(control=selector))
        self.assertEqual("", selector.value)
        self.assertEqual(2, app.PersistentStorage().data["function_usage"]["Function 9"]["count"])
        self.click(page, "Reset")
        self.assertEqual(64, selector.item_height)
        self.assertTrue(all(option.content.size == 16 for option in selector.options))

    def test_function_header_keeps_actions_together_and_flexes_description(self):
        page = self.start_page()
        rows = [control for control in self.walk(page.controls) if isinstance(control, ft.Row)]
        header = next(row for row in rows
                      if any(isinstance(child, ft.Text) and child.value == "Functions"
                             for child in row.controls))
        self.assertFalse(header.wrap)
        description = next(child for child in header.controls
                           if isinstance(child, ft.Text) and child.value.startswith("- Select"))
        self.assertTrue(description.expand)
        self.assertEqual(2, description.max_lines)
        actions = next(child for child in header.controls if isinstance(child, ft.Row))
        self.assertFalse(actions.wrap)
        self.assertTrue(actions.tight)
        self.assertEqual("Help Mode", actions.controls[0].label)
        self.assertEqual("🛑 Kill Switch", actions.controls[1].text)
        self.click(page, "A+")
        self.assertFalse(header.wrap or actions.wrap)


if __name__ == "__main__":
    unittest.main()
