# GEMS-to-DART Collection Runbook

## Goal and Boundaries

Prepare a GEMS-complete collection on Linux, pull a checksummed package into
desktop DART on the Mac, review without merging, and then perform a separately
approved Azure run and desktop merge.

This runbook is collection-agnostic, but assumes **one intellectual object per
source subfolder, with flat compounds** (`group_compound_objects=true`,
`create_multiple_objects=false`). If your layout differs, stop and review
[GEMS Filename Rules](GEMS_FILENAME_RULES.md) before assigning IDs.

**Do not run server commands until installation, storage, and source access
have been approved.** These steps do not deploy DART, mount storage, change
GEMS, or scaffold/publish a CollectionBuilder site. Linux never merges into
the authoritative Mac core CSV.

GEMS-complete does not mean DART-complete: DART still assigns/reuses IDs,
constructs compound rows, routes assets, and generates derivatives. GEMS
backfill protects DART identity, structure, and URL fields; it does not
automatically adopt GEMS URLs or derivatives.

## Execution Map

**Run every shell block in the same Mac terminal.** Blocks marked **Linux via
SSH** execute remotely through the helper defined below; do not paste them
into a separate Linux terminal. Desktop actions take place in Mac DART.

| Step | Where | Effect |
| --- | --- | --- |
| 0 | Mac terminal | Define reusable variables and an SSH helper; no server changes |
| 1 | Linux via SSH | Inspect readiness and sources; no changes |
| 2 | Mac terminal | Create a header-only core for a genuinely new collection |
| 3 | Mac terminal and desktop | Create a private Linux project, configure Mac DART, push snapshot |
| 4 | Linux via SSH | Create private JSON inputs and configure Linux DART |
| 5 | Linux via SSH | Prepare without uploads; **persists durable IDs** |
| 6 | Mac desktop | Pull, compare, inspect, and cancel; **do not merge** |
| 7 | Linux via SSH | After separate approval, prepare with **Azure uploads** |
| 8 | Mac desktop | Pull the publishing job, selectively merge, push updated snapshot |

Never delete or recreate a project or ID map to retry. Once IDs have been
assigned, reuse the same project, collection ID, source paths, and grouping.

## 0. Define Values Once on the Mac

### 0.1 Collection and Installation Variables

Edit the values in this block **once** before running it. The two
`REPLACE_...` values are required inputs, not working examples. Defaults for
installation paths and the SSH account must also match your approved setup.
Use absolute paths; do not put credentials in any variable.

```bash
export COLLECTION_ID='REPLACE_WITH_COLLECTION_SLUG'
export GEMS_RUN='/REPLACE_WITH_ABSOLUTE_GEMS_RUN_DIRECTORY'
export HEADLESS_HOST='sysadmin@dg-landing'

export MAC_DART="$HOME/GitHub/DART"
export SHOW_REPO="$HOME/GitHub/SHOW"
export LINUX_DART='/home/sysadmin/GitHub/DART'
export LINUX_CONFIG='/data/dart/config'
export LINUX_DATA='/data/dart/data'
export DART_BRANCH='linux'

# Derived values: change only if your verified layout uses different names.
export GEMS_CSV="$GEMS_RUN/collection_metadata.csv"
export MAC_CORE="$SHOW_REPO/collections/$COLLECTION_ID/_data/${COLLECTION_ID}_metadata.csv"
export CORE_TEMPLATE="$SHOW_REPO/collections/_collection-template/_data/collection-template.csv"
export MAC_WORK="$HOME/DART-projects/$COLLECTION_ID"
export LINUX_PROJECT="$LINUX_DATA/projects/$COLLECTION_ID"
export AZURE_PATH="/objs/$COLLECTION_ID"
```

`GEMS_RUN` is the run directory **containing** `objects/`, not `objects/`
itself. `GEMS_CSV` is initially a candidate: verify it in Step 1 and update
that variable if the cumulative metadata file is elsewhere. It is not the
Mac core. `MAC_WORK` is the dedicated desktop Working/Outputs folder, not the
SHOW collection directory or the Linux project.

`DART_BRANCH=linux` reflects the branch containing the headless and desktop
handoff workflow when this runbook was written. Use an approved successor
revision if those features have moved; do not blindly switch branches or
use an older packaged desktop app.

Changing the collection later requires rerunning this entire definitions
block so derived paths change too. Never repurpose an existing Linux project
for another collection.

### 0.2 Define the Remote Helper

