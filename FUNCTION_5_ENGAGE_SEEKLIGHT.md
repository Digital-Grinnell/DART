# Seeklight Workflow Sans API - Clickity, Click, Click

Since Seeklight does not yet have an API for integration with apps like DART, you, the user, will need to engage Seeklight "manually" and click through the user interface.  

The process is essentially designed for you to select one digital object file, upload that file to Seeklight, engage Seeklight to generate metadata, download the new metadata record as a .xlsx file, save that file as a CSV, and return to DART where you will select the new CSV file for transformation.  Once complete you may engage Function 6 -- Compare and Merge Seeklight CSV -- to compare and merge elements of the new Seeklight metadata with your project's corresponding core metadata CSV record.  

The manual portion of the workflow looks like this:  

1) Launch the web browser and navigate to https://stewardship.jstor.org or https://stewardship.jstor.org/#/dashboard.   
2) Enter authorization credentials if needed to land at https://stewardship.jstor.org/#/generate-metadata or go there directly.  
3) Select `Upload Media...` panel.  
4) Click `Browse Files` link.  
5) Select one or more files to upload.  
6) Optionally enter context to assist the processor.  
7) Click the `Upload` button.  
8) You are given two choices, select `Create new project...` and give it a descriptive name.  
9) Click the `Generate Metadata` button.  
10) ...the generation should be running until complete.  
11) Click back into the `Metadata Records` tab.  
12) Select items with newest at the top.  
13) Find the `...` menu and pick it.  
14) Click `Download Metadata` and the generated data should open in an Excel file.
15) Do with the metadata as you wish.  If downloaded it will save as a .xlsx file.  
16) In Excel, be sure to select `Save As` to save a copy of the .xlsx data as a UTF-8 CSV file (one of several options).  Remember the path to the new CSV file OR make sure you save it in your DART working directory to make it easy to find for the compare and merge operation in Function 6.  

## Transform Seeklight Metadata to DART Format

Once you have downloaded the Seeklight-generated metadata:

1) **Export to CSV**: Open the .xlsx file in Excel and export/save it as a CSV file.

2) **Run Function 5**: In DART, click Function 5 button.

3) **Select CSV**: Click "Select Seeklight CSV File..." and navigate to your exported CSV.

4) **Transform**: The transformation will:
   - Read the Seeklight metadata
   - Map Seeklight fields to DART core columns using `seeklight_mapping_template.json`
   - Handle Seeklight column names with or without bracketed numbers (e.g., `Title[3101377]` or `Title`)
   - **Leave objectid empty** (Seeklight generates new metadata without objectids)
   - Set filename from Seeklight data
   - Create a timestamped CSV: `DART_seeklight_transformed_YYYYMMDD_HHMMSS.csv`
   - Save to your `.DART-working-directory` folder

5) **Output**: Results show:
   - Number of rows processed
   - Confirmation that objectid fields are empty
   - Output filename and location
   - Reminder to use Function 6 for comparing/merging with core metadata

### Customizing Field Mapping

Edit `seeklight_mapping_template.json` in the DART folder to customize how Seeklight fields map to your core metadata columns:

```json
{
  "field_mapping": {
    "Title": "dc_title",
    "Description": "dc_description",
    "Creator": "creator"
  },
  "default_values": {
    "dc_language": "eng"
  },
  "filename_column": "Filename"
}
```

- **field_mapping**: Maps Seeklight column names (left) to your core CSV column names (right)
  - **Note**: Seeklight columns may have bracketed numbers like `Title[3101377]`. The mapping handles both `Title` and `Title[3101377]` automatically - you only need to specify the base name without brackets.
- **default_values**: Sets default values for columns not provided by Seeklight
- **filename_column**: Identifies which Seeklight column contains filenames
- **objectid handling**: The transformation **always leaves objectid empty** because Seeklight generates new metadata. Use Function 6 to compare and merge with existing core metadata using filename-based matching.
