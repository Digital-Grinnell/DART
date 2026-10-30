# October 29 Overnight Batch: Launch and Follow-Up

## What Is Ready

The approved **publishing** queue contains the 15 collections below, in the
requested order. It is staged on `dg-landing` but **has not been started**.

- Azure uploads: **on**, explicitly approved for all 15 without separate
  collection rehearsals.
- Overwrite existing Azure files: **off**.
- GEMS backfill and derivatives: **on**.
- Compound grouping: **on**, flat children (`create_multiple_objects=false`).
- OHM processing: **off**.
- Free-space reserve: **50 GiB**.
- Automatic cleanup, original offload, desktop merges, SHOW publishing: **none**.

All 15 authoritative SHOW cores were header-only with matching schemas at
staging. Exact GEMS source runs have been approved while preserving the previous
allowlist and other environment settings. Linux projects will be created during
the batch; staging did not assign IDs or create those projects.

### Staged Server Files

| File Under `/data/dart/config/` | Purpose |
| --- | --- |
| `overnight-20261029.json` | Approved queue; do not edit during execution |
| `overnight-20261029-core-template.csv` | Header-only schema matching the 15 Mac cores |
| `overnight-20261029-inventory.json` | Exact source runs, source counts, exclusions, and sizes |
| `launch-overnight-20261029.sh` | One-time systemd launcher with preflight checks |

The private environment backup `dart.env.before-overnight-20261029` contains
credentials. Leave it private on the server; do not copy it into Git or share it.

### Collection Review Ledger

Counts below describe sources, **not final DART export rows**. Compound parents
can increase row counts; unsupported material is not ingested. Take actual job
IDs, final row counts, warnings, and conflicts from the completed batch summary.
All core filenames are relative to the Mac SHOW repository.

| Order | Collection ID | GEMS Rows | Source Files | Eligible Assets | Core CSV |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | `faculty-scholarship` | 220 | 205 | 177 | `collections/faculty-scholarship/_data/faculty-scholarship_metadata.csv` |
| 2 | `handbooks` | 15 | 15 | 15 | `collections/handbooks/_data/handbooks_metadata.csv` |
| 3 | `lawrence` | 54 | 54 | 54 | `collections/lawrence/_data/lawrence_metadata.csv` |
| 4 | `cook` | 322 | 290 | 290 | `collections/cook/_data/cook_metadata.csv` |
| 5 | `grinnell-and-you` | 203 | 203 | 203 | `collections/grinnell-and-you/_data/grinnell-and-you_metadata.csv` |
| 6 | `buildings` | 363 | 264 | 264 | `collections/buildings/_data/buildings_metadata.csv` |
| 7 | `grinnell-in-china` | 90 | 62 | 62 | `collections/grinnell-in-china/_data/grinnell-in-china_metadata.csv` |
| 8 | `beaton` | 264 | 260 | 260 | `collections/beaton/_data/beaton_metadata.csv` |
| 9 | `stella` | 66 | 66 | 66 | `collections/stella/_data/stella_metadata.csv` |
| 10 | `kleinschmidt` | 196 | 138 | 138 | `collections/kleinschmidt/_data/kleinschmidt_metadata.csv` |
| 11 | `military` | 19 | 19 | 19 | `collections/military/_data/military_metadata.csv` |
| 12 | `new-students` | 30 | 30 | 30 | `collections/new-students/_data/new-students_metadata.csv` |
| 13 | `scarlet-black` | 417 | 417 | 417 | `collections/scarlet-black/_data/scarlet-black_metadata.csv` |
| 14 | `social-gospel` | 104 | 72 | 72 | `collections/social-gospel/_data/social-gospel_metadata.csv` |
| 15 | `underground` | 27 | 27 | 27 | `collections/underground/_data/underground_metadata.csv` |