Run once in the **same Mac terminal**, after the variables above:

```bash
dart_remote() {
  (
    set -eu
    : "${HEADLESS_HOST:?Run Step 0.1 first}"
    : "${COLLECTION_ID:?Run Step 0.1 first}"
    : "${GEMS_RUN:?Run Step 0.1 first}"
    case "$COLLECTION_ID:$GEMS_RUN" in
      *REPLACE_*) printf '%s\n' 'Stop: replace the Step 0.1 placeholders.' >&2; exit 1 ;;
    esac
    {
      printf 'export COLLECTION_ID=%q GEMS_RUN=%q GEMS_CSV=%q\n' \
        "$COLLECTION_ID" "$GEMS_RUN" "$GEMS_CSV"
      printf 'export DART_REPO=%q CONFIG=%q DATA=%q WORK=%q AZURE_PATH=%q\n' \
        "$LINUX_DART" "$LINUX_CONFIG" "$LINUX_DATA" "$LINUX_PROJECT" "$AZURE_PATH"
      cat
    } | ssh -o BatchMode=yes "$HEADLESS_HOST" 'bash -se'
  )
}
```

The helper sends the current variables with each script, quoting paths for
remote Bash. Its remote names are `DART_REPO`, `CONFIG`, `DATA`, and `WORK`;
`WORK` always means the **Linux project**. Each invocation gets a fresh Linux
shell and stops on a failed command. Nothing is installed or saved by defining
the helper. Keep the Mac terminal open throughout the workflow; if it closes,
repeat Step 0 before continuing, not the creation steps.

## 1. Inspect Linux Readiness and Sources

**Linux via SSH; inspection only.** Missing paths or an incomplete installation
can make this block fail. Retain the output and stop rather than repairing
anything implicitly.

```bash
dart_remote <<'LINUX'
id
findmnt -T "$GEMS_RUN/objects"
df -h "$GEMS_RUN/objects" "$DATA"
ls -ld "$GEMS_RUN" "$GEMS_RUN/objects"
find "$GEMS_RUN" -maxdepth 2 -type f -name '*.csv' -print
find "$GEMS_RUN/objects" -mindepth 1 -maxdepth 1 -type d ! -name '.*' -print
ls -ld "$CONFIG" "$DATA" "$DATA/projects" "$DATA/jobs"
ls -l "$CONFIG/dart.env" "$CONFIG/.dart-storage" "$DATA/.dart-storage"
cd "$DART_REPO"
git branch --show-current
test -x .venv/bin/python
.venv/bin/python -m dart_linux --help
test -r "$GEMS_CSV"
LINUX
```

Before continuing, verify:

- This is the intended GEMS run, with one intellectual object per subfolder.
  Do not rename or reorganize its assets. Stop GEMS writes to this run through
  the normal operator workflow while DART scans it.
- The CSV listing identifies the cumulative GEMS metadata file. If necessary,
  correct `GEMS_CSV` in Step 0.1 and rerun the inspection.
- Installation and storage pass [Installation](INSTALL-LINUX.md) and
  [Acceptance Testing](LINUX-ACCEPTANCE.md). A successful `--help` alone does
  not establish readiness. Both checkouts need `prepare` and desktop SSH
  handoff support.
- An administrator has approved source read access and configured
  `DART_SOURCE_ROOTS` in the private environment file. Its allowlist `path`
  must cover both `objects/` and the metadata CSV; its `mount` must match
  `findmnt`, not an assumed `/data`.
- Capacity, Azure destinations, containers, and credentials have been reviewed.
  Upload approval is a separate gate in Step 7.

DART enforces its own no-source-write boundary; an administrator-managed
read-only mount adds protection. Do not change GEMS permissions, ownership,
mounts, or service configuration to make DART work.

## 2. Establish the Authoritative Mac Core

**Mac terminal.** For a genuinely new collection, this creates only the core's
parent directories and a header-only CSV, not a fully scaffolded SHOW site.
Confirm `MAC_CORE` and `CORE_TEMPLATE` before running.

**Existing collection:** do not run this creation block. Inspect the established
core and ID mapping, set `MAC_CORE` to that core in Step 0, and review migration
and snapshot compatibility before proceeding. Never replace a populated core
with an empty one.

