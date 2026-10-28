# Headless Linux Installation

This is **installation and storage preparation**, not everyday operation.
Next: [Operating Overview](LINUX-HEADLESS-OVERVIEW.md).
Verification: [Acceptance Testing](LINUX-ACCEPTANCE.md).
The existing desktop launchers and helper-script CLIs remain available.

## Deployment Status And Approval Boundary

The `linux` branch adds a separate managed entry point. It does not install a
service, provision the host, mount a share, migrate archival data, or publish
anything. The intended host is `sysadmin@dg-landing`.

Read-only inspection on October 21, 2026 found a mounted XFS `/data` volume,
approximately 413 GB free, and no DART storage root. The operator approved this
**design**, not execution of provisioning commands:

```text
/data/dart/config
/data/dart/data
```

Both roots must belong to `sysadmin:sysadmin`, have mode `0700`, and remain
separate from GEMS. Private files use `0600`. Administrators must confirm
capacity, retention, backup coverage, and the actual source mount before use.
Do not infer that free space or mount status remains unchanged.

**Do not run the provisioning commands below without approval.** Code transfer,
Linux package installation, and deployment also require approval. Do not
modify the neighboring GEMS checkout or its service.

## Architecture And Compatibility

The desktop entry point is still `app.py`. Headless managed operation uses
`dart_linux.py`, `dart_service.py`, `dart_storage.py`, `dart_workflows.py`,
and `dart_handoff.py`. Existing compound grouping and CSV row construction are
shared through `dart_processing.py`; media and OHM helpers remain in `app.py`.
Importing those helpers no longer creates home-directory logs.

**Headless DART has no browser or web interface and opens no network
listener.** It prepares data up to the point of merge and leaves a handoff
package. Desktop DART on the operator's Mac pulls packages over key-based SSH
and performs every compare/merge decision in Function 4 against the
authoritative core CSV, which stays on the desktop. Desktop DART also pushes a
read-only `core-snapshot.csv` into each server project for schema and existing
IDs.

Each CLI invocation is one process with one worker thread and advisory
exclusive locks on **both** configured roots, so a second concurrent writer is
refused. A stopped process does not resume work on restart: queued/running/
cancelling records become `interrupted`.

Managed headless differences are deliberate:

- Only explicit existing server paths are accepted, in owner-only JSON input
  files; there are no file pickers.
- All local destinations and the core snapshot must be under the managed
  `projects` directory. Source trees are read-only, including GEMS sources.
- Analyze/export save durable mappings without the desktop preview/Close
  confirmation. A file with no saved mapping or filename ID reuses the core
  snapshot's `objectid` for a unique matching `original_file_name`.
- Every job uses saved collection settings (`dart_linux --configure`).
- Azure uploads and overwrite each require explicit per-job authorization.
  Containers must already exist; the managed workflow does not create them.
  Function 3's existing container-name substitution and blob subpath are
  preserved.
- Local-only derivatives are supported and retained, unlike desktop Function 3.
  Derivative files are not transferred to the desktop.
- GEMS backfill runs on the server when the project names a GEMS CSV.
- Headless DART never compares, merges, or writes a core CSV, and never
  retires sources. Neither `automatic_four` nor saved desktop upload flags can
  silently enable side effects.
- The native application refuses new managed storage roots; use the managed
  entry point there. Ordinary native project locations are unchanged.

Do not use an existing desktop project as a fresh Linux project without a
reviewed migration. Existing mapping keys may refer to Mac paths. Linux paths
are not automatically translated, and old mappings are not rewritten.

## Install Dependencies After Approval

The Linux checkout is intended to be:

```text
/home/sysadmin/GitHub/DART
```

Its required sibling checkout is:

```text
/home/sysadmin/GitHub/common-DG-utilities
```

Run the following steps **only after approval to transfer code and install
packages**. Approval of a metadata snapshot does not authorize deployment.
These commands do not provision active storage, mount sources, or start a
service. They leave GEMS and its Python environment untouched.

