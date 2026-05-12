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
- **Optional**: Working/Outputs folder (to load compound grouping setting)

## How It Works
1. **First checks** if files are selected in the Files Selection area
   - If files are selected, analyzes only those files
2. **Falls back** to scanning the Inputs Folder if no files are selected
   - Scans all files in the folder matching supported types
3. **Generates unique identifiers** using the standard DG format: `dg_<epoch_time>`
   - Each file receives a permanent identifier
   - IDs are reused if the file was previously processed
4. **Creates compound objects** (if grouping enabled)
   - Groups files by text similarity in filenames
   - Numbers are used for sequencing, not grouping
   - Each compound gets its own `dg_<epoch>` identifier
   - Child files track their parent via `parentid` field

## Compound Object Grouping

### What Are Compound Objects?
A **compound object** is a logical grouping of related digital assets. The compound itself doesn't represent a single file, but rather the folder containing multiple child assets that belong together.

**Examples:**
- Multi-page documents scanned as separate images
- Photo sequences (e.g., panorama parts)
- Multi-file recordings (video + audio tracks)

**Key Characteristics:**
- Associated with the folder path where children are located
- Has its own unique `dg_<epoch>` identifier
- Serves as the parent for all child assets in the group

### How Grouping Works
When `group_compound_objects` is enabled in Function 0:

1. **Intelligent Pattern Analysis**: Files are analyzed in three passes to find common patterns:
   
   **First Pass - Extract Base Patterns:**
   - Files with trailing numbers: extract everything before last number as prefix
   - `100 Nights-1.jpg` → prefix: "100 nights", sequence: 1
   - `Wit 042.JPG` → prefix: "wit", sequence: 42
   - `AnnaChristie-F14-23.pdf` → prefix: "annachristie-f14", sequence: 23
   
   **Second Pass - Match Against Numbered Files:**
   - For files without trailing numbers, check if they start with any known prefix from Pass 1
   - Uses longest matching prefix (most specific match)
   - `Wit Poster.jpg` starts with "wit" → uses prefix "wit"
   - `AnnaChristie-F14-Poster.pdf` starts with "annachristie-f14" → uses that prefix
   
   **Third Pass - Find Common Patterns Among Remaining Files:**
   - For unnumbered files that didn't match any numbered prefix
   - Extracts common base by removing last word after separator
   - `Traditions and Encounters - Poster.pdf` → base: "traditions and encounters"
   - `Traditions and Encounters_Program.pdf` → base: "traditions and encounters"
   - Automatically normalizes trailing separators and extra spaces for accurate matching
   - If 2+ files share the same base (3+ chars), they're grouped together
   
   **Matching Rules:**
   - Prefixes must be 3+ characters to qualify for grouping (weighted matching)
   - Flexible separators: space, underscore, hyphen between prefix and suffix
   - Case-insensitive comparison
   - Validates separator after prefix (prevents false substring matches)

2. **Sequence Detection**: For numbered files, analyzes if numbers form a sequence:
   - Calculates average gap and maximum gap between numbers
   - Sequential if: average gap ≤ 2.0 and max gap ≤ 5
   - Tolerates missing numbers (e.g., 1, 2, 3, 5, 6 is still sequential - missing 4)
   - **Zero-Padding**: Calculates padding width from max number (20 → 2 digits)
   - Reports details: number range, gaps, missing values, padding width

3. **Detailed Reporting**: Logs comprehensive analysis for each group:
   - Number of files (numbered vs unnumbered)
   - Sequence analysis (range, gaps, patterns)
   - Zero-padding recommendations
   - Grouping decision with rationale
   - Missing numbers or irregularities

4. **Smart Display**: Results show files in proper order:
   - Children sorted by sequence number (numbered first, then unnumbered)
   - Sequence numbers displayed with zero-padding: `[01]`, `[02]`, `[10]`
   - Makes visual inspection easier and confirms proper grouping

5. **Compound Object Creation**: For each group with 2+ files:
   - A compound object is created with its own `dg_<epoch>` identifier
   - The compound is associated with the **folder path** containing the children
   - Compound ID is reused if the same group (folder + text base) is processed again
   - The compound ID becomes the `parentid` for all children

6. **Child Tracking**: Each child asset:
   - Has its own unique `dg_<epoch>` identifier (objectid)
   - Has a `parentid` field pointing to the compound object
   - Retains its file path and other metadata

7. **Standalone Objects**: Files that don't match any group:
   - Prefix less than 3 characters (too short for matching)
   - Only file with that prefix (no group formed)
   - Have `parentid = None`
   - Are displayed as standalone objects

