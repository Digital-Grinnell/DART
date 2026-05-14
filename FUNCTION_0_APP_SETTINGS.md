# Function 0: App Settings

## Purpose
Open the application settings file in the selected working/outputs folder and edit values using popup text input fields.

## Security Note
**Sensitive fields are encrypted** (`api_key`, `api_secret`, `password`). You enter and see them as plain text in the editor, but they are automatically encrypted when saved to `dart_settings.json`. This makes it safe to commit your settings file to version control (GitHub, etc.) without exposing credentials.

The encryption key is stored separately in `~/.DART-data/encryption_key` with restricted permissions.

## Current Settings
- **auto_save_enabled**: When `true`, enables automatic saving of output from functions. **[BOOLEAN]**
- **auto_save_format**: Default output format for autosave files (e.g., `txt`, `csv`, `json`, etc.)
- **group_compound_objects**: When `true`, groups similar filenames as compound objects in asset analysis. **[BOOLEAN]**
- **use_working_folder_for_file_selection**: When `true`, the File Selector opens in the working/outputs folder. When `false`, it opens in the inputs folder. **[BOOLEAN]**
- **csv_structure_file**: Path to a CSV template file that defines the expected column structure for metadata exports. Use the "Browse..." button to select a CSV file. **[VALIDATED]**
- **core_metadata_csv**: Path to your main/controlling metadata CSV file. This is the master metadata file that future functions will update and merge into. **[VALIDATED, OPTIONAL]**
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
- Location: Inside the selected working/outputs folder

## Accepted Boolean Values
For `auto_save_enabled`, `group_compound_objects`, and `use_working_folder_for_file_selection`, you can enter:
- true/false
- yes/no
- 1/0
- on/off

## Notes
- Settings are specific to each working/outputs folder
- The settings file is created automatically with defaults if it doesn't exist
- Sensitive fields (marked **[ENCRYPTED]**) are stored encrypted in the JSON file
- `group_compound_objects` controls whether Function 1 groups similar filenames as compound objects
- `use_working_folder_for_file_selection` controls where the File Selector dialog opens (working/outputs folder when true, inputs folder when false)
- `azure_blob_storage_path` should use forward slashes and follow Azure Blob Storage path conventions (e.g., `container/folder/subfolder`)
- `azure_connection_string` is your Azure Storage account connection string from the Azure portal (stored encrypted)
- You can customize the sensitive fields list and default settings in `app.py`

### CSV Structure File Validation

The `csv_structure_file` setting allows you to specify a template CSV file that defines the required column structure for CollectionBuilder-compatible metadata exports. 

**Auto-Copy to Working Directory:** When you select a CSV template file and save settings, DART automatically copies it to your working directory if it's not already there. This keeps all project-related files together and ensures the template is available with your project data.

**Required Fields:**
- `objectid` - Unique identifier for each object (automatically generated as `dg_<epoch>`)
- `filename` - Original filename of the digital asset

**Recommended Fields:**
- `title` - Title or name of the object
- `format` - File format/MIME type
- `date` - Date associated with the object

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
objectid,filename,title,format,date,description,subject,creator
```

This ensures your metadata exports will be compatible with CollectionBuilder and other digital collection platforms that require specific column structures.

### Core Metadata CSV

The `core_metadata_csv` setting (optional) identifies your main/controlling metadata CSV file - the "source of truth" for your collection's metadata.

**Auto-Population:** If you select a CSV structure template but leave the core metadata CSV blank, DART automatically populates the core CSV field with the same file. This makes it easy to use a single CSV file as both your template and your working metadata file. You can always override this by selecting a different file.

**Auto-Copy to Working Directory:** When you save settings, DART automatically copies the core CSV to your working directory if it's not already there. If both the template and core CSV are the same file, DART copies it once and uses that copy for both settings. This ensures all project files stay together.

**Purpose:**
- Serves as the master metadata file for your collection
- Future DART functions will intelligently merge new metadata into this file
- Maintains consistency across workflow phases
- Enables incremental metadata updates without losing existing work

**How it works:**
1. Click the "Browse..." button next to the core_metadata_csv field
2. Select your existing metadata CSV file (can be from anywhere, or leave blank to auto-populate from template)
3. DART validates the file structure and checks compatibility with your template
4. When you save settings, the file is copied to your working directory (if not already there)
5. Settings are updated to point to the local copy
6. If a CSV structure template is configured, DART verifies the core CSV has all required columns
7. Green checkmark (✓) indicates valid structure and template compatibility
8. Red error (✗) indicates problems that need resolution

**Validation checks:**
- File exists and is readable
- Has required CollectionBuilder fields (`objectid`, `filename`)
- If CSV structure template is configured: verifies core CSV has all template columns
- Reports column count and compatibility status

**Workflow example:**
1. Create/select a CSV structure template defining your metadata schema (can be anywhere on your system)
2. Leave core_metadata_csv blank - it auto-populates from the template (or select a different file)
3. Save settings - both files are automatically copied to your working directory
4. Use Function 1 to analyze assets and generate new metadata
5. Future functions will merge new data into core_metadata_csv following the template structure
6. Core CSV grows and updates intelligently as you process batches of assets

**Note:** The core_metadata_csv field is **optional**. Leave it blank if:
- You're starting a new collection with no existing metadata
- You want to generate standalone CSV files without merging
- You prefer to manage CSV merging manually

When configured, it enables DART's intelligent metadata management workflow. All CSV files are kept in your working directory alongside your project data.

### Azure Blob Storage Configuration

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

**Note**: The `file_to_id_map` stores both individual file IDs and compound object IDs. Compound entries use the special format `{folder}::COMPOUND::{text_base}`.

## Customization
To add your own settings:
1. Edit `DEFAULT_APP_SETTINGS` in `app.py`
2. Add new fields to the Function 0 dialog
3. Mark sensitive fields in `SENSITIVE_FIELDS` list for encryption
4. Update this documentation
