"""Processing shared by the desktop application and managed jobs."""
import logging
import re
from pathlib import Path
from common_dg_utilities.dg_utils import generate_unique_id, get_mime_type

logger = logging.getLogger(__name__)


def select_compound_derivative_child(
    parent: dict[str, str], rows: list[dict[str, str]],
) -> dict[str, str] | None:
    """Choose the first image in this family, retaining a first-child PDF if no image exists."""
    def filename(row: dict[str, str]) -> str:
        return (row.get("original_file_name") or row.get("filename") or "").strip()

    parent_id = parent.get("objectid")
    if not parent_id:
        return None
    by_id = {row["objectid"]: row for row in rows if row.get("objectid")}
    descendants = []
    for row in rows:
        name = filename(row)
        if not name or name.startswith("_"):
            continue
        ancestor = row.get("parentid")
        seen = set()
        while ancestor and ancestor not in seen:
            seen.add(ancestor)
            if ancestor == parent_id:
                descendants.append(row)
                break
            ancestor = by_id.get(ancestor, {}).get("parentid")
    first_name = filename(parent).removeprefix("_")
    first = [row for row in descendants if filename(row) == first_name]
    if len(first) == 1 and get_display_template(Path(first_name).suffix) == "image":
        return first[0]
    images = sorted(
        (row for row in descendants if get_display_template(Path(filename(row)).suffix) == "image"),
        key=filename,
    )
    if not images:
        if len(first) == 1 and get_display_template(Path(first_name).suffix) == "pdf":
            return first[0]
        return None
    if sum(filename(row) == filename(images[0]) for row in images) != 1:
        return None
    return images[0]


def get_derivative_azure_paths(azure_path: str) -> tuple[str, str]:
    """Preserve Function 3's container substitution and unchanged blob subpath."""
    parts = azure_path.strip().strip("/").split("/", 1)
    container = parts[0]
    base_path = "/" + parts[1] if len(parts) == 2 else ""
    return (container.replace("objs", "smalls") + base_path,
            container.replace("objs", "thumbs") + base_path)


def get_stable_path(full_path: str) -> str:
    """Remove a macOS network-volume prefix for persistent ID mapping."""
    path_obj = Path(full_path)
    if len(path_obj.parts) >= 3 and path_obj.parts[0] == '/' and path_obj.parts[1] == 'Volumes':
        stable = Path(*path_obj.parts[3:])
        logger.debug(f"[STABLE PATH] {full_path} -> {stable}")
        return str(stable)
    return full_path


