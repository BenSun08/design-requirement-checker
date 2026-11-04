# matching.py — deterministic evidence, not acceptance

## Purpose and dependencies

A pure engine using `re`, frozen dataclasses, collections/typing abstractions
and domain values. It imports no Qt, filesystem or Word libraries. This makes
rules reproducible with synthetic values and independently labelled tests.

## Important types and functions

`NormalizedText` pairs normalized characters with raw source spans. `normalize`
applies N1–N3; `map_span` maps a normalized match back to raw offsets.
`_Candidate` represents a phrase hit; `_Occurrence` adds association, strike and
comparison inputs. `verify` coordinates `_collect_candidates`,
`_associate_candidates` and `_classify`.

## Inputs, outputs and data flow

Input: immutable `Document`, item sequence and optional cancellation callback.
Output: a tuple of `CheckResult` in input-item order, or
`VerificationCancelled`. The application excludes disabled items before this
call; the engine itself iterates the supplied sequence.

Each block is normalized once. Each item searches its detection phrase and
aliases. Duplicate detection methods at the same item/span retain the best
method (exact → normalized → alias), while separate occurrences remain.
After collection, cross-item overlap and forward requirement spans are assessed.
Classification then retains every occurrence as evidence.

## Important invariants and design reasons

Spaces/tabs/ideographic spaces and in-block breaks collapse; only selected
full-width punctuation maps. Case, units, digits, negation and operators remain
meaningful. A requirement span stops at a boundary, next match or block end.
Strike is evaluated over that span, not the paragraph. Comparison against the
expected description is independent of presence status.

## Failure modes and limits

A value after a comma may fall outside the span and make comparison unsafe.
Partial/unknown strike, active-plus-struck evidence and conflicting active
parameter sets require review. Ambiguous evidence is retained; clean evidence
elsewhere can still resolve an item, as `_classify` and its tests demonstrate.
Cancellation is checked immediately before each item/block search, and never
returns a partial completed result set. There is no fuzzy or semantic fallback.

References: [[src/design_requirement_checker/matching.py::verify]],
[[src/design_requirement_checker/matching.py::_classify]], [[tests/test_matching.py]].
Next: [DOCX adapter](docx-adapter.html) and [matching tutorial](../05-concepts/deterministic-matching.html).
