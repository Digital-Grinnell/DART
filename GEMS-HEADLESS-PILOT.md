# GEMS-to-DART Pilot: Social Justice

## Goal and Boundaries

Prepare one GEMS-complete collection on `dg-landing`, then pull a checksummed
package into desktop DART on the Mac for human comparison and merge.
**Do not run the Linux commands until installation, storage, and source access
have been approved and verified.** This runbook does not deploy DART, mount
storage, change GEMS, or execute uploads automatically.

Confirmed operator inputs:

| Item | Value |
| --- | --- |
| Collection ID | `social-justice` |
| GEMS objects on Linux | `/data/gems/data/collection-social-justice-at-grinnell-81310653130004641/2026-10-22_18-55-33_UTC/objects` |
| Azure destination | `objs/social-justice` (container `objs`, subdirectory `social-justice`) |
| Existing Mac core | None; create a collection-specific, header-only core below |

Proposed DART project: `/data/dart/data/projects/social-justice`.
The sibling GEMS `collection_metadata.csv` is a **candidate**, not a verified
path. Server deployment status, source permissions, capacity, and Azure
containers/credentials also remain unverified.

GEMS-complete does not mean DART-complete: DART still assigns/reuses IDs,
constructs compound rows, routes assets, and generates its derivatives.
Existing GEMS URLs and derivatives are not automatically adopted: GEMS backfill
protects DART identity, structure, and URL fields.

## Plan

1. Inspect Linux readiness and the small GEMS run without changing it.
2. Resolve installation/source approvals if needed.
3. Create a new Mac core containing the template's header only.
4. Configure the Mac project and push its core snapshot.
5. Configure a separate Linux project for flat GEMS compounds.
6. Prepare with GEMS backfill and derivatives, **without Azure uploads**.
7. Pull and compare on the Mac; inspect metadata, families, IDs, and warnings.
   Do not merge this rehearsal package.
8. After explicit Azure approval, prepare again using the **same Linux project**,
   pull the new package, and selectively merge it on the Mac.
9. Push the updated core snapshot and retain the Linux ID map and job evidence.

## 1. Inspect dg-landing from the Mac

This block only inspects the server. It does not initialize or repair anything.
It can fail when installation is incomplete; retain the output and stop.

```bash
ssh -o BatchMode=yes sysadmin@dg-landing 'bash -s' <<'LINUX'
set -eu
RUN=/data/gems/data/collection-social-justice-at-grinnell-81310653130004641/2026-10-22_18-55-33_UTC
id
findmnt -T "$RUN/objects"
df -h "$RUN/objects" /data
ls -ld "$RUN" "$RUN/objects"
find "$RUN" -maxdepth 2 -type f -name '*.csv' -print
find "$RUN/objects" -mindepth 1 -maxdepth 1 -type d ! -name '.*' -print
ls -ld /data/dart/config /data/dart/data \
  /data/dart/data/projects /data/dart/data/jobs
ls -l /data/dart/config/dart.env \
  /data/dart/config/.dart-storage /data/dart/data/.dart-storage
cd /home/sysadmin/GitHub/DART
git branch --show-current
test -x .venv/bin/python
.venv/bin/python -m dart_linux --help
LINUX
```

Confirm that this is the intended GEMS run and that its objects are organized
one intellectual object per subfolder. Review the CSV listing to identify the
cumulative GEMS metadata file; do not use the Mac core as the GEMS input.
Do not reorganize or rename GEMS assets for this pilot. Stop GEMS writes to
this run while DART scans it, through the normal operator workflow.

If anything is missing, follow [Installation](INSTALL-LINUX.md) and
[Acceptance Testing](LINUX-ACCEPTANCE.md) with the necessary approvals first.
The installed revision must include headless `prepare` and desktop SSH handoff;
an old checkout or a successful `--help` alone does not establish readiness.

An administrator must approve read access and add the GEMS run to
`DART_SOURCE_ROOTS` in the private environment file. Its allowlist `path`
should cover both `objects/` and the metadata CSV; its `mount` must be the
actual mount point verified with `findmnt`, not an assumed `/data`.
DART enforces its own no-source-write boundary; an administrator-managed
read-only mount provides additional protection. Do not change GEMS ownership,
permissions, mounts, or service configuration to make DART work.

## 2. Create the Mac Core

The following is a proposed local location, not a fully scaffolded SHOW
collection. It creates only the metadata directory and core CSV. It does not
configure or publish a CollectionBuilder site.

Run on the **Mac**, after confirming the proposed destination:

```bash
cd /Users/mcfatem/GitHub/DART
.venv/bin/python - <<'PY'
import csv
from pathlib import Path

template = Path("/Users/mcfatem/GitHub/SHOW/collections/_collection-template/_data/collection-template.csv")
target = Path("/Users/mcfatem/GitHub/SHOW/collections/social-justice/_data/social-justice_metadata.csv")
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
```

Exclusive creation (`"x"`) refuses to overwrite an existing core. If it exists,
inspect it instead of deleting it or rerunning a replacement command. Never
merge into `collection-template.csv`. Creating an empty core is appropriate
only for a collection with no established DART core; if an older core or ID map
is discovered, stop and review identifier migration before proceeding.

## 3. Create the Linux Project and Push the Snapshot

After storage readiness is confirmed, run on the **Mac**:

```bash
ssh -o BatchMode=yes sysadmin@dg-landing \
  'umask 077; mkdir -m 700 /data/dart/data/projects/social-justice'
```

This deliberately fails if the project already exists. Inspect an existing
project and its mappings; do not remove or recreate it.

In **desktop DART Function 0**, select a dedicated Mac Working/Outputs folder
for this pilot and save:

| Setting | Value |
| --- | --- |
| `collection-id` | `social-justice` |
| `core_metadata_csv` | `/Users/mcfatem/GitHub/SHOW/collections/social-justice/_data/social-justice_metadata.csv` |
| `headless_host` | `sysadmin@dg-landing` |
| `headless_project_dir` | `/data/dart/data/projects/social-justice` |
| `azure_blob_storage_path` | `objs/social-justice` |
| `gems_metadata_csv` | Blank on the Mac; server backfill supplies the metadata |
| `group_compound_objects` | `true` |
| `create_multiple_objects` | `false` |
| `process_OHM_data` | `false` |

The Mac does not need the Linux objects mounted, nor should it run Functions
1–3 against an unrelated local Inputs Folder.

For this first run, there is no local export yet. Function 4 opens the pull
dialog directly, which currently has no snapshot-push button. Bootstrap the
snapshot from a **Mac terminal** using DART's existing SSH transfer helper:

```bash
cd /Users/mcfatem/GitHub/DART
.venv/bin/python - <<'PY'
from dart_handoff import push_core_snapshot

checksum = push_core_snapshot(
    "sysadmin@dg-landing",
    "/data/dart/data/projects/social-justice",
    "/Users/mcfatem/GitHub/SHOW/collections/social-justice/_data/social-justice_metadata.csv",
)
print(f"Core snapshot pushed; SHA-256: {checksum}")
PY
```

Confirm success before continuing. Once a local export has been pulled,
the normal Function 4 file-selection dialog offers **Push Core Snapshot**.

## 4. Configure the Linux Pilot

Open a Linux session:

```bash
ssh sysadmin@dg-landing
```

Run the following **on Linux**. Replace the candidate `GEMS` path if inspection
found the CSV elsewhere. These commands create private JSON inputs, not
credentials. They refuse to overwrite existing input files.

```bash
(
set -eu
umask 077
cd /home/sysadmin/GitHub/DART
WORK=/data/dart/data/projects/social-justice
RUN=/data/gems/data/collection-social-justice-at-grinnell-81310653130004641/2026-10-22_18-55-33_UTC
GEMS="$RUN/collection_metadata.csv"
test -d "$RUN/objects"
test -r "$GEMS"
test -r "$WORK/core-snapshot.csv"
set -C
cat > /data/dart/config/settings-social-justice.json <<JSON
{
  "working_dir": "$WORK",
  "input_dir": "$RUN/objects",
  "collection-id": "social-justice",
  "core_metadata_csv": "$WORK/core-snapshot.csv",
  "gems_metadata_csv": "$GEMS",
  "azure_blob_storage_path": "objs/social-justice",
  "group_compound_objects": true,
  "create_multiple_objects": false,
  "process_OHM_data": false
}
JSON
cat > /data/dart/config/prepare-social-justice-review.json <<JSON
{
  "working_dir": "$WORK",
  "input_dir": "$RUN/objects",
  "derivatives": true,
  "backfill": true,
  "allow_uploads": false,
  "overwrite": false
}
JSON
.venv/bin/python -m dart_linux --env-file /data/dart/config/dart.env \
  --configure --inputs /data/dart/config/settings-social-justice.json
)
```

`--configure` validates the source allowlist, CSVs, schema, and collection ID.
If it fails, resolve the reported error before submitting a job. Do not change
the collection ID or relocate assets to bypass validation.

