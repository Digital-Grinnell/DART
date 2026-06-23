# Quick Fix: Normalize Legacy Dublin Core Field Names

## Problem

Older DART guidance converted CSV headers to `dc_`-prefixed forms such as `dc_title`. That convention no longer matches Digital-Grinnell/collectionbuilder-csv or upstream CollectionBuilder CSV, which both expect plain field names such as `title`.

Separate but related problem: field names written as `dc:title` or `dc.title` also break YAML or Liquid parsing.

## Correct Target Format

Use plain field names:
- `title`
- `description`
- `creator`
- `date`

Do not keep any of these legacy variants in active CSV/config/template files:
- `dc_title`
- `dc:title`
- `dc.title`

## Recommended Fix

Rename legacy fields back to their standard CollectionBuilder CSV names.

```bash
python3 scripts/rename_metadata_field.py \
  --csv ~/GitHub/GCCB-TDPS-Archive/_data/TDPS_DART_Core.csv \
  --old-field dc_title \
  --new-field title \
  --cb-dir ~/GitHub/GCCB-TDPS-Archive \
  --apply
```

If you used colon or period variants, normalize those to the same plain field name:

```bash
python3 scripts/rename_metadata_field.py \
  --csv ~/GitHub/GCCB-TDPS-Archive/_data/TDPS_DART_Core.csv \
  --old-field "dc:title" \
  --new-field title \
  --cb-dir ~/GitHub/GCCB-TDPS-Archive \
  --apply
```

## Batch Cleanup

To remove legacy prefixes from all standard Dublin Core fields in one pass:

```bash
bash scripts/batch_rename_dublin_core.sh \
  ~/GitHub/GCCB-TDPS-Archive/_data/TDPS_DART_Core.csv \
  ~/GitHub/GCCB-TDPS-Archive
```

If your CollectionBuilder theme uses CSV-based metadata configs, also run:

```bash
python3 scripts/fix_config_csv_fields.sh ~/GitHub/GCCB-TDPS-Archive
```

## Why This Matters

- DART Function 5 mappings now target plain field names.
- DART Function 6 merge review now expects plain field names.
- Digital-Grinnell/collectionbuilder-csv and upstream CollectionBuilder CSV both use unprefixed CSV headers.

## Validation

After cleanup, test the site:

```bash
cd ~/GitHub/GCCB-TDPS-Archive
bundle exec jekyll serve
```

Verify that titles, browse metadata, and item pages still render correctly.