```bash
(
set -eu
cd "$MAC_DART"
.venv/bin/python - <<'PY'
import csv
import os
import re
from pathlib import Path

collection = os.environ["COLLECTION_ID"]
if not re.fullmatch(r"[a-z0-9_-]+", collection) or collection == "collection-template":
    raise SystemExit("Stop: supply a valid, non-reserved collection ID in Step 0.")
template = Path(os.environ["CORE_TEMPLATE"])
target = Path(os.environ["MAC_CORE"])
if not target.is_absolute() or target.name == "collection-template.csv":
    raise SystemExit("Stop: core must be an absolute, non-template path.")
with template.open(newline="", encoding="utf-8-sig") as handle:
    columns = next(csv.reader(handle))
required = {"objectid", "original_file_name", "parentid", "type", "display_template",
            "object_location", "image_small", "image_thumb"}
if len(columns) != len(set(columns)) or not required.issubset(columns):
    raise SystemExit("Stop: template header is duplicate or missing required DART columns.")
target.parent.mkdir(parents=True, exist_ok=True)
with target.open("x", newline="", encoding="utf-8") as handle:
    csv.writer(handle).writerow(columns)
print(f"Created header-only core: {target}")
PY
)
```

Exclusive creation (`"x"`) refuses to overwrite an existing core. If it already
exists, inspect it; do not delete it to make this block succeed. Never merge
into `collection-template.csv`. Preserve all established identifiers.

## 3. Connect the Desktop Project and Push a Snapshot

### 3.1 Create a New Linux Project

**Linux via SSH**, only after readiness approval:

```bash
dart_remote <<'LINUX'
umask 077
mkdir -m 700 "$WORK"
LINUX
```

This deliberately fails if the project exists. For a retry or existing project,
inspect its settings and mappings, then reuse it; do not remove or recreate it.

### 3.2 Configure Mac DART

**Mac terminal.** Create the dedicated output folder and print the actual
values to enter in Function 0; no collection values need retyping in code.

```bash
(
set -eu
mkdir -p "$MAC_WORK"
printf 'Working/Outputs folder: %s\n' "$MAC_WORK"
printf 'collection-id: %s\ncore_metadata_csv: %s\n' "$COLLECTION_ID" "$MAC_CORE"
printf 'headless_host: %s\nheadless_project_dir: %s\n' "$HEADLESS_HOST" "$LINUX_PROJECT"
printf 'azure_blob_storage_path: %s\n' "$AZURE_PATH"
cd "$MAC_DART"
git branch --show-current
test "$(git branch --show-current)" = "$DART_BRANCH"
.venv/bin/python app.py
)
```

The branch check stops an unintended launch. If it fails, inspect
`git status --short` and resolve conflicting changes before deliberately
switching to the approved revision. Do not launch `dart_linux` on the Mac.
Leave the application terminal open; close DART when finished configuring
if you need that terminal for the next command.

In **desktop Function 0**, select the printed Working/Outputs folder and save
the printed settings, plus:

| Setting | Value |
| --- | --- |
| `gems_metadata_csv` | Blank on the Mac; Linux performs backfill |
| `group_compound_objects` | `true` |
| `create_multiple_objects` | `false` |
| `process_OHM_data` | `false` |

The Mac does not need the Linux objects mounted. Do not run desktop Functions
1-3 against unrelated local inputs. Selecting another Working/Outputs folder
can load another collection's settings.

### 3.3 Push the Core Snapshot

With no local export yet, Function 4 opens the pull dialog directly; that
dialog currently has no snapshot-push button. Bootstrap from the **Mac
terminal**, using the same definitions:

```bash
(
set -eu
cd "$MAC_DART"
.venv/bin/python - <<'PY'
import os
from dart_handoff import push_core_snapshot

checksum = push_core_snapshot(
    os.environ["HEADLESS_HOST"],
    os.environ["LINUX_PROJECT"],
    os.environ["MAC_CORE"],
)
print(f"Core snapshot pushed; SHA-256: {checksum}")
PY
)
```

Confirm success before continuing. Once a local export exists, Function 4's
file-selection dialog offers **Push Core Snapshot**. Linux reads the snapshot;
it never writes the authoritative Mac core.

## 4. Configure Linux DART

**Linux via SSH.** This creates private JSON inputs, not credentials. Python
serializes the variables as JSON, including paths containing spaces or quotes.
Existing JSON files are not overwritten.