def analyze_compound_objects(objects, group_compound, file_to_id_map, page, collection_id="", create_multiple=True, add_log_message=logger.debug):
    """
    Analyze objects for compound grouping patterns and assign parent/child relationships.

    This function performs three-pass analysis:
    1. Parse filenames to extract prefixes and sequence numbers
    2. Match unnumbered files to numbered prefixes
    3. Find common prefixes among remaining unnumbered files

    Args:
        objects: List of object dicts with objectid, filepath, filename
        group_compound: Boolean, whether to perform compound grouping
        file_to_id_map: Dict of existing file/compound ID mappings
        page: Flet page object for ID generation
        collection_id: Required collection identifier prefix for newly generated IDs
        create_multiple: When True (default), each numeric sequence of 2+ numbered
            files is nested under its own 'multiple' sub-object. When False, numbered
            files attach directly to the folder's compound (flat Alma/GEMS-style
            compounds); sequence numbers are still recorded for ordering.

    Returns:
        tuple: (compound_objects, file_to_id_map, new_mappings, reused_mappings)
            - compound_objects: One untitled 'compound' entry per folder, plus a
              nested 'multiple' entry (type='multiple', parentid=compound's objectid)
              for each numeric sequence (2+ numbered files) found in that folder
            - file_to_id_map: Updated mapping dict (with new compound IDs)
            - new_mappings: Count of new compound IDs created
            - reused_mappings: Count of existing compound IDs reused

    Side effects:
        Modifies objects in place, adding: parentid, type, sequence_number
    """
    compound_objects = []
    compound_new_mappings = 0
    compound_reused_mappings = 0

    if not group_compound:
        # No compound grouping - all objects are standalone
        add_log_message(f"[DEBUG] Compound grouping DISABLED - all objects standalone")
        for obj in objects:
            obj["parentid"] = None
            obj["type"] = "single"
        return compound_objects, file_to_id_map, compound_new_mappings, compound_reused_mappings

    add_log_message(f"[DEBUG] Compound grouping ENABLED - analyzing filename patterns")
    if not create_multiple:
        add_log_message(f"[DEBUG] create_multiple_objects DISABLED - numbered sequences attach directly to the compound")
    logger.info("[DEBUG] Starting compound object analysis")

    # FIRST PASS: Parse all filenames to extract prefix and number components
    parsed_files = []
    numbered_prefixes = set()  # Track prefixes from numbered files

    for obj in objects:
        stem = Path(obj['filename']).stem

        # Extract prefix and trailing sequence number
        # Pattern: everything before the LAST number is the prefix, last number is sequence
        match = re.match(r'^(.+?)[\s_\-]*(\d+)$', stem)
        if match:
            prefix = match.group(1).strip().lower()  # Normalize: lowercase, strip whitespace
            number = int(match.group(2))
            numbered_prefixes.add(prefix)
            parsed_files.append({
                'obj': obj,
                'prefix': prefix,
                'number': number,
                'filename': obj['filename'],
                'raw_stem': stem
            })
            logger.info(f"[PARSE] '{obj['filename']}' → prefix: '{prefix}', number: {number}")
        else:
            # No trailing number - defer prefix assignment
            parsed_files.append({
                'obj': obj,
                'prefix': None,  # Will be assigned in second pass
                'number': None,
                'filename': obj['filename'],
                'raw_stem': stem
            })
            logger.info(f"[PARSE] '{obj['filename']}' → no trailing number (defer prefix assignment)")

    # SECOND PASS: For unnumbered files, find matching prefix from numbered files.
    # Numbered prefixes are per-folder: a folder's unnumbered files may only borrow
    # a prefix from numbered files in the SAME folder (grouping never crosses folders).
    folder_numbered_prefixes = {}
    for pf in parsed_files:
        if pf['number'] is not None:
            pf_folder = str(Path(pf['obj']['filepath']).parent)
            folder_numbered_prefixes.setdefault(pf_folder, set()).add(pf['prefix'])
    logger.info(f"[PREFIX MATCHING] Found {len(numbered_prefixes)} numbered prefixes across {len(folder_numbered_prefixes)} folders: {sorted(numbered_prefixes)}")

    for pf in parsed_files:
        if pf['prefix'] is None:  # Unnumbered file needing prefix assignment
            stem_lower = pf['raw_stem'].strip().lower()
            best_match = None
            best_match_length = 0

            # Check if this stem starts with any known numbered prefix from its own folder
            pf_folder = str(Path(pf['obj']['filepath']).parent)
            for known_prefix in folder_numbered_prefixes.get(pf_folder, set()):
                if stem_lower.startswith(known_prefix):
                    # Verify there's a separator or end after prefix (not just substring match)
                    remainder = stem_lower[len(known_prefix):]
                    if not remainder or remainder[0] in [' ', '_', '-']:
                        # Valid match - track longest match
                        if len(known_prefix) > best_match_length:
                            best_match = known_prefix
                            best_match_length = len(known_prefix)

            if best_match:
                pf['prefix'] = best_match
                logger.info(f"[PREFIX MATCH] '{pf['filename']}' matched prefix '{best_match}' (common with numbered files in its folder)")
            else:
                # No match - use full stem as its own prefix (may be refined in pass 3)
                pf['prefix'] = stem_lower
                logger.info(f"[PREFIX MATCH] '{pf['filename']}' → no match in its folder, using full stem: '{stem_lower}'")

    # THIRD PASS: Find common prefixes among remaining unnumbered files, per folder.
    # 'Numbered in this folder' is judged per folder (same scope as Pass 2).
    unmatched = [pf for pf in parsed_files
                 if pf['number'] is None and pf['prefix'] not in folder_numbered_prefixes.get(str(Path(pf['obj']['filepath']).parent), set())]

    logger.info(f"[THIRD PASS] Total parsed files: {len(parsed_files)}")
    logger.info(f"[THIRD PASS] Unnumbered files: {len([pf for pf in parsed_files if pf['number'] is None])}")
    logger.info(f"[THIRD PASS] Numbered prefixes known: {sorted(numbered_prefixes)}")
    logger.info(f"[THIRD PASS] Unmatched files (for Pass 3): {len(unmatched)}")
    add_log_message(f"[THIRD PASS] Checking {len(unmatched)} unmatched unnumbered files for common patterns")

    if len(unmatched) >= 2:
        logger.info(f"[COMMON PREFIX SEARCH] Analyzing {len(unmatched)} unmatched files for common patterns")
        add_log_message(f"[COMMON PREFIX SEARCH] Analyzing {len(unmatched)} unmatched files")

        # List all unmatched files for debugging
        for pf in unmatched:
            logger.info(f"[COMMON PREFIX SEARCH] Unmatched file: '{pf['filename']}' with prefix: '{pf['prefix']}'")

        # Build a map of potential base prefixes, keyed by folder so a shared base
        # only groups unnumbered files that live in the SAME folder.
        potential_bases = {}
        for pf in unmatched:
            stem = pf['prefix']
            # Try to extract base by removing last word after separator
            match = re.match(r'^(.+)[\s_\-]+\w+$', stem)
            if match:
                # Strip whitespace AND trailing separators to normalize
                potential_base = match.group(1).strip().rstrip(' _-')
                logger.info(f"[COMMON PREFIX] '{pf['filename']}' (stem: '{stem}') → potential base: '{potential_base}'")
                if len(potential_base) >= 3:
                    pf_folder = str(Path(pf['obj']['filepath']).parent)
                    if (pf_folder, potential_base) not in potential_bases:
                        potential_bases[(pf_folder, potential_base)] = []
                    potential_bases[(pf_folder, potential_base)].append(pf)
            else:
                logger.info(f"[COMMON PREFIX] '{pf['filename']}' (stem: '{stem}') → NO MATCH for base extraction regex")

        logger.info(f"[COMMON PREFIX] Found {len(potential_bases)} potential folder/base pair(s): {sorted(potential_bases.keys())}")

        # Apply common base to files that share it (2+ files in one folder with same base)
        for (folder, base), files in potential_bases.items():
            if len(files) >= 2:
                msg = f"[COMMON PREFIX] Found {len(files)} files in {Path(folder).name} sharing base: '{base}'"
                logger.info(msg)
                add_log_message(msg)
                for pf in files:
                    old_prefix = pf['prefix']
                    pf['prefix'] = base
                    logger.info(f"[COMMON PREFIX] '{pf['filename']}' → prefix changed from '{old_prefix}' to '{base}'")

    # Group by (folder, prefix): prefix comparisons must never span folders, otherwise
    # same-named singles in different subfolders (GEMS one-folder-per-record layout)
    # would collapse into one misassigned compound. A prefix < 3 chars never groups.
    prefix_groups = {}
    for pf in parsed_files:
        prefix = pf['prefix']
        # Only group if prefix is 3+ characters (weighted matching)
        if len(prefix) >= 3:
            pf_folder = str(Path(pf['obj']['filepath']).parent)
            if (pf_folder, prefix) not in prefix_groups:
                prefix_groups[(pf_folder, prefix)] = []
            prefix_groups[(pf_folder, prefix)].append(pf)

    # Analyze each prefix group for patterns
    add_log_message(f"[GROUP ANALYSIS] Found {len(prefix_groups)} folder/prefix groups (3+ char prefixes)")
    logger.info(f"[GROUP ANALYSIS] Analyzing {len(prefix_groups)} folder/prefix groups")

    groups = {}
    for (pf_folder, prefix), items in prefix_groups.items():
        # Extract numbers from this group
        numbers = [item['number'] for item in items if item['number'] is not None]

        if len(items) < 2:
            # Single file with this prefix - don't group
            logger.info(f"[GROUP: '{prefix}'] Single file only - not creating compound")
            continue

        # Analyze numbering pattern
        is_sequential = False
        zero_pad_width = 0
        analysis_msg = f"[GROUP: '{prefix}'] {len(items)} files ({len(numbers)} numbered, {len(items)-len(numbers)} unnumbered)"
        add_log_message(analysis_msg)
        logger.info(analysis_msg)

        if len(numbers) >= 2:
            # Check if numbers form a sequence
            numbers_sorted = sorted(numbers)
            gaps = [numbers_sorted[i+1] - numbers_sorted[i] for i in range(len(numbers_sorted)-1)]
            max_gap = max(gaps)
            avg_gap = sum(gaps) / len(gaps)

            # Calculate zero-padding width based on max number
            max_number = max(numbers_sorted)
            zero_pad_width = len(str(max_number))

            # Sequential if average gap ≤ 2 and max gap ≤ 5 (allows small missing numbers)
            if avg_gap <= 2.0 and max_gap <= 5:
                is_sequential = True
                msg = f"  ✓ SEQUENTIAL pattern detected: range {min(numbers)}-{max(numbers)}, avg gap {avg_gap:.1f}, max gap {max_gap}"
                add_log_message(msg)
                logger.info(msg)

                # Report zero-padding recommendation
                msg = f"  → Sequence numbers will be zero-padded to {zero_pad_width} digits (e.g., {str(min(numbers)).zfill(zero_pad_width)}, {str(max(numbers)).zfill(zero_pad_width)})"
                add_log_message(msg)
                logger.info(msg)

                if max_gap > 1:
                    missing_count = sum(1 for g in gaps if g > 1)
                    msg = f"  ℹ Note: {missing_count} gap(s) in sequence (e.g., missing numbers)"
                    add_log_message(msg)
                    logger.info(msg)
            else:
                msg = f"  ✗ Not sequential: avg gap {avg_gap:.1f}, max gap {max_gap} (too irregular)"
                add_log_message(msg)
                logger.info(msg)
        elif len(numbers) == 1:
            msg = f"  • Mixed: 1 numbered file + {len(items)-1} unnumbered files with same prefix"
            add_log_message(msg)
            logger.info(msg)
            zero_pad_width = len(str(numbers[0]))  # Use single number's width
        else:
            msg = f"  • All files unnumbered but share common prefix (3+ chars: '{prefix}')"
            add_log_message(msg)
            logger.info(msg)

        # Decision: Group if 2+ files share prefix (3+ chars)
        msg = f"  ➤ DECISION: Creating compound (common prefix '{prefix}', {len(items)} files)"
        add_log_message(msg)
        logger.info(msg)

        # Store group with padding info, keyed by (folder, prefix)
        groups[(pf_folder, prefix)] = {
            'files': [item['obj'] for item in items],
            'zero_pad_width': zero_pad_width,
            'items': items  # Keep parsed items for sorting
        }

    # Bucket groups (2+ files) by folder so each folder gets ONE top-level
    # compound; sequence groups (2+ numbered files) become nested 'multiple'
    # children, and non-sequence groups attach directly to the compound.
    # Groups are folder-scoped by construction, so the bucket key is the group's folder.
    folder_buckets = {}
    for (pf_folder, text_base), group_data in groups.items():
        group_files = group_data['files']
        if len(group_files) >= 2:
            folder_buckets.setdefault(pf_folder, []).append((text_base, group_data))
        else:
            # Single file - not part of a compound
            group_files[0]["parentid"] = None
            group_files[0]["type"] = "single"
            logger.info(f"[DEBUG] Single object (no compound): {group_files[0]['filename']}")

    for folder_path, folder_group_list in folder_buckets.items():
        stable_folder = get_stable_path(folder_path)
        compound_key = f"{stable_folder}::COMPOUND"

        if compound_key in file_to_id_map:
            compound_id = file_to_id_map[compound_key]
            compound_reused_mappings += 1
            add_log_message(f"[DEBUG] Reusing existing compound ID {compound_id} for folder {folder_path}")
            logger.info(f"[DEBUG] Reused compound: {compound_id} | Folder: {folder_path}")
        else:
            compound_id = generate_unique_id(page, collection_id)
            file_to_id_map[compound_key] = compound_id
            compound_new_mappings += 1
            add_log_message(f"[DEBUG] Created new compound {compound_id} for folder {folder_path}")
            logger.info(f"[DEBUG] New compound: {compound_id} | Folder: {folder_path}")

        # Deterministic first-file across all groups in this folder (for CSV filename indexing)
        all_items = [item for _, group_data in folder_group_list for item in group_data['items']]
        first_child_filename = sorted(all_items, key=lambda x: x['filename'])[0]['filename']
        total_child_count = sum(len(group_data['files']) for _, group_data in folder_group_list)

        compound_objects.append({
            "objectid": compound_id,
            "text_base": "",
            "display_text_base": "",  # Folder-level compound is untitled
            "child_count": total_child_count,
            "folder_path": folder_path,
            "zero_pad_width": 0,
            "type": "compound",
            "first_child_filename": first_child_filename
        })

        for text_base, group_data in folder_group_list:
            zero_pad_width = group_data['zero_pad_width']
            parsed_items = group_data['items']
            numbered_items = [item for item in parsed_items if item.get('number') is not None]
            unnumbered_items = [item for item in parsed_items if item.get('number') is None]
            numbered_items.sort(key=lambda x: x['number'])
            unnumbered_items.sort(key=lambda x: x['filename'])

            first_raw_stem = (numbered_items + unnumbered_items)[0]['raw_stem']
            prefix_length = len(text_base)
            if len(first_raw_stem) >= prefix_length:
                display_text_base = first_raw_stem[:prefix_length]
            else:
                display_text_base = first_raw_stem

            if create_multiple and len(numbered_items) >= 2:
                # A numeric sequence of 2+ files gets its own 'multiple' parent
                # nested under the compound; unnumbered files in the same group
                # become direct children of the compound (siblings of 'multiple').
                multiple_key = f"{stable_folder}::MULTIPLE::{text_base}"
                if multiple_key in file_to_id_map:
                    multiple_id = file_to_id_map[multiple_key]
                    compound_reused_mappings += 1
                    logger.info(f"[DEBUG] Reused multiple: {multiple_id} | Folder: {folder_path} | Base: '{text_base}'")
                else:
                    multiple_id = generate_unique_id(page, collection_id)
                    file_to_id_map[multiple_key] = multiple_id
                    compound_new_mappings += 1
                    logger.info(f"[DEBUG] New multiple: {multiple_id} | Folder: {folder_path} | Base: '{text_base}'")

                compound_objects.append({
                    "objectid": multiple_id,
                    "parentid": compound_id,
                    "text_base": text_base,
                    "display_text_base": display_text_base,
                    "child_count": len(numbered_items),
                    "folder_path": folder_path,
                    "zero_pad_width": zero_pad_width,
                    "type": "multiple",
                    "first_child_filename": numbered_items[0]['filename']
                })

                for parsed_item in numbered_items:
                    child_obj = parsed_item['obj']
                    child_obj["parentid"] = multiple_id
                    child_obj["type"] = "child"
                    child_obj["sequence_number"] = parsed_item.get('number')

                for parsed_item in unnumbered_items:
                    child_obj = parsed_item['obj']
                    child_obj["parentid"] = compound_id
                    child_obj["type"] = "child"
                    child_obj["sequence_number"] = None
            else:
                # Not a sequence (or 'multiple' creation disabled) - all items
                # in this group are direct compound children
                for parsed_item in numbered_items + unnumbered_items:
                    child_obj = parsed_item['obj']
                    child_obj["parentid"] = compound_id
                    child_obj["type"] = "child"
                    child_obj["sequence_number"] = parsed_item.get('number')

            logger.info(f"[DEBUG] Compound: {compound_id} | Folder: {folder_path} | Group base: '{text_base}' | Files: {[item['filename'] for item in parsed_items]}")

    add_log_message(f"[DEBUG] Compound analysis complete: {len(compound_objects)} compounds created")
    logger.info(f"[DEBUG] Total compound objects: {len(compound_objects)}")

    return compound_objects, file_to_id_map, compound_new_mappings, compound_reused_mappings


