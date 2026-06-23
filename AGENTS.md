# DART — AI Agent Instructions

DART is a Python desktop application built with Flet for Digital.Grinnell digital asset workflows. The repository combines a large application entry point, workflow-specific helper scripts, and user-facing markdown documentation. DART is workflow-driven: it analyzes a source set of digital files, assigns durable identifiers, exports CollectionBuilder-compatible metadata, generates derivatives, optionally transforms Seeklight metadata, and merges updates back into a core metadata CSV.

> Companion files in this repo: `CLAUDE.md` points to this file so Claude-based tools get the same rules. `HUMANS.md` is the human-facing guide to working with AI on DART. Keep repository rules here in `AGENTS.md` so the other files do not drift.

## Change Priority Order

Always make the smallest change at the highest appropriate layer before editing lower-level runtime code:

1. `seeklight_mapping_template.json` — Seeklight field mapping and default metadata values
2. `FUNCTION_*.md`, `README.md`, `INSTALLATION.md`, `QUICKSTART.md`, and related docs — workflow guidance and expected user behavior
3. Targeted helper scripts such as `rename_metadata_field.py`, `fix_config_csv_fields.sh`, `batch_rename_dublin_core.sh`, and packaging scripts
4. `app.py` — core application logic and UI behavior
5. Build/distribution artifacts only when explicitly requested

If a behavior is driven by documentation, mappings, or a focused helper script, do not edit `app.py` first.

## Critical Rules

### Core Metadata CSV
- Treat the core metadata CSV as the project's source of truth
- Preserve `objectid` and `filename` semantics unless the user explicitly asks to change them
- Canonical CollectionBuilder CSV field names are unprefixed: `title`, `description`, `date`, and similar
- Treat `dc_`-prefixed field names as legacy cleanup targets, not new canonical names

### Durable Identifiers
- `dg_<epoch>` object identifiers are intended to be permanent once assigned
- Do not rewrite existing identifier mappings casually
- Be careful with logic touching `file_to_id_map`, compound object IDs, or merge matching behavior

### Generated and Working Files
- `.DART-working-directory/` content is generated workflow output, not source code
- Keep generated artifacts in `.DART-working-directory/`, including `DART_*`, `csvdiff_*`, `dart_settings.json`, merge backups (`*.backup_*`), and temporary derivative files
- Do not check in or hand-edit generated CSVs, backups, DMGs, or log output unless the user explicitly asks
- Do not treat `app.py.bak`, `app.py.bak2`, old DMGs, or files in `logfiles/` as primary edit targets

### Function-Specific Documentation
- When runtime behavior changes for a numbered workflow function, update the matching `FUNCTION_*.md` file
- Keep user-facing docs in sync with actual application behavior
- Prefer updating the specific function doc over hiding important behavior only in `README.md`

### Seeklight Integration
- Seeklight behavior is partly driven by `seeklight_mapping_template.json`
- If the change is about field routing or defaults, check that file before changing runtime logic
- Function 5 transforms metadata; Function 6 compares and selectively merges it back into the core CSV

### Settings and Secrets
- Per-project settings live in `dart_settings.json` inside `.DART-working-directory` under the selected working folder at runtime
- Sensitive values are encrypted; avoid replacing encryption-related behavior without understanding the consequences
- Do not hardcode credentials, connection strings, or machine-specific paths into source files

### Packaging and Launchers
- `run.sh`, `run.bat`, `build_dmg.sh`, and `build_windows_zip.sh` are operational scripts
- Avoid changing packaging behavior when the request is about application logic or metadata workflow

## Ask Before Doing These

Explain your plan and get confirmation before:

- Bulk-rewriting a user's metadata CSV or settings file outside the repository
- Changing object ID generation, persistence, or compound object matching behavior
- Altering Azure upload path semantics, encryption behavior, or settings storage format
- Deleting historical docs, backups, build artifacts, or migration notes
- Refactoring large sections of `app.py` when a focused change would solve the issue
- Renaming or removing a workflow function, button, or settings field used in the UI

## DART Surface Map

| File or Area | What it controls |
|---|---|
| `app.py` | Main Flet application, workflow logic, dialogs, validation, merge behavior |
| `seeklight_mapping_template.json` | Function 5 field mapping and default values |
| `FUNCTION_0_APP_SETTINGS.md` through `FUNCTION_6_COMPARE_MERGE_SEEKLIGHT.md` | User help for each workflow function |
| `README.md` / `QUICKSTART.md` / `INSTALLATION.md` | High-level onboarding, setup, and workflow documentation |
| `rename_metadata_field.py` | Targeted metadata field renaming across CSV/config contexts |
| `fix_config_csv_fields.sh` | Cleanup of CSV-based CollectionBuilder config field references |
| `batch_rename_dublin_core.sh` | Bulk normalization of legacy Dublin Core-style field names |
| `diagnose_rename_changes.sh` | Troubleshooting legacy field rename fallout |
| `migrate_legacy_working_files.py` | One-time migration of legacy DART artifacts into `.DART-working-directory` |
| `build_dmg.sh` / `build_windows_zip.sh` | Distribution packaging |
| `python_requirements.txt` | Python dependencies |

## Common Mistakes to Avoid

1. Editing `app.py.bak` or other backup files instead of the active source file
2. Treating generated working-directory CSVs as the authoritative schema instead of the configured core metadata CSV
3. Reintroducing `dc_`-prefixed field names as the preferred CollectionBuilder CSV convention
4. Changing docs without changing the matching runtime behavior, or vice versa
5. Editing broad packaging or installer logic for a workflow-specific issue
6. Modifying secrets or machine-specific settings in tracked source files
7. Making broad `app.py` rewrites when a mapping, helper script, or small local fix would do

## Reference Documentation

Consult these repo documents when needed:

- `README.md` — overall product overview and workflow summary
- `ARCHITECTURE.md` — design decisions and data model rationale
- `BEST_PRACTICES.md` — filename conventions and compound grouping guidance
- `FUNCTION_0_APP_SETTINGS.md` — settings behavior, encryption, core metadata CSV, Azure details
- `FUNCTION_1_ANALYZE_ASSETS.md` through `FUNCTION_6_COMPARE_MERGE_SEEKLIGHT.md` — per-function behavior
- `RENAME_METADATA_FIELD.md` and `FIXING_RENAME_ISSUES.md` — legacy metadata field normalization guidance
- `CHANGELOG.md` — release history and behavior changes

## Validation

Use focused validation that matches the edit:

```bash
python3 -m py_compile app.py rename_metadata_field.py fix_config_csv_fields.sh
bash -n batch_rename_dublin_core.sh diagnose_rename_changes.sh
```

If a change affects launch or packaging, use the narrowest relevant command or script. If a change affects only docs or JSON mappings, a grep or diff may be sufficient.

## Working Instructions

When given a task:

1. Identify whether the request is about workflow behavior, field mapping, helper scripts, docs, or packaging
2. Read the closest relevant file first instead of exploring broadly
3. Prefer focused edits that preserve the existing workflow model and terminology
4. Update matching documentation when the user-visible behavior changes
5. Validate the touched slice before moving on
