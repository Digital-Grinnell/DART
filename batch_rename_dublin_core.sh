#!/usr/bin/env bash
# batch_rename_dublin_core.sh - Normalize legacy Dublin Core field names
#
# Usage:
#   bash batch_rename_dublin_core.sh path/to/metadata.csv [path/to/collectionbuilder]
#
# This script removes legacy dc_ prefixes from standard metadata fields.
# It runs in preview mode first, then prompts before applying changes.

set -euo pipefail

CSV_FILE="${1:-}"
CB_DIR="${2:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RENAME_SCRIPT="$SCRIPT_DIR/rename_metadata_field.py"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Standard field mappings (legacy_field:canonical_field)
DC_FIELDS=(
    "dc_title:title"
    "dc_description:description"
    "dc_creator:creator"
    "dc_subject:subject"
    "dc_date:date"
    "dc_format:format"
    "dc_rights:rights"
    "dc_source:source"
    "dc_coverage:coverage"
    "dc_language:language"
    "dc_relation:relation"
    "dc_identifier:identifier"
    "dc_contributor:contributor"
    "dc_publisher:publisher"
)

usage() {
    cat << EOF
Usage: bash batch_rename_dublin_core.sh CSV_FILE [COLLECTIONBUILDER_DIR]

Remove legacy dc_ prefixes from standard metadata fields in one operation.

Arguments:
    CSV_FILE              Path to CSV metadata file (required)
    COLLECTIONBUILDER_DIR Path to CollectionBuilder repository (optional)

Fields that will be renamed (if they exist):
    dc_title       → title
    dc_description → description
    dc_creator     → creator
    dc_subject     → subject
    dc_date        → date
    dc_format      → format
    dc_rights      → rights
    dc_source      → source
    dc_coverage    → coverage
    dc_language    → language
    dc_relation    → relation
    dc_identifier  → identifier
    dc_contributor → contributor
    dc_publisher   → publisher

Examples:
    # Normalize headers in CSV only
    bash batch_rename_dublin_core.sh metadata.csv
    
    # Normalize CSV and CollectionBuilder configs
    bash batch_rename_dublin_core.sh metadata.csv ../collectionbuilder

EOF
    exit 1
}

# Validate inputs
if [ -z "$CSV_FILE" ]; then
    echo -e "${RED}Error: CSV file path required${NC}"
    usage
fi

if [ ! -f "$CSV_FILE" ]; then
    echo -e "${RED}Error: CSV file not found: $CSV_FILE${NC}"
    exit 1
fi

if [ ! -f "$RENAME_SCRIPT" ]; then
    echo -e "${RED}Error: rename_metadata_field.py not found: $RENAME_SCRIPT${NC}"
    exit 1
fi

echo "======================================================================"
echo "Batch Legacy Field Normalizer"
echo "======================================================================"
echo
echo -e "CSV File: ${BLUE}$CSV_FILE${NC}"
if [ -n "$CB_DIR" ]; then
    echo -e "CollectionBuilder: ${BLUE}$CB_DIR${NC}"
else
    echo -e "CollectionBuilder: ${YELLOW}Not specified (CSV only)${NC}"
fi
echo

# Read CSV headers to see which fields exist
echo "Reading CSV headers..."
HEADERS=$(head -1 "$CSV_FILE")
echo -e "Found headers: ${BLUE}$HEADERS${NC}"
echo

# Determine which fields need renaming
FIELDS_TO_RENAME=()
for mapping in "${DC_FIELDS[@]}"; do
    OLD_FIELD="${mapping%%:*}"
    NEW_FIELD="${mapping#*:}"
    
    # Check if old field exists and new field doesn't
    if echo "$HEADERS" | grep -q "\b$OLD_FIELD\b" && ! echo "$HEADERS" | grep -q "\b$NEW_FIELD\b"; then
        FIELDS_TO_RENAME+=("$mapping")
    fi
done

