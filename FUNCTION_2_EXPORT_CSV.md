# Function 2: Export Assets to CSV and Azure

## Purpose
Export analyzed digital assets to a CSV file using your configured template structure. This function generates a CollectionBuilder-compatible metadata CSV with automatically populated core fields.

## When to Use
Use this function when you want to:
- Generate metadata CSV files for CollectionBuilder
- Create structured metadata exports from analyzed assets
- Begin populating metadata that can be completed manually or by other functions
- Export object IDs and filenames in a standardized format

## Requirements
- **Working/Outputs folder** must be set
- **CSV structure template** must be configured in Function 0 settings
- Digital asset files to export (either selected files or in inputs folder)

## Workflow

1. Configure your CSV template in **Function 0: App Settings**
   - Set `csv_structure_file` to point to your template CSV
   - The template defines which columns will be in the export

2. Select digital assets:
   - Either use the **File Selector** to choose specific files
   - Or set an **Inputs Folder** to process all assets in that folder

3. Select **Function 2: Export Assets to CSV and Azure** from the dropdown

4. Click **Execute Function**

5. A timestamped CSV file is created in your working directory

## What Gets Exported

The function automatically populates these CollectionBuilder fields from your assets:

- **objectid**: Unique DG identifier (format: `dg_<epoch>`)
- **filename**: Original filename for files; underscore-prefixed first child filename for compound parents
  - Example: `photo_001.jpg` for a regular file
  - Example: `_photo_001.jpg` for a compound parent (no physical file, just an index)
  - The underscore prefix differentiates compound parents from actual files
- **parentid**: Parent object ID for child objects (if column exists and compound grouping enabled)
  - Blank for standalone objects and compound parents
  - Set to parent's objectid for child objects in a compound
- **display_template**: CollectionBuilder layout type (if column exists in template)
  - `image` for .jpg, .jpeg, .png, .gif, .tif, .tiff, .bmp, .webp
  - `video` for .mp4, .mov, .avi, .mkv, .wmv, .flv, .webm
  - `audio` for .mp3, .wav, .flac, .aac, .ogg, .m4a, .wma
  - `pdf` for .pdf files
  - `record` for archives (.zip, .tar, .gz, .7z, .rar, .bz2)
  - `compound_object` for compound parent objects (if grouping enabled)
- **format**: File extension (if column exists in template) - e.g., `jpg`, `pdf`, `mp4`
- **object_location**: Azure Blob Storage URL (if Azure is configured and column exists in template)
  - Full URL to file in Azure: `https://account.blob.core.windows.net/container/path/objectid.ext`
  - Files are uploaded to Azure with renamed filenames matching their objectid
  - Example: `https://collectionbuilder.blob.core.windows.net/objs/tdps/dg_1715614222.jpg`
  - Empty if Azure is not configured in Function 0 settings
- **title**: Suggested title for compound objects (if column exists and compound grouping enabled)
  - Generated from filename prefix pattern
  - Only populated for compound parent objects

All other columns from your template are included as empty fields, ready for you to populate with:
- Titles (for file objects)
- Descriptions
- Dates
- Subjects
- Creator names
- Rights statements
- And any other metadata defined in your template

## Azure Blob Storage Upload

When Azure is configured in Function 0 settings, Function 2 automatically:

1. **Validates Azure configuration** before export
   - Checks `azure_blob_storage_path` contains required `/objs/` folder
   - Tests Azure connection using `azure_connection_string`
   - Fails early if configuration is invalid

2. **Creates Azure container if needed**
   - Automatically checks if target container exists
   - Creates container if it doesn't exist
   - Handles concurrent creation gracefully
   - No manual Azure portal setup required

3. **Uploads files to Azure** during export (skips files that already exist)
   - Each file is uploaded with its `dg_<epoch>` identifier as the filename
   - Original extension is preserved (e.g., `dg_1715614222.jpg`)
   - Files are uploaded to the path specified in settings (e.g., `objs/tdps_archive`)
   - Content-Type headers are set automatically based on file extension
   - **Safe to re-run**: Checks if file exists before uploading, skips if already present
   - Only uploads new or changed files, never overwrites existing files

4. **Builds object_location URLs** for each file
   - Complete Azure Blob Storage URL
   - Format: `https://{account}.blob.core.windows.net/{container}/{path}/{objectid}{ext}`
   - Example: `https://collectionbuilder.blob.core.windows.net/objs/tdps/dg_1715614222.jpg`
   - Populated in CSV if `object_location` column exists in template
   - URL is generated even if upload was skipped (file already exists)

5. **Reports upload results**
   - Shows count of uploaded (new files), skipped (already exist), and failed
   - Safe to re-run Function 2 multiple times without re-uploading existing files
   - Detailed log messages for each upload
   - CSV is created even if some uploads fail
   - object_location URLs are included for all files (successful or not)

