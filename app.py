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
import re
import csv
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from cryptography.fernet import Fernet, InvalidToken
from azure.storage.blob import BlobServiceClient, ContentSettings
from PIL import Image, ImageOps
import io
import fitz  # PyMuPDF for PDF processing

# Import common DG utilities
from common_dg_utilities.dg_utils import generate_unique_id, get_mime_type

# Configure logging
DATA_DIR = Path.home() / "DART-data"
# LOG_DIR will be set dynamically based on working directory
# For now, use a temporary location until working dir is known
TEMP_LOG_DIR = DATA_DIR / "logfiles"
os.makedirs(TEMP_LOG_DIR, exist_ok=True)

# Create initial logger that will be reconfigured when working dir is known
log_filename = TEMP_LOG_DIR / f"dart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

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

def setup_working_dir_logging(working_dir: str):
    """Reconfigure logging to use the working directory for log files."""
    global file_handler, log_filename
    
    if not working_dir:
        return
    
    log_dir = Path(working_dir) / "logfiles"
    os.makedirs(log_dir, exist_ok=True)
    
    new_log_filename = log_dir / f"dart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Close old handler
    file_handler.close()
    logger.removeHandler(file_handler)
    
    # Create new handler for working directory
    new_file_handler = logging.FileHandler(new_log_filename)
    new_file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    new_file_handler.setFormatter(formatter)
    
    logger.addHandler(new_file_handler)
    file_handler = new_file_handler
    log_filename = new_log_filename
    
    logger.info(f"Logging reconfigured to use working directory: {log_dir}")
    return str(new_log_filename)

# Persistent storage file
PERSISTENCE_FILE = DATA_DIR / "persistent.json"

# Encryption key file
ENCRYPTION_KEY_FILE = DATA_DIR / "encryption_key"

# Sensitive fields that should be encrypted in settings
SENSITIVE_FIELDS = ["azure_connection_string"]

# App settings filename and defaults
APP_SETTINGS_FILENAME = "dart_settings.json"
DEFAULT_APP_SETTINGS = {
    "group_compound_objects": False,
    "use_working_folder_for_file_selection": False,
    "csv_structure_file": "",
    "core_metadata_csv": "",
    "azure_blob_storage_path": "",
    "azure_connection_string": "",
    "file_to_id_map": {},  # Maps full file paths to assigned dg_<epoch> IDs
}

# Required CollectionBuilder CSV fields
REQUIRED_CSV_FIELDS = ["objectid", "filename"]
RECOMMENDED_CSV_FIELDS = ["title", "format", "date"]


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


def validate_csv_structure(csv_path: str) -> Tuple[bool, str, list]:
    """
    Validate that a CSV file has the required CollectionBuilder fields.
    Returns (success, message, field_list).
    """
    if not csv_path or not csv_path.strip():
        return True, "No CSV structure file specified", []
    
    csv_file = Path(csv_path)
    if not csv_file.exists():
        return False, f"CSV file not found: {csv_path}", []
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader, None)
            
            if not headers:
                return False, "CSV file is empty or has no header row", []
            
            # Normalize headers (lowercase, strip whitespace)
            headers = [h.strip().lower() for h in headers]
            
            # Check for required fields
            missing_fields = [field for field in REQUIRED_CSV_FIELDS if field.lower() not in headers]
            
            if missing_fields:
                return False, f"Missing required fields: {', '.join(missing_fields)}", headers
            
            # Check for recommended fields (warning only)
            missing_recommended = [field for field in RECOMMENDED_CSV_FIELDS if field.lower() not in headers]
            
            if missing_recommended:
                msg = f"✓ Valid structure ({len(headers)} columns). Note: Missing recommended fields: {', '.join(missing_recommended)}"
            else:
                msg = f"✓ Valid structure with all required and recommended fields ({len(headers)} columns)"
            
            return True, msg, headers
            
    except Exception as e:
        return False, f"Error reading CSV file: {str(e)}", []


def validate_core_metadata_csv(csv_path: str, structure_path: str = "") -> Tuple[bool, str]:
    """
    Validate the core metadata CSV file.
    Checks that it exists, has valid structure, and matches template if provided.
    Returns (success, message).
    """
    if not csv_path or not csv_path.strip():
        return True, "No core metadata CSV specified (optional)"
    
    csv_file = Path(csv_path)
    if not csv_file.exists():
        return False, f"Core metadata CSV file not found: {csv_path}"
    
    # Validate basic structure
    valid, msg, headers = validate_csv_structure(csv_path)
    if not valid:
        return False, f"Core CSV validation failed: {msg}"
    
    # If structure template is provided, verify compatibility
    if structure_path and structure_path.strip():
        struct_valid, struct_msg, struct_headers = validate_csv_structure(structure_path)
        if struct_valid and struct_headers:
            # Check if core CSV has all columns from template
            missing_cols = [col for col in struct_headers if col not in headers]
            if missing_cols:
                return False, f"Core CSV missing columns from template: {', '.join(missing_cols)}"
            
            return True, f"✓ Core CSV valid and compatible with template ({len(headers)} columns)"
    
    return True, f"✓ Core CSV valid ({len(headers)} columns)"


def validate_azure_path(azure_path: str) -> Tuple[bool, str]:
    """
    Validate the Azure Blob Storage path.
    Checks that path contains /objs/ folder for original files.
    Also checks that user didn't enter a full URL by mistake.
    Returns (success, message).
    
    Note: /smalls/ and /thumbs/ folders should exist as parallel folders
    in Azure but are not validated programmatically.
    """
    if not azure_path or not azure_path.strip():
        return True, "No Azure path specified (optional)"
    
    path_normalized = azure_path.strip()
    
    # Check if user entered a URL instead of just the path
    if any(pattern in path_normalized.lower() for pattern in ['http://', 'https://', '.blob.core.windows.net', '.blob.']):
        return False, "✗ Enter only the path (e.g., 'objs/collection'), NOT the full URL. The URL is built automatically from your connection string."
    
    # Check for /objs/ folder (required)
    if "/objs/" not in path_normalized and not path_normalized.endswith("/objs"):
        return False, "✗ Path must contain /objs/ folder for original files"
    
    return True, "✓ Valid path with /objs/ folder (ensure /smalls/ and /thumbs/ exist in Azure)"


def copy_csv_to_working_dir(csv_path: str, working_dir: str, file_type: str) -> Tuple[str, bool, str]:
    """
    Copy a CSV file to the working directory if it's not already there.
    Returns (new_path, was_copied, message).
    file_type should be "template" or "core" for logging.
    """
    if not csv_path or not csv_path.strip():
        return "", False, ""
    
    source_path = Path(csv_path)
    working_path = Path(working_dir)
    
    if not source_path.exists():
        return csv_path, False, f"Source file not found: {csv_path}"
    
    # Check if file is already in working directory
    if source_path.parent.resolve() == working_path.resolve():
        return csv_path, False, f"{file_type.capitalize()} CSV already in working directory"
    
    # Copy file to working directory
    dest_path = working_path / source_path.name
    
    try:
        # Check if destination already exists
        if dest_path.exists():
            # Compare file contents to see if they're the same
            if source_path.read_bytes() == dest_path.read_bytes():
                return str(dest_path), False, f"{file_type.capitalize()} CSV already exists in working directory (identical)"
            else:
                # Files differ - create a unique name
                base_name = dest_path.stem
                suffix = dest_path.suffix
                counter = 1
                while dest_path.exists():
                    dest_path = working_path / f"{base_name}_{counter}{suffix}"
                    counter += 1
        
        shutil.copy2(source_path, dest_path)
        return str(dest_path), True, f"✓ Copied {file_type} CSV to working directory: {dest_path.name}"
    
    except Exception as e:
        return csv_path, False, f"Error copying {file_type} CSV: {str(e)}"


def sanitize_error_message(error_msg: str, connection_string: str) -> str:
    """
    Remove connection string and sensitive data from error messages.
    Azure SDK errors often include the full connection string.
    """
    sanitized = str(error_msg)
    
    # Remove the entire connection string if present
    if connection_string and connection_string in sanitized:
        sanitized = sanitized.replace(connection_string, "[CONNECTION_STRING_REDACTED]")
    
    # Remove AccountKey values
    import re
    sanitized = re.sub(r'AccountKey=[^;]+', 'AccountKey=[REDACTED]', sanitized)
    
    return sanitized


def init_azure_client(connection_string: str) -> Tuple[bool, Optional[BlobServiceClient], str]:
    """
    Initialize Azure Blob Service Client from connection string.
    Returns (success, client, message).
    """
    if not connection_string or not connection_string.strip():
        logger.warning("Azure connection string not configured")
        return False, None, "Azure connection string not configured"
    
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        # Test connection by getting account information
        account_info = blob_service_client.get_account_information()
        logger.info(f"Connected to Azure Storage (SKU: {account_info.get('sku_name', 'unknown')})")
        return True, blob_service_client, f"✓ Connected to Azure Storage (SKU: {account_info.get('sku_name', 'unknown')})"
    except Exception as e:
        # Sanitize error message before logging or displaying
        sanitized_msg = sanitize_error_message(str(e), connection_string)
        logger.error(f"Azure connection failed: {sanitized_msg}")
        return False, None, f"Failed to connect to Azure: {sanitized_msg}"


def build_object_location(azure_path: str, object_id: str, file_extension: str, connection_string: str) -> Tuple[bool, str, str]:
    """
    Build complete Azure Blob Storage URL for an object.
    
    Args:
        azure_path: Path like "objs/collection_name" or "container/objs/path"
        object_id: The dg_<epoch> identifier
        file_extension: Original file extension (e.g., '.jpg')
        connection_string: Azure connection string to extract account name
    
    Returns (success, url, message).
    
    URL format: https://{account}.blob.core.windows.net/{container}/{path}/{objectid}{ext}
    """
    try:
        # Parse connection string to get account name
        account_name = None
        for part in connection_string.split(';'):
            if part.startswith('AccountName='):
                account_name = part.split('=', 1)[1]
                break
        
        if not account_name:
            return False, "", "Could not extract AccountName from connection string"
        
        # Normalize path (remove leading/trailing slashes)
        normalized_path = azure_path.strip().strip('/')
        
        # Split path into container and blob path
        path_parts = normalized_path.split('/', 1)
        if len(path_parts) == 1:
            # Just container name provided (e.g., "objs")
            container = path_parts[0]
            blob_path = ""
        else:
            # Container and path provided (e.g., "container/objs/collection")
            container = path_parts[0]
            blob_path = path_parts[1]
        
        # Build blob name: path/objectid.ext
        if blob_path:
            blob_name = f"{blob_path}/{object_id}{file_extension}"
        else:
            blob_name = f"{object_id}{file_extension}"
        
        # Build complete URL
        url = f"https://{account_name}.blob.core.windows.net/{container}/{blob_name}"
        
        return True, url, f"Built URL for {object_id}{file_extension}"
        
    except Exception as e:
        sanitized_msg = sanitize_error_message(str(e), connection_string)
        logger.error(f"Error building object_location for {object_id}: {sanitized_msg}")
        return False, "", f"Error building object_location: {sanitized_msg}"


def upload_to_azure(
    blob_service_client: BlobServiceClient,
    local_file_path: str,
    azure_path: str,
    object_id: str,
    file_extension: str
) -> Tuple[bool, str]:
    """
    Upload a file to Azure Blob Storage with renamed filename.
    
    Args:
        blob_service_client: Initialized Azure BlobServiceClient
        local_file_path: Path to local file to upload
        azure_path: Azure path like "objs/collection" or "container/objs/path"
        object_id: The dg_<epoch> identifier (becomes the filename)
        file_extension: Original file extension to preserve
    
    Returns (success, message).
    """
    try:
        local_path = Path(local_file_path)
        if not local_path.exists():
            return False, f"Local file not found: {local_file_path}"
        
        # Normalize path
        normalized_path = azure_path.strip().strip('/')
        
        # Split path into container and blob path
        path_parts = normalized_path.split('/', 1)
        if len(path_parts) == 1:
            container = path_parts[0]
            blob_path = ""
        else:
            container = path_parts[0]
            blob_path = path_parts[1]
        
        # Build blob name with object_id as filename
        if blob_path:
            blob_name = f"{blob_path}/{object_id}{file_extension}"
        else:
            blob_name = f"{object_id}{file_extension}"
        
        # Debug logging to verify blob name construction
        logger.info(f"Uploading to Azure: local={local_path.name}, object_id={object_id}, extension={file_extension}, blob_name={blob_name}")
        
        # Get blob client
        blob_client = blob_service_client.get_blob_client(container=container, blob=blob_name)
        
        # Determine content type from extension
        content_type_map = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
            '.gif': 'image/gif', '.tif': 'image/tiff', '.tiff': 'image/tiff',
            '.bmp': 'image/bmp', '.webp': 'image/webp',
            '.pdf': 'application/pdf',
            '.mp4': 'video/mp4', '.mov': 'video/quicktime', '.avi': 'video/x-msvideo',
            '.mkv': 'video/x-matroska', '.webm': 'video/webm',
            '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.flac': 'audio/flac',
            '.aac': 'audio/aac', '.ogg': 'audio/ogg', '.m4a': 'audio/mp4',
            '.zip': 'application/zip', '.tar': 'application/x-tar',
            '.gz': 'application/gzip', '.7z': 'application/x-7z-compressed',
            '.rar': 'application/x-rar-compressed',
        }
        
        content_type = content_type_map.get(file_extension.lower(), 'application/octet-stream')
        content_settings = ContentSettings(content_type=content_type)
        
        # Upload file
        with open(local_path, 'rb') as data:
            blob_client.upload_blob(
                data,
                overwrite=True,
                content_settings=content_settings
            )
        
        logger.info(f"Successfully uploaded: {local_path.name} → Azure blob: {blob_name}")
        return True, f"✓ Uploaded {local_path.name} → {blob_name}"
        
    except Exception as e:
        # Note: Don't pass connection_string here as it's not available in this function
        error_msg = str(e)
        logger.error(f"Upload failed: {local_path.name} → blob_name={blob_name}, error={error_msg}")
        return False, f"Upload failed for {local_path.name} (as {blob_name.split('/')[-1]}): {error_msg}"


def generate_derivative(
    input_path: str,
    output_path: str,
    max_width: int,
    max_height: int,
    quality: int = 85
) -> Tuple[bool, str]:
    """
    Generate a derivative image at specified maximum dimensions.
    Maintains aspect ratio and handles various image formats.
    
    Args:
        input_path: Path to original image file
        output_path: Path where derivative should be saved
        max_width: Maximum width in pixels
        max_height: Maximum height in pixels
        quality: JPEG quality (0-100, default 85)
    
    Returns:
        (success, message) tuple
    """
    try:
        logger.info(f"Generating derivative: {output_path} (max {max_width}x{max_height})")
        
        # Open and process image
        with Image.open(input_path) as img:
            # Handle EXIF orientation
            img = ImageOps.exif_transpose(img)
            
            # Convert to RGB if necessary (for JPEG output)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparency
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
                img = background
            elif img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            
            # Create derivative maintaining aspect ratio
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # Save as JPEG
            img.save(output_path, 'JPEG', quality=quality, optimize=True)
            
            logger.info(f"Successfully created derivative: {output_path} ({img.size[0]}x{img.size[1]})")
            return True, f"✓ Created {os.path.basename(output_path)} ({img.size[0]}x{img.size[1]})"
            
    except FileNotFoundError:
        logger.error(f"Input file not found: {input_path}")
        return False, f"Input file not found: {input_path}"
    except PermissionError:
        logger.error(f"Permission denied: {input_path}")
        return False, f"Permission denied: {input_path}"
    except Exception as e:
        logger.error(f"Error generating derivative: {str(e)}")
        return False, f"Error generating derivative: {str(e)}"


def generate_pdf_derivative(
    input_path: str,
    output_path: str,
    max_width: int,
    max_height: int,
    quality: int = 85,
    dpi: int = 150
) -> Tuple[bool, str]:
    """
    Generate a derivative image from the first page of a PDF.
    Uses PyMuPDF to render the first page, then creates a JPEG derivative.
    
    Args:
        input_path: Path to original PDF file
        output_path: Path where derivative should be saved
        max_width: Maximum width in pixels
        max_height: Maximum height in pixels
        quality: JPEG quality (0-100, default 85)
        dpi: DPI for PDF rendering (default 150)
    
    Returns:
        (success, message) tuple
    """
    try:
        logger.info(f"Generating PDF derivative: {output_path} (max {max_width}x{max_height}, DPI {dpi})")
        
        # Open the PDF
        pdf_document = fitz.open(input_path)
        
        if pdf_document.page_count == 0:
            logger.error(f"PDF has no pages: {input_path}")
            pdf_document.close()
            return False, "PDF has no pages"
        
        # Get first page
        page = pdf_document[0]
        
        # Calculate zoom factor to achieve desired DPI
        # PyMuPDF default is 72 DPI, so zoom = desired_dpi / 72
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        
        # Render page to pixmap (raster image)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        logger.info(f"PDF page rendered, size: {pix.width}x{pix.height}")
        
        # Convert pixmap to PIL Image
        img_data = pix.tobytes("jpeg")
        img = Image.open(io.BytesIO(img_data))
        
        # Close PDF
        pdf_document.close()
        
        logger.info(f"PDF converted to image, size: {img.size}")
        
        # Create derivative maintaining aspect ratio
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        
        logger.info(f"Derivative size after resize: {img.size}")
        
        # Save as JPEG
        img.save(output_path, 'JPEG', quality=quality, optimize=True)
        
        logger.info(f"Successfully created PDF derivative: {output_path} ({img.size[0]}x{img.size[1]})")
        return True, f"✓ Created {os.path.basename(output_path)} ({img.size[0]}x{img.size[1]}) from PDF"
        
    except FileNotFoundError:
        logger.error(f"Input PDF file not found: {input_path}")
        return False, f"Input PDF file not found: {input_path}"
    except fitz.FileDataError as e:
        logger.error(f"Invalid or corrupted PDF file: {str(e)}")
        return False, f"Invalid or corrupted PDF file: {str(e)}"
    except PermissionError:
        logger.error(f"Permission denied: {input_path}")
        return False, f"Permission denied: {input_path}"
    except Exception as e:
        logger.error(f"Error generating PDF derivative: {str(e)}")
        return False, f"Error generating PDF derivative: {str(e)}"


