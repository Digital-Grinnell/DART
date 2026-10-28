# DART On Linux: Headless Operating Overview

**Headless DART prepares data on dg-landing. Desktop DART reviews and merges.**

Headless DART on `dg-landing` has no browser or web interface. It analyzes
approved server sources, assigns durable IDs, exports CSV metadata, optionally
generates derivatives and backfills GEMS metadata, and then leaves a
checksummed **handoff package**. Desktop DART on your Mac pulls that package
over SSH, and you make every compare/merge decision in
[Function 4](FUNCTION_4_COMPARE_MERGE_CSV.md) against the authoritative core
metadata CSV, which stays on the desktop.

Headless DART **never compares, merges, or writes a core metadata CSV**.

This is everyday operation **after approved installation and storage setup**.
For setup, use [Headless Linux Installation](INSTALL-LINUX.md).
For isolated checks, use [Acceptance Testing](LINUX-ACCEPTANCE.md).
For a small GEMS-complete collection, use the
[Collection-Agnostic GEMS-to-DART Runbook](GEMS-HEADLESS-PILOT.md), including copy/paste
commands for a no-upload rehearsal and a separately approved publishing run.

<style>
@media print {
  .dart-diagram {
    break-before: page;
    page-break-before: always;
    break-inside: avoid;
    page-break-inside: avoid;
  }
  .dart-diagram svg {
    display: block;
    max-width: 100% !important;
    max-height: 6in !important;
    width: auto !important;
    height: auto !important;
  }
}
</style>

<div class="dart-diagram">

## Division Of Work

```mermaid
%%{init: {"themeVariables": {"fontSize": "18px"}, "htmlLabels": false, "flowchart": {"htmlLabels": false, "wrappingWidth": 420, "rankSpacing": 28, "nodeSpacing": 22}}}%%
flowchart TB
    core[("Mac: Core Metadata CSV\nAuthoritative")]
    snap[("dg-landing: core-snapshot.csv\nRead-Only Copy")]
    job["dg-landing: Headless DART\nprepare Job"]
    pkg[("dg-landing: Handoff Package\nexport.csv + manifest.json")]
    f4["Mac: Desktop DART Function 4\nHuman Compare And Merge"]
    core -->|"Push Core Snapshot (SSH)"| snap
    snap --> job
    sources[("Approved Sources\nRead-Only")] --> job
    job --> pkg
    pkg -->|"Pull From Headless DART (SSH)"| f4
    f4 -->|"Reviewed Merge"| core
```

</div>

The core snapshot gives headless DART the collection's column schema and
existing object IDs. It is a read-only input; headless DART never edits it.

## Desktop Prerequisites

Desktop DART reaches `dg-landing` with the system `ssh` command in batch mode,
so **key-based SSH authentication is required**. Password or interactive
prompts fail instead of hanging. Confirm from a Mac terminal:

```bash
ssh -o BatchMode=yes sysadmin@dg-landing true
```

In desktop **Function 0**, under **Headless DART Handoff**, set:

| Setting | Example | Meaning |
| --- | --- | --- |
| `headless_host` | `sysadmin@dg-landing` | SSH target running headless DART |
| `headless_project_dir` | `/data/dart/data/projects/REPLACE-COLLECTION` | Absolute managed project directory on that host |

Both are optional and per desktop project. Leave both blank to turn the
handoff buttons off. Desktop DART validates them before saving and never
accepts SSH options in either field.

## One-Time Project Setup

1. **On Linux**, an operator creates the private project directory:

   ```bash
   umask 077
   mkdir -m 700 /data/dart/data/projects/REPLACE-COLLECTION
   ```

2. **On the Mac**, in desktop Function 4, click **Push Core Snapshot**. This
   copies the configured core metadata CSV to
   `REPLACE-COLLECTION/core-snapshot.csv` (owner-only) on `dg-landing`. The
   desktop core is not changed.

