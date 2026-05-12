# Function 1: Analyze Digital Assets & Generate Standard DG Identifiers

## Purpose
Analyze selected digital asset files or scan a folder to generate unique standard DG identifiers for each file. Each identifier follows the format `dg_<epoch_time>` ensuring global uniqueness.

## When to Use
Use this function to:
- Generate standard unique identifiers for digital assets
- Prepare asset metadata with guaranteed unique IDs
- Create identifiers that can be tracked across systems
- Ensure each file has a globally unique, timestamp-based identifier

## Supported File Types
- **Images**: JPG, JPEG, PNG, GIF, TIF, TIFF, BMP, WEBP
- **PDFs**: PDF
- **Video**: MP4, MOV, AVI, MKV, WMV, FLV, WEBM
- **Audio**: MP3, WAV, FLAC, AAC, OGG, M4A, WMA
- **Archives**: ZIP, TAR, GZ, 7Z, RAR, BZ2

## Requirements
- **Either**: Files selected using the Files Selection picker (recommended)
- **Or**: Inputs folder must be selected (will scan entire folder)

## How It Works
1. **First checks** if files are selected in the Files Selection area
   - If files are selected, analyzes only those files
2. **Falls back** to scanning the Inputs Folder if no files are selected
   - Scans all files in the folder matching supported types
3. **Generates unique identifiers** using the standard DG format: `dg_<epoch_time>`
   - Each identifier is based on the current epoch time (seconds since 1970)
   - Automatically increments if duplicate detected (extremely rare)
   - Guarantees global uniqueness across all files

## Standard DG Identifier Format
All identifiers follow the standard Digital Grinnell format:
- **Format**: `dg_<epoch_time>`
- **Example**: `dg_1736712345`
- **Uniqueness**: Based on Unix epoch time (seconds since January 1, 1970)
- **Collision handling**: If duplicate detected, automatically increments
- **Persistence**: Once assigned, IDs NEVER change

### Benefits
- **Globally unique**: Can be used across multiple systems and databases
- **Time-based**: Inherently sortable by creation time
- **Simple**: No dependency on filename structure or patterns
- **Standard**: Consistent with other Digital Grinnell applications
- **Permanent**: File-to-ID mappings are stored and reused on subsequent runs

### ID Assignment and Persistence
When you run Function 1:
1. The app checks if each file already has an assigned ID (stored in working folder settings using **full file path** as key)
2. If an ID exists for that file path, it reuses that ID - **IDs never change**
3. If a file is new, it generates a new `dg_<epoch>` identifier
4. The mapping (full path → ID) is saved to `dart_settings.json` in the working folder
5. Results show: "X new, Y reused" to indicate which IDs were newly generated vs. retrieved

This ensures that once a file receives an identifier, running the function again will always return the same ID for that file. Using full paths prevents collisions between files with the same name in different directories.

## Usage

### Option 1: Analyze Selected Files (Recommended)
1. Use the **Files Selection** → **Browse...** button to select one or more files
2. Select **Function 1: Analyze Digital Assets & Generate Standard DG Identifiers** from the dropdown
3. Click **Execute Function**
4. Review the analysis results in the dialog

### Option 2: Scan Entire Folder
1. Leave Files Selection empty
2. Select an inputs folder using the **Inputs Folder** → **Browse...** button
3. Select **Function 1: Analyze Digital Assets & Generate Standard DG Identifiers** from the dropdown
4. Click **Execute Function**
5. Review the analysis results in the dialog

## Output
The function displays:
- Total count of digital asset files found
- Count of new vs. reused identifiers
- Compound object grouping status (enabled/disabled)
- List of identifiers mapped to filenames

**ID Persistence**: Shows "X new, Y reused" indicating how many IDs were newly generated vs. retrieved from storage.

**Uniqueness Validation**: The function automatically validates that all identifiers are unique. Standard DG identifiers are virtually guaranteed to be unique due to epoch-based generation.

### Example Output
```
Found 100 digital asset file(s) from selected files
Identifiers: 5 new, 95 reused (IDs never change once assigned)
Compound object grouping: DISABLED

• dg_1736712345 → Wit 001.JPG (/Users/username/assets/Wit 001.JPG)
• dg_1736712346 → Wit 002.JPG (/Users/username/assets/Wit 002.JPG)
• dg_1736712347 → Wit 003.JPG (/Users/username/assets/Wit 003.JPG)
...
• dg_1736712444 → Wit 100.JPG (/Users/username/assets/Wit 100.JPG)
```

In this example, 95 files already had assigned IDs from a previous run, and 5 new files received new IDs. The full file path is shown in parentheses for each asset.

Compound Object [photo]:
  • photo-001 → photo_001.jpg
  • photo-002 → photo_002.jpg

• docum → document.pdf

Compound Object [scan]:
  • scan-1 → scan-page1.tif
  • scan-2 → scan-page2.tif
```

## Notes
- Only files with recognized digital asset extensions are analyzed
- Object IDs are generated automatically and cannot be manually specified
- The algorithm handles various filename patterns (underscores, hyphens, mixed case)
- Compound object detection looks for files with the same alphabetic prefix
- Results are displayed in the dialog but not automatically saved (use other functions to export)
