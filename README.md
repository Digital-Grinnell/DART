# � &nbsp; DART - Digital Asset Routing and Transformation

**DART** (Digital Asset Routing and Transformation) is a professional desktop application built with [Flet](https://flet.dev) for processing digital asset workflows. Select a 'truth' set folder of digital asset files or a CSV file listing assets, then apply powerful functions to create derivatives, modify metadata, and route assets through your transformation pipeline.

## Core Mission

DART is focused on providing a valid import/ingest-compatible CSV metadata file using the digital objects and their original filenames as the "source of truth". Each object is given a unique Digital.Grinnell identifier and DART can help maintain those while directing files to proper long-term/preservation storage.

**CSV Metadata Workflow:**
- Define your metadata schema using a **CSV structure template** (with required CollectionBuilder fields)
- Designate a **core metadata CSV** as your master/controlling metadata file
- Generate new metadata from asset batches using the template structure
- Future functions will intelligently merge new metadata into the core CSV
- Maintain consistency and avoid duplicate identifiers across workflow phases

## Purpose

DART provides a comprehensive platform for digital asset management workflows:
- **Select source assets** from a folder (truth set) or CSV manifest
- **Process and transform** digital assets through multiple workflow phases
- **Generate derivatives** in various formats and sizes
- **Modify and update** CSV metadata files
- **Route assets** to output directories with customizable organization
- **Track progress** with detailed logging and status reporting

## Features

### Core Platform Features
- **Persistent Settings**: Automatic saving/loading of window position, directories, and user preferences
- **Persistent File Selection**: Selected files are remembered across app restarts - no need to re-select
- **Permanent ID Assignment**: Files receive unique `dg_<epoch>` identifiers that never change once assigned
- **CSV Metadata Management**: Template-based CSV generation with intelligent merging into master metadata file
- **CollectionBuilder Compatibility**: Validates CSV structure for required fields (objectid, filename)
- **Professional Logging**: Timestamped log files in `{working_folder}/logfiles/` with real-time display
- **Function Management**: Icon-enhanced dropdown with usage tracking and workflow ordering
- **Help Mode**: Built-in markdown help viewer for each function with copy-to-clipboard
- **Smart Folder Management**: Collapsible folders section to maximize screen space
- **File Selection**: Dedicated file picker with persistence (separate from directories)
- **Status & Log Output**: Professional status display with copy/paste and log management
- **Secure Settings**: Encrypted storage for API keys and credentials

### Workflow Functions
- **Function 0** ⚙️: App Settings with encrypted sensitive fields
- **Function 1** 🎯: Analyze digital assets and generate standard DG identifiers (dg_<epoch>)
  - Creates compound objects for related file groups (optional)
  - Permanent ID assignment with folder-based compound tracking
- **Function 2** 📊: Export analyzed assets to CSV using template structure
  - Generates CollectionBuilder-compatible metadata files
  - Auto-populates objectid, filename, parentid, display_template, and format fields
  - Supports compound object export with parent/child relationships
  - Maps file types to CollectionBuilder layouts (image/video/audio/pdf/compound_object)
  - Timestamped exports to working directory
- **Function 3** 💻: Display system information

*Additional asset processing functions are added as needed for your specific workflow.*

## Quick Start

### Running from Source

1. **Clone or copy this repository**
   ```bash
   cd /path/to/your/projects
   cp -r DART my-new-app
   cd my-new-app
   ```

2. **Run the application**
   ```bash
   # macOS/Linux
   ./run.sh
   
   # Windows
   run.bat
   ```

The run scripts automatically:
- Create a Python virtual environment
- Install dependencies
- Launch the application

## Requirements

- **Python 3.8+**
- **Flet 0.25.2** (installed automatically by run scripts)

No other dependencies required for the base template.

## Project Structure

```
DART/
├── app.py                      # Main application
├── run.sh                      # macOS/Linux launcher
├── run.bat                     # Windows launcher
├── build_dmg.sh               # macOS installer builder
├── build_windows_zip.sh       # Windows package builder
├── python_requirements.txt     # Python dependencies
├── .gitignore                  # Git exclusions
├── LICENSE                     # MIT License
├── CHANGELOG.md               # Version history
├── QUICKSTART.md              # Quick reference guide
├── FUNCTION_0_APP_SETTINGS.md # Help docs for Function 0
├── FUNCTION_1_ANALYZE_ASSETS.md  # Help docs for Function 1
├── FUNCTION_2_EXPORT_CSV.md     # Help docs for Function 2 (CSV export)
├── FUNCTION_3_SYSTEM_INFO.md  # Help docs for Function 3
└── README.md                   # This file
```

### Runtime Files
When you run the application, these are created automatically:
```
~/DART-data/
├── persistent.json             # Saved settings and state
└── encryption_key              # Encryption key for sensitive settings

{working_folder}/
├── dart_settings.json          # Per-folder app settings (in working/outputs folder)
└── logfiles/                   # Application logs (in working/outputs folder)
    └── dart_YYYYMMDD_HHMMSS.log
```

**Note:** Log files are created in your working/outputs folder (set in the UI) to keep logs organized with the project data they relate to. On initial startup before a working folder is set, logs temporarily go to `~/DART-data/logfiles/`.
```

## Customizing DART for Your Application

### 1. Rename the Application

Update these items throughout the codebase:
- `page.title` in `app.py`
- Data directory name (`DART-data` → `YourApp-data`)
- Window title and header text
- Script headers in `run.sh` and `run.bat`
- README title and descriptions

### 2. Add Your Own Functions

To add a new function, follow the OHM-proven pattern:

**a) Create the function handler in `app.py`:**

```python
def on_function_4_your_feature(e):
    """Function 4: Your custom feature description."""
    storage.record_function_usage("Function 4")
    
    # Access current directory if needed
    if not current_directory or not current_directory.exists():
        update_status("Error: Please select an input folder first", is_error=True)
        return
    
    # Your implementation here
    # ... do work ...
    
    update_status("Your feature completed successfully")
    add_log_message("Function 4 completed")
    logger.info("Function 4: Completed")
```

**b) Add to the active_functions list:**

```python
active_functions = [
    "function_1_list_files",
    "function_2_count_files",
    "function_3_system_info",
    "function_4_your_feature",  # Add this
]
```

**c) Register in the functions dictionary:**

```python
functions = {
    # ... existing functions ...
    "function_4_your_feature": {
        "label": "4: Your Custom Feature",
        "icon": "🎯",  # Pick an emoji icon
        "handler": on_function_4_your_feature,
        "help_file": "FUNCTION_4_YOUR_FEATURE.md"
    },
}
```

**d) Create help documentation:**

Create `FUNCTION_4_YOUR_FEATURE.md` with markdown documentation. The template automatically:
- Shows help in a dialog when Help Mode is enabled
- Provides copy-to-clipboard functionality
- Displays the function's icon and label

### 3. Add Dependencies

If your functions need additional Python packages:

1. Add them to `python_requirements.txt`:
   ```
   flet==0.25.2
   flet-desktop==0.25.2
   your-package>=1.0.0
   ```

2. Import them in `app.py`:
   ```python
   try:
       import your_package
       YOUR_PACKAGE_AVAILABLE = True
   except ImportError:
       YOUR_PACKAGE_AVAILABLE = False
   ```

3. Check availability before use:
   ```python
   if not YOUR_PACKAGE_AVAILABLE:
       show_status("Error: your-package not installed", is_error=True)
       return
   ```

### 4. Modify UI Layout

The layout is defined in the `page.add()` section at the bottom of `app.py`. The structure uses Flet containers and rows:

```python
page.add(
    ft.Container(
        content=ft.Column([
            # Your UI components here
        ]),
        padding=30,
    )
)
```

Add your own UI elements:
- `ft.TextField()` - Text input fields
- `ft.Dropdown()` - Dropdown menus
- `ft.Checkbox()` - Checkboxes
- `ft.ElevatedButton()` - Buttons
- `ft.Text()` - Labels and text
- `ft.Row()` and `ft.Column()` - Layout containers

See [Flet documentation](https://flet.dev/docs/) for all available controls.

### 5. Persistent Settings

To save additional settings:

```python
# Save a custom setting
storage.set_ui_state("my_custom_field", "value")

# Load a custom setting
value = storage.get_ui_state("my_custom_field", default="default_value")
```

All settings are automatically saved to `~/DART-data/persistent.json`.

### 6. Remove Example Functions

Once you've built your own functions, clean up the examples:

1. Delete function handlers from `app.py`: `on_function_1_list_files`, `on_function_2_count_files`, `on_function_3_system_info`
2. Delete help files: `FUNCTION_1_ANALYZE_ASSETS.md`, `FUNCTION_2_COUNT_FILES.md`, `FUNCTION_3_SYSTEM_INFO.md`
3. Remove entries from `active_functions` list and `functions` dictionary
4. Update the title and description to match your application

## UI Architecture

DART uses OHM's proven layout structure:

- **Collapsible Directories Section**: Saves vertical space once directories are set
- **File Selection**: Always visible for quick file changes between operations
- **Functions Dropdown**: Icon-enhanced with emoji indicators
- **Status Output**: Multi-line with copy-to-clipboard
- **Log Output**: Timestamped entries with copy and clear functionality
- **Help Mode**: Toggle to view function documentation instead of executing

This layout has been refined through real-world use in production applications.

## Building Standalone Packages

### macOS DMG

Create a distributable DMG file:

```bash
bash build_dmg.sh 1.0
```

This creates `YourApp_v1.0.dmg` with:
- Self-contained app bundle
- Automatic dependency installation on first launch
- No code signing (users must right-click → Open on first launch)

### Windows ZIP

Create a distributable ZIP package:

```bash
bash build_windows_zip.sh 1.0
```

This creates `YourApp_v1.0_Windows.zip` with:
- All source files
- `run.bat` launcher
- Automatic dependency installation on first launch

Recipients need Python 3 installed (one-time setup).

## Logging

All application activity is logged to:
```
{working_folder}/logfiles/dart_YYYYMMDD_HHMMSS.log
```

Log files are stored in your working/outputs folder (set in the UI) to keep logs organized with the project data they relate to. On initial startup before a working folder is set, logs temporarily go to `~/DART-data/logfiles/`.

Use the logger in your functions:
```python
logger.info("Information message")
logger.warning("Warning message")
logger.error("Error message")
logger.debug("Debug message")
```

Console output shows only errors; all levels are written to log files.

## Help Documentation

Help files use GitHub Flavored Markdown and support:
- Headers (`#`, `##`, `###`)
- Lists (ordered and unordered)
- Code blocks with syntax highlighting
- Tables
- Links
- **Bold** and *italic* text

Create help documentation for each function to guide users.

## Examples of Apps Built with This Template

- **OHM - Oral History Manager**: Audio processing workflow for digital archives
- *(Add your own app here!)*

## Tips for Development

### Testing Your Changes

After modifying `app.py`, just rerun:
```bash
./run.sh  # or run.bat on Windows
```

The virtual environment and dependencies are cached, so subsequent runs are fast.

### Debugging

- Check log files in `{working_folder}/logfiles/` for errors (or `~/DART-data/logfiles/` before working folder is set)
- Console shows error-level messages immediately
- Use `logger.debug()` for detailed troubleshooting

### Version Control

Initialize a git repository for your new app:
```bash
git init
git add .
git commit -m "Initial commit based on DART"
```

The included `.gitignore` excludes:
- Virtual environments (`.venv/`)
- Python cache (`__pycache__/`)
- Log files
- Build artifacts

## Flet Resources

- **Documentation**: https://flet.dev/docs/
- **Controls Gallery**: https://flet.dev/docs/controls
- **GitHub**: https://github.com/flet-dev/flet
- **Discord**: https://discord.gg/dzWXP8SHG8

## License

MIT License - See [LICENSE](LICENSE) or [LICENSE.md](LICENSE.md) for full details.

Copyright (c) 2026 Digital.Grinnell / DART Contributors

Free to use, modify, and distribute. Attribution appreciated but not required.

## Contributing

Contributions are welcome! Please feel free to:
- Report bugs or issues
- Suggest new features or improvements
- Submit pull requests
- Share applications you've built with DART

## About

DART (Digital Asset Routing and Transformation) was created by extracting and generalizing the proven UI framework from OHM (Oral History Manager). It provides a professional platform for Flet desktop applications, with robust support for settings persistence, logging, function management, and help systems.

The application architecture has been refined through real-world production use, ensuring reliability and maintainability.

**Repository**: https://github.com/Digital-Grinnell/DART

Built with ❤️ using [Flet](https://flet.dev) by the Digital.Grinnell team.