```bash
dart_remote <<'LINUX'
umask 077
cd "$DART_REPO"
test -d "$GEMS_RUN/objects"
test -r "$GEMS_CSV"
test -r "$WORK/core-snapshot.csv"
.venv/bin/python - <<'PY'
import json
import os
from pathlib import Path

config = Path(os.environ["CONFIG"])
collection = os.environ["COLLECTION_ID"]
work = os.environ["WORK"]
source = str(Path(os.environ["GEMS_RUN"]) / "objects")
settings_path = config / f"settings-{collection}.json"
review_path = config / f"prepare-{collection}-review.json"
for path in (settings_path, review_path):
    if path.exists():
        raise SystemExit(f"Stop: inspect existing input file instead of replacing it: {path}")
settings = {
    "working_dir": work,
    "input_dir": source,
    "collection-id": collection,
    "core_metadata_csv": str(Path(work) / "core-snapshot.csv"),
    "gems_metadata_csv": os.environ["GEMS_CSV"],
    "azure_blob_storage_path": os.environ["AZURE_PATH"],
    "group_compound_objects": True,
    "create_multiple_objects": False,
    "process_OHM_data": False,
}
review = {
    "working_dir": work,
    "input_dir": source,
    "derivatives": True,
    "backfill": True,
    "allow_uploads": False,
    "overwrite": False,
}
for path, value in ((settings_path, settings), (review_path, review)):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")
    print(f"Created {path}")
PY
.venv/bin/python -m dart_linux --env-file "$CONFIG/dart.env" \
  --configure --inputs "$CONFIG/settings-$COLLECTION_ID.json"
LINUX
```

`--configure` validates the source allowlist, CSVs, schema, and collection ID.
Resolve reported errors before submitting a job; never change IDs or relocate
assets to bypass validation. For a retry, inspect existing JSON files and use
the final `--configure` command with those verified inputs rather than rerunning
their creation.

Keep the leading slash in `AZURE_PATH`: the current validator requires
`/objs/`. The uploader strips surrounding slashes and targets container
`objs`, subdirectory `COLLECTION_ID`, with parallel derivatives in
`smalls/COLLECTION_ID` and `thumbs/COLLECTION_ID`. This is not a Linux path.

## 5. Prepare Without Uploads

**Linux via SSH; foreground job.** Keep the Mac terminal and SSH connection
open until it finishes.

```bash
dart_remote <<'LINUX'
cd "$DART_REPO"
.venv/bin/python -m dart_linux --env-file "$CONFIG/dart.env" \
  --job prepare --inputs "$CONFIG/prepare-$COLLECTION_ID-review.json"
LINUX
```

This exports, generates local derivatives, backfills GEMS metadata, and creates
a handoff package. **It persists durable IDs even without uploads.**

Record the printed full job ID and package row count. Require exit status 0
and job state `succeeded`. Retain the job evidence under `LINUX_DATA/jobs/JOB-ID/`
and the project's settings/ID map. On failure, inspect that evidence; do not
delete mappings to retry.

Backfill fills only blank cells in columns present in the core schema.
Review the job's `gems-backfill.json` for unmatched rows, duplicate GEMS
filenames, and ignored columns. A successful job does not prove complete
metadata. Duplicate asset basenames across subfolders need deliberate
resolution: Function 4 requires unique `original_file_name` keys.

## 6. Pull and Review on the Mac Without Merging

### 6.1 Open the Correct Desktop Project

**Mac terminal**, if DART is not already open:

```bash
(
set -eu
cd "$MAC_DART"
test "$(git branch --show-current)" = "$DART_BRANCH"
.venv/bin/python app.py
)
```

**Mac desktop:**

1. Select the same `MAC_WORK` Working/Outputs folder.
2. Verify Function 0 matches the values printed in Step 3.2, especially
   collection ID, core, host, and Linux project. Keep `gems_metadata_csv` blank.
3. Ensure **Help Mode** is unchecked.
4. In **Select Function to Execute**, choose **4: Compare and Merge CSV Files**.
   Selecting it starts the function immediately; there is no separate execute
   button. If help opens instead, close it, uncheck Help Mode, and select again.

**Do not merge the rehearsal package.** Pulling, comparing, and opening
**Review & Merge Changes** are review steps, not writes to the core.

### 6.2 Select the Exact Linux Job and Pull

- **No local export:** **Pull From Headless DART** opens automatically.
- **Local exports exist:** in **Select New CSV to Compare**, click
  **Pull From Headless DART...**.

In the pull dialog:

1. Verify **Server project** matches `HEADLESS_HOST:LINUX_PROJECT`.
2. Find the **full Job ID from Step 5**, not merely the newest entry.
3. Compare its row count to the successful Linux package. Rows include
   generated parents and need not equal the number of source folders.