## 5. Prepare Without Uploads

Run **on Linux** in the foreground; keep SSH connected until it finishes:

```bash
cd /home/sysadmin/GitHub/DART
.venv/bin/python -m dart_linux --env-file /data/dart/config/dart.env \
  --job prepare --inputs /data/dart/config/prepare-social-justice-review.json
```

This exports, generates local derivatives, backfills GEMS metadata, and creates
a handoff package. It also **persists durable IDs**, even without uploads.
Record the printed job ID. Exit 0 and job state `succeeded` are required.
Retain `/data/dart/data/jobs/JOB-ID/` and the project settings/ID map.
On failure, inspect the reported evidence; do not delete mappings to retry.

Backfill fills only blank cells in columns present in the core schema.
Review `gems-backfill.json` for unmatched rows, duplicate GEMS filenames, and
ignored columns. A successful job does not prove complete descriptive metadata.
Duplicate asset basenames across subfolders must be resolved deliberately:
Function 4 requires unique `original_file_name` keys.

## 6. Review on the Mac Without Merging

1. Open the matching desktop project and **Function 4**.
2. Click **Pull From Headless DART...** and select the recorded job ID.
3. Check row counts, collection ID, backfill results, and manifest warnings.
4. Compare with the new core. An empty core should show additions only.
5. Inspect titles, descriptive metadata, one parent per compound folder,
   flat child relationships, ordering, and standalone files.
6. **Do not click Merge Selected for this rehearsal.** Local derivative paths
   are expected and are not publishable URLs; derivatives are not pulled to
   the Mac. Original `object_location` cells are also empty without uploads.

Stop on ID conflicts, missing metadata, unexpected compounds, duplicate keys,
or a stale snapshot warning. Correct the inputs/configuration deliberately and
rerun using the same project so assigned IDs survive. Do not change grouping
or asset paths after assigning IDs without reviewing the mapping consequences.

## 7. Optional Approved Azure Run

Only after the rehearsal is satisfactory and uploads are explicitly approved:

- Confirm the private Linux environment file holds the authorized Azure
  connection string. Never put it in JSON inputs, Git, or shell history.
- Confirm `objs` and the parallel derivative containers already exist and
  that DART's destination conventions are approved; see
  [Function 3](FUNCTION_3_GENERATE_DERIVATIVES.md).
- Retain the same project, collection ID, source paths, and ID map.
- Push a fresh snapshot first if the Mac core has changed.

Run **on Linux**:

```bash
(
set -eu
umask 077
cd /home/sysadmin/GitHub/DART
set -C
cat > /data/dart/config/prepare-social-justice-publish.json <<'JSON'
{
  "working_dir": "/data/dart/data/projects/social-justice",
  "input_dir": "/data/gems/data/collection-social-justice-at-grinnell-81310653130004641/2026-10-22_18-55-33_UTC/objects",
  "derivatives": true,
  "backfill": true,
  "allow_uploads": true,
  "overwrite": false
}
JSON
.venv/bin/python -m dart_linux --env-file /data/dart/config/dart.env \
  --job prepare --inputs /data/dart/config/prepare-social-justice-publish.json
)
```

This is the first block that authorizes Azure writes. Existing blobs are
skipped, not replaced; skipping is not a content-integrity check. Review an
unexpected existing blob rather than automatically enabling overwrite.

## 8. Pull, Merge, and Close the Loop

On the **Mac**, pull the successful publishing job, not the rehearsal job.
Confirm the selected export belongs to the new job and has approved HTTPS
`object_location`, `image_small`, and `image_thumb` values where applicable.
Review any asset types without derivatives individually.

Use Function 4 to compare and selectively merge the approved rows/fields.
Review complete families together. Existing core rows retain their order;
selected additions follow the prepared export's order. Function 4 creates a
backup before changing the core. Then **Push Core Snapshot** again.

Headless processing and handoff do **not** retire GEMS folders into `.complete`.
Leave GEMS sources intact; track completed job IDs and merged batches yourself.
Keep the Linux project and ID map for retries and later batches. Do not scan
the same run under a fresh project or point DART directly into `.complete`.
Publishing the CollectionBuilder site remains a separate workflow.

## Validation Status

The commands are based on the repository's implemented CLI and handoff
workflow. No server deployment, source scan, Azure upload, Mac core creation,
or merge was executed while writing this runbook. Actual server readiness,
the candidate GEMS CSV path, and end-to-end operation must be verified by
following the gated steps above.
