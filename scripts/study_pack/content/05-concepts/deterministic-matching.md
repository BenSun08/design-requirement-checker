# Deterministic matching: preserve the path back to raw evidence

## 1. Normalize narrowly

`normalize` collapses allowed whitespace and maps selected punctuation. It does
not apply Unicode NFKC, case folding, unit conversion or semantic equivalence.
For raw `A\t\tB`, normalized `A B` maps its middle space to raw span `[1,3)`.
This is why `NormalizedText.char_sources` exists: a displayed highlight must
cover the original tabs rather than an invented one-character position.

## 2. Detect configured identity

The matcher searches `detection_phrase` and explicit aliases, not the display
name. EXACT/NORMALIZED/ALIAS records how an occurrence qualified; an alias says
which function was mentioned, not whether the expected description is satisfied.
A phrase shared across items is a configuration issue; overlapping different
phrases can make identity ambiguous.

## 3. Associate within one block

A requirement span extends forward from the phrase to the earliest delimiter,
next qualifying match or block end. Decimal punctuation inside numbers is not
a boundary. It never borrows text from a previous clause, next paragraph or
adjacent table cell. Unsafe association makes comparison NOT_COMPARED with a
reason instead of inventing a value.

## 4. Classify while retaining evidence

| Evidence condition | Result |
|---|---|
| None in checked scope | RESOLVED / MISSING, no source evidence |
| Consistent active qualifying evidence | RESOLVED / CONFIGURED |
| All clean qualifying evidence fully struck | RESOLVED / STRUCK_OUT |
| Partial/unknown strike, active+struck, conflicting active values | UNRESOLVED / status unset |
| Only ambiguous identity evidence | UNRESOLVED / status unset |

All qualifying evidence is retained. `_classify` uses non-ambiguous occurrences
for classification when they exist; ambiguous evidence elsewhere does not
necessarily prevent resolution. This nuance has a dedicated test.

Description comparison is independent: an active `延时3s` against expected
`延时2s` can be CONFIGURED + DIFFERENT. A missing item cannot prove the function
is absent outside the supported checked scope.

References: [[src/design_requirement_checker/matching.py::normalize]],
[[src/design_requirement_checker/matching.py::map_span]],
[[src/design_requirement_checker/matching.py::_associate_candidates]],
[[tests/test_matching.py]]. Next: [practice questions](../06-learning-path/exercises.html).