### Azure Configuration Requirements

To enable Azure uploads:
1. Configure in **Function 0: App Settings**:
   - `azure_blob_storage_path`: Must contain `/objs/` folder (e.g., `objs/tdps_archive`)
   - `azure_connection_string`: Full connection string from Azure Portal (encrypted)
2. Ensure your template includes `object_location` column to store URLs
3. Files will be automatically uploaded when you run Function 2

### Azure Storage Structure

DART uses a three-folder structure in Azure:
- `/objs/` - Original source files (renamed to dg_<epoch>.ext)
- `/smalls/` - Medium-sized derivatives (future functions)
- `/thumbs/` - Thumbnail derivatives (future functions)

Function 2 currently uploads only to `/objs/`. Future functions will generate and upload derivatives to `/smalls/` and `/thumbs/`.

### If Azure is Not Configured

If Azure settings are not configured in Function 0:
- CSV export still works normally
- `object_location` column will be empty
- Log message indicates "Azure uploads disabled"
- You can configure Azure later and re-run Function 2 to upload files

## Kill Switch - Emergency Stop

Function 2 supports an **emergency stop** feature for long-running Azure upload operations:

### When to Use the Kill Switch

- Azure uploads are taking too long
- You need to stop the operation immediately
- You want to cancel a batch upload in progress
- Network issues are causing slow uploads

### How to Use

1. While Function 2 is running (during Azure uploads), click the **🛑 Kill Switch** button
2. The button is located in the Functions section, next to the Help Mode checkbox
3. Current file upload will complete, then processing stops
4. A warning message appears: "⚠️ Kill switch activated - stopping after current file"
5. CSV file is created with all files processed up to that point

### What Happens When Kill Switch is Activated

- Current file upload completes (cannot be interrupted mid-upload)
- All remaining files are skipped
- CSV export continues with files processed so far
- Log shows: "⚠️ Kill switch activated - Azure uploads stopped"
- Upload counts reflect partial completion (e.g., "15 succeeded, 0 failed" out of 50 total)
- Files not uploaded will have empty `object_location` fields in CSV

### After Using Kill Switch

- Kill switch automatically resets when you run Function 2 again
- You can re-run Function 2 to complete the remaining uploads
- Already-uploaded files won't be re-uploaded (Azure will return success for existing files)
- CSV will be regenerated with complete upload results

### Kill Switch vs. Force Quit

| Action | Kill Switch | Force Quit (Close App) |
|--------|-------------|------------------------|
| Current upload | Completes | Interrupted (may fail) |
| CSV file | Created with partial results | Not created |
| Azure consistency | Maintained | May have incomplete uploads |
| Resume later | Easy - just run Function 2 again | Must manually track what uploaded |
| Recommended | ✅ Yes - clean stop | ❌ No - only for emergencies |

**Best Practice**: Always use the Kill Switch button instead of force-quitting the application during long-running uploads.

## CollectionBuilder display_template Field

The `display_template` field tells CollectionBuilder how to display each item:

- **image**: Photo gallery layout with zoom/pan
- **video**: Video player layout
- **audio**: Audio player layout  
- **pdf**: PDF viewer layout
- **record**: Generic download/metadata layout for documents and archives
- **compound_object**: For multi-file objects (set by Function 1 if compound grouping enabled)
- **multiple**: Alternative compound object layout
- **panorama**: 360° panoramic image viewer
- **item**: Generic fallback layout

DART automatically maps file types to appropriate layouts. For compound objects (when grouping is enabled), parent objects may need `compound_object` or `multiple` set manually or by future functions.

## Output

**Filename format**: `DART_export_YYYYMMDD_HHMMSS.csv`

**Example**: `DART_export_20240513_143022.csv`

**Location**: Your working/outputs folder

## Example Output Structure

### Simple Export (No Compound Grouping)

Given a template with columns: `objectid,filename,title,creator,date,display_template,format,object_location`

```csv
objectid,filename,title,creator,date,display_template,format,object_location
dg_1715614222,photo_001.jpg,,,,image,jpg,https://account.blob.core.windows.net/objs/collection/dg_1715614222.jpg
dg_1715614223,photo_002.jpg,,,,image,jpg,https://account.blob.core.windows.net/objs/collection/dg_1715614223.jpg
dg_1715614224,document.pdf,,,,pdf,pdf,https://account.blob.core.windows.net/objs/collection/dg_1715614224.pdf
dg_1715614225,recording.mp3,,,,audio,mp3,https://account.blob.core.windows.net/objs/collection/dg_1715614225.mp3
```

**Note**: If Azure is not configured, the `object_location` column will be empty.

### Compound Object Export (Grouping Enabled)

