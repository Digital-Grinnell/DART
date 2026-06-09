#!/bin/bash
# cleanup_old_backups.sh
# Remove old non-hidden backup files from a CollectionBuilder repository
# Use this to clean up backup files created before the hidden backup feature was added

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

if [ $# -eq 0 ]; then
    echo -e "${RED}Error: CollectionBuilder directory path required${NC}"
    echo ""
    echo "Usage: bash cleanup_old_backups.sh <collectionbuilder_directory>"
    echo ""
    echo "Example:"
    echo "  bash cleanup_old_backups.sh ~/GitHub/GCCB-TDPS-Archive"
    exit 1
fi

CB_DIR="$1"

if [ ! -d "$CB_DIR" ]; then
    echo -e "${RED}Error: Directory not found: $CB_DIR${NC}"
    exit 1
fi

echo -e "${BLUE}=====================================================================${NC}"
echo -e "${BLUE}CollectionBuilder Backup Cleanup${NC}"
echo -e "${BLUE}=====================================================================${NC}"
echo ""
echo -e "CollectionBuilder directory: ${GREEN}$CB_DIR${NC}"
echo ""

# Find all non-hidden backup files (files with .backup_ in the name that don't start with .)
echo -e "${YELLOW}Searching for old backup files...${NC}"
echo ""

BACKUP_FILES=$(find "$CB_DIR" -type f -name "*.backup_*" ! -name ".*" 2>/dev/null || true)

if [ -z "$BACKUP_FILES" ]; then
    echo -e "${GREEN}✓ No old backup files found${NC}"
    echo ""
    echo "Your repository is clean! All backup files are either:"
    echo "  • Hidden (dotted) - these are good and won't cause conflicts"
    echo "  • Already removed"
    exit 0
fi

# Count files
FILE_COUNT=$(echo "$BACKUP_FILES" | wc -l | xargs)

echo -e "${YELLOW}Found $FILE_COUNT old backup file(s):${NC}"
echo ""
echo "$BACKUP_FILES" | while read file; do
    rel_path="${file#$CB_DIR/}"
    echo "  • $rel_path"
done
echo ""

# Calculate total size
TOTAL_SIZE=$(echo "$BACKUP_FILES" | xargs du -ch 2>/dev/null | tail -1 | cut -f1)
echo -e "${YELLOW}Total size: $TOTAL_SIZE${NC}"
echo ""

# Confirm deletion
echo -e "${RED}WARNING: This will permanently delete these backup files.${NC}"
echo "Make sure you don't need to restore from any of these backups!"
echo ""
read -p "Delete all old backup files? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo ""
    echo -e "${BLUE}Cancelled. No files were deleted.${NC}"
    exit 0
fi

# Delete files
echo ""
echo -e "${YELLOW}Deleting backup files...${NC}"
echo ""

DELETED=0
echo "$BACKUP_FILES" | while read file; do
    if [ -f "$file" ]; then
        rm "$file"
        rel_path="${file#$CB_DIR/}"
        echo -e "  ${GREEN}✓${NC} Deleted: $rel_path"
        DELETED=$((DELETED + 1))
    fi
done

echo ""
echo -e "${GREEN}=====================================================================${NC}"
echo -e "${GREEN}Cleanup Complete!${NC}"
echo -e "${GREEN}=====================================================================${NC}"
echo ""
echo "Deleted $FILE_COUNT old backup file(s)"
echo ""
echo -e "${BLUE}Note:${NC} Hidden backup files (starting with .) were preserved."
echo "These are the new format and won't cause CollectionBuilder conflicts."
echo ""
echo "To see hidden backup files, use: ${GREEN}ls -la${NC} in any directory"
