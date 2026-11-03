# Creating Compound Objects in Desktop DART

## What Desktop DART Supports

Desktop DART creates compound relationships automatically during **Function 1:
Analyze Digital Assets**. There is no control for manually selecting files and
assigning them to a compound parent.

Automatic grouping works without GEMS. The `gems_metadata_csv` setting is
optional and is used by Function 4 for metadata backfill; it does not define
compound membership.

## Create a Compound From Related Files

1. Select the collection's **Working/Outputs Folder** first. DART loads
   Function 0 settings from that project folder.
2. Open **Function 0: App Settings** and set:
   - `group_compound_objects` to `true`
   - `process_OHM_data` to `false`
   - `create_multiple_objects` as needed; see
     [Numbered Sequences](#numbered-sequences)
3. Save Function 0 settings.
4. Put the related, supported asset files in the **same directory** and use
   filenames whose shared pattern identifies the group. For example:

   ```text
   oral-history_001.mp3
   oral-history_002.mp3
   oral-history_transcript.pdf
   ```

   DART also groups eligible unnumbered files with a common filename base,
   such as `artifact_obverse.jpg` and `artifact_reverse.jpg`.
5. In the main window, either:
   - Select just those files with **Files Selection → Browse...**, or
   - Select the directory with **Inputs Folder → Browse...** and leave Files
     Selection empty. Function 1 scans supported assets in that directory and
     its subdirectories.
6. Run **Function 1** and inspect the results. A successful group appears
   beneath a `COMPOUND` entry. Numbered sequences may also show a nested
   `MULTIPLE` entry.
7. Choose **Close** in the results dialog to accept the analysis and save new
   identifier mappings. **Cancel** discards this analysis and does not save
   its new mappings.
8. Run **Function 2** to export the analyzed objects and their relationships
   to the working CSV.

## How DART Decides What Belongs Together

- Grouping is limited to files in the **same actual directory**. Files selected
  from different directories do not get grouped together, even if their names
  match.
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

Grouping is heuristic, so always review Function 1's result before accepting
it. In particular, if unrelated files accidentally share a filename prefix,
they may be grouped; if related names do not match the patterns, they may
remain standalone.

## Numbered Sequences

When a detected group contains at least two numbered files and
`create_multiple_objects` is `true` (the default), DART creates a `MULTIPLE`
object under the directory's compound, and the numbered files become children
of that `MULTIPLE`. Related unnumbered files remain direct children of the
compound.

Set `create_multiple_objects` to `false` when the numbered files should be
direct children of the compound instead. Sequence numbers are still retained
for ordering. This setting does not enable grouping by itself; it only changes
the structure of numbered groups after `group_compound_objects` has enabled
grouping.

## Important Limitations

- DART has no manual compound-membership editor. If related files do not meet
  the filename rules, Function 1 cannot currently create that relationship
  by user selection alone.
- DART's current model creates one top-level compound per directory. If
  separate detected groups in one directory must become separate top-level
  compounds, the current UI and grouping behavior cannot express that request.
- File and compound IDs are persistent. Moving or renaming files after they
  have been analyzed can affect path-based mappings. Do not reorganize an
  already-analyzed collection casually; review the project's mappings and
  existing identifiers first.

Supporting manually assigned members or multiple independent compounds in
one directory would require an application change. Until that is implemented,
do not treat manual assignment as a supported desktop workflow.

For the full grouping algorithm and examples, see
[Function 1: Analyze Digital Assets](FUNCTION_1_ANALYZE_ASSETS.md) and
[Best Practices and Filename Conventions](BEST_PRACTICES.md).
