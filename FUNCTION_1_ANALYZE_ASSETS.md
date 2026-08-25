# Function 1: Analyze Digital Assets & Generate Standard DG Identifiers

## Purpose
Analyze selected digital asset files or scan a folder to generate unique standard DG identifiers for each file. Legacy identifiers follow the format `dg_<epoch_time>`. If `dg_prefix` is configured in Function 0, new identifiers follow `<prefix>_dg_<epoch_time>`.

## Automated Workflow
**NEW**: Enable `automatic_four` in Function 0 (App Settings) to automatically execute Functions 2, 3, and 4 after this function completes successfully. This creates a seamless workflow:

1. **Function 1**: Analyze assets and generate identifiers
2. **Function 2**: Export to CSV and upload to Azure (automatic)
3. **Function 3**: Generate derivatives and upload to Azure (automatic)
4. **Function 4**: Compare and merge metadata into core CSV (automatic)

The workflow stops immediately if any errors occur. The `automatic_four` setting automatically resets to `false` at the start of each new session, ensuring you consciously enable automation when needed.

## When to Use
Use this function to:
- Generate standard unique identifiers for digital assets
- Prepare asset metadata with guaranteed unique IDs
- Create identifiers that can be tracked across systems
- Ensure each file has a globally unique, timestamp-based identifier
- **NEW**: Trigger the complete workflow automatically (when `automatic_four` is enabled)

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
- **OHM-data mode**: When `process_OHM_data` is enabled in Function 0, select the project folder containing `OHM-data` (or select `OHM-data` itself). Function 1 ignores file selections and ordinary assets, recursively finds only `.mp3` files, and assigns each one a standard persistent DG identifier.

## How It Works
1. **First checks** if files are selected in the Files Selection area
   - If files are selected, analyzes only those files
2. **Falls back** to scanning the Inputs Folder if no files are selected
   - Scans all files in the folder matching supported types
3. **Generates unique identifiers** using the standard DG format: `dg_<epoch_time>`
   - Each file receives a permanent identifier
   - If `dg_prefix` is set in Function 0, the generated format becomes `<prefix>_dg_<epoch_time>`
   - IDs are reused if the file was previously processed
4. **Creates compound objects** (if grouping enabled)
   - Groups files by text similarity in filenames
   - Numbers are used for sequencing, not grouping
   - One untitled compound per folder; numeric sequences nest under it as `multiple` children
   - Each compound/multiple gets its own permanent identifier using the same legacy or prefixed format
   - Child files track their parent via `parentid` field

### OHM-data Processing

When `process_OHM_data` is `true`, Function 1 uses the selected Inputs Folder as the project root and looks for an `OHM-data` directory. It recursively processes only `.mp3` files beneath that directory, including files in interviewee subdirectories. Selected files and all non-MP3 assets are ignored, and compound grouping is disabled automatically. The resulting MP3 objects can then be exported by Function 2 and uploaded to Azure using their assigned identifiers.

Function 2 creates one standalone metadata record for each OHM MP3. OHM mode does not create compound objects or `parentid` relationships.

## Compound Object Grouping

### What Are Compound Objects?
A **compound object** is a logical grouping of related digital assets. The compound itself doesn't represent a single file, but rather the folder containing multiple child assets that belong together.

**Examples:**
- Multi-page documents scanned as separate images
- Photo sequences (e.g., panorama parts)
- Multi-file recordings (video + audio tracks)

**Key Characteristics:**
- One compound is created per **folder**, not per filename pattern - if a folder contains several distinct groups (e.g. multiple numbered sequences), they all share the same single compound parent
- The compound itself is untitled (no title/text base) since it may represent several unrelated groups
- Has its own unique identifier in either `dg_<epoch>` or `<prefix>_dg_<epoch>` form
- Serves as the parent for all groups found in that folder

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

5. **Compound Object Creation**: All groups (2+ files each) found within the same folder share ONE compound:
   - A single, untitled compound object is created per folder with its own permanent identifier
   - The compound is associated with the **folder path** containing the children
   - Compound ID is reused if the same folder is processed again
   - The compound ID becomes the `parentid` for its direct children (non-sequence groups and any `multiple` objects)

6. **Multiple Object Creation (numeric sequences)**: For each group within the folder that contains 2+ numbered files:
   - A `multiple` object is created and nested under the folder's compound (`parentid` = compound's objectid)
   - All numbered files in that sequence become children of this `multiple` object, not the compound directly
   - Unnumbered files in the same group become direct children of the compound - siblings of the `multiple` object, not its children
   - Groups that are NOT a numeric sequence (all-unnumbered, or only 1 numbered file) skip the `multiple` wrapper entirely - their files attach directly to the compound
   - The `multiple` ID is reused if the same group (folder + group base) is processed again, just like compound IDs

7. **Child Tracking**: Each child asset:
   - Has its own unique permanent identifier (objectid)
   - Has a `parentid` field pointing to its immediate parent (the compound, or the `multiple` object for sequenced files)
   - Retains its file path and other metadata

8. **Standalone Objects**: Files that don't match any group:
   - Prefix less than 3 characters (too short for matching)
   - Only file with that prefix (no group formed)
   - Have `parentid = None`
   - Are displayed as standalone objects

