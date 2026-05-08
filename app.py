"""
FLAT - Flet Layout Application Template
A template Flet desktop application with persistent settings, logging,
function management, and help documentation system based on OHM's proven UI.
"""

import flet as ft
import os
import getpass
import logging
import json
import platform
import socket
from datetime import datetime
from pathlib import Path

# Configure logging
DATA_DIR = Path.home() / "FLAT-data"
os.makedirs(DATA_DIR / "logfiles", exist_ok=True)
log_filename = DATA_DIR / "logfiles" / f"flat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

file_handler = logging.FileHandler(log_filename)
file_handler.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])
logger = logging.getLogger(__name__)

# Reduce Flet's logging verbosity
logging.getLogger("flet").setLevel(logging.WARNING)
logging.getLogger("flet_core").setLevel(logging.WARNING)
logging.getLogger("flet_desktop").setLevel(logging.WARNING)

# Persistent storage file
PERSISTENCE_FILE = DATA_DIR / "persistent.json"


class PersistentStorage:
    """Handle persistent storage of UI state and function usage."""

    def __init__(self):
        self.data = self.load()

    def load(self) -> dict:
        """Load persistent data from file."""
        try:
            if os.path.exists(PERSISTENCE_FILE):
                with open(PERSISTENCE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"Loaded persistent data from {PERSISTENCE_FILE}")
                return data
        except Exception as e:
            logger.warning(f"Could not load persistent data: {str(e)}")

        return {
            "ui_state": {
                "last_input_dir": "",
                "last_output_dir": "",
                "last_file": "",
                "window_left": None,
                "window_top": None,
            },
            "function_usage": {},
        }

    def save(self):
        """Save persistent data to file."""
        try:
            with open(PERSISTENCE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved persistent data to {PERSISTENCE_FILE}")
        except Exception as e:
            logger.error(f"Could not save persistent data: {str(e)}")

    def set_ui_state(self, field: str, value: str):
        """Update UI state field."""
        self.data["ui_state"][field] = value
        self.save()

    def get_ui_state(self, field: str, default: str = "") -> str:
        """Get UI state field."""
        return self.data["ui_state"].get(field, default)

    def record_function_usage(self, function_name: str):
        """Record that a function was used."""
        if function_name not in self.data["function_usage"]:
            self.data["function_usage"][function_name] = {"count": 0}

        self.data["function_usage"][function_name]["last_used"] = datetime.now().isoformat()
        self.data["function_usage"][function_name]["count"] = (
            self.data["function_usage"][function_name].get("count", 0) + 1
        )
        self.save()


def load_help_document(filename: str) -> str:
    """Load help documentation from markdown file."""
    try:
        help_path = Path(__file__).parent / filename
        if help_path.exists():
            return help_path.read_text(encoding="utf-8")
        else:
            return f"# Help Documentation Not Found\n\nCould not find {filename}"
    except Exception as e:
        logger.error(f"Error loading help document {filename}: {e}")
        return f"# Error Loading Help\n\n{str(e)}"


def main(page: ft.Page):
    page.title = "FLAT - Flet Layout Application Template"
    page.padding = 20
    page.window.width = 1050
    page.window.height = 900
    page.scroll = ft.ScrollMode.AUTO

    storage = PersistentStorage()
    logger.info("FLAT application started")

    # ------------------------------------------------------------------ helpers

    def add_log_message(text: str):
        """Prepend a timestamped line to the log output field."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        existing = log_output.value or ""
        log_output.value = f"[{timestamp}] {text}\n{existing}"
        page.update()

    def update_status(message: str, is_error: bool = False):
        """Update the status text field."""
        status_text.value = message
        status_text.color = ft.Colors.RED_700 if is_error else ft.Colors.BLACK
        add_log_message(message)
        page.update()

    def on_copy_status_click(e):
        """Copy status text to clipboard."""
        if status_text.value:
            page.set_clipboard(status_text.value)
            add_log_message("Status copied to clipboard")

    def on_copy_log_click(e):
        """Copy log output to clipboard."""
        if log_output.value:
            page.set_clipboard(log_output.value)
            add_log_message("Log output copied to clipboard")

    def on_clear_log_click(e):
        """Clear the log output."""
        log_output.value = ""
        page.update()
        logger.info("Log cleared")

    # ------------------------------------------------------------------ UI state

    current_directory = None
    input_dir = storage.get_ui_state("last_input_dir")
    if input_dir and Path(input_dir).exists():
        current_directory = Path(input_dir)

    dirs_expanded = True

    # ------------------------------------------------------------------ directory selection

    def on_input_dir_result(e: ft.FilePickerResultEvent):
        nonlocal current_directory
        if e.path:
            current_directory = Path(e.path)
            input_dir_field.value = str(current_directory)
            storage.set_ui_state("last_input_dir", str(current_directory))
            update_status(f"Input directory set: {current_directory.name}")
            page.update()

    def on_output_dir_result(e: ft.FilePickerResultEvent):
        if e.path:
            output_dir_field.value = e.path
            storage.set_ui_state("last_output_dir", e.path)
            update_status(f"Output directory set: {Path(e.path).name}")
            page.update()

    def on_file_result(e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            file_path = e.files[0].path
            file_field.value = file_path
            storage.set_ui_state("last_file", file_path)
            update_status(f"File selected: {Path(file_path).name}")
            page.update()

    input_dir_picker = ft.FilePicker(on_result=on_input_dir_result)
    output_dir_picker = ft.FilePicker(on_result=on_output_dir_result)
    file_picker = ft.FilePicker(on_result=on_file_result)

    page.overlay.extend([input_dir_picker, output_dir_picker, file_picker])

    # ------------------------------------------------------------------ function implementations

    def on_function_1_list_files(e):
        """Function 1: List all files in input directory."""
        storage.record_function_usage("Function 1")

        if not current_directory or not current_directory.exists():
            update_status("Error: Please select an input directory first", is_error=True)
            return

        files = list(current_directory.glob("*"))
        file_list = [f.name for f in files if f.is_file()]

        result_text = f"Found {len(file_list)} file(s) in {current_directory.name}:\n\n"
        result_text += "\n".join(f"• {name}" for name in sorted(file_list)) if file_list else "(No files found)"

        def close_dialog(e):
            dialog.open = False
            page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Function 1: List Files"),
            content=ft.Container(
                content=ft.Text(result_text, selectable=True),
                width=600,
                height=400,
            ),
            actions=[ft.TextButton("Close", on_click=close_dialog)],
        )

        page.overlay.append(dialog)
        dialog.open = True
        page.update()

        update_status(f"Listed {len(file_list)} file(s)")
        logger.info(f"Function 1: Listed {len(file_list)} files from {current_directory}")

    def on_function_2_count_files(e):
        """Function 2: Count files by extension."""
        storage.record_function_usage("Function 2")

        if not current_directory or not current_directory.exists():
            update_status("Error: Please select an input directory first", is_error=True)
            return

        ext_counts = {}
        for file_path in current_directory.glob("*"):
            if file_path.is_file():
                ext = file_path.suffix.lower() or "(no extension)"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

        result_text = f"File count by extension in {current_directory.name}:\n\n"
        if ext_counts:
            for ext, count in sorted(ext_counts.items(), key=lambda x: x[1], reverse=True):
                result_text += f"• {ext}: {count}\n"
        else:
            result_text += "(No files found)"

        def close_dialog(e):
            dialog.open = False
            page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Function 2: Count Files by Extension"),
            content=ft.Container(
                content=ft.Text(result_text, selectable=True),
                width=600,
                height=400,
            ),
            actions=[ft.TextButton("Close", on_click=close_dialog)],
        )

        page.overlay.append(dialog)
        dialog.open = True
        page.update()

        total = sum(ext_counts.values())
        update_status(f"Counted {total} file(s) across {len(ext_counts)} extension(s)")
        logger.info(f"Function 2: Counted files by extension in {current_directory}")

    def on_function_3_system_info(e):
        """Function 3: Display system information."""
        storage.record_function_usage("Function 3")

        info_lines = [
            f"Hostname: {socket.gethostname()}",
            f"OS: {platform.system()} {platform.release()}",
            f"Machine: {platform.machine()}",
            f"Python: {platform.python_version()}",
            f"User: {getpass.getuser()}",
            f"Data Directory: {DATA_DIR}",
        ]

        result_text = "System Information:\n\n" + "\n".join(f"• {line}" for line in info_lines)

        def close_dialog(e):
            dialog.open = False
            page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Function 3: System Info"),
            content=ft.Container(
                content=ft.Text(result_text, selectable=True),
                width=600,
                height=300,
            ),
            actions=[ft.TextButton("Close", on_click=close_dialog)],
        )

        page.overlay.append(dialog)
        dialog.open = True
        page.update()

        update_status("Displayed system information")
        logger.info("Function 3: Displayed system information")

    # ------------------------------------------------------------------ function management

    active_functions = [
        "function_1_list_files",
        "function_2_count_files",
        "function_3_system_info",
    ]

    functions = {
        "function_1_list_files": {
            "label": "1: List Files",
            "icon": "📁",
            "handler": on_function_1_list_files,
            "help_file": "FUNCTION_1_LIST_FILES.md"
        },
        "function_2_count_files": {
            "label": "2: Count Files by Extension",
            "icon": "📊",
            "handler": on_function_2_count_files,
            "help_file": "FUNCTION_2_COUNT_FILES.md"
        },
        "function_3_system_info": {
            "label": "3: System Information",
            "icon": "💻",
            "handler": on_function_3_system_info,
            "help_file": "FUNCTION_3_SYSTEM_INFO.md"
        },
    }

    help_mode_enabled = ft.Ref[ft.Checkbox]()

    def show_help_dialog(function_key):
        """Display the help markdown file for a function"""
        if function_key not in functions:
            return

        func_info = functions[function_key]
        help_file = func_info.get("help_file")
        display_label = func_info['label']

        if not help_file:
            add_log_message(f"No help file available for {display_label}")
            return

        markdown_content = load_help_document(help_file)
        add_log_message(f"Displaying help for: {display_label}")

        def close_help_dialog(e):
            help_dialog.open = False
            page.update()

        def copy_help(e):
            page.set_clipboard(markdown_content)
            add_log_message("Help content copied to clipboard")

        help_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Function {display_label}", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Markdown(
                            markdown_content,
                            selectable=True,
                            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        ),
                    ],
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=700,
                height=500,
            ),
            actions=[
                ft.TextButton("Copy to Clipboard", on_click=copy_help),
                ft.TextButton("Close", on_click=close_help_dialog),
            ],
        )

        page.overlay.append(help_dialog)
        help_dialog.open = True
        page.update()

    def execute_selected_function(function_key):
        """Execute or show help for the selected function."""
        if not function_key or function_key not in functions:
            return

        if help_mode_enabled.current and help_mode_enabled.current.value:
            show_help_dialog(function_key)
        else:
            func_info = functions[function_key]
            handler = func_info.get("handler")
            if handler:
                logger.info(f"Executing {func_info['label']}")
                handler(None)

        active_function_dropdown.value = None
        page.update()

    def get_sorted_function_options(function_list):
        """Return dropdown options sorted by function number."""
        opts = []
        for func_key in function_list:
            if func_key in functions:
                f = functions[func_key]
                opts.append(
                    ft.dropdown.Option(
                        key=func_key,
                        text=f"{f['icon']} {f['label']}"
                    )
                )
        return opts

    # ------------------------------------------------------------------ UI fields

    input_dir_field = ft.TextField(
        label="Input Directory",
        value=storage.get_ui_state("last_input_dir"),
        read_only=True,
        expand=True,
    )

    output_dir_field = ft.TextField(
        label="Working/Output Directory",
        value=storage.get_ui_state("last_output_dir"),
        read_only=True,
        expand=True,
    )

    file_field = ft.TextField(
        label="Select File",
        value=storage.get_ui_state("last_file"),
        read_only=True,
        expand=True,
    )

    status_text = ft.TextField(
        value="Ready",
        multiline=True,
        min_lines=2,
        max_lines=3,
        read_only=True,
    )

    log_output = ft.TextField(
        value="",
        multiline=True,
        min_lines=8,
        max_lines=8,
        read_only=True,
    )

    def toggle_dirs(e):
        nonlocal dirs_expanded
        dirs_expanded = not dirs_expanded
        dirs_toggle_button.icon = (
            ft.Icons.EXPAND_LESS if dirs_expanded else ft.Icons.EXPAND_MORE
        )
        inputs_inner_column.visible = dirs_expanded
        page.update()

    dirs_toggle_button = ft.IconButton(
        icon=ft.Icons.EXPAND_LESS,
        tooltip="Collapse/Expand directories section",
        on_click=toggle_dirs,
    )

    inputs_inner_column = ft.Column(
        controls=[
            ft.Row(
                controls=[
                    input_dir_field,
                    ft.ElevatedButton(
                        "Browse...",
                        icon=ft.Icons.FOLDER_OPEN,
                        on_click=lambda _: input_dir_picker.get_directory_path(
                            dialog_title="Select Input Directory"
                        ),
                    ),
                ],
            ),
            ft.Container(height=5),
            ft.Row(
                controls=[
                    output_dir_field,
                    ft.ElevatedButton(
                        "Browse...",
                        icon=ft.Icons.FOLDER_OPEN,
                        on_click=lambda _: output_dir_picker.get_directory_path(
                            dialog_title="Select Working/Output Directory"
                        ),
                    ),
                ],
            ),
        ],
        visible=True,
    )

    # ------------------------------------------------------------------ layout

    page.add(
        ft.Column(
            controls=[
                # ---- Title
                ft.Row([
                    ft.Icon(ft.Icons.APARTMENT, size=28, color=ft.Colors.BLUE_700),
                    ft.Text(
                        "FLAT — Flet Layout Application Template",
                        size=24,
                        weight=ft.FontWeight.BOLD,
                    ),
                ], spacing=10),
                ft.Text(
                    "A template application with persistent settings, logging, and function management",
                    size=13,
                    color=ft.Colors.GREY_700,
                    italic=True,
                ),
                ft.Divider(height=5),

                # ---- Directories section (collapsible)
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Text(
                                        "Directories",
                                        size=18,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    dirs_toggle_button,
                                ],
                            ),
                            inputs_inner_column,
                        ],
                        spacing=5,
                    ),
                    padding=5,
                ),

                ft.Divider(height=5),

                # ---- File Selection
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "File Selection",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Row(
                                controls=[
                                    file_field,
                                    ft.ElevatedButton(
                                        "Browse...",
                                        icon=ft.Icons.FILE_OPEN,
                                        on_click=lambda _: file_picker.pick_files(
                                            dialog_title="Select File",
                                            allow_multiple=False,
                                        ),
                                    ),
                                ],
                            ),
                        ],
                        spacing=5,
                    ),
                    padding=5,
                ),

                ft.Divider(height=5),

                # ---- Functions
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Column(
                                        controls=[
                                            ft.Text(
                                                "Functions",
                                                size=18,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Text(
                                                "Select and execute workflow functions",
                                                size=12,
                                                italic=True,
                                                color=ft.Colors.GREY_700,
                                            ),
                                            ft.Container(height=5),
                                            active_function_dropdown := ft.Dropdown(
                                                label="Select Function to Execute",
                                                hint_text="Choose a function",
                                                width=500,
                                                options=[],
                                                on_change=lambda e: execute_selected_function(
                                                    e.control.value
                                                ),
                                            ),
                                            ft.Container(height=5),
                                            ft.Checkbox(
                                                label="Help Mode",
                                                ref=help_mode_enabled,
                                                tooltip="Enable to view help documentation for functions instead of executing them",
                                            ),
                                        ],
                                        spacing=5,
                                    ),
                                ],
                                vertical_alignment=ft.CrossAxisAlignment.START,
                            ),
                        ],
                        spacing=5,
                    ),
                    padding=5,
                ),

                ft.Divider(height=5),

                # ---- Status
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Text(
                                        "Status",
                                        size=18,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.COPY,
                                        tooltip="Copy status to clipboard",
                                        on_click=on_copy_status_click,
                                        icon_size=20,
                                    ),
                                ],
                            ),
                            status_text,
                        ],
                        spacing=5,
                    ),
                    padding=5,
                ),

                ft.Divider(height=5),

                # ---- Log output
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Text(
                                        "Log Output",
                                        size=18,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_SWEEP,
                                        tooltip="Clear log",
                                        on_click=on_clear_log_click,
                                        icon_size=20,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.COPY,
                                        tooltip="Copy log to clipboard",
                                        on_click=on_copy_log_click,
                                        icon_size=20,
                                    ),
                                ],
                            ),
                            log_output,
                        ],
                        spacing=5,
                    ),
                    padding=5,
                ),
            ],
            spacing=5,
        )
    )

    # Initialize function dropdown
    active_function_dropdown.options = get_sorted_function_options(active_functions)
    page.update()

    logger.info("UI initialised successfully")
    add_log_message("FLAT application ready. Select a function to begin.")


if __name__ == "__main__":
    logger.info("Application starting…")
    ft.app(target=main)
