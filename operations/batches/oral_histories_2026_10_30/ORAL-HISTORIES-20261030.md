# Oral History Overnight Jobs — October 30, 2026

## Run on the Mac

These are two separate, approved publishing pipelines. **Run one at a time.**
Quit desktop DART and do not edit the selected SHOW cores or run competing
SHOW builds while a pipeline is active.

### Job 1: Alumni of the 1940s and PHPP Oral Histories

```bash
bash "$HOME/GitHub/DART/operations/batches/oral_histories_2026_10_30/run_oral_histories.sh" 1
```

### Job 2: Remaining Available Alumni Collections

```bash
bash "$HOME/GitHub/DART/operations/batches/oral_histories_2026_10_30/run_oral_histories.sh" 2
```

Job 2 includes `alumni-1950s`, `alumni-1960s`, `alumni-1970s`, `alumni-1980s`,
`alumni-1990s`, `alumni-2000s`, and `alumni-2010s`.

### October 31: Retry Only the Five Failed Collections

Original Job 2 batch `5816a0f2b3064a348a50c77a435ba328` accepted/built
1950s (22 rows) and 1960s (60 rows) with missing-parent coverage warnings.
Leave those populated cores unchanged and reconcile their warnings before
publication. The later five collections failed before saving ID maps or
uploading original media: numbered `dg_<digits>` siblings were all assigned
the same filename-derived asset ID. Subsequent acceptance's
`Requires a succeeded publishing collection` is a downstream eligibility
refusal, not an SSH connection failure.

The headless export now assigns distinct durable IDs to previously unmapped
assets with ambiguous embedded IDs, preserving existing mappings/core IDs,
unambiguous filenames, and OHM behavior. The fix is installed on dg-landing
with its previous runtime backed up. A no-write real-source analysis proved
unique IDs for all five scans; no probe IDs were persisted.

**Prepared, not launched.** Run this from a Mac terminal, with desktop DART
closed and no other DART/oral-history pipeline active:

```bash
cd "$HOME/GitHub/DART"
caffeinate -i .venv/bin/python -u -m scripts.run_headless_pipeline \
  --queue /data/dart/config/oral-history-2-retry-20261031.json \
  --inventory /data/dart/config/oral-history-2-retry-20261031-inventory.json \
  --unit dart-oral-history-2-retry-20261031 \
  --collections alumni-1970s alumni-1980s alumni-1990s alumni-2000s alumni-2010s \
  --apply
```

This new queue reuses the existing five projects and prepared transcript
metadata from Job 2, without rerunning transcript preparation or resetting
ID maps. The five SHOW cores were verified header-only. The locked staging
and actual Mac pipeline preview passed; the accepted 1950s/1960s cores
still match their acceptance checksums. Original queue/evidence stay intact.
Uploads remain non-overwriting, eligible acceptance/snapshot pushes/builds
are enabled, and catalog updates/website deployment remain off.
Existing transcript-pairing exceptions and missing-parent coverage warnings
may still require review; unique IDs alone do not establish complete coverage.

**`alumni-2020s` cannot be processed:** no active GEMS source exists. Its saved
October 23 audit found zero API-visible direct Alma members. Its SHOW core
remains unchanged, and Job 2 records it as unavailable rather than complete.
Do not invent an empty migration job or treat this as proof about historical
collection contents.

Authorize the initial Linux `sudo systemd-run` prompt. After that there are
no per-collection approvals, no no-upload rehearsals, and no desktop dialogs.
Automatic checksum, ID, relationship, source, title, disk-space, and
acceptance checks remain enabled; this is unattended processing, not
validation bypass.

Keep the **Mac plugged in, lid open, terminal open, and VPN connected**.
`caffeinate` prevents idle sleep, not closed-lid sleep or network loss.
The Linux system service survives disconnection; automatic Mac acceptance
and local builds do not run while the Mac is disconnected.

The Linux wrapper waits up to 24 hours for an active DART writer, including
the current Life publishing job, before changing the environment or starting
processing. Do not stop Life to start these jobs. A Mac-side shared lock
prevents the two oral-history pipelines from overlapping.

## What Was Approved and Staged

- Azure media and transcript uploads: **on**.
- Overwriting existing blobs: **off**. A differing existing transcript is
  reported as an error, never replaced.
