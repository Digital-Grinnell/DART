# DART Quick Start Guide

Welcome to **DART - Digital Asset Routing and Transformation**!

This application was created by extracting the proven UI framework from OHM (Oral History Manager) and adapting it for digital asset management workflows.

## What's Included

### Core Files
- **app.py** - Main application with 3 example functions
- **python_requirements.txt** - Just Flet dependencies
- **run.sh** / **run.bat** - Launch scripts for macOS/Linux and Windows
- **.gitignore** - Python/Flet-appropriate exclusions

### Documentation
- **README.md** - Comprehensive guide to using and customizing DART
- **FUNCTION_1_LIST_FILES.md** - Help for example function 1
- **FUNCTION_2_COUNT_FILES.md** - Help for example function 2
- **FUNCTION_3_SYSTEM_INFO.md** - Help for example function 3
- **CHANGELOG.md** - Version history starting at 1.0.0
- **LICENSE** - MIT license

### Build Tools
- **build_dmg.sh** - Create macOS .dmg installers
- **build_windows_zip.sh** - Create Windows .zip packages

### Git Repository
- Initialized with initial commit
- Ready to push to GitHub or other remote

## Try It Out

```bash
cd /Users/mcfatem/GitHub/DART
./run.sh
```

This will:
1. Create a Python virtual environment
2. Install Flet
3. Launch the application

## Next Steps

### 1. Test the Example Functions

The app includes three example functions:
- **Function 1**: Lists files in a directory
- **Function 2**: Counts files by extension
- **Function 3**: Shows system information

Enable "Help Mode" to view the documentation for each function.

### 2. Customize for Your New App

Follow the detailed instructions in **README.md** to:
- Rename the application
- Replace example functions with your own
- Add new UI components
- Include additional dependencies
- Modify the layout

### 3. Push to GitHub

```bash
cd /Users/mcfatem/GitHub/DART
git remote add origin https://github.com/yourusername/your-repo.git
git branch -M main
git push -u origin main
```

## What Was Removed from OHM

To create this generic template, the following OHM-specific items were removed:

### Removed Code
- All 6 OHM functions (merge audio, WAV→MP3, transcription, etc.)
- Audio file processing logic
- Speaker names UI components
- OHM-data directory structure
- MS Word Online integration
- PDF/DOCX generation
- Audio file listing and scanning
- FFmpeg dependency checking

### Removed Dependencies
- python-docx
- reportlab
- docx2pdf
- common-DG-utilities (sanitize_filename)

### Removed Files
- FUNCTION_0_MERGE_AUDIO.md through FUNCTION_5_REPORT_PROGRESS.md
- migrate_ohm_names.py
- OHM-specific build messages

### What Was Kept

The valuable framework components:
- ✅ Persistent settings system (window position, directories, function usage)
- ✅ Logging infrastructure with organized log files
- ✅ Function dropdown and execution pattern
- ✅ Help mode with markdown documentation viewer
- ✅ Directory picker dialogs with state persistence
- ✅ Status bar for user feedback
- ✅ Clean desktop UI layout
- ✅ Build scripts for distribution
- ✅ Virtual environment management

## Naming Suggestions

Dart (Digital Asset Routing and Transformation) was chosen for this application. The name reflects its focus on managing and transforming digital assets through a robust desktop interface.

To rename for your own purposes, search and replace throughout the codebase:
- `DART` → Your new name
- `Digital Asset Routing and Transformation` → Your new tagline
- `DART-data` → `YourName-data`

## OHM Remains Unchanged

As requested, the OHM directory at `/Users/mcfatem/GitHub/OHM` was not modified. All changes were made only in the new DART directory.

You can verify:
```bash
cd /Users/mcfatem/GitHub/OHM
git status  # Shows: "working tree clean"
```

## Questions?

See **README.md** for comprehensive documentation on:
- Adding your own functions
- Modifying the UI
- Managing dependencies
- Building standalone packages
- Flet resources and documentation links

Happy building! 🚀
