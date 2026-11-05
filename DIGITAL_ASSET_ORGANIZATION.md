# Organizing Digital Assets for DART

Use this guide to organize source folders and filenames for standalone assets,
flat compounds, and compounds containing numbered `multiple` objects in desktop
DART. Organize new assets before their first analysis; moving or renaming
previously analyzed files can affect persistent identifier mappings.

## Object Types

| Object | Meaning | Relationship |
|---|---|---|
| Standalone (`single`) | One supported asset file, such as a photograph, PDF, or recording | No parent |
| Compound (`compound`) | A generated parent representing related assets | Contains file children and optional `multiple` objects |
| Multiple (`multiple`) | A generated parent for two or more numbered files sharing a recognized filename base | Nested under a compound; the numbered files are its children |
| File child (`child`) | An asset file belonging to a compound or a `multiple` | References its parent through `parentid` |

Compound and `multiple` parents are metadata objects, not extra files you must
create on disk. A multi-page PDF is still one asset file; DART does not split
its pages into children.

Desktop DART creates relationships automatically during **Function 1: Analyze
Digital Assets**. There is no control for manually selecting files and
assigning them to a parent.

Automatic grouping works without GEMS. The `gems_metadata_csv` setting is
optional and is used by Function 4 for metadata backfill; it does not define
object membership.

## Choose the Organization Mode

| Desired Structure | App Settings | Source Organization |
|---|---|---|
| Standalone files only | **Compounds Grouped by Subdirectory** off; **Group Compound Objects** off | Every supported file stays standalone, even in subfolders |
| Flat compounds alongside standalone files | **Compounds Grouped by Subdirectory** on (the default); **Nest Numbered Sequences Under 'Multiple' Objects** off | One immediate subfolder per compound; standalone files directly in the Inputs Folder |
| Subdirectory compounds containing `multiple` parents | **Compounds Grouped by Subdirectory** on; **Nest Numbered Sequences Under 'Multiple' Objects** on | One immediate subfolder per compound; matching numbered files in each actual directory form a `multiple` |
| Filename-based compounds, without `multiple` parents | **Compounds Grouped by Subdirectory** off; **Group Compound Objects** on; **Nest Numbered Sequences Under 'Multiple' Objects** off | One folder per compound, with related filename bases |
| Filename-based compounds containing `multiple` parents | **Compounds Grouped by Subdirectory** off; **Group Compound Objects** on; **Nest Numbered Sequences Under 'Multiple' Objects** on | One folder per compound; each numbered filename base defines a possible `multiple` |

The corresponding setting keys are `group_by_source_directory`,
`group_compound_objects`, and `create_multiple_objects`. The last setting
defaults to `true` and applies in both grouping modes. Subdirectory grouping
defines the top-level compound by folder, then applies numbered-filename rules
within that compound. With nesting off, numbered files remain direct compound
children and retain their sequence numbers.

Enabling subdirectory grouping also enables and locks **Group Compound Objects**
in App Settings. To disable all grouping, turn off subdirectory grouping first.
Keep **Process OHM-Data Objects** (`process_OHM_data`) off for the ordinary asset
workflows in this guide; OHM mode bypasses grouping.

**Existing subdirectory-grouped projects:** sequence nesting now applies inside
these compounds too. If **Nest Numbered Sequences Under 'Multiple' Objects** is
already checked, the next analysis/export can add `multiple` parents and
re-parent numbered children without changing existing file or compound IDs.
Uncheck it before running if you need to preserve a flat hierarchy.

## Analyze and Export the Assets

1. Select the collection's **Working/Outputs Folder** first. DART loads
   App Settings values from that project folder.
2. Open **App Settings**, supply the required **Collection ID**, choose the
   organization mode above, and save.
3. Arrange supported asset files using one of the examples below.
4. Select the top-level source directory through **Inputs Folder**, leaving
   **Files Selection** empty. Function 1 scans supported assets recursively.
   Alternatively, with subdirectory grouping off, select specific files through
   **Files Selection → Browse...**; filename-based rules apply to those files.
5. Run **Function 1** and inspect the results. A successful group appears
   beneath a `COMPOUND` entry. Numbered sequences may also show a nested
   `MULTIPLE` entry.
6. Choose **Close** in the results dialog to accept the analysis and save new
   identifier mappings. **Cancel** discards this analysis and does not save
   its new mappings.
