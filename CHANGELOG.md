# DART Changelog

All notable changes to the DART (Digital Asset Routing and Transformation) project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] - 2026-05-12

### Summary
Version 1.2.0 represents a major architectural upgrade focused on adopting Digital Grinnell standards and enhancing data persistence:

**Key Highlights:**
- Integrated with `common-DG-utilities` shared library for ecosystem consistency
- Replaced custom filename-based IDs with standard `dg_<epoch>` format
- Implemented permanent file-to-ID mappings (IDs never change once assigned)
- Added persistent file selection across app restarts
- Enhanced with full file path tracking to prevent collisions
- Implemented true compound object system with parentid tracking

### Added
- **Common DG Utilities Integration**: Imported shared utilities from `../common-DG-utilities`
  - Added `common_dg_utilities` package to dependencies
  - Enables code reuse across Digital Grinnell applications
- **Standard DG Identifier System**: Function 1 now uses standard `dg_<epoch>` format
  - All identifiers follow Digital Grinnell standard: `dg_<epoch_time>`
  - Epoch-based generation ensures global uniqueness
  - Automatic collision detection and handling (increments if duplicate found)
  - Consistent with other Digital Grinnell applications
- **Persistent ID Assignment**: File-to-ID mappings stored in settings
  - Once a file receives an ID, it NEVER changes
  - Mappings use **full file paths** as keys to prevent collisions
  - Stored per working folder in `file_to_id_map`
  - Running Function 1 again reuses existing IDs for known file paths
  - Only generates new IDs for files not previously seen
  - Shows statistics: "X new, Y reused" in results
- **Persistent File Selection**: Selected files remembered across app restarts
  - File picker selections stored in persistent.json
  - On app restart, previously selected files are restored and displayed
  - No need to re-select files each time you open the app
  - Supports both single and multiple file selections
- **Function 0 Enhancement**: New `use_working_folder_for_file_selection` boolean setting
  - Controls initial directory for file picker dialog
  - When `true`: Opens file picker in working/outputs folder
  - When `false`: Opens file picker in inputs folder (overrides Flet default behavior)
  - Default value: `false`
- **Multiple File Selection**: File picker now supports selecting multiple files simultaneously
  - Smart display: Shows single file path or count with first 3 filenames
  - Storage: Maintains both `last_file` (single) and `last_files` (comma-separated) for compatibility
  - Helper function: `get_selected_files()` returns list of all selected files as Path objects
- **Compound Object Implementation**: Function 1 now creates true compound objects with parentid tracking
  - Compound objects have their own `dg_<epoch>` identifiers
  - Compound objects are associated with the **folder path** containing their children
  - Compound IDs stored using key format: `{folder_path}::COMPOUND::{text_base}`
  - Compound IDs persist across runs - same folder + text base = same ID
  - Child objects track their parent via `parentid` field (not vice-versa)
  - Text-based filename grouping (numbers ignored - used for sequencing)
  - Groups require 2+ files to form a compound
  - Files that don't match any group become standalone objects (`parentid = None`)
  - Enhanced display: Shows compounds with folder path and children indented, standalone objects separately
- **Debug Logging for Function 1**: Comprehensive debug output tracking inputs, processing, and outputs
  - Logs input sources, identifier generation, and validation
  - All debug messages prefixed with `[DEBUG]` for easy identification
- **Function 1 Enhancement**: Now processes selected files from Files Selection
  - If files are selected, analyzes only those files (ignores Inputs Folder)
  - Falls back to scanning Inputs Folder if no files are selected
  - Allows precise control over which files to analyze
- **Function 1 Uniqueness Validation**: Automatic detection and reporting of duplicate identifiers
  - Validates all generated identifiers are unique
  - Shows detailed error dialog if duplicates detected (extremely rare with epoch-based IDs)

