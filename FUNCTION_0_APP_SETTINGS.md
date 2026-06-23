# Function 0: App Settings

## Purpose
Open the application settings file in the selected working/outputs folder's `.DART-working-directory` subfolder and edit values using popup text input fields.

## Security Note
**Sensitive fields are encrypted** (`api_key`, `api_secret`, `password`). You enter and see them as plain text in the editor, but they are automatically encrypted when saved to `dart_settings.json`. This makes it safe to commit your settings file to version control (GitHub, etc.) without exposing credentials.

The encryption key is stored separately in `~/.DART-data/encryption_key` with restricted permissions.

## Current Settings
- **group_compound_objects**: When `true`, groups similar filenames as compound objects in asset analysis. **[BOOLEAN]**
- **use_working_folder_for_file_selection**: When `true`, the File Selector opens in the working/outputs folder. When `false`, it opens in the inputs folder. **[BOOLEAN]**
- **automatic_four**: When `true`, automatically executes Functions 2, 3, and 4 sequentially after Function 1 completes successfully. This creates a seamless workflow from asset analysis through CSV export, derivative generation, and metadata merge. Automatically resets to `false` at the start of each new session. **[BOOLEAN]**
- **dg_prefix**: Optional project prefix for newly generated DG identifiers. Leave blank to keep the legacy `dg_<epoch>` format. When set, DART generates IDs as `<prefix>_dg_<epoch>`. Limited to 4 letters/numbers; the trailing underscore is added automatically. **[OPTIONAL, MAX 4]**
- **core_metadata_csv**: Path to your core metadata CSV file. This file serves two purposes: (1) defines the column structure/template for metadata exports, and (2) acts as the master metadata file that future functions will update and merge into. **[VALIDATED]**
- **azure_blob_storage_path**: Azure Blob Storage path for cloud storage operations. **[VALIDATED]**
  - **REQUIRED**: Path must contain `/objs/` folder (this holds original source files)
  - Format: `container/objs/subfolder` or `objs/collection_name`
  - Example: `objs/TDPS_archive` or `mycontainer/objs/photos`
  - **Parallel folders**: Your Azure storage should also contain `/smalls/` and `/thumbs/` folders as siblings to `/objs/` for derivative files
  - Validation ensures `/objs/` is present; `/smalls/` and `/thumbs/` are expected but not verified programmatically
- **azure_connection_string**: Azure Storage account connection string for authentication. Required for uploading files to Azure Blob Storage. **[ENCRYPTED]**
- **api_key**: Your API key for external services. **[ENCRYPTED]**
- **api_secret**: Your API secret for external services. **[ENCRYPTED]**
- **password**: General password field for application use. **[ENCRYPTED]**

**Note**: The settings file also contains an internal `file_to_id_map` field that stores permanent file-to-identifier mappings using **full file paths** as keys. This is managed automatically by Function 1 and ensures that once a file receives a `dg_<epoch>` identifier, it never changes. Using full paths prevents collisions between files with the same name in different directories.

**Compound Object Mapping**: When `group_compound_objects` is enabled, the `file_to_id_map` also stores compound object IDs using the format `{folder_path}::COMPOUND::{text_base}`. This ensures compound objects in a given folder always receive the same identifier across runs. Example: `/Users/name/assets::COMPOUND::photo` maps to a specific compound ID.

## Requirements
- A **Working/Outputs Folder** must be selected first.

## Usage
1. Set **Working/Outputs Folder**.
2. Select **0: App Settings** from the function list.
3. Edit values in the text input fields.
4. Click **Save**.

## Settings File
- File name: `dart_settings.json`
- Location: Inside `.DART-working-directory` under the selected working/outputs folder

## Accepted Boolean Values
For `group_compound_objects` and `use_working_folder_for_file_selection`, you can enter:
- true/false
- yes/no
- 1/0
- on/off

