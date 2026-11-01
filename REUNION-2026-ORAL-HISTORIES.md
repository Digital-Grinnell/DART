# Reunion 2026 Oral Histories Merge

How to merge the OHM-processed Reunion 2026 alumni oral histories from
`~/GitHub/gccb-2026-Reunion-OH` into the SHOW `alumni-<decade>` collections
with [`scripts/merge_reunion_oral_histories.py`](scripts/merge_reunion_oral_histories.py).

## What It Does

- Routes each interview to `~/GitHub/SHOW/collections/alumni-<decade>/` using
  the interviewee's class year.
- Copies each interview's files from the `collectionbuilder` account (where
  OHM/DART first published them under `re26/`) into the `digitalgrinnell`
  account under the alumni collection's path:

  | File | `digitalgrinnell` Destination |
  | --- | --- |
  | MP3 | `objs/<slug>/<objectid>.mp3` |
  | Image derivatives (when present) | `smalls/<slug>/<objectid>_SMALL.jpg`, `thumbs/<slug>/<objectid>_TN.jpg` |
  | Transcript CSV | `transcripts/<slug>/<objectid>_transcript.csv` |

  New SHOW rows reference only these `digitalgrinnell` URLs. Copies never
  overwrite: an existing blob must already match byte-for-byte. Each upload is
  re-downloaded anonymously and checked by SHA-256. The `collectionbuilder`
  originals are left in place.
- Preserves durable identifiers: rows keep their existing `re26_dg_<epoch>`
  `objectid`. SHOW's remote-transcript plugin loads `object_transcript` at
  build time.
- Fills alumni-convention metadata: title `First Last 'YY`, `date` = class
  year, `creator_personal`/`interviewee` `Last, First 'YY`, interviewer in
  `interviewer` and `contributor_personal`, `type` `Sound`,
  `display_template` `transcript`, `extent` from the audio duration, and
  `rights`/`publisher`/`contributing_institution` copied from each core's
  existing convention. Only columns present in the destination core are written.

## Steps

Run from `~/GitHub/DART` with DART's venv, which provides
`azure-storage-blob` and `cryptography`.

1. **Draft the mapping** (already done once; rerun only with `--force`):

   ```bash
   .venv/bin/python scripts/merge_reunion_oral_histories.py init
   ```

   This writes `~/GitHub/gccb-2026-Reunion-OH/reunion-alumni-merge-map.csv`
   with each class year, the evidence used (source metadata or the
   interviewee's own self-introduction in the transcript), and a `notes`
   column for anything needing review.

2. **Review and edit the mapping.** Confirm class years, preferred names
   (for example Mike versus Michael, or Sarah Shipp who was Sarah Hibbs at
   Grinnell), titles, descriptions, and interviewer spellings. Set
   `include` to `no` to hold an interview back. If you change `class_year`,
   change `collection` to match; the merge refuses mismatches.

3. **Dry run** (anonymous reads only; checks every source file, validates
   transcripts, and lists each planned copy or already-present blob):

   ```bash
   .venv/bin/python scripts/merge_reunion_oral_histories.py merge
   ```

4. **Apply** with a `digitalgrinnell` connection string, either from a DART
   settings file whose encrypted connection string targets that account (for
   example `baumann`), or from `DART_AZURE_CONNECTION_STRING`. The script
   refuses any other storage account and never prints the secret.

   ```bash
   .venv/bin/python scripts/merge_reunion_oral_histories.py merge --apply \
     --settings ~/DART-projects/baumann/.DART-working-directory/dart_settings.json
   ```

   For each collection, all files are copied and verified first. Only then is
   its core backed up to
   `~/DART-projects/<slug>/.DART-working-directory/<slug>_metadata.csv.backup_<timestamp>`,
   new rows appended without rewriting existing bytes, and a dated entry
   added to the collection's `Collection_Notes.md`. If a copy fails, that
   collection's core is not touched; rerunning reuses verified copies and
   skips objects already in a core.

5. Build and review the affected SHOW collections locally before committing
   or deploying.

## Safety Checks

The merge refuses to write when a mapped object is missing from the source,
a class year does not match its target decade, a title or name is incomplete,
the target is reserved (`collection-template` or `_`-prefixed), an
`originating_system_id` or destination `object_location` already exists under
a different `objectid`, a source MP3, image, or transcript fails to load or
fails SHOW's transcript validation, a destination blob exists with different
content, or an upload does not read back identically.

## Caveats

- Object IDs stay `re26_dg_<epoch>` rather than `alumni-<decade>_dg_<epoch>`;
  only the storage location changes.
- Appending rows changes the Mac core relative to the dg-landing snapshot
  accepted by the October 30–31 oral-history pipelines. Do not rerun
  header-only acceptance for these collections; see
  [ORAL-HISTORIES-20261030.md](ORAL-HISTORIES-20261030.md).
- The one OHM input never processed (a WAV once misnamed
  `Blanchard_Mark_with_Kane_Jesse_AOH`) is not in the source metadata, so it
  is not merged.
