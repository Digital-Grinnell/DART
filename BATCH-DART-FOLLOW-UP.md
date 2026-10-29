# Following Up on a Headless DART Batch

## Purpose and Boundaries

Use this runbook **after a headless batch finishes**. Linux has prepared
handoff packages; it has not merged the authoritative SHOW metadata CSVs or
published collection sites. Work through each successful collection separately:

1. Verify the batch and record exact publishing job IDs.
2. Select the matching Mac project and core.
3. Pull, inspect, and selectively merge the publishing package.
4. Verify the merged core and push a fresh snapshot to Linux.
5. Build/review SHOW, then publish only after separate approval.
6. Optionally reclaim verified local derivatives; retain originals and IDs.

The commands below do not launch another batch. Do not rerun a successful
queue just to retrieve its results. For job preparation, use the
[operating overview](LINUX-HEADLESS-OVERVIEW.md#overnight-collection-batches).
For the full single-collection workflow, use the
[GEMS runbook](GEMS-HEADLESS-PILOT.md).

## Terminals and Process Lifetimes

| Location | Role | When to Continue |
| --- | --- | --- |
| Terminal A: local Mac Bash shell | Defines collection values, starts desktop DART, runs SHOW commands | A one-shot command must finish successfully before proceeding |
| Mac DART window | Function 0 settings, Function 4 pull/review/merge/snapshot | Keep Terminal A's desktop process running until UI work finishes |
| Terminal B: Linux shell on `dg-landing` | Reads batch evidence, checks space, optionally runs cleanup | Inspection commands finish; cleanup must finish before another managed writer starts |

Open Terminal A locally on the Mac and run `bash` once. Keep that shell open
to retain the variables below. Terminal B can be a separate SSH session.
Commands marked **Linux** belong at the Linux prompt, not in the occupied
desktop-launch terminal. Never paste shell commands while desktop DART is
running in that terminal. Quit DART normally to recover the prompt.

The completed systemd batch does not need to remain running for desktop review.
SSH/VPN must be available during pulls and snapshot pushes. Do not interrupt a
merge, pull, snapshot push, or cleanup to reclaim a prompt.

## 1. Verify the Batch Result

**Terminal B - Linux.** Replace the batch ID for a different run:

```bash
# LINUX. Read-only inspection of the October 29 afternoon batch.
export BATCH_ID='4645079de84549df96ed488c5f0e2db2'
python3 -m json.tool "/data/dart/data/batches/$BATCH_ID/summary.json"
df -h /data
```

Inspect the overall state and every collection record. Record its collection
ID, working directory, exact job ID, state, row count, conflicts, warnings,
and package path. For each intended publishing package, verify its job's
`inputs.allow_uploads` is true in `jobs/JOB-ID/job.json`, and inspect the
handoff manifest for local-only derivative warnings. A successful rehearsal
is not a publishing package.

- `succeeded`: proceed with that collection's review, not automatic acceptance.
- `failed`, `cancelled`, or `interrupted`: inspect job logs/partial outputs.
  Do not merge an incomplete package.
- Batch `blocked` with `stop_reason=low_space` / exit `75`: successful
  collections can still be reviewed; pending entries have not finished.
  Reclaim verified space and requeue only unfinished entries later.
- Batch `running` is not proof of a live worker after a crash. Check the
  service and job evidence before starting another writer.

### Worked Example: October 29 Afternoon Batch

These are the verified results for batch
`4645079de84549df96ed488c5f0e2db2`. For future runs, use their summaries
instead of reusing these job IDs.

| Collection ID | Publishing Job ID | Prepared Rows | SHOW Core Relative to SHOW Root |
| --- | --- | ---: | --- |
| `baumann` | `02da48d276004e9fb215cd94aa92d67e` | 18 | `collections/baumann/_data/baumann.csv` |
| `syllabi` | `dc70eb8262794ac0aca2a99dbacb89ee` | 84 | `collections/syllabi/_data/syllabi_metadata.csv` |
| `ley` | `920f7b2818d44c28a5d625d567dfb389` | 702 | `collections/ley/_data/ley_metadata.csv` |
| `cyclone` | `56a2c979593e40db80a309c3e0ce69eb` | 31 | `collections/cyclone/_data/cyclone_metadata.csv` |

All four reported zero ID conflicts and no warnings. That does not establish
complete source coverage, content identity in Azure, or publication readiness.
Start with Baumann, then repeat Sections 2-7 for each remaining collection.

## 2. Select One Mac Collection and Launch DART

> **STOP: WORKING/OUTPUTS FOLDER FIRST, FUNCTION 0 SECOND.**
> The launch command does **not** configure DART. Its printed values are
> instructions for you to enter in the window. After launch, select the
> collection's Working/Outputs folder **before opening Function 0**.
> Settings belong to that folder, not to the app globally. Changing folders
> loads a different project's settings; it does not transfer your entries.

**Terminal A - Mac.** Set all values together each time you change collections.
This first block selects Baumann; substitute the exact ID, job ID, and core
filename from the table for the next collection:

```bash
# MAC. Define values for ONE collection; no server changes.
export COLLECTION_ID='baumann'
export JOB_ID='02da48d276004e9fb215cd94aa92d67e'
export CORE_BASENAME='baumann'
export MAC_DART="$HOME/GitHub/DART"
export SHOW_REPO="$HOME/GitHub/SHOW"
export MAC_WORK="$HOME/DART-projects/$COLLECTION_ID"
export MAC_CORE="$SHOW_REPO/collections/$COLLECTION_ID/_data/$CORE_BASENAME.csv"
export HEADLESS_HOST='sysadmin@dg-landing'
export LINUX_PROJECT="/data/dart/data/projects/$COLLECTION_ID"
```

For Syllabi, paste this **whole replacement definitions block** before the
launch block. Changing only `COLLECTION_ID` does not recompute existing paths.
Do not rerun the Baumann block afterward.

```bash
# MAC. Select Syllabi and recompute EVERY dependent path.
export COLLECTION_ID='syllabi'
export JOB_ID='dc70eb8262794ac0aca2a99dbacb89ee'
export CORE_BASENAME='syllabi_metadata'
export MAC_DART="$HOME/GitHub/DART"
export SHOW_REPO="$HOME/GitHub/SHOW"
export MAC_WORK="$HOME/DART-projects/$COLLECTION_ID"
export MAC_CORE="$SHOW_REPO/collections/$COLLECTION_ID/_data/$CORE_BASENAME.csv"
export HEADLESS_HOST='sysadmin@dg-landing'
export LINUX_PROJECT="/data/dart/data/projects/$COLLECTION_ID"
```

Use the collection's established Mac Working/Outputs directory if it differs
from this convention. Never replace an existing core or create a new Linux
project/ID map as part of follow-up. If the SHOW overlay is absent, use SHOW's
preview-first `scripts/initialize_collection.rb` before proceeding; see
[Mac core initialization](GEMS-HEADLESS-PILOT.md#2-establish-the-authoritative-mac-core).
Confirm its schema matches the Linux snapshot.

```bash
# MAC. Launch desktop DART; this terminal remains occupied.
(
set -eu
: "${COLLECTION_ID:?Run the collection definitions block first}"
: "${JOB_ID:?Run the collection definitions block first}"
: "${MAC_CORE:?Run the collection definitions block first}"
: "${MAC_WORK:?Run the collection definitions block first}"
: "${HEADLESS_HOST:?Run the collection definitions block first}"
: "${LINUX_PROJECT:?Run the collection definitions block first}"
: "${MAC_DART:?Run the collection definitions block first}"
printf 'Collection: %s\nJob: %s\nCore: %s\n' "$COLLECTION_ID" "$JOB_ID" "$MAC_CORE"
printf 'Working/Outputs: %s\nServer: %s:%s\n' "$MAC_WORK" "$HEADLESS_HOST" "$LINUX_PROJECT"
printf '\nSTOP: These values are NOT applied automatically.\n'
printf '1. In DART, select Working/Outputs FIRST: %s\n' "$MAC_WORK"
printf '2. ONLY THEN open Function 0, enter/verify this collection settings, and SAVE.\n'
printf '3. Keep that folder selected; then open Function 4.\n\n'
if [ ! -r "$MAC_CORE" ]; then
  printf 'ERROR: Core CSV is missing or unreadable: %s\nRerun the complete definitions block for this collection.\n' "$MAC_CORE" >&2
  exit 1
fi
if [ "$(basename "$MAC_CORE")" = 'collection-template.csv' ]; then
  printf 'ERROR: Select a collection core, not collection-template.csv.\n' >&2
  exit 1
fi
printf 'Checking SSH connectivity to %s...\n' "$HEADLESS_HOST"
if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "$HEADLESS_HOST" true; then
  printf 'ERROR: SSH check failed; resolve connectivity before launching.\n' >&2
  exit 1
fi
mkdir -p "$MAC_WORK"
cd "$MAC_DART" || { printf 'ERROR: Cannot enter DART checkout: %s\n' "$MAC_DART" >&2; exit 1; }
if [ ! -x .venv/bin/python ] || [ ! -r app.py ]; then
  printf 'ERROR: This checkout needs a readable app.py and executable .venv/bin/python.\n' >&2
  exit 1
fi
.venv/bin/python app.py
)
```

Use a checkout containing desktop headless handoff support, not an older
packaged application. If the SSH test fails, resolve connectivity first;
do not rerun publishing to fix a connection problem.

If an older launch block returns immediately with no output, its initial
`test -r "$MAC_CORE"` may have failed under `set -e`. The revised block above
prints the selected paths before checking them and reports the failure.
Syllabi's core is `syllabi_metadata.csv`, **not** `syllabi.csv`.

### Function 0 Settings

**Mac DART window - do these steps in this order, for EVERY collection:**

1. **FIRST:** use **Working/Outputs Folder -> Browse...** to select the printed
   `MAC_WORK`. Verify the displayed path before continuing.
2. **SECOND:** open **Function 0**. Enter/verify the settings below and save.
3. **THIRD:** keep that folder selected and proceed to **Function 4**.

**Do not enter Function 0 settings and then change the working folder.**
If you already did, select the correct folder now, reopen Function 0, and
enter/verify and save its settings again. Previously saved settings remain
with the folder selected when you saved them.

| Setting | Required Value for This Workflow |
| --- | --- |
| `collection-id` | The selected collection ID |
| `core_metadata_csv` | The printed authoritative Mac core, not the Linux snapshot or export |
| `headless_host` | `sysadmin@dg-landing` |
| `headless_project_dir` | The printed `/data/dart/data/projects/COLLECTION-ID` |
| `gems_metadata_csv` | Blank: Linux already performed GEMS backfill |
| `group_compound_objects` | `true` for this batch's flat-compound configuration |
| `create_multiple_objects` | `false` for this batch |
| `process_OHM_data` | `false` for this batch |

Other batch layouts must retain their actual grouping/OHM configuration.
The disabled Inputs Folder/file-selection controls are expected for headless
handoff; no Mac-mounted copy of Linux originals is needed.

## 3. Pull the Exact Publishing Package

**Mac DART window; keep Terminal A running:**

1. Uncheck **Help Mode**.
2. Choose **4: Compare and Merge CSV Files**. Selection starts the function;
   there is no separate execute button in this workflow.
3. In **Select New CSV to Compare**, click **Pull From Headless DART...**.
   The pull dialog can open automatically when there is no local export.
4. Confirm **Server project** matches the selected collection's Linux project.
5. Select the **exact publishing job ID** from the summary/table, not merely
   the latest package. Check its row count, backfill statistics, and warnings.
6. Click **Pull For Review** (or **Pulled (Pull Again)** for that same job).
   Wait for checksum/collection-ID verification and return to Function 4.

The local working directory now contains:

- `.DART-working-directory/DART_export_handoff_JOB-ID.csv`
- `.DART-working-directory/DART_handoff_JOB-ID_manifest.json`

If a local file with different contents already exists, stop and inspect it;
do not delete it blindly. A snapshot mismatch can mean the local core changed
since preparation; reconcile that before merging. Re-pulling an older package
after a merge can legitimately warn, but must not be used to overwrite later
metadata indiscriminately.

## 4. Compare and Reconcile Coverage Before Merging

**Mac DART window:**

1. Confirm the displayed core is the intended `MAC_CORE`.
2. Leave **Backfill empty fields from GEMS metadata CSV** off.
3. Leave **After a successful merge, move completed object folders to
   objects/.complete** off. Headless follow-up does not retire sources.
4. Select `DART_export_handoff_JOB-ID.csv` for the recorded job.
   **Use Newest** is safe only when it selects that exact file.
5. For a header-only core, expect additions equal to prepared rows, zero
   changed records, and zero missing records. For an existing populated core,
   inspect all actual differences instead. Missing records are not a deletion
   instruction.
6. Open **Review & Merge Changes**. New records begin checked; this is not
   evidence that every addition should be accepted.

The interactive viewer does not display every CSV field. In Finder, open
`MAC_WORK`, use **Command-Shift-.** to show hidden files, and open the exact
export/manifest in VS Code or a CSV viewer. Treat pulled evidence as read-only;
do not save spreadsheet conversions over it.

### Collection Review Checklist

- IDs are nonempty/unique; existing IDs and filename-to-ID pairings are preserved.
- `original_file_name` values match source names, extensions, and case.
  Generated compound parent names begin with `_`.
- Children reference the correct parent; flat compounds have no unintended
  intermediate `multiple` layer. Review complete families together.
- Titles, descriptions, dates, rights, and other required fields are present.
  Review GEMS unmatched rows and ignored columns; a core schema cannot receive
  descriptive fields it does not contain.
- Applicable originals/derivatives have the expected HTTPS Azure URLs, not
  Linux paths or rehearsal blanks. Audio and unsupported derivative types
  need individual review. Compound parents should use appropriate child images.
- Manifest collection ID, job ID, row count, conflicts, backfill statistics,
  and warnings match the selected result.
- Reconcile **GEMS records, physical files, eligible DART assets, and generated
  parent rows separately**. These counts need not be equal.
- Open representative URLs: original PDFs/images, thumbnails, and smalls;
  include the largest PDF and at least one compound family when present.
  A successful upload or working URL does not establish byte-level identity.

### Syllabi Coverage Gate for This Batch

GEMS reported **90 metadata rows**, while DART produced **84 rows**.
Do not treat the absence of warnings as proof that all 90 should have been
exported. Compare GEMS `collection_metadata.csv`, the publishing job's
`analysis.json`, and its handoff CSV by filename/record identity. Account for
unsupported source extensions, metadata-only records, and compound parent
construction. These are possible explanations, **not an established diagnosis**.

If expected objects were omitted, cancel the merge and investigate eligibility,
schema, or source organization. Do not invent six replacement records, rebuild
ID maps, or rerun under a fresh project to make counts match. Record the
reconciliation and any intentionally excluded material in the collection's
`Collection_Notes.md`.

## 5. Merge, Verify, and Refresh the Snapshot

**Mac DART window:**

1. Select only approved additions and field changes; preserve complete families.
2. Click **Merge Selected Changes**.
3. Verify the confirmation's core path and selections; confirm **Merge Changes**
   only when correct.
4. Wait for successful completion. Function 4 creates a backup before writing.
5. Inspect the authoritative SHOW core: row counts, IDs, families, order,
   descriptive fields, and URLs. Do not equate clicking Merge with validation.
6. Return to Function 4's **Select New CSV to Compare** dialog and click
   **Push Core Snapshot**. Verify server/project and wait for success.

The snapshot updates Linux's read-only input for future jobs; it does not
perform another merge. Do not prepare later updates for this collection until
the current core snapshot has been refreshed.

For a partially accepted package, document the unmerged records and why they
were withheld. A snapshot reflects only the accepted core; do not mark the
whole collection complete. Cancel instead of merging unexplained differences.
Never reset IDs or delete the Linux project to retry.

## 6. Validate SHOW and Record Publication Separately

Finish UI work and **quit DART normally**. Wait for Terminal A's Mac prompt.
Review `collections/COLLECTION-ID/_config.yml`: `baseurl` must match the slug,
`metadata` must match the core CSV base name, and `collection-title` must match
the catalog's intended title. In this example Baumann uses `metadata: baumann`;
the other three use their respective `_metadata` base names.

```bash
# MAC. Build one selected collection, not every collection.
(
set -eu
cd "$SHOW_REPO"
rake "collection:build[$COLLECTION_ID]"
test -f "_site/$COLLECTION_ID/index.html"
test -f "_site/$COLLECTION_ID/browse.html"
)
```

Require a successful build/Pagefind index. Inspect browse cards, compound
families, item metadata, PDFs, navigation, and search in a local preview using
SHOW's supported preview tasks. For ordinary live preview:

```bash
# MAC. Stays running until Ctrl+C; stop it before using this terminal again.
cd "$SHOW_REPO"
rake "collection:serve[$COLLECTION_ID]"
```

Open `http://127.0.0.1:4000/COLLECTION-ID/`, replacing the slug. Live Jekyll
preview is not proof of a fresh Pagefind index; use SHOW's documented
Pagefind preview procedure when validating search.

Record the batch/job IDs, accepted counts, coverage findings, unresolved issues,
merge verification, snapshot push, and build/preview result in the collection's
`Collection_Notes.md`. Update `_data/digital_collections.csv` only for verified
milestones, preserving its other fields, earlier progress, and coverage claims.
**DART success, merge success, and site publication are different milestones.**

After separate publication approval, follow SHOW's
`docs/DG-documents/Creating a New Collection (Overlay Model).md` deployment
procedure. Verify deployed pages/assets and the intended catalog
`status`/`search_index` settings; rebuild/deploy the portal when catalog changes
must become public. Do not mark a collection `published` or `COMPLETE` merely
because a headless job or local build succeeded. Do not commit generated
`_site` files, working exports, settings, or credentials.

## 7. Optional Verified Derivative Cleanup

Cleanup is optional and separate from merging. It can reclaim local derivatives
from successful publishing jobs before or after review, but cannot establish
collection acceptance. No automatic cleanup or source retirement occurs.
Do not run it alongside another managed batch/writer.

**Terminal B - Linux.** Use the exact job being cleaned, not Terminal A's
variables (which are not shared):

```bash
# LINUX. Baumann example: preview downloads Azure bytes for verification only.
cd /home/sysadmin/GitHub/DART
.venv/bin/python -m dart_linux --env-file /data/dart/config/dart.env \
  --cleanup-derivatives 02da48d276004e9fb215cd94aa92d67e
```

Review the listed paths, SHA-256 verification, byte count, and receipt.
Only after explicit approval:

```bash
# LINUX. Re-verifies Azure before removing only named local derivatives.
.venv/bin/python -m dart_linux --env-file /data/dart/config/dart.env \
  --cleanup-derivatives 02da48d276004e9fb215cd94aa92d67e --apply
```

Repeat with the other publishing IDs only when intended. Cleanup retains
originals, ID maps/settings, CSVs, handoffs, transcripts, job evidence, and batch
summaries. Receipts live under `jobs/JOB-ID/cleanup-<id>.json`. A mismatch or
unknown file stops cleanup; keep the local copy and investigate. Preview and
apply perform Azure reads and consume bandwidth. Keep corresponding Azure
blobs unchanged while verification runs.

Original reclamation requires verified Azure copies, accepted desktop results,
a fresh snapshot, and an independently verified archive. The existing GEMS
offload helper handles completed files under `migrated` only; it is not a
general cleanup command for these new run directories. See
[disk-space and cleanup safeguards](LINUX-HEADLESS-OVERVIEW.md#disk-space-guards-and-verified-cleanup).

## 8. Close the Batch and Prepare the Next Queue

For each collection, record:

- [ ] Exact successful publishing job/package identified.
- [ ] Coverage reconciled, including expected exclusions.
- [ ] Approved metadata merged and verified, or unresolved records documented.
- [ ] Updated core snapshot pushed successfully.
- [ ] SHOW build and preview checked.
- [ ] Publication state recorded accurately, with deployment separately approved.
- [ ] Optional derivative cleanup receipt retained.
- [ ] Originals, durable IDs, and review evidence retained.

One collection's unresolved issue does not prevent reviewing another successful
package. Do not call the whole batch accepted until each collection's review
outcome is recorded.

Before the next queue, check `df -h /data`, preserve the selected reserve,
confirm source approvals and current snapshots, and include only intended new
or unfinished work. Do not rerun this successful four-collection queue to
advance publication status or recover a log. Existing project/ID mappings must
be reused for any deliberate reprocessing.