def get_display_template(file_extension):
    """
    Map file extension to CollectionBuilder display_template value.

    Args:
        file_extension: File extension (with or without leading dot)

    Returns:
        str: CollectionBuilder display_template value (image, video, audio, pdf, record)
    """
    ext = file_extension.lower().lstrip('.')

    # Image formats → "image"
    if ext in ['jpg', 'jpeg', 'png', 'gif', 'tif', 'tiff', 'bmp', 'webp']:
        return 'image'

    # Video formats → "video"
    elif ext in ['mp4', 'mov', 'avi', 'mkv', 'wmv', 'flv', 'webm']:
        return 'video'

    # Audio formats → "audio"
    elif ext in ['mp3', 'wav', 'flac', 'aac', 'ogg', 'm4a', 'wma']:
        return 'audio'

    # PDF → "pdf"
    elif ext == 'pdf':
        return 'pdf'

    # Archives and other formats → "record"
    elif ext in ['zip', 'tar', 'gz', '7z', 'rar', 'bz2']:
        return 'record'

    # Unknown → empty (will use CB default)
    else:
        return ''


def build_export_rows(template_columns, objects, compound_objects, process_ohm_data=False):
    """Build the existing Function 2 CSV shape without UI or file writes."""
    # Normalize to canonical filename column and ensure filepath is present.
    export_columns = ['original_file_name' if c == 'filename' else c for c in template_columns]
    if 'original_file_name' not in export_columns:
        export_columns.insert(1 if 'objectid' in export_columns else 0, 'original_file_name')

    # Ensure 'filepath' column is included (required by Function 3 for derivative generation)
    if 'filepath' not in export_columns:
        # Insert filepath after original_file_name for logical grouping
        if 'original_file_name' in export_columns:
            filename_idx = export_columns.index('original_file_name')
            export_columns.insert(filename_idx + 1, 'filepath')
        else:
            # No filename column? Add filepath at beginning
            export_columns.insert(0, 'filepath')


    if process_ohm_data:
        if 'parentid' not in export_columns:
            export_columns.append('parentid')
        if 'object_transcript' not in export_columns:
            export_columns.append('object_transcript')
        if 'type' not in export_columns:
            export_columns.append('type')
        if 'image_small' not in export_columns:
            export_columns.append('image_small')
        if 'image_thumb' not in export_columns:
            export_columns.append('image_thumb')
        if 'title' not in export_columns:
            export_columns.append('title')
        if 'interviewee' not in export_columns:
            export_columns.append('interviewee')
        if 'interviewer' not in export_columns:
            export_columns.append('interviewer')
        if 'subject' not in export_columns:
            export_columns.append('subject')

    rows = []
    # Write compound parent objects first (if compound grouping enabled)
    parent_rows = compound_objects
    if parent_rows:
        for compound in parent_rows:
            row = {}
            for col in export_columns:
                if col == 'objectid':
                    row[col] = compound.get('objectid', '')
                elif col == 'original_file_name':
                    # Use first child's filename with underscore prefix for indexing
                    # This maintains original_file_name as source of truth for ALL objects
                    first_child = compound.get('first_child_filename', '')
                    row[col] = f"_{first_child}" if first_child else ''
                elif col == 'filepath':
                    # Compound parents have no physical file
                    row[col] = ''
                elif col == 'parentid':
                    # Top-level compounds have no parent; nested 'multiple'
                    # objects (numeric sequences) point back to their compound
                    row[col] = compound.get('parentid', '') or ''
                elif col == 'display_template':
                    # Set compound_object layout for parent
                    row[col] = 'compound_object'
                elif col == 'type':
                    row[col] = compound.get('type', 'compound')
                elif col == 'image_small':
                    row[col] = compound.get('image_small', '')
                elif col == 'image_thumb':
                    row[col] = compound.get('image_thumb', '')
                elif col == 'title':
                    # Use display_text_base for title (preserves original case from filename)
                    title = compound.get('title', compound.get('display_text_base', ''))
                    row[col] = title.replace('_', ' ').replace('-', ' ')
                elif col == 'originating_system_id':
                    # Use display_text_base (common portion of compound family filenames)
                    row[col] = compound.get('originating_system_id', compound.get('display_text_base', ''))
                else:
                    row[col] = ''

            rows.append(row)

    # Write file objects (children or standalone)
    for obj in objects:
        # Build row with template columns
        row = {}
        for col in export_columns:
            # Map known fields
            if col == 'objectid':
                row[col] = obj.get('objectid', '')
            elif col == 'original_file_name':
                row[col] = obj.get('filename', '')
            elif col == 'filepath':
                row[col] = obj.get('filepath', '')
            elif col == 'parentid':
                row[col] = obj.get('parentid', '')
            elif col == 'display_template':
                row[col] = obj.get('display_template', '')
            elif col == 'format':
                # Auto-populate format with MIME type based on file extension
                filename = obj.get('filename', '')
                if filename:
                    row[col] = get_mime_type(filename)
                else:
                    row[col] = obj.get('format', '')
            elif col == 'object_location':
                row[col] = obj.get('object_location', '')
            elif col == 'type':
                row[col] = obj.get('type', '')
            elif col == 'object_transcript':
                row[col] = obj.get('object_transcript', '')
            elif col == 'transcript':
                row[col] = obj.get('object_transcript', '')
            elif col == 'title' and process_ohm_data:
                row[col] = obj.get('title', '')
            elif col == 'interviewee' and process_ohm_data:
                row[col] = obj.get('interviewee', '')
            elif col == 'interviewer' and process_ohm_data:
                row[col] = obj.get('interviewer', '')
            elif col == 'subject' and process_ohm_data:
                row[col] = obj.get('subject', '')
            elif col == 'originating_system_id':
                if process_ohm_data:
                    row[col] = obj.get('originating_system_id', '')
                else:
                    # Extract common portion of filename (prefix before numbers)
                    filename = obj.get('filename', '')
                    stem = Path(filename).stem
                    match = re.match(r'^(.+?)[\s_\-]*\d+$', stem)
                    if match:
                        row[col] = match.group(1).strip()
                    else:
                        row[col] = stem
            else:
                # Leave other columns empty for manual population
                row[col] = ''

        rows.append(row)

    return export_columns, rows
