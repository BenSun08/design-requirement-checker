# Design Requirement Checker — Tasks

The actionable execution and backlog document. It does not define product
semantics ([spec.md](spec.md)), engineering invariants
([constitution.md](constitution.md)) or technical decisions
([plan.md](plan.md)).

## Status legend

```text
[x]  implemented and merged to main
[ ]  open / not started
DEFERRED  intentionally postponed by the owner for the v0.1 milestone
BLOCKED   cannot proceed without external input (evidence, decision, access)
AUTHORIZED  requires explicit owner authorization before starting
```

## Completed work

```text
[x] S1/S2 DOCX fidelity, locations and coverage spikes
[x] S6 deterministic rules and scale spike
[x] Baseline persistence validation spike (atomic-save contract corrected)
[x] Task 2 — real DOCX ingestion (+ ingestion/coverage remediation)
[x] Task 3 — deterministic verification engine (+ cancellation-checkpoint remediation)
[x] Task 4 — Qt review workspace (background import/verify, cancel, stale suppression,
           summary, ordering, filters, search, multi-evidence, source context, LIMITED notice)
[x] Task 5 — baseline management and persistence (checklist/editor dialogs,
           atomic JSON store, backup recovery, startup conditions, invalidation)
[x] Task 6 — evaluation tooling only (validation/ schema, harness, metrics, report, CLI)
[x] v0.1 demo documentation closeout
[x] Cross-platform CI (macOS + Windows, Python 3.13) and Windows onedir build workflow
[x] Documentation consolidation into constitution / spec / plan / tasks
```

Detailed subtask history and commit SHAs live in Git, not here.

## Deferred validation (DEFERRED by owner for the v0.1 internal-demo milestone)

These remain prerequisites before any production/pilot readiness claim. Do
not start them without explicit owner authorization.

**Task 6 — historical measurement (BLOCKED on evidence, not code):**

```text
[ ] obtain a real/sanitized independently labelled historical corpus
[ ] execute Task 6 real measurements (precision/recall, strike accuracy,
    comparison accuracy, unresolved rate, coverage/unsupported rate,
    review-time change — all with denominators)
[ ] classify historical discrepancies (extraction / matching / normalization /
    configuration / policy / unsupported-scope)
[ ] fix agreed high-impact failures with regression tests
[ ] agree production release thresholds with the owner
```

**Task 7 — Windows deployment validation (AUTHORIZED-gated):**

```text
[ ] clean Windows 10 x64 deployment, standard user, no admin
[ ] clean Windows 11 x64 deployment, standard user, no admin
[ ] standard-user / no-admin matrix
[ ] fully offline clean-machine test (no cached prerequisites)
[ ] company Python 3.8 present / unchanged coexistence test
[ ] Python absent machine test
[ ] enterprise endpoint-protection / execution-policy behavior recorded
[ ] application replacement / upgrade preserves baseline data
[ ] formal error-log location validation
```

**Existing manual-validation gaps (DEFERRED):**

```text
[ ] Windows DPI scaling matrix
[ ] Chinese-input (IME) validation matrix
[ ] long-description layout validation at target window sizes
[ ] target-desktop screenshots inspection
```

## V0.2 backlog (CANDIDATE — unscheduled, not committed)

Feature definitions and constraints: [spec.md §14](spec.md). Phasing:
[plan.md §8](plan.md). No dates are assigned; each item requires an explicit
product decision before scheduling.

```text
[ ] result / report export
[ ] enhanced textual diff display
[ ] drag-and-drop DOCX import
[ ] fuzzy candidate matching for human review (labelled similarity only)
[ ] optional manual confirmation / review workflow on UNRESOLVED items
[ ] improved internal document preview
[ ] multiple baselines / customer or order templates
[ ] baseline version / history support
```

## Future backlog (EXPLORATORY — NOT COMMITTED)

Requires an explicit owner product decision **and** authorization before any
planning or implementation:

```text
[ ] semantic / LLM fallback matching
[ ] RAG over requirement corpora
[ ] generated corrections / suggested wording
[ ] DOCX editing or rewriting (violates current source-immutability principle)
[ ] Word integration / automation
[ ] reviewer comments and multi-user team synchronization
[ ] cloud / shared baseline infrastructure
[ ] rule-version management workflows
```

## Maintenance tasks (default agent work for the v0.1 milestone)

```text
[ ] bug fixes (reproduce with a focused regression test first)
[ ] small demo usability fixes
[ ] documentation maintenance (keep the four canonical docs consistent)
[ ] keep CI green on macOS + Windows, Python 3.13
```

## Definition of ready

A work item is ready when:

1. its product semantics exist in `spec.md` (new features) or the defect is
   reproduced with a failing focused test;
2. its engineering constraints are checked against `constitution.md`;
3. its prerequisite evidence or owner authorization exists (especially for
   deferred/backlog sections);
4. it is bounded enough for one focused branch with reviewable subtasks.

## Definition of done

A task is done when:

1. focused tests pass with independently written expected outcomes;
2. the full quality gates pass: `python -m pytest -q`, `ruff check .`,
   `ruff format --check .`, `mypy src`, `pip check`, `git diff --check`;
3. CI is green on macOS and Windows (Python 3.13);
4. the diff has been reviewed against the actual implementation, not only
   commit messages or green CI;
5. documentation matches observed behavior — no unverified PASS claims;
6. the branch/PR is **not** auto-merged; merge requires its own authorization.
