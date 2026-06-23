#!/usr/bin/env python3
"""
Rename Metadata Field Script
Coordinates field name changes between CSV metadata files and CollectionBuilder configuration.

Usage:
    python rename_metadata_field.py --csv path/to/metadata.csv --old-field dc_title --new-field title
    python3 scripts/rename_metadata_field.py --csv path/to/metadata.csv --old-field dc_title --new-field title
    python3 scripts/rename_metadata_field.py --csv path/to/metadata.csv --old-field dc_title --new-field title --cb-dir path/to/collectionbuilder --apply
    print("Usage: python3 scripts/rename_metadata_field.py --csv path/to/metadata.csv --old-field dc_title --new-field title")
    print("  python3 scripts/rename_metadata_field.py --csv metadata.csv --old-field title --new-field dc:title")
    print("  python3 scripts/rename_metadata_field.py --csv metadata.csv --old-field title --new-field dc:title --apply")
    print("  python3 scripts/rename_metadata_field.py --csv metadata.csv --old-field title --new-field dc:title --cb-dir ../collectionbuilder --apply")

Options:
    --csv               Path to the CSV metadata file
    --old-field         Current field name to rename
    --new-field         New field name (use underscores, not colons)
    --cb-dir            Path to CollectionBuilder repository (optional)
    --dry-run           Preview changes without applying (default)
    --apply             Apply changes (creates backups)
    --no-backup         Skip backup creation (not recommended)

Note:
    Use plain CollectionBuilder CSV field names (e.g., title) when syncing with
    Digital-Grinnell/collectionbuilder-csv and upstream CollectionBuilder CSV.
    Colons and periods still cause syntax issues in YAML and Liquid templates.
"""

import csv
import argparse
import os
import shutil
import re
from pathlib import Path
from datetime import datetime
import sys


