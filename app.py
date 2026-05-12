"""
DART - Digital Asset Routing and Transformation
A Flet desktop application for digital asset management with persistent settings,
logging, function management, and help documentation based on OHM's proven UI.
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
from typing import Optional, Tuple
from cryptography.fernet import Fernet, InvalidToken

# Import common DG utilities
from common_dg_utilities.dg_utils import generate_unique_id

# Configure logging
DATA_DIR = Path.home() / "DART-data"
LOG_DIR = Path.cwd() / "logfiles"
os.makedirs(LOG_DIR, exist_ok=True)
log_filename = LOG_DIR / f"dart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

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

# Encryption key file
ENCRYPTION_KEY_FILE = DATA_DIR / "encryption_key"

# Sensitive fields that should be encrypted in settings
SENSITIVE_FIELDS = ["api_key", "api_secret", "password"]

# App settings filename and defaults
APP_SETTINGS_FILENAME = "dart_settings.json"
DEFAULT_APP_SETTINGS = {
    "auto_save_enabled": False,
    "auto_save_format": "txt",
    "group_compound_objects": False,
    "use_working_folder_for_file_selection": False,
    "csv_structure_file": "",
    "api_key": "",
    "api_secret": "",
    "password": "",
    "file_to_id_map": {},  # Maps full file paths to assigned dg_<epoch> IDs
}


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
                "last_files": "",
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


def get_or_create_encryption_key() -> bytes:
    """
    Get or create the encryption key from ~/.DART-data/encryption_key.
    Returns the Fernet key as bytes.
    """
    if ENCRYPTION_KEY_FILE.exists():
        try:
            with open(ENCRYPTION_KEY_FILE, "rb") as f:
                key = f.read()
            # Verify it's a valid Fernet key
            Fernet(key)
            return key
        except Exception as e:
            logger.warning(f"Invalid encryption key file, regenerating: {str(e)}")
    
    # Generate a new key
    key = Fernet.generate_key()
    try:
        with open(ENCRYPTION_KEY_FILE, "wb") as f:
            f.write(key)
        # Restrict permissions to owner only
        os.chmod(ENCRYPTION_KEY_FILE, 0o600)
    except Exception as e:
        logger.error(f"Could not save encryption key: {str(e)}")
    
    return key


def encrypt_sensitive_settings(settings: dict) -> dict:
    """
    Encrypt sensitive fields in settings dictionary.
    Returns a new dictionary with encrypted values.
    """
    try:
        key = get_or_create_encryption_key()
        cipher = Fernet(key)
        encrypted = dict(settings)
        
        for field in SENSITIVE_FIELDS:
            if field in encrypted and encrypted[field]:
                plaintext = str(encrypted[field])
                ciphertext = cipher.encrypt(plaintext.encode()).decode()
                encrypted[field] = ciphertext
        
        return encrypted
    except Exception as e:
        logger.error(f"Could not encrypt settings: {str(e)}")
        return settings


def decrypt_sensitive_settings(settings: dict) -> dict:
    """
    Decrypt sensitive fields in settings dictionary.
    Returns a new dictionary with decrypted values.
    Gracefully handles already-decrypted values and encryption errors.
    """
    try:
        key = get_or_create_encryption_key()
        cipher = Fernet(key)
        decrypted = dict(settings)
        
        for field in SENSITIVE_FIELDS:
            if field in decrypted and decrypted[field]:
                ciphertext = decrypted[field]
                try:
                    # Try to decrypt; if it fails, assume it's already plaintext
                    plaintext = cipher.decrypt(ciphertext.encode()).decode()
                    decrypted[field] = plaintext
                except (InvalidToken, ValueError):
                    # Already plaintext or corrupted; leave as-is
                    pass
        
        return decrypted
    except Exception as e:
        logger.error(f"Could not decrypt settings: {str(e)}")
        return settings


def get_app_settings_path(working_dir: str) -> Path:
    """Return the settings file path for a working directory."""
    return Path(working_dir) / APP_SETTINGS_FILENAME


def ensure_app_settings_file(working_dir: str) -> Path:
    """Create the app settings file with defaults if it does not exist."""
    settings_path = get_app_settings_path(working_dir)
    os.makedirs(settings_path.parent, exist_ok=True)
    if not settings_path.exists():
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_APP_SETTINGS, f, indent=2, ensure_ascii=False)
    return settings_path


def load_app_settings(working_dir: str) -> Tuple[dict, str]:
    """Load app settings from the working directory settings file."""
    try:
        settings_path = ensure_app_settings_file(working_dir)
        with open(settings_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        # Decrypt sensitive fields
        loaded = decrypt_sensitive_settings(loaded)
        settings = dict(DEFAULT_APP_SETTINGS)
        settings.update(loaded)
        return settings, ""
    except Exception as e:
        logger.error(f"Could not load app settings: {str(e)}")
        return dict(DEFAULT_APP_SETTINGS), f"Error loading app settings: {str(e)}"


def save_app_settings(working_dir: str, settings: dict) -> Tuple[bool, str]:
    """Save app settings to the working directory settings file.
    Sensitive fields are encrypted before saving.
    """
    try:
        settings_path = ensure_app_settings_file(working_dir)
        # Encrypt sensitive fields before saving
        settings_to_save = encrypt_sensitive_settings(settings)
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings_to_save, f, indent=2, ensure_ascii=False)
        return True, str(settings_path)
    except Exception as e:
        logger.error(f"Could not save app settings: {str(e)}")
        return False, f"Error saving app settings: {str(e)}"


def parse_bool_text(value: str) -> Optional[bool]:
    """Parse user-entered boolean text. Returns None if invalid."""
    lowered = (value or "").strip().lower()
    if lowered in ["true", "1", "yes", "y", "on"]:
        return True
    if lowered in ["false", "0", "no", "n", "off"]:
        return False
    return None


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
    page.title = "DART - Digital Asset Routing and Transformation"
    page.padding = 20
    page.window.width = 1050
    page.window.height = 900
    page.scroll = ft.ScrollMode.AUTO

    storage = PersistentStorage()
    logger.info("DART application started")

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
            update_status(f"Inputs folder set: {current_directory.name}")
            page.update()

    def on_output_dir_result(e: ft.FilePickerResultEvent):
        if e.path:
            output_dir_field.value = e.path
            storage.set_ui_state("last_output_dir", e.path)
            update_status(f"Outputs folder set: {Path(e.path).name}")
            page.update()

    def on_file_result(e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            if len(e.files) == 1:
                file_path = e.files[0].path
                file_field.value = file_path
                storage.set_ui_state("last_file", file_path)
                update_status(f"File selected: {Path(file_path).name}")
            else:
                # Multiple files selected
                file_paths = [f.path for f in e.files]
                file_names = [Path(f).name for f in file_paths]
                file_field.value = f"{len(file_paths)} files: {', '.join(file_names[:3])}{'...' if len(file_names) > 3 else ''}"
                storage.set_ui_state("last_file", file_paths[0])  # Store first file for reference
                storage.set_ui_state("last_files", ",".join(file_paths))  # Store all files
                update_status(f"{len(file_paths)} files selected")
            page.update()

    input_dir_picker = ft.FilePicker(on_result=on_input_dir_result)
    output_dir_picker = ft.FilePicker(on_result=on_output_dir_result)
    file_picker = ft.FilePicker(on_result=on_file_result)

    page.overlay.extend([input_dir_picker, output_dir_picker, file_picker])

    # ------------------------------------------------------------------ helper functions

    def open_file_picker_with_settings():
        """Open file picker, using working folder or inputs folder as initial directory based on settings."""
        working_dir = output_dir_field.value
        initial_dir = None
        
        if working_dir:
            settings, _ = load_app_settings(working_dir)
            use_working_folder = settings.get("use_working_folder_for_file_selection", False)
            if use_working_folder:
                initial_dir = working_dir
            else:
                # When false, use inputs folder if available
                input_dir = input_dir_field.value
                if input_dir:
                    initial_dir = input_dir
        
        file_picker.pick_files(
            dialog_title="Select Files",
            allow_multiple=True,
            initial_directory=initial_dir,
        )

    def get_selected_files():
        """Get list of selected files from storage. Returns list of Path objects."""
        last_files = storage.get_ui_state("last_files")
        if last_files:
            # Multiple files stored
            return [Path(f) for f in last_files.split(",")]
        else:
            # Single file or no files
            last_file = storage.get_ui_state("last_file")
            if last_file:
                return [Path(last_file)]
            return []

    # ------------------------------------------------------------------ function implementations

    def on_function_0_app_settings(e):
        """Function 0: Open and edit app settings in working directory."""
        storage.record_function_usage("Function 0")

        working_dir = output_dir_field.value
        if not working_dir:
            update_status("Error: Please select a Working/Outputs Folder first", is_error=True)
            return

        settings, load_error = load_app_settings(working_dir)
        if load_error:
            update_status(load_error, is_error=True)
            return

        settings_path = get_app_settings_path(working_dir)
        
        # Create form fields
        auto_save_field = ft.TextField(
            label="auto_save_enabled",
            value=str(settings.get("auto_save_enabled", False)).lower(),
            hint_text="true or false",
            width=320,
        )
        auto_save_format_field = ft.TextField(
            label="auto_save_format",
            value=str(settings.get("auto_save_format", "txt")).lower(),
            hint_text="txt, csv, json, etc.",
            width=320,
        )
        group_compound_field = ft.TextField(
            label="group_compound_objects",
            value=str(settings.get("group_compound_objects", False)).lower(),
            hint_text="true or false - group similar assets as compound objects",
            width=320,
        )
        use_working_folder_field = ft.TextField(
            label="use_working_folder_for_file_selection",
            value=str(settings.get("use_working_folder_for_file_selection", False)).lower(),
            hint_text="true or false - use working folder as initial directory for file picker",
            width=320,
        )
        csv_structure_field = ft.TextField(
            label="csv_structure_file",
            value=str(settings.get("csv_structure_file", "")),
            hint_text="Path to CSV file defining expected column structure",
            width=320,
        )
        api_key_field = ft.TextField(
            label="api_key",
            value=str(settings.get("api_key", "")),
            hint_text="API key (encrypted)",
            width=320,
        )
        api_secret_field = ft.TextField(
            label="api_secret",
            value=str(settings.get("api_secret", "")),
            hint_text="API secret (encrypted)",
            password=True,
            can_reveal_password=True,
            width=320,
        )
        password_field = ft.TextField(
            label="password",
            value=str(settings.get("password", "")),
            hint_text="Password (encrypted)",
            password=True,
            can_reveal_password=True,
            width=320,
        )

        settings_path_text = ft.Text(
            f"Settings file: {settings_path}",
            size=12,
            color=ft.Colors.GREY_700,
            selectable=True,
        )

        def close_dialog(evt):
            settings_dialog.open = False
            page.update()

        def save_settings_click(evt):
            parsed_auto_save = parse_bool_text(auto_save_field.value)
            if parsed_auto_save is None:
                update_status(
                    "Error: auto_save_enabled must be true/false (or yes/no, 1/0)",
                    is_error=True,
                )
                return
            
            parsed_group_compound = parse_bool_text(group_compound_field.value)
            if parsed_group_compound is None:
                update_status(
                    "Error: group_compound_objects must be true/false (or yes/no, 1/0)",
                    is_error=True,
                )
                return
            
            parsed_use_working_folder = parse_bool_text(use_working_folder_field.value)
            if parsed_use_working_folder is None:
                update_status(
                    "Error: use_working_folder_for_file_selection must be true/false (or yes/no, 1/0)",
                    is_error=True,
                )
                return

            new_settings = {
                "auto_save_enabled": parsed_auto_save,
                "auto_save_format": (auto_save_format_field.value or "").strip() or "txt",
                "group_compound_objects": parsed_group_compound,
                "use_working_folder_for_file_selection": parsed_use_working_folder,
                "csv_structure_file": (csv_structure_field.value or "").strip(),
                "api_key": (api_key_field.value or "").strip(),
                "api_secret": (api_secret_field.value or "").strip(),
                "password": (password_field.value or "").strip(),
            }
            ok, save_result = save_app_settings(working_dir, new_settings)
            if not ok:
                update_status(save_result, is_error=True)
                return

            add_log_message(f"Settings saved: {save_result}")
            update_status("Application settings updated")
            settings_dialog.open = False
            page.update()

        settings_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Function 0: App Settings", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Edit app settings and save them to the working folder.",
                            size=13,
                        ),
                        settings_path_text,
                        ft.Container(height=8),
                        auto_save_field,
                        auto_save_format_field,
                        group_compound_field,
                        use_working_folder_field,
                        csv_structure_field,
                        ft.Container(height=8),
                        ft.Text(
                            "Sensitive fields (encrypted in file):",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                        ),
                        api_key_field,
                        ft.Row(
                            controls=[
                                api_secret_field,
                                password_field,
                            ]
                        ),
                    ],
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=700,
                height=400,
            ),
            actions=[
                ft.TextButton("Save", on_click=save_settings_click),
                ft.TextButton("Cancel", on_click=close_dialog),
            ],
        )

        page.overlay.append(settings_dialog)
        settings_dialog.open = True
        page.update()

    def on_function_1_list_files(e):
        """Function 1: Analyze digital assets and generate standard DG identifiers."""
        storage.record_function_usage("Function 1")

        # Load settings to check compound object grouping
        working_dir = output_dir_field.value
        group_compound = False
        if working_dir:
            settings, _ = load_app_settings(working_dir)
            group_compound = settings.get("group_compound_objects", False)
        
        # DEBUG: Log settings
        add_log_message(f"[DEBUG] Working/Outputs Folder: {working_dir or 'Not set'}")
        add_log_message(f"[DEBUG] Compound grouping: {group_compound}")
        logger.info(f"[DEBUG] Working folder: {working_dir}, Compound grouping: {group_compound}")

        # Digital asset file extensions
        asset_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.tif', '.tiff', '.bmp', '.webp',  # Images
            '.pdf',  # PDFs
            '.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm',  # Video
            '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma',  # Audio
            '.zip', '.tar', '.gz', '.7z', '.rar', '.bz2',  # Archives
        }

        # Get files to process - either selected files or scan inputs folder
        selected_files = get_selected_files()
        files = []
        source_description = ""
        
        if selected_files:
            # Use selected files
            add_log_message(f"[DEBUG] Using {len(selected_files)} selected file(s)")
            logger.info(f"[DEBUG] Selected files: {selected_files}")
            for file_path in selected_files:
                if file_path.is_file() and file_path.suffix.lower() in asset_extensions:
                    files.append(str(file_path))  # Store full path
            source_description = "from selected files"
        else:
            # Fall back to scanning inputs folder
            if not current_directory or not current_directory.exists():
                update_status("Error: Please select files or an inputs folder first", is_error=True)
                return
            
            add_log_message(f"[DEBUG] No files selected - scanning Inputs Folder: {current_directory}")
            logger.info(f"[DEBUG] Scanning folder: {current_directory}")
            for file_path in current_directory.glob("*"):
                if file_path.is_file() and file_path.suffix.lower() in asset_extensions:
                    files.append(str(file_path))  # Store full path
            source_description = f"in {current_directory.name}"

        # DEBUG: Log files found
        add_log_message(f"[DEBUG] Found {len(files)} asset files matching extensions")
        logger.info(f"[DEBUG] Files found: {files}")
        
        if not files:
            update_status("No digital asset files found in folder", is_error=True)
            add_log_message("[DEBUG] No files found - exiting Function 1")
            return

        files.sort()

        # Load existing file-to-ID mappings
        file_to_id_map = {}
        if working_dir:
            settings, _ = load_app_settings(working_dir)
            file_to_id_map = settings.get("file_to_id_map", {})
            add_log_message(f"[DEBUG] Loaded {len(file_to_id_map)} existing file-to-ID mappings")
            logger.info(f"[DEBUG] Existing mappings: {file_to_id_map}")

        # Generate or retrieve standard DG identifiers for each file
        add_log_message(f"[DEBUG] Assigning standard dg_<epoch> identifiers")
        logger.info("[DEBUG] Using standard DG identifier format: dg_<epoch_time>")
        
        objects = []
        new_mappings = 0
        reused_mappings = 0
        
        for file_path_str in files:
            # Check if this file already has an assigned ID (using full path as key)
            if file_path_str in file_to_id_map:
                # Reuse existing ID - never change once assigned!
                unique_id = file_to_id_map[file_path_str]
                reused_mappings += 1
                logger.info(f"[DEBUG] Reusing existing: {unique_id} → {file_path_str}")
            else:
                # Generate new unique DG identifier
                unique_id = generate_unique_id(page)
                file_to_id_map[file_path_str] = unique_id
                new_mappings += 1
                logger.info(f"[DEBUG] Generated new: {unique_id} → {file_path_str}")
            
            # Store both full path and display name
            objects.append({
                "objectid": unique_id,
                "filepath": file_path_str,
                "filename": Path(file_path_str).name,
            })

        add_log_message(f"[DEBUG] IDs assigned: {new_mappings} new, {reused_mappings} reused")
        logger.info(f"[DEBUG] Total mappings in cache: {len(file_to_id_map)}")
        
        # Save updated file-to-ID mappings
        if working_dir and new_mappings > 0:
            settings["file_to_id_map"] = file_to_id_map
            ok, save_result = save_app_settings(working_dir, settings)
            if ok:
                add_log_message(f"[DEBUG] Saved {len(file_to_id_map)} file-to-ID mappings to settings")
                logger.info(f"[DEBUG] Settings saved: {save_result}")
            else:
                logger.error(f"[DEBUG] Failed to save mappings: {save_result}")
                add_log_message(f"[DEBUG] Warning: Could not save ID mappings - {save_result}")


        # Validate uniqueness of object IDs (should always be unique with epoch-based IDs)
        objectid_counts = {}
        for obj in objects:
            oid = obj["objectid"]
            objectid_counts[oid] = objectid_counts.get(oid, 0) + 1
        
        duplicates = {oid: count for oid, count in objectid_counts.items() if count > 1}
        if duplicates:
            error_msg = f"ERROR: Duplicate object IDs found: {duplicates}"
            add_log_message(f"[DEBUG] {error_msg}")
            logger.error(f"[DEBUG] {error_msg}")
            logger.error(f"[DEBUG] Objects with duplicates: {[obj for obj in objects if obj['objectid'] in duplicates]}")
            update_status("Error: Duplicate object IDs detected - check log for details", is_error=True)
            
            # Show error dialog with details
            dup_details = []
            for oid in sorted(duplicates.keys()):
                files_with_oid = [obj["filename"] for obj in objects if obj["objectid"] == oid]
                dup_details.append(f"• {oid} appears {duplicates[oid]} times:")
                for fname in files_with_oid:
                    dup_details.append(f"    - {fname}")
            
            def close_error(e):
                error_dialog.open = False
                page.update()
            
            error_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Error: Duplicate Object IDs", weight=ft.FontWeight.BOLD, color=ft.Colors.RED),
                content=ft.Container(
                    content=ft.Text("\n".join(dup_details), selectable=True),
                    width=700,
                    height=400,
                ),
                actions=[ft.TextButton("Close", on_click=close_error)],
            )
            page.overlay.append(error_dialog)
            error_dialog.open = True
            page.update()
            return
        
        # Build result text
        add_log_message(f"[DEBUG] Generated {len(objects)} UNIQUE objects from {len(files)} files")
        logger.info(f"[DEBUG] Uniqueness validated: All {len(objects)} object IDs are unique")
        logger.info(f"[DEBUG] Final objects list: {objects}")
        
        result_lines = [f"Found {len(files)} digital asset file(s) {source_description}"]
        result_lines.append(f"Identifiers: {new_mappings} new, {reused_mappings} reused (IDs never change once assigned)")
        result_lines.append(f"Compound object grouping: {'ENABLED' if group_compound else 'DISABLED'}")
        result_lines.append("")
        
        # Show list of identifiers (grouping logic will be modified soon)
        for obj in objects:
            result_lines.append(f"• {obj['objectid']} → {obj['filename']} ({obj['filepath']})")

        result_text = "\n".join(result_lines)

        def close_dialog(e):
            dialog.open = False
            page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Function 1: Analyze Digital Assets", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Text(result_text, selectable=True),
                width=700,
                height=500,
            ),
            actions=[ft.TextButton("Close", on_click=close_dialog)],
        )

        page.overlay.append(dialog)
        dialog.open = True
        page.update()

        update_status(f"Analyzed {len(files)} file(s), generated {len(objects)} unique object ID(s)")
        logger.info(f"Function 1: Analyzed {len(files)} files, generated {len(objects)} unique object IDs")

    def on_function_2_count_files(e):
        """Function 2: Count files by extension."""
        storage.record_function_usage("Function 2")

        if not current_directory or not current_directory.exists():
            update_status("Error: Please select an inputs folder first", is_error=True)
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
            f"Data Folder: {DATA_DIR}",
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
        "function_0_app_settings",
        "function_1_list_files",
        "function_2_count_files",
        "function_3_system_info",
    ]

    functions = {
        "function_0_app_settings": {
            "label": "0: App Settings",
            "icon": "⚙️",
            "handler": on_function_0_app_settings,
            "help_file": "FUNCTION_0_APP_SETTINGS.md"
        },
        "function_1_list_files": {
            "label": "1: Analyze Digital Assets & Generate Object IDs",
            "icon": "🎯",
            "handler": on_function_1_list_files,
            "help_file": "FUNCTION_1_ANALYZE_ASSETS.md"
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
        label="Inputs Folder",
        value=storage.get_ui_state("last_input_dir"),
        read_only=True,
        expand=True,
    )

    output_dir_field = ft.TextField(
        label="Working/Outputs Folder",
        value=storage.get_ui_state("last_output_dir"),
        read_only=True,
        expand=True,
    )

    # Initialize file field with persisted selection
    def get_initial_file_display():
        last_files = storage.get_ui_state("last_files")
        if last_files:
            file_paths = last_files.split(",")
            if len(file_paths) == 1:
                return file_paths[0]
            else:
                file_names = [Path(f).name for f in file_paths]
                return f"{len(file_paths)} files: {', '.join(file_names[:3])}{'...' if len(file_names) > 3 else ''}"
        else:
            return storage.get_ui_state("last_file")
    
    file_field = ft.TextField(
        label="Select Files",
        value=get_initial_file_display(),
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
        tooltip="Collapse/Expand folders section",
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
                            dialog_title="Select Inputs Folder"
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
                            dialog_title="Select Working/Outputs Folder"
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
                    ft.Text("🎯", size=32),
                    ft.Text(
                        "DART — Digital Asset Routing and Transformation",
                        size=24,
                        weight=ft.FontWeight.BOLD,
                    ),
                ], spacing=10),
                ft.Text(
                    "Process digital assets from folders or CSV manifests to create derivatives and transformations",
                    size=13,
                    color=ft.Colors.GREY_700,
                    italic=True,
                ),
                ft.Divider(height=5),

                # ---- Folders section (collapsible)
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Text(
                                        "Folders",
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

                # ---- Files Selection
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(
                                "Files Selection",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Row(
                                controls=[
                                    file_field,
                                    ft.ElevatedButton(
                                        "Browse...",
                                        icon=ft.Icons.FILE_OPEN,
                                        on_click=lambda _: open_file_picker_with_settings(),
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
    add_log_message("DART application ready. Select a function to begin.")


if __name__ == "__main__":
    logger.info("Application starting…")
    ft.app(target=main)