### Data Structure
```python
# Compound object (one per folder, untitled - may represent several groups)
{
  "objectid": "dg_1736712345",
  "type": "compound",
  "text_base": "",
  "display_text_base": "",
  "child_count": 5,
  "folder_path": "/Users/username/assets"
}

# Multiple object (nested under the folder's compound; one per numeric sequence)
{
  "objectid": "dg_1736712400",
  "parentid": "dg_1736712345",  # Points to the folder's compound
  "type": "multiple",
  "text_base": "photo",
  "display_text_base": "photo",
  "child_count": 3
}

# Child objects (have files)
{
  "objectid": "dg_1736712346",
  "parentid": "dg_1736712400",  # Points to the multiple object (or the compound if unnumbered)
  "type": "child",
  "filepath": "/Users/username/assets/photo_001.jpg",
  "filename": "photo_001.jpg"
}
```

### Compound and Multiple ID Persistence
Compound IDs are tracked using a key format: `{folder_path}::COMPOUND` (one per folder, no group/text base component).

Example: `/Users/username/assets::COMPOUND`

Multiple IDs (created only for groups with 2+ numbered files) use a key format that still includes the group's base: `{folder_path}::MULTIPLE::{text_base}`

Example: `/Users/username/assets::MULTIPLE::photo`

This ensures:
- The same folder always gets the same compound ID, and the same group within that folder always gets the same multiple ID
- Different folders always get different compound IDs
- Compound and multiple IDs persist across runs just like file IDs

### ID Assignment and Persistence
When you run Function 1:
1. The app checks if each file already has an assigned ID (stored in working folder settings using **full file path** as key)
2. If an ID exists for that file path, it reuses that ID - **IDs never change**
3. If a file is new, it generates a new identifier in either `dg_<epoch>` form or `<prefix>_dg_<epoch>` form
4. The mapping (full path → ID) is saved to `dart_settings.json` in the working folder
5. Results show: "X new, Y reused" to indicate which IDs were newly generated vs. retrieved

### Legacy and Prefixed ID Cutoff

- Epoch cutoff for this feature: `1782237851`
- IDs with epoch values earlier than `1782237851` are legacy-era IDs and will appear as `dg_<epoch>`
- IDs created at or after `1782237851` may still appear as `dg_<epoch>` if `dg_prefix` is blank
- When `dg_prefix` is configured, new IDs created at or after `1782237851` appear as `<prefix>_dg_<epoch>`

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
5. Choose one of the result actions:
   - **Close**: Accepts the analysis, saves updated ID mappings, and advances workflow tracking
   - **Cancel**: Discards the latest Function 1 analysis results, does not save new mappings, and does not advance the suggested Next function

### Option 2: Scan Entire Folder
1. Leave Files Selection empty
2. Select an inputs folder using the **Inputs Folder** → **Browse...** button
3. Select **Function 1: Analyze Digital Assets & Generate Standard DG Identifiers** from the dropdown
4. Click **Execute Function**
5. Review the analysis results in the dialog
6. Choose **Close** to keep results or **Cancel** to back out the latest analysis without saving

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

📦 COMPOUND: dg_1736712345 ('untitled' - 3 children)
    Folder: /Users/username/assets
    ▣ MULTIPLE: dg_1736712400 ('photo' - 3 sequenced children)
        ↳ dg_1736712346 [1] → photo_001.jpg
        ↳ dg_1736712347 [2] → photo_002.jpg
        ↳ dg_1736712348 [3] → photo_003.jpg

📦 COMPOUND: dg_1736712349 ('untitled' - 2 children)
    Folder: /Users/username/documents
    ▣ MULTIPLE: dg_1736712401 ('scan' - 2 sequenced children)
        ↳ dg_1736712350 [1] → scan_page_1.tif
        ↳ dg_1736712351 [2] → scan_page_2.tif

📄 STANDALONE OBJECTS:
• dg_1736712352 → poster.pdf
```

In this example:
- 2 compound objects created, one per folder (/assets and /documents) - each untitled since a compound represents the whole folder, not a single group
- Each compound shows its associated folder path
- Since each folder's group has 2+ numbered files, a `multiple` object is nested under that folder's compound, and the numbered files become its children instead of the compound's direct children
- If a folder had multiple distinct sequences (e.g. "photo" and "scan" both in /assets), they would share the SAME compound, each as its own sibling `multiple` object
- 1 standalone object (poster.pdf doesn't match any group)
- Each compound has its own ID; each `multiple` object's parentid points to its folder's compound, and sequenced children's parentid points to the `multiple` object

## Notes
- Only files with recognized digital asset extensions are analyzed
- Object IDs are generated automatically and cannot be manually specified
- When compound grouping is DISABLED, all files are standalone with no parentid
- When compound grouping is ENABLED, files are analyzed for text-based grouping
- One untitled compound object is created per folder, even if that folder contains several distinct groups
- Compound IDs persist: same folder always produces the same compound ID
- Groups with 2+ numbered files get their own nested `multiple` object (sibling to other groups in the same folder); its ID persists the same way, keyed by folder + group base
- Non-sequence groups (all-unnumbered, or only 1 numbered file) attach directly to the compound, without a `multiple` wrapper
- Children track their immediate parent via the `parentid` field (the `multiple` object for sequenced files, or the compound otherwise)
- Results are displayed in the dialog but not automatically saved (use other functions to export)
