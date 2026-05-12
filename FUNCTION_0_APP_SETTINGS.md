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
- **csv_structure_file**: Path to a CSV file that defines the expected column structure for exports
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
- `csv_structure_file` should be a full path to a CSV file that defines expected columns for exports
- You can customize the sensitive fields list and default settings in `app.py`

## Example Settings File (stored encrypted)
```json
{
  "auto_save_enabled": false,
  "auto_save_format": "txt",
  "group_compound_objects": true,
  "use_working_folder_for_file_selection": false,
  "csv_structure_file": "/path/to/structure.csv",
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
