# Function 5: Generate Seeklight Metadata

Function 5 sends selected source media directly to the Seeklight Public API, waits for processing, maps the returned metadata into DART's CollectionBuilder CSV format, and saves a transformed CSV for Function 6.

## Setup

The Seeklight Python library is installed from the pinned revision in `python_requirements.txt` the next time DART installs its dependencies. Configure both `SEEKLIGHT_API_BASE_URL` and `SEEKLIGHT_API_KEY` in the environment, or provide non-empty `url.md` and `key.md` files in the sibling `Seeklight-Resources/api-info/` directory. The API key file is local configuration and must not be committed.

Each source that is submitted for processing uses one item from the Seeklight allowance. Raw API results and any transcript are retained in `.DART-working-directory` because Seeklight only keeps results for a limited time.

## Workflow

1. Set the working folder and core metadata CSV in Function 0.
2. Open Function 5 and add one or more image/PDF files, or add a folder whose files form one multipage document. Supported images include JPEG, TIFF, PNG, GIF, BMP, WebP, and HEIC.
3. Metadata is always requested. Optionally request a transcript or image alt text, and provide context (up to 2,000 characters).
4. Optionally enable **Override merge target filename** to write the same `original_file_name` for every result. Otherwise, each source filename is used for Function 6 matching.
5. Select **Generate Metadata**. Progress and per-source errors appear in the DART log while processing continues in the background.
6. When complete, use Function 6 to compare and merge the generated `DART_seeklight_transformed_*.csv` with the core metadata CSV.

The transformed rows leave `objectid` blank for Function 6 matching. The mapping template controls field names and default values; unmapped API fields are added with underscore-prefixed names. Multi-value separators are converted from ` | ` to `; `. Each run also saves the raw results JSON and any transcript under `.DART-working-directory`.

### Customizing Field Mapping

Edit `seeklight_mapping_template.json` in the DART folder to customize how Seeklight fields map to your core metadata columns:

```json
{
  "field_mapping": {
    "Title": "title",
    "Description": "description",
    "Creator": "creator"
  },
  "default_values": {
    "language": "eng"
  }
}
```

- **field_mapping**: Maps Seeklight column names (left) to your core CSV column names (right)
  - **Sync note**: Use plain CollectionBuilder CSV field names here to stay aligned with Digital-Grinnell/collectionbuilder-csv and its upstream repository.
  - **Note**: Seeklight columns may have bracketed numbers like `Title[3101377]`. The mapping handles both `Title` and `Title[3101377]` automatically - you only need to specify the base name without brackets.
  - **Empty string values** (e.g., `"Keywords": ""`) are treated as unmapped - those fields will be auto-created as new columns if Seeklight provides data for them.
- **default_values**: Sets default values for columns not provided by Seeklight
- **Source filename**: Function 5 uses the selected source's filename as `original_file_name`.
- **Multi-value fields**: Seeklight uses pipe separators (` | `) for multi-value fields. The transformation automatically converts these to DART's semicolon separators (`;`) for compatibility.
- **Unmapped fields**: If Seeklight provides data in fields not listed in your mapping template, new columns are automatically created in the output CSV. These column names start with an underscore and use lowercase with spaces converted to underscores (e.g., "Named Entities" → "_named_entities"). You can later add these to your mapping template if desired.
- **Target Record Override**: Use this when you want to merge Seeklight metadata with a different record than what the Seeklight original_file_name would normally match. Common use cases:
  - You renamed the file after uploading to Seeklight
  - Seeklight data is for a compound parent object while filenames reference children
  - You want to merge multiple Seeklight analyses into a single target record
  - When checked and filled in, ALL rows in the transformed CSV will use the specified original_file_name instead of the Seeklight filename values
- **objectid handling**: The transformation **always leaves objectid empty** because Seeklight generates new metadata. Use Function 6 to compare and merge with existing core metadata using original_file_name-based matching.
