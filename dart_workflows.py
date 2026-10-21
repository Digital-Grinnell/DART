"""Managed workflows using DART's existing identifier, compound, and media helpers."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import app as core
from dart_processing import (analyze_compound_objects, build_export_rows, get_derivative_azure_paths,
                             get_display_template, get_stable_path)
from dart_storage import Storage, atomic_bytes, atomic_json, private

KINDS = {"analyze", "export", "derivatives", "compare", "merge"}
FLAGS = ("group_compound_objects", "create_multiple_objects", "process_OHM_data")
FORM_FIELDS = ("input_dir", "core_metadata_csv", "gems_metadata_csv", "collection-id", "azure_blob_storage_path")
ASSETS = core.GEMS_ASSET_EXTENSIONS


class Cancelled(Exception):
    pass


def read_csv(path: Path, *, metadata: bool = False) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames
        if not columns or len(set(columns)) != len(columns):
            raise ValueError(f"CSV needs a header with unique column names: {path}")
        if metadata and ("objectid" not in columns or not any(key in columns for key in core.CSV_FILENAME_FIELDS)):
            raise ValueError(f"Metadata CSV requires objectid and original_file_name (or legacy filename): {path}")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f"CSV rows do not match the header: {path}")
    if metadata and any(not row.get("objectid", "").strip() for row in rows):
        raise ValueError(f"Metadata CSV contains a row without an objectid: {path}")
    return core.normalize_csv_filename_columns(columns, rows)


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    atomic_bytes(path, output.getvalue().encode("utf-8"))


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def project_settings(storage: Storage, working: str) -> dict[str, Any]:
    directory = storage.working(working) / ".DART-working-directory"
    path = directory / core.APP_SETTINGS_FILENAME
    if not path.exists():
        if path.is_symlink():
            raise ValueError(f"Broken settings symlink: {path}")
        return dict(core.DEFAULT_APP_SETTINGS, file_to_id_map={})
    private(path)
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Invalid project settings object: {path}")
    settings = dict(core.DEFAULT_APP_SETTINGS, **value)
    mappings = settings["file_to_id_map"]
    if not isinstance(mappings, dict) or not all(isinstance(k, str) and isinstance(v, str) and v
                                               for k, v in mappings.items()):
        raise ValueError("file_to_id_map must contain string paths and nonempty string identifiers.")
    for key in FLAGS:
        if not isinstance(settings[key], bool):
            raise ValueError(f"{key} must be a boolean.")
    return settings


def save_settings(storage: Storage, working: str, values: dict[str, Any]) -> dict[str, Any]:
    directory = storage.working(working) / ".DART-working-directory"
    settings = project_settings(storage, working)
    valid, collection, error = core.validate_collection_id(str(values.get("collection-id", "")))
    if not valid:
        raise ValueError(error)
    if settings["file_to_id_map"] and settings["collection-id"] != collection:
        raise ValueError("This project already has durable IDs. Do not change its collection-id.")
    source = storage.source(str(values.get("input_dir", "")), directory=True)
    work = storage.working(working)
    if work.is_relative_to(source) or source == work:
        raise ValueError("The working directory must not be inside the source scan tree.")
    csv_path = storage.managed(str(values.get("core_metadata_csv", "")))
    valid, error = core.validate_core_metadata_csv(str(csv_path))
    if not valid:
        raise ValueError(error)
    gems = str(values.get("gems_metadata_csv", "")).strip()
    if gems:
        gems = str(storage.source(gems))
        valid, error = core.validate_gems_metadata_csv(gems)
        if not valid:
            raise ValueError(error)
    azure = str(values.get("azure_blob_storage_path", "")).strip()
    if azure:
        valid, error = core.validate_azure_path(azure)
        if not valid or "?" in azure:
            raise ValueError(error or "Use an Azure container/path, never a signed URL.")
    for key in FLAGS:
        if not isinstance(values.get(key), bool):
            raise ValueError(f"{key} must be a boolean.")
        settings[key] = values[key]
    if settings["group_compound_objects"] and not settings["process_OHM_data"]:
        columns, _ = read_csv(csv_path)
        if not {"parentid", "type", "display_template"}.issubset(columns):
            raise ValueError("Compound exports require parentid, type, and display_template columns in the core schema.")
    settings.update({"collection-id": collection, "core_metadata_csv": str(csv_path),
                     "gems_metadata_csv": gems, "azure_blob_storage_path": azure})
    # Preserve any existing encrypted credential unchanged; browser jobs never use it.
    directory.mkdir(mode=0o700, exist_ok=True)
    storage.check()
    atomic_json(directory / core.APP_SETTINGS_FILENAME, settings)
    atomic_json(directory / "web-form.json", {"input_dir": str(source)})
    return settings


class Workflow:
    def __init__(self, storage: Storage, job_dir: Path, job_id: str,
                 checkpoint: Callable[[], None], report: Callable[[str, float | None], None]) -> None:
        self.storage, self.job_dir, self.job_id = storage, job_dir, job_id
        self.checkpoint, self.report = checkpoint, report
        self.results: dict[str, Any] = {}

    def artifact(self, **paths: str) -> None:
        self.results.update(paths)
        self.report("Result paths: " + json.dumps(paths), None)

    def run(self, kind: str, inputs: dict[str, Any]) -> dict[str, Any]:
        if kind not in KINDS:
            raise ValueError(f"Unknown workflow: {kind}")
        self.work = self.storage.working(inputs["working_dir"])
        self.hidden = self.work / ".DART-working-directory"
        self.hidden.mkdir(mode=0o700, exist_ok=True)
        self.settings = project_settings(self.storage, str(self.work))
        self.checkpoint()
        if kind in {"analyze", "export"}:
            return self.assets(kind, inputs)
        if kind == "derivatives":
            return self.derivatives(inputs)
        if kind == "compare":
            return self.compare(inputs)
        return self.merge(inputs)

    def source_files(self, raw: str) -> list[Path]:
        source = self.storage.source(raw, directory=True)
        if self.work.is_relative_to(source):
            raise ValueError("The working directory must not be inside the source scan tree.")
        scan_root = source
        if self.settings["process_OHM_data"] and source.name != "OHM-data":
            scan_root = self.storage.source(str(source / "OHM-data"), directory=True)
        files = []
        def walk_error(error: OSError) -> None:
            raise error
        # Path.rglob suppresses some permission errors; os.walk exposes them.
        for directory, subdirs, names in os.walk(scan_root, onerror=walk_error, followlinks=False):
            self.checkpoint()
            subdirs[:] = sorted(name for name in subdirs if not name.startswith("."))
            if any((Path(directory) / name).is_symlink() for name in subdirs):
                raise ValueError(f"Source directory contains symlinked subdirectories; review them explicitly: {directory}")
            self.report(f"Scanning sources: {len(files)} assets found", None)
            for name in sorted(names):
                path = Path(directory) / name
                eligible = path.suffix.lower() == ".mp3" if self.settings["process_OHM_data"] else path.suffix.lower() in ASSETS
                if not name.startswith(".") and eligible:
                    files.append(path)
        if not files:
            raise ValueError("No supported digital assets found in the approved source directory.")
        resolved = []
        for path in sorted(files):
            self.checkpoint()
            # Reject aliases: persistent keys are never silently translated.
            if path.is_symlink() or path.resolve(strict=True) != path:
                raise ValueError(f"Source aliases/symlinks require explicit administrator review: {path}")
            resolved.append(self.storage.source(str(path)))
        return resolved

    def assets(self, kind: str, inputs: dict[str, Any]) -> dict[str, Any]:
        valid, collection, error = core.validate_collection_id(self.settings["collection-id"])
        if not valid:
            raise ValueError(error + "; save this project's settings first.")
        source = self.storage.source(inputs["input_dir"], directory=True)
        files = self.source_files(str(source))
        mappings = dict(self.settings["file_to_id_map"])
        core_path = self.storage.managed(self.settings["core_metadata_csv"])
        columns, existing = read_csv(core_path, metadata=True)
        page = SimpleNamespace(session=SimpleNamespace(
            generated_ids=set(mappings.values()) | {row["objectid"] for row in existing if row.get("objectid")}))
        objects = []
        auxiliary = []
        for index, path in enumerate(files):
            self.checkpoint()
            stable = get_stable_path(str(path))
            if self.settings["process_OHM_data"]:
                object_id = core.get_ohm_filename_id(path, collection)
            else:
                object_id = mappings.get(stable) or core.get_filename_dg_id(path, collection)
                if not object_id:
                    object_id = core.generate_unique_id(page, collection)
            mappings[stable] = object_id
            page.session.generated_ids.add(object_id)
            objects.append(dict(objectid=object_id, filepath=str(path), filename=path.name,
                                display_template=get_display_template(path.suffix), parentid=None))
            self.report(f"Assigned or reused IDs: {index + 1}/{len(files)}", (index + 1) / len(files) * 0.3)
        parents = []
        if not self.settings["process_OHM_data"]:
            parents, mappings, _, _ = analyze_compound_objects(
                objects, self.settings["group_compound_objects"], mappings, page, collection,
                self.settings["create_multiple_objects"],
                add_log_message=lambda message: self.report(message, None))
        identifiers = [obj["objectid"] for obj in [*parents, *objects]]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Duplicate object IDs found; review existing mappings and filenames.")
        self.checkpoint()
        # IDs are committed before network work so a failed/cancelled upload cannot remint them.
        self.settings["file_to_id_map"] = mappings
        atomic_json(self.hidden / core.APP_SETTINGS_FILENAME, self.settings)
        analysis = self.job_dir / "analysis.json"
        self.artifact(analysis=str(analysis), settings=str(self.hidden / core.APP_SETTINGS_FILENAME))
        atomic_json(analysis, {"objects": objects, "parents": parents})
        result = dict(analysis=str(analysis), files=len(objects), parents=len(parents),
                      settings=str(self.hidden / core.APP_SETTINGS_FILENAME))
        if kind == "analyze":
            return result
        if self.settings["process_OHM_data"]:
            for path in files:
                for sibling in path.parent.iterdir():
                    if sibling.is_file():
                        self.storage.source(str(sibling))
                transcript = core.find_ohm_transcript_csv(path)
                if transcript is None:
                    raise ValueError(f"Missing OHM transcript beside {path}")
                destination = self.work / "_data"
                if destination.exists() and (destination.is_symlink() or not destination.is_dir()):
                    raise ValueError("OHM _data destination must be a real project directory.")
                for folder in ("transcripts",):
                    target = destination / folder
                    if target.exists() and target.is_symlink():
                        raise ValueError(f"OHM destination must not be a symlink: {target}")
                target_file = destination / "transcripts" / core.get_ohm_filename(transcript, collection)
                if target_file.is_symlink():
                    raise ValueError(f"OHM transcript destination must not be a symlink: {target_file}")
                read_csv(transcript)
                transcript_json = core.find_ohm_transcript_json(path)
                if transcript_json is not None:
                    json.loads(transcript_json.read_text())
            self.artifact(transcripts=str(self.work / "_data" / "transcripts"))
            objects, auxiliary, _, _ = core.prepare_ohm_data_objects(
                files, str(self.work), mappings, collection, page,
                copy_transcript=lambda src, dest: atomic_bytes(dest, src.read_bytes()))
            self.settings["file_to_id_map"] = mappings
            self.checkpoint()
            atomic_json(self.hidden / core.APP_SETTINGS_FILENAME, self.settings)
        client = self.azure(inputs)
        uploaded = skipped = 0
        if client is not None:
            for index, obj in enumerate(objects):
                self.checkpoint()
                obj["object_location"], did_upload = self.upload(
                    client, Path(obj["filepath"]), self.settings["azure_blob_storage_path"],
                    obj["objectid"], inputs["overwrite"])
                uploaded += int(did_upload)
                skipped += int(not did_upload)
                self.report(f"Original uploads: {index + 1}/{len(objects)}", 0.3 + 0.5 * (index + 1) / len(objects))
            for obj in auxiliary:
                self.checkpoint()
                destination = self.settings["azure_blob_storage_path"]
                if obj["azure_path_type"] == "transcripts":
                    destination = core.get_parallel_azure_path(destination, "transcripts")
                self.upload(client, Path(obj["source"]), destination, obj["azure_object_id"], inputs["overwrite"])
        columns, rows = build_export_rows(columns, objects, parents, self.settings["process_OHM_data"])
        output = self.hidden / f"DART_export_{self.job_id}.csv"
        self.artifact(csv=str(output))
        self.checkpoint()
        write_csv(output, list(dict.fromkeys(columns)), rows)
        result.update(csv=str(output), rows=len(rows), uploaded=uploaded, skipped_uploads=skipped)
        return result

    def azure(self, inputs: dict[str, Any]):
        if not inputs.get("allow_uploads"):
            if inputs.get("overwrite"):
                raise ValueError("Overwrite requires explicit upload consent.")
            return None
        connection = os.environ.get("DART_AZURE_CONNECTION_STRING", "")
        if not connection:
            raise ValueError("Upload consent given, but DART_AZURE_CONNECTION_STRING is missing from the private environment file.")
        path = self.settings["azure_blob_storage_path"]
        valid, error = core.validate_azure_path(path)
        if not valid or not path:
            raise ValueError(error or "Configure an Azure container/path first.")
        self.checkpoint()
        # No account probe or container creation is attempted without per-job consent.
        return core.BlobServiceClient.from_connection_string(
            connection, connection_timeout=10, read_timeout=30, retry_total=2)

    def upload(self, client, source: Path, destination: str, object_id: str, overwrite: bool) -> tuple[str, bool]:
        if "/" in object_id or "\\" in object_id or object_id in {".", ".."}:
            raise ValueError("Object IDs cannot contain path separators.")
        parts = destination.strip("/").split("/", 1)
        container = parts[0]
        blob = (parts[1] + "/" if len(parts) == 2 else "") + object_id + source.suffix
        blob_client = client.get_blob_client(container=container, blob=blob)
        self.checkpoint()
        exists = blob_client.exists(timeout=30)
        if exists and not overwrite:
            return blob_client.url.split("?", 1)[0], False
        # Unlike desktop mode, browser mode requires an existing approved container.
        last_progress = 0.0
        def progress(current: int, total: int) -> None:
            nonlocal last_progress
            self.checkpoint()
            if time.monotonic() - last_progress >= 0.5 or current == total:
                self.report(f"Uploading {source.name}: {current}/{total} bytes", None)
                last_progress = time.monotonic()
        with source.open("rb") as handle:
            blob_client.upload_blob(handle, overwrite=overwrite, timeout=30,
                                    progress_hook=progress,
                                    content_settings=core.ContentSettings(content_type=core.get_mime_type(source.name)))
        self.checkpoint()
        return blob_client.url.split("?", 1)[0], True

    def derivatives(self, inputs: dict[str, Any]) -> dict[str, Any]:
        csv_path = self.storage.managed(inputs["csv_path"])
        columns, rows = read_csv(csv_path, metadata=True)
        for column in ("image_small", "image_thumb"):
            if column not in columns:
                columns.append(column)
        directory = self.hidden / f"derivatives_{self.job_id}"
        directory.mkdir(mode=0o700)
        self.artifact(derivatives=str(directory))
        client = self.azure(inputs)
        generated = 0
        for index, row in enumerate(rows):
            self.checkpoint()
            name = core.get_csv_filename_value(row)
            if not name or name.startswith("_"):
                continue
            if not row.get("objectid") or not re_safe_id(row["objectid"]):
                raise ValueError(f"Missing or unsafe object ID for {name}")
            source = self.storage.source(row.get("filepath", ""))
            if self.settings["process_OHM_data"]:
                sibling = core.find_ohm_sibling_image(source)
                if sibling is None:
                    self.report(f"No OHM sibling image; skipped {name}", (index + 1) / max(1, len(rows)))
                    continue
                source = self.storage.source(str(sibling))
            if source.suffix.lower() not in core.GEMS_DERIVATIVE_EXTENSIONS:
                continue
            for field, suffix, size, target in (("image_small", "_SMALL", 800, "smalls"),
                                                ("image_thumb", "_TN", 400, "thumbs")):
                self.checkpoint()
                output = directory / f"{row['objectid']}{suffix}.jpg"
                if source.suffix.lower() == ".pdf":
                    ok, message = core.generate_pdf_derivative(str(source), str(output), size, size, quality=85)
                else:
                    ok, message = core.generate_derivative(str(source), str(output), size, size, quality=85, temp_dir=str(directory))
                if not ok:
                    raise RuntimeError(message)
                if client is not None:
                    destinations = get_derivative_azure_paths(self.settings["azure_blob_storage_path"])
                    destination = destinations[0 if target == "smalls" else 1]
                    row[field], _ = self.upload(client, output, destination, row["objectid"] + suffix, inputs["overwrite"])
                else:
                    row[field] = str(output)
                generated += 1
            self.report(f"Derivative rows: {index + 1}/{len(rows)}", (index + 1) / max(1, len(rows)))
        by_id = {row["objectid"]: row for row in rows if row.get("objectid")}
        for row in rows:
            name = core.get_csv_filename_value(row)
            if name.startswith("_"):
                children = [candidate for candidate in rows
                            if core.get_csv_filename_value(candidate) == name[1:]]
                descendants = []
                for candidate in children:
                    parent_id = candidate.get("parentid")
                    seen = set()
                    while parent_id and parent_id not in seen:
                        seen.add(parent_id)
                        if parent_id == row["objectid"]:
                            descendants.append(candidate)
                            break
                        parent_id = by_id.get(parent_id, {}).get("parentid")
                if len(descendants) == 1:
                    for field in ("image_small", "image_thumb"):
                        row[field] = descendants[0].get(field, "")
                else:
                    self.report(f"Compound {row['objectid']}: no unambiguous first-child derivative", None)
        output = self.hidden / f"DART_export_with_derivatives_{self.job_id}.csv"
        self.artifact(csv=str(output))
        self.checkpoint()
        write_csv(output, columns, rows)
        return dict(csv=str(output), derivatives=str(directory), images=generated, rows=len(rows),
                    local_only=client is None)

    def compare(self, inputs: dict[str, Any]) -> dict[str, Any]:
        from csvdiff import diff_files

        old = self.storage.managed(self.settings["core_metadata_csv"])
        new = self.storage.managed(inputs["csv_path"])
        if old == new:
            raise ValueError("Choose an export different from the core CSV.")
        old_digest = digest(old)
        old_columns, old_rows = read_csv(old, metadata=True)
        new_columns, new_rows = read_csv(new, metadata=True)
        for label, rows in (("core", old_rows), ("export", new_rows)):
            names = [core.get_csv_filename_value(row) for row in rows]
            if not all(names) or len(set(names)) != len(names):
                raise ValueError(f"The {label} CSV has missing/duplicate original_file_name keys; resolve ambiguity before comparing.")
        if inputs.get("backfill"):
            gems = self.storage.source(self.settings["gems_metadata_csv"])
            gems_columns, gems_rows = read_csv(gems)
            new_rows, stats = core.backfill_dart_export_from_gems(new_columns, new_rows, gems_columns, gems_rows)
            atomic_json(self.job_dir / "gems-backfill.json", stats)
        before = self.job_dir / "core-snapshot.csv"
        after = self.job_dir / "export-snapshot.csv"
        old_columns = [column for column in old_columns if column != "filepath"]
        new_columns = [column for column in new_columns if column != "filepath"]
        write_csv(before, old_columns, old_rows)
        write_csv(after, new_columns, new_rows)
        self.checkpoint()
        changes = diff_files(str(before), str(after), index_columns=[core.CSV_FILENAME_FIELD])
        if digest(old) != old_digest:
            raise ValueError("Core CSV changed during comparison. Compare again before reviewing.")
        plan = dict(core=str(old), core_sha256=old_digest, columns=old_columns, changes=changes,
                    source=str(new), warning_missing_metadata=core.should_warn_missing_metadata(changes.get("added", [])))
        path = self.job_dir / "comparison.json"
        self.artifact(comparison=str(path))
        atomic_json(path, plan)
        return dict(comparison=str(path), added=len(changes.get("added", [])),
                    changed=len(changes.get("changed", [])), missing=len(changes.get("removed", [])),
                    warning_missing_metadata=plan["warning_missing_metadata"])

    def merge(self, inputs: dict[str, Any]) -> dict[str, Any]:
        if not inputs.get("confirm_merge"):
            raise ValueError("Review the comparison and explicitly confirm the core CSV write.")
        plan_path = Path(inputs["comparison"])
        if plan_path.name != "comparison.json" or plan_path.parent.parent != self.storage.jobs:
            raise ValueError("Select a persisted DART comparison job.")
        private(plan_path)
        plan = json.loads(plan_path.read_text())
        old = self.storage.managed(plan["core"])
        if old != self.storage.managed(self.settings["core_metadata_csv"]):
            raise ValueError("Comparison belongs to another core CSV.")
        if core.is_protected_core_csv_name(old):
            raise ValueError("The reserved collection-template.csv must never be overwritten.")
        if digest(old) != plan["core_sha256"]:
            raise ValueError("Core CSV changed since comparison. Compare again before merging.")
        columns, rows = read_csv(old, metadata=True)
        selected_added = inputs.get("selected_added", [])
        selected_fields = inputs.get("selected_fields", [])
        changes = plan["changes"]
        if not selected_added and not selected_fields:
            raise ValueError("Select at least one addition or field change.")
        indexed = {core.get_csv_filename_value(row): row for row in rows}
        for index in selected_added:
            if type(index) is not int or not 0 <= index < len(changes.get("added", [])):
                raise ValueError("Invalid selected addition.")
            record = changes["added"][index]
            if core.get_csv_filename_value(record) in indexed:
                raise ValueError("Selected record already exists in core.")
            rows.append(record)
        for selection in selected_fields:
            if not isinstance(selection, list) or len(selection) != 2:
                raise ValueError("Invalid selected field.")
            index, field = selection
            if type(index) is not int or not 0 <= index < len(changes.get("changed", [])):
                raise ValueError("Invalid changed-record selection.")
            change = changes["changed"][index]
            if field not in columns or field not in change["fields"] or field in core.CSV_FILENAME_FIELDS or field == "objectid":
                raise ValueError("Only existing metadata fields may be changed; identifiers are protected.")
            indexed[change["key"][0]][field] = change["fields"][field]["to"]
        known = set()
        for row in rows:
            value = row.get("objectid")
            if not value or value in known:
                raise ValueError("Merge would introduce missing/duplicate object IDs.")
            known.add(value)
        self.checkpoint()
        backup = self.hidden / f"{old.name}.backup_{self.job_id}"
        self.artifact(core=str(old), backup=str(backup))
        atomic_bytes(backup, old.read_bytes())
        self.checkpoint()
        if digest(old) != plan["core_sha256"]:
            raise ValueError("Core CSV changed before commit; merge refused.")
        write_csv(old, columns, rows)
        return dict(core=str(old), backup=str(backup), rows=len(rows), additions=len(selected_added),
                    fields_updated=len(selected_fields), source_retirement=False)


def re_safe_id(value: str) -> bool:
    import re
    return bool(re.fullmatch(r"[a-zA-Z0-9_-]+", value))