## Notes
- Settings are specific to each working/outputs folder
- The settings file is created automatically with defaults in `.DART-working-directory` if it doesn't exist
- If a legacy root-level `dart_settings.json` is found, DART automatically migrates it into `.DART-working-directory`
- Sensitive fields (marked **[ENCRYPTED]**) are stored encrypted in the JSON file
- `group_compound_objects` controls whether Function 1 groups similar filenames as compound objects
- `use_working_folder_for_file_selection` controls where the File Selector dialog opens (working/outputs folder when true, inputs folder when false)
- `dg_prefix` is highly recommended when DART is used across multiple projects at the same time, but it is not required
- Recommended convention: use a short 2-4 character project code such as `tdps`, `csm`, or `ohm`
- Keep the prefix stable for the life of a project so newly assigned IDs sort consistently and remain easy to recognize
- IDs created before epoch `1782237851` will always be in legacy `dg_<epoch>` form
- IDs created at or after epoch `1782237851` may appear either as legacy `dg_<epoch>` (blank prefix) or new `<prefix>_dg_<epoch>` values
- `azure_blob_storage_path` should use forward slashes and follow Azure Blob Storage path conventions (e.g., `container/folder/subfolder`)
- `azure_connection_string` is your Azure Storage account connection string from the Azure portal (stored encrypted)
- You can customize the sensitive fields list and default settings in `app.py`

### Core Metadata CSV

The `core_metadata_csv` setting identifies your core metadata CSV file - this single file serves as both:
1. **Column structure template** - Defines required/recommended fields for CollectionBuilder compatibility
2. **Master metadata file** - The "source of truth" for your collection's metadata 

**Auto-Copy to Working Directory:** When you select a CSV template file and save settings, DART automatically copies it to your working directory if it's not already there. This keeps all project-related files together and ensures the template is available with your project data.

**Required Fields:**
- `objectid` - Unique identifier for each object (automatically generated as `dg_<epoch>`)
- `original_file_name` - Original filename of the digital asset

**Recommended Fields:**
- `title` - Title or name of the object
- `format` - File format/MIME type
- `date` - Date associated with the object
ore_metadata_csv
**How it works:**
1. Click the "Browse..." button next to the csv_structure_file field
2. Select a CSV file that has the column headers you want to use (can be from anywhere)
3. DART automatically validates the file structure
4. When you save settings, the file is copied to your working directory (if not already there)
5. Settings are updated to point to the local copy
6. Green checkmark (✓) indicates all required fields are present
7. Red error (✗) indicates missing required fields
8. On app startup, DART validates the configured CSV structure and logs the result

**Example template CSV:**
```csv
objectid,original_file_name,title,format,date,description,subject,creator
```

**Purpose:**

**Auto-Population:** If you select a CSV structure template but leave the core metadata CSV blank, DART automatically populates the core CSV field with the same file. This makes it easy to use a single CSV file as both your template and your working metadata file. You can always override this by selecting a different file.

**Auto-Copy to Working Directory:** When you save settings, DART automatically copies the core CSV to your working directory if it's not already there. If both the template and core CSV are the same file, DART copies it once and uses that copy for both settings. This ensures all project files stay together.

**Purpose:**
- Defines your metadata schema with required and recommended fields
- Serves as the master metadata file for your collection
- Future DART functions will intelligently merge new metadata into this file
- Maintains consistency across workflow phases
- Enables incremental metadata updates without losing existing work

**File structure validation:**
- File exists and is readable
- Has required CollectionBuilder fields (`objectid`, `original_file_name`)
- Reports column count and compatibility status

**Workflow example:**
1. Create/select a CSV file with your desired metadata columns (can be anywhere on your system)
2. The file should have headers like: `objectid,original_file_name,title,format,date,description,subject,creator`
3. Save settings - file is automatically copied to your working directory
4. Use Function 2 to analyze assets and generate new metadata rows
5. Future functions will merge new data into this CSV following its column structure
6. Core CSV grows and updates intelligently as you process batches of assets

When configured, it enables DART's intelligent metadata management workflow. The CSV file is

The Azure Blob Storage settings enable DART to upload files directly to Microsoft Azure cloud storage.

**Two Settings Required:**

