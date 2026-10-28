# Headless Linux Acceptance Testing

This is **verification**, not installation or everyday operation.
See [Installation](INSTALL-LINUX.md) and [Operating Overview](LINUX-HEADLESS-OVERVIEW.md).

## Safety And Test Boundaries

The finite runner is offline by default and has **no live API/upload mode**.
It never loads the normal private environment file. It creates a unique
private disposable tree and initializes only its own roots. It opens no
network listener, never mounts/unmounts a share, modifies GEMS, or stops an
unrelated process. Only its own temporary subprocesses are stopped.

The test suite denies network connections in managed workflow tests, and SSH
pull/push tests use a fake runner rather than a real host. No originals from
institutional storage, actual collection CSVs, or live credentials are
needed. Live operations require explicit operator approval and per-job
consent; do not reinterpret an offline PASS as that approval.

## Run The Finite Automated Checks

From the approved Linux checkout, or a Mac development checkout with the
Linux requirements already installed:

```bash
cd ~/GitHub/DART
.venv/bin/python -m dart_acceptance
```

The command prints its exact evidence directory. By default this is a unique
directory in the platform's temporary area. **It is retained**, not deleted.
For evidence that must survive temporary-directory cleanup, specify an
existing owner-only, approved evidence parent:

```bash
.venv/bin/python -m dart_acceptance \
  --evidence-parent /APPROVED/PRIVATE/EVIDENCE-DIRECTORY \
  --timeout 90
```

The parent is not provisioned by the runner. Each invocation still creates
its own `dart-acceptance-RANDOM` child. Do not supply the actual source tree or
a GEMS directory. Do not reuse a prior acceptance child as the normal service.
The runner's isolated `dart.env` contains empty credentials and no external
source roots.

Exit **0** means all executed automated components passed, **not full
operational acceptance**. A failed component is `FAIL`, exits nonzero, retains
its traceback, and leaves later checks `PENDING`. Manual checks always remain
`PENDING` until a human records their evidence separately.

Each child command/job has a timeout; the command is finite. A truly stuck
filesystem/kernel operation is an administrator-supervised outage case, not
something a Python timeout can guarantee to repair.

## Automated Components And Measurable Criteria

| Component | Required Pass Criteria | Evidence |
| --- | --- | --- |
| Baseline | `pip check` and offline unit suite exit zero; OS/interpreter/revision captured | `host.json`, `packages.log`, `revision.log`, `worktree.log`, `pip-check.log`, `tests.log` |
| Offline Workflows | One fixture source produces one export row; derivatives are generated; a handoff package is written with a manifest whose CSV checksum verifies; the core snapshot is byte-for-byte unchanged; pre/post source SHA-256 matches | `offline-results.json`, isolated job records, export CSVs, and `handoff/JOB-ID/` |
| Lifecycle | Controlled real derivative job becomes `cancelled`; killed child becomes `interrupted` after reopening; neither is `succeeded`; each retains two partial JPEGs | `lifecycle.json`, `cancel.log`, `interrupt.log`, job records |
| Storage Fail-Closed | Removing only the isolated marker blocks submission; marker is not recreated; restoring the test marker permits checks again | `storage-failure.json` |
| Headless CLI | `dart_linux --job prepare` succeeds and writes a package manifest; a second process is refused while the first holds the writer locks; the removed `--web` option is rejected | `cli-prepare.log`, `second-writer.log`, `web-removed.log`, `headless-cli.json` |

Lifecycle checks introduce a controlled pause after real local derivative
work. They do not claim to reproduce an Azure transaction or actual network
storage outage. The interruption test kills **only its own child**.

The focused unit suite also checks:

- Stable ID reuse, nested versus flat compounds, and the original compound
  processing body's extraction fingerprint.
- Canonical/legacy filename columns and OHM CSV row shape.
- Exact image bounds, handoff packages that never write the core, duplicate-key
  rejection, and rejection of the removed compare/merge job kinds.
