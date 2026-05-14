# Function 3: Generate Small & Thumbnail Derivatives

## Purpose
Generate small and thumbnail derivative images from your original files and upload them to Azure Blob Storage with automatic URL population in your CSV metadata file.

## When to Use
Use this function after Function 2 (Export Assets to CSV) when you want to:
- Create web-optimized derivative images for CollectionBuilder
- Generate small images (max 800x800px) for detail pages
- Generate thumbnail images (max 400x400px) for browse/grid views
- Upload derivatives to Azure cloud storage
- Automatically populate `image_small` and `image_thumb` URL columns in your CSV

## Requirements
- **Working/Outputs folder** must be set
- **Azure Blob Storage** must be configured in Function 0 settings
  - Valid `azure_blob_storage_path` (contains `/objs/` folder)
  - Valid `azure_connection_string`
- **CSV export from Function 2** must exist in working directory
- **Original source files** must be accessible (image files only)

## Workflow

1. Run **Function 2: Export Assets to CSV** to create your metadata CSV

2. Configure **Azure Blob Storage** in Function 0 if not already done

3. Select **Function 3: Generate Small & Thumbnail Derivatives**

4. Click **Execute Function**

5. DART processes each image file:
   - Generates small derivative (800x800px max, maintains aspect ratio)
   - Generates thumbnail derivative (400x400px max, maintains aspect ratio)
   - Uploads small to `/smalls/` Azure folder with `_SMALL` suffix
   - Uploads thumbnail to `/thumbs/` Azure folder with `_TN` suffix
   - Populates `image_small` and `image_thumb` columns with Azure URLs

6. A new timestamped CSV is created with the added columns

## What Gets Generated

### Small Derivatives
- **Purpose**: Detail page images in CollectionBuilder
- **Filename**: `dg_<epoch>_SMALL.jpg`
- **Size**: Maximum 800x800 pixels (maintains aspect ratio)
- **Quality**: 85% JPEG compression
- **Location**: `/smalls/` folder in Azure (parallel to `/objs/`)
- **CSV Column**: `image_small`
- **URL Format**: `https://account.blob.core.windows.net/container/smalls/path/dg_1234567890_SMALL.jpg`

### Thumbnail Derivatives
- **Purpose**: Browse grid and list view images in CollectionBuilder
- **Filename**: `dg_<epoch>_TN.jpg`
- **Size**: Maximum 400x400 pixels (maintains aspect ratio)
- **Quality**: 85% JPEG compression
- **Location**: `/thumbs/` folder in Azure (parallel to `/objs/`)
- **CSV Column**: `image_thumb`
- **URL Format**: `https://account.blob.core.windows.net/container/thumbs/path/dg_1234567890_TN.jpg`

## Supported Image Formats

The following image formats are processed:
- **JPEG**: `.jpg`, `.jpeg`
- **PNG**: `.png` (converted to JPEG with white background for transparency)
- **GIF**: `.gif`
- **TIFF**: `.tif`, `.tiff`
- **BMP**: `.bmp`
- **WebP**: `.webp`

**Note**: Only image files are processed. PDFs, videos, and audio files are skipped. Rows in the CSV without filenames (like compound parent objects) are also skipped.

## Image Processing Details

### Aspect Ratio Preservation
- Derivatives maintain the original image's aspect ratio
- Images are never stretched or distorted
- Maximum dimensions (800x800 or 400x400) are constraints
- Actual size depends on original aspect ratio

Examples:
- Landscape photo (1600x1200) → Small: 800x600, Thumbnail: 400x300
- Portrait photo (1200x1600) → Small: 600x800, Thumbnail: 300x400
- Square photo (2000x2000) → Small: 800x800, Thumbnail: 400x400

### EXIF Orientation Handling
- Automatically rotates images based on EXIF orientation data
- Ensures derivatives display correctly regardless of how camera captured them
- Common with smartphone photos taken in portrait mode

### Transparency Handling
- PNG and GIF images with transparency are converted to JPEG
- Transparent areas are replaced with white background
- Ensures consistent appearance and smaller file sizes

### Quality Optimization
- JPEG quality set to 85% (good balance between quality and file size)
- LANCZOS resampling for high-quality resizing
- Optimized JPEG encoding enabled