7. Run **Function 2** to export the analyzed objects and their relationships
   to the working CSV.

## Example: Two Compounds and Six Individual Objects

This layout represents two compound objects with four and five direct children,
alongside six standalone digital objects:

```text
collection-inputs/                 <-- Select as Inputs Folder
|
+-- theatre-program/              <-- Compound A: 4 children
|   +-- theatre_001.jpg
|   +-- theatre_002.jpg
|   +-- theatre_003.jpg
|   +-- theatre_004.jpg
|
+-- botanical-album/              <-- Compound B: 5 children
|   +-- botanical_001.jpg
|   +-- botanical_002.jpg
|   +-- botanical_003.jpg
|   +-- botanical_004.jpg
|   +-- botanical_005.jpg
|
+-- sundial.jpg                    <-- Individual object
+-- waterfall.tif                  <-- Individual object
+-- bicycle.png                    <-- Individual object
+-- manuscript.pdf                 <-- Individual object
+-- interview.mp3                  <-- Individual object
+-- observatory.mp4                <-- Individual object
```

### Settings and Selection

1. Enable **Compounds Grouped by Subdirectory** in App Settings.
2. Turn **Nest Numbered Sequences Under 'Multiple' Objects**
   (`create_multiple_objects`) off so the numbered files remain direct compound
   children rather than being nested under generated `multiple` parents.
3. Keep `process_OHM_data` set to `false`.
4. Select `collection-inputs/` through **Inputs Folder**, leaving **Files
   Selection** empty.

### Why the Six Stay Separate

In subdirectory-grouping mode, files directly in the selected Inputs Folder
remain standalone. Only the two immediate subfolders define compounds.

Additionally, the six standalone filenames have distinct, single-word stems,
no shared bases, and no trailing sequence numbers. They therefore avoid
filename-based grouping patterns too. Avoid renaming them to a shared numbered
pattern such as `photo_001.jpg` and `photo_002.jpg`, which could group them if
filename-based grouping is used later.

**Expected result:** two compound parents containing four and five direct
children, plus six standalone objects. That is 15 asset files and 17 total
objects including the two generated compound parents. The parent objects are
created by DART; no separate parent files are needed.

Review Function 1's results before accepting, then use Function 2 to export
the objects and relationships.

## How DART Decides What Belongs Together

- With **Compounds Grouped by Subdirectory** enabled (the default), each immediate
  child directory under the selected Inputs Folder defines one compound. Every
  supported file beneath it, including files in nested directories, is a child
  of that compound regardless of filename, either directly or through a
  `multiple` parent when sequence nesting is enabled. Sequence matching stays
  within each actual directory: matching bases in separate nested directories
  do not combine. Unnumbered files and unmatched files remain direct compound
  children. Files directly in the selected
  root remain standalone. Function 2 uses the same rule when exporting an
  Inputs Folder scan. This mode does not apply when specific files are
  selected.
- When subdirectory grouping is disabled, the following filename-based rules
  apply:
  - Grouping is limited to files in the **same actual directory**. Files
    selected from different directories do not get grouped together, even if
    their names match.
  - A group needs at least **two supported files** with a matching filename
    pattern. Prefix matching is case-insensitive, and the usable common prefix
    must be at least three characters.
  - A numbered filename pattern such as `photo_01.jpg` and `photo_02.jpg` can
    form a group. A related unnumbered file such as `photo_cover.jpg` can join
    when its name matches that numbered prefix.
  - Two or more unnumbered files can also group when DART identifies a shared
    base, such as `artifact_obverse.jpg` and `artifact_reverse.jpg`.
  - DART creates **one top-level compound per directory** that has one or more
    detected groups. Separate detected groups in the same directory share that
    compound; DART does not create one top-level compound per filename prefix.
  - A lone file, a prefix shorter than three characters, or files with no
    recognized shared pattern remain standalone.

Filename-based grouping is heuristic, so always review Function 1's result
before accepting it. In particular, if unrelated files accidentally share a
filename prefix, they may be grouped; if related names do not match the
patterns, they may remain standalone.

## Rules for Numbered Sequences and Multiple Objects

With compound grouping on and `create_multiple_objects` set to `true`, DART
creates one `multiple` parent for each recognized filename group containing at
least two numbered files. This applies both inside subdirectory-defined
compounds and in filename-based grouping:

- Put all members of a sequence in the **same actual directory**.
- Use a consistent filename base of at least three characters.
- Put the sequence number at the end of the stem, immediately before the
  extension: `gallery_001.jpg`, `gallery_002.jpg`, `gallery_003.jpg`.
  Prefer a consistent separator and zero-padding for predictable file sorting.
- Related unnumbered files such as `gallery_cover.pdf` remain direct children
  of the compound, not children of the `multiple`.
- One numbered file plus an unnumbered related file can form a compound, but
  does not create a `multiple`. At least two numbered files are required.
  In subdirectory mode, every supported file beneath an immediate subfolder
  belongs to that compound even without a matching filename.
- Separate numbered bases in one directory create separate `multiple` objects
  under the **same** directory-level compound.
- Numbered children are sorted numerically. Gaps do not prevent `multiple`
  creation; DART's sequential/irregular diagnostic is not a membership gate.

Set `create_multiple_objects` to `false` to attach numbered files directly to
the compound instead. In filename-based mode their sequence numbers are still
recorded. This setting alone does not enable grouping and never creates a
standalone, top-level `multiple`.

### Example: One Compound with Two Multiples and Two Standalone Assets

Use these settings to make the immediate `exhibition/` subfolder the compound:

```text
group_by_source_directory = true
group_compound_objects = true
create_multiple_objects = true
process_OHM_data = false
```

Select `exhibition-inputs/` as the **Inputs Folder**, with **Files Selection**
empty. The physical files are:

```text
exhibition-inputs/
|
+-- exhibition/
|   +-- gallery_001.jpg
|   +-- gallery_002.jpg
|   +-- gallery_003.jpg
|   +-- gallery_cover.pdf
|   +-- lecture_001.mp3
|   +-- lecture_002.mp3
|   +-- lecture_transcript.pdf
|
+-- sundial.jpg
+-- waterfall.tif
```

The resulting logical object hierarchy is different from the disk layout:

```text
Analyzed Objects
|
+-- COMPOUND (exhibition)
|   +-- MULTIPLE (gallery)
|   |   +-- gallery_001.jpg
|   |   +-- gallery_002.jpg
|   |   +-- gallery_003.jpg
|   +-- gallery_cover.pdf
|   +-- MULTIPLE (lecture)
|   |   +-- lecture_001.mp3
|   |   +-- lecture_002.mp3
|   +-- lecture_transcript.pdf
|
+-- sundial.jpg                    <-- Standalone
+-- waterfall.tif                  <-- Standalone
```

**Expected result:** nine asset files plus three generated parents (one compound
and two `multiple` objects), for 12 total objects. The compound has four direct
children: the two `multiple` parents, the cover PDF, and the transcript PDF.
The `multiple` parents contain three and two file children respectively.

Turning **Nest Numbered Sequences Under 'Multiple' Objects** off would instead
produce one flat compound with seven direct file children, plus the same two
standalone assets (10 total objects). With subdirectory grouping off and
**Group Compound Objects** on, these filenames also produce the illustrated
two-`multiple` hierarchy, but the directory-level compound is untitled.
Unmatched files inside that directory would remain standalone in filename-based
mode, rather than automatically joining the compound.

## Important Limitations

- DART has no manual parent-membership editor. In filename-based mode, related
  files must meet the filename rules; selecting them together is not enough.
  Use subdirectory grouping for flat compounds whose filenames do not match.
- DART's current model creates one top-level compound per directory. If
  separate detected groups in one directory must become separate top-level
  compounds, the current UI and grouping behavior cannot express that request.
- File and compound IDs are persistent. Moving or renaming files after they
  have been analyzed can affect path-based mappings. Do not reorganize an
  already-analyzed collection casually; review the project's mappings and
  existing identifiers first.

Never invent `dg_<digits>` tokens in source filenames: DART treats those as
pre-assigned permanent identifiers. Do not casually change grouping settings
for an already-analyzed collection; review its saved mappings and exported
relationships first.

## Related Documentation

For settings, the grouping algorithm, and additional filename examples, see
[App Settings](APP_SETTINGS.md),
[Function 1: Analyze Digital Assets](FUNCTION_1_ANALYZE_ASSETS.md) and
[Best Practices and Filename Conventions](BEST_PRACTICES.md).
