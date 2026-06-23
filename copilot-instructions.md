# GitHub Copilot Instructions for DART

Use `AGENTS.md` as the primary repository source of truth for DART-specific behavior and constraints. This file is a short Copilot-oriented companion that reinforces the most important rules for this codebase.

## Preferred Change Order

Before editing `app.py`, check whether the request belongs in one of these higher-level surfaces:

1. `seeklight_mapping_template.json`
2. `FUNCTION_*.md`, `README.md`, `INSTALLATION.md`, `QUICKSTART.md`
3. Focused helper scripts such as `scripts/rename_metadata_field.py`, `scripts/fix_config_csv_fields.sh`, `scripts/batch_rename_dublin_core.sh`
4. `app.py`

## DART-Specific Rules

- Treat the configured core metadata CSV as the source of truth.
- Preserve `objectid`, `original_file_name`, and `file_to_id_map` semantics unless the user explicitly asks to change them.
- Preserve optional `dg_prefix` behavior for new IDs: legacy IDs may remain `dg_<epoch>`, while new IDs may be generated as `<prefix>_dg_<epoch>`.
- Canonical CollectionBuilder CSV field names are unprefixed: `title`, `description`, `date`, and similar.
- Treat `dc_` field names as legacy cleanup targets only.
- Keep generated artifacts in `.DART-working-directory`, including `DART_*`, `csvdiff_*`, `dart_settings.json`, merge backups (`*.backup_*`), and temporary derivative files.
- Do not edit `app.py.bak`, `app.py.bak2`, files in `logfiles/`, DMGs, or generated `.DART-working-directory` output unless the user explicitly asks.
- If a numbered workflow function changes behavior, update the matching `FUNCTION_*.md` file.
- If the change affects Seeklight field routing or defaults, inspect `seeklight_mapping_template.json` before changing runtime logic.
- Avoid packaging changes unless the request is specifically about launchers or distribution.

## Ask Before Risky Changes

Explain the plan and get confirmation before:

- changing durable ID generation or persistence
- bulk-rewriting metadata CSVs or settings outside the repository
- altering Azure path semantics, encryption behavior, or settings storage format
- deleting historical docs, backups, or build artifacts
- refactoring broad sections of `app.py` for a local behavior fix

## Validation

Use the narrowest validation that matches the edit.

For Python and helper-script changes, prefer:

```bash
python3 -m py_compile app.py scripts/rename_metadata_field.py scripts/fix_config_csv_fields.sh scripts/migrate_legacy_working_files.py
bash -n scripts/batch_rename_dublin_core.sh scripts/diagnose_rename_changes.sh scripts/run.sh scripts/build_dmg.sh scripts/build_windows_zip.sh scripts/cleanup_old_backups.sh
```

For docs or JSON-only edits, a focused readback, grep, or diff is usually sufficient.

## Documentation Anchors

When you need context, read the nearest relevant file first:

- `README.md`
- `ARCHITECTURE.md`
- `BEST_PRACTICES.md`
- `FUNCTION_0_APP_SETTINGS.md` through `FUNCTION_6_COMPARE_MERGE_SEEKLIGHT.md`
- `RENAME_METADATA_FIELD.md`
- `FIXING_RENAME_ISSUES.md`
- `CHANGELOG.md`