## Azure Folder Structure

Function 3 uses the same container and base path as Function 2 but uploads to parallel folders:

**If your azure_blob_storage_path is**: `objs/TDPS_archive`

**Function 3 will upload to**:
- Small derivatives: `smalls/TDPS_archive`
- Thumbnails: `thumbs/TDPS_archive`

### Automatic Container Creation

Function 3 automatically manages Azure container creation:
- **Checks for container existence**: Verifies both `smalls` and `thumbs` containers exist
- **Creates containers as needed**: No manual Azure Portal setup required
- **Handles concurrent creation**: Gracefully handles race conditions
- **Logs container status**: Shows which containers existed vs. were created

This means you can point to a new Azure path and Function 3 will set up the folder structure automatically.

Example full structure:
```
https://collectionbuilder.blob.core.windows.net/
  ├── objs/TDPS_archive/
  │   ├── dg_1715614222.jpg (original from Function 2)
  │   ├── dg_1715614223.jpg
  │   └── dg_1715614224.jpg
  ├── smalls/TDPS_archive/
  │   ├── dg_1715614222_SMALL.jpg (generated by Function 3)
  │   ├── dg_1715614223_SMALL.jpg
  │   └── dg_1715614224_SMALL.jpg
  └── thumbs/TDPS_archive/
      ├── dg_1715614222_TN.jpg (generated by Function 3)
      ├── dg_1715614223_TN.jpg
      └── dg_1715614224_TN.jpg
```

## Smart Processing Features

### Skip Existing Derivatives

Function 3 intelligently checks Azure before generating new derivatives:

1. **Checks Azure for existing files** before processing each image
   - Looks for both `_SMALL.jpg` and `_TN.jpg` files in Azure
   - Uses Azure Blob Storage API for fast existence checks

2. **Skips generation when both derivatives exist**
   - No unnecessary image processing
   - No redundant Azure uploads
   - Saves processing time on large collections

3. **Builds URLs from existing files**
   - Populates `image_small` and `image_thumb` columns from existing Azure files
   - Includes skipped files in success counts
   - Logs skipped files as "⏩ Derivatives already exist in Azure - skipping"

4. **Re-run safe**
   - You can safely re-run Function 3 on the same CSV
   - Only missing derivatives are generated
   - Useful for interrupted processes or partial failures

**Benefits**:
- Faster re-runs when only some files need processing
- Safe to run after Azure issues or interruptions
- No duplicate storage costs from re-uploading
- Supports incremental updates to collections

## Output

**Filename format**: `dart_export_with_derivatives_YYYYMMDD_HHMMSS.csv`

**Example**: `dart_export_with_derivatives_20260513_204500.csv`

**Location**: Your working/outputs folder

**Added Columns**:
- `image_small` - Azure URL for small derivative
- `image_thumb` - Azure URL for thumbnail derivative

### Results Dialog

After processing completes, Function 3 shows a detailed results dialog with:

- **Total CSV rows processed**
- **Count of image files processed**
- **Count of rows skipped** with clickable **"see log for details"** link
- **Small images**: Success and failure counts
- **Thumbnails**: Success and failure counts
- **Output CSV filename and location**

**Clickable Log Link**: The "see log for details" text is a clickable button that opens the complete log file in a read-only popup window. This allows you to:
- Review which specific files were skipped and why
- See detailed error messages for any failures
- Verify Azure upload confirmations
- Check processing timestamps
- Copy log content for troubleshooting

The log file is also saved to `logfiles/` in your working directory for later review.

## Example Updated CSV

**Before Function 3** (output from Function 2):
```csv
objectid,filename,title,display_template,object_location
dg_1715614222,photo_001.jpg,,image,https://account.blob.core.windows.net/objs/collection/dg_1715614222.jpg
dg_1715614223,photo_002.jpg,,image,https://account.blob.core.windows.net/objs/collection/dg_1715614223.jpg
```

