# Function 2: Export Assets to CSV

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

3. Select **Function 2: Export Assets to CSV** from the dropdown

4. Click **Execute Function**

5. A timestamped CSV file is created in your working directory

## What Gets Exported

The function automatically populates these CollectionBuilder fields from your assets:

- **objectid**: Unique DG identifier (format: `dg_<epoch>`)
- **filename**: Original filename (blank for compound parent objects)
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

**Filename format**: `dart_export_YYYYMMDD_HHMMSS.csv`

**Example**: `dart_export_20240513_143022.csv`

**Location**: Your working/outputs folder

## Example Output Structure

### Simple Export (No Compound Grouping)

Given a template with columns: `objectid,filename,title,creator,date,display_template,format`

```csv
objectid,filename,title,creator,date,display_template,format
dg_1715614222,photo_001.jpg,,,,image,jpg
dg_1715614223,photo_002.jpg,,,,image,jpg
dg_1715614224,document.pdf,,,,pdf,pdf
dg_1715614225,recording.mp3,,,,audio,mp3
```

### Compound Object Export (Grouping Enabled)

Given a template with columns: `objectid,parentid,filename,title,display_template,format`

With files: `wit_001.jpg`, `wit_002.jpg`, `wit_003.jpg`

```csv
objectid,parentid,filename,title,display_template,format
dg_1715614220,,,Wit,compound_object,
dg_1715614221,dg_1715614220,wit_001.jpg,,image,jpg
dg_1715614222,dg_1715614220,wit_002.jpg,,image,jpg
dg_1715614223,dg_1715614220,wit_003.jpg,,image,jpg
```

**Note**: 
- Compound parent object (first row) has no filename, has suggested title, display_template is `compound_object`
- Child objects (following rows) have the parent's objectid in their `parentid` field
- The `display_template`, `format`, and `parentid` columns are only populated if they exist in your template

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