Totals: **2,122 source files**, **2,094 eligible assets**, about **57.5 GiB**
of already-present sources. DART does not duplicate that entire source tree.
There was about **223.4 GiB free** at preparation, leaving roughly 173 GiB
above the reserve. This is not a prediction of runtime or conversion space:
the guard can still stop the batch, and other writers can consume disk.

## 1. Start Tonight on Terminal B

**Terminal B is an SSH session on dg-landing, not the Mac prompt.**
From a Mac terminal, connect first:

```bash
# MAC: opens the Linux shell for Terminal B.
ssh sysadmin@dg-landing
```

Then paste this **at the Linux prompt**:

```bash
# LINUX: starts the approved publishing batch.
bash /data/dart/config/launch-overnight-20261029.sh
```

The script checks its host/account, paths, queue, source approvals, space, and
whether this exact queue already has batch evidence. It requires your `sudo`
authorization to create system service **`dart-overnight-20261029`**. Do not
run the script with `sudo bash`: it expects the storage owner, `sysadmin`.
Do not pull code, change configuration, or edit sources while it is running.

### Verify the Launch Before Disconnecting

**Terminal B - Linux:**

```bash
sudo systemctl status dart-overnight-20261029 --no-pager -l
sudo journalctl -u dart-overnight-20261029 -n 40 --no-pager
df -h /data
```

Require a running service and the journal's **`Batch:`** and **`Summary:`**
lines. Record that exact batch ID/path for tomorrow. A fast-completing service
may already be inactive: inspect its exit status and summary instead. A
successful `systemd-run` submission alone does not establish a healthy batch.

Optional live viewing:

```bash
# LINUX: stays open until Ctrl+C; Ctrl+C stops the viewer, not the batch.
sudo journalctl -fu dart-overnight-20261029
```

Once readiness is verified, you may disconnect SSH, put the Mac to sleep, or
disconnect VPN. The system service runs on Linux; neither desktop DART nor
DGIngest needs to remain mounted. This launcher does not use a recurring timer
or an automatic restart loop.

To stop processing deliberately, use:

```bash
# LINUX: requests cooperative cancellation; wait for the service to stop.
sudo systemctl stop dart-overnight-20261029
```

## 2. Inspect Results Tomorrow

**Terminal B - Linux.** Replace `REPLACE_WITH_BATCH_ID` with the actual ID from
the launch journal:

```bash
export BATCH_ID='REPLACE_WITH_BATCH_ID'
python3 -m json.tool "/data/dart/data/batches/$BATCH_ID/summary.json"
sudo journalctl -u dart-overnight-20261029 -n 60 --no-pager
df -h /data
```

- Exit `0`: all entries succeeded; human review is still required.
- Exit `1`: some failed; successful packages remain reviewable.
- Exit `75`: free-space guard blocked further processing. Preserve partial
  outputs and requeue only unfinished entries after resolving space.
- Exit `130`: cancelled; inspect which entries finished.

Do not rerun this whole queue to recover a failure or fetch a package. The
launcher refuses an exact repeat once batch evidence exists. Build a separately
named retry queue for only failed/interrupted/pending collections, reusing
their projects/settings and permanent IDs.

## 3. Launch the Correct Mac Review Project

> **WORKING/OUTPUTS FOLDER FIRST. FUNCTION 0 SECOND.**
> The shell block prints settings but does **not** enter them into DART.
> In the DART main window select the printed Working/Outputs folder **before
> opening Function 0**. Changing folders loads different settings; it does not
> transfer your entries. Repeat this order for every collection.

**Terminal A - Mac.** Start `bash` once if not already using Bash. For each
collection, paste the **whole block** below, changing only `COLLECTION_ID`
and `BATCH_ID` at the top. The remaining paths recompute automatically. Unlike
the afternoon example, all 15 cores use `<collection-id>_metadata.csv`.
Do not use the afternoon's job IDs.