Given a template with columns: `objectid,parentid,filename,title,display_template,format,object_location`

With files: `wit_001.jpg`, `wit_002.jpg`, `wit_003.jpg`

```csv
objectid,parentid,filename,title,display_template,format,object_location
dg_1715614220,,_wit_001.jpg,Wit,compound_object,,
dg_1715614221,dg_1715614220,wit_001.jpg,,image,jpg,https://account.blob.core.windows.net/objs/collection/dg_1715614221.jpg
dg_1715614222,dg_1715614220,wit_002.jpg,,image,jpg,https://account.blob.core.windows.net/objs/collection/dg_1715614222.jpg
dg_1715614223,dg_1715614220,wit_003.jpg,,image,jpg,https://account.blob.core.windows.net/objs/collection/dg_1715614223.jpg
```

**Note**: 
- Compound parent (first row) has underscore-prefixed filename `_wit_001.jpg` (no physical file, just an index based on first child)
- This maintains filename as the source of truth for ALL objects, eliminating the need for objectid fallback
- Child objects have Azure URLs in their object_location field 
- Compound parent has suggested title, display_template is `compound_object`
- Child objects (following rows) have the parent's objectid in their `parentid` field
- The `display_template`, `format`, and `parentid` columns are only populated if they exist in your template

## Kill Switch - Emergency Stop

### When to Use the Kill Switch

Use the **🛑 Kill Switch** button when you need to stop a long-running Azure upload operation:

- Azure uploads are taking longer than expected
- You need to make changes to files or settings before continuing
- Network issues are causing upload failures
- You want to verify results before processing more files
- Emergency situations requiring immediate stop

### How to Use

1. **During Function 2 execution**, if Azure uploads are in progress
2. Click the **🛑 Kill Switch** button (red button next to Help Mode checkbox)
3. The current file upload will complete
4. All remaining uploads will be skipped
5. CSV file is created with partial results (files processed before stop)
6. Status shows "⚠️ Kill switch activated - stopping after current file"

### What Happens When Activated

**Safe behavior:**
- Current file upload completes (no data corruption)
- Remaining files are NOT uploaded
- CSV file is created with all processed files
- object_location URLs included for uploaded files
- object_location blank for skipped files
- File-to-ID mappings saved (can resume later)

**To Resume:**
- Simply run Function 2 again
- Previously uploaded files will be skipped (same IDs)
- New files will be uploaded
- Kill switch automatically resets when Function 2 starts

### Kill Switch vs Force Quit

| Action | Kill Switch | Force Quit (⌘Q or Alt+F4) |
|--------|-------------|---------------------------|
| **When to use** | Stop between files | Emergency only |
| **Current file** | Completes safely | May corrupt |
| **CSV created** | Yes, with partial results | No |
| **Settings saved** | Yes | May be lost |
| **Azure state** | Clean (uploaded files are fine) | Unknown |
| **Resume** | Easy (just run again) | Manual recovery needed |

**Best Practice**: Always use Kill Switch instead of force quitting the application.

## Integration with Other Functions

- **Function 1** analyzes assets and creates compound objects - use it to preview grouping before export
- Object ID assignments are persistent (stored in settings)
- Each file always gets the same object ID, even across multiple exports
- Compound object IDs are also persistent (based on folder + filename pattern)
- Enable **compound object grouping** in Function 0 settings to group related files
- Future functions will merge additional metadata into these CSV files

## Notes

- The CSV uses UTF-8 encoding (supports international characters)
- Object IDs are never reassigned - once a file has an ID, it keeps it
- Compound object IDs are also persistent (same pattern = same compound ID)
- Empty template columns are preserved for manual or automated metadata population
- CollectionBuilder requires `objectid` and `filename` at minimum (both are auto-populated)
- For compound objects, `parentid` is required to link children to parents
- Compound parent objects are written first in the CSV, followed by their children
- Timestamps ensure you never overwrite previous exports
- All exports are saved to your working directory alongside other project files
- Azure uploads happen during export - if configured and template has `object_location` column
- Files are renamed in Azure to match their DG identifiers (e.g., `dg_1715614222.jpg`)
- Original files remain unchanged in your local directories

## Tips

- Run Function 1 first to verify your asset files and IDs before exporting
- Keep your CSV template in version control to maintain consistency
- Use the `core_metadata_csv` setting to designate one CSV as your master file
- You can merge multiple exports into your core CSV as you process batches
- Consider using descriptive filenames without trailing numbers for better compound object grouping

## Error Messages

**"CSV structure template not configured"**: Configure `csv_structure_file` in Function 0

**"No digital asset files found"**: Select files or verify your inputs folder contains supported file types

**"Please set a working/outputs folder first"**: Configure working directory in main UI
