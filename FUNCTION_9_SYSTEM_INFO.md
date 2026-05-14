# Function 9: System Information

## Purpose
Display information about the system running the application.

## When to Use
Use this function when you want to:
- Check system configuration
- Verify Python version
- Identify the current user and hostname
- Find the data folder location

## Requirements
- None (this function has no dependencies on directories or files)

## Usage

1. Select **Function 9: System Information** from the dropdown
2. Click **Execute Function**
3. A dialog will display system information

## Output
The function displays:
- **Hostname**: Computer network name
- **OS**: Operating system and version
- **Machine**: Hardware architecture (e.g., x86_64, arm64)
- **Python**: Python interpreter version
- **User**: Current username
- **Data Folder**: Location where DART stores logs and settings

## Example Output
```
System Information:

• Hostname: MacBook-Pro.local
• OS: Darwin 23.1.0
• Machine: arm64
• Python: 3.11.5
• User: jsmith
• Data Folder: /Users/jsmith/DART-data
```

## Notes
- This function demonstrates gathering system information using Python's standard library
- No external dependencies required
- Useful for troubleshooting or support requests
- Data folder is where logs and persistent.json are stored