if [ ${#FIELDS_TO_RENAME[@]} -eq 0 ]; then
    echo -e "${YELLOW}⚠️  No fields need renaming.${NC}"
    echo "Possible reasons:"
    echo "  • Fields already use standard CollectionBuilder CSV names"
    echo "  • CSV doesn't contain standard metadata fields"
    echo
    exit 0
fi

echo -e "${GREEN}Found ${#FIELDS_TO_RENAME[@]} field(s) to rename:${NC}"
for mapping in "${FIELDS_TO_RENAME[@]}"; do
    OLD_FIELD="${mapping%%:*}"
    NEW_FIELD="${mapping#*:}"
    echo "  • $OLD_FIELD → $NEW_FIELD"
done
echo

# Preview mode
echo "======================================================================"
echo "PREVIEW MODE - Checking what would change"
echo "======================================================================"
echo

for mapping in "${FIELDS_TO_RENAME[@]}"; do
    OLD_FIELD="${mapping%%:*}"
    NEW_FIELD="${mapping#*:}"
    
    echo -e "${BLUE}--- Previewing: $OLD_FIELD → $NEW_FIELD ---${NC}"
    
    if [ -n "$CB_DIR" ]; then
        python3 "$RENAME_SCRIPT" --csv "$CSV_FILE" --old-field "$OLD_FIELD" --new-field "$NEW_FIELD" --cb-dir "$CB_DIR" 2>&1 | grep -v "^===" || true
    else
        python3 "$RENAME_SCRIPT" --csv "$CSV_FILE" --old-field "$OLD_FIELD" --new-field "$NEW_FIELD" 2>&1 | grep -v "^===" || true
    fi
    echo
done

echo "======================================================================"
echo "PREVIEW COMPLETE"
echo "======================================================================"
echo

# Prompt to continue
read -p "Apply these changes? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Cancelled by user${NC}"
    exit 0
fi

echo
echo "======================================================================"
echo "APPLYING CHANGES"
echo "======================================================================"
echo

SUCCESS_COUNT=0
FAIL_COUNT=0

for mapping in "${FIELDS_TO_RENAME[@]}"; do
    OLD_FIELD="${mapping%%:*}"
    NEW_FIELD="${mapping#*:}"
    
    echo -e "${BLUE}--- Applying: $OLD_FIELD → $NEW_FIELD ---${NC}"
    
    if [ -n "$CB_DIR" ]; then
        if python3 "$RENAME_SCRIPT" --csv "$CSV_FILE" --old-field "$OLD_FIELD" --new-field "$NEW_FIELD" --cb-dir "$CB_DIR" --apply; then
            ((SUCCESS_COUNT++))
            echo -e "${GREEN}✓ Success${NC}"
        else
            ((FAIL_COUNT++))
            echo -e "${RED}✗ Failed${NC}"
        fi
    else
        if python3 "$RENAME_SCRIPT" --csv "$CSV_FILE" --old-field "$OLD_FIELD" --new-field "$NEW_FIELD" --apply; then
            ((SUCCESS_COUNT++))
            echo -e "${GREEN}✓ Success${NC}"
        else
            ((FAIL_COUNT++))
            echo -e "${RED}✗ Failed${NC}"
        fi
    fi
    echo
done

echo "======================================================================"
echo "BATCH OPERATION COMPLETE"
echo "======================================================================"
echo
echo -e "${GREEN}Successful renames: $SUCCESS_COUNT${NC}"
if [ $FAIL_COUNT -gt 0 ]; then
    echo -e "${RED}Failed renames: $FAIL_COUNT${NC}"
fi
echo
echo "📋 Backup files created with .backup_TIMESTAMP suffix"
echo
echo "Next steps:"
if [ -n "$CB_DIR" ]; then
    echo "  1. Test your CollectionBuilder site: cd $CB_DIR && bundle exec jekyll serve"
    echo "  2. Verify metadata displays correctly"
    echo "  3. If issues occur, restore from backup files"
else
    echo "  1. Update your CollectionBuilder configuration to use new field names"
    echo "  2. Test the site thoroughly"
fi
echo
