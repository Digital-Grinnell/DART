# DART Best Practices & Filename Conventions

**Core Mission:** DART is focused on providing a valid import/ingest-compatible CSV metadata file using groups of digital objects and their original filenames as the "source of truth". Each object is given a unique Digital.Grinnell identifier and DART helps maintain those while directing files to proper long-term/preservation storage.

This guide helps you get the best results from DART's intelligent compound object grouping and other features.  

---

## Table of Contents
1. [Compound Grouping Setting](#compound-grouping-setting)
2. [How Compound Grouping Works](#how-compound-grouping-works)
3. [Filename Convention Guidelines](#filename-convention-guidelines)
4. [Common Scenarios](#common-scenarios)
5. [Troubleshooting](#troubleshooting)

---

## Compound Grouping Setting

**Compound grouping must be enabled in Function 0 (App Settings)** to group related files together. Look for the checkbox labeled "Group compound objects" in the settings.

**When ENABLED:** DART analyzes filename patterns and groups related files (e.g., "Wit 001.jpg", "Wit 002.jpg", "Wit Poster.jpg") into a single compound object with one parent ID and multiple children. This is ideal for collections where multiple files represent different views, pages, or components of the same intellectual object.

**When DISABLED:** Every file becomes a standalone object with its own unique identifier. Use this mode when each file represents a completely independent object with no relationship to other files, or when you want full control over grouping decisions.

---

## How Compound Grouping Works

DART's compound grouping, when **enabled**, uses a **three-pass intelligent algorithm**:

### Pass 1: Learn Patterns from Numbered Files
The app first looks for files with trailing sequence numbers and extracts their base prefix:
- `Wit 001.jpg` → learns prefix **"wit"**
- `100 Nights-15.jpg` → learns prefix **"100 nights"**
- `AnnaChristie-F14-23.pdf` → learns prefix **"annachristie-f14"**

### Pass 2: Match Related Files Against Numbered Prefixes
For files without trailing numbers, the app checks if they **start with** any known prefix:
- `Wit Poster.jpg` starts with "wit" → **matched!**
- `100 Nights - Cover.pdf` starts with "100 nights" → **matched!**
- `AnnaChristie-F14-Program.pdf` starts with "annachristie-f14" → **matched!**

### Pass 3: Find Common Patterns Among Remaining Files
For files that didn't match any numbered prefix, the app looks for common base patterns:
- `Traditions and Encounters - Poster.pdf` → extracts base **"traditions and encounters"**
- `Traditions and Encounters_Program.pdf` → extracts base **"traditions and encounters"**
- Both share the same base (3+ chars) → **grouped together!**

This works by removing the last word after a separator (space, underscore, hyphen) and checking if other files share that base.

### Key Insight
**The app now groups files based on what they have in common, even without numbered files!**

---

## Filename Convention Guidelines

### ✅ Best Practices

#### 1. **Use Consistent Base Names**
All related files should start with the exact same text (case-insensitive).

**Good:**
```
Wit 001.jpg
Wit 002.jpg
Wit Poster.jpg
Wit Program.pdf
```
All start with "Wit" → groups perfectly!

**Good:**
```
2013_Exhibit_001.tif
2013_Exhibit_002.tif
2013_Exhibit_Catalog.pdf
2013_Exhibit_Invitation.pdf
```
All start with "2013_Exhibit" → groups perfectly!

#### 2. **Use Clear Separators**
When adding descriptive terms after the base name, use clear separators (space, hyphen, underscore):

**Good:**
```
Project Alpha - Poster.pdf
Project Alpha - Program.pdf
Project Alpha_Cover.jpg
```

**Better (with numbered files):**
```
Project Alpha 01.jpg
Project Alpha 02.jpg
Project Alpha - Poster.pdf
Project Alpha - Program.pdf
```

#### 3. **Number Sequences at the End**
Put sequence numbers at the **end** of filenames:

**Good:**
```
photo_001.jpg
photo_002.jpg
photo_album.pdf
```

**Avoid:**
```
001_photo.jpg  ← Number at start doesn't define sequence
photo001middle_text.jpg  ← Number in middle is ambiguous
```

#### 4. **Use Zero-Padding for Sequences**
While not required (DART adds zero-padding in display), using zero-padded numbers in filenames helps with sorting:

**Good:**
```
scan_001.tif
scan_010.tif
scan_100.tif
```

**Works but less ideal:**
```
scan_1.tif
scan_10.tif
scan_100.tif
```

#### 5. **Minimum Prefix Length: 3 Characters**
DART requires at least 3 characters for the common prefix to avoid false matches:

**Good:**
```
Wit 001.jpg  ← "wit" is 3 chars
Art 001.jpg  ← "art" is 3 chars
```

**Won't Group:**
```
AB 001.jpg   ← "ab" is only 2 chars
XY 002.jpg   ← "xy" is only 2 chars
```

---

## Common Scenarios

### Scenario 1: Numbered Sequence + Supplementary Files

**Your Files:**
```
Wit 001.JPG
Wit 002.JPG
...
Wit 100.JPG
Wit Poster.jpg
Wit Program.pdf
```

**Result:** ✅ All grouped in one compound
- The numbered files establish "wit" as the prefix
- Poster and Program match that prefix
- 100 files in compound: 98 numbered + Poster + Program

---

### Scenario 2: Only Supplementary Files (No Numbered Sequence)

**Your Files:**
```
Traditions and Encounters - Poster.pdf
Traditions and Encounters_Program.pdf
```

**Result:** ✅ Grouped in one compound!
- Pass 3 extracts common base "traditions and encounters" from both files
- Both files grouped together even without numbered files
- Requires: separator before last word (space, underscore, or hyphen)
- Algorithm automatically normalizes trailing separators and extra spaces

**Previous Behavior:** These would have been standalone objects.

**Even Better with a numbered file:**
```
Traditions and Encounters 01.pdf  ← Establishes base prefix in Pass 1
Traditions and Encounters - Poster.pdf
Traditions and Encounters_Program.pdf
```
Result: ✅ All three grouped (Pass 1 establishes pattern)

---

### Scenario 3: Multiple Projects in Same Folder

**Your Files:**
```
Project A 01.jpg
Project A 02.jpg
Project A Poster.pdf
Project B 01.jpg
Project B 02.jpg
Project B Poster.pdf
```

**Result:** ✅ Two compounds
- Compound 1: "project a" (3 files)
- Compound 2: "project b" (3 files)

Each project's files properly grouped separately!

---

### Scenario 4: Leading Numbers in Titles

**Your Files:**
```
100 Nights-1.jpg
100 Nights-2.jpg
...
100 Nights-20.jpg
```

**Result:** ✅ All grouped in one compound
- DART handles leading numbers correctly
- Prefix: "100 nights"
- Sequence: 1-20
- Zero-padded display: [01], [02], ... [20]

---

### Scenario 5: Mixed Separators

**Your Files:**
```
exhibit_2013_001.tif
exhibit_2013_002.tif
exhibit 2013 catalog.pdf
exhibit-2013-poster.jpg
```

**Result:** ⚠️ Likely won't group well
- Inconsistent separators create different prefixes
- "exhibit_2013" ≠ "exhibit 2013" ≠ "exhibit-2013"

**Solution: Pick one separator style and stick with it:**
```
exhibit_2013_001.tif
exhibit_2013_002.tif
exhibit_2013_catalog.pdf
exhibit_2013_poster.jpg
```

---

## Troubleshooting

### Problem: Files aren't grouping that should be related

**Check:**
1. ✅ Do you have at least one numbered file to establish the base prefix?
2. ✅ Do all related files start with the exact same text (case-insensitive)?
3. ✅ Is the common prefix at least 3 characters long?
4. ✅ Are separators consistent across all files?

**Note:** DART automatically handles trailing separators and double spaces, so "Project -  Poster" and "Project_Program" will correctly group together.

**Solutions:**
- Add a numbered file (even just `ProjectName 01.pdf`)
- Rename files to have consistent base prefix
- Ensure common prefix is 3+ characters
- Standardize separators (all spaces, all underscores, or all hyphens)

---

### Problem: Files are grouping that shouldn't be related

**Check:**
1. Do the files accidentally start with the same text?
2. Is a prefix too generic (like "photo" when you have multiple photo projects)?

**Solutions:**
- Make prefixes more specific: `photo` → `photo_2024_exhibit`
- Use different base names for different projects
- Keep different projects in separate folders

---

### Problem: Compound shows wrong number of children

**Check:**
1. Are there hidden files or system files being included?
2. Do some files have different extensions that aren't recognized?

**Solutions:**
- DART only processes known media extensions (`.jpg`, `.tif`, `.pdf`, etc.)
- Check the log output for `[PARSE]` messages to see what was included
- Move non-media files to a different folder

---

### Problem: Sequence numbers look wrong

DART automatically detects and zero-pads sequence numbers based on the maximum value:
- Range 1-9: 1 digit (no padding needed)
- Range 1-99: 2 digits (`[01]`, `[02]`, ... `[99]`)
- Range 1-999: 3 digits (`[001]`, `[002]`, ... `[999]`)

This is **display only** - your original filenames are not changed.

---

## Quick Reference: Filename Patterns

### ✅ Excellent Patterns
```
ProjectName 001.jpg         ← Clear base + zero-padded sequence
ProjectName 002.jpg
ProjectName Poster.pdf      ← Descriptive suffix

Collection_Name_001.tif     ← Underscores for spaces
Collection_Name_002.tif
Collection_Name_Cover.jpg

2024-Event-01.jpg           ← Year prefix OK
2024-Event-02.jpg
2024-Event-Program.pdf
```

### ⚠️ Problematic Patterns
```
Poster.pdf                  ← No base name
Program.pdf                 ← Can't group without common prefix

AB-1.jpg                    ← Prefix too short (2 chars)
AB-2.jpg

photo1.jpg                  ← Generic base, no separator
photo2.jpg
another_photo_album.pdf     ← Won't match "photo"

001-ProjectName.jpg         ← Sequence at start (less ideal)
```

---

## Advanced Tips

### Using Folder Structure
If you have many related groups, consider organizing by folder:
```
/projects/
  /Wit-F13/
    Wit 001.jpg
    Wit Poster.jpg
  /100-Nights-S14/
    100 Nights-1.jpg
    100 Nights-Poster.pdf
```

Each folder's files are analyzed separately, reducing potential conflicts.

### Sequential Gaps Are OK
DART tolerates missing sequence numbers:
```
photo_001.jpg
photo_002.jpg
photo_005.jpg  ← Missing 003, 004
photo_006.jpg
```
Still recognized as sequential (avg gap ≤ 2, max gap ≤ 5).

### Multiple File Types
You can mix different file types in one compound:
```
scan_001.tif
scan_002.tif
scan_003.jpg     ← Different extension
scan_catalog.pdf ← Different extension
```
As long as they share the common prefix, they'll group together.

### Controlling Child Object Order
Don't use trailing numbers (like "000") to try to influence the display order of supplementary files:

**Avoid:**
```
Wit 001.jpg
Wit 002.jpg
Wit - Poster 000.jpg    ← Don't do this!
Wit - Program 000.pdf   ← These won't group correctly
```

**Instead:**
```
Wit 001.jpg
Wit 002.jpg
Wit - Poster.jpg        ← No trailing number
Wit - Program.pdf       ← No trailing number
```

After DART generates the CSV file with all your objects, you can easily adjust the order of child objects by moving rows around in the CSV. This gives you complete control over ordering without affecting the filename-based grouping logic.

---

## Summary: Keys to Success

1. **Consistency is king** - Use the same base name for all related files
2. **Numbers at the end** - Sequence numbers should be the last element
3. **At least 3 characters** - Common prefix must be 3+ chars
4. **Clear separators** - Space, underscore, or hyphen between elements
5. **One numbered file minimum** - Establishes the pattern for matching

Follow these guidelines and DART will intelligently group your files with minimal manual intervention!