1. **azure_blob_storage_path**: The path within Azure storage where files should be uploaded
   - **REQUIRED**: Must contain `/objs/` folder for original source files
   - Format: `container/objs/subfolder` or `objs/collection_name`
   - Example: `objs/TDPS_archive` or `mycontainer/objs/photos`
   - **IMPORTANT**: Enter ONLY the path, NOT a full URL
   - ✓ Correct: `objs/TDPS_archive`
   - ✗ Wrong: `https://account.blob.core.windows.net/objs/TDPS_archive`
   - ✗ Wrong: `collectionbuilder.blob.core.windows.net/objs/TDPS_archive`
   - The full URL is built automatically from your connection string
   - **Validation**: DART checks that `/objs/` is present and rejects URLs
   - **Expected structure**: Your Azure container should have three parallel folders:
     - `/objs/` - Original source files (source of truth)
     - `/smalls/` - Medium-sized derivatives
     - `/thumbs/` - Thumbnail-sized derivatives
   - Note: Only `/objs/` is validated; `/smalls/` and `/thumbs/` should exist but aren't checked programmatically

2. **azure_connection_string**: Your Azure Storage account connection string (encrypted)
   - Found in Azure Portal → Storage Account → Access Keys → Connection string
   - Format: `DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net`
   - Stored encrypted for security
   - Password field allows reveal/hide toggle

**How to Get Your Connection String:**

1. Log into the Azure Portal (portal.azure.com)
2. Navigate to your Storage Account (e.g., "collectionbuilder")
3. Go to "Access keys" in the left menu
4. Copy either the "Connection string" from key1 or key2
5. Paste it into the `azure_connection_string` field in DART

**Example Configuration:**

If your Azure storage structure is:
```
https://collectionbuilder.blob.core.windows.net/
  ├── objs/TDPS_archive/
  ├── smalls/TDPS_archive/
  └── thumbs/TDPS_archive/
```

Configure DART with:
- **azure_blob_storage_path**: `objs/TDPS_archive`
- **azure_connection_string**: `DefaultEndpointsProtocol=https;AccountName=collectionbuilder;AccountKey=xxxxx...;EndpointSuffix=core.windows.net`

DART will validate that `/objs/` is in the path and expect `/smalls/` and `/thumbs/` exist as parallel folders.

**Security Notes:**
- The connection string is encrypted in `dart_settings.json`
- It's safe to commit the settings file to version control
- The encryption key is stored separately in `~/.DART-data/encryption_key`
- Never share your connection string in plain text

**Common Errors:**

❌ **"The specifed resource name contains invalid characters"**
- **Cause**: You entered a full URL in `azure_blob_storage_path` instead of just the path
- **Wrong**: `https://account.blob.core.windows.net/objs/collection` or `account.blob.core.windows.net/objs/collection`
- **Correct**: `objs/collection`
- **Fix**: Edit Function 0 settings and remove the account name/URL portion

❌ **"Path must contain /objs/ folder"**
- **Cause**: The path doesn't include the required `/objs/` folder
- **Fix**: Update path to include `/objs/` (e.g., `objs/collection` or `container/objs/subfolder`)

❌ **"Failed to connect to Azure"**
- **Cause**: Invalid connection string or network issue
- **Fix**: Verify connection string is correct and complete from Azure Portal

**Future Functions:**
Once configured, future DART functions will be able to:
- Upload processed files to Azure Blob Storage
- Maintain file organization in the cloud
- Generate public URLs for CollectionBuilder
- Sync local working files with cloud storage

## Example Settings File (stored encrypted)
```json
{
  "auto_save_enabled": false,
  "auto_save_format": "txt",
  "group_compound_objects": true,
  "use_working_folder_for_file_selection": false,
  "csv_structure_file": "/path/to/metadata_template.csv",
  "core_metadata_csv": "/path/to/collection_metadata_master.csv",
  "azure_blob_storage_path": "objs/tdps-archive",
  "azure_connection_string": "gAAAAABk...[encrypted]",
  "api_key": "gAAAAABk...[encrypted]",
  "api_secret": "gAAAAABk...[encrypted]",
  "password": "gAAAAABk...[encrypted]",
  "file_to_id_map": {
    "/Users/name/assets/photo_001.jpg": "dg_1736712346",
    "/Users/name/assets/photo_002.jpg": "dg_1736712347",
    "/Users/name/assets::COMPOUND::photo": "dg_1736712345",
    "/Users/name/docs/scan_page_1.tif": "dg_1736712350"
  }
}
```
group_compound_objects": true,
  "use_working_folder_for_file_selection": false,
  "core_metadata_csv": "/path/to/collection_metadata.csv",
  "azure_blob_storage_path": "objs/tdps-archive",
  "azure_connection_string