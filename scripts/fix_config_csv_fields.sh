#!/usr/bin/env python3
"""
Fix CSV config files to remove legacy dc_ prefixes from standard fields.
This updates config-browse.csv, config-metadata.csv, etc.
"""

import csv
import sys
from pathlib import Path
from datetime import datetime

# Field mappings (legacy_name -> standard_name)
FIELD_MAP = {
    'dc_title': 'title',
    'dc_description': 'description',
    'dc_creator': 'creator',
    'dc_subject': 'subject',
    'dc_date': 'date',
    'dc_format': 'format',
    'dc_rights': 'rights',
    'dc_source': 'source',
    'dc_coverage': 'coverage',
    'dc_language': 'language',
    'dc_relation': 'relation',
    'dc_identifier': 'identifier',
    'dc_contributor': 'contributor',
    'dc_publisher': 'publisher',
}

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/fix_config_csv_fields.sh <collectionbuilder_dir>")
        print("")
        print("Example:")
        print("  python3 scripts/fix_config_csv_fields.sh ~/GitHub/GCCB-TDPS-Archive")
        sys.exit(1)
    
    cb_dir = Path(sys.argv[1]).expanduser()
    data_dir = cb_dir / '_data'
    
    if not data_dir.exists():
        print(f"Error: CollectionBuilder _data directory not found: {data_dir}")
        sys.exit(1)
    
    print("=" * 70)
    print("Fix CSV Config Fields - Remove dc_ Prefixes")
    print("=" * 70)
    print()
    print(f"CollectionBuilder: {cb_dir}")
    print()
    
    # Find all config CSV files
    config_csv_files = list(data_dir.glob('config-*.csv'))
    config_csv_files = [f for f in config_csv_files if not f.name.startswith('.') and 'backup' not in f.name]
    
    if not config_csv_files:
        print(f"No config CSV files found in {data_dir}")
        return
    
    print("Found config CSV files:")
    for f in config_csv_files:
        print(f"  - {f.name}")
    print()
    
    total_files_updated = 0
    total_fields_renamed = 0
    
    for csv_file in config_csv_files:
        print(f"Processing: {csv_file.name}")
        
        try:
            # Read the CSV
            with open(csv_file, 'r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)
                rows = list(reader)
            
            if not rows:
                print("  ⚠️  Skipped (empty file)")
                print()
                continue
            
            # Check if file has a 'field' column
            headers = rows[0]
            if 'field' not in headers:
                print("  ⚠️  Skipped (no 'field' column)")
                print()
                continue
            
            field_col_idx = headers.index('field')
            
            # Count and update fields
            changes = 0
            for i in range(1, len(rows)):  # Skip header
                old_field = rows[i][field_col_idx]
                if old_field in FIELD_MAP:
                    rows[i][field_col_idx] = FIELD_MAP[old_field]
                    changes += 1
            
            if changes == 0:
                print("  ℹ️  No changes needed")
                print()
                continue
            
            # Create backup
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = csv_file.parent / f"{csv_file.stem}.backup_{timestamp}{csv_file.suffix}"
            with open(csv_file, 'r', encoding='utf-8') as src, open(backup_file, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
            print(f"  📋 Backup: {backup_file.name}")
            
            # Write updated CSV
            with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            
            print(f"  ✅ Updated: {changes} field(s) renamed")
            print()
            
            total_files_updated += 1
            total_fields_renamed += changes
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            print()
    
    print("=" * 70)
    print("Update Complete!")
    print("=" * 70)
    print()
    print(f"Files updated: {total_files_updated}")
    print(f"Fields renamed: {total_fields_renamed}")
    print()
    print("Next steps:")
    print(f"  1. Test your site: cd {cb_dir} && bundle exec jekyll serve")
    print("  2. Verify browse page shows titles and dates")
    print("  3. If issues occur, restore from backup files")
    print()

if __name__ == '__main__':
    main()