4. Check GEMS backfill counts and warnings. Matched-row and fields-filled
   counts show backfill ran, not that every required field is complete.
5. Expect a warning about server-local derivatives in this rehearsal.
   Investigate ID conflicts, unmatched GEMS rows, or other unexpected warnings.
6. Click **Pull For Review**. A previously pulled job shows
   **Pulled (Pull Again)**.

DART verifies the CSV checksum and collection ID, then saves under `MAC_WORK`:

```text
.DART-working-directory/
  DART_export_handoff_JOB-ID.csv
  DART_handoff_JOB-ID_manifest.json
```

`JOB-ID` represents the actual full job ID, not text to type literally.
Pulling does not copy assets/derivatives, upload anything, or change the core.
On success, Function 4 reopens with the pulled export available for comparison.

If SSH fails, test from the **Mac terminal** after closing DART if needed:

```bash
ssh -o BatchMode=yes "$HEADLESS_HOST" true
```

If no package appears, verify job success, project directory, and collection
ID. Do not create another project or regenerate IDs.

### 6.3 Compare the Pulled Export

In **Select New CSV to Compare**, set these options **before** choosing a file:

- Verify the displayed core matches `MAC_CORE`.
- Leave **Backfill empty fields from GEMS metadata CSV** off. It should be
  disabled with the Mac GEMS setting blank; backfill already ran on Linux.
- Leave **After a successful merge, move completed object folders to
  objects/.complete** off. Headless handoff does not retire GEMS sources.

Click the exact handoff filename for the recorded job. **Use Newest** is safe
only after checking that it selects that same file. Either action immediately
starts comparison.

For a **header-only core**, expect:

| Comparison Result | Expected Value |
| --- | --- |
| Core CSV | The file selected by `MAC_CORE` |
| New CSV | The handoff file for the recorded job |
| New records | The prepared package's row count |
| Changed records | `0` |
| Missing in new | `0` |

For an **existing populated core**, these counts do not apply: review additions,
changes, and missing records against that established core instead. A missing
record can simply be outside this batch; do not assume it should be deleted.
Comparison writes JSON and summary evidence in `.DART-working-directory`,
not into the core.

### 6.4 Inspect Complete Records and Relationships

Click **Review & Merge Changes** to open **Interactive Comparison & Merge**.
For a new core, the blue **NEW RECORDS** section summarizes filename, ID,
title, and **Add this record** checkboxes. They begin checked but do not write
anything until merge is invoked.

**This viewer is not a complete CSV-field viewer.** In Finder, open `MAC_WORK`,
press **Command-Shift-.** to show hidden files, and open the exact pulled CSV
and manifest in `.DART-working-directory` with VS Code or a CSV viewer.
Treat the CSV as read-only; do not save spreadsheet conversions over it.

| What to Inspect | Expected Result |
| --- | --- |
| `objectid` | Nonempty and unique. Newly assigned IDs start with the configured collection ID followed by `_dg_`; preserve established IDs. |
| `original_file_name` | Exact source basename, extension, and case; no duplicate keys. Generated parent names start with `_` and are not physical files. |
| Descriptive fields | GEMS-supplied values appear where applicable; required fields are not unexpectedly blank. Not every field must have a value. |
| Standalone records | A single-file object has no `parentid`. |
| Compound records | Each intended compound has its own generated parent; physical children point directly to it, without an unwanted intermediate `multiple` layer. Not every folder must become a compound. |
| Row order | Appropriate collection/child sequence; GEMS row order is used where backfill matches are available. |
| `object_location` | Blank in this no-upload export; protected GEMS URLs are not copied here. |
| `image_small`, `image_thumb` | Image/PDF records use Linux-local paths. Parents inherit derivatives from a suitable child; audio/video need not have them. |

Linux-local paths will not open as Mac files: derivatives were not transferred.
This verifies references, not visual quality. Inspect server images through an
approved access method if visual verification is required before upload approval.

In the manifest, check:

- `collection_id`, `job_id`, and `rows` match this collection and recorded job.
- `id_conflicts` is empty for a new-core rehearsal. Investigate any conflicts.
- `derivatives_local_only` is expected to be `true` when local image/PDF
  derivatives were generated.
- `warnings` contains no unexplained warnings beyond local-only derivatives.
- `gems_backfill`: review `matched_rows`, `fields_filled`,
  `unmatched_dart_rows`, `gems_duplicate_names`, and `ignored_gems_columns`.
  Unmatched rows need an explanation; ignored fields can reveal missing core
  schema columns. These statistics also appear in server `gems-backfill.json`,
  which is not downloaded separately.

