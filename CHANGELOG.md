# DART Changelog

All notable changes to the DART (Digital Asset Routing and Transformation) project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- **Function 1** 📁: List all files in a directory
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
  - `FUNCTION_1_LIST_FILES.md`
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
