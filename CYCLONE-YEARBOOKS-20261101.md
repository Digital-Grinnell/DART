# Cyclone Yearbooks From DGIngest — November 1, 2026

`dg-landing` cannot reach `//storage/MEDIADB/DGIngest`, so this job runs on the Mac with
[scripts/process_cyclone_yearbooks.py](scripts/process_cyclone_yearbooks.py).

## What It Does

1. Downloads the yearbook Google Sheet as CSV and matches each row to a PDF in
   `/Volumes/DGIngest/Cyclones` by year plus suffix (for example, `1936_Malteaser`).
2. Uses the sheet's `dg_<epoch>` as `cyclone_dg_<epoch>` and records the IDs in
   `~/DART-projects/cyclone/.DART-working-directory/dart_settings.json` before uploading anything.
3. Copies one pending PDF at a time into a temporary local folder under `.DART-working-directory`,
   checks its size and source modification time, and uses that local copy for uploads and derivatives.
   The copy is removed when that yearbook finishes or an error occurs. Requires the PDF's size
   plus 1 GiB of free local disk space. Uploads each original to `objs/cyclone/` without overwriting. An existing blob with the same
   size is reused; a different size stops the run.
4. Creates `_SMALL` (800 px) and `_TN` (400 px) JPEGs from page 1 (as in Function 3) and uploads
   them to `smalls/cyclone/` and `thumbs/cyclone/`.
5. Writes `DART_export_cyclone_yearbooks_<ts>.csv`. After every yearbook is done, it backs up the
   SHOW core and **appends** the new rows to it. Existing rows are never changed.

Progress is saved per yearbook in `cyclone_yearbooks_ledger.json`. Rerunning the same command
continues where it stopped.

## Run It

### Remaining 15 Only

The first 74 uploaded yearbooks have been verified in Azure and appended to SHOW's core.
The core now has **105 rows** (31 unchanged original rows plus 74 new rows).
The remaining 15 IDs and a metadata snapshot are frozen in the cyclone project's
`.DART-working-directory/cyclone_remaining_15.json` and `cyclone_remaining_metadata.csv`.
No build, deployment, or Linux snapshot push was performed.

Reconnect VPN and remount DGIngest before running the separate remaining-only script:

```bash
cd "$HOME/GitHub/DART"
set -o pipefail
caffeinate -i .venv/bin/python scripts/process_remaining_cyclone_yearbooks.py --apply \
  2>&1 | tee "$HOME/DART-projects/cyclone/logfiles/cyclone-remaining-$(date +%Y%m%d_%H%M).log"
```

Without `--apply`, it previews only. `--limit 1` can process one remaining PDF as a trial.
Each PDF is staged locally, then uploaded and used for derivatives. Completed ledger entries
are reused. When all 15 finish, they are appended to the core with another backup:
the expected final count is **120 rows**. This command does not build or publish SHOW.

### Original Full-Batch Command

Mount `smb://storage/MEDIADB/DGIngest`, quit desktop DART, and keep the Mac plugged in with the lid
open and VPN connected. About 228 GiB is uploaded, so this can take many hours.

```bash
cd "$HOME/GitHub/DART"
set -o pipefail
.venv/bin/python scripts/process_cyclone_yearbooks.py            # dry run: plan + skips
caffeinate -i .venv/bin/python -u scripts/process_cyclone_yearbooks.py --apply \
  2>&1 | tee "$HOME/DART-projects/cyclone/logfiles/cyclone-yearbooks-$(date +%Y%m%d_%H%M).log"
```

The script uses the cyclone project's own Azure connection string.
If needed, save it in desktop DART Function 0 with `~/DART-projects/cyclone` selected,
or export `DART_AZURE_CONNECTION_STRING` in the terminal session. Without one, `--apply` stops
before writing anything.
Use `--limit N` to process N yearbooks per run, or `--no-merge` to stop after the export CSV.

## Recovering From an Interrupted Upload

The November 1 evening failures ended with `ServiceResponseError` wrapping
`OSError(5, 'Input/output error')`; DGIngest was subsequently unmounted. Azure `SubStream`
finalization messages are secondary to the failed upload. The updated script stages each
PDF locally so Azure's parallel uploads no longer read directly from SMB.

Reconnect the VPN and mount `smb://storage/MEDIADB/DGIngest` in Finder. Check that
`/Volumes/DGIngest/Cyclones` exists, then rerun the command above. Completed ledger entries
are retained (74 complete, 15 pending at the evening failure); do not delete the ledger or
reset IDs. The interrupted PDF upload restarts from the beginning, not its last uploaded block.
If the mount drops during staging, the script stops without marking that yearbook complete.

## Skips

89 of 91 sheet rows are processed. Skipped items are listed in SHOW's
`collections/cyclone/Collection_Notes.md`: 1899 Blue Book and 1946 (no media), plus
`Cyclone1955.pdf`, `Cyclone1989.pdf`, and `Cyclone1990Supplement.pdf` (no sheet rows).
No year is TIFF-only. A year with TIFF pages and no PDF would be skipped.

## After the Merge

- Review the core, then build: `cd ~/GitHub/SHOW && rake "collection:build[cyclone]"`.
- Optionally push the core snapshot to dg-landing with desktop DART so later headless jobs see
  these IDs.
- `collection-title` in SHOW's `collections/cyclone/_config.yml` still says "(1956 thru 1988)".