### Check The Linux Host And Install Python Prerequisites

From a **Mac terminal**, connect:

```bash
ssh sysadmin@dg-landing
```

In that **Linux SSH session**, inspect the platform:

```bash
whoami
printf 'Home: %s\n' "$HOME"
cat /etc/os-release
python3 --version
df -h /home/sysadmin /data
```

Expected account/home: `sysadmin` and `/home/sysadmin`. Read-only inspection
on October 21, 2026 found Ubuntu 24.04 and Python 3.12.3, which meets DART's
Python 3.11+ requirement. Stop if the account or platform differs; do not
replace the system Python or reuse GEMS's virtual environment.

After administrator approval, install the Ubuntu prerequisites:

```bash
sudo apt-get update
sudo apt-get install --yes python3 python3-venv python3-pip git rsync ca-certificates
python3 --version
```

The declared Python packages normally provide Linux wheels for this host.
No graphical desktop, X server, browser, or Flutter SDK is needed for
headless operation. Do not install speculative native build dependencies:
if pip reports a missing compiler, library, or unsupported wheel, retain the
error and resolve that specific requirement before continuing.

### Create Fresh Sibling Checkouts

Still in the **Linux SSH session**, run this first-install block. It stops
rather than modifying an existing checkout:

```bash
(
 set -eu
 umask 077
 test "$HOME" = /home/sysadmin
 mkdir -p "$HOME/GitHub"
 cd "$HOME/GitHub"
 test ! -e DART
 test ! -e common-DG-utilities
 git clone https://github.com/Digital-Grinnell/common-DG-utilities.git
 git -C common-DG-utilities checkout --detach 4e3dd13143173e1aace55db4a6c3c4533f2d1407
 git clone https://github.com/Digital-Grinnell/DART.git
 git -C DART switch -c linux 95d07cd401f407f683d1fe1c38e7f75a24485243
)
```

If either directory already exists, stop and inspect it rather than deleting,
resetting, or overwriting it. If GitHub requires authentication, use the
institution's approved SSH/credential mechanism; never embed a token in a URL
or command. The hashes above identify the inspected shared-utility revision
and DART's starting `main` revision for this implementation.

**The headless implementation currently includes uncommitted files on the
Mac's `linux` branch. Cloning GitHub alone does not install those changes.**
The next step overlays the reviewed Mac source files without committing or
pushing them. Do not launch the baseline clone before that transfer.

### Transfer The Reviewed Mac Source Changes

Open a **second Mac terminal**; do not run this block inside SSH. Confirm the
source checkout is on `linux`, then prepare a Git-filtered transfer list:

```bash
cd ~/GitHub/DART
git branch --show-current
git status --short
DART_TRANSFER_LIST="$(mktemp -t dart-source-list)"
git ls-files --cached --others --exclude-standard > "$DART_TRANSFER_LIST"
cat "$DART_TRANSFER_LIST"
```

Expected branch: `linux`. Review the list before continuing. It includes
tracked files and nonignored new files, including the Linux implementation,
but not ignored virtual environments, credentials, generated working files,
or Git internals. Stop if it includes any private settings, source collections,
or unrelated files. This recipe assumes filenames do not contain newlines.

Preview the transfer:

```bash
rsync -rltpni --chmod=go-rwx \
 --files-from="$DART_TRANSFER_LIST" \
 "$HOME/GitHub/DART/" \
 sysadmin@dg-landing:/home/sysadmin/GitHub/DART/
```

After reviewing the preview, copy using the same list:

```bash
rsync -rltpi --chmod=go-rwx \
 --files-from="$DART_TRANSFER_LIST" \
 "$HOME/GitHub/DART/" \
 sysadmin@dg-landing:/home/sysadmin/GitHub/DART/
```

Verify content with a checksum dry run; expected output is **no file changes**:

```bash
rsync -rltpcni --chmod=go-rwx \
 --files-from="$DART_TRANSFER_LIST" \
 "$HOME/GitHub/DART/" \
 sysadmin@dg-landing:/home/sysadmin/GitHub/DART/
rm "$DART_TRANSFER_LIST"
unset DART_TRANSFER_LIST
```

Stop on any nonzero transfer exit or remaining checksum differences. These
commands do not use `--delete`, copy the Mac virtual environment, transfer
collection data, or change the dependency checkout. Keep the Mac source
unchanged during the transfer. This first-install overlay does not propagate
file deletions; a later code update needs a separately reviewed update plan.

### Create DART's Own Virtual Environment

Return to the **Linux SSH session**. Confirm the overlay and sibling dependency
are present:

```bash
cd ~/GitHub/DART
git status --short --branch
test -f dart_linux.py
test -f dart_handoff.py
test -f python_linux_requirements.txt
test -f ../common-DG-utilities/setup.py
git -C ../common-DG-utilities rev-parse HEAD
```

Expect branch `linux` with the transferred modifications/new files, and the
shared-utility hash shown above. Do not continue if a required file is missing.
Create a **new Linux virtual environment**; never copy the Mac's environment:

```bash
(
  set -eu
  cd ~/GitHub/DART
  umask 077
  test ! -e .venv
  python3 -m venv .venv
  .venv/bin/python -m pip install -r python_linux_requirements.txt
  .venv/bin/python -m pip check
)
```

Always invoke this environment explicitly:

```bash
cd ~/GitHub/DART
.venv/bin/python --version
.venv/bin/python -m pip show flet python-dotenv common-dg-utilities
```

The existing requirements contain `-e ../common-DG-utilities`. That installs
the sibling source as an **editable dependency**, not an independent copy.
Keep that checkout in place and do not update it casually: later edits there
affect DART's next process. Running installation from the DART directory keeps
the relative dependency path unambiguous.

### Verify The Headless Runtime Before Storage Setup

Run finite acceptance in isolated disposable roots before normal operation:

```bash
cd ~/GitHub/DART
.venv/bin/python -m dart_acceptance --timeout 180
```

The runner prints its retained evidence directory. Require every automated
group to report `PASS`; inspect `report.json` and the per-check logs there on
failure. The runner uses its own temporary roots and does not read the normal
DART environment file. Manual checks correctly remain `PENDING`. See
[Acceptance Testing](LINUX-ACCEPTANCE.md) for the complete criteria and
evidence layout.

For a quick dependency-only recheck later:

```bash
cd ~/GitHub/DART
.venv/bin/python -m pip check
```

Do not repeat environment creation over an existing `.venv` or treat a failed
installation as usable. Resolve its explicit error before proceeding.

The Linux requirements include the existing desktop requirements, preserving
the desktop dependency set used by shared helpers, plus `python-dotenv`. No
web server, websocket, or Flet Web packages are needed.

**A successful install or `pip check` is not a startup test.** Run the finite
acceptance runner before approving normal operation. It runs the actual
headless CLI against disposable roots.

## Provision Private Storage After Separate Approval

These are proposed administrator-reviewed commands, not commands executed by
this change. Recheck the mount before creating anything:

```bash
findmnt -T /data
df -h /data
id
ls -ld /data /data/dart /data/gems
```

Once approval has been given, create DART's own directories as `sysadmin`.
Do not change GEMS ownership or permissions:

```bash
umask 077
mkdir -m 700 /data/dart
mkdir -m 700 /data/dart/config /data/dart/data
cp ~/GitHub/DART/dart.env.example /data/dart/config/dart.env
chmod 600 /data/dart/config/dart.env
```

The private environment file is:

```text
/data/dart/config/dart.env
```

Edit that private copy. It is authoritative: inherited `DART_*` roots and
credentials are cleared before its values are loaded. Missing roots, wrong
ownership, permissive modes, invalid JSON, unknown setting names, or missing
markers produce errors, not home-directory defaults.

