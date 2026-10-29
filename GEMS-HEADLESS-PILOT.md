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

For multiple collections, use
[Overnight Collection Batches](LINUX-HEADLESS-OVERVIEW.md#overnight-collection-batches).
That mode can set up new Linux projects from a staged header-only schema,
prepare collections sequentially in a disconnect-safe system service, and
leave per-collection packages and a durable summary for next-day desktop
review. It does not automate the rehearsal approval, publishing approval,
Mac core creation, or merge gates below.

## Execution Map

**Yes: one local Mac terminal and one SSH terminal are enough. In fact, this
runbook requires only the local Mac terminal, plus the DART desktop window.**
Use these names throughout:

- **Terminal A - Mac:** a local shell on the Mac, **not** a shell logged into
  Linux. Paste **every `bash` block in this document here**, including blocks
  beginning with `dart_remote`. Keep this terminal open to preserve Step 0's
  variables and helper.
- **Terminal B - SSH (optional):** a separate terminal logged into Linux.
  You may use it for independent, approved inspection, but **none of this
  runbook's blocks belongs here**. It does not inherit Terminal A's variables
  or helper. It need not stay connected for Terminal A's jobs to run.
- **Mac DART window:** the graphical application launched from Terminal A.
  Perform instructions labeled **Mac desktop** in that window, not in a shell.

**Before Step 0, at Terminal A's local Mac prompt, run `bash` once.** Use that
same Bash shell for the entire runbook. This makes the shell-block comments
and helper behavior consistent even if your normal Mac shell is Zsh. Do not
start a new shell or run `exit` between steps; leaving this Bash shell loses
its helper and variable definitions.

**"Linux via SSH" describes where commands execute, not where you paste them.**
`dart_remote <<'LINUX'` starts a temporary SSH connection from Terminal A;
the helper runs the lines through the closing `LINUX` on Linux. Paste the
**whole block**, including both delimiter lines, into Terminal A. Do not copy
only the middle lines or add an interactive `ssh` session in Terminal A.

| Step | Paste Shell Blocks Into | Actual Execution | Effect |
| --- | --- | --- | --- |
| 0 | Terminal A - Mac | Mac | Define reusable variables and an SSH helper; no server changes |
| 1 | Terminal A - Mac | Linux via SSH | Inspect readiness and sources; no changes |
| 2 | Terminal A - Mac | Mac | Create a header-only core for a genuinely new collection |
| 3 | Terminal A - Mac | Linux via SSH, then Mac | Create a private Linux project, configure Mac DART, push snapshot |
| 4 | Terminal A - Mac | Linux via SSH | Create private JSON inputs and configure Linux DART |
| 5 | Terminal A - Mac | Linux via SSH | Prepare without uploads; **persists durable IDs** |
| 6 | Terminal A - Mac for launch only | Mac desktop | Pull, compare, inspect, and cancel; **do not merge** |
| 7 | Terminal A - Mac | Linux via SSH | After separate approval, prepare with **Azure uploads** |
| 8 | Terminal A - Mac if relaunch/push needed | Mac desktop | Pull the publishing job, selectively merge, push updated snapshot |

### Process Lifetimes and Prompt Rules

| Command or Activity | Must It Remain Running? | When to Continue |
| --- | --- | --- |
| Step 0 variables and helper definition | No background process starts. Keep Terminal A's shell open to retain them. | The local Mac prompt returns immediately. |
| Step 1 inspection, Step 2 core creation, Step 3.1 `mkdir`, Step 3.3 snapshot push, Step 4 configuration | No. Each is a one-shot command and should exit. | Wait for the local Mac prompt and require success before the next step. |
| `.venv/bin/python app.py` in Steps 3.2 and 6.1 | **Yes, while using the Mac DART window.** It occupies Terminal A in the foreground. | Save/finish the specified desktop work, quit DART normally, and wait for the local Mac prompt before pasting another shell block. |
| `--job prepare` in Steps 5 and 7 | **Yes, until the Linux job finishes.** Leave Terminal A, its foreground SSH connection, the Mac, and network available; prevent sleep/disconnection. | Wait for the final job result, state `succeeded`, exit status `0`, and the local Mac prompt. Silence alone is not completion. |
| Optional Terminal B SSH session | No. It is not the SSH connection used by `dart_remote`. | Closing it does not finish or cancel Terminal A's command. |

**Never paste the next block while Terminal A is occupied by DART or a job.**
Do not use Ctrl-C to reclaim it during a job, pull, snapshot push, or merge.
Do not close Terminal A or background a command to skip a wait. This runbook
does not use a persistent Linux daemon, web server, or SSH tunnel that you
must leave running between steps.

After each one-shot shell block, inspect errors. If the exit status is unclear,
run `echo $?` in **Terminal A immediately after the block**, before another
command; `0` means the shell command succeeded, not that review gates passed.
Stop on a nonzero result.

Never delete or recreate a project or ID map to retry. Once IDs have been
assigned, reuse the same project, collection ID, source paths, and grouping.

## 0. Define Values Once on the Mac

### 0.1 Collection and Installation Variables

Edit the values in this block **once** before running it. The two
`REPLACE_...` values are required inputs, not working examples. Defaults for
installation paths and the SSH account must also match your approved setup.
Use absolute paths; do not put credentials in any variable.

```bash
# PASTE INTO TERMINAL A - MAC. One-shot setup; wait for the Mac prompt.
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
# PASTE INTO TERMINAL A - MAC. Defines a helper; no SSH session stays running.
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

**Paste into Terminal A - Mac; executes on Linux via SSH; inspection only.**
Wait for the local Mac prompt before Step 2. Missing paths or an incomplete
installation can make this block fail. Retain the output and stop rather
than repairing anything implicitly.

```bash
# PASTE INTO TERMINAL A - MAC, including the dart_remote and LINUX lines.
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

**Terminal A - Mac; executes locally; one-shot.** For a genuinely new
collection, initialize the SHOW overlay **together**: a header-only core CSV,
a populated `_config.yml`, and populated `Collection_Notes.md`, using
`SHOW/collections/_collection-template/`. The helper also updates the matching
row in `SHOW/_data/digital_collections.csv`. It uses that row's title, preserves
description/audit fields and existing progress text, and updates the progress
date/status to **SHOW initialized; DART review/merge pending**. It does not mark
the collection complete or published.

The helper lives in SHOW's `scripts/initialize_collection.rb`; update the SHOW
checkout to a revision containing it before using this step. Preview first:

```bash
# PASTE INTO TERMINAL A - MAC. Preview only; no files are changed.
(
set -eu
ruby "$SHOW_REPO/scripts/initialize_collection.rb" \
  --slug "$COLLECTION_ID" --metadata-name "${COLLECTION_ID}_metadata"
)
```

Confirm the planned CSV path equals `MAC_CORE`, then apply the same plan:

```bash
# PASTE INTO TERMINAL A - MAC ONLY AFTER REVIEWING THE PREVIEW.
(
set -eu
test "$MAC_CORE" = "$SHOW_REPO/collections/$COLLECTION_ID/_data/${COLLECTION_ID}_metadata.csv"
ruby "$SHOW_REPO/scripts/initialize_collection.rb" \
  --slug "$COLLECTION_ID" --metadata-name "${COLLECTION_ID}_metadata" --apply
)
```

If the catalog row is missing (or its title is blank), add `--title 'Actual
Collection Title'` to **both** commands. A new row is created as `draft` with
`search_index=FALSE`; collection description, images, migration classification,
and coverage claims are not invented. Existing catalog publication/search
settings are preserved. Published collections' progress is not downgraded.

**Existing collection:** inspect the established core and ID mapping, set
`MAC_CORE` to that core, and review migration/snapshot compatibility. The helper
can fill in missing companion files without changing an existing CSV, config,
or notes, but use the core's **actual base name** with `--metadata-name`.
Conflicting config identity, duplicate catalog matches, symlinked paths, or a
different existing metadata CSV cause an error rather than silent replacement.
Once initialized, reruns are no-ops; subsequent review progress is not reset.
Never delete a populated core or ID map to make initialization succeed.
Never merge into `collection-template.csv`.

## 3. Connect the Desktop Project and Push a Snapshot

### 3.1 Create a New Linux Project

**Paste into Terminal A - Mac; executes on Linux via SSH**, only after
readiness approval. This is a one-shot directory creation, **not** a running
service. It should return to the local Mac prompt immediately:

```bash
# PASTE INTO TERMINAL A - MAC, including the dart_remote and LINUX lines.
dart_remote <<'LINUX'
umask 077
mkdir -m 700 "$WORK"
LINUX
```

This deliberately fails if the project exists. For a retry or existing project,
inspect its settings and mappings, then reuse it; do not remove or recreate it.
Running this **whole block on the Mac is correct**, not a mistake. It does not
configure the external GEMS source allowlist.

### 3.2 Configure Mac DART

> **STOP: WORKING/OUTPUTS FOLDER FIRST, FUNCTION 0 SECOND.**
> The launch block only prints guidance; it does **not** configure DART.
> After launch, select the printed Working/Outputs folder in the main window
> **before opening Function 0**. Settings are per folder. Switching folders
> loads that folder's settings instead of transferring what you just entered.
> Repeat this order every time you change collections.

**Terminal A - Mac; executes locally, then holds the terminal while DART is
open.** Create the dedicated output folder and print the actual
values to enter in Function 0; no collection values need retyping in code.

```bash
# PASTE INTO TERMINAL A - MAC. Leave this process running during desktop setup.
(
set -eu
mkdir -p "$MAC_WORK"
printf 'Working/Outputs folder: %s\n' "$MAC_WORK"
printf 'STOP: Printed values do NOT configure DART.\nFIRST select the Working/Outputs folder above; ONLY THEN open Function 0 and save settings.\n'
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
**No shell prompt while DART is open is normal.** Do not paste Step 3.3 yet.
Leave Terminal A and its Python process running while configuring DART.

In the **main DART window**, select the printed **Working/Outputs Folder
FIRST**. **ONLY THEN open Function 0**, enter/verify and save the printed
settings, plus:

| Setting | Value |
| --- | --- |
| `gems_metadata_csv` | Blank on the Mac; Linux performs backfill |
| `group_compound_objects` | `true` |
| `create_multiple_objects` | `false` |
| `process_OHM_data` | `false` |

The Mac does not need the Linux objects mounted. Do not run desktop Functions
1-3 against unrelated local inputs. Selecting another Working/Outputs folder
can load another collection's settings.

**Before Step 3.3:** save Function 0 settings, then quit the Mac DART
application normally. Wait for Terminal A's local Mac prompt. Closing DART
here is intentional: it frees the same terminal for the snapshot command.
Do **not** close the terminal itself. No Linux process from Step 3.1 needs
to remain running. DART will be relaunched in Step 6.1.

### 3.3 Push the Core Snapshot

With no local export yet, Function 4 opens the pull dialog directly; that
dialog currently has no snapshot-push button. Bootstrap from **Terminal A -
Mac**, using the same definitions. DART must be closed and the
local shell prompt visible. This one-shot command connects to Linux, pushes
the snapshot, and exits:

```bash
# PASTE INTO TERMINAL A - MAC after quitting DART normally.
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

**Paste into Terminal A - Mac; executes on Linux via SSH; one-shot.**
Wait for successful configuration and the local Mac prompt before Step 5.
This creates private JSON inputs, not credentials. Python
serializes the variables as JSON, including paths containing spaces or quotes.
Existing JSON files are not overwritten.

```bash
# PASTE INTO TERMINAL A - MAC, including the dart_remote and LINUX lines.
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

**Retry configuration with existing, verified JSON:** paste this complete
block into **Terminal A - Mac**, with Mac DART closed and the local prompt
visible. It runs on Linux and exits; it does not start a job:

```bash
# PASTE INTO TERMINAL A - MAC. Configure existing inputs only; no job.
dart_remote <<'LINUX'
cd "$DART_REPO"
test -r "$CONFIG/settings-$COLLECTION_ID.json"
.venv/bin/python -m dart_linux --env-file "$CONFIG/dart.env" \
  --configure --inputs "$CONFIG/settings-$COLLECTION_ID.json"
LINUX
```

### Source Allowlist Error and Interrupted-Session Recovery

If configuration or a job reports:

```text
DART startup/job error: Source must be inside a DART project or an explicitly approved source mount.
```

**Stop before submitting/retrying a job.** The rejected source path is outside
the managed projects tree and every configured `DART_SOURCE_ROOTS` entry.
This can be the objects directory, the GEMS metadata CSV, or another source
used by the job. The message does **not** mean the Step 3.1 `mkdir` process
needed to stay alive or that its `dart_remote` block belonged in Terminal B.

**Paste this diagnostic block into Terminal A - Mac; it executes on Linux
via SSH and exits.** If DART is open, finish/save desktop work and quit it
normally first. It displays only source paths and allowlist entries, not
credentials. Storage validation performs temporary write probes inside
DART's managed roots; it does not change sources, settings, or mappings.

```bash
# PASTE INTO TERMINAL A - MAC. Diagnostic only; do not edit the allowlist here.
dart_remote <<'LINUX'
cd "$DART_REPO"
findmnt -T "$GEMS_RUN/objects"
findmnt -T "$GEMS_CSV"
.venv/bin/python - <<'PY'
import os
from pathlib import Path
from dart_storage import Storage, load_environment

load_environment(str(Path(os.environ["CONFIG"]) / "dart.env"))
storage = Storage.from_environment()
print("Approved source roots:", flush=True)
for path, mount in storage.sources:
    print(f"  path={path} mount={mount}", flush=True)
for label, path, directory in (
    ("GEMS objects", str(Path(os.environ["GEMS_RUN"]) / "objects"), True),
    ("GEMS metadata CSV", os.environ["GEMS_CSV"], False),
):
    print(f"Checking {label}: {path}", flush=True)
    print(f"  Accepted: {storage.source(path, directory=directory)}", flush=True)
PY
LINUX
```

- The final `Checking ...` line before an exception identifies which of these
  two paths failed. An empty approved-root list does not authorize an external
  GEMS run. If both pass but the job still fails, inspect the existing job
  inputs, saved project settings, and job evidence for a different source
  path; do not assume the failing path or broaden access blindly.
- Ask the administrator to verify the **selected** private environment file,
  `LINUX_CONFIG/dart.env`. Its `DART_SOURCE_ROOTS` must cover both canonical
  Linux paths and use the actual mount from `findmnt`; see
  [Approve Linux Source Access Separately](INSTALL-LINUX.md#approve-linux-source-access-separately).
  An `export DART_SOURCE_ROOTS=...` in either terminal does not override this
  file: DART treats the selected environment file as authoritative.
- Do not move GEMS assets, grant a blanket filesystem allowlist, change
  permissions/mounts, recreate the project, or regenerate IDs to bypass this
  check. After approved correction, rerun the diagnostic. Then paste this
  complete configuration block into **Terminal A - Mac**; do not recreate
  JSON inputs or start a job:

```bash
# PASTE INTO TERMINAL A - MAC after approved source-access correction.
dart_remote <<'LINUX'
cd "$DART_REPO"
test -r "$CONFIG/settings-$COLLECTION_ID.json"
.venv/bin/python -m dart_linux --env-file "$CONFIG/dart.env" \
  --configure --inputs "$CONFIG/settings-$COLLECTION_ID.json"
LINUX
```

**If you closed something prematurely:**

1. If only the Mac DART window closed after settings were saved, continue
   from the next shell step. No continuously running desktop is required
   during Linux configuration or preparation.
2. If Terminal A closed, open a **local Mac shell** and repeat Steps 0.1 and
   0.2 with the same collection and paths. Variables and the helper were
   shell-local; files, settings, and IDs persist. Do not rerun creation blocks.
3. If a Linux job or its SSH connection was interrupted, do not assume either
   success or a clean rollback. Inspect the recorded job's evidence under
   `LINUX_DATA/jobs/JOB-ID/` and confirm no earlier job is still running
   before retrying with the same project and verified existing JSON inputs.

Keep the leading slash in `AZURE_PATH`: the current validator requires
`/objs/`. The uploader strips surrounding slashes and targets container
`objs`, subdirectory `COLLECTION_ID`, with parallel derivatives in
`smalls/COLLECTION_ID` and `thumbs/COLLECTION_ID`. This is not a Linux path.

### Preview-First Setup Recovery

If you do not know how far an attempt progressed, **do not delete anything
or restart at Step 2**. Use
[`scripts/recover_headless_project.py`](scripts/recover_headless_project.py)
to inspect early Linux setup and preview the narrow source-approval repair.
It is a recovery helper, **not a factory reset**.

**Terminal A - Mac:** quit Mac DART normally, wait for the local prompt, and
restore the same Step 0 definitions if needed. The Mac checkout must contain
the helper; the Linux checkout needs the existing headless workflow, but
the helper itself is streamed over SSH without installing a server file.
No separate Terminal B is needed. The local `python3` uses only the standard
library and existing DART SSH helpers; remote execution uses Linux DART's
virtual environment.

**Verify `--source-mount` against Step 1's `findmnt` output.** `/data` below
was verified for the student-scholarship run; it is not a universal default.
`GEMS_RUN` must identify the specific approved collection run, not the entire
mount or a shared parent containing other collections.

```bash
# PASTE INTO TERMINAL A - MAC. PREVIEW ONLY; wait for the Mac prompt.
python3 "$MAC_DART/scripts/recover_headless_project.py" "$COLLECTION_ID" \
  --host "$HEADLESS_HOST" --repo "$LINUX_DART" \
  --env-file "$LINUX_CONFIG/dart.env" \
  --inputs "$LINUX_CONFIG/settings-$COLLECTION_ID.json" \
  --source-root "$GEMS_RUN" --source-mount /data
```

The preview reports snapshot row count/checksum, saved settings, ID-map count,
recorded collection jobs, and the proposed allowlist action. It reads files
and temporarily takes shared locks on existing service-lock files; it does
not start DART's job service or change interrupted job states. An active
writer prevents inspection. **This Linux report alone does not establish
whether a Mac merge or Azure upload happened:** check the Mac core, pulled
files, and existing job evidence too.

**Apply only after the preview has no blockers and an administrator has
approved the exact source run and mount.** This refuses projects with IDs,
job history, or handoff evidence, and refuses any active/stale-active job
record in the shared job store. Those need case-specific recovery instead
of a generic reset. Existing collection/grouping settings cannot be changed
by this helper.

```bash
# PASTE INTO TERMINAL A - MAC ONLY AFTER APPROVAL. Configure only; no job.
python3 "$MAC_DART/scripts/recover_headless_project.py" "$COLLECTION_ID" \
  --host "$HEADLESS_HOST" --repo "$LINUX_DART" \
  --env-file "$LINUX_CONFIG/dart.env" \
  --inputs "$LINUX_CONFIG/settings-$COLLECTION_ID.json" \
  --source-root "$GEMS_RUN" --source-mount /data --apply
```

Apply preserves existing allowlist entries, appends the approved run only if
needed, and invokes `--configure` with the **existing settings JSON**. It does
not recreate JSON inputs, assign IDs, run `prepare`, upload, merge, delete
files, or move sources. It never writes the Mac core or Linux snapshot.

Before changing the environment file, it saves a private, timestamped copy
under the Linux project's `.DART-working-directory/recovery/`.
**That backup contains secrets. Keep it private; do not share, commit, or
include its contents in a report.** Other private environment values are
preserved. If configuration fails, the new approval and backup remain in
place; inspect the explicit error rather than assuming a rollback.

Wait for `RECOVERED`, exit status `0`, and the local Mac prompt. Configuration
should now be saved, with the ID map unchanged. **Resume at Step 5**, not the
creation blocks in Steps 2-4. Step 5 still assigns permanent IDs, and Step 7
still requires separate Azure approval. Keep the same collection, project,
source paths, and grouping. On later processing failures, preserve evidence
and seek job-specific recovery; do not use this helper to wipe the project.

## 5. Prepare Without Uploads

**Paste into Terminal A - Mac; executes on Linux via SSH; foreground job.**
Mac DART should be closed so Terminal A is available. **Keep Terminal A and
its SSH connection running until the job finishes.** Do not type the next
block, press Ctrl-C, close the terminal, or let the Mac sleep during this job.
Terminal B is not required and cannot keep this job's connection alive.

```bash
# PASTE INTO TERMINAL A - MAC. WAIT for the final result and Mac prompt.
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

**Terminal A - Mac; executes locally**, after Step 5 has finished successfully.
Launch DART if it is not already open. **Keep this foreground process and
Terminal A open throughout Steps 6.1-6.5; use the Mac DART window, not the
occupied terminal:**

```bash
# PASTE INTO TERMINAL A - MAC. KEEP RUNNING while reviewing in the DART window.
(
set -eu
printf 'Working/Outputs folder: %s\n' "$MAC_WORK"
printf 'STOP: Printed values do NOT configure DART.\nFIRST select the Working/Outputs folder above; ONLY THEN open Function 0 and save settings.\n'
printf 'collection-id: %s\ncore_metadata_csv: %s\n' "$COLLECTION_ID" "$MAC_CORE"
printf 'headless_host: %s\nheadless_project_dir: %s\n' "$HEADLESS_HOST" "$LINUX_PROJECT"
cd "$MAC_DART"
test "$(git branch --show-current)" = "$DART_BRANCH"
.venv/bin/python app.py
)
```

**Mac desktop:**

1. **FIRST select** the same `MAC_WORK` **Working/Outputs Folder** in the main window.
2. **ONLY THEN open Function 0** and verify it matches the printed values:
   `collection-id=COLLECTION_ID`, `core_metadata_csv=MAC_CORE`,
   `headless_host=HEADLESS_HOST`, and `headless_project_dir=LINUX_PROJECT`.
   Keep `gems_metadata_csv` blank, `group_compound_objects=true`,
   `create_multiple_objects=false`, and `process_OHM_data=false`.
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

If SSH fails, finish/cancel desktop activity and quit DART normally.
At the returned **Terminal A - Mac** prompt, run this one-shot connection
test; do not recreate inputs:

```bash
# PASTE INTO TERMINAL A - MAC after quitting DART normally.
ssh -o BatchMode=yes "$HEADLESS_HOST" true
```

If that succeeds, **paste this launch block into Terminal A - Mac** and
leave it running while using the desktop window:

```bash
# PASTE INTO TERMINAL A - MAC. KEEP RUNNING while using the DART window.
(
set -eu
printf 'Working/Outputs folder: %s\n' "$MAC_WORK"
printf 'STOP: Printed values do NOT configure DART.\nFIRST select the Working/Outputs folder above; ONLY THEN open Function 0 and save settings.\n'
printf 'collection-id: %s\ncore_metadata_csv: %s\n' "$COLLECTION_ID" "$MAC_CORE"
printf 'headless_host: %s\nheadless_project_dir: %s\n' "$HEADLESS_HOST" "$LINUX_PROJECT"
cd "$MAC_DART"
test "$(git branch --show-current)" = "$DART_BRANCH"
.venv/bin/python app.py
)
```

In the **Mac DART window**, select the printed Working/Outputs folder,
verify the printed Function 0 settings and blank `gems_metadata_csv`, uncheck
**Help Mode**, and choose **4: Compare and Merge CSV Files**. In the file
selection dialog click **Pull From Headless DART...**; if there is no local
export, the pull dialog opens automatically. Choose the recorded successful
rehearsal Job ID, verify row count and warnings, and click **Pull For Review**.
Continue with the comparison instructions immediately below.

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

**Before Step 7:** after canceling review, quit Mac DART normally and wait
for Terminal A's local Mac prompt. Keep Terminal A itself open. No DART
desktop process needs to remain running during the publishing job.

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

**Paste into Terminal A - Mac; executes on Linux via SSH; foreground job.**
DART must be closed and the local Mac prompt visible before pasting.
**This is the first block authorizing Azure writes. Keep Terminal A and its
SSH connection running until the final job result and Mac prompt return.**
Do not press Ctrl-C, close the terminal, or let the Mac sleep.

```bash
# PASTE INTO TERMINAL A - MAC. WAIT for the final result and Mac prompt.
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
overwrite automatically.

### Retry With an Existing Publishing JSON

**Do not run the `.venv/bin/python -m dart_linux ...` lines by themselves
on the Mac.** `CONFIG`, `DART_REPO`, and `WORK` are Linux-side names supplied
by `dart_remote`, not local Mac variables. Running the inner command on the
Mac with an unset `CONFIG` produces a `/dart.env` not-found error; that
invocation fails before starting a job.

If Terminal A lost its definitions, repeat Steps 0.1 and 0.2 with the same
collection and paths first. Do not rerun project/core creation or recovery.
Quit Mac DART normally and wait for the local Mac prompt.

**First, paste this whole inspection block into Terminal A - Mac.** It runs
on Linux, prints the existing publishing inputs, and exits without a job:

```bash
# PASTE INTO TERMINAL A - MAC. Inspect only; no job or uploads.
dart_remote <<'LINUX'
test -r "$CONFIG/prepare-$COLLECTION_ID-publish.json"
printf 'Expected project: %s\nExpected source: %s/objects\n' "$WORK" "$GEMS_RUN"
cat "$CONFIG/prepare-$COLLECTION_ID-publish.json"
printf '\n'
LINUX
```

Verify that `working_dir` and `input_dir` match the printed project/source,
`derivatives` and `backfill` are `true`, `allow_uploads` is `true`, and
`overwrite` is `false`. If values differ, stop and review them rather than
overwriting the file.

**If inspection reports the publishing JSON is absent:** after confirming
no publishing job has already succeeded or is still running, paste this
complete block into **Terminal A - Mac**. It creates the missing publishing
JSON exclusively and **starts the upload job**; do not also run the retry
block below:

```bash
# PASTE INTO TERMINAL A - MAC ONLY IF PUBLISHING JSON IS ABSENT. Starts uploads.
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

Keep Terminal A, VPN, and the Mac awake until `succeeded` and the local prompt
return. Record the publishing Job ID, then continue forward to the publishing
pull and merge instructions. Do not submit a second publishing job.

**Do not retry while a previous publishing job might still be running.**
If its connection dropped, inspect its job evidence and confirm it has
stopped first. A completed successful publishing job should proceed to
Step 8, not be submitted again.

**After inspection and the Step 7 approval gate, paste this entire retry
block into Terminal A - Mac, including `dart_remote` and the final `LINUX`:**

```bash
# PASTE INTO TERMINAL A - MAC. STARTS AZURE UPLOADS; wait for completion.
dart_remote <<'LINUX'
cd "$DART_REPO"
test -r "$CONFIG/prepare-$COLLECTION_ID-publish.json"
.venv/bin/python -m dart_linux --env-file "$CONFIG/dart.env" \
  --job prepare --inputs "$CONFIG/prepare-$COLLECTION_ID-publish.json"
LINUX
```

This reuses the JSON; it does not recreate it. **Keep Terminal A, VPN, and
its SSH connection running, and keep the Mac awake, until the final result
reports `succeeded` and the local Mac prompt returns.** Record the new
publishing Job ID for Step 8.

## 8. Pull the Publishing Job, Merge, and Close the Loop

For a completed multi-collection batch, use the standalone
[Following Up on a Headless DART Batch](BATCH-DART-FOLLOW-UP.md) runbook.
It covers the per-collection desktop loop, coverage reconciliation, SHOW
validation/publication milestones, and optional verified cleanup, including
the October 29 four-collection worked example.

### 8.1 Launch Mac DART

**After the publishing job succeeds and Terminal A's local Mac prompt
returns, paste this complete block into Terminal A - Mac.** It runs locally.
Keep this process running throughout the desktop pull, comparison, merge,
and any UI snapshot push. Do not paste shell commands into the occupied
terminal.

```bash
# PASTE INTO TERMINAL A - MAC. KEEP RUNNING while using the DART window.
(
set -eu
printf 'Working/Outputs folder: %s\n' "$MAC_WORK"
printf 'STOP: Printed values do NOT configure DART.\nFIRST select the Working/Outputs folder above; ONLY THEN open Function 0 and save settings.\n'
printf 'collection-id: %s\ncore_metadata_csv: %s\n' "$COLLECTION_ID" "$MAC_CORE"
printf 'headless_host: %s\nheadless_project_dir: %s\n' "$HEADLESS_HOST" "$LINUX_PROJECT"
cd "$MAC_DART"
test "$(git branch --show-current)" = "$DART_BRANCH"
.venv/bin/python app.py
)
```

**In the Mac DART window:**

1. **FIRST select** the printed `MAC_WORK` **Working/Outputs Folder** in the main window.
2. **ONLY THEN open Function 0** and verify the printed collection ID, core CSV, headless host,
   and Linux project. Keep `gems_metadata_csv` blank,
   `group_compound_objects=true`, `create_multiple_objects=false`, and
   `process_OHM_data=false`. Save settings if needed.
3. Uncheck **Help Mode**.
4. Choose **4: Compare and Merge CSV Files** in **Select Function to
   Execute**. Selection starts the function immediately; there is no
   separate execute button.

### 8.2 Pull the Publishing Package

**Mac DART window; leave Terminal A's launch process running:**

1. In **Select New CSV to Compare**, click **Pull From Headless DART...**.
   If there is no local export, the pull dialog opens automatically.
2. Verify **Server project** matches the printed
   `HEADLESS_HOST:LINUX_PROJECT`.
3. Select the **full successful publishing Job ID recorded at the end of
   the upload job**, not the rehearsal job and not just the newest entry.
4. Verify its row count matches the publishing job's result. Rows include
   generated compound parents; they need not equal the source-folder count.
5. Inspect GEMS backfill counts and warnings. Stop for ID conflicts,
   unexplained unmatched metadata, or a stale snapshot warning. Uploaded
   image/PDF derivatives should no longer have server-local-only references.
6. Click **Pull For Review** (or **Pulled (Pull Again)** for that same job).
   DART verifies checksum and collection ID, saves the handoff CSV and
   manifest under `MAC_WORK/.DART-working-directory`, and reopens Function 4.

If SSH fails, do not start another publishing job. Cancel/finish desktop
activity, quit DART normally, and wait for Terminal A's local prompt.
**Paste this connection test and relaunch block into Terminal A - Mac:**

```bash
# PASTE INTO TERMINAL A - MAC after quitting DART normally.
(
set -eu
ssh -o BatchMode=yes "$HEADLESS_HOST" true
printf 'Working/Outputs folder: %s\n' "$MAC_WORK"
printf 'STOP: Printed values do NOT configure DART.\nFIRST select the Working/Outputs folder above; ONLY THEN open Function 0 and save settings.\n'
printf 'collection-id: %s\ncore_metadata_csv: %s\n' "$COLLECTION_ID" "$MAC_CORE"
printf 'headless_host: %s\nheadless_project_dir: %s\n' "$HEADLESS_HOST" "$LINUX_PROJECT"
cd "$MAC_DART"
test "$(git branch --show-current)" = "$DART_BRANCH"
.venv/bin/python app.py
)
```

If the test fails, stop and resolve VPN/SSH connectivity; DART will not
launch. If it succeeds, keep the launch process running. In the DART window,
select the printed Working/Outputs folder, verify Function 0's printed
settings and blank GEMS CSV, uncheck Help Mode, choose **4: Compare and Merge
CSV Files**, click **Pull From Headless DART...**, and select the same
successful publishing Job ID. Verify project, row count, and warnings, then
click **Pull For Review**. Do not recreate the project, inputs, or IDs.

### 8.3 Compare and Inspect the Publishing Records

**Mac DART window:**

1. In **Select New CSV to Compare**, verify the displayed core matches
   `MAC_CORE`.
2. Leave **Backfill empty fields from GEMS metadata CSV** off. Linux already
   performed backfill.
3. Leave **After a successful merge, move completed object folders to
   objects/.complete** off. Headless handoff does not retire GEMS sources.
4. Choose `DART_export_handoff_JOB-ID.csv` for the recorded **publishing**
   Job ID. **Use Newest** is safe only if it selects that exact file.
   Choosing the file starts comparison immediately.
5. For a still-header-only core, expect new records equal to the publishing
   package's row count, changed records `0`, and missing in new `0`. For a
   populated core, review additions, changes, and missing records against
   that established core instead; absence from a batch is not a deletion
   instruction.
6. Click **Review & Merge Changes** to open **Interactive Comparison &
   Merge**. This viewer is not a complete CSV-field viewer.

In Finder, open `MAC_WORK`, press **Command-Shift-.** to show hidden files,
and open the exact publishing CSV and
`DART_handoff_JOB-ID_manifest.json` under `.DART-working-directory` in VS Code
or a CSV viewer. Treat them as read-only; do not save spreadsheet conversions
over them.

Verify all of the following before authorizing a merge:

- `objectid` is nonempty and unique; established IDs remain unchanged.
- Physical records have the exact source `original_file_name`, extension,
  and case, with no duplicate keys. Generated parent names start with `_`.
- GEMS descriptive fields are present where expected; required metadata is
  not unexpectedly blank. Inspect unmatched rows and ignored schema fields.
- Standalone records have no `parentid`; each compound's physical children
  point directly to its intended generated parent, without an unwanted
  intermediate `multiple` layer. Review complete families together.
- Row order follows the intended collection/child sequence.
- `object_location`, `image_small`, and `image_thumb` contain the approved
  HTTPS Azure URLs where applicable, not blank rehearsal locations or Linux
  paths. Review asset types without derivatives individually. Parents
  should inherit appropriate derivative references from a child.
- Manifest `collection_id`, `job_id`, and `rows` match this collection and
  publishing job. Investigate `id_conflicts`, stale snapshot warnings,
  `derivatives_local_only`, and every unexplained warning. Check GEMS
  backfill matched rows, fields filled, unmatched rows, duplicate names,
  and ignored columns; a successful job alone does not prove completeness.

If anything is wrong, **Cancel**; do not merge or regenerate IDs.

### 8.4 Merge Only Approved Changes

**Mac DART window; keep Terminal A's process running:**

1. In **Interactive Comparison & Merge**, select only approved additions
   and field changes. New records begin checked; uncheck anything not
   approved. Keep complete parent/child families together.
2. Click **Merge Selected Changes**.
3. Review the confirmation's core and selections. Confirm **Merge Changes**
   only if they are correct; otherwise cancel.
4. Wait for successful completion. Do not quit DART during the merge.
5. Verify the merged authoritative `MAC_CORE` CSV. Function 4 makes a backup
   before writing. Existing rows retain their order; selected additions
   follow export order. Verify intended rows, IDs, relationships, and URLs.

### 8.5 Push the Updated Core Snapshot

After verifying the merged core, use **one** of these methods:

- **Mac DART window:** open Function 4's **Select New CSV to Compare**
  dialog and click **Push Core Snapshot**. Verify the intended server/project
  and wait for success. Keep DART and Terminal A running during the transfer.
- **Terminal A - Mac:** if using the terminal instead, finish desktop
  activity and quit DART normally. Wait for the local Mac prompt, then
  paste this **complete** block:

```bash
# PASTE INTO TERMINAL A - MAC after quitting DART normally. Snapshot push only.
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

Keep Terminal A and VPN connected until the snapshot push succeeds and the
local prompt returns. The push updates Linux's read-only input snapshot,
not the authoritative Mac core. Do not quit during any merge or transfer.

**Finished:** require a successful snapshot push. Once all desktop operations
and transfers are complete, quit DART normally. After Terminal A's local Mac
prompt returns, it may be closed; optional Terminal B may also be closed.

Headless processing and handoff do **not** move GEMS folders into `.complete`.
Leave sources intact and track completed job IDs and merged batches yourself.
Retain the Linux project and ID map for retries and future batches. Do not
scan the same run under a fresh project or point DART directly into `.complete`.
Publishing the CollectionBuilder site is a separate workflow.

For disk-space planning and local derivative reclamation, follow
[Disk-Space Guards and Verified Cleanup](LINUX-HEADLESS-OVERVIEW.md#disk-space-guards-and-verified-cleanup).
Headless jobs now default to a 50 GiB reserve and exit `75` on insufficient
space. Preview/apply cleanup can reclaim only the selected successful
publishing job's Azure-verified derivatives; it never deletes originals or
ID maps. Original offload requires separate acceptance and verified archival
storage, not merely a successful publishing job.

## Validation Status

All shell blocks and embedded Python snippets passed syntax checks;
local document links, the installation anchor, and table headers were checked.
Isolated temporary-storage tests verified that the source diagnostic accepts
approved objects and metadata, identifies a rejected path, and rejects an empty
allowlist even when the parent shell exports a different one.

The recovery helper's nine focused tests cover a non-mutating preview,
configuration-only recovery, repeat runs, environment/backup preservation,
SSH quoting, and refusals for IDs, job evidence, active writers, stale-active
records, and sources outside the approved run. Configuration-only recovery
was also verified over SSH: existing approvals/private values were preserved,
the core and snapshot stayed unchanged, and no job or IDs were created.

Earlier isolated temporary-file tests verified header-only core creation,
JSON contents, overwrite refusal, and collection-ID checks. A local SSH
stand-in verified variable forwarding with spaces and quotes; it made no
network connection.

No server deployment, source scan, Azure upload, real collection core creation,
or merge was performed while restructuring this runbook. Actual paths,
permissions, installation revision, GEMS CSV, and end-to-end operation remain
operator checks at the gates above.
