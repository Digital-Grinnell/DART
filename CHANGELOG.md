# DART Changelog

All notable changes to the DART (Digital Asset Routing and Transformation) project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.4.1] - 2026-05-14

### Summary
Version 1.4.1 improves Function 2 and Function 3 with automatic Azure container management, intelligent derivative skipping, enhanced logging, and improved user experience with clickable log links.

### Added
- **Automatic Container Creation**: Both Function 2 and Function 3
  - Checks if target Azure containers exist before upload operations
  - Automatically creates containers if they don't exist
  - Handles concurrent creation and race conditions gracefully
  - Logs container creation status (created vs. already exists)
  - No manual Azure Portal setup required for new collections
  - **Function 2**: Creates `objs` container automatically
  - **Function 3**: Creates `smalls` and `thumbs` containers automatically
- **Smart Derivative Skipping**: Function 3 optimization
  - Checks Azure for existing derivatives before processing each image
  - Looks for both `_SMALL.jpg` and `_TN.jpg` files
  - Skips generation when both derivatives already exist in Azure
  - Builds URLs from existing files and populates CSV columns
  - Logs skipped files: "⏩ Derivatives already exist in Azure - skipping"
  - Counts skipped files in success totals
  - Safe to re-run Function 3 on same CSV (only generates missing derivatives)
  - Saves processing time and Azure bandwidth on re-runs
- **Clickable Log Link**: Enhanced results dialog
  - "see log for details" is now a clickable link/button
  - Opens complete log file in read-only popup window (800x600px)
  - Shows log filename in popup title
  - Scrollable text field with full log content
  - Supports text selection and copying
  - Error handling if log file can't be accessed
- **Enhanced Logging System**: Comprehensive log file writing
  - `add_log_message()` now writes to both UI and log file
  - Intelligent log level detection based on message content
  - ERROR level: `[ERROR]`, `✗`, "Error:" prefix
  - WARNING level: `[WARN]`, `⚠` prefix
  - INFO level: `[SUCCESS]`, `✓`, `✅`, and default messages
  - DEBUG level: `[DEBUG]` prefix
  - All UI log messages now persisted to log file
  - Complete audit trail of all operations

### Fixed
- **Function 3 Container Path Logic**: Derivative upload bug fix
  - Fixed bug where derivatives uploaded to `objs` instead of `smalls`/`thumbs`
  - Was replacing "objs" in wrong part of path (searched in `base_path` instead of `container`)
  - Now correctly replaces container name: `objs` → `smalls` or `thumbs`
  - Example fix: `objs/TDPS_archive` → `smalls/TDPS_archive` (not `objs/TDPS_archive`)
  - Derivatives now upload to correct parallel folder structure

### Changed
- **Function 3 Results Dialog**: Improved layout
  - Replaced plain text with structured `ft.Column` layout
  - Individual text elements for better formatting
  - Clickable button for log access integrated inline
  - Better spacing and visual hierarchy
  - Maintains 600x400px dialog size

### Documentation
- **FUNCTION_2_EXPORT_CSV.md**: Updated Azure section
  - Added automatic container creation step
  - Renumbered Azure upload process steps
  - Explained no manual setup requirement
- **FUNCTION_3_GENERATE_DERIVATIVES.md**: Major enhancements
  - Added "Automatic Container Creation" subsection
  - Added "Smart Processing Features" section with skip logic
  - Added "Results Dialog" section with clickable log link details
  - Explained re-run safety and incremental updates
  - Documented benefits of skip existing derivatives feature

### Technical Details
- Container creation uses `blob_service_client.get_container_client()` and `create_container()`
- Derivative existence check uses Azure `blob_client.exists()` API
- Log popup uses `ft.TextField` with `read_only=True` and `multiline=True`
- Log level mapping in `add_log_message()` with prefix detection
- Container path parsing splits on first `/` to separate container from path

### Performance Improvements
- Function 3 re-runs are faster (skips existing derivatives)
- No redundant Azure uploads for already-processed images
- Reduced network bandwidth on partial re-runs
- Faster log file access (no need to open file manually)

---

## [1.4.0] - 2026-05-13