### Changed
- **Log File Location**: Moved from `~/DART-data/logfiles/` to `./logfiles/` (project directory)
  - Easier access for debugging and testing
  - Keeps logs with the project for better organization
  - Already excluded in `.gitignore`
- **Folder Naming Consistency**: Updated all references to use plural forms
  - "Input Folder" → "Inputs Folder"
  - "Output Folder" → "Outputs Folder"
  - "Working/Output Folder" → "Working/Outputs Folder"
  - Applied to UI labels, dialog titles, status messages, and error messages
- **File Selection Terminology**: Updated to plural forms
  - "File Selection" → "Files Selection"
  - "Select File" → "Select Files"
  - Dialog title: "Select File" → "Select Files"
- **File Picker Behavior**: Enhanced with smart directory selection
  - Respects `use_working_folder_for_file_selection` setting
  - Falls back to inputs folder when setting is false and inputs folder is available
  - Improved user workflow by reducing navigation steps

### Removed
- **Filename-Based Object ID System**: Replaced with standard DG identifiers
  - Previous system derived IDs from filenames (e.g., "wit-001" from "Wit 001.JPG")
  - New system uses epoch-based identifiers (e.g., "dg_1736712345")
  - Eliminates complexity from filename parsing and pattern matching
  - Note: Compound object grouping feature retained for future use with modifications

### Documentation
- Updated FUNCTION_1_ANALYZE_ASSETS.md for standard DG identifiers
  - Documented new `dg_<epoch>` format and benefits
  - Removed filename-based object ID generation rules
  - Simplified examples to show epoch-based ID assignment
  - Compound grouping documentation will be updated when modifications are implemented
- Updated FUNCTION_0_APP_SETTINGS.md with new `use_working_folder_for_file_selection` setting
- Revised all function documentation to use plural folder naming (Inputs/Outputs)
- Updated FUNCTION_2_COUNT_FILES.md with plural terminology
- Enhanced notes section explaining file picker behavior based on settings
- Updated README.md with new log file location (`./logfiles/`)
- Updated QUICKSTART.md to reflect current function list and dependencies

### Technical Details
**Standard DG Identifier Implementation:**
- Imported `generate_unique_id()` from `common_dg_utilities.dg_utils`
- IDs generated as `dg_<epoch_time>` where epoch is Unix timestamp (seconds since 1970)
- Uniqueness enforced via `page.session.generated_ids` set
- Automatic collision handling increments epoch if duplicate detected (rare)

**Persistent ID Mapping:**
- Mappings stored in `dart_settings.json` per working folder
- Dictionary structure: `{"/full/path/to/file.jpg": "dg_1736712345"}`
- Full file paths used as keys to prevent collisions
- Loaded at start of Function 1, saved after new IDs generated
- Object data structure enhanced: `{objectid, filepath, filename}`

**Persistent File Selection:**
- Added `last_files` field to persistent.json `ui_state`
- Comma-separated list of full file paths
- Restored on app startup with smart display logic
- Helper function `get_initial_file_display()` formats display text
- Maintains backward compatibility with single-file `last_file` field

**Compound Object Implementation:**
- **Folder-Based Association**: Compounds are associated with the folder path containing their children
  - More logical than file-based tracking (compound has no single file)
  - Folder path provides stable, persistent reference point
  - Same folder + text base = same compound ID across runs
- **Intelligent Pattern Analysis**: Two-pass grouping algorithm finds what filenames have in common
  - **Pass 1**: Extract prefixes from numbered files: `re.match(r'^(.+?)[\s_\-]*(\d+)$', stem)`
    - Handles leading numbers: "100 Nights-1" → prefix "100 nights", seq 1
  - **Pass 2**: Match unnumbered files against known prefixes
    - Checks if unnumbered filename starts with any numbered prefix
    - Uses longest matching prefix (most specific)
    - Validates separator after prefix (space, underscore, hyphen)
    - "Wit Poster" starts with "wit" → matched
    - "AnnaChristie-F14-Program" starts with "annachristie-f14" → matched
  - Weighted matching: requires 3+ character prefix for grouping
  - Case-insensitive comparison
  - No hardcoded suffix list - adapts to actual file patterns
