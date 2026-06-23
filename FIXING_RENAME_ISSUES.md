# Fixing Legacy Prefix Renaming Issues

## Problem

If an older DART workflow renamed metadata fields to `dc_`-prefixed versions, CollectionBuilder pages may stop rendering titles or browse metadata correctly because current CollectionBuilder CSV themes expect plain field names such as `title`.

## What Should Exist Now

Metadata references:
- `item.title`
- `site.data.metadata.title`
- `field,title` rows in CSV config files

Page/front-matter references:
- `page.title`
- `site.title`

## Common Symptoms

- Browse page has blank titles or dates
- Item layouts still reference `item.dc_title`
- Config CSV rows still point at `dc_title`
- `_config.yml` or page front matter was changed accidentally

## Quick Checks

Check for lingering legacy metadata references:

```bash
grep -r "dc_" _data _includes _layouts pages
```

Check the site title:

```bash
grep "^title:" _config.yml
```

## Fixes

Normalize the CSV header and related metadata references:

```bash
python3 rename_metadata_field.py \
  --csv metadata.csv \
  --old-field dc_title \
  --new-field title \
  --cb-dir ~/GitHub/GCCB-TDPS-Archive \
  --apply
```

Normalize CSV-based config files if needed:

```bash
python3 fix_config_csv_fields.sh ~/GitHub/GCCB-TDPS-Archive
```

## Template Distinction

Use `page.title` for site pages and `item.title` for item metadata.

```liquid
<title>{{ page.title }} | {{ site.title }}</title>
<h1>{{ item.title }}</h1>
```

## Restore From Backup

If the rename touched the wrong files, restore the hidden backups:

```bash
find . -name ".*.backup_*" -type f
```

Then copy the needed backup over the modified file and rerun the rename in dry-run mode first.

## Prevention

- Always preview with dry-run before applying changes.
- Keep backups until the site renders correctly.
- Treat removing `dc_` prefixes as part of syncing a DART collection with Digital-Grinnell/collectionbuilder-csv and upstream CollectionBuilder CSV.
