# Function 5: Generate Seeklight Metadata

Function 5 sends selected source media directly to the Seeklight Public API, waits for processing, maps the returned metadata into DART's CollectionBuilder CSV format, and saves a transformed CSV for Function 6.

## Setup

The Seeklight Python library is installed from the pinned revision in `python_requirements.txt` the next time DART installs its dependencies. For distributed installs, configure the per-user `seeklight_credentials.json` file described in `INSTALLATION.md`. DART first checks both `SEEKLIGHT_API_BASE_URL` and `SEEKLIGHT_API_KEY` in the environment, then the per-user file, then the sibling `Seeklight-Resources/api-info/url.md` and `key.md` files used for development. An incomplete pair of environment variables is an error. Never include credential files in the distribution.

If credentials are missing or invalid, Function 5 shows the setup error in its dialog before submission and logs the details. You can correct the credential file and retry without sending a request.

Each source that is submitted for processing uses one item from the Seeklight allowance. Raw API results and any transcript are retained in `.DART-working-directory` because Seeklight only keeps results for a limited time.

## Workflow

1. Set the working folder and core metadata CSV in Function 0.
2. In the main Files Selection area, select one or more image/PDF files. Optionally select a Seeklight Page Folder to submit its files as one multipage document; the folder is used only by Function 5. Supported images include JPEG, TIFF, PNG, GIF, BMP, WebP, and HEIC.
3. Open Function 5 to review the selected sources. Metadata is always requested. Optionally request a transcript or image alt text, and provide context (up to 2,000 characters).
4. Optionally enable **Override merge target filename** to write the same `original_file_name` for every result. Otherwise, each source filename is used for Function 6 matching.
5. Select **Generate Metadata**. The Function 5 dialog shows the current source, Seeklight's latest reported stage, and the number and percentage of sources processed; it refreshes the elapsed waiting time every 15 seconds while the API is quiet. The percentage counts attempted sources, not time remaining for the current source, and can stay at 0% while the first document is queued. Keep DART open until processing finishes. Detailed progress and per-source errors also appear in the DART log.
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