- **Sequence Detection**: Analyzes numbered files for sequential patterns
  - Calculates average gap and maximum gap between sorted numbers
  - Sequential if: avg gap ≤ 2.0 and max gap ≤ 5 (tolerates missing numbers)
  - **Zero-Padding**: Automatically calculates padding width from max number
  - Reports sequence details: range, gaps, missing values, padding recommendation
- **Detailed Reporting**: Comprehensive analysis logged for each group
  - File counts (numbered vs unnumbered)
  - Sequence analysis with statistics
  - Zero-padding recommendations
  - Grouping decisions with rationale
  - Examples: "wit 001.jpg", "wit poster.jpg" → both grouped under prefix "wit"
  - Examples: "100 nights-1.jpg", "100 nights-20.jpg" → grouped under "100 nights"
- **Smart Display**: Children displayed in proper sequence order
  - Numbered files sorted by sequence, then unnumbered alphabetically
  - Sequence numbers shown with zero-padding: `[01]`, `[02]`, `[10]`
  - Visual confirmation of proper grouping and ordering
- Compound objects created for groups with 2+ files
- Folder path extracted from first child: `Path(filepath).parent`
- Compound key format: `{folder_path}::COMPOUND::{text_base}` for ID mapping
- Checks for existing compound IDs before generating new ones
- Each compound gets unique `dg_<epoch>` ID via `generate_unique_id(page)`
- Object types: `"compound"` (has folder_path), `"child"` (has file + parentid), `"single"` (no parent)
- Object structure: `{objectid, parentid, type, filepath, filename}` for children
- Compound structure: `{objectid, type, text_base, child_count, folder_path}` for compounds
- Display organizes by compound with folder path shown and children indented

**Dependencies:**
- Added `common-DG-utilities` as editable package: `-e ../common-DG-utilities`
- Requires sibling directory structure: `GitHub/common-DG-utilities/` and `GitHub/DART/`

---

## [1.1.0] - 2026-05-11

### Added
- **Function 0 Enhancements**: Added two new settings fields
  - `group_compound_objects`: Boolean to enable grouping of similar filenames as compound objects
  - `csv_structure_file`: Path to CSV file defining expected column structure for exports
- **Function 1 Redesign**: Completely redesigned as "Analyze Digital Assets & Generate Object IDs"
  - Scans folders for digital asset files (images, PDFs, video, audio, archives)
  - Generates 3-5 character object IDs from filenames
  - Extracts and appends numeric portions for unique identifiers
  - Optional compound object grouping based on similar filenames
  - Supports 20+ file format extensions across multiple media types

### Changed
- Updated Function 1 icon from 📁 to 🎯 (dart target) to reflect asset analysis focus
- Function 1 now respects `group_compound_objects` setting from Function 0
- Enhanced result display with grouped compound objects when enabled
- Updated all user-facing text to use "folder" instead of "directory"

### Documentation
- Completely rewrote FUNCTION_1_ANALYZE_ASSETS.md with comprehensive usage guide
- Updated FUNCTION_0_APP_SETTINGS.md with new settings descriptions
- Added examples for object ID generation and compound object grouping

---

## [1.0.0] - 2026-05-04

### Initial Release

DART (Digital Asset Routing and Transformation) is a production-ready desktop application built with Flet. It was created by extracting and generalizing the proven UI framework from OHM (Oral History Manager), resulting in a clean, robust platform that maintains all of OHM's battle-tested features while providing flexibility for digital asset management workflows.

### Features