### Summary
Version 1.4.0 adds Function 3 for generating web-optimized image derivatives (small and thumbnail) with automatic Azure upload and CSV metadata population. Previous Function 3 (System Info) becomes Function 4.

### Added
- **Function 3: Generate Small & Thumbnail Derivatives** 🖼️
  - Generates small derivatives (800x800px max) for detail pages
  - Generates thumbnail derivatives (400x400px max) for browse views
  - Maintains aspect ratios for all processed images
  - Handles EXIF orientation automatically
  - Converts transparency to white background
  - JPEG optimization with 85% quality
  - Uploads to Azure `/smalls/` and `/thumbs/` folders
  - Populates `image_small` and `image_thumb` CSV columns
  - Creates timestamped CSV with new columns
  - **Kill Switch**: Emergency stop for long-running generation
  - Processes most recent CSV from Function 2
  - Skips non-image files and compound parents
  - Cleans up temporary files automatically
- **Helper Function**: `generate_derivative()`
  - Robust image processing with PIL/Pillow
  - Thumbnail generation with LANCZOS resampling
  - RGBA/transparency conversion to RGB
  - Error handling for FileNotFoundError and PermissionError
  - Returns success/failure tuple with messages
- **Image Support**: Comprehensive format handling
  - JPEG, PNG, GIF, TIFF, BMP, WebP
  - EXIF orientation with ImageOps.exif_transpose()
  - Transparency handling for PNG/GIF
  - Consistent JPEG output for all formats
- **Azure Integration**: Parallel folder structure
  - Derivatives use same container/base path as originals
  - Small images: `/smalls/` folder with `_SMALL` suffix
  - Thumbnails: `/thumbs/` folder with `_TN` suffix
  - Automatic URL generation for both derivatives
  - Naming: `dg_<epoch>_SMALL.jpg`, `dg_<epoch>_TN.jpg`

### Changed
- **Function Numbering**: System Info moved from 3 to 4
  - `on_function_3_system_info()` → `on_function_4_system_info()`
  - Updated functions dictionary with new order
  - Updated active_functions list
  - Renamed FUNCTION_3_SYSTEM_INFO.md → FUNCTION_4_SYSTEM_INFO.md
- **Dependencies**: Added PIL/Pillow
  - `from PIL import Image, ImageOps` in imports
  - `import io` for image processing
  - `Pillow>=10.0.0` in python_requirements.txt

### Documentation
- **FUNCTION_3_GENERATE_DERIVATIVES.md**: Complete new function guide
  - Purpose and workflow explanation
  - Azure folder structure details
  - Image processing specifications
  - Supported formats and handling
  - Error messages and troubleshooting
  - Performance notes and tips
  - CollectionBuilder integration notes
  - Kill switch usage
- **README.md**: Updated workflow functions section
  - Added Function 3 description with derivative details
  - Updated Function 3 from System Info to Derivatives
  - System Info now listed as Function 4

### Technical Details
- Temporary derivatives stored in `temp_derivatives/` folder
- Sequential processing (not parallel)
- Approximate processing time: 1-5 seconds per image
- Network overhead: 70-280 KB uploaded per image
- CSV columns added: image_small, image_thumb
- Output: `dart_export_with_derivatives_YYYYMMDD_HHMMSS.csv`

---

## [1.3.3] - 2026-05-13

### Summary
Version 1.3.3 adds an emergency stop feature (Kill Switch) to halt long-running Azure upload operations in Function 2.

### Added
- **Kill Switch Button**: Emergency stop for batch operations
  - Red "🛑 Kill Switch" button in Functions section
  - Stops Azure uploads immediately after current file completes
  - Located next to Help Mode checkbox in UI
  - Provides clean stop without data corruption
- **Kill Switch Logic**: Safe operation interruption
  - Boolean flag checked in Azure upload loop
  - Current file upload completes before stopping (no mid-upload interruption)
  - Logs warning message when activated
  - Updates UI status with stop notification
  - Automatically resets when Function 2 runs again
- **Handler Function**: `on_kill_switch_click()`
  - Sets kill_switch flag to True
  - Logs warning to file and UI
  - Updates status text with error styling