```bash
# MAC: select one collection, fetch its actual successful job ID, and launch.
(
set -eu
COLLECTION_ID='faculty-scholarship'
BATCH_ID='REPLACE_WITH_BATCH_ID'
case "$COLLECTION_ID" in
  faculty-scholarship|handbooks|lawrence|cook|grinnell-and-you|buildings|grinnell-in-china|beaton|stella|kleinschmidt|military|new-students|scarlet-black|social-gospel|underground) ;;
  *) printf 'ERROR: Collection is not in this overnight queue.\n' >&2; exit 1 ;;
esac
if [[ ! "$BATCH_ID" =~ ^[0-9a-f]{32}$ ]]; then
  printf 'ERROR: Replace BATCH_ID with the 32-character ID from the overnight journal.\n' >&2
  exit 1
fi
MAC_DART="$HOME/GitHub/DART"
MAC_CORE="$HOME/GitHub/SHOW/collections/$COLLECTION_ID/_data/${COLLECTION_ID}_metadata.csv"
MAC_WORK="$HOME/DART-projects/$COLLECTION_ID"
LINUX_PROJECT="/data/dart/data/projects/$COLLECTION_ID"
printf 'Collection: %s\nCore: %s\n' "$COLLECTION_ID" "$MAC_CORE"
printf 'STOP: Printed settings are NOT applied automatically.\n'
printf 'FIRST select Working/Outputs: %s\n' "$MAC_WORK"
printf 'ONLY THEN open Function 0, save the settings below, and proceed to Function 4.\n'
printf 'collection-id: %s\nheadless_host: sysadmin@dg-landing\nheadless_project_dir: %s\n' "$COLLECTION_ID" "$LINUX_PROJECT"
if [ ! -r "$MAC_CORE" ]; then
  printf 'ERROR: Core CSV missing/unreadable: %s\n' "$MAC_CORE" >&2
  exit 1
fi
mkdir -p "$MAC_WORK/.DART-working-directory"
SUMMARY="$MAC_WORK/.DART-working-directory/overnight-20261029-summary.json"
if ! scp -o BatchMode=yes -o ConnectTimeout=15 \
  "sysadmin@dg-landing:/data/dart/data/batches/$BATCH_ID/summary.json" "$SUMMARY"; then
  printf 'ERROR: Cannot fetch this batch summary; check ID and SSH/VPN.\n' >&2
  exit 1
fi
JOB_ID=$(python3 - "$SUMMARY" "$COLLECTION_ID" "$BATCH_ID" <<'PY'
import json, re, sys
summary = json.load(open(sys.argv[1]))
if summary["id"] != sys.argv[3]:
    raise SystemExit("ERROR: Unexpected batch ID in summary")
entries = [r for r in summary["collections"] if r["collection_id"] == sys.argv[2]]
if len(entries) != 1 or entries[0]["state"] != "succeeded":
    raise SystemExit("ERROR: This collection has no successful package in this batch")
job = entries[0]["job_id"]
if not re.fullmatch(r"[0-9a-f]{32}", job):
    raise SystemExit("ERROR: Invalid job ID")
print(job)
PY
)
printf '\nPULL THIS EXACT PUBLISHING JOB: %s\n' "$JOB_ID"
cd "$MAC_DART" || { printf 'ERROR: Cannot enter the DART checkout.\n' >&2; exit 1; }
if [ ! -x .venv/bin/python ] || [ ! -r app.py ]; then
  printf 'ERROR: DART checkout/interpreter is unavailable.\n' >&2
  exit 1
fi
.venv/bin/python app.py
)
```

Terminal A stays occupied until you quit DART. Do not paste shell commands into
it while the window is running. This block does not rerun any server job.

### Enter Settings in This Order

1. **FIRST:** main window -> **Working/Outputs Folder -> Browse...** -> the
   printed `~/DART-projects/COLLECTION-ID` path. Verify the displayed path.