#### UI Architecture (Based on OHM)
- **Professional Layout** with proven vertical spacing and organization
- **Dart Target Icon** (🎯) in header using Flet Icons
- **Collapsible Directories Section** to maximize screen space once directories are set
- **File Selection Section** always visible for quick file changes between operations
- **Status Output** with copy-to-clipboard button
- **Log Output** with timestamped entries, copy and clear buttons
- **Function Dropdown** with emoji icons and workflow ordering
- **Help Mode** checkbox to view documentation instead of executing functions

#### Core Systems
- **Persistent Settings**
  - Automatic save/restore of window position
  - Directory and file selections persisted across sessions
  - Function usage tracking with timestamps and counts
  - Stored in `~/DART-data/persistent.json`

- **Logging System**
  - Timestamped log files in `~/DART-data/logfiles/`
  - Real-time log display in UI with prepended entries
  - Separate file and console handlers
  - Configurable log levels
  - Reduced verbosity for Flet internal logging

- **Function Management**
  - Dictionary-based function registry
  - Icon support with emoji indicators
  - Help file association per function
  - Usage tracking and statistics
  - Automatic dropdown population

#### Example Functions
- **Function 0** ⚙️: App Settings with encrypted credentials
- **Function 1** 🎯: Analyze digital assets and generate object IDs
- **Function 2** 📊: Count files by extension type with statistics
- **Function 3** 💻: Display system information
- Each includes professional help documentation in markdown

#### Development & Distribution
- **Runtime Scripts**
  - `run.sh`: macOS/Linux launcher with automatic venv management
  - `run.bat`: Windows launcher with automatic venv management
  
- **Distribution Tools**
  - `build_dmg.sh`: Create macOS DMG installers
  - `build_windows_zip.sh`: Create Windows ZIP packages
  
- **Documentation**
  - Comprehensive README with customization guide
  - QUICKSTART.md for rapid onboarding
  - Individual function help files in markdown
  - CHANGELOG following Keep a Changelog format

- **Quality**
  - `.gitignore` with sensible Python/Flet exclusions
  - MIT License
  - Clean 715-line codebase (down from OHM's 3160 lines)
  - Well-commented code with docstrings

### Technical Details
- **Python 3.8+** required
- **Flet 0.25.2** with flet-desktop
- No additional dependencies for base template
- Cross-platform: macOS, Windows, Linux

### Credits
DART's UI architecture is based on the patterns developed for OHM (Oral History Manager) by Mark McFate for Digital.Grinnell. The application represents the distillation of real-world application development experience into a robust platform for digital asset management.

---

## Future Plans

Planned improvements for future releases:
- Additional example functions demonstrating common patterns
- Theme customization support
- Window state management (maximized, minimized)
- Multi-language support framework
- Plugin/extension system
- Additional UI components (progress bars, tabs, etc.)

---

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for:
- Bug fixes
- Documentation improvements  
- Additional example functions
- UI enhancements
- Code optimization

## Repository

https://github.com/Digital-Grinnell/DART

### Documentation

- Comprehensive README with:
  - Quick start guide
  - Customization instructions
  - How to add new functions
  - How to modify UI layout
  - Building standalone packages
  - Flet resources and tips

- Function-specific help documentation:
  - `FUNCTION_1_ANALYZE_ASSETS.md`
  - `FUNCTION_2_COUNT_FILES.md`
  - `FUNCTION_3_SYSTEM_INFO.md`

### Technical Details

- Built with Flet 0.25.2
- Python 3.8+ required
- No external dependencies beyond Flet
- Cross-platform: macOS, Windows, Linux

---

## Future Development

DART provides a robust platform for digital asset management. When you customize or extend DART:

1. Update the changelog with your version history
2. Customize functions for your specific workflows
3. Adjust the UI to match your requirements
4. Add any additional dependencies needed

---

## Credits

DART was derived from the OHM (Oral History Manager) project, which demonstrated effective patterns for Flet desktop applications including persistent settings, logging, function management, and help documentation.

Built with [Flet](https://flet.dev) - a Python framework for building desktop applications.
