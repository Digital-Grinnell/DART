# Function 1: Analyze Digital Assets & Generate Object IDs

## Purpose
Scan a folder of digital asset files (images, PDFs, video, audio, archives) and generate unique object IDs from filenames. Optionally groups similar filenames into compound objects.

## When to Use
Use this function to:
- Analyze a folder of digital assets and derive standardized object identifiers
- Identify compound objects (multi-file items like page scans, photo sequences)
- Prepare asset metadata for CSV export or further processing
- Verify filename patterns and object ID generation

## Supported File Types
- **Images**: JPG, JPEG, PNG, GIF, TIF, TIFF, BMP, WEBP
- **PDFs**: PDF
- **Video**: MP4, MOV, AVI, MKV, WMV, FLV, WEBM
- **Audio**: MP3, WAV, FLAC, AAC, OGG, M4A, WMA
- **Archives**: ZIP, TAR, GZ, 7Z, RAR, BZ2

## Requirements
- Inputs folder must be selected
- Working/Outputs folder must be selected (to load settings)

## Settings
This function respects the `group_compound_objects` setting from Function 0:
- **false** (default): Each file gets a unique object ID
- **true**: Files with similar base names are grouped as compound objects

## Object ID Generation Rules
1. Extract the base filename (without extension)
2. Separate alphabetic prefix from numeric suffix
3. Create a 3-5 character objectid from the prefix (lowercase)
4. Append numeric suffix if present to create unique IDs

### Examples
| Filename | Compound Grouping | Object ID | Notes |
|----------|-------------------|-----------|-------|
| `photo_001.jpg` | OFF | `photo-001` | Single object |
| `photo_002.jpg` | OFF | `photo-002` | Single object |
| `photo_001.jpg` | ON | `photo-001` | Part of compound |
| `photo_002.jpg` | ON | `photo-002` | Part of compound |
| `document.pdf` | OFF/ON | `docum` | No numeric suffix |
| `scan-page1.tif` | ON | `scan-1` | Extracted number |
| `scan-page2.tif` | ON | `scan-2` | Grouped together |

## Usage

1. Select an inputs folder using the **Browse...** button (contains your digital assets)
2. Select a working/outputs folder (to load settings)
3. Configure `group_compound_objects` in Function 0 if needed
4. Select **Function 1: Analyze Digital Assets & Generate Object IDs** from the dropdown
5. Click **Execute Function**
6. Review the analysis results in the dialog

## Output
The function displays:
- Total count of digital asset files found
- Compound grouping status (enabled/disabled)
- List of object IDs mapped to filenames
- When grouping is enabled, compound objects are visually grouped

### Example Output (Grouping DISABLED)
```
Found 4 digital asset file(s) in assets
Compound object grouping: DISABLED

• photo-001 → photo_001.jpg
• photo-002 → photo_002.jpg
• docum → document.pdf
• scan-1 → scan-page1.tif
```

### Example Output (Grouping ENABLED)
```
Found 4 digital asset file(s) in assets
Compound object grouping: ENABLED

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