### Changed
- **Function 2**: Enhanced with kill switch checking
  - Resets kill_switch to False at function start
  - Checks kill_switch in Azure upload loop
  - Breaks upload loop cleanly when activated
  - CSV export continues with partial results
  - Logs show files uploaded before stop

### Documentation
- **FUNCTION_2_EXPORT_CSV.md**: New "Kill Switch - Emergency Stop" section
  - When to use the kill switch
  - How to use step-by-step instructions
  - What happens when activated
  - Comparison table: Kill Switch vs Force Quit
  - Best practices for clean operation stops
- **User Pattern**: Based on CABB (Crunch Alma Bibs in Bulk) kill switch implementation
  - Proven pattern for emergency stops in batch operations
  - Consistent UX across Digital.Grinnell tools

---

## [1.3.2] - 2026-05-13

### Summary
Version 1.3.2 implements Azure Blob Storage upload functionality in Function 2, enabling automatic file uploads with renamed filenames and complete object_location URL generation for CollectionBuilder.

### Added
- **Azure Upload in Function 2**: Automatic file uploads to Azure Blob Storage during CSV export
  - Files uploaded to Azure with `dg_<epoch>` identifiers as filenames (e.g., `dg_1715614222.jpg`)
  - Original file extensions preserved
  - Content-Type headers automatically set based on file type
  - Validates Azure configuration before starting export
  - Reports upload success/failure statistics
  - Continues CSV export even if some uploads fail
- **object_location Field**: Complete Azure Blob Storage URLs auto-populated in CSV
  - Format: `https://{account}.blob.core.windows.net/{container}/{path}/{objectid}{ext}`
  - Example: `https://collectionbuilder.blob.core.windows.net/objs/tdps/dg_1715614222.jpg`
  - Populated automatically if `object_location` column exists in template
  - Empty if Azure is not configured
- **Azure Helper Functions**: Core Azure functionality
  - `init_azure_client()`: Initialize BlobServiceClient and validate connection
  - `build_object_location()`: Generate complete Azure URLs from path and object ID
  - `upload_to_azure()`: Upload files with renamed filenames and content type detection
- **Dependency**: Added `azure-storage-blob>=12.19.0` to requirements
  - Enables Azure Blob Storage operations
  - Connection validation and file upload capabilities

### Changed
- **Function 2 CSV Export**: Enhanced with Azure upload integration
  - Validates Azure configuration at start (if configured)
  - Builds object_location for each file during processing
  - Uploads files to Azure in parallel with CSV generation
  - Includes object_location in CSV output (if column exists)
  - Result dialog shows upload statistics (succeeded/failed counts)
  - Log messages track each upload attempt
- **Import Statements**: Added Azure SDK imports
  - `from azure.storage.blob import BlobServiceClient, ContentSettings`

### Documentation
- **FUNCTION_2_EXPORT_CSV.md**: Comprehensive Azure upload documentation
  - New "Azure Blob Storage Upload" section explaining the four-step process
  - Azure configuration requirements and setup instructions
  - Updated CSV examples to include `object_location` column
  - Notes on DART's three-folder structure (/objs/, /smalls/, /thumbs/)
  - Behavior when Azure is not configured
- **Updated Examples**: All CSV examples now show `object_location` field

### Technical Details
- **File Renaming**: Original files (e.g., `photo_001.jpg`) uploaded as `dg_1715614222.jpg`
- **URL Structure**: Account name extracted from connection string to build complete URLs
- **Content Types**: Automatic MIME type detection for images, videos, audio, PDFs, archives
- **Error Handling**: Individual upload failures don't block CSV export
- **Validation Order**: Path validation → Connection test → Upload → CSV generation

### Notes
- Azure uploads only to `/objs/` folder in this version
- Future functions will handle `/smalls/` and `/thumbs/` derivatives
- Original local files remain unchanged
- CSV export works with or without Azure configured
- Compound parent objects have no object_location (no physical file)

---

## [1.3.1] - 2026-05-13

### Summary
Version 1.3.1 adds Azure Blob Storage path validation to ensure proper folder structure for DART's three-tier storage system.

