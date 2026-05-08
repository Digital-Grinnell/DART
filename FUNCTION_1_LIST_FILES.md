# Function 1: List Files

## Purpose
List all files in the selected input directory with their names.

## When to Use
Use this function when you want to see what files exist in a directory without opening a file manager.

## Requirements
- Input directory must be selected

## Usage

1. Select an input directory using the **Browse...** button
2. Select **Function 1: Example Function - List Files** from the dropdown
3. Click **Execute Function**
4. A dialog will display all files found in the directory

## Output
The function displays:
- Total count of files
- Alphabetically sorted list of filenames
- Message if no files are found

## Example Output
```
Found 5 file(s) in Documents:

• document1.txt
• image.png
• notes.md
• report.pdf
• spreadsheet.xlsx
```

## Notes
- Only files are listed (subdirectories are excluded)
- Files are sorted alphabetically
- The list is displayed in a dialog window
