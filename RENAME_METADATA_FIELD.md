# Metadata Field Renamer

A Python script for coordinating metadata field name changes across CSV files and CollectionBuilder configuration files.

## Purpose

When you need to rename a metadata field (e.g., `title` → `dc_title`), this script helps ensure consistency by updating:
- CSV metadata file headers
- CollectionBuilder YAML configuration files
- Liquid template references in layouts and includes

## Features

- **Safe by default**: Runs in dry-run mode to preview changes
- **Field name validation**: Prevents problematic characters (colons, periods, slashes, etc.) with helpful error messages
- **Automatic backups**: Creates timestamped backups before modifying files
- **Pattern matching**: Finds field references in multiple contexts (YAML keys, Liquid variables, quoted strings)
- **Clear reporting**: Shows exactly what will change or was changed
- **Selective updates**: Can update just CSV, or both CSV and CollectionBuilder configs

## Installation

No installation needed - it's a standalone Python script. Requires Python 3.6+.

## Usage

### Basic Syntax

```bash
python rename_metadata_field.py --csv <path> --old-field <name> --new-field <name> [options]
```

### Options

- `--csv` - Path to CSV metadata file (required)
- `--old-field` - Current field name to rename (required)
- `--new-field` - New field name (required)
- `--cb-dir` - Path to CollectionBuilder repository root (optional)
- `--apply` - Actually apply changes (default is dry-run preview)
- `--no-backup` - Skip creating backup files (not recommended)

### Examples

**1. Preview changes to CSV only (dry run):**
```bash
python rename_metadata_field.py \
  --csv ~/Documents/TDPS-Archive-data/TDPS_DART_Core.csv \
  --old-field title \
  --new-field dc_title
```

**2. Apply changes to CSV only:**
```bash
python rename_metadata_field.py \
  --csv ~/Documents/TDPS-Archive-data/TDPS_DART_Core.csv \
  --old-field title \
  --new-field dc_title \
  --apply
```

**3. Preview changes to CSV and CollectionBuilder configs:**
```bash
python rename_metadata_field.py \
  --csv ~/Documents/TDPS-Archive-data/TDPS_DART_Core.csv \
  --old-field title \
  --new-field dc_title \
  --cb-dir ~/GitHub/tdps-collectionbuilder
```

**4. Apply all changes (CSV + CollectionBuilder):**
```bash
python rename_metadata_field.py \
  --csv ~/Documents/TDPS-Archive-data/TDPS_DART_Core.csv \
  --old-field title \
  --new-field dc_title \
  --cb-dir ~/GitHub/tdps-collectionbuilder \
  --apply
```

**5. Rename another field:**
```bash
python rename_metadata_field.py \
  --csv ~/Documents/TDPS-Archive-data/TDPS_DART_Core.csv \
  --old-field description \
  --new-field dc_description \
  --cb-dir ~/GitHub/tdps-collectionbuilder \
  --apply
```

## What Gets Updated

### In CSV Files
- Column header in the first row
- All data rows remain unchanged (only header changes)

### In CollectionBuilder Files
The script searches these locations and patterns:

**Files checked:**
- `_config.yml` - Main site configuration
- `_data/config-*.yml` - Metadata display configuration
- `_data/theme.yml` - Theme configuration
- `pages/*.md` - Page content
- `_layouts/*.html` - Layout templates
- `_includes/*.html` - Include templates

**Patterns matched:**
- Liquid metadata variables: `item.title` → `item.dc_title` (collection item metadata)
- Liquid data references: `site.data.metadata.title` → `site.data.metadata.dc_title`
- In metadata config files (`_data/config-*.yml`):
  - YAML keys: `title:` → `dc_title:`
  - Quoted strings: `"title"` → `"dc_title"`

**What is NOT changed:**
- **`page.title`** - This refers to page front matter (About, Browse, etc.), NOT metadata fields
- Site-level config in `_config.yml` (e.g., site title)
- UI labels and display text (in most cases)
- Field names are only changed in metadata contexts

**Important**: In CollectionBuilder:
- `page.title` = The title of a site page from its YAML front matter (e.g., "About", "Browse")
- `item.title` = The title field from your CSV metadata (collection item)
- These are DIFFERENT and must be treated differently!
- Field names are only changed in metadata contexts

## Safety Features

### Dry Run by Default
Without `--apply`, the script only shows what would change:
```
[DRY RUN] Processing CSV: TDPS_DART_Core.csv
  ✓ Found field 'title' at column 2
    Will rename to: 'dc_title'
    Affects 145 data rows
```

### Automatic Backups
Before modifying any file, creates a timestamped hidden backup (dotted filename):
```
.TDPS_DART_Core.backup_20260609_143022.csv
._config.backup_20260609_143022.yml
```

Backup files are hidden (prefixed with `.`) to prevent CollectionBuilder from processing them as source files.

### Validation
- **Rejects problematic field names**: Blocks colons, periods, slashes, and other characters that cause issues
- Provides helpful suggestions for valid alternatives (e.g., `dc_title` instead of `dc:title` or `dc.title`)
- **Encourages underscores**: Recommends underscore separators for namespaced fields
- Checks that CSV file exists and is valid
- Verifies old field exists in CSV headers
- Prevents duplicate field names
- Reports any errors clearly