def main(page: ft.Page):
    page.title = "DART - Digital Asset Routing and Transformation"
    page.padding = 20
    page.window.width = 1050
    page.window.height = 900
    page.scroll = ft.ScrollMode.AUTO

    storage = PersistentStorage()
    logger.info("DART application started")
    
    # Kill switch for emergency stop of batch operations
    kill_switch = False
    
    # Setup logging in working directory if it exists
    working_dir = storage.get_ui_state("last_output_dir")
    if working_dir:
        if Path(working_dir).exists():
            setup_working_dir_logging(working_dir)
        else:
            logger.warning(f"Saved working directory does not exist: {working_dir}")

    # ------------------------------------------------------------------ helpers

    def add_log_message(text: str):
        """Prepend a timestamped line to the log output field and write to log file."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        existing = log_output.value or ""
        log_output.value = f"[{timestamp}] {text}\n{existing}"
        
        # Also write to log file for persistence
        # Determine log level based on message prefix
        if text.startswith("[ERROR]") or text.startswith("✗") or "Error:" in text:
            logger.error(text)
        elif text.startswith("[WARN]") or text.startswith("⚠"):
            logger.warning(text)
        elif text.startswith("[SUCCESS]") or text.startswith("✓") or text.startswith("✅"):
            logger.info(text)
        elif text.startswith("[DEBUG]"):
            logger.debug(text)
        else:
            logger.info(text)
        
        page.update()

    def update_status(message: str, is_error: bool = False, log_clickable: bool = False):
        """Update the status, optionally with clickable log link."""
        color = ft.Colors.RED_700 if is_error else ft.Colors.BLACK
        
        if log_clickable:
            # Create a row with message and clickable "check log" link
            status_container.content = ft.Row(
                controls=[
                    ft.Text(
                        message,
                        color=color,
                        size=14,
                    ),
                    ft.TextButton(
                        "check log",
                        on_click=on_view_full_log_click,
                        style=ft.ButtonStyle(padding=0),
                    ),
                ],
                spacing=5,
                wrap=True,
            )
        else:
            # Simple text status
            status_container.content = ft.Text(
                message,
                color=color,
                size=14,
            )
        
        add_log_message(message)
        page.update()

    def on_copy_status_click(e):
        """Copy status text to clipboard."""
        # Extract text from status_container content
        status_text_value = ""
        if isinstance(status_container.content, ft.Text):
            status_text_value = status_container.content.value or ""
        elif isinstance(status_container.content, ft.Row):
            # Get text from first control (Text widget)
            if status_container.content.controls:
                first_control = status_container.content.controls[0]
                if isinstance(first_control, ft.Text):
                    status_text_value = first_control.value or ""
        
        if status_text_value:
            page.set_clipboard(status_text_value)
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
    
    def on_view_full_log_click(e):
        """Open full log file in read-only popup dialog."""
        global log_filename
        try:
            with open(log_filename, 'r', encoding='utf-8') as f:
                log_content = f.read()
            
            def close_log_dialog(e):
                log_dialog.open = False
                page.update()
            
            log_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(f"Full Log File: {Path(log_filename).name}", weight=ft.FontWeight.BOLD),
                content=ft.Container(
                    content=ft.TextField(
                        value=log_content,
                        multiline=True,
                        read_only=True,
                        text_size=11,
                        border=ft.InputBorder.NONE,
                    ),
                    width=800,
                    height=600,
                ),
                actions=[ft.TextButton("Close", on_click=close_log_dialog)],
            )
            
            page.overlay.append(log_dialog)
            log_dialog.open = True
            page.update()
        except Exception as ex:
            logger.error(f"Could not open log file: {ex}")
            update_status(f"Error opening log: {ex}", is_error=True)

    def get_stable_path(full_path: str) -> str:
        """Extract stable path by removing /Volumes/<mount>/ prefix for network-agnostic ID mapping.
        
        This allows file-to-ID mappings to persist across network mount changes.
        
        Examples:
            /Volumes/OldMount/photos/image.jpg -> photos/image.jpg
            /Volumes/NewMount/photos/image.jpg -> photos/image.jpg (same stable path!)
            /Users/local/photos/image.jpg -> /Users/local/photos/image.jpg (unchanged)
        """
        path_obj = Path(full_path)
        
        # Check if path starts with /Volumes/ (network mount on macOS)
        if len(path_obj.parts) >= 3 and path_obj.parts[0] == '/' and path_obj.parts[1] == 'Volumes':
            # Remove /Volumes/<mount_name>/ and return the rest
            stable = Path(*path_obj.parts[3:])  # Skip /, Volumes, and mount name
            logger.debug(f"[STABLE PATH] {full_path} → {stable}")
            return str(stable)
        
        # For local paths, return as-is
        return full_path
    
    def on_kill_switch_click(e):
        """Handle Kill Switch button click - emergency stop for batch operations."""
        nonlocal kill_switch
        logger.warning("KILL SWITCH ACTIVATED")
        kill_switch = True
        add_log_message("⚠️ KILL SWITCH ACTIVATED - Stopping batch operation")
        update_status("⚠️ Kill switch activated - stopping after current file", True)

    def validate_directories():
        """Validate that configured directories exist and show warnings if not."""
        warnings = []
        
        # Check input directory
        input_dir = input_dir_field.value
        if input_dir:
            if not Path(input_dir).exists():
                warnings.append(f"⚠️ Inputs folder does not exist (may be unmounted): {input_dir}")
                logger.warning(f"Input directory not accessible: {input_dir}")
        
        # Check output directory  
        output_dir = output_dir_field.value
        if output_dir:
            if not Path(output_dir).exists():
                warnings.append(f"⚠️ Working/Outputs folder does not exist (may be unmounted): {output_dir}")
                logger.warning(f"Output directory not accessible: {output_dir}")
        
        # Display warnings if any
        if warnings:
            for warning in warnings:
                add_log_message(warning)
            update_status(f"{len(warnings)} directory warning(s) -", is_error=True, log_clickable=True)
        
        return len(warnings) == 0

    # ------------------------------------------------------------------ UI state

    current_directory = None
    input_dir = storage.get_ui_state("last_input_dir")
    if input_dir:
        if Path(input_dir).exists():
            current_directory = Path(input_dir)
        else:
            logger.warning(f"Saved input directory does not exist (may be unmounted): {input_dir}")

    dirs_expanded = True

    # ------------------------------------------------------------------ directory selection

    def on_input_dir_result(e: ft.FilePickerResultEvent):
        nonlocal current_directory
        if e.path:
            path = Path(e.path)
            if not path.exists():
                update_status(f"Error: Directory does not exist: {e.path}", is_error=True)
                return
            current_directory = path
            input_dir_field.value = str(current_directory)
            storage.set_ui_state("last_input_dir", str(current_directory))
            update_status(f"Inputs folder set: {current_directory.name}")
            page.update()

    def on_output_dir_result(e: ft.FilePickerResultEvent):
        if e.path:
            path = Path(e.path)
            if not path.exists():
                update_status(f"Error: Directory does not exist: {e.path}", is_error=True)
                return
            output_dir_field.value = e.path
            storage.set_ui_state("last_output_dir", e.path)
            update_status(f"Outputs folder set: {path.name}")
            
            # Reconfigure logging to use the working directory
            setup_working_dir_logging(e.path)
            
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
    
    def clear_file_selection(e):
        """Clear the current file selection."""
        storage.set_ui_state("last_file", "")
        storage.set_ui_state("last_files", "")
        file_field.value = ""
        update_status("File selection cleared")
        page.update()

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
            width=500,
            read_only=False,
        )
        
        csv_validation_text = ft.Text(
            "",
            size=11,
            color=ft.Colors.GREY_700,
            visible=False,
        )
        
        # Validate existing CSV if one is set
        existing_csv = settings.get("csv_structure_file", "")
        if existing_csv:
            valid, msg, fields = validate_csv_structure(existing_csv)
            csv_validation_text.value = msg
            csv_validation_text.color = ft.Colors.GREEN if valid else ft.Colors.RED
            csv_validation_text.visible = True
        
        def on_csv_picker_result(picker_event: ft.FilePickerResultEvent):
            """Handle CSV file picker result."""
            if picker_event.files and len(picker_event.files) > 0:
                csv_path = picker_event.files[0].path
                csv_structure_field.value = csv_path
                
                # Validate the selected CSV
                valid, msg, fields = validate_csv_structure(csv_path)
                csv_validation_text.value = msg
                csv_validation_text.color = ft.Colors.GREEN if valid else ft.Colors.RED
                csv_validation_text.visible = True
                
                # Auto-populate core CSV if it's empty
                if not core_csv_field.value or not core_csv_field.value.strip():
                    core_csv_field.value = csv_path
                    # Validate the auto-populated core CSV
                    core_valid, core_msg = validate_core_metadata_csv(csv_path, csv_path)
                    core_csv_validation_text.value = core_msg
                    core_csv_validation_text.color = ft.Colors.GREEN if core_valid else ft.Colors.RED
                    core_csv_validation_text.visible = True
                    add_log_message(f"Auto-populated core metadata CSV from template: {Path(csv_path).name}")
                    logger.info(f"Auto-populated core_metadata_csv from template: {csv_path}")
                
                page.update()
        
        csv_picker = ft.FilePicker(on_result=on_csv_picker_result)
        page.overlay.append(csv_picker)
        
        def browse_csv_click(evt):
            """Open file picker for CSV selection."""
            csv_picker.pick_files(
                dialog_title="Select CSV Structure File",
                allowed_extensions=["csv"],
                allow_multiple=False,
            )
        
        csv_browse_button = ft.ElevatedButton(
            "Browse...",
            on_click=browse_csv_click,
            height=40,
        )
        
        # Core Metadata CSV field with picker
        core_csv_field = ft.TextField(
            label="core_metadata_csv",
            value=str(settings.get("core_metadata_csv", "")),
            hint_text="Path to core/controlling metadata CSV file (optional)",
            width=500,
            read_only=False,
        )
        
        core_csv_validation_text = ft.Text(
            "",
            size=11,
            color=ft.Colors.GREY_700,
            visible=False,
        )
        
        # Validate existing core CSV if one is set
        existing_core_csv = settings.get("core_metadata_csv", "")
        if existing_core_csv:
            valid, msg = validate_core_metadata_csv(existing_core_csv, existing_csv)
            core_csv_validation_text.value = msg
            core_csv_validation_text.color = ft.Colors.GREEN if valid else ft.Colors.RED
            core_csv_validation_text.visible = True
        
        def on_core_csv_picker_result(picker_event: ft.FilePickerResultEvent):
            """Handle core CSV file picker result."""
            if picker_event.files and len(picker_event.files) > 0:
                core_csv_path = picker_event.files[0].path
                core_csv_field.value = core_csv_path
                
                # Validate the selected core CSV
                template_path = csv_structure_field.value
                valid, msg = validate_core_metadata_csv(core_csv_path, template_path)
                core_csv_validation_text.value = msg
                core_csv_validation_text.color = ft.Colors.GREEN if valid else ft.Colors.RED
                core_csv_validation_text.visible = True
                page.update()
        
        core_csv_picker = ft.FilePicker(on_result=on_core_csv_picker_result)
        page.overlay.append(core_csv_picker)
        
        def browse_core_csv_click(evt):
            """Open file picker for core CSV selection."""
            core_csv_picker.pick_files(
                dialog_title="Select Core Metadata CSV File",
                allowed_extensions=["csv"],
                allow_multiple=False,
            )
        
        core_csv_browse_button = ft.ElevatedButton(
            "Browse...",
            on_click=browse_core_csv_click,
            height=40,
        )
        
        azure_storage_field = ft.TextField(
            label="azure_blob_storage_path",
            value=str(settings.get("azure_blob_storage_path", "")),
            hint_text="Azure Blob Storage path (must contain /objs/ folder)",
            width=500,
        )
        
        azure_path_validation_text = ft.Text(
            "",
            size=11,
            color=ft.Colors.GREY_700,
            visible=False,
        )
        
        # Validate existing Azure path if one is set
        existing_azure_path = settings.get("azure_blob_storage_path", "")
        if existing_azure_path:
            valid, msg = validate_azure_path(existing_azure_path)
            azure_path_validation_text.value = msg
            azure_path_validation_text.color = ft.Colors.GREEN if valid else ft.Colors.RED
            azure_path_validation_text.visible = True
        
        def on_azure_path_change(e):
            """Validate Azure path when field value changes."""
            path_value = azure_storage_field.value or ""
            if path_value.strip():
                valid, msg = validate_azure_path(path_value)
                azure_path_validation_text.value = msg
                azure_path_validation_text.color = ft.Colors.GREEN if valid else ft.Colors.RED
                azure_path_validation_text.visible = True
            else:
                azure_path_validation_text.visible = False
            page.update()
        
        azure_storage_field.on_change = on_azure_path_change
        
        azure_connection_field = ft.TextField(
            label="azure_connection_string",
            value=str(settings.get("azure_connection_string", "")),
            hint_text="Azure Storage connection string (encrypted)",
            password=True,
            can_reveal_password=True,
            width=500,
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
            
            # Validate CSV structure if provided
            csv_file_path = (csv_structure_field.value or "").strip()
            if csv_file_path:
                valid, msg, fields = validate_csv_structure(csv_file_path)
                if not valid:
                    update_status(f"CSV structure validation error: {msg}", is_error=True)
                    csv_validation_text.value = msg
                    csv_validation_text.color = ft.Colors.RED
                    csv_validation_text.visible = True
                    page.update()
                    return
                else:
                    add_log_message(f"CSV structure validated: {msg}")
                    logger.info(f"CSV structure validated: {csv_file_path} - {msg}")
            
            # Validate core metadata CSV if provided
            core_csv_path = (core_csv_field.value or "").strip()
            if core_csv_path:
                valid, msg = validate_core_metadata_csv(core_csv_path, csv_file_path)
                if not valid:
                    update_status(f"Core CSV validation error: {msg}", is_error=True)
                    core_csv_validation_text.value = msg
                    core_csv_validation_text.color = ft.Colors.RED
                    core_csv_validation_text.visible = True
                    page.update()
                    return
                else:
                    add_log_message(f"Core metadata CSV validated: {msg}")
                    logger.info(f"Core CSV validated: {core_csv_path} - {msg}")
            
            # Copy CSV files to working directory if they're not already there
            # Handle case where both files might be the same
            files_to_copy = {}
            if csv_file_path:
                files_to_copy['template'] = csv_file_path
            if core_csv_path and core_csv_path != csv_file_path:
                files_to_copy['core'] = core_csv_path
            elif core_csv_path and core_csv_path == csv_file_path:
                # Both are the same file - copy once, use for both
                files_to_copy['both'] = csv_file_path
            
            copied_template_path = csv_file_path
            copied_core_path = core_csv_path
            
            for file_type, file_path in files_to_copy.items():
                new_path, was_copied, copy_msg = copy_csv_to_working_dir(file_path, working_dir, file_type)
                if copy_msg:
                    add_log_message(copy_msg)
                    logger.info(copy_msg)
                
                if was_copied:
                    if file_type == 'template':
                        copied_template_path = new_path
                        csv_structure_field.value = new_path
                    elif file_type == 'core':
                        copied_core_path = new_path
                        core_csv_field.value = new_path
                    elif file_type == 'both':
                        # Same file used for both - update both paths
                        copied_template_path = new_path
                        copied_core_path = new_path
                        csv_structure_field.value = new_path
                        core_csv_field.value = new_path
                        add_log_message(f"Both template and core CSV point to the same file: {Path(new_path).name}")
            
            # Update validation displays if paths changed
            if copied_template_path != csv_file_path:
                csv_file_path = copied_template_path
            if copied_core_path != core_csv_path:
                core_csv_path = copied_core_path
            
            page.update()

            # Validate Azure path before saving
            azure_path_value = (azure_storage_field.value or "").strip()
            if azure_path_value:
                valid, msg = validate_azure_path(azure_path_value)
                if not valid:
                    update_status(f"Azure path validation failed: {msg}", is_error=True)
                    return

            new_settings = {
                "group_compound_objects": parsed_group_compound,
                "use_working_folder_for_file_selection": parsed_use_working_folder,
                "csv_structure_file": csv_file_path,
                "core_metadata_csv": core_csv_path,
                "azure_blob_storage_path": azure_path_value,
                "azure_connection_string": (azure_connection_field.value or "").strip(),
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
                        group_compound_field,
                        use_working_folder_field,
                        ft.Container(height=8),
                        ft.Text(
                            "CSV File Settings:",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Row(
                            controls=[
                                csv_structure_field,
                                csv_browse_button,
                            ],
                            alignment=ft.MainAxisAlignment.START,
                        ),
                        csv_validation_text,
                        ft.Row(
                            controls=[
                                core_csv_field,
                                core_csv_browse_button,
                            ],
                            alignment=ft.MainAxisAlignment.START,
                        ),
                        core_csv_validation_text,
                        ft.Container(height=8),
                        azure_storage_field,
                        azure_path_validation_text,
                        ft.Container(height=8),
                        ft.Text(
                            "Azure Storage (encrypted):",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                        ),
                        azure_connection_field,
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

    def analyze_compound_objects(objects, group_compound, file_to_id_map, page):
        """
        Analyze objects for compound grouping patterns and assign parent/child relationships.
        
        This function performs three-pass analysis:
        1. Parse filenames to extract prefixes and sequence numbers
        2. Match unnumbered files to numbered prefixes
        3. Find common prefixes among remaining unnumbered files
        
        Args:
            objects: List of object dicts with objectid, filepath, filename
            group_compound: Boolean, whether to perform compound grouping
            file_to_id_map: Dict of existing file/compound ID mappings
            page: Flet page object for ID generation
            
        Returns:
            tuple: (compound_objects, file_to_id_map, new_mappings, reused_mappings)
                - compound_objects: List of compound parent objects created
                - file_to_id_map: Updated mapping dict (with new compound IDs)
                - new_mappings: Count of new compound IDs created
                - reused_mappings: Count of existing compound IDs reused
                
        Side effects:
            Modifies objects in place, adding: parentid, type, sequence_number
        """
        compound_objects = []
        compound_new_mappings = 0
        compound_reused_mappings = 0
        
        if not group_compound:
            # No compound grouping - all objects are standalone
            add_log_message(f"[DEBUG] Compound grouping DISABLED - all objects standalone")
            for obj in objects:
                obj["parentid"] = None
                obj["type"] = "single"
            return compound_objects, file_to_id_map, compound_new_mappings, compound_reused_mappings
        
        add_log_message(f"[DEBUG] Compound grouping ENABLED - analyzing filename patterns")
        logger.info("[DEBUG] Starting compound object analysis")
        
        # FIRST PASS: Parse all filenames to extract prefix and number components
        parsed_files = []
        numbered_prefixes = set()  # Track prefixes from numbered files
        
        for obj in objects:
            stem = Path(obj['filename']).stem
            
            # Extract prefix and trailing sequence number
            # Pattern: everything before the LAST number is the prefix, last number is sequence
            match = re.match(r'^(.+?)[\s_\-]*(\d+)$', stem)
            if match:
                prefix = match.group(1).strip().lower()  # Normalize: lowercase, strip whitespace
                number = int(match.group(2))
                numbered_prefixes.add(prefix)
                parsed_files.append({
                    'obj': obj,
                    'prefix': prefix,
                    'number': number,
                    'filename': obj['filename'],
                    'raw_stem': stem
                })
                logger.info(f"[PARSE] '{obj['filename']}' → prefix: '{prefix}', number: {number}")
            else:
                # No trailing number - defer prefix assignment
                parsed_files.append({
                    'obj': obj,
                    'prefix': None,  # Will be assigned in second pass
                    'number': None,
                    'filename': obj['filename'],
                    'raw_stem': stem
                })
                logger.info(f"[PARSE] '{obj['filename']}' → no trailing number (defer prefix assignment)")
        
        # SECOND PASS: For unnumbered files, find matching prefix from numbered files
        logger.info(f"[PREFIX MATCHING] Found {len(numbered_prefixes)} numbered prefixes: {sorted(numbered_prefixes)}")
        
        for pf in parsed_files:
            if pf['prefix'] is None:  # Unnumbered file needing prefix assignment
                stem_lower = pf['raw_stem'].strip().lower()
                best_match = None
                best_match_length = 0
                
                # Check if this stem starts with any known numbered prefix
                for known_prefix in numbered_prefixes:
                    if stem_lower.startswith(known_prefix):
                        # Verify there's a separator or end after prefix (not just substring match)
                        remainder = stem_lower[len(known_prefix):]
                        if not remainder or remainder[0] in [' ', '_', '-']:
                            # Valid match - track longest match
                            if len(known_prefix) > best_match_length:
                                best_match = known_prefix
                                best_match_length = len(known_prefix)
                
                if best_match:
                    pf['prefix'] = best_match
                    logger.info(f"[PREFIX MATCH] '{pf['filename']}' matched prefix '{best_match}' (common with numbered files)")
                else:
                    # No match - use full stem as its own prefix (may be refined in pass 3)
                    pf['prefix'] = stem_lower
                    logger.info(f"[PREFIX MATCH] '{pf['filename']}' → no match, using full stem: '{stem_lower}'")
        
        # THIRD PASS: Find common prefixes among remaining unnumbered files
        unmatched = [pf for pf in parsed_files if pf['number'] is None and pf['prefix'] not in numbered_prefixes]
        
        logger.info(f"[THIRD PASS] Total parsed files: {len(parsed_files)}")
        logger.info(f"[THIRD PASS] Unnumbered files: {len([pf for pf in parsed_files if pf['number'] is None])}")
        logger.info(f"[THIRD PASS] Numbered prefixes known: {sorted(numbered_prefixes)}")
        logger.info(f"[THIRD PASS] Unmatched files (for Pass 3): {len(unmatched)}")
        add_log_message(f"[THIRD PASS] Checking {len(unmatched)} unmatched unnumbered files for common patterns")
        
        if len(unmatched) >= 2:
            logger.info(f"[COMMON PREFIX SEARCH] Analyzing {len(unmatched)} unmatched files for common patterns")
            add_log_message(f"[COMMON PREFIX SEARCH] Analyzing {len(unmatched)} unmatched files")
            
            # List all unmatched files for debugging
            for pf in unmatched:
                logger.info(f"[COMMON PREFIX SEARCH] Unmatched file: '{pf['filename']}' with prefix: '{pf['prefix']}'")
            
            # Build a map of potential base prefixes
            potential_bases = {}
            for pf in unmatched:
                stem = pf['prefix']
                # Try to extract base by removing last word after separator
                match = re.match(r'^(.+)[\s_\-]+\w+$', stem)
                if match:
                    # Strip whitespace AND trailing separators to normalize
                    potential_base = match.group(1).strip().rstrip(' _-')
                    logger.info(f"[COMMON PREFIX] '{pf['filename']}' (stem: '{stem}') → potential base: '{potential_base}'")
                    if len(potential_base) >= 3:
                        if potential_base not in potential_bases:
                            potential_bases[potential_base] = []
                        potential_bases[potential_base].append(pf)
                else:
                    logger.info(f"[COMMON PREFIX] '{pf['filename']}' (stem: '{stem}') → NO MATCH for base extraction regex")
            
            logger.info(f"[COMMON PREFIX] Found {len(potential_bases)} potential base(s): {list(potential_bases.keys())}")
            
            # Apply common base to files that share it (2+ files with same base)
            for base, files in potential_bases.items():
                if len(files) >= 2:
                    msg = f"[COMMON PREFIX] Found {len(files)} files sharing base: '{base}'"
                    logger.info(msg)
                    add_log_message(msg)
                    for pf in files:
                        old_prefix = pf['prefix']
                        pf['prefix'] = base
                        logger.info(f"[COMMON PREFIX] '{pf['filename']}' → prefix changed from '{old_prefix}' to '{base}'")
        
        # Group by prefix (must be 3+ characters for grouping)
        prefix_groups = {}
        for pf in parsed_files:
            prefix = pf['prefix']
            # Only group if prefix is 3+ characters (weighted matching)
            if len(prefix) >= 3:
                if prefix not in prefix_groups:
                    prefix_groups[prefix] = []
                prefix_groups[prefix].append(pf)
        
        # Analyze each prefix group for patterns
        add_log_message(f"[GROUP ANALYSIS] Found {len(prefix_groups)} prefix groups (3+ char prefixes)")
        logger.info(f"[GROUP ANALYSIS] Analyzing {len(prefix_groups)} prefix groups")
        
        groups = {}
        for prefix, items in prefix_groups.items():
            # Extract numbers from this group
            numbers = [item['number'] for item in items if item['number'] is not None]
            
            if len(items) < 2:
                # Single file with this prefix - don't group
                logger.info(f"[GROUP: '{prefix}'] Single file only - not creating compound")
                continue
            
            # Analyze numbering pattern
            is_sequential = False
            zero_pad_width = 0
            analysis_msg = f"[GROUP: '{prefix}'] {len(items)} files ({len(numbers)} numbered, {len(items)-len(numbers)} unnumbered)"
            add_log_message(analysis_msg)
            logger.info(analysis_msg)
            
            if len(numbers) >= 2:
                # Check if numbers form a sequence
                numbers_sorted = sorted(numbers)
                gaps = [numbers_sorted[i+1] - numbers_sorted[i] for i in range(len(numbers_sorted)-1)]
                max_gap = max(gaps)
                avg_gap = sum(gaps) / len(gaps)
                
                # Calculate zero-padding width based on max number
                max_number = max(numbers_sorted)
                zero_pad_width = len(str(max_number))
                
                # Sequential if average gap ≤ 2 and max gap ≤ 5 (allows small missing numbers)
                if avg_gap <= 2.0 and max_gap <= 5:
                    is_sequential = True
                    msg = f"  ✓ SEQUENTIAL pattern detected: range {min(numbers)}-{max(numbers)}, avg gap {avg_gap:.1f}, max gap {max_gap}"
                    add_log_message(msg)
                    logger.info(msg)
                    
                    # Report zero-padding recommendation
                    msg = f"  → Sequence numbers will be zero-padded to {zero_pad_width} digits (e.g., {str(min(numbers)).zfill(zero_pad_width)}, {str(max(numbers)).zfill(zero_pad_width)})"
                    add_log_message(msg)
                    logger.info(msg)
                    
                    if max_gap > 1:
                        missing_count = sum(1 for g in gaps if g > 1)
                        msg = f"  ℹ Note: {missing_count} gap(s) in sequence (e.g., missing numbers)"
                        add_log_message(msg)
                        logger.info(msg)
                else:
                    msg = f"  ✗ Not sequential: avg gap {avg_gap:.1f}, max gap {max_gap} (too irregular)"
                    add_log_message(msg)
                    logger.info(msg)
            elif len(numbers) == 1:
                msg = f"  • Mixed: 1 numbered file + {len(items)-1} unnumbered files with same prefix"
                add_log_message(msg)
                logger.info(msg)
                zero_pad_width = len(str(numbers[0]))  # Use single number's width
            else:
                msg = f"  • All files unnumbered but share common prefix (3+ chars: '{prefix}')"
                add_log_message(msg)
                logger.info(msg)
            
            # Decision: Group if 2+ files share prefix (3+ chars)
            msg = f"  ➤ DECISION: Creating compound (common prefix '{prefix}', {len(items)} files)"
            add_log_message(msg)
            logger.info(msg)
            
            # Store group with padding info
            groups[prefix] = {
                'files': [item['obj'] for item in items],
                'zero_pad_width': zero_pad_width,
                'items': items  # Keep parsed items for sorting
            }
        
        # Create compound objects for groups with 2+ files
        for text_base, group_data in groups.items():
            group_files = group_data['files']
            zero_pad_width = group_data['zero_pad_width']
            
            if len(group_files) >= 2:
                # Get the folder path from the first child (all children should be in same folder)
                folder_path = str(Path(group_files[0]['filepath']).parent)
                
                # Create a compound key using stable path (folder + text_base) for network-agnostic mapping
                stable_folder = get_stable_path(folder_path)
                compound_key = f"{stable_folder}::COMPOUND::{text_base}"
                
                # Check if this compound already has an assigned ID
                if compound_key in file_to_id_map:
                    # Reuse existing compound ID
                    compound_id = file_to_id_map[compound_key]
                    compound_reused_mappings += 1
                    add_log_message(f"[DEBUG] Reusing existing compound ID {compound_id} for '{text_base}' in {folder_path}")
                    logger.info(f"[DEBUG] Reused compound: {compound_id} | Folder: {folder_path} | Base: '{text_base}'")
                else:
                    # Generate new compound object ID
                    compound_id = generate_unique_id(page)
                    file_to_id_map[compound_key] = compound_id
                    compound_new_mappings += 1
                    add_log_message(f"[DEBUG] Created new compound {compound_id} for '{text_base}' in {folder_path}")
                    logger.info(f"[DEBUG] New compound: {compound_id} | Folder: {folder_path} | Base: '{text_base}'")
                
                # Sort children to determine the deterministic "first" child for filename indexing
                # Numbered children first (by sequence), then unnumbered (alphabetically)
                parsed_items = group_data['items']
                numbered_items = [item for item in parsed_items if item.get('number') is not None]
                unnumbered_items = [item for item in parsed_items if item.get('number') is None]
                numbered_items.sort(key=lambda x: x['number'])
                unnumbered_items.sort(key=lambda x: x['filename'])
                sorted_items = numbered_items + unnumbered_items
                
                # Use first child's filename as the compound's filename index (will be prefixed with _ in CSV)
                first_child_filename = sorted_items[0]['filename']
                
                # Extract display text_base from first child's raw stem (preserves original case)
                # The lowercase text_base is used for grouping, but display_text_base preserves case
                first_raw_stem = sorted_items[0]['raw_stem']
                prefix_length = len(text_base)
                
                # Extract the first prefix_length characters from raw_stem to get original case
                if len(first_raw_stem) >= prefix_length:
                    display_text_base = first_raw_stem[:prefix_length]
                else:
                    display_text_base = first_raw_stem
                
                compound_objects.append({
                    "objectid": compound_id,
                    "text_base": text_base,  # Lowercase version for internal use
                    "display_text_base": display_text_base,  # Original case for display/titles
                    "child_count": len(group_files),
                    "folder_path": folder_path,
                    "zero_pad_width": zero_pad_width,
                    "type": "compound",
                    "first_child_filename": first_child_filename
                })
                
                # Assign this compound ID as parentid to all children
                # Also store sequence numbers from parsed data for display
                # Use sorted_items to maintain consistent ordering
                for parsed_item in sorted_items:
                    child_obj = parsed_item['obj']
                    child_obj["parentid"] = compound_id
                    child_obj["type"] = "child"
                    child_obj["sequence_number"] = parsed_item.get('number')  # Store for display
                
                logger.info(f"[DEBUG] Compound: {compound_id} | Base: '{text_base}' | Folder: {folder_path} | Children: {[f['filename'] for f in group_files]}")
            else:
                # Single file - not part of a compound
                group_files[0]["parentid"] = None
                group_files[0]["type"] = "single"
                logger.info(f"[DEBUG] Single object (no compound): {group_files[0]['filename']}")
        
        add_log_message(f"[DEBUG] Compound analysis complete: {len(compound_objects)} compounds created")
        logger.info(f"[DEBUG] Total compound objects: {len(compound_objects)}")
        
        return compound_objects, file_to_id_map, compound_new_mappings, compound_reused_mappings

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
            # Use stable path (without /Volumes/<mount>/) as lookup key for network-agnostic mapping
            stable_path = get_stable_path(file_path_str)
            
            # Check if this file already has an assigned ID (using stable path as key)
            if stable_path in file_to_id_map:
                # Reuse existing ID - never change once assigned!
                unique_id = file_to_id_map[stable_path]
                reused_mappings += 1
                logger.info(f"[DEBUG] Reusing existing: {unique_id} → {stable_path} (full: {file_path_str})")
            else:
                # Generate new unique DG identifier
                unique_id = generate_unique_id(page)
                file_to_id_map[stable_path] = unique_id
                new_mappings += 1
                logger.info(f"[DEBUG] Generated new: {unique_id} → {stable_path} (full: {file_path_str})")
            
            # Store both full path and display name
            objects.append({
                "objectid": unique_id,
                "filepath": file_path_str,  # Keep full current path for file access
                "filename": Path(file_path_str).name,
            })

        add_log_message(f"[DEBUG] IDs assigned: {new_mappings} new, {reused_mappings} reused")
        logger.info(f"[DEBUG] Total mappings in cache: {len(file_to_id_map)}")
        
        # Process compound object grouping if enabled (using shared function)
        compound_objects, file_to_id_map, compound_new, compound_reused = analyze_compound_objects(
            objects, group_compound, file_to_id_map, page
        )
        
        # Update mapping counts
        new_mappings += compound_new
        reused_mappings += compound_reused
        
        # Save updated file-to-ID mappings (save whenever files were processed)
        if working_dir and (new_mappings > 0 or reused_mappings > 0):
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
            update_status("Error: Duplicate object IDs detected -", is_error=True, log_clickable=True)
            
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
        total_objects = len(objects) + len(compound_objects)
        add_log_message(f"[DEBUG] Generated {len(objects)} file objects + {len(compound_objects)} compound objects = {total_objects} total")
        logger.info(f"[DEBUG] Uniqueness validated: All object IDs are unique")
        logger.info(f"[DEBUG] Final objects list: {objects}")
        logger.info(f"[DEBUG] Compound objects: {compound_objects}")
        
        result_lines = [f"Found {len(files)} digital asset file(s) {source_description}"]
        result_lines.append(f"Identifiers: {new_mappings} new, {reused_mappings} reused (IDs never change once assigned)")
        result_lines.append(f"Compound object grouping: {'ENABLED' if group_compound else 'DISABLED'}")
        
        if group_compound:
            result_lines.append(f"Total: {len(compound_objects)} compound objects, {len(objects)} file objects")
        
        result_lines.append("")
        
        # Display logic based on compound grouping
        if group_compound and compound_objects:
            # Group children by parentid for organized display
            children_by_parent = {}
            standalone = []
            
            for obj in objects:
                if obj.get("parentid"):
                    parent_id = obj["parentid"]
                    if parent_id not in children_by_parent:
                        children_by_parent[parent_id] = []
                    children_by_parent[parent_id].append(obj)
                else:
                    standalone.append(obj)
            
            # Display compound objects with their children
            for compound in compound_objects:
                zero_pad = compound.get('zero_pad_width', 0)
                display_name = compound.get('display_text_base', compound.get('text_base', ''))
                result_lines.append(f"📦 COMPOUND: {compound['objectid']} ('{display_name}' - {compound['child_count']} children)")
                result_lines.append(f"    Folder: {compound['folder_path']}")
                
                # Show children indented, sorted by sequence number
                if compound['objectid'] in children_by_parent:
                    children = children_by_parent[compound['objectid']]
                    
                    # Sort: numbered files by sequence, then unnumbered alphabetically
                    numbered = [c for c in children if c.get('sequence_number') is not None]
                    unnumbered = [c for c in children if c.get('sequence_number') is None]
                    numbered.sort(key=lambda x: x['sequence_number'])
                    unnumbered.sort(key=lambda x: x['filename'])
                    
                    for child in numbered + unnumbered:
                        seq_num = child.get('sequence_number')
                        if seq_num is not None and zero_pad > 0:
                            seq_display = f"[{str(seq_num).zfill(zero_pad)}]"
                            result_lines.append(f"    ↳ {child['objectid']} {seq_display} → {child['filename']}")
                        else:
                            result_lines.append(f"    ↳ {child['objectid']} → {child['filename']}")
                result_lines.append("")  # Blank line between compounds
            
            # Display standalone objects
            if standalone:
                result_lines.append("📄 STANDALONE OBJECTS:")
                for obj in standalone:
                    result_lines.append(f"• {obj['objectid']} → {obj['filename']}")
        else:
            # No compound grouping - simple list
            for obj in objects:
                result_lines.append(f"• {obj['objectid']} → {obj['filename']}")

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

        if group_compound and compound_objects:
            update_status(f"Analyzed {len(files)} file(s): {len(compound_objects)} compounds, {len(objects)} file objects")
            logger.info(f"Function 1: Analyzed {len(files)} files, created {len(compound_objects)} compounds + {len(objects)} file objects")
        else:
            update_status(f"Analyzed {len(files)} file(s), generated {len(objects)} unique object ID(s)")
            logger.info(f"Function 1: Analyzed {len(files)} files, generated {len(objects)} unique object IDs")

    def get_display_template(file_extension):
        """
        Map file extension to CollectionBuilder display_template value.
        
        Args:
            file_extension: File extension (with or without leading dot)
            
        Returns:
            str: CollectionBuilder display_template value (image, video, audio, pdf, record)
        """
        ext = file_extension.lower().lstrip('.')
        
        # Image formats → "image"
        if ext in ['jpg', 'jpeg', 'png', 'gif', 'tif', 'tiff', 'bmp', 'webp']:
            return 'image'
        
        # Video formats → "video"
        elif ext in ['mp4', 'mov', 'avi', 'mkv', 'wmv', 'flv', 'webm']:
            return 'video'
        
        # Audio formats → "audio"
        elif ext in ['mp3', 'wav', 'flac', 'aac', 'ogg', 'm4a', 'wma']:
            return 'audio'
        
        # PDF → "pdf"
        elif ext == 'pdf':
            return 'pdf'
        
        # Archives and other formats → "record"
        elif ext in ['zip', 'tar', 'gz', '7z', 'rar', 'bz2']:
            return 'record'
        
        # Unknown → empty (will use CB default)
        else:
            return ''

    def on_function_2_export_csv(e):
        """Function 2: Export analyzed assets to CSV using template structure."""
        nonlocal kill_switch
        kill_switch = False  # Reset kill switch at start of operation
        storage.record_function_usage("Function 2")

        # Check for working directory
        working_dir = output_dir_field.value
        if not working_dir or not Path(working_dir).exists():
            update_status("Error: Please set a working/outputs folder first", is_error=True)
            return

        # Load settings and check for CSV template
        settings, _ = load_app_settings(working_dir)
        csv_template_path = settings.get("csv_structure_file", "")
        
        if not csv_template_path or not Path(csv_template_path).exists():
            update_status("Error: CSV structure template not configured in settings", is_error=True)
            add_log_message("[ERROR] No CSV template found - configure in Function 0")
            return

        # Load CSV template to get column structure
        try:
            with open(csv_template_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                template_columns = reader.fieldnames
                add_log_message(f"[DEBUG] Loaded CSV template with {len(template_columns)} columns")
                logger.info(f"CSV template columns: {template_columns}")
        except Exception as ex:
            update_status(f"Error reading CSV template: {ex}", is_error=True)
            return

        # Check if Azure is configured and validate connection
        azure_path = settings.get("azure_blob_storage_path", "")
        azure_connection_string = settings.get("azure_connection_string", "")
        azure_enabled = False
        blob_service_client = None
        
        if azure_path and azure_connection_string:
            add_log_message("[INFO] Azure configuration detected, validating...")
            
            # Validate Azure path
            path_valid, path_msg = validate_azure_path(azure_path)
            if not path_valid:
                update_status(f"Azure path validation failed: {path_msg}", is_error=True)
                add_log_message(f"[ERROR] {path_msg}")
                return
            
            # Initialize Azure client
            success, client, msg = init_azure_client(azure_connection_string)
            if not success:
                logger.error(f"Azure connection failed: {msg}")
                update_status(f"Azure connection failed: {msg}", is_error=True)
                add_log_message(f"[ERROR] {msg}")
                return
            
            blob_service_client = client
            azure_enabled = True
            add_log_message(f"[SUCCESS] {msg}")
            add_log_message(f"[INFO] Azure uploads ENABLED - files will be uploaded to: {azure_path}")
        else:
            add_log_message("[INFO] Azure not configured - uploads disabled (CSV export only)")

        # Get files to process (similar to Function 1)
        group_compound = settings.get("group_compound_objects", False)
        
        asset_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.tif', '.tiff', '.bmp', '.webp',
            '.pdf',
            '.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm',
            '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma',
            '.zip', '.tar', '.gz', '.7z', '.rar', '.bz2',
        }

        selected_files = get_selected_files()
        files = []
        
        if selected_files:
            for file_path in selected_files:
                if file_path.is_file() and file_path.suffix.lower() in asset_extensions:
                    files.append(str(file_path))
        else:
            if not current_directory or not current_directory.exists():
                update_status("Error: Please select files or an inputs folder first", is_error=True)
                return
            
            for file_path in current_directory.glob("*"):
                if file_path.is_file() and file_path.suffix.lower() in asset_extensions:
                    files.append(str(file_path))

        if not files:
            update_status("Error: No digital asset files found to export", is_error=True)
            return

        files.sort()
        add_log_message(f"[DEBUG] Found {len(files)} files to export")

        # Load or generate object IDs (reuse Function 1 logic)
        file_to_id_map = settings.get("file_to_id_map", {})
        
        objects = []
        new_mappings = 0
        reused_mappings = 0
        
        for file_path_str in files:
            # Use stable path (without /Volumes/<mount>/) as lookup key for network-agnostic mapping
            stable_path = get_stable_path(file_path_str)
            
            if stable_path in file_to_id_map:
                unique_id = file_to_id_map[stable_path]
                reused_mappings += 1
            else:
                unique_id = generate_unique_id(page)
                file_to_id_map[stable_path] = unique_id
                new_mappings += 1
            
            file_path = Path(file_path_str)
            objects.append({
                "objectid": unique_id,
                "filepath": file_path_str,  # Keep full current path for file access
                "filename": file_path.name,
                "display_template": get_display_template(file_path.suffix),
                "format": file_path.suffix.lower().lstrip('.'),
                "parentid": None,  # Will be set if compound grouping enabled
            })
        
        add_log_message(f"[DEBUG] IDs: {new_mappings} new, {reused_mappings} reused")
        
        # Process compound object grouping if enabled (using shared function)
        compound_objects, file_to_id_map, compound_new, compound_reused = analyze_compound_objects(
            objects, group_compound, file_to_id_map, page
        )
        
        # Update mapping counts
        new_mappings += compound_new
        reused_mappings += compound_reused

        # Build object_location URLs and upload files to Azure if enabled
        upload_success_count = 0
        upload_skip_count = 0
        upload_fail_count = 0
        
        if azure_enabled and blob_service_client:
            # Ensure the target Azure container exists
            normalized_path = azure_path.strip().strip('/')
            path_parts = normalized_path.split('/', 1)
            container_name = path_parts[0]
            
            try:
                container_client = blob_service_client.get_container_client(container_name)
                if not container_client.exists():
                    container_client.create_container()
                    add_log_message(f"[INFO] Created Azure container: {container_name}")
                else:
                    add_log_message(f"[INFO] Azure container exists: {container_name}")
            except Exception as ex:
                error_msg = str(ex)
                if "ContainerAlreadyExists" in error_msg or "already exists" in error_msg.lower():
                    add_log_message(f"[INFO] Azure container exists: {container_name}")
                else:
                    add_log_message(f"[ERROR] Could not verify/create container {container_name}: {error_msg}")
                    azure_enabled = False  # Disable uploads if container check fails
            
            if azure_enabled:
                add_log_message(f"[INFO] Starting Azure uploads for {len(objects)} files...")
                
                for obj in objects:
                    # Check kill switch
                    if kill_switch:
                        logger.warning("Kill switch activated - stopping Azure uploads")
                        add_log_message("⚠️ Kill switch activated - Azure uploads stopped")
                        break
                    
                    object_id = obj['objectid']
                    file_path = obj['filepath']
                    file_extension = Path(file_path).suffix
                    
                    # Build object_location URL
                    success, url, msg = build_object_location(
                        azure_path,
                        object_id,
                        file_extension,
                        azure_connection_string
                    )
                    
                    if success:
                        obj['object_location'] = url
                        
                        # Check if file already exists in Azure before uploading
                        # Build blob name to check existence
                        normalized_path = azure_path.strip().strip('/')
                        path_parts = normalized_path.split('/', 1)
                        container_name = path_parts[0]
                        blob_path = path_parts[1] if len(path_parts) > 1 else ""
                        
                        if blob_path:
                            blob_name = f"{blob_path}/{object_id}{file_extension}"
                        else:
                            blob_name = f"{object_id}{file_extension}"
                        
                        try:
                            blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
                            file_exists = blob_client.exists()
                        except Exception as ex:
                            # If we can't check existence, assume it doesn't exist
                            add_log_message(f"  [WARN] Could not check if file exists in Azure: {ex}")
                            file_exists = False
                        
                        if file_exists:
                            # File already exists - skip upload
                            azure_filename = f"{object_id}{file_extension}"
                            add_log_message(f"  ⏩ {obj['filename']} ({azure_filename}) already exists in Azure - skipping upload")
                            logger.info(f"Skipped upload (file exists): {obj['filename']} → {blob_name}")
                            # Count as skipped
                            upload_skip_count += 1
                        else:
                            # Upload file to Azure
                            upload_success, upload_msg = upload_to_azure(
                                blob_service_client,
                                file_path,
                                azure_path,
                                object_id,
                                file_extension
                            )
                            
                            if upload_success:
                                upload_success_count += 1
                                add_log_message(f"[SUCCESS] {upload_msg}")
                            else:
                                upload_fail_count += 1
                                logger.error(f"Upload failed: {upload_msg}")
                                add_log_message(f"[ERROR] {upload_msg}")
                                # Still include object_location in CSV even if upload failed
                    else:
                        obj['object_location'] = ''
                        logger.error(f"Failed to build object_location: {msg}")
                        add_log_message(f"[ERROR] {msg}")
                
                logger.info(f"Azure upload complete: {upload_success_count} uploaded, {upload_skip_count} skipped (already exist), {upload_fail_count} failed")
                add_log_message(f"[INFO] Upload complete: {upload_success_count} uploaded, {upload_skip_count} skipped, {upload_fail_count} failed")
        else:
            # Azure not enabled - set empty object_location for all objects
            for obj in objects:
                obj['object_location'] = ''

        # Create CSV filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f"DART_export_{timestamp}.csv"
        csv_output_path = Path(working_dir) / csv_filename

        # Ensure 'filepath' column is included (required by Function 3 for derivative generation)
        export_columns = list(template_columns)
        if 'filepath' not in export_columns:
            # Insert filepath after filename for logical grouping
            if 'filename' in export_columns:
                filename_idx = export_columns.index('filename')
                export_columns.insert(filename_idx + 1, 'filepath')
            else:
                # No filename column? Add filepath at beginning
                export_columns.insert(0, 'filepath')
            add_log_message(f"[DEBUG] Added 'filepath' column to export (required for Function 3)")

        # Write CSV file
        try:
            with open(csv_output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=export_columns)
                writer.writeheader()
                
                # Write compound parent objects first (if compound grouping enabled)
                if group_compound and compound_objects:
                    for compound in compound_objects:
                        row = {}
                        for col in export_columns:
                            if col == 'objectid':
                                row[col] = compound.get('objectid', '')
                            elif col == 'filename':
                                # Use first child's filename with underscore prefix for indexing
                                # This maintains filename as source of truth for ALL objects
                                first_child = compound.get('first_child_filename', '')
                                row[col] = f"_{first_child}" if first_child else ''
                            elif col == 'filepath':
                                # Compound parents have no physical file
                                row[col] = ''
                            elif col == 'parentid':
                                # Compound objects have no parent
                                row[col] = ''
                            elif col == 'display_template':
                                # Set compound_object layout for parent
                                row[col] = 'compound_object'
                            elif col == 'title':
                                # Use display_text_base for title (preserves original case from filename)
                                row[col] = compound.get('display_text_base', '').replace('_', ' ').replace('-', ' ')
                            elif col == 'originating_system_id':
                                # Use display_text_base (common portion of compound family filenames)
                                row[col] = compound.get('display_text_base', '')
                            else:
                                row[col] = ''
                        
                        writer.writerow(row)
                
                # Write file objects (children or standalone)
                for obj in objects:
                    # Build row with template columns
                    row = {}
                    for col in export_columns:
                        # Map known fields
                        if col == 'objectid':
                            row[col] = obj.get('objectid', '')
                        elif col == 'filename':
                            row[col] = obj.get('filename', '')
                        elif col == 'filepath':
                            row[col] = obj.get('filepath', '')
                        elif col == 'parentid':
                            row[col] = obj.get('parentid', '')
                        elif col == 'display_template':
                            row[col] = obj.get('display_template', '')
                        elif col == 'format':
                            # Auto-populate format with MIME type based on file extension
                            filename = obj.get('filename', '')
                            if filename:
                                row[col] = get_mime_type(filename)
                            else:
                                row[col] = obj.get('format', '')
                        elif col == 'object_location':
                            row[col] = obj.get('object_location', '')
                        elif col == 'originating_system_id':
                            # Extract common portion of filename (prefix before numbers)
                            filename = obj.get('filename', '')
                            stem = Path(filename).stem
                            # Match pattern: text before last number
                            match = re.match(r'^(.+?)[\s_\-]*\d+$', stem)
                            if match:
                                # Preserve original case for originating_system_id
                                prefix = match.group(1).strip()
                                row[col] = prefix
                            else:
                                # No number found, use whole stem
                                row[col] = stem
                        else:
                            # Leave other columns empty for manual population
                            row[col] = ''
                    
                    writer.writerow(row)
            
            add_log_message(f"[SUCCESS] Exported {len(objects)} objects to {csv_filename}")
            logger.info(f"CSV export successful: {csv_output_path}")
            
            # Update settings with new mappings
            settings["file_to_id_map"] = file_to_id_map
            save_app_settings(working_dir, settings)
            
            total_rows = len(objects) + len(compound_objects)
            result_text = f"✅ CSV Export Successful\n\n"
            result_text += f"Exported: {total_rows} total rows\n"
            if group_compound and compound_objects:
                result_text += f"  • {len(compound_objects)} compound objects (parents)\n"
                result_text += f"  • {len(objects)} file objects (children/standalone)\n"
            else:
                result_text += f"  • {len(objects)} file objects\n"
            result_text += f"Template: {Path(csv_template_path).name}\n"
            result_text += f"Columns: {len(export_columns)}\n"
            result_text += f"Output: {csv_filename}\n"
            result_text += f"Location: {working_dir}\n"
            result_text += f"Compound grouping: {'ENABLED' if group_compound else 'DISABLED'}\n"
            
            # Add Azure upload information if enabled
            if azure_enabled:
                result_text += f"Azure uploads: {'ENABLED' if azure_enabled else 'DISABLED'}\n"
                if upload_success_count > 0 or upload_skip_count > 0 or upload_fail_count > 0:
                    result_text += f"  • Uploaded: {upload_success_count} new files\n"
                    if upload_skip_count > 0:
                        result_text += f"  • Skipped: {upload_skip_count} (already exist in Azure)\n"
                    if upload_fail_count > 0:
                        result_text += f"  • Failed: {upload_fail_count}\n"
                    result_text += f"  • Azure path: {azure_path}\n"
            else:
                result_text += f"Azure uploads: DISABLED (configure in Function 0)\n"
            
            result_text += f"\nAuto-populated fields:\n"
            result_text += f"• objectid (unique DG identifier)\n"
            result_text += f"• filename (original filename)\n"
            result_text += f"• filepath (full path to source file, for Function 3)\n"
            
            # List fields actually in the template
            populated_fields = ['objectid', 'filename', 'filepath']
            if 'parentid' in export_columns:
                result_text += f"• parentid (compound object parent ID)\n"
                populated_fields.append('parentid')
            if 'display_template' in export_columns:
                result_text += f"• display_template (CB layout: image/video/audio/pdf/compound_object)\n"
                populated_fields.append('display_template')
            if 'format' in export_columns:
                result_text += f"• format (file extension)\n"
                populated_fields.append('format')
            if 'object_location' in export_columns:
                if azure_enabled:
                    result_text += f"• object_location (Azure Blob Storage URL)\n"
                else:
                    result_text += f"• object_location (empty - Azure not configured)\n"
                populated_fields.append('object_location')
            if 'title' in export_columns and group_compound and compound_objects:
                result_text += f"• title (suggested title for compound objects)\n"
                populated_fields.append('title')
            
            result_text += f"\nEmpty fields ready for metadata:\n"
            empty_fields = [col for col in export_columns if col not in populated_fields]
            for field in empty_fields[:10]:  # Show first 10
                result_text += f"• {field}\n"
            if len(empty_fields) > 10:
                result_text += f"• ... and {len(empty_fields) - 10} more\n"

            def close_dialog(e):
                dialog.open = False
                page.update()

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Function 2: Export to CSV", weight=ft.FontWeight.BOLD),
                content=ft.Container(
                    content=ft.Text(result_text, selectable=True),
                    width=600,
                    height=500,
                ),
                actions=[ft.TextButton("Close", on_click=close_dialog)],
            )

            page.overlay.append(dialog)
            dialog.open = True
            page.update()

            update_status(f"✅ Exported {total_rows} rows to {csv_filename}")
            
        except Exception as ex:
            error_msg = f"Error writing CSV: {ex}"
            update_status(error_msg, is_error=True)
            add_log_message(f"[ERROR] {error_msg}")
            logger.error(error_msg)

    def on_function_3_generate_derivatives(e):
        """Function 3: Generate small and thumbnail derivatives and upload to Azure."""
        nonlocal kill_switch
        kill_switch = False  # Reset kill switch
        storage.record_function_usage("Function 3")

        # Check for working directory
        working_dir = output_dir_field.value
        if not working_dir or not Path(working_dir).exists():
            update_status("Error: Please set a valid working/outputs folder first (may be unmounted)", is_error=True)
            return
        
        # Check for input directory
        input_dir = input_dir_field.value
        if not input_dir or not Path(input_dir).exists():
            update_status("Error: Please set a valid inputs folder first (may be unmounted)", is_error=True)
            add_log_message("[ERROR] Input directory required for Function 3 to locate source files")
            return

        # Load settings
        settings, _ = load_app_settings(working_dir)
        
        # Check Azure configuration
        azure_path = settings.get("azure_blob_storage_path", "")
        azure_connection_string = settings.get("azure_connection_string", "")
        
        if not azure_path or not azure_connection_string:
            update_status("Error: Azure Blob Storage not configured. Configure in Function 0.", is_error=True)
            add_log_message("[ERROR] Azure configuration required for Function 3")
            return
        
        # Validate and initialize Azure client
        path_valid, path_msg = validate_azure_path(azure_path)
        if not path_valid:
            update_status(f"Azure path validation failed: {path_msg}", is_error=True)
            return
        
        success, blob_service_client, msg = init_azure_client(azure_connection_string)
        if not success:
            update_status(msg, is_error=True)
            return
        
        add_log_message(f"[INFO] {msg}")
        
        # Get input directory for fallback file lookup
        input_dir = input_dir_field.value
        input_directory = Path(input_dir) if input_dir and Path(input_dir).exists() else None
        if input_directory:
            add_log_message(f"[INFO] Input directory for file lookup: {input_directory}")
        else:
            add_log_message("[WARN] No input directory set - files must have valid filepath in CSV")
        
        # Find latest CSV export or let user select
        # Exclude derivative CSVs (which contain "with_derivatives") to avoid processing output as input
        all_csv_files = sorted(Path(working_dir).glob("DART_export_*.csv"), reverse=True)
        csv_files = [f for f in all_csv_files if "with_derivatives" not in f.name]
        if not csv_files:
            update_status("Error: No CSV exports found. Run Function 2 first.", is_error=True)
            return
        
        # Use the most recent CSV
        csv_path = csv_files[0]
        add_log_message(f"[INFO] Processing CSV: {csv_path.name}")
        
        # Read CSV
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = list(reader.fieldnames)
                rows = list(reader)
        except Exception as ex:
            update_status(f"Error reading CSV: {ex}", is_error=True)
            return
        
        # Add image_small and image_thumb columns if not present
        if 'image_small' not in fieldnames:
            fieldnames.append('image_small')
        if 'image_thumb' not in fieldnames:
            fieldnames.append('image_thumb')
        
        # Build base Azure paths for derivatives
        # Extract container and path from objs path
        normalized_path = azure_path.strip().strip('/')
        path_parts = normalized_path.split('/', 1)
        if len(path_parts) == 1:
            container = path_parts[0]
            base_path = ""
        else:
            container = path_parts[0]
            base_path = path_parts[1]
        
        # Create derivative containers by replacing 'objs' with 'smalls'/'thumbs'
        smalls_container = container.replace('objs', 'smalls')
        thumbs_container = container.replace('objs', 'thumbs')
        
        # Rebuild full paths with new containers
        smalls_azure_path = f"{smalls_container}/{base_path}" if base_path else smalls_container
        thumbs_azure_path = f"{thumbs_container}/{base_path}" if base_path else thumbs_container
        
        # Ensure derivative containers exist in Azure
        for container_name in [smalls_container, thumbs_container]:
            try:
                container_client = blob_service_client.get_container_client(container_name)
                if not container_client.exists():
                    container_client.create_container()
                    add_log_message(f"[INFO] Created Azure container: {container_name}")
                else:
                    add_log_message(f"[INFO] Azure container exists: {container_name}")
            except Exception as ex:
                # Container might already exist (race condition) or other error
                error_msg = str(ex)
                if "ContainerAlreadyExists" in error_msg or "already exists" in error_msg.lower():
                    add_log_message(f"[INFO] Azure container exists: {container_name}")
                else:
                    add_log_message(f"[WARN] Could not verify/create container {container_name}: {error_msg}")
        
        add_log_message(f"[INFO] Derivatives will be uploaded to:")
        add_log_message(f"  • Small: {smalls_azure_path}")
        add_log_message(f"  • Thumbs: {thumbs_azure_path}")
        
        # Process each row
        total_rows = len(rows)
        processed_count = 0
        skipped_count = 0
        small_success = 0
        small_fail = 0
        thumb_success = 0
        thumb_fail = 0
        
        # Create temp directory for derivatives
        temp_dir = Path(working_dir) / "temp_derivatives"
        temp_dir.mkdir(exist_ok=True)
        
        # Pre-scan to show what will be processed/skipped
        processable = 0
        no_filename = 0
        non_image = 0
        for row in rows:
            filename = row.get('filename', '').strip()
            if not filename:
                no_filename += 1
            elif filename.startswith('_'):
                # Compound parent (underscore-prefixed first child filename)
                no_filename += 1
            else:
                ext = Path(filename).suffix.lower()
                if ext not in {'.jpg', '.jpeg', '.png', '.gif', '.tif', '.tiff', '.bmp', '.webp', '.pdf'}:
                    non_image += 1
                else:
                    processable += 1
        
        add_log_message(f"[INFO] CSV Analysis: {total_rows} total rows")
        add_log_message(f"  • {processable} image/PDF files to process")
        if no_filename > 0:
            add_log_message(f"  • {no_filename} rows with no file (compound parents or metadata-only)")
        if non_image > 0:
            add_log_message(f"  • {non_image} non-image/PDF files (will be skipped)")
        
        add_log_message(f"[INFO] Processing {total_rows} rows...")
        
        for idx, row in enumerate(rows):
            # Check kill switch
            if kill_switch:
                add_log_message("⚠️ Kill switch activated - stopping derivative generation")
                break
            
            # Skip rows without files (compound parents have underscore-prefixed filenames)
            filename = row.get('filename', '').strip()
            if not filename:
                objectid = row.get('objectid', 'unknown')
                title = row.get('title', '')[:50] if row.get('title') else 'no title'
                add_log_message(f"[SKIP #{idx+1}] No filename (objectid: {objectid}, title: {title}...)")
                skipped_count += 1
                continue
            
            if filename.startswith('_'):
                # Compound parent (no physical file) - will populate derivatives after children processed
                skipped_count += 1
                continue
            
            # Skip non-image/PDF files
            ext = Path(filename).suffix.lower()
            if ext not in {'.jpg', '.jpeg', '.png', '.gif', '.tif', '.tiff', '.bmp', '.webp', '.pdf'}:
                add_log_message(f"[SKIP #{idx+1}] Non-image/PDF file: {filename}")
                skipped_count += 1
                continue
            
            objectid = row.get('objectid', '')
            if not objectid:
                add_log_message(f"[ERROR #{idx+1}] No object ID for {filename}")
                skipped_count += 1
                continue
            
            # Find source file
            source_path = Path(row.get('filepath', ''))
            if not source_path.exists() or not source_path.is_file():
                # Try to find it in input directory
                if input_directory:
                    source_path = input_directory / filename
                if not source_path.exists() or not source_path.is_file():
                    add_log_message(f"[ERROR #{idx+1}] Source file not found: {filename} (filepath: {row.get('filepath', 'empty')})")
                    skipped_count += 1
                    continue
            
            add_log_message(f"[{idx+1}/{total_rows}] Processing {filename} ({objectid})")
            
            # Check if derivatives already exist in Azure
            small_filename = f"{objectid}_SMALL.jpg"
            thumb_filename = f"{objectid}_TN.jpg"
            small_local_path = temp_dir / small_filename
            thumb_local_path = temp_dir / thumb_filename
            
            # Build blob names for checking existence
            small_blob_name = f"{base_path}/{objectid}_SMALL.jpg" if base_path else f"{objectid}_SMALL.jpg"
            thumb_blob_name = f"{base_path}/{objectid}_TN.jpg" if base_path else f"{objectid}_TN.jpg"
            
            try:
                small_blob_client = blob_service_client.get_blob_client(container=smalls_container, blob=small_blob_name)
                thumb_blob_client = blob_service_client.get_blob_client(container=thumbs_container, blob=thumb_blob_name)
                small_exists = small_blob_client.exists()
                thumb_exists = thumb_blob_client.exists()
            except Exception as ex:
                # If we can't check existence, assume they don't exist
                add_log_message(f"  [WARN] Could not check if derivatives exist: {ex}")
                small_exists = False
                thumb_exists = False
            
            if small_exists and thumb_exists:
                # Both derivatives already exist - skip generation
                add_log_message(f"  ⏩ Derivatives ({small_filename}, {thumb_filename}) already exist in Azure - skipping")
                # Build URLs for existing derivatives
                success_small_url, small_url, small_url_msg = build_object_location(
                    smalls_azure_path,
                    objectid + "_SMALL",
                    ".jpg",
                    azure_connection_string
                )
                success_thumb_url, thumb_url, thumb_url_msg = build_object_location(
                    thumbs_azure_path,
                    objectid + "_TN",
                    ".jpg",
                    azure_connection_string
                )
                if success_small_url:
                    row['image_small'] = small_url
                    small_success += 1
                if success_thumb_url:
                    row['image_thumb'] = thumb_url
                    thumb_success += 1
                skipped_count += 1
                continue
            
            processed_count += 1
            
            # Detect if file is PDF
            is_pdf = ext == '.pdf'
            
            # Generate small (800x800)
            if is_pdf:
                success_small, msg_small = generate_pdf_derivative(
                    str(source_path),
                    str(small_local_path),
                    800, 800, quality=85, dpi=150
                )
            else:
                success_small, msg_small = generate_derivative(
                    str(source_path),
                    str(small_local_path),
                    800, 800, quality=85
                )
            
            if success_small:
                # Upload small to Azure
                upload_success, upload_msg = upload_to_azure(
                    blob_service_client,
                    str(small_local_path),
                    smalls_azure_path,
                    objectid + "_SMALL",
                    ".jpg"
                )
                
                if upload_success:
                    # Build URL
                    success_url, url, url_msg = build_object_location(
                        smalls_azure_path,
                        objectid + "_SMALL",
                        ".jpg",
                        azure_connection_string
                    )
                    if success_url:
                        row['image_small'] = url
                        small_success += 1
                        add_log_message(f"  ✓ Small: {small_filename}")
                    else:
                        small_fail += 1
                        add_log_message(f"  ✗ Small URL failed: {url_msg}")
                else:
                    small_fail += 1
                    add_log_message(f"  ✗ Small upload failed: {upload_msg}")
            else:
                small_fail += 1
                add_log_message(f"  ✗ Small generation failed: {msg_small}")
            
            # Generate thumbnail (400x400)
            if is_pdf:
                success_thumb, msg_thumb = generate_pdf_derivative(
                    str(source_path),
                    str(thumb_local_path),
                    400, 400, quality=85, dpi=150
                )
            else:
                success_thumb, msg_thumb = generate_derivative(
                    str(source_path),
                    str(thumb_local_path),
                    400, 400, quality=85
                )
            
            if success_thumb:
                # Upload thumbnail to Azure
                upload_success, upload_msg = upload_to_azure(
                    blob_service_client,
                    str(thumb_local_path),
                    thumbs_azure_path,
                    objectid + "_TN",
                    ".jpg"
                )
                
                if upload_success:
                    # Build URL
                    success_url, url, url_msg = build_object_location(
                        thumbs_azure_path,
                        objectid + "_TN",
                        ".jpg",
                        azure_connection_string
                    )
                    if success_url:
                        row['image_thumb'] = url
                        thumb_success += 1
                        add_log_message(f"  ✓ Thumb: {thumb_filename}")
                    else:
                        thumb_fail += 1
                        add_log_message(f"  ✗ Thumb URL failed: {url_msg}")
                else:
                    thumb_fail += 1
                    add_log_message(f"  ✗ Thumb upload failed: {upload_msg}")
            else:
                thumb_fail += 1
                add_log_message(f"  ✗ Thumb generation failed: {msg_thumb}")
        
        # Populate derivatives for compound parents
        # Compound parents use their first child's derivative URLs (based on filename without underscore)
        add_log_message(f"[INFO] Populating compound parent derivatives...")
        compound_derivatives_populated = 0
        
        for row in rows:
            filename = row.get('filename', '').strip()
            if filename.startswith('_'):
                # Compound parent - find matching first child
                child_filename = filename[1:]  # Remove leading underscore
                
                # Find the child row with this filename
                child_row = None
                for potential_child in rows:
                    if potential_child.get('filename', '').strip() == child_filename:
                        child_row = potential_child
                        break
                
                if child_row:
                    # Copy derivative URLs from child to parent
                    child_small = child_row.get('image_small', '').strip()
                    child_thumb = child_row.get('image_thumb', '').strip()
                    
                    if child_small:
                        row['image_small'] = child_small
                    if child_thumb:
                        row['image_thumb'] = child_thumb
                    
                    if child_small and child_thumb:
                        compound_derivatives_populated += 1
                        objectid = row.get('objectid', 'unknown')
                        title = row.get('title', '')[:30] if row.get('title') else 'no title'
                        add_log_message(f"  ✓ Compound parent {objectid} ({title}...) derivatives from {child_filename}")
                    elif child_small or child_thumb:
                        add_log_message(f"  ⚠️ Compound parent {row.get('objectid', 'unknown')}: partial derivatives from {child_filename}")
                    else:
                        add_log_message(f"  ⚠️ Compound parent {row.get('objectid', 'unknown')}: no derivatives found for child {child_filename}")
                else:
                    add_log_message(f"  ⚠️ Compound parent {row.get('objectid', 'unknown')}: child file {child_filename} not found in CSV")
        
        if compound_derivatives_populated > 0:
            add_log_message(f"[SUCCESS] Populated derivatives for {compound_derivatives_populated} compound parent(s)")
        
        # Clean up temp directory
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as ex:
            logger.warning(f"Could not remove temp directory: {ex}")
        
        # Write updated CSV
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_csv = Path(working_dir) / f"DART_export_with_derivatives_{timestamp}.csv"
        
        try:
            with open(output_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
            
            add_log_message(f"[SUCCESS] Updated CSV saved: {output_csv.name}")
            logger.info(f"Saved updated CSV: {output_csv}")
            
            # Show results
            def close_dialog(e):
                dialog.open = False
                page.update()
            
            def show_log(e):
                """Open log file in read-only popup dialog."""
                global log_filename
                try:
                    with open(log_filename, 'r', encoding='utf-8') as f:
                        log_content = f.read()
                    
                    def close_log_dialog(e):
                        log_dialog.open = False
                        page.update()
                    
                    log_dialog = ft.AlertDialog(
                        modal=True,
                        title=ft.Text(f"Log File: {Path(log_filename).name}", weight=ft.FontWeight.BOLD),
                        content=ft.Container(
                            content=ft.TextField(
                                value=log_content,
                                multiline=True,
                                read_only=True,
                                text_size=11,
                                border=ft.InputBorder.NONE,
                            ),
                            width=800,
                            height=600,
                        ),
                        actions=[ft.TextButton("Close", on_click=close_log_dialog)],
                    )
                    
                    page.overlay.append(log_dialog)
                    log_dialog.open = True
                    page.update()
                except Exception as ex:
                    logger.error(f"Could not open log file: {ex}")
                    update_status(f"Error opening log: {ex}", is_error=True)
            
            # Build result content with clickable log link
            result_content = ft.Column([
                ft.Text("✅ Derivatives Generated and Uploaded", weight=ft.FontWeight.BOLD, size=16),
                ft.Text(""),
                ft.Text(f"CSV Rows: {total_rows} total"),
                ft.Text(f"  • {processed_count} image files processed"),
                ft.Row([
                    ft.Text(f"  • {skipped_count} rows skipped "),
                    ft.TextButton(
                        "see log for details",
                        on_click=show_log,
                        style=ft.ButtonStyle(padding=0),
                    ),
                ], spacing=0),
                ft.Text(""),
                ft.Text(f"Small images (800x800):"),
                ft.Text(f"  • Success: {small_success}"),
                ft.Text(f"  • Failed: {small_fail}"),
                ft.Text(""),
                ft.Text(f"Thumbnails (400x400):"),
                ft.Text(f"  • Success: {thumb_success}"),
                ft.Text(f"  • Failed: {thumb_fail}"),
                ft.Text(""),
                ft.Text(f"Updated CSV: {output_csv.name}"),
                ft.Text(f"Location: {working_dir}"),
                ft.Text(""),
                ft.Text(f"Columns added: image_small, image_thumb"),
            ], scroll=ft.ScrollMode.AUTO, tight=True)
            
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Function 3: Generate Derivatives", weight=ft.FontWeight.BOLD),
                content=ft.Container(
                    content=result_content,
                    width=600,
                    height=400,
                ),
                actions=[ft.TextButton("Close", on_click=close_dialog)],
            )
            
            page.overlay.append(dialog)
            dialog.open = True
            page.update()
            
            update_status(f"Generated {small_success + thumb_success} derivatives")
            
        except Exception as ex:
            update_status(f"Error writing CSV: {ex}", is_error=True)
            logger.error(f"Error writing updated CSV: {ex}")

    def on_function_4_compare_merge(e):
        """Function 4: Compare and merge CSV files with review output."""
        storage.record_function_usage("Function 4")
        
        # Check for working directory
        working_dir = output_dir_field.value
        if not working_dir or not Path(working_dir).exists():
            update_status("Error: Please set a working/outputs folder first", is_error=True)
            return
        
        working_path = Path(working_dir)
        
        # Load settings to get core metadata CSV
        settings, _ = load_app_settings(working_dir)
        core_csv_path = settings.get("core_metadata_csv", "")
        
        if not core_csv_path or not core_csv_path.strip():
            update_status("Error: Core metadata CSV not configured in settings", is_error=True)
            add_log_message("[ERROR] No core metadata CSV configured in Function 0 settings")
            add_log_message("[INFO] Configure core_metadata_csv in Function 0 to use comparison feature")
            return
        
        old_csv = Path(core_csv_path)
        if not old_csv.exists():
            update_status(f"Error: Core CSV file not found: {old_csv.name}", is_error=True)
            add_log_message(f"[ERROR] Core metadata CSV not found: {core_csv_path}")
            add_log_message("[INFO] Update core_metadata_csv path in Function 0 settings")
            return
        
        # Find all DART_export CSV files in working directory, sorted by modification time (newest first)
        csv_files = sorted(
            [f for f in working_path.glob("DART_export_*.csv") if f.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        if len(csv_files) < 1:
            update_status("Error: No DART_export CSV files found in working directory", is_error=True)
            add_log_message(f"[ERROR] No DART_export CSV files found in {working_dir}")
            add_log_message("[INFO] Run Function 2 first to generate a CSV export")
            return
        
        # Auto-select newest CSV as "new" file
        new_csv = csv_files[0]
        
        # Check if new CSV is the same as core CSV
        if new_csv.resolve() == old_csv.resolve():
            # Find second newest CSV
            if len(csv_files) < 2:
                update_status("Error: Only core CSV found, no DART_export files to compare", is_error=True)
                add_log_message(f"[ERROR] Only one DART_export CSV file (core metadata) found in {working_dir}")
                add_log_message("[INFO] Run Function 2 to generate a new CSV export to compare")
                return
            new_csv = csv_files[1]
        
        add_log_message(f"[INFO] Using core metadata CSV as 'old': {old_csv.name}")
        add_log_message(f"[INFO] Auto-selected newest DART_export CSV as 'new': {new_csv.name}")
        
        # Define helper functions
        def show_comparison_results(result):
            """Display comparison results with preview and summary."""
            
            def close_result_dialog(ev):
                result_dialog.open = False
                page.update()
            
            def show_log(ev):
                """Open log file in read-only popup dialog."""
                global log_filename
                try:
                    with open(log_filename, 'r', encoding='utf-8') as f:
                        log_content = f.read()
                    
                    def close_log_dialog(ev):
                        log_dialog.open = False
                        page.update()
                    
                    log_dialog = ft.AlertDialog(
                        modal=True,
                        title=ft.Text(f"Log File: {Path(log_filename).name}", weight=ft.FontWeight.BOLD),
                        content=ft.Container(
                            content=ft.TextField(
                                value=log_content,
                                multiline=True,
                                read_only=True,
                                text_size=11,
                                border=ft.InputBorder.NONE,
                            ),
                            width=800,
                            height=600,
                        ),
                        actions=[ft.TextButton("Close", on_click=close_log_dialog)],
                    )
                    
                    page.overlay.append(log_dialog)
                    log_dialog.open = True
                    page.update()
                except Exception as ex:
                    logger.error(f"Could not open log file: {ex}")
                    update_status(f"Error opening log: {ex}", is_error=True)
            
            # Get preview of changes (first 10 changed/new/missing rows)
            # Group compound families together when children have changes
            changes_df = result['merged'][result['merged']['status'].isin(['changed', 'new', 'missing_in_new'])].copy()
            all_merged_df = result['merged']
            
            # Build parent-child relationship map from the full dataset
            parent_children_map = {}  # parentid -> [child rows]
            parent_rows_map = {}  # parentid -> parent row
            
            for idx, row in all_merged_df.iterrows():
                filename = row.get('filename', '')
                if pd.notna(filename) and str(filename).strip().startswith('_'):
                    # This is a parent (underscore-prefixed filename)
                    objectid_new = row.get('objectid_new', '')
                    objectid_old = row.get('objectid_old', '')
                    parent_id = objectid_new if pd.notna(objectid_new) and str(objectid_new).strip() else objectid_old
                    if pd.notna(parent_id) and str(parent_id).strip():
                        parent_rows_map[str(parent_id).strip()] = row
            
            for idx, row in changes_df.iterrows():
                # Check if this is a child with a parent
                parentid_new = row.get('parentid_new', '')
                parentid_old = row.get('parentid_old', '')
                parent_id = parentid_new if pd.notna(parentid_new) and str(parentid_new).strip() else parentid_old
                if pd.notna(parent_id) and str(parent_id).strip():
                    parent_id_str = str(parent_id).strip()
                    if parent_id_str not in parent_children_map:
                        parent_children_map[parent_id_str] = []
                    parent_children_map[parent_id_str].append(row)
            
            # Build preview with grouped compound families
            preview_rows = []
            processed_indices = set()
            items_shown = 0
            max_items = 10
            
            for idx, row in changes_df.iterrows():
                if items_shown >= max_items:
                    break
                if idx in processed_indices:
                    continue
                
                # Check if this is a child with a parent
                parentid_new = row.get('parentid_new', '')
                parentid_old = row.get('parentid_old', '')
                parent_id = parentid_new if pd.notna(parentid_new) and str(parentid_new).strip() else parentid_old
                
                if pd.notna(parent_id) and str(parent_id).strip():
                    parent_id_str = str(parent_id).strip()
                    # This is a compound child - show parent first
                    if parent_id_str in parent_rows_map and parent_id_str in parent_children_map:
                        parent_row = parent_rows_map[parent_id_str]
                        children = parent_children_map[parent_id_str]
                        
                        # Check if we already showed this family
                        if parent_id_str not in processed_indices:
                            processed_indices.add(parent_id_str)
                            
                            # Show parent
                            parent_filename = parent_row.get('filename', '')
                            parent_objectid = parent_row.get('objectid_new', parent_row.get('objectid_old', ''))
                            parent_status = parent_row.get('status', 'match')
                            parent_icon = {
                                'new': '✨',
                                'changed': '📝',
                                'missing_in_new': '⚠️',
                                'match': '📦'
                            }.get(parent_status, '📦')
                            
                            preview_rows.append(ft.Text(
                                f"{parent_icon} {parent_filename} ({parent_objectid}) [COMPOUND PARENT]",
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.PURPLE_700
                            ))
                            items_shown += 1
                            
                            # Show children (indented)
                            for child_row in children:
                                if items_shown >= max_items:
                                    break
                                child_idx = child_row.name
                                if child_idx not in processed_indices:
                                    processed_indices.add(child_idx)
                                    
                                    status_icon = {
                                        'new': '✨',
                                        'changed': '📝',
                                        'missing_in_new': '⚠️'
                                    }.get(child_row['status'], '•')
                                    
                                    identifier = child_row.get('filename', '')
                                    if pd.isna(identifier) or str(identifier).strip() == '':
                                        identifier = child_row.get('objectid_old', child_row.get('objectid_new', f'Row {child_idx}'))
                                    
                                    status = child_row['status']
                                    changed_fields = child_row['changed_fields']
                                    
                                    preview_text = f"  ↳ {status_icon} {identifier} ({status})"
                                    if changed_fields:
                                        preview_text += f" - {changed_fields}"
                                    
                                    preview_rows.append(ft.Text(preview_text, size=11))
                                    items_shown += 1
                else:
                    # Standalone record (not a compound child)
                    processed_indices.add(idx)
                    
                    status_icon = {
                        'new': '✨',
                        'changed': '📝',
                        'missing_in_new': '⚠️'
                    }.get(row['status'], '•')
                    
                    identifier = row.get('filename', '')
                    if pd.isna(identifier) or str(identifier).strip() == '':
                        identifier = row.get('objectid_old', row.get('objectid_new', f'Row {idx}'))
                        if pd.isna(identifier) or str(identifier).strip() == '':
                            identifier = f'Row {idx}'
                    
                    status = row['status']
                    changed_fields = row['changed_fields']
                    
                    preview_text = f"{status_icon} {identifier} ({status})"
                    if changed_fields:
                        preview_text += f" - {changed_fields}"
                    
                    preview_rows.append(ft.Text(preview_text, size=11))
                    items_shown += 1
            
            if not preview_rows:
                preview_rows.append(ft.Text("All records match!", size=11, italic=True))
            
            # Build result content
            result_content = ft.Column([
                ft.Text("✅ CSV Comparison Complete", weight=ft.FontWeight.BOLD, size=16),
                ft.Text(""),
                ft.Text(f"Compared Files:", weight=ft.FontWeight.BOLD),
                ft.Text(f"  Old/Core: {result['old_csv_name']}", size=12),
                ft.Text(f"  New: {result['new_csv_name']}", size=12),
                ft.Text(""),
                ft.Text(f"Total Records: {result['total_rows']}", weight=ft.FontWeight.BOLD),
                ft.Text(f"  • {result['match_count']} matches (identical)", color=ft.Colors.GREEN),
                ft.Text(f"  • {result['new_count']} new records", color=ft.Colors.BLUE),
                ft.Text(f"  • {result['changed_count']} changed records", color=ft.Colors.ORANGE),
                ft.Text(f"  • {result['missing_count']} missing in new", color=ft.Colors.RED),
                ft.Text(""),
                ft.Text("Preview (first 10 changes):", weight=ft.FontWeight.BOLD, size=12),
                ft.Container(
                    content=ft.Column(preview_rows, spacing=2, scroll=ft.ScrollMode.AUTO),
                    border=ft.border.all(1, ft.Colors.GREY_400),
                    border_radius=4,
                    padding=8,
                    height=200,
                ),
                ft.Text(""),
                ft.Text("Output Files:", weight=ft.FontWeight.BOLD),
                ft.Text(f"  • {result['output_all'].name}", size=11),
                ft.Text(f"  • {result['output_changes'].name}", size=11),
                ft.Text(f"  • {result['output_summary'].name}", size=11),
                ft.Row([
                    ft.Text("  • "),
                    ft.TextButton("See log for details", on_click=show_log),
                ], spacing=0),
            ], spacing=4, scroll=ft.ScrollMode.AUTO)
            
            result_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("📊 Function 4: CSV Comparison Results"),
                content=ft.Container(
                    content=result_content,
                    width=600,
                    height=500,
                ),
                actions=[ft.TextButton("Close", on_click=close_result_dialog)],
            )
            
            page.overlay.append(result_dialog)
            result_dialog.open = True
            page.update()
        
        # Show comparison result dialog
        def show_results(comparison_result):
            show_comparison_results(comparison_result)
        
        # Perform comparison directly
        def perform_comparison(selected_new_csv):
            try:
                add_log_message(f"[INFO] Comparing CSV files...")
                add_log_message("[INFO] Using csvdiff tool for comparison")
                
                # Check if csvdiff is installed
                try:
                    from csvdiff import diff_files
                except ImportError:
                    update_status("Error: csvdiff not installed. Install with: pip install csvdiff", is_error=True)
                    add_log_message("[ERROR] csvdiff package not found. Run: pip install csvdiff")
                    add_log_message("[INFO] To install: pip install csvdiff")
                    return
                
                update_status("Running csvdiff comparison...")
                
                try:
                    # Strip 'filepath' column from both CSVs before comparison
                    # (filepath is internal DART data, not CollectionBuilder metadata)
                    import tempfile
                    import shutil
                    
                    temp_old = None
                    temp_new = None
                    
                    # Read and filter old CSV
                    with open(old_csv, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        old_fieldnames = [col for col in reader.fieldnames if col != 'filepath']
                        old_rows = list(reader)
                    
                    # Read and filter new CSV
                    with open(selected_new_csv, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        new_fieldnames = [col for col in reader.fieldnames if col != 'filepath']
                        new_rows = list(reader)
                    
                    # Create temporary filtered CSV files
                    temp_old = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8', newline='')
                    writer = csv.DictWriter(temp_old, fieldnames=old_fieldnames, extrasaction='ignore')
                    writer.writeheader()
                    writer.writerows(old_rows)
                    temp_old.close()
                    
                    temp_new = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8', newline='')
                    writer = csv.DictWriter(temp_new, fieldnames=new_fieldnames, extrasaction='ignore')
                    writer.writeheader()
                    writer.writerows(new_rows)
                    temp_new.close()
                    
                    add_log_message("[DEBUG] Stripped 'filepath' column from both CSVs for comparison")
                    
                    # Use csvdiff to compare filtered files with filename as key
                    diff_result = diff_files(temp_old.name, temp_new.name, index_columns=['filename'])
                    
                    # Clean up temp files
                    import os
                    os.unlink(temp_old.name)
                    os.unlink(temp_new.name)
                    
                    # Convert csvdiff result to our format
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    output_diff = working_path / f"csvdiff_result_{timestamp}.json"
                    output_summary = working_path / f"csvdiff_summary_{timestamp}.txt"
                    
                    # Write JSON output
                    import json
                    with open(output_diff, 'w') as f:
                        json.dump(diff_result, f, indent=2)
                    
                    # Create summary
                    added = len(diff_result.get('added', []))
                    removed = len(diff_result.get('removed', []))
                    changed = len(diff_result.get('changed', []))
                    
                    summary_text = f"""CSV Comparison Summary (csvdiff)
{"="*40}