- GEMS backfill and image/PDF derivatives: **on**.
- Flat compound grouping: **on**; `create_multiple_objects=false`.
- OHM processing: **off**.
- Free-space reserve: **50 GiB**.
- Eligible header-only SHOW core acceptance, checked Linux snapshot pushes,
  and local Jekyll/Pagefind builds: **on**.
- Catalog/publication/search-status edits, website deployment, original
  cleanup, ID-map resets, and speculative relationship repairs: **off**.

The nine available SHOW cores were all header-only. Each was backed up in
`~/DART-projects/<slug>/.DART-working-directory/` and expanded from 23 to 59
columns, retaining the original column order and adding missing GEMS fields
plus `object_transcript`. Source spellings, including `lanugage`, are retained;
the legacy `filename` alias is not added. No data rows were created.
Retaining a column does not automatically add it to item-detail display,
Browse filters, or Pagefind facets.

For each job number `N`, private server files under `/data/dart/config/` are:

| File | Purpose |
| --- | --- |
| `oral-history-N-20261030.json` | Exact batch queue |
| `oral-history-N-20261030-plan.json` | Transcript preparation and report paths |
| `oral-history-N-20261030-inventory.json` | Counts, exclusions, source metadata/VTT fingerprints, and core checksums |
| `oral-history-N-20261030-<slug>-core.csv` | Header-only template matching the SHOW core |

No job was started during staging. No media or transcript upload, durable
migration ID assignment, core acceptance, catalog edit, or deployment was
performed during staging.

## Source Inventory

All selected sources are the saved October 22 GEMS runs under
`/data/gems/data/`; exact paths are in the private inventories.
The nine sources total 6,347,933,321 bytes (approximately 5.91 GiB).

| Job | Collection | GEMS Rows | Physical Files | Eligible Assets | Automatic VTT Conversions |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | `alumni-1940s` | 7 | 9 | 5 | 4 |
| 1 | `phpp-oral` | 32 | 63 | 32 | 30 |
| 2 | `alumni-1950s` | 24 | 42 | 21 | 19 |
| 2 | `alumni-1960s` | 63 | 93 | 54 | 37 |
| 2 | `alumni-1970s` | 50 | 83 | 44 | 36 |
| 2 | `alumni-1980s` | 43 | 66 | 37 | 27 |
| 2 | `alumni-1990s` | 25 | 45 | 24 | 21 |
| 2 | `alumni-2000s` | 35 | 60 | 33 | 27 |
| 2 | `alumni-2010s` | 8 | 6 | 6 | 0 |

These are source counts, not guaranteed final parent/item counts. Grouping
depends on the actual supported files in each source folder; oral histories
are not forcibly turned into compounds merely because of their subject.
VTT and the one PHPP XML file are excluded from DART's ordinary asset scan;
VTT text is handled by the separate conversion step below.

## Non-OHM Transcript Handling

The Linux wrapper uses `prepare_oral_history_batch.py` before DART's
existing batch runner. It does not alter DART's normal asset scan or require
OHM naming/processing.

1. After acquiring DART's normal writer locks, add only this queue's exact
   GEMS run paths to the source allowlist, preserving existing entries and
   unrelated environment values. A private environment backup stays on the
   server; it contains credentials and must never be copied into git/chat.
2. Verify inventoried file counts/sizes and metadata/VTT fingerprints.
3. Pair a VTT with an MP3 only when their folder contains exactly one of
   each and the audio has exactly one matching GEMS filename row.
4. Convert cues to UTF-8 CSV with `timestamp,speaker,words`. Preserve text,
   line breaks, speaker labels when present, and source cue order. Decode
   VTT markup/entities into plain text; truncate start milliseconds to the
   whole-second precision supported by SHOW. Minutes beyond 59 are
   represented as the equivalent `HH:MM:SS`.
5. Upload to the existing shared `transcripts` container as
   `<collection>/<original-audio-stem>_transcript.csv`, with CSV MIME type.
   Existing content must match exactly. Verify anonymous HTTPS bytes.
6. Fill `object_transcript` on the corresponding audio row in a **prepared
   GEMS sidecar**, and on its existing GEMS parent only when that parent has
   exactly one MP3 child. Never guess a multi-audio parent's transcript.
7. Leave original GEMS metadata, VTTs, and media untouched. Prepared metadata,
   CSV copies, and per-collection reports live under
   `/data/dart/data/projects/.oral-history-N-20261030/<slug>/`.
   The standard batch reads this sidecar for normal GEMS backfill.