2. **SECOND:** open **Function 0**, enter/verify and save:
   - `collection-id`: the selected slug.
   - `core_metadata_csv`: the printed SHOW core.
   - `headless_host`: `sysadmin@dg-landing`.
   - `headless_project_dir`: printed Linux project path.
   - `gems_metadata_csv`: **blank**; Linux already backfilled.
   - `group_compound_objects=true`, `create_multiple_objects=false`,
     `process_OHM_data=false`.
3. **THIRD:** keep that folder selected, uncheck **Help Mode**, and choose
   **4: Compare and Merge CSV Files**. No separate execute button.
4. **Pull From Headless DART...** -> select the **exact printed job ID** ->
   **Pull For Review**. Confirm collection, row count, warnings, and conflicts.

If you entered settings before changing folders, reopen Function 0 after
selecting the correct folder and save them there again.

## 4. Review, Merge, and Refresh Each Snapshot

Use the detailed [post-batch review runbook](BATCH-DART-FOLLOW-UP.md#4-compare-and-reconcile-coverage-before-merging),
but use **this overnight summary's IDs and this document's core paths**, not
the four-collection afternoon table.

- Keep desktop GEMS backfill and move-to-`.complete` options **off**.
- Compare the exact pulled CSV. For a still-header-only core, expect all package
  rows as additions, zero changed records, and zero missing records.
- Inspect complete compound families, filenames, descriptive metadata, and
  representative original/derivative URLs. A successful job is not coverage
  acceptance or proof of byte-identical Azure copies.
- Reconcile GEMS records, eligible assets, excluded files, and generated parent
  rows separately. Record exclusions/unresolved issues in `Collection_Notes.md`.
- Select approved changes -> **Merge Selected Changes** -> confirm **Merge
  Changes** -> verify the actual core and backup.
- **Push Core Snapshot** and wait for success before later jobs for that
  collection.
- Quit DART before pasting the Mac launch block for the next collection.

### Known Coverage Gates

**Faculty Scholarship:** 205 physical files, 177 eligible assets, 220 GEMS rows.
There are **28 excluded files**, including WARC/binary/spreadsheet/compressed
and other non-asset formats. The empty
`grinnell_23326/grinnell_23326-08.bin` is among those exclusions, not an eligible
PDF/image. DART may upload supported video/archive formats without generating
image derivatives. Review export warnings and the inventory's exclusions;
do not claim a complete collection migration based only on job success.
No unsupported/empty source has been removed or repaired.

**Scarlet & Black:** the selected normalized source run is
`2026-10-22_19-58-47_UTC-grinnell-203709`, not the sibling unsuffixed run.
Both contain the same set of 417 PDF SHA-256 contents, but the unsuffixed CSV
lacks `original_file_name`. Use only the selected run and its corresponding
metadata for this batch; do not process both or combine their mappings.

**Compound-heavy collections:** Cook, Buildings, Grinnell in China,
Kleinschmidt, and Social Gospel need particular parent/child coverage review.
Beaton's 264 metadata rows versus 260 files also requires reconciliation.
The inventory counts are not guarantees of expected final row counts.

## 5. SHOW Validation, Publication, and Storage

For each accepted core, verify `_config.yml` uses the selected slug and
`metadata: <slug>_metadata`. Build/preview the selected collection, review
compound navigation and assets, and record actual progress in
`Collection_Notes.md` and SHOW's `_data/digital_collections.csv`. Publication,
catalog/search enablement, and portal deployment remain separate decisions.
See [SHOW follow-up](BATCH-DART-FOLLOW-UP.md#6-validate-show-and-record-publication-separately).

Do not automatically repeat the afternoon's original-file verification waiver.
This queue deletes nothing. Local derivative cleanup can be previewed later
for exact successful publishing IDs using the existing Azure-verifying command.
Original deletion requires a separately approved scope and archive/verification
decision. There is no dependency on tonight's partial DGIngest archive.

For each of the 15 collections record: exact batch/job, warnings/conflicts,
coverage disposition, accepted merge count, snapshot push, SHOW validation,
publication state, and any separately approved cleanup receipt.