- Core-snapshot ID reuse only for unique filenames, with ID conflicts reported
  in the manifest.
- Desktop handoff settings validation, package listing by collection,
  checksum/collection/clobber refusal on pull, SSH failure reporting, and
  quoted atomic core-snapshot push (with a fake SSH runner).
- Server GEMS backfill (on by default when configured) without identifier
  replacement.
- Single-writer locks across processes, including a changed config root.
- Cancellation, concurrent-job refusal, and restart-to-interrupted recovery.
- Missing markers, failed atomic replacement, storage failures during a job,
  private permissions, symlink escapes, and unavailable source mounts.
- Credential/signed-URL redaction and upload opt-in, with no live Azure calls.
- Safe module import without creating home-directory application storage.
- Real headless `--configure` and `--job prepare` CLI runs, and existing
  helper-script CLI help entry points.

For a targeted developer run:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

## Read And Retain The Evidence

Set this to the exact directory printed by your run:

```bash
EVIDENCE='/EXACT/PRINTED/dart-acceptance-RANDOM'
.venv/bin/python -m json.tool "$EVIDENCE/report.json"
.venv/bin/python -m json.tool "$EVIDENCE/lifecycle.json"
```

Important paths relative to that root:

```text
report.json
failure.log
config/
data/jobs/JOB-ID/job.json
data/jobs/JOB-ID/job.log
data/projects/collection/collection.csv
data/projects/collection/.DART-working-directory/
```

`failure.log` exists on component failure. Planned result paths may precede
file completion; do not count them as successful output. Keep failed evidence
as well as successful evidence. Evidence is private and may contain local
paths or collection metadata. Do not upload whole trees to public issues.

No automatic evidence deletion or retention policy is installed. Copy
approved evidence to institutional retention storage before temporary-area
cleanup. Removing a disposable test tree is a separate deliberate action,
never a reason to remove a source tree or active service root.

## Manual Desktop Handoff Checks

After administrator-approved installation, use the normal operating guide.
Use disposable approved collection data, not preservation originals.

| Check | Required Pass Criteria |
| --- | --- |
| SSH Key Access | `ssh -o BatchMode=yes HOST true` succeeds from the operator Mac without a prompt |
| Settings | Function 0 saves valid `headless_host`/`headless_project_dir`, rejects half-set or option-like values, and blank values turn the buttons off |
| Core Snapshot Push | **Push Core Snapshot** writes `core-snapshot.csv` with mode `0600` in the server project; the local core is unchanged |
| Headless Prepare | `dart_linux --job prepare` succeeds; `--list-jobs` shows it; the package has `export.csv` and `manifest.json` |
| Pull | **Pull From Headless DART...** lists only complete packages for this collection; pulling saves `DART_export_handoff_JOB-ID.csv`; Function 4 reopens with it as newest |
| Pull Safety | A tampered CSV, wrong collection, or differing local file is refused with nothing copied |
| Snapshot Drift | After changing the local core, a pull warns that the core changed since the snapshot |
| ID Conflicts | A deliberately conflicting filename/ID appears in manifest warnings and is reviewed, not silently merged |
| Review Safety | Function 4 review, selection, backup, and reserved-template refusal behave as in ordinary desktop use |
| Cancellation | Ctrl+C during a headless job yields `cancelled`, or correctly `succeeded` if commit already finished; inspect partial output |

Record desktop DART version, host, job IDs, and actual outcomes.

## Manual Content And Real Source Review

**Pending until the administrator provides the approved read-only mount.**

Record the exact server share, mount point, allowlisted collection root, mount
options, source checksums, core schema, stable mapping history, and collection
ID. Compare representative standalone, compound, flat/nested, PDF/TIFF, and
OHM records as applicable.

Pass only if:

1. Selected Linux files are the approved originals; no archival paths or
   durable mappings were silently translated.