Real source VTTs contain empty zero-duration lead cues, nonchronological
starts, and two malformed end times. Empty cues are omitted with notices;
valid starts/text and their source order are preserved. SHOW uses start
times only, so an invalid/earlier end is recorded as a notice rather than
discarding the transcript. Invalid starts or other unconvertible files are
reported as exceptions, not repaired speculatively. All 201 unambiguous
transcripts converted successfully during the converter's read-only check,
yielding 13,992 nonempty cues.

### Unresolved Transcript Pairings

The following four folders contain two MP3s and two VTTs with differing
suffixes. All eight VTTs are retained for review; none is automatically paired:

| Collection | Folder |
| --- | --- |
| `alumni-1950s` | `grinnell_18525` |
| `alumni-1960s` | `grinnell_19485` |
| `alumni-1970s` | `grinnell_21209` |
| `alumni-1980s` | `grinnell_21215` |

`alumni-1970s/grinnell_23385_MEDIATRACK` has one VTT but no MP3 in its folder;
it is also reported without a guessed cross-folder match.
The 2010s source contains no VTT files.

These exceptions are printed and saved in transcript reports without
stopping unrelated collections. Transcript notices/exceptions are **not**
automatically written into SHOW metadata cells or interpreted as publication
approval. Serious upload/source/setup errors fail the affected collection;
normal batch behavior continues to later collections where safe.

## Monitor on dg-landing

Log in from the Mac:

```bash
ssh sysadmin@dg-landing
```

For Job 1:

```bash
systemctl status dart-oral-history-1-20261030.service --no-pager
sudo journalctl -u dart-oral-history-1-20261030.service -f -n 40
```

For Job 2, replace `-1-` with `-2-`. Ctrl+C stops log viewing, not the job.
While waiting for Life, the journal explicitly says it is waiting for the
active DART writer.

The journal prints the batch ID and exact summary path. During ordinary
asset preparation, detailed progress is in the individual job's `job.json`
and `job.log` under `/data/dart/data/jobs/<job-id>/`; the batch journal does
not echo every upload-progress update.

## Results and Retries

Mac pipeline results:

```text
~/DART-projects/.DART-working-directory/pipeline-dart-oral-history-1-20261030.json
~/DART-projects/.DART-working-directory/pipeline-dart-oral-history-2-20261030.json
```

Each contains the actual batch ID and acceptance summary path. Packages,
backups, evidence, and build logs stay in each collection's
`.DART-working-directory`. Server transcript summaries are:

```text
/data/dart/config/oral-history-1-20261030-transcript-report.json
/data/dart/config/oral-history-2-20261030-transcript-report.json
```

The pipeline records failures and continues with eligible collections;
coverage warnings allow partial editable cores under the existing policy.
Blank titles, invalid families, checksum/inventory mismatches, package
conflicts, ambiguous GEMS backfill, and changed/populated cores still block
acceptance. Exit 1 may therefore mean some collections succeeded and others
need review; inspect per-collection results. Warnings are never silently
called complete.

If the Mac disconnects, reconnect and rerun **the same numbered Mac command**.
It resumes monitoring an active service, or discovers its completed batch and
retries eligible acceptance without regenerating IDs or re-uploading media.
Byte-identical already-accepted cores are safe retries; manually edited
populated cores are refused. There is no cross-collection rollback.

If the service fails **before creating batch evidence**, inspect its journal
and transcript report instead of choosing a new service name or deleting
projects. A stopped service is not proof of success. Keep all source paths,
templates, settings, and ID maps stable through review.

After both jobs, visually review the built audio players, transcripts,
compound pages, metadata, and search before separately approving publication.

## Staging Verification

The focused DART transcript, pipeline, acceptance, and batch suites passed
49 tests. Both real pipeline previews found the exact expected queues and no
existing batch. All nine cores remain header-only with 59 unique columns and
matching staged checksums. The Mac/Linux helper SHA-256 values match.
SHOW's production `RemoteTranscripts.parse` accepted all 201 converted CSVs
and 13,992 cues. Python compilation, shell syntax, Markdown links, and
whitespace checks passed. Pylance could not inspect sibling DART files, so
runtime tests and compilation were used instead.

These checks do not claim that future uploads, package acceptance, or
collection builds have already succeeded.