3. **On Linux**, save the collection's headless settings from an owner-only
   JSON file. `core_metadata_csv` must point to the pushed snapshot:

   ```json
   {
     "working_dir": "/data/dart/data/projects/REPLACE-COLLECTION",
     "input_dir": "/APPROVED/LINUX/SOURCE",
     "collection-id": "replace-collection",
     "core_metadata_csv": "/data/dart/data/projects/REPLACE-COLLECTION/core-snapshot.csv",
     "gems_metadata_csv": "",
     "azure_blob_storage_path": "",
     "group_compound_objects": true,
     "create_multiple_objects": false,
     "process_OHM_data": false
   }
   ```

   ```bash
   chmod 600 /data/dart/config/settings-REPLACE-COLLECTION.json
   cd ~/GitHub/DART
   .venv/bin/python -m dart_linux --env-file /data/dart/config/dart.env \
     --configure --inputs /data/dart/config/settings-REPLACE-COLLECTION.json
   ```

Use the **same `collection-id`** as the desktop project. Once a project has
durable IDs, headless DART refuses to change its collection ID. Set
`gems_metadata_csv` to an approved readable GEMS CSV path to enable server-side
GEMS backfill. Source paths must be actual Linux mount paths; Mac volume names
are never translated.

Push a fresh core snapshot whenever the desktop core changes materially,
especially after a merge, so new jobs reuse the latest IDs.

## Everyday Flow

### 1. Prepare A Package On Linux

Put job inputs in an owner-only JSON file:

```json
{
  "working_dir": "/data/dart/data/projects/REPLACE-COLLECTION",
  "input_dir": "/APPROVED/LINUX/SOURCE",
  "allow_uploads": false,
  "overwrite": false
}
```

```bash
chmod 600 /data/dart/config/job-inputs.json
cd ~/GitHub/DART
.venv/bin/python -m dart_linux --env-file /data/dart/config/dart.env \
  --job prepare --inputs /data/dart/config/job-inputs.json
```

`prepare` runs export, then derivatives, then handoff, as one job. Optional
input keys:

| Key | Default | Effect |
| --- | --- | --- |
| `derivatives` | `true` | Generate derivatives before packaging |
| `backfill` | `true` when the project has `gems_metadata_csv` | Fill blank export fields from GEMS metadata on the server |
| `allow_uploads` | `false` | Permit Azure uploads for this job only |
| `overwrite` | `false` | Permit replacing existing blobs; requires `allow_uploads` |

No credentials belong in inputs. Azure credentials come only from the private
environment file, and containers must already exist.

The CLI prints the job ID, evidence path, and the final job record, including
the package path, row count, ID-conflict count, and warnings. Exit 0 means
`succeeded`; nonzero means failure, cancellation, or startup rejection.
Ctrl+C or SIGTERM requests cooperative cancellation.

### 2. Pull And Review On The Mac

1. Open desktop DART on the matching project and click **Function 4**.
2. Click **Pull From Headless DART...**. The dialog lists complete packages
   on `dg-landing` with their row counts and warnings.
3. Pull the intended package. DART verifies its checksum and collection ID,
   then saves it as `DART_export_handoff_JOB-ID.csv` (with its manifest as
   `DART_handoff_JOB-ID_manifest.json`) in `.DART-working-directory`.
4. The pulled CSV is now the newest export. Compare, review, and merge exactly
   as in any other Function 4 session.

If the desktop core changed since the snapshot was pushed, the pull warns you
before review. If no local `DART_export_*.csv` exists, Function 4 opens the
pull dialog automatically when headless handoff is configured.

## Individual Job Kinds

`prepare` is the normal path. The individual stages remain available:

| Job | Required Inputs | Result |
| --- | --- | --- |
| `analyze` | `working_dir`, `input_dir` | Saves durable file/compound ID mappings |
| `export` | `working_dir`, `input_dir` | `DART_export_JOB-ID.csv` in the project working directory |
| `derivatives` | `working_dir`, `csv_path` | Local or uploaded derivatives and an updated CSV |
| `handoff` | `working_dir`, `csv_path` | Handoff package from an existing managed CSV |
| `prepare` | `working_dir`, `input_dir` | Export, optional derivatives, and handoff |

Review job history at any time:

```bash
.venv/bin/python -m dart_linux --env-file /data/dart/config/dart.env --list-jobs
```

## Identifier Reuse

Headless export assigns object IDs in this order:

1. The project's saved `file_to_id_map` entry for the file
2. A `dg_<epoch>` identifier already present in the filename
3. The core snapshot's `objectid` for the same `original_file_name`, used only
   when that name is unique in both the snapshot and the scan