### Added
- **Azure Path Validation**: Function 0 now validates `azure_blob_storage_path` setting
  - **Required**: Path must contain `/objs/` folder for original source files
  - Real-time validation feedback as you type
  - Validation before saving settings prevents invalid configurations
  - Helpful error messages guide correct path format
  - Function: `validate_azure_path()` checks path structure
- **Documentation**: Updated FUNCTION_0_APP_SETTINGS.md
  - Documented `/objs/` folder requirement
  - Explained three-folder structure: `/objs/`, `/smalls/`, `/thumbs/`
  - Added validation notes and examples
  - Updated example configurations to show proper structure

### Changed
- **azure_blob_storage_path Setting**: Now validated before save
  - Must contain `/objs/` folder (enforced)
  - Should have parallel `/smalls/` and `/thumbs/` folders (documented, not enforced)
  - Real-time validation text appears below field
  - Hint text updated to: "Azure Blob Storage path (must contain /objs/ folder)"

### Notes
- **DART Storage Structure**: Three parallel folders in Azure:
  - `/objs/` - Original source files (source of truth)
  - `/smalls/` - Medium-sized derivatives
  - `/thumbs/` - Thumbnail-sized derivatives
- Only `/objs/` is validated programmatically
- `/smalls/` and `/thumbs/` are expected to exist but not verified (would require Azure SDK/API call)

---

## [1.3.0] - 2026-05-13

### Summary
Version 1.3.0 introduces comprehensive CSV metadata management for CollectionBuilder workflows:

**Key Highlights:**
- Complete CSV metadata infrastructure with template validation
- Function 2 replaced with CSV export functionality
- Azure Blob Storage connection string support (encrypted)
- Core metadata CSV designation and auto-copy to working directory
- CollectionBuilder-compatible CSV generation with auto-populated fields

### Added
- **Function 2: CSV Export** 📊: Complete rewrite of Function 2
  - Exports analyzed assets to CSV using configured template structure
  - Auto-populates objectid, filename, parentid, display_template, and format fields
  - Full compound object support with parent/child relationships:
    - Writes compound parent objects first with `display_template=compound_object`
    - Child objects include `parentid` field linking to parent
    - Suggested title auto-generated for compound parents from filename pattern
    - Compound parents have blank filename (no physical file)
  - Maps file extensions to CollectionBuilder display_template layouts:
    - Images (.jpg, .png, etc.) → `image`
    - Videos (.mp4, .mov, etc.) → `video`
    - Audio (.mp3, .wav, etc.) → `audio`
    - PDFs → `pdf`
    - Archives (.zip, etc.) → `record`
    - Compound parents → `compound_object`
  - Generates timestamped CSV files: `dart_export_YYYYMMDD_HHMMSS.csv`
  - Validates template has required CollectionBuilder fields (objectid, filename)
  - Preserves empty template columns for manual/automated metadata population
  - Integrates with Function 1 compound grouping logic for consistent behavior
- **CSV Template Configuration**: Function 0 settings expanded
  - `csv_structure_file`: Path to CSV template defining metadata schema
  - `core_metadata_csv`: Master metadata CSV file designation (optional)
  - Browse buttons with file picker integration
  - Clear buttons to reset file selections
  - Real-time validation of CSV structure on selection
  - Auto-populates core CSV from template when undefined
- **CSV Auto-Copy Feature**: Intelligent file management
  - Copies both CSV files to working directory on settings save
  - Handles case where template and core point to same file
  - Deduplication logic prevents double-copying
  - Ensures CSV files stay with project data
- **Azure Storage Integration**: Cloud storage connection settings
  - `azure_connection_string`: Encrypted connection string field (password field with reveal)
  - Added to SENSITIVE_FIELDS for automatic encryption
  - Dedicated UI section "Azure Storage (encrypted)"
  - Comprehensive documentation on obtaining connection string from Azure Portal
  - Ready for future upload functions to use
- **CSV Validation Functions**: Robust template checking
  - `validate_csv_structure()`: Verifies required CollectionBuilder fields exist
  - `validate_core_metadata_csv()`: Checks core CSV matches template structure
  - `copy_csv_to_working_dir()`: Smart copy with same-file detection
  - Real-time feedback in Function 0 dialog