If many new records lack descriptive metadata, investigate filename matching,
backfill statistics, and the core schema rather than dismissing the warning.

### 6.5 Cancel and Apply the Review Gate

1. Click **Cancel** in **Interactive Comparison & Merge**.
2. Close the results dialog if it remains open.
3. Do **not** click **Merge Selected Changes** or confirm **Merge Changes**.
   If a confirmation opens accidentally, cancel it.
4. Retain pulled files, comparison outputs, and Linux job evidence.

Proceed only when the intended job was pulled, counts agree, metadata and
relationships make sense, and all warnings are explained. The core must be
unchanged: for a new collection, still header-only.

Stop for ID conflicts, missing required metadata, unexpected compounds,
duplicate keys, or a stale snapshot warning. Correct inputs deliberately and
retry using the same Linux project. Do not change grouping or source paths
after ID assignment without reviewing mapping consequences.

## 7. Prepare With Separately Approved Azure Uploads

**Approval gate:** rehearsal review must be satisfactory and Azure uploads
explicitly approved. Confirm:

- The authorized connection string is in the private Linux environment file,
  never JSON inputs, Git, or shell history.
- `objs` and parallel derivative containers exist and destination conventions
  are approved; see [Function 3](FUNCTION_3_GENERATE_DERIVATIVES.md).
- Project, collection ID, source paths, grouping, and ID map are unchanged.
- A fresh core snapshot has been pushed if the Mac core changed.

**Linux via SSH. This is the first block authorizing Azure writes.**

```bash
dart_remote <<'LINUX'
umask 077
cd "$DART_REPO"
.venv/bin/python - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["CONFIG"]) / f"prepare-{os.environ['COLLECTION_ID']}-publish.json"
inputs = {
    "working_dir": os.environ["WORK"],
    "input_dir": str(Path(os.environ["GEMS_RUN"]) / "objects"),
    "derivatives": True,
    "backfill": True,
    "allow_uploads": True,
    "overwrite": False,
}
with path.open("x", encoding="utf-8") as handle:
    json.dump(inputs, handle, indent=2)
    handle.write("\n")
print(f"Created {path}")
PY
.venv/bin/python -m dart_linux --env-file "$CONFIG/dart.env" \
  --job prepare --inputs "$CONFIG/prepare-$COLLECTION_ID-publish.json"
LINUX
```

Require exit status 0 and state `succeeded`; record the **new publishing Job ID
and row count**. Existing blobs are skipped, not replaced. Skipping is not a
content-integrity check; investigate unexpected blobs rather than enabling
overwrite automatically. For a retry with an existing publishing JSON file,
inspect it and run only the final job command through `dart_remote`.

## 8. Pull the Publishing Job, Merge, and Close the Loop

**Mac desktop:**

1. Repeat Step 6's pull and comparison workflow using the **successful
   publishing Job ID from Step 7**, not the rehearsal job.
2. Verify approved HTTPS `object_location`, `image_small`, and `image_thumb`
   values where applicable. Review asset types without derivatives individually.
3. Review all metadata and complete families together. Select only approved
   additions and field changes in Function 4.
4. Click **Merge Selected Changes**, review the confirmation, and confirm
   **Merge Changes** only for the intended core and selections.
5. Verify the merged core. Function 4 creates a backup before writing it.
   Existing rows retain their order; selected additions follow export order.
6. **Push Core Snapshot** again, using the Function 4 file-selection dialog
   or the terminal command in Step 3.3 after closing DART if needed.

Headless processing and handoff do **not** move GEMS folders into `.complete`.
Leave sources intact and track completed job IDs and merged batches yourself.
Retain the Linux project and ID map for retries and future batches. Do not
scan the same run under a fresh project or point DART directly into `.complete`.
Publishing the CollectionBuilder site is a separate workflow.

## Validation Status

All 12 shell blocks and four embedded Python snippets passed syntax checks.
Isolated temporary-file tests verified header-only core creation, JSON contents,
overwrite refusal, and collection-ID checks. A local SSH stand-in verified
variable forwarding with spaces and quotes; it made no network connection.

No server deployment, source scan, Azure upload, real collection core creation,
or merge was performed while restructuring this runbook. Actual paths,
permissions, installation revision, GEMS CSV, and end-to-end operation remain
operator checks at the gates above.