4. A newly generated `<collection-id>_dg_<epoch>` identifier

Compound parent IDs are not seeded from the snapshot. When an export row's
filename and ID disagree with the snapshot, the package lists it under
`id_conflicts` and adds a warning. Resolve these during desktop review; DART
never rewrites an existing core ID.

## Handoff Package Contents

Let `WORK` be the project directory and `JOB-ID` the job ID.

| Location | Contents |
| --- | --- |
| `WORK/handoff/JOB-ID/export.csv` | Prepared metadata, without the server-only `filepath` column |
| `WORK/handoff/JOB-ID/manifest.json` | Format, job ID, collection ID, CSV SHA-256, row count, snapshot SHA-256, ID conflicts, warnings |
| `WORK/handoff/JOB-ID/gems-backfill.json` | GEMS backfill statistics, when backfill ran |

`manifest.json` is written last, so a package without it is incomplete and is
never listed for pull. Packages are retained until an operator removes them;
no automatic cleanup runs.

**Derivatives are not transferred.** Without upload consent, derivative cells
contain local Linux paths. The manifest flags this as
`derivatives_local_only` with a warning. Those paths are not published URLs.
Authorize uploads for publishing-ready derivative URLs.

## Other Server Locations

| Location | Contents |
| --- | --- |
| `/data/dart/config/dart.env` | Private roots, approved source mounts, optional Azure credential |
| `/data/dart/config/.dart-service.lock` | Configuration writer lock |
| `/data/dart/data/.dart-service.lock` | Data writer lock |
| `/data/dart/data/jobs/JOB-ID/job.json` | State, timestamps, inputs, progress, result and artifact paths |
| `/data/dart/data/jobs/JOB-ID/job.log` | Redacted job activity/error log |
| `/data/dart/data/jobs/JOB-ID/settings-snapshot.json` | Effective settings and pre-job ID map, excluding credentials |
| `/data/dart/data/jobs/JOB-ID/analysis.json` | Analyzed file/compound records |
| `WORK/core-snapshot.csv` | Read-only core copy pushed by desktop DART |
| `WORK/.DART-working-directory/dart_settings.json` | Collection settings and durable ID map |
| `WORK/.DART-working-directory/DART_export_JOB-ID.csv` | Export CSV |
| `WORK/.DART-working-directory/derivatives_JOB-ID/` | Retained local derivatives and transient TIFF normalization |
| `WORK/.DART-working-directory/DART_export_with_derivatives_JOB-ID.csv` | Derivative metadata CSV |
| `WORK/_data/transcripts/` | OHM transcript copies, when applicable |

Headless DART never moves GEMS objects into `.complete`, never deletes
sources, and never publishes a CollectionBuilder site.

## Concurrency, Cancellation, And Recovery

Only one headless DART process may write the managed roots at a time. A second
writer is refused; inspect the existing process rather than deleting locks.
OS advisory locks release when the owner exits.

Cancellation is cooperative and occurs between checkpoints. If the final
atomic commit completed first, `succeeded` is correct. After a crash or
forced stop, the next start marks unfinished jobs `interrupted`, retains
evidence, and does not resume them. Review mappings and partial outputs
before submitting a replacement.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Desktop pull or push reports an SSH error | Confirm `ssh -o BatchMode=yes HOST true` succeeds from the Mac; install a key if needed |
| No packages listed | Confirm the `prepare`/`handoff` job succeeded and `headless_project_dir` matches the server project |
| Pull refuses a collection mismatch | The package's collection ID differs from the desktop project's `collection-id`; pull from the right project |
| Pull refuses to overwrite a local file | A different file already uses that name; review and remove it deliberately |
| Core snapshot differs warning | Push a fresh snapshot and re-run `prepare`, or review carefully knowing IDs may be stale |
| `id_conflicts` in the manifest | Review those rows during Function 4; existing core IDs are never changed |
| Local paths in derivative cells | That was local-only processing; authorize uploads only after approval |
| Another writer error | Wait for or inspect the existing headless process |
| Missing storage marker or changed identity | Stop; ask the administrator to verify storage; never initialize a fallback |
| Mac/UNC source path rejected | Use the approved Linux mount path; DART does not translate paths |
| Azure error | Review the redacted job log and private configuration; do not paste secrets |
