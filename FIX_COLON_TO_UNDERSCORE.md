# Quick Fix: Using Underscores in Field Names

## Problem
Field names with **colons** (like `dc:title`) or **periods** (like `dc.title`) cause syntax issues in YAML, Liquid templates, and other CollectionBuilder components.

### Why These Characters Fail:
- **Colons (`:`)**: Require special quoting in YAML and can break Liquid template parsing
- **Periods (`.`)**: Conflict with Liquid object notation (e.g., `item.title` means "title property of item")

## Solution
**Always use underscores**: `dc_title`, `dc_description`, etc.

## Protection Built-In

As of version 2.2.1, the `rename_metadata_field.py` script **automatically prevents** you from using problematic field names:

```bash
# This will be rejected with a helpful error message
python3 rename_metadata_field.py \
  --csv metadata.csv \
  --old-field title \
  --new-field "dc:title"

# Error: Field name 'dc:title' contains a colon (:)...
#   Suggestion: Use underscores instead. For example: 'dc_title'

# This will also be rejected
python3 rename_metadata_field.py \
  --csv metadata.csv \
  --old-field title \
  --new-field "dc.title"

# Error: Field name 'dc.title' contains a period (.)...
#   Suggestion: Use underscores instead. For example: 'dc_title'
```

The script validates field names and rejects:
- **Colons (`:`)** - causes YAML/Liquid parsing issues
- **Periods (`.`)** - conflicts with Liquid object notation
- Slashes (`/`, `\`) - filesystem conflicts
- Brackets (`[`, `]`, `{`, `}`) - parsing issues
- Special characters (`<`, `>`, `|`, `?`, `*`, `"`, `'`) - various conflicts

**Valid characters**: Letters, numbers, underscores (`_`), and hyphens (`-`)

**Recommended**: Use underscores for namespace separators (e.g., `dc_title`, `dcterms_type`)

---

## If You Already Applied dc:title or dc.title Format

If you already ran the rename script with `dc:title` or `dc.title` format, here's how to fix it:

### Step 1: Revert to original field name

```bash
cd /Users/mcfatem/GitHub/DART

# If you used dc:title format, revert it:
python rename_metadata_field.py \
  --csv ~/GitHub/GCCB-TDPS-Archive/_data/TDPS_DART_Core.csv \
  --old-field "dc:title" \
  --new-field title \
  --cb-dir ~/GitHub/GCCB-TDPS-Archive \
  --apply

# OR if you used dc.title format, revert it:
python rename_metadata_field.py \
  --csv ~/GitHub/GCCB-TDPS-Archive/_data/TDPS_DART_Core.csv \
  --old-field "dc.title" \
  --new-field title \
  --cb-dir ~/GitHub/GCCB-TDPS-Archive \
  --apply
```

### Step 2: Apply the correct underscore format

```bash
# Now apply the correct underscore format (title → dc_title)
python rename_metadata_field.py \
  --csv ~/GitHub/GCCB-TDPS-Archive/_data/TDPS_DART_Core.csv \
  --old-field title \
  --new-field dc_title \
  --cb-dir ~/GitHub/GCCB-TDPS-Archive \
  --apply
```

### Alternative: Use Backups

If the rename just happened, you have automatic backup files (hidden with dot prefix):

```bash
cd ~/GitHub/GCCB-TDPS-Archive

# Find the backup files (they are hidden files with timestamps)
# Use -name pattern with dot prefix
find . -name ".*.backup_*" -type f | head -20

# Or use ls -la to see hidden files in a specific directory
ls -la _data/ | grep backup

# Example: restore CSV from backup
mv _data/TDPS_DART_Core.csv _data/TDPS_DART_Core.csv.broken
mv _data/.TDPS_DART_Core.backup_20260609_*.csv _data/TDPS_DART_Core.csv

# Restore config files similarly (remember the dot prefix)
mv .config.backup_20260609_*.yml config.yml

# Then run Step 2 above with the correct format
```

---

## Batch Converting All Fields

Once you've fixed the title field, you can convert all other Dublin Core fields:

```bash
cd /Users/mcfatem/GitHub/DART

# This will rename all standard fields to dc_ format
bash batch_rename_dublin_core.sh \
  ~/GitHub/GCCB-TDPS-Archive/_data/TDPS_DART_Core.csv \
  ~/GitHub/GCCB-TDPS-Archive
```

The batch script will:
1. Check which fields exist in your CSV
2. Show you a preview of all changes
3. Prompt for confirmation
4. Apply changes with automatic backups

---

## Testing Your Site

After applying the underscore format, test your CollectionBuilder site:

```bash
cd ~/GitHub/GCCB-TDPS-Archive
bundle exec jekyll serve
```

Visit http://localhost:4000 and verify that:
- Items display correctly
- Browse page works
- Search functions properly
- Metadata fields appear as expected

---

## Why Underscores Work Better

### Problems with Colons (`:`)
- YAML parsers may require quotes: `"dc:title": value`
- Liquid can misinterpret as namespace: `{{ item.dc:title }}`
- Some tools don't handle colons in identifiers
- CSS selectors and JavaScript may have issues

### Problems with Periods (`.`)
- **Liquid uses dots for object properties**: `item.title` means "the title property of the item object"
- **Creates ambiguity**: If you name a field `dc.title`, Liquid templates would see `item.dc.title` as "the title property of the dc property of item" instead of a single field name
- **Hard to distinguish**: `{{ item.dc.title }}` - is this field "dc.title" or property chain "dc" → "title"?
- Makes debugging confusing and error-prone

### Benefits of Underscores (`_`):
- Works everywhere without special handling
- No quoting needed in YAML
- Standard identifier character
- Compatible with all tools and parsers
- Follows common naming conventions

---

## Field Reference Table

Standard Dublin Core fields with **correct underscore format**:

| Original Field | ✅ Correct Format (underscore) | ❌ Don't Use (colon) | ❌ Don't Use (period) |
|----------------|--------------------------------|----------------------|-----------------------|
| title          | dc_title                       | dc:title             | dc.title              |
| description    | dc_description                 | dc:description       | dc.description        |
| creator        | dc_creator                     | dc:creator           | dc.creator            |
| subject        | dc_subject                     | dc:subject           | dc.subject            |
| date           | dc_date                        | dc:date              | dc.date               |
| format         | dc_format                      | dc:format            | dc.format             |
| rights         | dc_rights                      | dc:rights            | dc.rights             |
| source         | dc_source                      | dc:source            | dc.source             |
| coverage       | dc_coverage                    | dc:coverage          | dc.coverage           |
| language       | dc_language                    | dc:language          | dc.language           |
| relation       | dc_relation                    | dc:relation          | dc.relation           |
| identifier     | dc_identifier                  | dc:identifier        | dc.identifier         |
| contributor    | dc_contributor                 | dc:contributor       | dc.contributor        |
| publisher      | dc_publisher                   | dc:publisher         | dc.publisher          |

**Remember**: The script now blocks both colons and periods, so you can only use the underscore format!

---

## Questions?

- See [RENAME_METADATA_FIELD.md](RENAME_METADATA_FIELD.md) for complete documentation
- Check [SESSION_SUMMARY_2026-06-09.md](SESSION_SUMMARY_2026-06-09.md) for today's changes
- All scripts create automatic hidden backups before modifying files
- Use `bash cleanup_old_backups.sh <collectionbuilder_dir>` to remove old non-hidden backup files
- Hidden backup files (dotted) won't cause CollectionBuilder conflicts