class MetadataFieldRenamer:
    """Handles renaming of metadata fields across CSV and CollectionBuilder files."""
    
    def __init__(self, csv_path, old_field, new_field, cb_dir=None, dry_run=True, create_backup=True):
        self.csv_path = Path(csv_path)
        self.old_field = old_field
        self.new_field = new_field
        self.cb_dir = Path(cb_dir) if cb_dir else None
        self.dry_run = dry_run
        self.create_backup = create_backup
        self.changes = []
        
    def validate_inputs(self):
        """Validate that required files and directories exist."""
        if self.new_field.startswith('dc_'):
            suggested_name = self.new_field[3:] or 'title'
            raise ValueError(
                f"Field name '{self.new_field}' uses the retired 'dc_' prefix.\n"
                f"  Suggestion: Use the plain field name instead. For example: '{suggested_name}'\n"
                f"  Why: DART now stays in sync with Digital-Grinnell/collectionbuilder-csv\n"
                f"  and upstream CollectionBuilder CSV by using unprefixed field names."
            )

        # Validate field names - check for colons
        if ':' in self.new_field:
            suggested_name = self.new_field.split(':')[-1].replace(':', '_') or 'title'
            raise ValueError(
                f"Field name '{self.new_field}' contains a colon (:) which causes issues in YAML and Liquid templates.\n"
                f"  Suggestion: Use a plain field name instead. For example: '{suggested_name}'\n"
                f"  Why: Colons require special quoting in YAML and can break Liquid template parsing.\n"
                f"  See FIX_COLON_TO_UNDERSCORE.md for more information."
            )
        
        # Check for periods - conflicts with Liquid object notation
        if '.' in self.new_field:
            suggested_name = self.new_field.split('.')[-1].replace('.', '_') or 'title'
            raise ValueError(
                f"Field name '{self.new_field}' contains a period (.) which conflicts with Liquid template syntax.\n"
                f"  Suggestion: Use a plain field name instead. For example: '{suggested_name}'\n"
                f"  Why: Liquid uses dots for object properties (e.g., item.title, page.title).\n"
                f"  A field named 'dc.title' would create ambiguity with Liquid's object notation."
            )
        
        # Check for other problematic characters
        problematic_chars = ['/', '\\', '[', ']', '{', '}', '<', '>', '|', '?', '*', '"', "'"]
        for char in problematic_chars:
            if char in self.new_field:
                raise ValueError(
                    f"Field name '{self.new_field}' contains invalid character '{char}'.\n"
                    f"  Field names should contain only letters, numbers, underscores, and hyphens.\n"
                    f"  Suggestion: Use '{self.new_field.replace(char, '_')}'"
                )
        
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")
        
        if not self.csv_path.suffix.lower() == '.csv':
            raise ValueError(f"File is not a CSV: {self.csv_path}")
        
        if self.cb_dir and not self.cb_dir.exists():
            raise FileNotFoundError(f"CollectionBuilder directory not found: {self.cb_dir}")
        
        # Check if old field exists in CSV
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
            if self.old_field not in headers:
                raise ValueError(f"Field '{self.old_field}' not found in CSV headers: {headers}")
            if self.new_field in headers:
                raise ValueError(f"Field '{self.new_field}' already exists in CSV headers")
    
    def backup_file(self, file_path):
        """Create a timestamped hidden backup of a file (dotted filename)."""
        if not self.create_backup:
            return None
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Create hidden backup file (dotted) to prevent CollectionBuilder from processing it
        backup_path = file_path.parent / f".{file_path.stem}.backup_{timestamp}{file_path.suffix}"
        shutil.copy2(file_path, backup_path)
        return backup_path
    
    def rename_csv_field(self):
        """Rename field in CSV file header."""
        print(f"\n{'[DRY RUN] ' if self.dry_run else ''}Processing CSV: {self.csv_path}")
        
        # Read the CSV
        with open(self.csv_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        if not rows:
            print("  ⚠️  CSV file is empty")
            return
        
        # Update header
        headers = rows[0]
        try:
            field_index = headers.index(self.old_field)
            old_header = headers[:]
            headers[field_index] = self.new_field
            
            change_info = {
                'file': str(self.csv_path),
                'type': 'csv_header',
                'old': self.old_field,
                'new': self.new_field,
                'position': field_index
            }
            self.changes.append(change_info)
            
            print(f"  ✓ Found field '{self.old_field}' at column {field_index}")
            print(f"    Will rename to: '{self.new_field}'")
            print(f"    Affects {len(rows)-1} data rows")
            
            if not self.dry_run:
                # Backup original
                if self.create_backup:
                    backup_path = self.backup_file(self.csv_path)
                    print(f"    📋 Backup created: {backup_path.name}")
                
                # Write updated CSV
                rows[0] = headers
                with open(self.csv_path, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
                print(f"    ✅ CSV updated successfully")
        
        except ValueError:
            print(f"  ⚠️  Field '{self.old_field}' not found in CSV")
    
    def find_cb_config_files(self):
        """Find CollectionBuilder configuration files (excluding backup files)."""
        if not self.cb_dir:
            return []
        
        config_files = []
        
        # Common CollectionBuilder config locations
        patterns = [
            '_config.yml',
            '_data/config-*.yml',
            '_data/config-*.csv',  # CSV-based config files
            '_data/theme.yml',
            'pages/*.md',
            '_layouts/*.html',
            '_includes/*.html'
        ]
        
        for pattern in patterns:
            for file_path in self.cb_dir.glob(pattern):
                # Skip backup files (hidden dotted files or files with .backup_ in name)
                if file_path.is_file() and not file_path.name.startswith('.') and '.backup_' not in file_path.name:
                    config_files.append(file_path)
        
        return config_files
    
    def update_cb_config_file(self, file_path):
        """Update field references in a CollectionBuilder configuration file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            matches = []
            
            # Determine file type to apply appropriate patterns
            is_metadata_config = any(x in str(file_path) for x in ['config-browse', 'config-map', 'config-metadata', 'config-nav', 'config-search', 'config-table', 'config-timeline', 'theme.yml'])
            is_main_config = file_path.name == '_config.yml'
            
            # Build patterns based on file type
            patterns = []
            
            # ONLY match item.field Liquid references (these are definitively metadata fields from CSV)
            patterns.append((rf'item\.{re.escape(self.old_field)}\b', 'liquid_item'))
            patterns.append((rf'site\.data\.\w+\.\w+\.{re.escape(self.old_field)}\b', 'liquid_data'))
            
            # DO NOT match page.field - these are page front matter, not metadata fields
            # page.title, page.description, etc. refer to the individual page's YAML front matter
            # They should NOT be renamed when renaming metadata fields
            
            # For metadata config files (_data/config-*.yml), match YAML keys and quoted strings
            if is_metadata_config:
                patterns.append((rf'(?:^|\n)(\s*){re.escape(self.old_field)}(?=\s*:)', 'yaml_key'))  # YAML keys with indentation
                patterns.append((rf':\s*{re.escape(self.old_field)}(?=\s*(?:\n|$))', 'yaml_value'))  # YAML values
                patterns.append((rf'"{re.escape(self.old_field)}"', 'quoted'))
                patterns.append((rf"'{re.escape(self.old_field)}'", 'quoted_single'))
            
            # Skip _config.yml for direct key matching (site-level config, not metadata)
            # Only process Liquid references in _config.yml
            
            for pattern, match_type in patterns:
                for match in re.finditer(pattern, content, re.MULTILINE):
                    # For yaml_key matches, preserve the indentation
                    if match_type == 'yaml_key' and match.lastindex and match.lastindex >= 1:
                        # Capture group 1 is the indentation
                        indent = match.group(1)
                        matches.append({
                            'type': match_type,
                            'start': match.start() + len(indent),  # Skip indentation
                            'end': match.end(),
                            'text': self.old_field,
                            'indent': indent
                        })
                    else:
                        matches.append({
                            'type': match_type,
                            'start': match.start(),
                            'end': match.end(),
                            'text': match.group()
                        })
            
            if not matches:
                return False, 0
            
            # Replace all matches (work backwards to preserve positions)
            matches.sort(key=lambda x: x['start'], reverse=True)
            for match in matches:
                replacement = match['text'].replace(self.old_field, self.new_field)
                content = content[:match['start']] + replacement + content[match['end']:]
            
            change_info = {
                'file': str(file_path.relative_to(self.cb_dir)),
                'type': 'config_file',
                'matches': len(matches),
                'match_types': list(set(m['type'] for m in matches))
            }
            self.changes.append(change_info)
            
            if not self.dry_run:
                # Backup original
                if self.create_backup:
                    backup_path = self.backup_file(file_path)
                
                # Write updated content
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            return True, len(matches)
            
        except Exception as e:
            print(f"  ⚠️  Error processing {file_path.name}: {e}")
            return False, 0
    
    def update_cb_config_csv_file(self, file_path):
        """Update field references in a CSV configuration file (e.g., config-browse.csv)."""
        try:
            with open(file_path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)
                rows = list(reader)
            
            if not rows or len(rows) < 2:
                return False, 0  # Empty or header-only CSV
            
            headers = rows[0]
            
            # Find the 'field' column (usually the first column in config CSVs)
            try:
                field_col_index = headers.index('field')
            except ValueError:
                # No 'field' column, skip this file
                return False, 0
            
            # Count and update field references
            matches = 0
            for i in range(1, len(rows)):  # Skip header row
                if rows[i][field_col_index] == self.old_field:
                    if not self.dry_run:
                        rows[i][field_col_index] = self.new_field
                    matches += 1
            
            if matches == 0:
                return False, 0
            
            change_info = {
                'file': str(file_path.relative_to(self.cb_dir)),
                'type': 'config_file',
                'matches': matches,
                'match_types': ['csv_field_column']
            }
            self.changes.append(change_info)
            
            if not self.dry_run:
                # Backup original
                if self.create_backup:
                    backup_path = self.backup_file(file_path)
                
                # Write updated CSV
                with open(file_path, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
            
            return True, matches
            
        except Exception as e:
            print(f"  ⚠️  Error processing CSV {file_path.name}: {e}")
            return False, 0
    
    def update_cb_configs(self):
        """Update all CollectionBuilder configuration files."""
        if not self.cb_dir:
            print("\n⚠️  No CollectionBuilder directory specified, skipping config updates")
            return
        
        print(f"\n{'[DRY RUN] ' if self.dry_run else ''}Searching CollectionBuilder configs: {self.cb_dir}")
        
        config_files = self.find_cb_config_files()
        if not config_files:
            print("  ℹ️  No configuration files found")
            return
        
        print(f"  Found {len(config_files)} configuration files to check")
        
        updated_count = 0
        total_replacements = 0
        
        for config_file in config_files:
            # Route to appropriate handler based on file extension
            if config_file.suffix.lower() == '.csv':
                updated, count = self.update_cb_config_csv_file(config_file)
            else:
                updated, count = self.update_cb_config_file(config_file)
            if updated:
                updated_count += 1
                total_replacements += count
                rel_path = config_file.relative_to(self.cb_dir)
                print(f"  ✓ {rel_path}: {count} replacement(s)")
        
        if updated_count > 0:
            print(f"\n  {'Would update' if self.dry_run else 'Updated'} {updated_count} file(s) with {total_replacements} total replacement(s)")
        else:
            print(f"  ℹ️  No references to '{self.old_field}' found in configuration files")
    
    def print_summary(self):
        """Print summary of changes."""
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        
        if self.dry_run:
            print("🔍 DRY RUN MODE - No changes were applied")
            print("   Run with --apply to make actual changes")
        else:
            print("✅ Changes applied successfully")
            if self.create_backup:
                print("📋 Backup files created with .backup_TIMESTAMP suffix")
        
        print(f"\nField rename: '{self.old_field}' → '{self.new_field}'")
        
        csv_changes = [c for c in self.changes if c['type'] == 'csv_header']
        config_changes = [c for c in self.changes if c['type'] == 'config_file']
        
        if csv_changes:
            print(f"\nCSV Updates: {len(csv_changes)}")
            for change in csv_changes:
                print(f"  • {Path(change['file']).name}: column {change['position']}")
        
        if config_changes:
            print(f"\nConfig File Updates: {len(config_changes)}")
            for change in config_changes:
                print(f"  • {change['file']}: {change['matches']} replacement(s)")
        
        if not csv_changes and not config_changes:
            print("\n⚠️  No changes found")
        
        print("="*70 + "\n")
    
    def run(self):
        """Execute the field rename operation."""
        try:
            print("="*70)
            print("Metadata Field Renamer")
            print("="*70)
            
            self.validate_inputs()
            self.rename_csv_field()
            self.update_cb_configs()
            self.print_summary()
            
            return True
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description='Rename metadata fields in CSV and CollectionBuilder configuration',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview changes (dry run)
  python rename_metadata_field.py --csv metadata.csv --old-field title --new-field dc:title
  
  # Apply changes to CSV only
  python rename_metadata_field.py --csv metadata.csv --old-field title --new-field dc:title --apply
  
  # Apply changes to CSV and CollectionBuilder configs
  python rename_metadata_field.py --csv metadata.csv --old-field title --new-field dc:title --cb-dir ../collectionbuilder --apply
        """
    )
    
    parser.add_argument('--csv', required=True, help='Path to CSV metadata file')
    parser.add_argument('--old-field', required=True, help='Current field name to rename')
    parser.add_argument('--new-field', required=True, help='New field name')
    parser.add_argument('--cb-dir', help='Path to CollectionBuilder repository (optional)')
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry-run)')
    parser.add_argument('--no-backup', action='store_true', help='Skip creating backups')
    
    args = parser.parse_args()
    
    renamer = MetadataFieldRenamer(
        csv_path=args.csv,
        old_field=args.old_field,
        new_field=args.new_field,
        cb_dir=args.cb_dir,
        dry_run=not args.apply,
        create_backup=not args.no_backup
    )
    
    success = renamer.run()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
