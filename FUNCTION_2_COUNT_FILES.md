# Function 2: Count Files by Extension

## Purpose
Analyze the inputs folder and count files grouped by their file extension.

## When to Use
Use this function when you want to:
- Get an overview of file types in a folder
- Identify the most common file types
- Verify file organization

## Requirements
- Inputs folder must be selected

## Usage

1. Select an inputs folder using the **Browse...** button
2. Select **Function 2: Example Function - Count Files** from the dropdown
3. Click **Execute Function**
4. A dialog will display file counts organized by extension

## Output
The function displays:
- File extensions found
- Count of files for each extension
- Results sorted by count (highest to lowest)
- Message if no files are found

## Example Output
```
File count by extension in Documents:

• .txt: 15
• .pdf: 8
• .png: 5
• .md: 3
• (no extension): 1
```

## Notes
- Extensions are case-insensitive (.TXT and .txt are counted together)
- Files without extensions are listed as "(no extension)"
- Only files are counted (subdirectories are excluded)
- Results are sorted by count, showing most common types first
