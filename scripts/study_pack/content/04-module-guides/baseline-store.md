# baseline_store.py — recoverable local persistence

## Purpose and dependencies

Own the one local UTF-8 JSON baseline and its `.bak` backup. Standard-library
`json`, `tempfile`, `shutil`, `os` and `Path` implement persistence. A lazy
`QStandardPaths` lookup in `default_path` is the documented Qt exception.
No generic repository abstraction is needed for this single concrete boundary.

## Important types and functions

`BaselineLoadSource` records primary, backup or no-baseline. The separate
`UnsupportedBaselineSchemaError` prevents compatibility failures from being
mistaken for corruption. `serialize_baseline` / `deserialize_baseline` convert
values. `save_baseline` / `load_baseline` own disk policy. `_phase_replace`
labels backup and primary replacement for precise failure injection.

## Inputs, outputs and data flow

Save consumes a path, item sequence and baseline ID, then either returns normally
or raises. Load returns items, baseline ID and source. Both files absent is
ordinary first use; corrupt/missing primary with valid backup is recovery.
An unsupported schema propagates immediately rather than silently using backup.
Load never repairs or overwrites files implicitly.

## Important invariants and design reasons

Stable IDs are stored verbatim, not derived from names/codes. Same-directory
temporary files allow atomic replacement. `flush` moves buffered text to the OS;
`fsync` requests persistence of file contents. Backup is a **copy** of valid old
primary, installed before new primary. The primary stays present through the
entire preparation phase. This is not a universal guarantee against every
filesystem/power-loss scenario: directory metadata is not separately fsynced.

## Failure modes

Permission, write, fsync and replace failures are explicit. Corrupt primary must
not overwrite a good backup; unsupported schema aborts save. Primary replacement
failure leaves old primary available even if backup has already been refreshed.
Storage validation and business validation differ: duplicate codes are handled
by application validation. Read actual field checks rather than assuming an
exhaustive schema validator from the word “strict.”

References: [[src/design_requirement_checker/baseline_store.py::save_baseline]],
[[src/design_requirement_checker/baseline_store.py::load_baseline]], [[tests/test_baseline_store.py]].
Next: [checklist UI](ui-components.html).
