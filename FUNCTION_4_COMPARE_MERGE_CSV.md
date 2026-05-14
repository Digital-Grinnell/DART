# Function 4: Compare and Merge CSV Files

## Purpose
Compare two CSV files to identify matching records, new records, changed values, and records missing from the new file. This function automatically uses your core metadata CSV (from settings) as the baseline and auto-selects the newest DART_export CSV from your working directory for comparison.

## When to Use
Use this function when you want to:
- Compare a new DART_export CSV against your core/master metadata file
- Identify which records have changed between two versions
- Review new records before merging them into your core file
- Audit metadata updates and track what changed
- Prepare a clean merge of two CSV files with full change tracking

## Requirements
- **Working/Outputs folder** must be set
- **Core metadata CSV** must be configured in Function 0 settings
- **At least 1 DART_export CSV file** must exist in the working directory (for comparison)
- Both CSV files must have a `filename` column (unique identifier)
- No duplicate `filename` values within each file

## Comparison Methods

Function 4 supports two comparison methods, selectable in Function 0 settings:

### Pandas-based Comparison (Default)
**Setting**: `CSV_review_with_csvdiff = false`

Uses pandas DataFrame merge operations to:
- Create side-by-side comparison with `_old` and `_new` columns
- Generate three output CSV files with full details
- Show preview dialog with first 10 changes
- Provide per-column change flags
- Skip first data row (headings row)
- Handle empty filenames (used to disable objects from display)

**Best for**: Detailed review, manual inspection, Excel-friendly output

### csvdiff Tool (Alternative)
**Setting**: `CSV_review_with_csvdiff = true`

Uses the csvdiff Python library for comparison:
- Produces JSON output with detailed diff structure
- Creates text summary file with counts
- Faster for large files
- Follows csvdiff's native output format

**Best for**: Programmatic processing, integration with other tools, large datasets

**Note**: Requires `csvdiff` package to be installed: `pip install csvdiff`

## Workflow

1. Configure **core_metadata_csv** in Function 0 settings (used as baseline)

2. Ensure your working directory contains DART_export CSV file(s) to compare

3. Select **Function 4: Compare and Merge CSV Files** from the dropdown

4. Click **Execute Function**

5. DART automatically:
   - Uses core metadata CSV as the "old" file
   - Auto-selects the newest DART_export CSV as the "new" file
   - If newest is same as core, uses second newest DART_export CSV

6. DART performs the comparison and generates output files

7. Review the results dialog showing:
   - Summary counts by status
   - Preview of first 10 changes (pandas mode)
   - Links to output files

## What Gets Compared

DART automatically:
- Uses `filename` as the unique identifier for matching records between files
- Detects all shared columns between both files (excludes `filename`)
- Performs **case-sensitive** comparison of all values
- Normalizes whitespace (strips leading/trailing spaces)
- Treats empty strings and missing values (NaN) as equivalent
- Validates that `filename` is unique in both files
- For display purposes: Uses `filename` to identify records, falls back to `objectid` when filename is blank (e.g., for compound parent objects)

## Output Files

Function 4 generates three timestamped CSV files in your working directory:

### 1. Full Review File
**File**: `merged_review_YYYYMMDD_HHMMSS.csv`

Contains all records from both files with:
- `filename`: The unique identifier
- `status`: Classification (match, new, changed, missing_in_new)
- `_merge`: Pandas merge indicator (both, left_only, right_only)
- `changed_fields`: Comma-separated list of columns that differ
- `fieldname_old`: Original value from old/core CSV
- `fieldname_new`: New value from new CSV
- `fieldname_changed`: Boolean flag (True if values differ)

**Use this for**: Complete audit trail and comprehensive review

### 2. Changes Only File
**File**: `merged_changes_only_YYYYMMDD_HHMMSS.csv`

Contains only records with changes:
- New records (only in new file)
- Changed records (values differ)
- Missing records (only in old file)

Excludes all "match" records for focused review.

**Use this for**: Quick review of what actually changed

### 3. Summary File
**File**: `merge_summary_YYYYMMDD_HHMMSS.csv`

Simple count table:
| status | count |
|--------|-------|
| match | 145 |
| new | 12 |
| changed | 8 |
| missing_in_new | 3 |

**Use this for**: High-level statistics and reporting

## Status Classifications

Each record is classified into one of four categories:

- **match**: `filename` exists in both files, all compared values are identical
- **new**: `filename` appears only in the new file
- **changed**: `filename` exists in both files, one or more values differ
- **missing_in_new**: `filename` appears only in the old file (retired/deleted)

## Side-by-Side Comparison Format

For records that exist in both files, DART preserves both values using suffixes:

**Example for a changed record:**

| filename | status | changed_fields | title_old | title_new | title_changed |
|----------|--------|----------------|-----------|-----------|---------------|
| photo_001.jpg | changed | title | Old Bridge | Bridge Renovated | True |

This makes it easy to:
- See exactly what changed
- Filter by specific fields that changed
- Sort by change status
- Review in Excel or any CSV viewer

## Results Dialog

After comparison completes, a dialog displays:

1. **File Names**: Shows which files were compared
2. **Summary Counts**: Total records and breakdown by status
3. **Preview**: First 10 changed records with:
   - Status icon (✨ new, 📝 changed, ⚠️ missing)
   - Object ID
   - List of fields that changed
4. **Output Files**: Names of the three generated files
5. **Log Link**: Clickable button to view detailed processing log
Core metadata CSV is configured in settings
- Core CSV file exists and is accessible
- At least 1 CSV file available in working directory
- Both files have `filename` column
- No duplicate `filename` values in either file

**Common errors:**

- **"Core metadata CSV not configured"**: Set core_metadata_csv in Function 0 settings
- **"Core CSV file not found"**: Verify core_metadata_csv path is correct in settings
- **"No DART_export CSV files found"**: Run Function 2 to generate a CSV export
- **"Only core CSV found, no DART_export files to compare"**: Run Function 2 to generate a new export to compare
- **"Missing filename column"**: Both files must have this column
- **"Duplicate filename values"**: Fix duplicates before comparison
- **"Error comparing CSVs"**: Check log for pandas/data format issues

## Comparison Logic

Function 4 implements the merge workflow recommended by the PDF guide:

1. Load both CSV files as pandas DataFrames with string dtype
2. Normalize `filename` (strip whitespace)
3. Validate uniqueness of `filename` in both files
4. Auto-detect shared columns (all non-filename columns in both files)
5. Perform outer merge on `filename` (keeps all records from both sides)
6. Use suffixes `_old` and `_new` for overlapping columns
7. Add merge indicator to track record origin
8. Compare all shared columns case-sensitively
9. Classify each row by status
10. Generate `changed_fields` list for each record
11. Add per-column boolean flags (`fieldname_changed`)
12. Reorder columns for clarity
13. Write three output files

## Integration with Other Functions

- **Function 2** generates new CSV exports - compare these against your core file
- **Function 3** updates image_small and image_thumb columns - track which derivatives were added
- **Function 1** creates object IDs - verify they match between exports
- Use Function 4 to audit any CSV-based workflow changes

## Tips

- Run Function 4 after each Function 2 export to track what changed
- Keep your core metadata CSV as the "old" file for consistent comparison
- Review the "changes only" file first for efficiency
- Use the `changed_fields` column to filter by specific field changes
- Sort by `status` in Excel to group records by classification
- TConfigure core_metadata_csv in Function 0 (e.g., `core_metadata.csv`)
2. Run Function 2 to export new batch of assets (creates `DART_export_20260514_143022.csv`)
3. Run Function 4 to compare
4. Selection dialog shows:
   - Core: `core_metadata.csv` (from settings)
   - Available CSVs with `DART_export_20260514_143022.csv` ⭐ (newest)
5. Click "Use Newest" button (or select specific CSV)
6. Review results: 145 matches, 12 new, 8 changed, 3 missing
7. Open `merged_changes_only_20260514_143105.csv` in Excel
8. Review the 23 changes (12+8+3)
9. Manually merge approved changes into your core file, or use the full review file as your new core

## Notes

- **Core CSV is always from settings** - ensures consistent baseline
- **Newest CSV is recommended** for most workflows (highlighted with ⭐)
- Selection dialog shows modification times for all CSV files
- Core CSV is labeled in the list if it's also in working directory
- Comparison is always **case-sensitive** (per user requirements)
- Whitespace is normalized automatically (stripped from values)
- Empty cells and NaN are treated as equivalent
- All shared columns are compared (no manual selection needed)
- Output files are timestamped to avoid overwrite
- Empty cells and NaN are treated as equivalent
- All shared columns are compared (no manual selection needed)
- Output files are timestamped to avoid overwrites
- The newest CSV is always auto-selected as "new"
- Pandas merge uses `validate='one_to_one'` to enforce key uniqueness

## Future Enhancements

Potential additions:
- Option to auto-merge after review (update core CSV directly)
- Filter comparison to specific columns
- Ignore certain columns (like timestamps)
- Case-insensitive comparison mode
- Visual diff viewer in UI
- Export change report as HTML

---

**Related Functions:**
- Function 2: Export Assets to CSV and Azure
- Function 3: Generate Derivatives for CSV and Azure