Core CSV: {old_csv.name}
New CSV: {Path(selected_new_csv).name}

Results:
  • {added} new records (in new file only)
  • {removed} missing in new (in core file only)
  • {changed} changed records (different values)

Detailed results: {output_diff.name}
"""
                    
                    with open(output_summary, 'w') as f:
                        f.write(summary_text)
                    
                    add_log_message(f"[SUCCESS] csvdiff comparison complete:")
                    add_log_message(f"  • {added} new records")
                    add_log_message(f"  • {removed} missing in new")
                    add_log_message(f"  • {changed} changed records")
                    add_log_message(f"[SUCCESS] Wrote results: {output_diff.name}")
                    add_log_message(f"[SUCCESS] Wrote summary: {output_summary.name}")
                    
                    # Show result dialog with color-coded viewer option
                    def close_csvdiff_dialog(e):
                        csvdiff_dialog.open = False
                        page.update()
                    
                    def show_color_coded_view(e):
                        """Display interactive color-coded diff results with merge capability."""
                        try:
                            # Track selections: 
                            # - added: {record_idx: checkbox_ref}
                            # - changed: {record_idx: {field_name: checkbox_ref}}
                            selections = {'added': {}, 'changed': {}}
                            
                            # Build color-coded view
                            view_rows = []
                            
                            # Create field order based on new CSV columns (for consistent display)
                            # Remove 'filename' since it's the key, not a changed field
                            field_order = [f for f in new_fieldnames if f != 'filename']
                            
                            # Count data loss warnings (old value replaced with empty)
                            data_loss_count = 0
                            for change in diff_result.get('changed', []):
                                fields = change.get('fields', {})
                                for field_name, field_change in fields.items():
                                    old_val = str(field_change.get('from', '')).strip()
                                    new_val = str(field_change.get('to', '')).strip()
                                    if old_val and not new_val:  # Has old value but new is empty
                                        data_loss_count += 1
                            
                            # Checkbox behavior explanation
                            view_rows.append(ft.Container(
                                content=ft.Row([
                                    ft.Text("ℹ️", size=18),
                                    ft.Column([
                                        ft.Text("How Checkboxes Work", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.BLUE_900),
                                        ft.Text("• CHECKED: Merge this change into the core CSV (accept the new value)", size=10),
                                        ft.Text("• UNCHECKED: Skip this change (keep the existing core CSV value)", size=10),
                                        ft.Text("• Most changes are checked by default, except data loss fields (highlighted in orange)", size=10, italic=True),
                                    ], spacing=2),
                                ], spacing=8),
                                bgcolor=ft.Colors.BLUE_50,
                                border=ft.border.all(1, ft.Colors.BLUE_300),
                                border_radius=4,
                                padding=10,
                                margin=ft.margin.only(bottom=10),
                            ))
                            
                            # Show warning banner if data loss detected
                            if data_loss_count > 0:
                                view_rows.append(ft.Container(
                                    content=ft.Row([
                                        ft.Text("⚠️", size=20),
                                        ft.Column([
                                            ft.Text("DATA LOSS WARNING", weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_900, size=14),
                                            ft.Text(f"{data_loss_count} field(s) being replaced with empty values (highlighted in orange below)", size=11, color=ft.Colors.ORANGE_800),
                                            ft.Text("These fields are UNCHECKED by default to prevent accidental data loss - review carefully before enabling", size=10, italic=True),
                                        ], spacing=2),
                                    ], spacing=8),
                                    bgcolor=ft.Colors.ORANGE_100,
                                    border=ft.border.all(2, ft.Colors.ORANGE_400),
                                    border_radius=4,
                                    padding=10,
                                ))
                                view_rows.append(ft.Divider(height=2, color=ft.Colors.ORANGE_400))
                                view_rows.append(ft.Text(""))
                            
                            # Added records (Blue) with checkboxes
                            if added > 0:
                                view_rows.append(ft.Text(f"✨ NEW RECORDS ({added})", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE, size=14))
                                view_rows.append(ft.Divider(height=1))
                                
                                for idx, record in enumerate(diff_result.get('added', [])):
                                    filename = record.get('filename', 'Unknown')
                                    objectid = record.get('objectid', '')
                                    title = record.get('title', '')
                                    
                                    record_header = f"{filename}"
                                    if objectid:
                                        record_header += f" (ID: {objectid})"
                                    if title:
                                        record_header += f" - {title}"
                                    
                                    # Record header with larger text
                                    view_rows.append(ft.Text(record_header, weight=ft.FontWeight.BOLD, size=14, color=ft.Colors.BLUE_800))
                                    view_rows.append(ft.Divider(height=1, color=ft.Colors.BLUE_200))
                                    
                                    # Checkbox for adding this record
                                    checkbox = ft.Checkbox(value=True, label="Add this record")
                                    selections['added'][idx] = checkbox
                                    
                                    view_rows.append(ft.Container(
                                        content=checkbox,
                                        bgcolor=ft.Colors.BLUE_50,
                                        padding=4,
                                        border_radius=2,
                                    ))
                                    view_rows.append(ft.Container(height=8))
                                
                                view_rows.append(ft.Text(""))
                            
                            # Removed records (Gray) - READ ONLY, no checkbox
                            if removed > 0:
                                view_rows.append(ft.Text(f"⚠️ MISSING IN NEW ({removed}) - READ ONLY", weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_700, size=14))
                                view_rows.append(ft.Text("These records are in core but not in new CSV (not merged)", size=10, italic=True))
                                view_rows.append(ft.Divider(height=1))
                                
                                for idx, record in enumerate(diff_result.get('removed', [])[:20]):  # Show first 20
                                    filename = record.get('filename', 'Unknown')
                                    objectid = record.get('objectid', '')
                                    title = record.get('title', '')
                                    
                                    record_text = f"• {filename}"
                                    if objectid:
                                        record_text += f" (ID: {objectid})"
                                    if title:
                                        record_text += f" - {title}"
                                    
                                    view_rows.append(ft.Container(
                                        content=ft.Text(record_text, size=11, color=ft.Colors.GREY_700),
                                        bgcolor=ft.Colors.GREY_200,
                                        padding=4,
                                        border_radius=2,
                                    ))
                                
                                if removed > 20:
                                    view_rows.append(ft.Text(f"... and {removed - 20} more", size=10, italic=True))
                                view_rows.append(ft.Text(""))
                            
                            # Changed records (Red/Green) with field-level checkboxes
                            # Group compound families together
                            if changed > 0:
                                view_rows.append(ft.Text(f"📝 CHANGED RECORDS ({changed})", weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE, size=14))
                                view_rows.append(ft.Text("Each field can be individually selected. Compound families grouped with parent blanket toggles.", size=10, italic=True))
                                view_rows.append(ft.Divider(height=1))
                                
                                # Build parent-child map for compound objects
                                parent_child_map = {}  # parentid -> [child_indices]
                                parent_records = {}  # parentid -> parent_record (from added or changed)
                                processed_children = set()
                                
                                # First pass: identify parents from added records
                                for idx, record in enumerate(diff_result.get('added', [])):
                                    filename = record.get('filename', '')
                                    if filename and filename.startswith('_'):
                                        # This is a parent
                                        parent_id = record.get('objectid', '')
                                        if parent_id:
                                            parent_records[parent_id] = {'idx': idx, 'type': 'added', 'record': record}
                                
                                # Identify parents from changed records
                                for idx, change in enumerate(diff_result.get('changed', [])):
                                    key = change.get('key', ['Unknown'])[0]
                                    if key and key.startswith('_'):
                                        # Extract objectid from the record (check fields for objectid if available)
                                        parent_id = None
                                        # Try to get objectid from changed fields or original record
                                        # For csvdiff, the key is typically the filename
                                        # We need to look through all records to find matching objectid
                                        # For now, use the key as parent identifier
                                        parent_records[key] = {'idx': idx, 'type': 'changed', 'change': change}
                                
                                # Second pass: identify children and link to parents
                                for idx, change in enumerate(diff_result.get('changed', [])):
                                    key = change.get('key', ['Unknown'])[0]
                                    fields = change.get('fields', {})
                                    
                                    # Check if has parentid field
                                    parentid_change = fields.get('parentid', {})
                                    parent_id = parentid_change.get('to', parentid_change.get('from', ''))
                                    
                                    if parent_id and str(parent_id).strip():
                                        # This is a child - map it to parent
                                        parent_id_str = str(parent_id).strip()
                                        if parent_id_str not in parent_child_map:
                                            parent_child_map[parent_id_str] = []
                                        parent_child_map[parent_id_str].append(idx)
                                
                                # Third pass: render records, grouping compound families
                                processed_change_indices = set()
                                
                                for idx, change in enumerate(diff_result.get('changed', [])):
                                    if idx in processed_change_indices:
                                        continue
                                    
                                    key = change.get('key', ['Unknown'])[0]
                                    fields = change.get('fields', {})
                                    
                                    # Check if this record has children
                                    # For csvdiff, we need to extract objectid from the record
                                    record_objectid = None
                                    if 'objectid' in fields:
                                        record_objectid = fields['objectid'].get('to', fields['objectid'].get('from', ''))
                                    
                                    # Check if this is a parent with children
                                    is_compound_parent = record_objectid and record_objectid in parent_child_map
                                    
                                    if is_compound_parent:
                                        # This is a compound parent with children - create grouped container
                                        compound_container = ft.Column([], spacing=6)
                                        
                                        # Parent header
                                        compound_container.controls.append(ft.Text(
                                            f"📦 COMPOUND OBJECT: {key} ({record_objectid})",
                                            weight=ft.FontWeight.BOLD,
                                            size=14,
                                            color=ft.Colors.PURPLE_700
                                        ))
                                        compound_container.controls.append(ft.Divider(height=2, color=ft.Colors.PURPLE_400))
                                        
                                        # Get all children for this parent
                                        children_indices = parent_child_map[record_objectid]
                                        
                                        # Collect all unique fields that changed across parent and children
                                        all_changed_fields = set(fields.keys())
                                        for child_idx in children_indices:
                                            if child_idx < len(diff_result.get('changed', [])):
                                                child_change = diff_result['changed'][child_idx]
                                                all_changed_fields.update(child_change.get('fields', {}).keys())
                                        
                                        # Create blanket toggles for parent
                                        blanket_toggles = {}  # field_name -> blanket_checkbox
                                        parent_blanket_container = ft.Column([
                                            ft.Text("Parent Blanket Controls (affect all children):", 
                                                   weight=ft.FontWeight.BOLD, size=10, color=ft.Colors.PURPLE_900)
                                        ], spacing=2)
                                        
                                        # Initialize field checkbox dict for parent
                                        selections['changed'][idx] = {}
                                        
                                        # Initialize storage for children checkboxes (for blanket control)
                                        children_checkboxes = {}  # field_name -> [child_checkboxes]
                                        
                                        # Iterate fields in new CSV column order for consistent display
                                        ordered_changed_fields = [f for f in field_order if f in all_changed_fields]
                                        for field_name in ordered_changed_fields:
                                            if field_name not in fields:
                                                continue  # Parent doesn't have this field changed
                                            
                                            field_change = fields[field_name]
                                            old_val = str(field_change.get('from', ''))[:60]
                                            new_val = str(field_change.get('to', ''))[:60]
                                            
                                            # Detect data loss
                                            is_data_loss = old_val.strip() and not new_val.strip()
                                            
                                            # Default to checked unless data loss detected or title field
                                            # Title fields always default to unchecked to prevent accidental overwrites
                                            default_checked = False if field_name == 'title' else (not is_data_loss)
                                            
                                            # Create parent's own checkbox (always enabled, visual warning for data loss)
                                            parent_checkbox = ft.Checkbox(
                                                value=default_checked,
                                                label=""
                                            )
                                            selections['changed'][idx][field_name] = parent_checkbox
                                            
                                            # Create blanket checkbox
                                            def make_blanket_handler(field, p_cb, children_cbs_dict):
                                                def on_blanket_change(e):
                                                    # Update parent and all children checkboxes for this field
                                                    new_value = e.control.value
                                                    p_cb.value = new_value
                                                    if field in children_cbs_dict:
                                                        for child_cb in children_cbs_dict[field]:
                                                            if not child_cb.disabled:
                                                                child_cb.value = new_value
                                                    page.update()
                                                return on_blanket_change
                                            
                                            blanket_checkbox = ft.Checkbox(
                                                value=default_checked,
                                                label=""
                                            )
                                            blanket_toggles[field_name] = blanket_checkbox
                                            blanket_checkbox.on_change = make_blanket_handler(field_name, parent_checkbox, children_checkboxes)
                                            
                                            # Show blanket toggle (without Enable button for compound objects)
                                            if is_data_loss:
                                                parent_blanket_container.controls.append(ft.Container(
                                                    content=ft.Row([
                                                        blanket_checkbox,
                                                        ft.Text("⚠️", size=10),
                                                        ft.Text(f"{field_name}:", size=9, weight=ft.FontWeight.BOLD, width=90),
                                                        ft.Text("(controls parent + children)", size=9, italic=True, color=ft.Colors.GREY_600),
                                                    ], spacing=4, wrap=True),
                                                    padding=4,
                                                    bgcolor=ft.Colors.ORANGE_50,
                                                    border_radius=2,
                                                ))
                                            else:
                                                parent_blanket_container.controls.append(ft.Container(
                                                    content=ft.Row([
                                                        blanket_checkbox,
                                                        ft.Text(f"{field_name}:", size=9, weight=ft.FontWeight.BOLD, width=90),
                                                        ft.Text("(controls parent + children)", size=9, italic=True, color=ft.Colors.GREY_600),
                                                    ], spacing=4),
                                                    padding=2,
                                                ))
                                        
                                        compound_container.controls.append(ft.Container(
                                            content=parent_blanket_container,
                                            bgcolor=ft.Colors.PURPLE_50,
                                            padding=6,
                                            border_radius=4,
                                            border=ft.border.all(2, ft.Colors.PURPLE_300),
                                        ))
                                        
                                        # Show parent's own changes
                                        parent_change_container = ft.Column([
                                            ft.Text(f"📄 Parent: {key}", weight=ft.FontWeight.BOLD, size=13),
                                            ft.Divider(height=1, color=ft.Colors.PURPLE_200)
                                        ], spacing=2)
                                        
                                        # Display fields in new CSV column order
                                        ordered_parent_fields = [f for f in field_order if f in fields]
                                        for field_name in ordered_parent_fields:
                                            field_change = fields[field_name]
                                            old_val = str(field_change.get('from', ''))[:100]
                                            new_val = str(field_change.get('to', ''))[:100]
                                            is_data_loss = old_val.strip() and not new_val.strip()
                                            
                                            field_checkbox = selections['changed'][idx][field_name]
                                            
                                            if is_data_loss:
                                                parent_change_container.controls.append(ft.Container(
                                                    content=ft.Row([
                                                        field_checkbox,
                                                        ft.Text("⚠️", size=12),
                                                        ft.Text(f"{field_name}:", size=10, weight=ft.FontWeight.BOLD, width=100),
                                                        ft.Container(
                                                            content=ft.Text(old_val, size=10),
                                                            bgcolor=ft.Colors.RED_50,
                                                            padding=2,
                                                            border_radius=2,
                                                        ),
                                                        ft.Text("←⃠", size=12, color=ft.Colors.ORANGE),
                                                        ft.Container(
                                                            content=ft.Text('(empty)', size=10, italic=True, color=ft.Colors.ORANGE_900),
                                                            bgcolor=ft.Colors.ORANGE_100,
                                                            padding=2,
                                                            border_radius=2,
                                                            border=ft.border.all(1, ft.Colors.ORANGE_400),
                                                        ),
                                                    ], spacing=4, wrap=True),
                                                    padding=ft.padding.only(left=10, top=2, bottom=2),
                                                    bgcolor=ft.Colors.ORANGE_50,
                                                    border_radius=4,
                                                ))
                                            else:
                                                parent_change_container.controls.append(ft.Container(
                                                    content=ft.Row([
                                                        field_checkbox,
                                                        ft.Text(f"{field_name}:", size=10, weight=ft.FontWeight.BOLD, width=130),
                                                        ft.Container(
                                                            content=ft.Text(old_val if old_val else '(empty)', size=10),
                                                            bgcolor=ft.Colors.RED_50,
                                                            padding=2,
                                                            border_radius=2,
                                                        ),
                                                        ft.Text("←", size=10),
                                                        ft.Container(
                                                            content=ft.Text(new_val if new_val else '(empty)', size=10),
                                                            bgcolor=ft.Colors.GREEN_50,
                                                            padding=2,
                                                            border_radius=2,
                                                        ),
                                                    ], spacing=4, wrap=True),
                                                    padding=ft.padding.only(left=10, top=2, bottom=2),
                                                ))
                                        
                                        compound_container.controls.append(parent_change_container)
                                        
                                        # Show children
                                        children_container = ft.Column([
                                            ft.Text(f"Children ({len(children_indices)}):", weight=ft.FontWeight.BOLD, size=10, color=ft.Colors.PURPLE_700)
                                        ], spacing=4)
                                        
                                        for child_idx in children_indices:
                                            if child_idx >= len(diff_result.get('changed', [])):
                                                continue
                                            
                                            processed_change_indices.add(child_idx)
                                            child_change = diff_result['changed'][child_idx]
                                            child_key = child_change.get('key', ['Unknown'])[0]
                                            child_fields = child_change.get('fields', {})
                                            
                                            child_change_container = ft.Column([
                                                ft.Text(f"  ↳ {child_key}", weight=ft.FontWeight.BOLD, size=12),
                                                ft.Divider(height=1, color=ft.Colors.PURPLE_100)
                                            ], spacing=2)
                                            
                                            # Initialize field checkbox dict for child
                                            selections['changed'][child_idx] = {}
                                            
                                            # Show each changed field for this child in column order
                                            ordered_child_fields = [f for f in field_order if f in child_fields]
                                            for field_name in ordered_child_fields:
                                                field_change = child_fields[field_name]
                                                old_val = str(field_change.get('from', ''))[:100]
                                                new_val = str(field_change.get('to', ''))[:100]
                                                is_data_loss = old_val.strip() and not new_val.strip()
                                                
                                                # Default to checked unless data loss detected or title field
                                                # Title fields always default to unchecked to prevent accidental overwrites
                                                default_checked = False if field_name == 'title' else (not is_data_loss)
                                                
                                                child_checkbox = ft.Checkbox(
                                                    value=default_checked,
                                                    label=""
                                                )
                                                selections['changed'][child_idx][field_name] = child_checkbox
                                                
                                                # Add to children checkboxes for blanket control
                                                if field_name not in children_checkboxes:
                                                    children_checkboxes[field_name] = []
                                                children_checkboxes[field_name].append(child_checkbox)
                                                
                                                if is_data_loss:
                                                    child_change_container.controls.append(ft.Container(
                                                        content=ft.Row([
                                                            child_checkbox,
                                                            ft.Text("⚠️", size=12),
                                                            ft.Text(f"{field_name}:", size=9, width=90),
                                                            ft.Container(
                                                                content=ft.Text(old_val, size=9),
                                                                bgcolor=ft.Colors.RED_50,
                                                                padding=2,
                                                                border_radius=2,
                                                            ),
                                                            ft.Text("←⃠", size=10, color=ft.Colors.ORANGE),
                                                            ft.Container(
                                                                content=ft.Text('(empty)', size=9, italic=True),
                                                                bgcolor=ft.Colors.ORANGE_100,
                                                                padding=2,
                                                                border_radius=2,
                                                            ),
                                                        ], spacing=3, wrap=True),
                                                        padding=ft.padding.only(left=20, top=1, bottom=1),
                                                        bgcolor=ft.Colors.ORANGE_50,
                                                        border_radius=2,
                                                    ))
                                                else:
                                                    child_change_container.controls.append(ft.Container(
                                                        content=ft.Row([
                                                            child_checkbox,
                                                            ft.Text(f"{field_name}:", size=9, width=90),
                                                            ft.Container(
                                                                content=ft.Text(old_val if old_val else '(empty)', size=9),
                                                                bgcolor=ft.Colors.RED_50,
                                                                padding=2,
                                                                border_radius=2,
                                                            ),
                                                            ft.Text("←", size=9),
                                                            ft.Container(
                                                                content=ft.Text(new_val if new_val else '(empty)', size=9),
                                                                bgcolor=ft.Colors.GREEN_50,
                                                                padding=2,
                                                                border_radius=2,
                                                            ),
                                                        ], spacing=3, wrap=True),
                                                        padding=ft.padding.only(left=20, top=1, bottom=1),
                                                    ))
                                            
                                            children_container.controls.append(child_change_container)
                                        
                                        compound_container.controls.append(ft.Container(
                                            content=children_container,
                                            bgcolor=ft.Colors.PURPLE_50,
                                            padding=6,
                                            border_radius=4,
                                            border=ft.border.all(1, ft.Colors.PURPLE_200),
                                        ))
                                        
                                        # Add the complete compound container
                                        view_rows.append(ft.Container(
                                            content=compound_container,
                                            bgcolor=ft.Colors.WHITE,
                                            padding=8,
                                            border_radius=6,
                                            border=ft.border.all(2, ft.Colors.PURPLE_400),
                                        ))
                                        view_rows.append(ft.Text(""))
                                        
                                        processed_change_indices.add(idx)
                                        
                                    else:
                                        # Standalone record (not a compound parent with children)
                                        # Check if it's a child (will be handled with its parent)
                                        parentid_change = fields.get('parentid', {})
                                        parent_id = parentid_change.get('to', parentid_change.get('from', ''))
                                        
                                        if parent_id and str(parent_id).strip():
                                            # This is a child - it will be rendered with its parent
                                            # Skip it here if parent hasn't been processed yet
                                            continue
                                        
                                        # Regular standalone record
                                        has_data_loss = any(
                                            str(fc.get('from', '')).strip() and not str(fc.get('to', '')).strip()
                                            for fc in fields.values()
                                        )
                                        
                                        change_container = ft.Column([
                                            ft.Text(f"📄 {key} ({len(fields)} fields changed)", 
                                                   weight=ft.FontWeight.BOLD, size=14),
                                            ft.Divider(height=1, color=ft.Colors.ORANGE_200)
                                        ], spacing=4)
                                        
                                        # Initialize field checkbox dict for this record
                                        selections['changed'][idx] = {}
                                        
                                        # Create checkbox for each changed field in column order
                                        ordered_fields = [f for f in field_order if f in fields]
                                        for field_name in ordered_fields:
                                            field_change = fields[field_name]
                                            old_val = str(field_change.get('from', ''))[:100]
                                            new_val = str(field_change.get('to', ''))[:100]
                                            
                                            old_has_value = old_val and old_val.strip()
                                            new_is_empty = not new_val or not new_val.strip()
                                            is_data_loss = old_has_value and new_is_empty
                                            
                                            # Default to checked unless data loss detected or title field
                                            # Title fields always default to unchecked to prevent accidental overwrites
                                            default_checked = False if field_name == 'title' else (not is_data_loss)
                                            
                                            field_checkbox = ft.Checkbox(
                                                value=default_checked,
                                                label=""
                                            )
                                            selections['changed'][idx][field_name] = field_checkbox
                                            
                                            if is_data_loss:
                                                change_container.controls.append(ft.Container(
                                                    content=ft.Row([
                                                        field_checkbox,
                                                        ft.Text("⚠️", size=12),
                                                        ft.Text(f"{field_name}:", size=10, weight=ft.FontWeight.BOLD, width=100),
                                                        ft.Container(
                                                            content=ft.Text(old_val, size=10),
                                                            bgcolor=ft.Colors.RED_50,
                                                            padding=2,
                                                            border_radius=2,
                                                        ),
                                                        ft.Text("←⃠", size=12, color=ft.Colors.ORANGE),
                                                        ft.Container(
                                                            content=ft.Text('(empty)', size=10, italic=True, color=ft.Colors.ORANGE_900),
                                                            bgcolor=ft.Colors.ORANGE_100,
                                                            padding=2,
                                                            border_radius=2,
                                                            border=ft.border.all(1, ft.Colors.ORANGE_400),
                                                        ),
                                                    ], spacing=4, wrap=True),
                                                    padding=ft.padding.only(left=10, top=2, bottom=2),
                                                    bgcolor=ft.Colors.ORANGE_50,
                                                    border_radius=4,
                                                ))
                                            else:
                                                change_container.controls.append(ft.Container(
                                                    content=ft.Row([
                                                        field_checkbox,
                                                        ft.Text(f"{field_name}:", size=10, weight=ft.FontWeight.BOLD, width=130),
                                                        ft.Container(
                                                            content=ft.Text(old_val if old_val else '(empty)', size=10),
                                                            bgcolor=ft.Colors.RED_50,
                                                            padding=2,
                                                            border_radius=2,
                                                        ),
                                                        ft.Text("←", size=10),
                                                        ft.Container(
                                                            content=ft.Text(new_val if new_val else '(empty)', size=10),
                                                            bgcolor=ft.Colors.GREEN_50,
                                                            padding=2,
                                                            border_radius=2,
                                                        ),
                                                    ], spacing=4, wrap=True),
                                                    padding=ft.padding.only(left=10, top=2, bottom=2),
                                                ))
                                        
                                        view_rows.append(ft.Container(
                                            content=change_container,
                                            bgcolor=ft.Colors.ORANGE_50 if has_data_loss else ft.Colors.WHITE,
                                            padding=6,
                                            border_radius=4,
                                            border=ft.border.all(1, ft.Colors.ORANGE_300 if has_data_loss else ft.Colors.GREY_300),
                                        ))
                                        view_rows.append(ft.Text(""))
                                        
                                        processed_change_indices.add(idx)
                            
                            def close_color_view(e):
                                color_view_dialog.open = False
                                page.update()
                            
                            def merge_selected_changes(e):
                                """Merge selected changes into core CSV."""
                                try:
                                    # Count selected changes
                                    selected_added = [idx for idx, cb in selections['added'].items() if cb.value]
                                    
                                    # Count selected field changes
                                    selected_field_changes = []
                                    for record_idx, field_checkboxes in selections['changed'].items():
                                        for field_name, checkbox in field_checkboxes.items():
                                            if checkbox.value:
                                                selected_field_changes.append((record_idx, field_name))
                                    
                                    if not selected_added and not selected_field_changes:
                                        update_status("No changes selected to merge", is_error=True)
                                        return
                                    
                                    # Confirm merge
                                    def confirm_merge(ev):
                                        confirm_dialog.open = False
                                        page.update()
                                        
                                        # Perform merge
                                        update_status("Merging selected changes...")
                                        
                                        try:
                                            # Load core CSV
                                            import csv
                                            from datetime import datetime
                                            import shutil
                                            
                                            # Create backup of core CSV
                                            backup_path = Path(str(old_csv) + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                                            shutil.copy2(old_csv, backup_path)
                                            add_log_message(f"[INFO] Created backup: {backup_path.name}")
                                            
                                            # Read core CSV
                                            with open(old_csv, 'r', encoding='utf-8') as f:
                                                reader = csv.DictReader(f)
                                                fieldnames = reader.fieldnames
                                                core_rows = list(reader)
                                            
                                            # Create filename-to-row mapping
                                            core_by_filename = {row['filename']: row for row in core_rows if row.get('filename')}
                                            
                                            # Apply selected additions
                                            added_records = diff_result.get('added', [])
                                            for idx in selected_added:
                                                if idx < len(added_records):
                                                    new_record = added_records[idx]
                                                    core_rows.append(new_record)
                                                    add_log_message(f"[INFO] Added: {new_record.get('filename', 'Unknown')}")
                                            
                                            # Apply selected field changes
                                            changed_records = diff_result.get('changed', [])
                                            fields_updated_count = 0
                                            records_updated = set()
                                            
                                            for record_idx, field_name in selected_field_changes:
                                                if record_idx < len(changed_records):
                                                    change = changed_records[record_idx]
                                                    filename_key = change.get('key', [''])[0]
                                                    
                                                    if filename_key in core_by_filename:
                                                        # Update this specific field only
                                                        field_change = change.get('fields', {}).get(field_name, {})
                                                        new_value = field_change.get('to', '')
                                                        core_by_filename[filename_key][field_name] = new_value
                                                        fields_updated_count += 1
                                                        records_updated.add(filename_key)
                                            
                                            if records_updated:
                                                for filename in records_updated:
                                                    add_log_message(f"[INFO] Updated fields in: {filename}")
                                            
                                            # Write updated CSV using atomic write (temp file then rename)
                                            # This prevents "_1" copies and ensures clean overwrite
                                            temp_fd, temp_path = tempfile.mkstemp(suffix='.csv', dir=old_csv.parent, text=True)
                                            try:
                                                # Write to temporary file
                                                with os.fdopen(temp_fd, 'w', encoding='utf-8', newline='') as f:
                                                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                                                    writer.writeheader()
                                                    writer.writerows(core_rows)
                                                
                                                # Atomic replace: rename temp file to target (overwrites on all platforms)
                                                os.replace(temp_path, old_csv)
                                                add_log_message(f"[INFO] Successfully overwrote {old_csv.name}")
                                            except Exception as write_error:
                                                # Clean up temp file if something went wrong
                                                if Path(temp_path).exists():
                                                    os.remove(temp_path)
                                                raise write_error
                                            
                                            add_log_message(f"[SUCCESS] Merged {len(selected_added)} additions and {fields_updated_count} field changes across {len(records_updated)} records")
                                            update_status(f"Successfully merged {len(selected_added)} additions and {fields_updated_count} field changes")
                                            
                                            # Close dialogs
                                            color_view_dialog.open = False
                                            page.update()
                                            
                                        except Exception as merge_ex:
                                            logger.error(f"Error during merge: {merge_ex}")
                                            update_status(f"Merge error: {merge_ex}", is_error=True)
                                            add_log_message(f"[ERROR] Merge failed: {merge_ex}")
                                    
                                    def cancel_merge(ev):
                                        confirm_dialog.open = False
                                        page.update()
                                    
                                    # Count unique records being changed
                                    unique_records = len(set(record_idx for record_idx, _ in selected_field_changes))
                                    
                                    confirm_dialog = ft.AlertDialog(
                                        modal=True,
                                        title=ft.Text("⚠️ Confirm Merge", weight=ft.FontWeight.BOLD),
                                        content=ft.Column([
                                            ft.Text(f"You are about to merge into the core CSV:", size=12),
                                            ft.Text(f"  • {len(selected_added)} new records", color=ft.Colors.BLUE),
                                            ft.Text(f"  • {len(selected_field_changes)} field changes across {unique_records} records", color=ft.Colors.ORANGE),
                                            ft.Text(""),
                                            ft.Text(f"Core CSV: {old_csv.name}", size=11, weight=ft.FontWeight.BOLD),
                                            ft.Text(""),
                                            ft.Text("A backup will be created automatically.", size=10, italic=True),
                                            ft.Text(""),
                                            ft.Text("This action cannot be undone (except by restoring backup).", size=10, color=ft.Colors.RED),
                                        ], spacing=4, tight=True),
                                        actions=[
                                            ft.TextButton("Cancel", on_click=cancel_merge),
                                            ft.ElevatedButton("Merge Changes", on_click=confirm_merge, bgcolor=ft.Colors.BLUE),
                                        ],
                                    )
                                    
                                    page.overlay.append(confirm_dialog)
                                    confirm_dialog.open = True
                                    page.update()
                                    
                                except Exception as ex:
                                    logger.error(f"Error preparing merge: {ex}")
                                    update_status(f"Error: {ex}", is_error=True)
                            
                            color_view_dialog = ft.AlertDialog(
                                modal=True,
                                title=ft.Text("🎨 Interactive Comparison & Merge", weight=ft.FontWeight.BOLD),
                                content=ft.Container(
                                    content=ft.Column(view_rows, spacing=2, scroll=ft.ScrollMode.ALWAYS),
                                    width=900,
                                    height=600,
                                ),
                                actions=[
                                    ft.TextButton("Cancel", on_click=close_color_view),
                                    ft.ElevatedButton("Merge Selected Changes", on_click=merge_selected_changes, bgcolor=ft.Colors.GREEN),
                                ],
                            )
                            
                            page.overlay.append(color_view_dialog)
                            color_view_dialog.open = True
                            page.update()
                            
                        except Exception as ex:
                            logger.error(f"Error showing color-coded view: {ex}")
                            update_status(f"Error: {ex}", is_error=True)
                    
                    csvdiff_dialog = ft.AlertDialog(
                        modal=True,
                        title=ft.Text("📊 csvdiff Comparison Results"),
                        content=ft.Container(
                            content=ft.Column([
                                ft.Text(f"Core CSV: {old_csv.name}", size=11),
                                ft.Text(f"New CSV: {Path(selected_new_csv).name}", size=11),
                                ft.Text(""),
                                ft.Text("Results:", weight=ft.FontWeight.BOLD),
                                ft.Text(f"  • {added} new records", color=ft.Colors.BLUE),
                                ft.Text(f"  • {changed} changed records", color=ft.Colors.ORANGE),
                                ft.Text(f"  • {removed} missing in new", color=ft.Colors.RED),
                                ft.Text(""),
                                ft.Text("Output Files:", weight=ft.FontWeight.BOLD),
                                ft.Text(f"  • {output_diff.name} (detailed JSON)", size=11),
                                ft.Text(f"  • {output_summary.name} (summary)", size=11),
                            ], spacing=4, scroll=ft.ScrollMode.AUTO),
                            width=600,
                            height=300,
                        ),
                        actions=[
                            ft.ElevatedButton("Review & Merge Changes", on_click=show_color_coded_view, bgcolor=ft.Colors.GREEN),
                            ft.TextButton("Close", on_click=close_csvdiff_dialog),
                        ],
                    )
                    
                    page.overlay.append(csvdiff_dialog)
                    csvdiff_dialog.open = True
                    page.update()
                    
                    update_status(f"csvdiff comparison complete: {added} new, {changed} changed, {removed} missing")
                    return
                
                except Exception as csvdiff_err:
                    update_status(f"Error running csvdiff: {csvdiff_err}", is_error=True)
                    add_log_message(f"[ERROR] csvdiff failed: {csvdiff_err}")
                    return
            
            except Exception as ex:
                update_status(f"Error comparing CSVs: {ex}", is_error=True)
                add_log_message(f"[ERROR] Comparison failed: {ex}")
                logger.error(f"CSV comparison error: {ex}", exc_info=True)
        
        # Build CSV selection dialog for "new" file
        def close_select_dialog(ev):
            select_dialog.open = False
            page.update()
        
        def on_csv_selected(selected_file):
            select_dialog.open = False
            page.update()
            add_log_message(f"[INFO] User selected new CSV: {selected_file.name}")
            perform_comparison(selected_file)
        
        def use_default(ev):
            select_dialog.open = False
            page.update()
            add_log_message(f"[INFO] Using default (newest) CSV: {new_csv.name}")
            perform_comparison(new_csv)
        
        # Build CSV selection list
        csv_choices = []
        for i, csv_file in enumerate(csv_files, 1):
            mod_time = datetime.fromtimestamp(csv_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            is_newest = csv_file == new_csv
            is_core = csv_file.resolve() == old_csv.resolve()
            
            label = f"{i}. {csv_file.name}\n   Modified: {mod_time}"
            if is_newest:
                label += " ⭐ (newest)"
            if is_core:
                label += " (core)"
            
            csv_choices.append(
                ft.Container(
                    content=ft.TextButton(
                        label,
                        on_click=lambda e, f=csv_file: on_csv_selected(f),
                    ),
                    padding=4,
                    bgcolor=ft.Colors.GREEN_50 if is_newest else None,
                    border_radius=4,
                )
            )
        
        select_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("📊 Select New CSV to Compare", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(
                        f"Core metadata CSV (from settings):\n  {old_csv.name}",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.BLUE_700
                    ),
                    ft.Divider(),
                    ft.Text("Select the new CSV file to compare against core:", size=13),
                    ft.Text("⭐ Newest file is recommended (highlighted)", size=11, italic=True),
                    ft.Container(height=8),
                    ft.Column(csv_choices, spacing=2, scroll=ft.ScrollMode.AUTO),
                ], spacing=4),
                width=600,
                height=450,
            ),
            actions=[
                ft.ElevatedButton("Use Newest", on_click=use_default, icon=ft.Icons.STAR),
                ft.TextButton("Cancel", on_click=close_select_dialog),
            ],
        )
        
        page.overlay.append(select_dialog)
        select_dialog.open = True
        page.update()
        
        add_log_message(f"[INFO] Function 4: Found {len(csv_files)} CSV files in working directory")
        add_log_message(f"[INFO] Newest CSV: {new_csv.name}")
        update_status(f"Function 4: Select new CSV to compare with core ({old_csv.name})")

    def on_function_9_system_info(e):
        """Function 9: Display system information."""
        storage.record_function_usage("Function 9")

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
            title=ft.Text("Function 9: System Info"),
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
        logger.info("Function 9: Displayed system information")

    # ------------------------------------------------------------------ function management

    active_functions = [
        "function_0_app_settings",
        "function_1_list_files",
        "function_2_export_csv",
        "function_3_generate_derivatives",
        "function_4_compare_merge",
        "function_9_system_info",
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
        "function_2_export_csv": {
            "label": "2: Export Assets to CSV and Azure",
            "icon": "📊",
            "handler": on_function_2_export_csv,
            "help_file": "FUNCTION_2_EXPORT_CSV.md"
        },
        "function_3_generate_derivatives": {
            "label": "3: Generate Derivatives for CSV and Azure",
            "icon": "🖼️",
            "handler": on_function_3_generate_derivatives,
            "help_file": "FUNCTION_3_GENERATE_DERIVATIVES.md"
        },
        "function_4_compare_merge": {
            "label": "4: Compare and Merge CSV Files",
            "icon": "🔀",
            "handler": on_function_4_compare_merge,
            "help_file": "FUNCTION_4_COMPARE_MERGE_CSV.md"
        },
        "function_9_system_info": {
            "label": "9: System Information",
            "icon": "💻",
            "handler": on_function_9_system_info,
            "help_file": "FUNCTION_9_SYSTEM_INFO.md"
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

    # Container for status - can hold either simple text or row with clickable link
    status_container = ft.Container(
        content=ft.Text(
            "Ready",
            size=14,
            color=ft.Colors.BLACK,
        ),
        padding=ft.padding.all(8),
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
                                    ft.ElevatedButton(
                                        "Clear",
                                        icon=ft.Icons.CLEAR,
                                        on_click=clear_file_selection,
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
                                            ft.Row(
                                                controls=[
                                                    ft.Checkbox(
                                                        label="Help Mode",
                                                        ref=help_mode_enabled,
                                                        tooltip="Enable to view help documentation for functions instead of executing them",
                                                    ),
                                                    ft.Container(width=20),
                                                    ft.ElevatedButton(
                                                        "🛑 Kill Switch",
                                                        on_click=on_kill_switch_click,
                                                        icon=ft.Icons.CANCEL,
                                                        color=ft.Colors.WHITE,
                                                        bgcolor=ft.Colors.RED_700,
                                                        tooltip="Emergency stop - halts batch processing immediately",
                                                    ),
                                                ],
                                                spacing=10,
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
                            status_container,
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
                                        icon=ft.Icons.OPEN_IN_NEW,
                                        tooltip="View full log file",
                                        on_click=on_view_full_log_click,
                                        icon_size=20,
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
    
    # Validate directories on startup
    validate_directories()
    
    # Validate CSV structure file on startup if configured
    working_dir = output_dir_field.value
    if working_dir:
        settings, _ = load_app_settings(working_dir)
        csv_file = settings.get("csv_structure_file", "")
        core_csv = settings.get("core_metadata_csv", "")
        
        # Auto-populate core CSV from template if core is undefined but template exists
        if csv_file and not core_csv:
            core_csv = csv_file
            settings["core_metadata_csv"] = core_csv
            save_app_settings(working_dir, settings)
            add_log_message(f"Auto-populated core metadata CSV from template: {Path(csv_file).name}")
            logger.info(f"Auto-populated core_metadata_csv from template at startup: {csv_file}")
        
        if csv_file:
            valid, msg, fields = validate_csv_structure(csv_file)
            if valid:
                add_log_message(f"✓ CSV structure template validated: {msg}")
                logger.info(f"CSV structure validated on startup: {csv_file}")
            else:
                add_log_message(f"⚠ CSV structure validation warning: {msg}")
                logger.warning(f"CSV structure validation failed: {csv_file} - {msg}")
        
        if core_csv:
            valid, msg = validate_core_metadata_csv(core_csv, csv_file)
            if valid:
                add_log_message(f"✓ Core metadata CSV validated: {msg}")
                logger.info(f"Core metadata CSV validated on startup: {core_csv}")
            else:
                add_log_message(f"⚠ Core metadata CSV validation warning: {msg}")
                logger.warning(f"Core metadata CSV validation failed: {core_csv} - {msg}")


if __name__ == "__main__":
    logger.info("Application starting…")
    ft.app(target=main)
