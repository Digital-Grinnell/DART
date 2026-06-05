# DART Installation Guide

This document provides detailed installation instructions for DART (Digital Asset Routing and Transformation) on macOS, Windows, and Linux systems.

---

## Table of Contents

- [macOS Installation (DMG)](#macos-installation-dmg)
- [Windows Installation (ZIP)](#windows-installation-zip)
- [Linux Installation (Source)](#linux-installation-source)
- [Prerequisites](#prerequisites)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)

---

## macOS Installation (DMG)

DART for macOS is distributed as a DMG file with an automated installer that requires **no admin permissions**.

### Prerequisites

- **macOS 12** (Monterey) or later
- **Python 3.8+** must be installed
  - Download from: [python.org/downloads](https://python.org/downloads)
  - Or install via Homebrew: `brew install python`
  - Verify: `python3 --version`

### Installation Steps

1. **Download the DMG**
   - Download `DART_v2.x.dmg` from your distribution source

2. **Open the DMG**
   - Double-click the downloaded DMG file
   - A new window opens showing the installer contents

3. **Run the Installer**
   - Double-click: `Install DART.command`
   
   **Note for first-time users (unsigned app):**
   - If the installer won't open, macOS Gatekeeper is blocking it
   - Right-click on `Install DART.command` → select "Open"
   - Click "Open" in the security dialog
   - This is only needed once

4. **Follow the Installation**
   - A Terminal window opens with the installer
   - The installer checks for Python 3
   - Confirms installation location: `~/DART/`
   - Copies all files (takes a few seconds)
   - Creates a launcher on your Desktop
   - Press Enter when finished

5. **Eject the DMG**
   - Right-click the mounted DART volume → Eject
   - Or drag it to the Trash

### Installation Location

DART is installed to: `~/DART/` (your home directory)

```
~/DART/
├── Launch DART.command   # Double-click to start DART
├── app.py                # Main application
├── run.sh                # Launcher script
├── common_dg_utilities/  # Utility functions (included)
├── INSTALLATION.md       # This file
├── README.md            # Full documentation
└── ... (other files)
```

### Desktop Shortcut

The installer creates: **Launch DART** on your Desktop

- Double-click this to launch DART at any time
- It's a symbolic link to `~/DART/Launch DART.command`

### First Launch

1. **Start DART**
   - Double-click: `Launch DART` (on Desktop)
   - Or navigate to `~/DART/` and double-click: `Launch DART.command`

2. **Automatic Setup (first time only)**
   - A Terminal window opens
   - Python virtual environment is created in `~/DART/.venv/`
   - Dependencies install automatically (1-2 minutes)
   - Progress is shown in the Terminal

3. **DART Window Opens**
   - The DART application window appears when ready
   - The Terminal window stays open (don't close it!)
   - Minimize the Terminal if you want it out of the way

4. **Subsequent Launches**
   - Just double-click the launcher
   - DART starts immediately (no setup needed)
   - Dependencies are already installed

### Why No Applications Folder?

**Traditional approach issues:**
- Many work computers restrict Applications folder access
- Requires admin permissions to install
- Users encounter permission errors

**DART's solution:**
- Installs to `~/DART/` in your home directory
- No admin permissions required
- Works on all systems, including managed/restricted computers
- Clean, predictable location

---

## Windows Installation (ZIP)

DART for Windows is distributed as a ZIP archive.

### Prerequisites

- **Windows 10** or **Windows 11**
- **Python 3.8+** must be installed
  - Download from: [python.org/downloads](https://python.org/downloads)
  - **During installation: Check "Add Python to PATH"** ✅
  - Verify: Open Command Prompt, type `python --version`

### Installation Steps

1. **Download the ZIP**
   - Download `DART_v2.x_Windows.zip` from your distribution source

2. **Extract the Archive**
   - Right-click the ZIP file → Extract All...
   - Choose a convenient location (e.g., `C:\Users\YourName\DART\`)
   - Or extract to your Desktop

3. **Installation Location**
   - The extracted folder contains all DART files
   - No further installation needed

### First Launch

1. **Open the DART folder**
   - Navigate to where you extracted the files

2. **Run the launcher**
   - Double-click: `run.bat`

3. **Automatic Setup (first time only)**
   - A Command Prompt window opens
   - Python virtual environment is created in `.venv\`
   - Dependencies install automatically (1-2 minutes)
   - Progress is shown in the console

4. **DART Window Opens**
   - The DART application window appears when ready
   - The Command Prompt window stays open (don't close it!)
   - Minimize the console if you want it out of the way

5. **Subsequent Launches**
   - Just double-click `run.bat`
   - DART starts immediately

### Creating a Desktop Shortcut (Optional)

1. Right-click `run.bat` → Send to → Desktop (create shortcut)
2. Rename the shortcut to "DART"
3. Double-click the Desktop shortcut to launch DART

---

## Linux Installation (Source)

DART runs from source on Linux systems.

### Prerequisites

- **Python 3.8+**
  - Most Linux distributions include Python 3
  - Verify: `python3 --version`
  - Install if needed:
    - Debian/Ubuntu: `sudo apt install python3 python3-venv`
    - Fedora/RHEL: `sudo dnf install python3`
    - Arch: `sudo pacman -S python`

### Installation Steps

1. **Download or Clone**
   ```bash
   # If you have the source archive:
   unzip DART_v2.x.zip
   cd DART_v2.x
   
   # Or clone from repository:
   git clone https://github.com/Digital-Grinnell/DART.git
   cd DART
   ```

2. **Run DART**
   ```bash
   ./run.sh
   ```

3. **First Launch**
   - The script creates a Python virtual environment in `.venv/`
   - Installs all dependencies automatically
   - Launches the DART application
   - Subsequent runs skip the setup phase

### Creating a Desktop Launcher (Optional)

Create `~/.local/share/applications/dart.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=DART
Comment=Digital Asset Routing and Transformation
Exec=/path/to/DART/run.sh
Icon=utilities-terminal
Terminal=false
Categories=Utility;
```

Update `/path/to/DART/` with your actual path.

---

## Prerequisites

### Python 3.8 or Later

DART requires Python 3.8 or later. To verify your Python version:

```bash
# macOS/Linux
python3 --version

# Windows
python --version
```

**Installation:**

- **macOS:**
  - Download: [python.org/downloads](https://python.org/downloads)
  - Or via Homebrew: `brew install python`

- **Windows:**
  - Download: [python.org/downloads](https://python.org/downloads)
  - **Important:** Check "Add Python to PATH" during installation

- **Linux:**
  - Usually pre-installed
  - If needed: `sudo apt install python3` (Debian/Ubuntu)

### Python Dependencies

The following Python packages are installed automatically on first launch:

- **flet 0.25.2** — UI framework
- **flet-desktop 0.25.2** — Desktop-specific features
- **cryptography** — Encrypted settings storage
- **azure-storage-blob 12.19.0+** — Azure Blob Storage integration
- **Pillow** — Image processing
- **PyMuPDF (fitz)** — PDF processing
- **pandas** — Data manipulation

**You don't need to install these manually** — the `run.sh` / `run.bat` scripts handle everything.

---

## Troubleshooting

### macOS Issues

#### "Install DART.command can't be opened"

**Cause:** macOS Gatekeeper blocking unsigned app

**Solution:**
1. Right-click on `Install DART.command`
2. Select "Open" from the menu
3. Click "Open" in the security dialog
4. Only needed once

#### "Python 3 not found" error

**Cause:** Python not installed or not in PATH

**Solution:**
```bash
# Install Python via Homebrew
brew install python

# Or download from python.org
# Then verify:
python3 --version
```

#### Installer says "DART is already installed"

**Cause:** Previous DART installation exists

**Solution:**
- Type `y` to overwrite the old installation
- Or type `n` to cancel and manually remove `~/DART/` first

#### DART window doesn't appear

**Cause:** Terminal window was closed during setup

**Solution:**
1. Open Terminal
2. Navigate: `cd ~/DART`
3. Run manually: `bash run.sh`
4. Watch for error messages

### Windows Issues

#### "python is not recognized"

**Cause:** Python not installed or not in PATH

**Solution:**
1. Install Python from [python.org](https://python.org/downloads)
2. **During installation: Check "Add Python to PATH"**
3. Restart Command Prompt
4. Verify: `python --version`

#### Dependencies fail to install

**Cause:** Network issues or pip outdated

**Solution:**
```cmd
# Upgrade pip
python -m pip install --upgrade pip

# Then re-run DART
run.bat
```

#### Virtual environment errors

**Cause:** Corrupt virtual environment

**Solution:**
```cmd
# Delete the virtual environment
rmdir /s .venv

# Re-run launcher (recreates .venv)
run.bat
```

### Linux Issues

#### `./run.sh`: Permission denied

**Cause:** Script not executable

**Solution:**
```bash
chmod +x run.sh
./run.sh
```

#### "No module named 'tkinter'"

**Cause:** tkinter not installed (required by flet)

**Solution:**
```bash
# Debian/Ubuntu
sudo apt install python3-tk

# Fedora/RHEL
sudo dnf install python3-tkinter
```

### Common Issues (All Platforms)

#### DART closes immediately after launch

**Cause:** Error during startup

**Solution:**
1. Look for error messages in the Terminal/Console window
2. Check log files in `~/DART-data/logfiles/` or `{working_folder}/logfiles/`
3. Common causes:
   - Missing Python dependencies (re-run installer)
   - Corrupted settings file (delete `~/DART-data/persistent.json`)

#### "common_dg_utilities not found" error

**Cause:** DMG/ZIP was missing the utilities folder

**Solution:**
- This should not happen with properly built installers
- Contact support or rebuild DMG/ZIP with utilities included
- For developers: Ensure `../common-DG-utilities/` exists when building

---

## Uninstallation

### macOS

1. **Delete the application folder:**
   ```bash
   rm -rf ~/DART
   ```

2. **Delete user data (optional):**
   ```bash
   rm -rf ~/DART-data
   ```

3. **Remove Desktop shortcut:**
   - Drag `Launch DART` from Desktop to Trash

### Windows

1. **Delete the DART folder:**
   - Navigate to where you extracted DART
   - Delete the entire folder

2. **Delete user data (optional):**
   - Navigate to: `C:\Users\YourName\DART-data\`
   - Delete the folder

3. **Remove Desktop shortcut (if created):**
   - Delete the DART shortcut from Desktop

### Linux

```bash
# Delete DART folder
rm -rf ~/path/to/DART

# Delete user data (optional)
rm -rf ~/DART-data

# Remove desktop launcher (if created)
rm ~/.local/share/applications/dart.desktop
```

---

## Support

### Documentation

- **README.md** — Full application documentation
- **QUICKSTART.md** — Quick reference guide
- **Function Help** — Built-in help for each function (Help Mode toggle in app)

### Getting Help

- **Repository:** [https://github.com/Digital-Grinnell/DART](https://github.com/Digital-Grinnell/DART)
- **Issues:** Report bugs on GitHub Issues
- **Questions:** Use GitHub Discussions

### Log Files

DART maintains detailed log files for troubleshooting:

- **Startup logs:** `~/DART-data/logfiles/`
- **Operational logs:** `{working_folder}/logfiles/` (set in app)
- **Format:** `dart_YYYYMMDD_HHMMSS.log`

Include relevant log excerpts when reporting issues.

---

## System Requirements

### Minimum

- **OS:** macOS 12+, Windows 10+, or modern Linux
- **Python:** 3.8 or later
- **Memory:** 2 GB RAM
- **Disk:** 500 MB free space
- **Display:** 1280x720 or higher

### Recommended

- **OS:** macOS 13+, Windows 11, or latest LTS Linux
- **Python:** 3.10 or later
- **Memory:** 4 GB RAM
- **Disk:** 1 GB free space
- **Display:** 1920x1080 or higher

---

## Security Note

DART stores sensitive settings (like Azure connection strings) using encrypted storage:

- **Encryption key:** `~/DART-data/encryption_key`
- **Settings file:** `~/DART-data/persistent.json` (sensitive fields encrypted)
- **Working settings:** `{working_folder}/dart_settings.json` (per-project)

**Keep your encryption key secure.** If lost, you'll need to re-enter encrypted settings.

---

*Last updated: June 5, 2026*  
*DART Version: 2.x*  
*Documentation: [https://github.com/Digital-Grinnell/DART](https://github.com/Digital-Grinnell/DART)*
