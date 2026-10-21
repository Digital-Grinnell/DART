# DART Architecture & Key Design Decisions

## Optional Managed Linux Architecture

The native Flet entry point remains `app.py`; managed Linux/browser and
headless operation use `dart_linux.py`. See
[Installation](INSTALL-LINUX.md), [Operation](LINUX-WEB-OVERVIEW.md), and
[Acceptance](LINUX-ACCEPTANCE.md).

- `dart_processing.py` contains the extracted compound algorithm, stable-path
  helper, display templates, and CSV row construction shared with desktop.
- `dart_workflows.py` coordinates existing identifier/media/OHM/GEMS helpers
  without running a desktop page or native picker. Module import no longer
  creates home-directory logs.
- `dart_storage.py` requires explicit private roots, markers, permissions,
  source allowlists and real mount points, with no automatic fallback.
- `dart_service.py` owns advisory locks on both roots, one operator lease,
  one non-browser-owned worker, atomic job state, progress, redacted logs,
  cancellation, and restart-to-interrupted recovery.
- `dart_web.py` provides server-path controls, action-local errors, history,
  explicit upload consent, and selective comparison/merge review.
- `dart_acceptance.py` exercises isolated disposable roots and a separate
  loopback port, retains evidence, and leaves unverified manual checks pending.

Managed settings retain collection-scoped ID maps. The private environment
file is authoritative for browser credentials; no encryption format or
archival-path migration is performed. All local writes stay under DART
managed storage. Sources are read-only and never automatically retired.
Desktop operation is refused on these new marked roots to avoid bypassing the
managed writer protocol; ordinary desktop projects and existing CLIs remain.

Completed writes use atomic replacement. Job success is recorded only after
the workflow returns successfully. A lost state store cannot reliably record
a terminal state; the service explicitly blocks further submissions and
restart converts the last persisted active state to interrupted. Cancellation
after a final atomic commit may correctly yield success rather than claiming
that the committed write was cancelled.

## Compound Object Filename Indexing

### The Problem
In DART's workflow, original filenames serve as the "source of truth" for indexing digital objects. However, compound objects (parents that group related files) don't have actual files associated with them - they're logical containers. This created a challenge:
- Individual files have filenames: `photo_001.jpg`, `photo_002.jpg`
- Compound parents had no filename: just an objectid like `dg_1715614220`
- This required a 2-pronged indexing approach with fallback logic

### The Solution: Underscore-Prefixed First Child Filename

**Decision**: Use the first child's filename as the compound parent's index, prepended with an underscore.

**Implementation**:
1. When creating a compound object, capture the first child's filename
2. Store `_<first_child_filename>` in the compound parent's `filename` column in CSV exports
3. The first child retains its original filename (no underscore)
4. This differentiates the parent index from the actual child file

**Example**:
```csv
objectid,filename,parentid,display_template
dg_1715614220,_photo_001.jpg,,compound_object     ← Compound parent (underscore prefix)
dg_1715614221,photo_001.jpg,dg_1715614220,image  ← First child (original filename)
dg_1715614222,photo_002.jpg,dg_1715614220,image  ← Second child
```

### Benefits

1. **Unified Indexing**: ALL objects now have a filename as their source of truth
   - No need for fallback logic using objectid
   - Consistent approach across the entire system

2. **Clear Differentiation**: The underscore prefix makes it visually obvious
   - `_photo_001.jpg` = compound parent (no actual file)
   - `photo_001.jpg` = first child file (actual file exists)

3. **Deterministic Ordering**: First child is always the "index child"
   - Sorted by sequence number (numbered files first)
   - Then alphabetically for unnumbered files
   - Consistent across re-runs

4. **Maintains Relationships**: Parent-child connections remain clear
   - Filename shows which group a compound represents
   - Easy to trace compound back to its first member

### Implementation Details

**In `analyze_compound_objects()` function**:
- Sort children to find the consistent "first" child
- Extract first child's filename and store in compound object
- This happens during compound creation (Function 1 and Function 2)

**In CSV Export (Function 2)**:
- Write compound parent's filename as `_<first_child_filename>`
- Maintains all other compound parent fields (objectid, display_template, etc.)
- First child and all other children write their original filenames
- Compound parents do NOT receive `object_location` values (no physical file)

**In Derivative Generation (Function 3)**:
- Skip compound parents during derivative generation (no physical file to process)
- After all children are processed, populate compound parent derivatives:
  - Remove underscore from compound parent filename
  - Find matching child row by filename
  - Copy `image_small` and `image_thumb` URLs from child to parent
- This avoids duplicate uploads - derivatives already exist in Azure for first child
- Compound parents reference the same derivative URLs as their first child
- Log messages show which compound parents received derivative URLs

### Technical Rationale

This approach eliminates complexity while maintaining data integrity:
- **Before**: If `filename` is blank, fall back to `objectid` for indexing
- **After**: Always use `filename` - underscore prefix indicates special case
- Simpler code, fewer conditionals, more maintainable
- Works seamlessly with existing CollectionBuilder compatibility

### Date Implemented
May 15, 2026

### Related Files
- `app.py` - Core implementation
- `FUNCTION_1_ANALYZE_ASSETS.md` - User-facing documentation
- `FUNCTION_2_EXPORT_CSV.md` - CSV export documentation
- `FUNCTION_3_GENERATE_DERIVATIVES.md` - Derivative processing
