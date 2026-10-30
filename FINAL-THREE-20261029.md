# Final Three Collections: One-Command Overnight Pipeline

## Launch on the Mac

The approved `vaf`, `coins`, and `geology` publishing queue, header-only template,
source inventory, and exact source approvals are already staged on dg-landing.
No processing was started during staging.

**Quit desktop DART first. Run this in Terminal A on the Mac, not Linux:**

```bash
bash "$HOME/GitHub/DART/scripts/run_final_three.sh"
```

Authorize the initial Linux `sudo systemd-run` prompt if requested. After that,
the command waits for Linux completion and proceeds automatically. Keep the
**terminal open, Mac plugged in, lid open, and VPN connected**. `caffeinate`
prevents idle sleep, not closed-lid sleep or network disconnection.
DGIngest does not need to be mounted.

Linux runs as service `dart-final-three-20261029`, with uploads enabled,
overwrites disabled, GEMS backfill, flat compound grouping, derivatives, and a
**50 GiB reserve**. It survives Mac disconnection, but Mac follow-up requires
the connection. If the connection fails, reconnect and rerun **the same Mac
command**: it discovers the existing queue's batch rather than submitting it
again. It refuses ambiguous duplicate batches.

## Automatic Follow-Up

After Linux finishes, each successful collection independently passes the
[new-record-only acceptance gates](OVERNIGHT-20261029.md#what-the-automated-job-does).
For eligible collections only, the pipeline:

1. Pulls/checksums the exact publishing package and reconciles source/GEMS coverage.
2. Backs up the header-only SHOW core, atomically writes validated new records,
   and verifies the bytes. Nonidentical populated cores are never overwritten.
3. Pushes a checked Linux snapshot under managed writer locks.
4. Backs up the SHOW catalog and changes **only that collection's three cells**:
   - `status`: `published`
   - `collection_group`: `Batch of 3`
   - `progress status`: `DART Complete, Pending Review of 3`
5. Builds the local SHOW collection with Pagefind enabled.

No separate Working/Outputs selection or Function 0 entry is needed: the script
explicitly uses `~/DART-projects/<slug>` and
`~/GitHub/SHOW/collections/<slug>/_data/<slug>_metadata.csv`.

**No deployment, search-index flag changes, original cleanup, or ID regeneration
occurs.** Setting catalog `status=published` is your requested local catalog
change; it is not evidence that the site was deployed or visually reviewed.
The catalog update precedes the build, so a failed build may leave those approved
cells updated. The result records the exact failed stage.

## Coverage Gates Still Apply

| Collection | GEMS Metadata Rows | Physical/Eligible Assets |
| --- | ---: | ---: |
| `vaf` | 105 | 70 |
| `coins` | 138 | 92 |
| `geology` | 176 | 49 |

No excluded or zero-byte files were found in these source runs. Compound parents
can explain some differences, but counts alone cannot prove complete coverage.
In particular, Geology's metadata-to-file difference requires exact reconciliation
after preparation. **A collection with unexplained missing GEMS records, blank
titles, conflicts, warnings, changed cores, or invalid families is skipped**, not
silently repaired or marked complete. Other eligible collections continue.
There are no mid-run approval questions; real errors are recorded rather than
bypassed.

## Results Tomorrow

**Terminal A - Mac:**

```bash
python3 -m json.tool \
  "$HOME/DART-projects/.DART-working-directory/pipeline-dart-final-three-20261029.json"
```

That result contains the actual batch ID and acceptance summary path. Inspect
the referenced `summary.json` for each collection's `state`, `stage`, `message`,
and `build_log`. Successful builds live in SHOW's `_site/<slug>/`.

- Exit `0`: all three completed the approved pipeline.
- Exit `1`: some require attention; eligible collections may still have finished.
- `review_required`: a safety gate failed; inspect before making corrections.
- `failed`: an operational failure; the stage identifies what persisted.

Backups, pulled packages, evidence, and build logs stay in each project's
`.DART-working-directory`. There is no cross-collection rollback: a written
core remains if a later push/catalog/build fails. Exact byte-identical retries
are accepted so rerunning the same command can finish interrupted follow-up.
Keep DART, other acceptance jobs, and SHOW edits/builds closed during retries.

Linux-only monitoring, if desired, uses Terminal B on dg-landing:

```bash
sudo systemctl status dart-final-three-20261029 --no-pager -l
sudo journalctl -u dart-final-three-20261029 -n 40 --no-pager
```