- **Documentation**: Complete help system
  - FUNCTION_2_EXPORT_CSV.md: Comprehensive Function 2 guide
  - FUNCTION_0_APP_SETTINGS.md: Updated with CSV and Azure sections
  - BEST_PRACTICES.md: CSV workflow guidance and filename conventions
  - README.md: Updated Core Mission with CSV workflow description
- **Code Refactoring**: Improved maintainability
  - Extracted `analyze_compound_objects()` as shared function (~300 lines)
  - Eliminated ~150 lines of duplicated compound analysis code from Function 2
  - Both Function 1 and Function 2 now call same analysis logic
  - Single source of truth for parent/child relationship identification
  - Improved consistency and reduced maintenance burden

### Changed
- **Function 2 Purpose**: Complete functional replacement
  - **Old**: Count files by extension (simple example function)
  - **New**: Export assets to CSV for CollectionBuilder workflows
  - Icon unchanged (📊) but represents data export now
  - Help file changed from FUNCTION_2_COUNT_FILES.md to FUNCTION_2_EXPORT_CSV.md
- **Settings UI Organization**: Restructured Function 0 dialog
  - CSV fields grouped together with validation feedback
  - Azure settings in dedicated "Azure Storage (encrypted)" section
  - Other sensitive fields grouped under "Other sensitive fields (encrypted)"
  - Improved visual hierarchy and field grouping
- **Default Settings**: Added new fields to DEFAULT_APP_SETTINGS
  - csv_structure_file: ""
  - core_metadata_csv: ""
  - azure_blob_storage_path: ""
  - azure_connection_string: ""

### Removed
- **Old Function 2**: File counting functionality removed
  - `on_function_2_count_files()` replaced by `on_function_2_export_csv()`
  - FUNCTION_2_COUNT_FILES.md retained for reference but not linked

### Notes
- CSV workflow supports iterative metadata development across batches
- Object IDs remain persistent - same file always gets same ID
- Empty CSV columns ready for enrichment by future functions or manual editing
- Azure upload functionality to be implemented in future functions
- CollectionBuilder compatibility validated at template selection time

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
- **Function 1 Enhanced Pattern Matching**: Third pass algorithm improved with trailing separator normalization
  - Automatically strips trailing spaces, underscores, and hyphens from extracted base names
  - Handles double spaces and inconsistent trailing separators
  - Example: "Traditions and Encounters - " and "Traditions and Encounters" now normalize to same base
  - Ensures more reliable grouping for files with spacing variations

### Changed
- **Log File Location**: Dynamically created in `{working_folder}/logfiles/`
  - Logs are now stored in the working/outputs folder for better organization
  - Creates `logfiles` subdirectory within your working folder
  - Initial startup uses `~/DART-data/logfiles/` until working folder is set
  - Automatically switches to working folder logs when folder is selected
  - Keeps logs with the project data they relate to
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
- **Intelligent Pattern Analysis**: Three-pass grouping algorithm finds what filenames have in common
  - **Pass 1**: Extract prefixes from numbered files: `re.match(r'^(.+?)[\s_\-]*(\d+)$', stem)`
    - Handles leading numbers: "100 Nights-1" → prefix "100 nights", seq 1
  - **Pass 2**: Match unnumbered files against known numbered prefixes
    - Checks if unnumbered filename starts with any numbered prefix
    - Uses longest matching prefix (most specific)
    - Validates separator after prefix (space, underscore, hyphen)
    - "Wit Poster" starts with "wit" → matched
    - "AnnaChristie-F14-Program" starts with "annachristie-f14" → matched
  - **Pass 3**: Find common patterns among remaining unnumbered files
    - Extracts common base by removing last word after separator: `re.match(r'^(.+?)[\s_\-]+\w+$', stem)`
    - Groups files sharing the same base (2+ files, 3+ char base)
    - "Traditions and Encounters - Poster" → base "traditions and encounters"
    - "Traditions and Encounters_Program" → base "traditions and encounters" → grouped!
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