**After Function 3**:
```csv
objectid,filename,title,display_template,object_location,image_small,image_thumb
dg_1715614222,photo_001.jpg,,image,https://account.blob.core.windows.net/objs/collection/dg_1715614222.jpg,https://account.blob.core.windows.net/smalls/collection/dg_1715614222_SMALL.jpg,https://account.blob.core.windows.net/thumbs/collection/dg_1715614222_TN.jpg
dg_1715614223,photo_002.jpg,,image,https://account.blob.core.windows.net/objs/collection/dg_1715614223.jpg,https://account.blob.core.windows.net/smalls/collection/dg_1715614223_SMALL.jpg,https://account.blob.core.windows.net/thumbs/collection/dg_1715614223_TN.jpg
```

## Kill Switch - Emergency Stop

Function 3 supports the kill switch for stopping long-running derivative generation operations:

1. Click the **🛑 Kill Switch** button during processing
2. Current file processing completes
3. All remaining files are skipped
4. CSV is saved with partial results (derivatives generated before stop)

The kill switch is useful when:
- Processing is taking longer than expected
- You need to make changes before continuing
- Network issues are causing upload failures
- You want to verify results on a subset before processing all files

## Integration with Other Functions

- **Function 2** creates the initial CSV with original file metadata
- **Function 3** enhances it with derivative URLs
- Future functions can further enrich the same CSV with additional metadata
- The CSV workflow supports incremental enhancement across multiple functions

## Processing Details

### What Gets Processed
- ✓ Image files with valid extensions (jpg, png, gif, tif, bmp, webp)
- ✓ Rows with both objectid and filename populated
- ✓ Files where source can be located

### What Gets Skipped
- ⊘ Rows without filenames (compound parent objects)
- ⊘ Non-image files (PDF, video, audio, archives)
- ⊘ Files that can't be found on disk
- ⊘ Rows without object IDs

### Temporary Files
- Derivatives are generated in `temp_derivatives/` folder in your working directory
- Temporary files are automatically cleaned up after upload
- If process is interrupted, you can safely delete the `temp_derivatives/` folder

## Error Handling

### Common Errors

**"No CSV exports found. Run Function 2 first."**
- Cause: No `dart_export_*.csv` files in working directory
- Fix: Run Function 2 to create initial CSV

**"Azure Blob Storage not configured."**
- Cause: Missing azure_blob_storage_path or azure_connection_string in settings
- Fix: Configure Azure settings in Function 0

**"Source file not found: filename.jpg"**
- Cause: Original file has been moved or deleted
- Fix: Ensure original files are in their original locations from Function 2

**Upload Failed Errors**
- Cause: Network issues, invalid Azure credentials, or path problems
- Fix: Check Azure connection string, verify network connectivity, ensure paths are correct

### Partial Completion
If Function 3 fails or is stopped mid-process:
- Derivatives successfully generated before the failure are preserved in Azure
- The updated CSV contains URLs for completed derivatives only
- Failed items have empty image_small and image_thumb columns
- You can re-run Function 3 to process remaining items (already-uploaded derivatives may be overwritten)

## Performance Notes

- **Processing Time**: Depends on image sizes and count
  - Small images (< 1MB): ~1-2 seconds per file
  - Large images (> 5MB): ~3-5 seconds per file
  - Plus network upload time to Azure
- **Network Usage**: Uploads approximately:
  - Small derivative: 50-200 KB per image
  - Thumbnail: 20-80 KB per image
- **Disk Space**: Temporary derivatives are stored during processing then deleted
- **Concurrent Processing**: Files are processed sequentially (no parallel processing)

## Tips

- Run Function 2 first to ensure all original files are uploaded
- Verify Azure configuration before starting large batches
- Test with a small sample CSV first
- Use the kill switch if you need to stop and verify results
- Keep original source files accessible during processing
- Check log files for detailed error information if issues occur

## CollectionBuilder Integration

The `image_small` and `image_thumb` columns are recognized by CollectionBuilder:
- **image_small**: Used on item detail pages
- **image_thumb**: Used in browse grids and card layouts
- Derivatives provide faster page loads and better user experience
- Original files (`object_location`) can still be downloaded by users

## Notes

- Only the most recent CSV from Function 2 is processed
- The original CSV is not modified; a new timestamped CSV is created
- Derivatives use lossy JPEG compression for optimal web delivery
- All image formats are converted to JPEG for consistency
- File sizes are optimized for web viewing while maintaining good quality
- The same CSV can be processed multiple times (derivatives will be regenerated/overwritten)
