# Persistence: protect the previous good state

## Identity and location

The one baseline is UTF-8 JSON with `schemaVersion=1`, stable baseline/item/alias
IDs and editable labels. IDs must survive renaming; deriving them from a code or
phrase would break that property. `QStandardPaths.AppDataLocation` selects
per-user writable storage rather than a file beside the packaged executable.

## Atomic save is a sequence, not a magic flag

1. Validate the candidate in the application layer.
2. Write temp-new beside the destination; flush and fsync its contents.
3. If old primary is valid, copy it into temp-backup, flush/fsync and install `.bak`.
4. Replace primary atomically with temp-new using `os.replace`.
5. Only after return, publish the new in-memory baseline and invalidate results.

Moving primary to backup before step 4 would create a window with no primary.
Copying avoids that gap. If step 4 fails, the previous primary remains available;
backup may already have been refreshed. If primary was corrupt, copying it over
a valid backup would destroy recovery, so backup preparation is skipped.

## Recovery versus incompatible data

Primary valid → use it. Primary missing/corrupt + valid backup → expose recovery
provenance without silently rewriting primary. Both absent → ordinary first use.
Neither usable → explicit failure. Unsupported schema on a consulted file is a
compatibility problem, not corruption: it stops fallback. Saving over an
unsupported primary also stops rather than downgrading data.

The implementation syncs file contents, not parent-directory metadata, and does
not claim a universal power-loss durability guarantee. Failure-injection tests
exercise exact replacement phases; actual company filesystem/endpoint behaviour
remains separate deployment evidence.

References: [[src/design_requirement_checker/baseline_store.py::_phase_replace]],
[[src/design_requirement_checker/baseline_store.py::save_baseline]],
[[src/design_requirement_checker/ui/main_window.py::MainWindow._save_baseline_snapshot]],
[[tests/test_baseline_store.py]]. Next: [testing](testing-strategy.html).