2. Original bytes and locations are unchanged.
3. IDs remain stable across reruns; compound parents/children and first-child
   references are correct.
4. GEMS backfill fills only approved empty metadata and preserves DART IDs,
   structure, and URLs.
5. OHM transcript copies are correct and remain inside the managed project.
6. CSV content and derivative appearance meet collection-specific review
   criteria. Pixel bounds alone are not visual-content approval.

If a case is not represented, record `PENDING` or explicitly not applicable
with a reason; do not invent a PASS.

## Explicitly Authorized Azure Checks

Not run by the automated suite. Get approval for the exact disposable account,
existing containers, collection path, source fixtures, expected cost, and
cleanup procedure. Put credentials only in the private environment file.

Use per-job `allow_uploads` consent for export/derivatives/prepare and record
the job IDs.
Verify expected blob names and byte hashes, URL reachability under the
approved access policy, expected derivative appearance, no overwrite when
overwrite is unchecked, and controlled replacement only when separately
authorized. Failed uploads must be failed jobs; reruns must reuse IDs.

Do not publish a collection or delete remote objects without separate
approval. Never publish local-only derivative paths. Keep credential and
signed-URL errors redacted in retained evidence.

## Administrator-Supervised Storage Outage

The missing-marker simulation is **not** an actual outage test. Do not
unmount shared storage for acceptance without an administrator.

Agree on a disposable target and an outage plan. Observe reads, writes,
progress, cancellation, and state persistence during the outage. Required:
no alternate home/local output tree, no false `succeeded`, no source changes,
explicit storage errors, and safe retention of partial output. If job-state
storage itself is unavailable, the job may show `interrupted` only in memory;
after storage is restored and the service is restarted, the last persisted
active record must become `interrupted`.

Stop and inspect before restart when filesystem identity changes. Do not
initialize a missing marker to suppress the error.

## Institutional Backup Restore

No institutional restore is automated or claimed by this change.
Coordinate a quiesced backup of configuration, job history/logs, project
settings/mappings, core CSVs, and outputs with the responsible administrator.
The private credential file and any existing encryption keys require the
institution's secret-handling policy.

Restore into separately approved roots, not over the active environment.
Pass criteria: expected inventory and SHA-256 hashes match, private
permissions/ownership survive, job history opens accurately, unfinished
records become interrupted, no jobs resume, and a new disposable offline
workflow can run. Reconcile embedded absolute paths explicitly; do not
silently rewrite historical inputs or mappings.

## Markdown PDF And Diagram Review

Target VS Code's **Markdown PDF** extension. Export the operating overview and
inspect each Mermaid diagram at actual print size. Required: no syntax-error
placeholder, no clipped text/edges, readable labels, a hard page break before
the diagram, and the complete diagram on one printed page.

For these trusted local documents, the installed Markdown PDF 2.2 renderer
needs its sanitizer disabled **for the export** to retain the overview's
print-only CSS. Its default `gfm` sanitizer removes `<style>` blocks.
Use this VS Code export setting only for reviewed documents, not arbitrary
untrusted Markdown:

```json
{
  "markdown-pdf.sanitize": "none"
}
```

Use the extension's configured Mermaid renderer (Mermaid 10.9.5 was used for
the local development render). If exporting offline, point its Mermaid
renderer setting at an administrator-approved local copy rather than
assuming a CDN is reachable.

The overview uses compact vertical flow, short plain labels, `htmlLabels: false`,
18-pixel diagram fonts, and print-size bounds. Keep installation, everyday
operation, and acceptance as linked separate documents. A Mermaid source
block or HTML rendering alone is not proof of the PDF result.

## Acceptance Decision

Maintain separate results for automated checks, manual desktop handoff checks,
content/source review, approved Azure actions, supervised outages,
institutional restore, and PDF review. Only the operator/administrator can
approve deployment. A runner report intentionally retains overall acceptance
as `PENDING`; it cannot sign off on institutional operations.