## Workflow Example

**Scenario**: Rename `title` to `dc_title` in TDPS Archive project

1. **Preview the changes:**
   ```bash
   python rename_metadata_field.py \
     --csv ~/Documents/TDPS-Archive-data/TDPS_DART_Core.csv \
     --old-field title \
     --new-field dc_title \
     --cb-dir ~/GitHub/tdps-collectionbuilder
   ```

2. **Review the output:**
   ```
   Processing CSV: TDPS_DART_Core.csv
     ✓ Found field 'title' at column 2
       Will rename to: 'dc_title'
   
   Searching CollectionBuilder configs
     ✓ _config.yml: 3 replacement(s)
     ✓ _data/config-browse.yml: 2 replacement(s)
     ✓ _layouts/item.html: 5 replacement(s)
   ```

3. **If everything looks good, apply:**
   ```bash
   python rename_metadata_field.py \
     --csv ~/Documents/TDPS-Archive-data/TDPS_DART_Core.csv \
     --old-field title \
     --new-field dc_title \
     --cb-dir ~/GitHub/tdps-collectionbuilder \
     --apply
   ```

4. **Test your CollectionBuilder site:**
   ```bash
   cd ~/GitHub/tdps-collectionbuilder
   bundle exec jekyll serve
   ```

5. **If issues occur, restore from backups:**
   ```bash
   # Backups are hidden files in the same directories with .backup_TIMESTAMP suffix
   # Use ls -la to see hidden files
   ls -la ~/Documents/TDPS-Archive-data/ | grep backup
   
   # Restore from backup
   mv .TDPS_DART_Core.backup_20260609_143022.csv TDPS_DART_Core.csv
   ```

## Common Field Renames

Here are common field renames to add Dublin Core prefixes:

```bash
# Dublin Core fields
title → dc_title
description → dc_description
creator → dc_creator
subject → dc_subject
date → dc_date
format → dc_format
rights → dc_rights
source → dc_source
coverage → dc_coverage
language → dc_language

# DCMI Type
type → dcterms_type

# Example: Rename multiple fields
for field in title description creator subject; do
  python rename_metadata_field.py \
    --csv metadata.csv \
    --old-field $field \
    --new-field dc_$field \
    --cb-dir ../collectionbuilder \
    --apply
done
```

## Troubleshooting

**"Field 'title' not found in CSV headers"**
- Check that the field name matches exactly (case-sensitive)
- View CSV headers: `head -1 your_file.csv`

**"Field 'dc_title' already exists in CSV headers"**
- The new field name is already in use
- Choose a different new name or check if rename already happened

**"CollectionBuilder directory not found"**
- Verify the path to your CollectionBuilder repository
- Use absolute path if relative path doesn't work

**Script finds no matches in CollectionBuilder files**
- The field might not be used in config files
- Check if the field is only used in CSV/data files
- This is normal for fields that aren't displayed on the site

**"Conflict: destination is shared by multiple files" (CollectionBuilder build warning)**
- Old non-hidden backup files are being processed by CollectionBuilder
- Solution: Run `bash cleanup_old_backups.sh <collectionbuilder_dir>` to remove old backup files
- New backups are hidden (dotted) and won't cause this issue

**Site title or page titles disappeared after renaming**
- The script may have changed some page-level titles (in front matter)
- Site title in `_config.yml` should NOT be changed (protected in v2.2.1+)
- See [FIXING_RENAME_ISSUES.md](FIXING_RENAME_ISSUES.md) for detailed troubleshooting
- Always preview changes with dry-run before applying

## Notes

- **Always run without `--apply` first to preview changes** - review the output carefully
- **Test after renaming**: Verify your site builds and displays correctly before renaming additional fields
- Keep backup files until you've verified the site works correctly
- Backup files are hidden (dotted) to prevent CollectionBuilder from processing them
- Use `ls -la` to see hidden backup files in directories
- **Use underscores for separators**: Always use `dc_title` not `dc:title` or `dc.title`
  - Colons cause issues in YAML parsing
  - Periods conflict with Liquid object notation (`item.title` means "title property of item")
  - Underscores are safe and recommended
- The script preserves all data - only header/config names change
- Changes are atomic per file (either all changes apply or none do)
- **Distinction**: Page titles (front matter) vs. metadata fields (CSV) are different - see [FIXING_RENAME_ISSUES.md](FIXING_RENAME_ISSUES.md)

## Integration with DART

This script complements DART's metadata workflow:
1. Use DART to generate metadata CSV exports
2. Use this script to rename fields for Dublin Core compliance
3. Use DART's Function 4 to compare/merge updated CSV
4. Deploy updated metadata to CollectionBuilder

## Requirements

- Python 3.6 or higher
- No additional Python packages required (uses only standard library)
- Read/write access to CSV and CollectionBuilder files

## License

Part of the DART project. Same license applies (MIT).