```dotenv
DART_CONFIG_DIR=/data/dart/config
DART_DATA_DIR=/data/dart/data
DART_SOURCE_ROOTS='[]'
DART_AZURE_CONNECTION_STRING=
```

Do not put credentials in a shell command, Git, job inputs, or
public evidence. If approved Azure work is needed, populate only the private
file. Existing encrypted desktop credentials are preserved unchanged in copied
project settings but are **not used** by headless jobs. No desktop key migration
or encryption-format conversion is performed.

Explicitly initialize the already approved existing roots:

```bash
cd ~/GitHub/DART
.venv/bin/python -m dart_linux \
  --env-file /data/dart/config/dart.env --initialize-storage
```

This creates DART markers and private `jobs`/`projects` directories. Normal
startup never initializes missing roots or recreates missing markers. Never
use initialization as a workaround for a missing mount.

Create a new approved collection working directory separately:

```bash
umask 077
mkdir -m 700 /data/dart/data/projects/REPLACE-COLLECTION
```

Do not bulk-copy source objects. Then, from desktop DART on the Mac, set
`headless_host` and `headless_project_dir` in Function 0 and click **Push Core
Snapshot** in Function 4. This writes `core-snapshot.csv` (owner-only) into
the project. The snapshot needs `objectid` and `original_file_name` (legacy
`filename` is normalized) and the desired CollectionBuilder columns. The
desktop core remains authoritative; the snapshot is read-only input. Finally,
save the project's settings with `dart_linux --configure` as described in the
[Operating Overview](LINUX-HEADLESS-OVERVIEW.md).

## Approve Linux Source Access Separately

No working CIFS/NFS source mount was verified during inspection. An existing
`/mnt/_GEMS-Migration` entry returned **No such device**; it is not approved
source storage. Do not mount, unmount, repair, or reuse it on this task's behalf.

The operator chose to have an administrator supply an approved **read-only**
Linux mount. Large objects may remain on the institutional storage share.
The administrator must determine the actual SMB server/share, collection
subdirectory, institutional credentials mechanism, read-only mount options,
and Linux mount point. Mac volume names are not sufficient evidence.

After approval and successful administrator-managed mounting, configure an
allowlist object in the private environment file. This example is a shape,
**not a real approved path**:

```dotenv
DART_SOURCE_ROOTS='[{"path":"/mnt/approved-share/approved-collection","mount":"/mnt/approved-share"}]'
```

Each `mount` must be a real mount point, and its `path` must exist beneath it.
The application rechecks mount availability and filesystem identity while
working. Source files must be readable and inside an approved root. Mac
`/Volumes` and UNC paths are rejected, not rewritten. Symlinked asset aliases
are rejected rather than changing durable mapping keys silently.

Sources already in a DART project are also allowed for small approved local
fixtures. The working directory must not be within the source scan tree.
Scanning includes supported assets recursively, excludes hidden paths, and
reports traversal errors. In OHM mode, select `OHM-data` or its project parent.

Do not relocate existing mapping keys or change a collection ID to make Linux
validation pass. A migration of an established collection needs a separate
path/ID review. Real-source acceptance remains pending until this is done.

## Verify Storage Before Normal Startup

```bash
findmnt -T /data
ls -ld /data/dart/config /data/dart/data \
  /data/dart/data/projects /data/dart/data/jobs
ls -l /data/dart/config/dart.env \
  /data/dart/config/.dart-storage /data/dart/data/.dart-storage
```

Expected: correct mounted volume; directories `drwx------`; private regular
files `-rw-------`; ownership `sysadmin:sysadmin`. Stop on discrepancies.

## Run Acceptance Before Approving Operation

Follow [Acceptance Testing](LINUX-ACCEPTANCE.md), not the everyday startup
instructions. Acceptance uses a fresh disposable evidence tree and never
touches the normal roots or GEMS.

No permanent service is included or started. If a future supervised service is
desired, separately approve the unit, account, working directory, private
environment file, shutdown policy, monitoring, backup policy, and resource
limits. Do not repurpose a GEMS unit.
