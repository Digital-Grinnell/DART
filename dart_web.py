"""Private browser controls; no desktop file pickers or browser-owned workers."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import flet as ft

from dart_service import ACTIVE, JobService
from dart_storage import Storage, redact
from dart_workflows import FLAGS


def main(page: ft.Page, service: JobService) -> None:
    page.title = "DART - Private Linux Browser"
    page.padding = 24
    page.theme_mode = ft.ThemeMode.LIGHT
    page.scroll = ft.ScrollMode.AUTO
    session = page.session_id
    service.claim(session)
    defaults = service.defaults()
    work = ft.TextField(label="Working Project (Existing Private Server Directory)")
    source = ft.TextField(label="Source Directory (Approved Server Path; Read-Only)")
    collection = ft.TextField(label="Collection-ID (Collection-Specific; Required)")
    core = ft.TextField(label="Core Metadata CSV (Inside DART Projects)")
    gems = ft.TextField(label="Optional GEMS Metadata CSV (Read-Only)")
    azure = ft.TextField(label="Azure Container/Path (Existing Containers Only)")
    flags = {key: ft.Checkbox(label=key, value=defaults[key]) for key in FLAGS}
    remember = ft.Checkbox(label="Remember Only These Three Checkboxes As Defaults For New Collections", value=False)
    uploads = ft.Checkbox(label="Authorize Azure Uploads For This Next Job", value=False)
    overwrite = ft.Checkbox(label="Also Authorize Replacing Existing Azure Blobs", value=False)
    backfill = ft.Checkbox(label="Backfill Empty Metadata From Configured GEMS CSV", value=False)
    csv_path = ft.TextField(label="Export CSV For Derivatives Or Comparison (Explicit Server Path)")
    history = ft.Dropdown(label="Persisted Job History", options=[])
    status = ft.Text(selectable=True)
    results = ft.TextField(label="Job Inputs And Result Paths", multiline=True, read_only=True, min_lines=5, max_lines=14)
    log = ft.TextField(label="Redacted Job Log (Last 32 KiB)", multiline=True, read_only=True, min_lines=5, max_lines=14)
    progress = ft.ProgressBar(value=0, visible=False)
    operator_note = ft.Text(selectable=True)
    review = ft.Column()
    review_note = ft.Text(selectable=True)
    confirm_merge = ft.Checkbox(label="I Reviewed These Selections And Authorize Updating The Core CSV", value=False)
    selected_additions: list[ft.Checkbox] = []
    selected_changes: list[tuple[int, str, ft.Checkbox]] = []
    comparison: str | None = None
    selected: str | None = None
    connected = True
    poll_task = None
    action_errors: list[ft.Text] = []
    writer_controls: list[ft.Control] = []
    form_controls = [work, source, collection, core, gems, azure, remember, uploads, overwrite,
                     backfill, csv_path, confirm_merge, *flags.values()]

    def local_notice() -> ft.Text:
        notice = ft.Text(selectable=True, color=ft.Colors.RED_700)
        action_errors.append(notice)
        return notice

    configure_notice = local_notice()
    analyze_notice, export_notice, derivative_notice, compare_notice, merge_notice = [local_notice() for _ in range(5)]
    cancel_notice = local_notice()

    def call(notice: ft.Text, action) -> None:
        notice.value = ""
        notice.color = ft.Colors.RED_700
        try:
            action()
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            notice.value = redact(exc)
        page.update()

    def values() -> dict:
        return {"collection-id": collection.value or "", "input_dir": source.value or "",
                "core_metadata_csv": core.value or "", "gems_metadata_csv": gems.value or "",
                "azure_blob_storage_path": azure.value or "",
                **{key: bool(control.value) for key, control in flags.items()}}

    def load() -> None:
        if not service.claim(session):
            raise ValueError("Another browser tab is the active operator.")
        saved = service.load_form(work.value or "")
        for key, control in (("collection-id", collection), ("input_dir", source),
                             ("core_metadata_csv", core), ("gems_metadata_csv", gems),
                             ("azure_blob_storage_path", azure)):
            control.value = saved.get(key, "")
        for key, control in flags.items():
            control.value = saved[key]
        uploads.value = overwrite.value = confirm_merge.value = False
        configure_notice.value = "Loaded this project's settings. Upload and merge consent are never remembered."
        configure_notice.color = ft.Colors.GREEN_800

    def save() -> None:
        service.configure(session, work.value or "", values(), remember_defaults=bool(remember.value))
        load()
        configure_notice.value = "Project settings saved. Collection paths and IDs are not reusable global defaults."
        configure_notice.color = ft.Colors.GREEN_800

    def submit(kind: str, notice: ft.Text) -> None:
        saved = service.load_form(work.value or "")
        current = values()
        if any(saved.get(key, "") != value for key, value in current.items()):
            raise ValueError("Project fields differ from the saved settings. Validate And Save Project Settings first.")
        inputs = dict(working_dir=work.value or "", input_dir=source.value or "",
                      csv_path=csv_path.value or "", allow_uploads=bool(uploads.value),
                      overwrite=bool(overwrite.value), backfill=bool(backfill.value))
        if kind not in {"export", "derivatives"}:
            inputs.update(allow_uploads=False, overwrite=False)
        if kind == "merge":
            inputs.update(comparison=comparison or "", confirm_merge=bool(confirm_merge.value),
                          selected_added=[i for i, control in enumerate(selected_additions) if control.value],
                          selected_fields=[[i, field] for i, field, control in selected_changes if control.value])
        job_id = service.submit(session, kind, inputs)
        uploads.value = overwrite.value = confirm_merge.value = False
        notice.value = f"Submitted {kind}: {job_id}. Closing this tab will not stop the job."
        notice.color = ft.Colors.GREEN_800
        page.go(f"/jobs/{job_id}")
        refresh()

    def use_result() -> None:
        if not service.claim(session):
            raise ValueError("Another browser tab is the active operator.")
        job = next((job for job in service.jobs() if job["id"] == selected), None)
        if not job or job["state"] != "succeeded" or not job["result"].get("csv"):
            raise ValueError("Select a successful export or derivative job with a CSV result.")
        work.value = job["inputs"]["working_dir"]
        load()
        csv_path.value = job["result"]["csv"]

    def load_review() -> None:
        nonlocal comparison
        if not service.claim(session):
            raise ValueError("Another browser tab is the active operator.")
        job = next((job for job in service.jobs() if job["id"] == selected), None)
        if not job or job["state"] != "succeeded" or job["kind"] != "compare":
            raise ValueError("Select a successful comparison job.")
        service.storage.check()
        comparison = job["result"]["comparison"]
        plan = json.loads(Path(comparison).read_text())
        work.value = job["inputs"]["working_dir"]
        load()
        selected_additions.clear()
        selected_changes.clear()
        review.controls.clear()
        confirm_merge.value = False
        changes = plan["changes"]
        review.controls.append(ft.Text(f"Core: {plan['core']}", selectable=True))
        if plan["warning_missing_metadata"]:
            review.controls.append(ft.Text("WARNING: Most additions lack descriptive metadata. Review GEMS backfill before merging.",
                                           color=ft.Colors.RED_700, selectable=True))
        for record in changes.get("added", []):
            control = ft.Checkbox(label=f"Add: {record.get('original_file_name')} | {record.get('objectid')}", value=True)
            selected_additions.append(control)
            review.controls.extend([control, ft.Text(json.dumps(record, indent=2), selectable=True)])
        for index, change in enumerate(changes.get("changed", [])):
            review.controls.append(ft.Text(f"Changed: {change['key'][0]}", weight=ft.FontWeight.BOLD, selectable=True))
            for field, values_ in change.get("fields", {}).items():
                if field in {"objectid", "original_file_name", "filename"} or field not in plan["columns"]:
                    review.controls.append(ft.Text(f"Protected identifier or non-core field not selectable: {field}", selectable=True))
                    continue
                safe_default = field != "title" and bool(str(values_.get("to", "")).strip())
                control = ft.Checkbox(label=f"{field}: {values_.get('from', '')!r} -> {values_.get('to', '')!r}",
                                      value=safe_default)
                selected_changes.append((index, field, control))
                review.controls.append(control)
        review.controls.append(ft.Text(
            f"Missing-in-new records: {len(changes.get('removed', []))}; retained in core, never deleted.",
            selectable=True))
        review_note.value = "Review full values above. Title changes and empty replacements are unchecked; IDs are protected."

    def button(label: str, action, notice: ft.Text) -> ft.Control:
        control = ft.ElevatedButton(label, on_click=lambda _: call(notice, action))
        writer_controls.append(control)
        return control

    def route_changed(_event=None) -> None:
        nonlocal selected
        parts = page.route.strip("/").split("/")
        selected = parts[1] if len(parts) == 2 and parts[0] == "jobs" else None
        refresh()

    def refresh() -> None:
        nonlocal selected
        jobs = service.jobs()
        operator = service.claim(session)
        busy = any(job["state"] in ACTIVE for job in jobs)
        try:
            service.storage.check()
            storage_message = service.storage_error
        except (OSError, ValueError) as exc:
            storage_message = redact(exc)
        disabled = not operator or busy or bool(storage_message)
        for control in [*writer_controls, *form_controls, *selected_additions,
                        *(control for _, _, control in selected_changes)]:
            control.disabled = disabled
        cancel_button.disabled = not operator or not busy
        operator_note.value = ("Active Operator" if operator else "Read-Only: Another Browser Tab Is The Active Operator")
        if storage_message:
            operator_note.value += "\nSTORAGE ERROR: " + storage_message
            # Keep failures beside each submission action, not just above the page.
            for notice in action_errors:
                notice.value = storage_message
                notice.color = ft.Colors.RED_700
        history.options = [ft.dropdown.Option(job["id"], f"{job['created_at']} | {job['kind']} | {job['state']}")
                           for job in jobs]
        if selected is None and jobs:
            selected = jobs[0]["id"]
        history.value = selected
        job = next((job for job in jobs if job["id"] == selected), None)
        if job:
            status.value = f"{job['id']} | {job['state']}: {job['message']}"
            results.value = redact(json.dumps({key: job.get(key) for key in
                                              ("inputs", "result", "directory", "log", "settings_snapshot")}, indent=2))
            if job["state"] in {"failed", "interrupted"}:
                notices = dict(analyze=analyze_notice, export=export_notice, derivatives=derivative_notice,
                               compare=compare_notice, merge=merge_notice)
                notice = notices[job["kind"]]
                notice.value = f"{job['state']}: {job['message']}"
                notice.color = ft.Colors.RED_700
            progress.visible = job["state"] in ACTIVE
            progress.value = job["progress"]
            try:
                log.value = service.log_tail(job["id"])
            except (OSError, ValueError) as exc:
                log.value = redact(exc)
        else:
            status.value = "Unknown Job" if selected else "Ready"
        page.update()

    cancel_button = ft.ElevatedButton("Cancel Active Job", disabled=True,
                                     on_click=lambda _: call(cancel_notice, lambda: service.cancel(session)))
    history.on_change = lambda _: page.go(f"/jobs/{history.value}")
    page.on_route_change = route_changed

    async def poll() -> None:
        while connected:
            await asyncio.sleep(1)
            if connected:
                refresh()

    def disconnect(_event) -> None:
        nonlocal connected
        connected = False
        service.release(session)
        if poll_task is not None:
            poll_task.cancel()

    def connect(_event) -> None:
        nonlocal connected, poll_task
        if not connected:
            connected = True
            refresh()
            poll_task = page.run_task(poll)

    page.on_disconnect = page.on_close = disconnect
    page.on_connect = connect
    page.add(
        ft.Text("DART - Private Linux Browser", size=28, weight=ft.FontWeight.BOLD),
        ft.Text("One trusted operator. All paths are on the Linux server. Sources are read-only; no source retirement."),
        ft.Text(f"Configuration: {service.storage.config}\nData: {service.storage.data}", selectable=True),
        ft.Text("Approved External Sources: " + (", ".join(str(path) for path, _ in service.storage.sources) or "None Configured"),
                selectable=True),
        operator_note, ft.Divider(), ft.Text("0. Collection Settings", size=22),
        work, button("Load This Project's Settings", load, configure_notice),
        source, collection, core, gems, azure, *flags.values(), remember,
        button("Validate And Save Project Settings", save, configure_notice), configure_notice,
        ft.Divider(), ft.Text("1. Analyze And Save Durable IDs", size=22),
        ft.Text("This action commits mappings, without copying originals or contacting Azure."),
        button("Analyze And Save IDs", lambda: submit("analyze", analyze_notice), analyze_notice), analyze_notice,
        ft.Divider(), ft.Text("2. Export Metadata", size=22),
        ft.Text("Uploads are OFF unless explicitly authorized below. Export uses the saved collection settings."),
        uploads, overwrite,
        button("Export CSV", lambda: submit("export", export_notice), export_notice), export_notice,
        ft.Divider(), ft.Text("3. Generate Derivatives", size=22), csv_path,
        button("Use Selected Job's CSV And Project", use_result, derivative_notice),
        ft.Text("Local-only derivatives are retained. Authorize uploads above only when approved."),
        button("Generate Derivatives", lambda: submit("derivatives", derivative_notice), derivative_notice), derivative_notice,
        ft.Divider(), ft.Text("4. Compare, Review, And Merge", size=22), backfill,
        button("Compare CSV With Core", lambda: submit("compare", compare_notice), compare_notice), compare_notice,
        button("Load Selected Comparison For Review", load_review, merge_notice), review_note, review,
        confirm_merge, button("Merge Reviewed Selections", lambda: submit("merge", merge_notice), merge_notice), merge_notice,
        ft.Divider(), ft.Text("Job History And Progress", size=22), history, status, progress, results,
        cancel_button, cancel_notice, log,
        ft.Text("Tab closure does not cancel jobs. Service restart marks unfinished jobs interrupted; it never resumes them."),
    )
    refresh()
    poll_task = page.run_task(poll)


def launch(storage: Storage, *, port: int = 8560) -> None:
    if port in {8550, 8551} or not 1024 <= port <= 65535:
        raise ValueError("Use an unprivileged DART port, not GEMS ports 8550/8551.")
    if os.environ.get("FLET_SERVER_IP", "127.0.0.1") != "127.0.0.1":
        raise ValueError("DART browser mode only binds 127.0.0.1. Use an SSH tunnel.")
    os.environ["FLET_SERVER_IP"] = "127.0.0.1"
    os.environ["FLET_SERVER_PORT"] = str(port)
    # Never expose the repository or configuration through Flet's static assets.
    with JobService(storage) as service:
        ft.app(target=lambda page: main(page, service), host="127.0.0.1", port=port, view=None,
               assets_dir=str(Path(__file__).parent / "_dart_no_public_assets"))
