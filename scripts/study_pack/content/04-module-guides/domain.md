# domain.py — the vocabulary and invariant boundary

## Purpose

Represent evidence, checklist inputs and results without Qt, Word library
objects, filesystem paths or storage services. Frozen dataclasses and tuples
make snapshots suitable for deterministic comparison and thread handoff.
`Enum` makes independent dimensions explicit rather than mixing UI labels into
business decisions.

## Important types and functions

- `Document`, `DocumentBlock`, `TextRun` and `DocumentLocation` describe a single
  identified input. `TableCellCoordinates` retains table position.
- `CheckItem` and `CheckItemAlias` carry stable IDs and explicit detection text.
- `MatchEvidence` retains raw text, raw half-open spans and strike coverage.
- `CheckResult` carries status, resolution, comparison, reasons and rule revision.
- Each `__post_init__` checks the invariants owned by that value type.

## Inputs, outputs and data flow

The adapter constructs document values; the store reconstructs checklist values;
the matcher consumes both and emits result values. A `TextRun`'s offsets must
span exactly the length of its text. A block checks contiguous runs and exact
concatenation. A document checks block identity and coverage/warning consistency.
No constructor performs I/O.

## Important invariants and design reasons

`effective_strike=None` requires a reason; unknown cannot become false.
`Resolution.UNRESOLVED` requires `status=None`, while RESOLVED requires a status.
`ComparisonState` is orthogonal: CONFIGURED + DIFFERENT is valid. MISSING has no
fabricated evidence. Offsets count Python Unicode code points, not UTF-8 bytes.
Frozen values prevent routine assignment, but do not magically validate every
possible semantic relation; read the actual checks in each constructor.

## Failure modes

Invalid offsets, mismatched identities and inconsistent coverage raise
`ValueError`. Confusing UNRESOLVED with a fourth status loses information.
Using mutable Word objects across a worker boundary would bypass this design.
The `CheckItem` docstring contains a historical “later slices” comment about
persistence; current application/store code implements it already.

References: [[src/design_requirement_checker/domain.py::TextRun]],
[[src/design_requirement_checker/domain.py::CheckResult]], [[tests/test_domain.py]].
Next: [matching](matching.html).
