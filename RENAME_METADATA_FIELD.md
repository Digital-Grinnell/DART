# Metadata Field Renamer

A Python script for coordinating metadata field name changes across CSV files and CollectionBuilder configuration files.

## Purpose

Use this script when an older CollectionBuilder project still has legacy Dublin Core-prefixed field names such as `dc_title` and needs to be brought back to the plain CSV field names expected by Digital-Grinnell/collectionbuilder-csv and upstream CollectionBuilder CSV.

Typical examples:
- `dc_title` → `title`
- `dc_description` → `description`
- `dc_date` → `date`

## Features

- Safe by default: runs in dry-run mode until you add `--apply`
- Updates CSV headers plus related CollectionBuilder config/template references
- Creates timestamped hidden backups before modifying files
- Rejects new target names that still use the retired `dc_` prefix
- Rejects colon and period field names that break YAML or Liquid parsing
- Preserves `page.title` and other page/front-matter semantics while updating metadata references

## Usage

```bash
python rename_metadata_field.py --csv <path> --old-field <name> --new-field <name> [options]
```

Options:
- `--csv` required CSV metadata path
- `--old-field` existing field name
- `--new-field` replacement field name
- `--cb-dir` optional CollectionBuilder repository root
- `--apply` write changes instead of previewing them
- `--no-backup` skip backup creation

## Examples

Preview a header cleanup:

```bash
python rename_metadata_field.py \
  --csv ~/Documents/TDPS-Archive-data/TDPS_DART_Core.csv \
  --old-field dc_title \
  --new-field title
```

Apply the same cleanup to CSV plus CollectionBuilder configs:

```bash
python rename_metadata_field.py \
  --csv ~/Documents/TDPS-Archive-data/TDPS_DART_Core.csv \
  --old-field dc_title \
  --new-field title \
  --cb-dir ~/GitHub/tdps-collectionbuilder \
  --apply
```

Normalize another standard field:

```bash
python rename_metadata_field.py \
  --csv ~/Documents/TDPS-Archive-data/TDPS_DART_Core.csv \
  --old-field dc_description \
  --new-field description \
  --cb-dir ~/GitHub/tdps-collectionbuilder \
  --apply
```

## What Gets Updated

In CSV files:
- the first-row header value only

In CollectionBuilder files:
- `_data/config-*.yml`
- `_data/config-*.csv`
- `_layouts/*.html`
- `_includes/*.html`
- `pages/*.md`

Patterns updated in metadata contexts:
- `item.dc_title` → `item.title`
- `site.data.metadata.dc_title` → `site.data.metadata.title`
- metadata config keys or quoted field values that still use legacy field names

What does not change:
- `page.title`
- site title in `_config.yml`
- display labels unless they directly encode the field name

## Workflow

1. Preview the rename without `--apply`.
2. Review the reported CSV/config/template replacements.
3. Re-run with `--apply`.
4. Test the CollectionBuilder site.
5. If needed, restore from the hidden `.backup_YYYYMMDD_HHMMSS` files.

## Batch Cleanup

For standard Dublin Core fields, use the batch helper:

```bash
bash batch_rename_dublin_core.sh metadata.csv ../collectionbuilder
```

For CSV-based metadata config files that still reference `dc_` field names:

```bash
python3 fix_config_csv_fields.sh ../collectionbuilder
```

## Validation Rules

- Plain field names such as `title`, `description`, and `date` are the preferred targets.
- Colons and periods are rejected because they cause YAML/Liquid parsing ambiguity.
- New target names beginning with `dc_` are rejected so DART stays aligned with CollectionBuilder CSV.

## Troubleshooting

If the old field is not found:
- verify the exact CSV header with `head -1 your_file.csv`

If the new field already exists:
- the rename may already have happened, or another column already uses that name

If titles or dates disappear from a CollectionBuilder site after cleanup:
- run `python3 fix_config_csv_fields.sh <collectionbuilder_dir>`
- review [FIXING_RENAME_ISSUES.md](FIXING_RENAME_ISSUES.md)

## Integration with DART

This cleanup is now a required sync step whenever a DART-managed collection still uses `dc_`-prefixed CSV fields. DART Functions 5 and 6, Digital-Grinnell/collectionbuilder-csv, and upstream CollectionBuilder CSV all now assume the unprefixed field names are canonical.