### Data Structure
```python
# Compound object (associated with folder path)
{
  "objectid": "dg_1736712345",
  "type": "compound",
  "text_base": "photo",
  "child_count": 3,
  "folder_path": "/Users/username/assets"
}

# Child objects (have files)
{
  "objectid": "dg_1736712346",
  "parentid": "dg_1736712345",  # Points to compound
  "type": "child",
  "filepath": "/Users/username/assets/photo_001.jpg",
  "filename": "photo_001.jpg"
}
```

### Compound ID Persistence
Compound IDs are tracked using a key format: `{folder_path}::COMPOUND::{text_base}`

Example: `/Users/username/assets::COMPOUND::photo`

This ensures:
- Same group in same folder always gets the same compound ID
- Different folders can have compounds with same text base (different IDs)
- Compound IDs persist across runs just like file IDs

### ID Assignment and Persistence
When you run Function 1:
1. The app checks if each file already has an assigned ID (stored in working folder settings using **full file path** as key)
2. If an ID exists for that file path, it reuses that ID - **IDs never change**
3. If a file is new, it generates a new `dg_<epoch>` identifier
4. The mapping (full path → ID) is saved to `dart_settings.json` in the working folder
5. Results show: "X new, Y reused" to indicate which IDs were newly generated vs. retrieved

This ensures that once a file receives an identifier, running the function again will always return the same ID for that file. Using full paths prevents collisions between files with the same name in different directories.

### Grouping Analysis Example
When analyzing files with compound grouping enabled, detailed analysis is logged:

```
[GROUP ANALYSIS] Found 3 prefix groups (3+ char prefixes)
[PREFIX MATCHING] Found 2 numbered prefixes: ['100 nights', 'wit']
[PREFIX MATCH] 'Wit Poster.jpg' matched prefix 'wit' (common with numbered files)
[PREFIX MATCH] 'Wit Program.pdf' matched prefix 'wit' (common with numbered files)

[GROUP: 'wit'] 100 files (98 numbered, 2 unnumbered)
  ✓ SEQUENTIAL pattern detected: range 1-100, avg gap 1.0, max gap 2
  → Sequence numbers will be zero-padded to 3 digits (e.g., 001, 100)
  ℹ Note: 2 gap(s) in sequence (e.g., missing numbers)
  ➤ DECISION: Creating compound (common prefix 'wit', 100 files)

[GROUP: '100 nights'] 20 files (20 numbered, 0 unnumbered)
  ✓ SEQUENTIAL pattern detected: range 1-20, avg gap 1.0, max gap 1
  → Sequence numbers will be zero-padded to 2 digits (e.g., 01, 20)
  ➤ DECISION: Creating compound (common prefix '100 nights', 20 files)

[GROUP: 'annachristie-f14'] 2 files (0 numbered, 2 unnumbered)
  • All files unnumbered but share common prefix (3+ chars: 'annachristie-f14')
  ➤ DECISION: Creating compound (common prefix 'annachristie-f14', 2 files)
```

This helps you understand:
- How files were grouped and why
- Whether sequences are complete or have gaps
- Which files are numbered vs descriptive (poster, program, etc.)

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
Found 6 digital asset file(s) from selected files
Identifiers: 6 new, 0 reused (IDs never change once assigned)
Compound object grouping: ENABLED
Total: 2 compound objects, 6 file objects

📦 COMPOUND: dg_1736712345 ('photo' - 3 children)
    Folder: /Users/username/assets
    ↳ dg_1736712346 → photo_001.jpg
    ↳ dg_1736712347 → photo_002.jpg
    ↳ dg_1736712348 → photo_003.jpg

📦 COMPOUND: dg_1736712349 ('scan' - 2 children)
    Folder: /Users/username/documents
    ↳ dg_1736712350 → scan_page_1.tif
    ↳ dg_1736712351 → scan_page_2.tif

📄 STANDALONE OBJECTS:
• dg_1736712352 → poster.pdf
```

In this example:
- 2 compound objects created ("photo" group in /assets, "scan" group in /documents)
- Each compound shows its associated folder path
- 1 standalone object (poster.pdf doesn't match any group)
- Each compound has its own ID that serves as the parentid for its children

## Notes
- Only files with recognized digital asset extensions are analyzed
- Object IDs are generated automatically and cannot be manually specified
- When compound grouping is DISABLED, all files are standalone with no parentid
- When compound grouping is ENABLED, files are analyzed for text-based grouping
- Compound objects are associated with the folder containing their children
- Compound IDs persist: same folder + text base always produces same compound ID
- Children track their parent via the `parentid` field
- Results are displayed in the dialog but not automatically saved (use other functions to export)
