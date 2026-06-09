# Fixing Over-Aggressive Field Renaming

## Problem
When renaming a metadata field like "title", the script may have changed references that shouldn't be changed, such as:
- Site title in `_config.yml`
- Page titles in front matter
- UI labels and display text

## Updated Script (v2.2.1+)

The script has been updated to be more selective:

### What Gets Changed (Metadata Fields Only):
✅ **Liquid variable references** (always metadata):
-  `item.title` → `item.dc_title`
- `page.title` → `page.dc_title` 
- `site.data.metadata.title` → `site.data.metadata.dc_title`

✅ **Metadata config files** (`_data/config-*.yml`):
- YAML keys: `title:` → `dc_title:`
- Quoted values: `"title"` → `"dc_title"`

### What DOESN'T Get Changed (Site Configuration):
❌ **Site-level config** in `_config.yml`:
- `title:` (site title) - NOT changed
- `url:`, `baseurl:`, etc. - NOT changed

❌ **Page front matter** in individual `.md` files:
- `title:` (page title) - may still change, see below

## If Your Site Title Disappeared

### Check _config.yml
```bash
cd ~/GitHub/GCCB-TDPS-Archive
grep "^title:" _config.yml
```

**If it shows `dc.title:` or `dc_title:`** instead of `title:`:
```bash
# Find the backup
ls -la | grep "\.config\.backup"

# Restore from backup
mv .config.backup_TIMESTAMP.yml _config.yml
```

**Or manually fix it:**
```bash
# Edit _config.yml
nano _config.yml

# Change this:
dc_title: Your Site Name

# Back to this:
title: Your Site Name
```

### Check Banner/Layout Files

If the banner is looking for `page.title` but pages now have `page.dc_title`:

```bash
# Search for changed references in layouts
grep -r "page\.dc_title\|page\.dc\.title" _includes/ _layouts/

# Search for what the banner actually uses
grep -A 5 "banner\|title" _includes/collection-banner.html
```

## Preventing Future Issues

### 1. Always Preview First
```bash
# DRY RUN - see what would change
python3 rename_metadata_field.py \
  --csv metadata.csv \
  --old-field title \
  --new-field dc_title \
  --cb-dir ~/GitHub/GCCB-TDPS-Archive
```

Review the output carefully before adding `--apply`.

### 2. Rename Less Common Fields First
Test with a field that's less commonly used:
```bash
# Try with a less common field first
python3 rename_metadata_field.py \
  --csv metadata.csv \
  --old-field creator \
  --new-field dc_creator \
  --cb-dir ~/GitHub/GCCB-TDPS-Archive \
  --apply
```

### 3. Test Your Site After Each Field
```bash
cd ~/GitHub/GCCB-TDPS-Archive
bundle exec jekyll serve
```

Visit http://localhost:4000 and verify everything works before renaming the next field.

### 4. Keep Backups
Don't delete backup files until you've verified the site works:
```bash
# List all backup files
find ~/GitHub/GCCB-TDPS-Archive -name ".*.backup_*" -type f

# These are your safety net!
```

## Manual Fixes for Common Issues

### Site Title Missing
**File:** `_config.yml`
**Fix:** Ensure `title:` exists at the top level
```yaml
title: Your Site Name
tagline: Your tagline
```

### Page Banner Title Missing
**Files:** `_layouts/*.html`, `_includes/*.html`
**Issue:** Looking for `page.title` but metadata field was renamed
**Fix:** Site pages should use `page.title` (page's front matter), items should use `item.dc_title` (metadata field)

```liquid
<!-- For site pages (About, Browse, etc.) -->
<h1>{{ page.title }}</h1>

<!-- For collection items (actual artifacts) -->
<h1>{{ item.dc_title }}</h1>
```

### Distinguish Between Page Title and Metadata Title

In CollectionBuilder:
- **Page title** = The title of a site page (About, Browse, Home) - stored in page front matter
- **Metadata title** = The title field in your CSV metadata - used for collection items

These are DIFFERENT and should be handled differently:

```liquid
<!-- Page layouts (_layouts/page.html, etc.) -->
<!-- These use page.title from front matter - DON'T rename -->
<title>{{ page.title }} | {{ site.title }}</title>

<!-- Item layouts (_layouts/item.html, etc.) -->
<!-- These use metadata fields - DO rename -->
<h1>{{ item.dc_title }}</h1>
```

## Restore Everything from Backups

If you want to start over:

```bash
cd ~/GitHub/GCCB-TDPS-Archive

# Find all backup files
find . -name ".*.backup_*" -type f > backup_list.txt

# Restore each one (example)
while read backup; do
    original="${backup%.backup_*}"
    original="${original#.}"  # Remove leading dot
    if [ -f "$backup" ]; then
        echo "Restoring: $original"
        cp "$backup" "$original"
    fi
done < backup_list.txt
```

## Contact / Help

If you're still having issues:
1. Check what changed: `git diff` (if using version control)
2. Look at the dry-run output before applying changes
3. Test each field rename individually
4. Keep backup files until everything works

The updated script (v2.2.1+) is more conservative and should prevent most issues, but always preview changes first!
