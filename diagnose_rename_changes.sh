#!/bin/bash
# diagnose_rename_changes.sh
# Diagnose what changed when renaming a metadata field

set -e

if [ $# -lt 2 ]; then
    echo "Usage: bash diagnose_rename_changes.sh <collectionbuilder_dir> <old_field> [new_field]"
    echo ""
    echo "Example:"
    echo "  bash diagnose_rename_changes.sh ~/GitHub/GCCB-TDPS-Archive title dc_title"
    echo ""
    echo "This will show you where the field was changed and help identify issues."
    exit 1
fi

CB_DIR="$1"
OLD_FIELD="$2"
NEW_FIELD="${3:-}"

if [ ! -d "$CB_DIR" ]; then
    echo "Error: Directory not found: $CB_DIR"
    exit 1
fi

echo "======================================================================"
echo "Metadata Field Rename Diagnosis"
echo "======================================================================"
echo ""
echo "CollectionBuilder: $CB_DIR"
echo "Old field: $OLD_FIELD"
if [ -n "$NEW_FIELD" ]; then
    echo "New field: $NEW_FIELD"
fi
echo ""

# Check _config.yml for site title
echo "--- Checking _config.yml (site configuration) ---"
if [ -f "$CB_DIR/_config.yml" ]; then
    echo "Site title line:"
    grep -n "^title:" "$CB_DIR/_config.yml" || echo "  No 'title:' found in _config.yml"
    echo ""
    
    if [ -n "$NEW_FIELD" ]; then
        echo "Searching for new field name ($NEW_FIELD) in _config.yml:"
        grep -n "$NEW_FIELD" "$CB_DIR/_config.yml" || echo "  Not found (good - site config shouldn't change)"
    fi
    echo ""
fi

# Check for backup files
echo "--- Checking for backup files ---"
BACKUPS=$(find "$CB_DIR" -name ".*.backup_*" -type f 2>/dev/null | wc -l | xargs)
echo "Found $BACKUPS hidden backup file(s)"
if [ "$BACKUPS" -gt 0 ]; then
    echo "Most recent backups:"
    find "$CB_DIR" -name ".*.backup_*" -type f -print0 2>/dev/null | xargs -0 ls -lt | head -5 | awk '{print "  " $9}'
fi
echo ""

# Check metadata config files
echo "--- Checking metadata config files (_data/) ---"
if [ -d "$CB_DIR/_data" ]; then
    if [ -n "$NEW_FIELD" ]; then
        echo "Files containing new field ($NEW_FIELD):"
        grep -l "$NEW_FIELD" "$CB_DIR/_data"/*.yml 2>/dev/null || echo "  None found"
    else
        echo "Files containing old field ($OLD_FIELD):"
        grep -l "$OLD_FIELD" "$CB_DIR/_data"/*.yml 2>/dev/null || echo "  None found"
    fi
fi
echo ""

# Check Liquid templates
echo "--- Checking Liquid templates ---"
if [ -n "$NEW_FIELD" ]; then
    echo "Liquid references to new field (item.$NEW_FIELD, page.$NEW_FIELD):"
    grep -r "item\.$NEW_FIELD\|page\.$NEW_FIELD" "$CB_DIR/_layouts" "$CB_DIR/_includes" 2>/dev/null | head -10 || echo "  None found"
else
    echo "Liquid references to old field (item.$OLD_FIELD, page.$OLD_FIELD):"
    grep -r "item\.$OLD_FIELD\|page\.$OLD_FIELD" "$CB_DIR/_layouts" "$CB_DIR/_includes" 2>/dev/null | head -10 || echo "  None found"
fi
echo ""

# Check banner specifically
echo "--- Checking collection banner ---"
if [ -f "$CB_DIR/_includes/collection-banner.html" ]; then
    echo "Banner title references:"
    grep -n "title\|Title" "$CB_DIR/_includes/collection-banner.html" | head -10 || echo "  No title references"
else
    echo "  collection-banner.html not found"
fi
echo ""

# Summary
echo "======================================================================"
echo "Summary"
echo "======================================================================"
echo ""
echo "To restore from backups:"
echo "  find '$CB_DIR' -name '.*.backup_*' -type f"
echo ""
echo "To test your site:"
echo "  cd '$CB_DIR' && bundle exec jekyll serve"
echo ""
echo "For detailed troubleshooting, see:"
echo "  FIXING_RENAME_ISSUES.md"
echo ""
