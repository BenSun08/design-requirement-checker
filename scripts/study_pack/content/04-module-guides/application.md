# application.py — use cases and honest outcomes

## Purpose and dependencies

Coordinate domain values, adapter, matcher and store without `QWidget` logic.
The module uses frozen dataclasses for outcomes, `Enum` for run lifecycle and
`Path` for explicit file boundaries. UI workers can call it without knowing
OOXML or matching internals.

## Important types and functions

`ImportFailure` makes an unreadable input explicit. `VerificationOutcome`
contains document identity, coverage, lifecycle and results.
`BaselineValidationIssue` / `BaselineValidationResult` separate errors from
warnings. `BaselineLoadResult` carries items, identity, provenance and failure.
Entry points are `import_document`, `verify_document`, `validate_baseline`,
`load_baseline_from` and `save_baseline_to`.

## Inputs, outputs and data flow

Import takes a path and returns Document or ImportFailure. Verification accepts
a document and items, removes disabled items and returns a completed or cancelled
outcome. The matcher exception becomes CANCELLED with an empty result tuple.
Unexpected exceptions are not swallowed here; workers translate them to failure
signals at the background-operation boundary.

Baseline validation rejects duplicate codes and warns about duplicate names,
normalized phrase collisions and overlaps. Save validates then persists.
Load distinguishes unsupported schema from general failure, returning explicit
source tokens for UI mapping.

## Important invariants and design reasons

Cancelled/failed outcomes cannot carry results. Failure is never translated into
an empty successful document or an all-MISSING report. UI publication belongs
after successful persistence, so a disk failure cannot install unsaved inputs.
Warning order is stable, making validation reproducible.

## Failure modes

Do not parse human-readable error strings to decide startup state. Do not treat
warning-only validation as an error. The save docstring's broad claim about
unchanged primary/backup on failure is stronger than the actual phased store:
backup can already contain the old valid primary if final installation fails.
The [persistence flow](../03-runtime-flows/baseline-persistence.html) describes
that distinction without changing the application.

References: [[src/design_requirement_checker/application.py::VerificationOutcome]],
[[src/design_requirement_checker/application.py::save_baseline_to]], [[tests/test_application.py]].
Next: [store](baseline-store.html).
