# Design Requirement Checker Constitution

This document defines the non-negotiable engineering and product principles,
architectural boundaries, domain invariants, quality/validation rules and
scope-governance rules for this repository. It should change rarely; any
change here is a deliberate governance decision, not an implementation
convenience.

## 1. Purpose

A local desktop tool that checks engineering `.docx` documents against a
maintained checklist baseline and presents explainable, deterministic results
for human engineering review.

## 2. Source-of-truth hierarchy

```text
constitution.md   (this file — principles and invariants; changes rarely)
      ↓
spec.md           (what the product is — requirements, semantics, UX, limitations, future features)
      ↓
plan.md           (how it is built — stack, architecture decisions, milestones, roadmap)
      ↓
tasks.md          (what work exists — completed / deferred / backlog)
```

When documents conflict, the higher document wins. `AGENTS.md` and `README.md`
are entry points and must link here rather than restate this material.

## 3. Core engineering principles

Every result must be explainable from source evidence (**traceability**).
Identical inputs and rule revision must produce identical outputs
(**determinism**). Unsupported, ambiguous, conflicting or partially known
cases must never be silently converted into confident results (**explicit
uncertainty**). Human engineering judgment remains authoritative — the tool
surfaces evidence; it never accepts or rejects a design. The application is
local and offline: no telemetry, network calls, cloud storage or automatic
external fetches. The source `.docx` is immutable; the application never
modifies it.

No AI, fuzzy matching, hidden heuristics, services or generic frameworks may
be added unless a future task explicitly authorizes them.

These distinctions are permanent:

```text
unknown ≠ false
unsupported ≠ complete
cancelled ≠ completed
different ≠ missing
stale ≠ current
green CI ≠ deployment validated
```

## 4. Architectural boundaries

```text
PySide6 UI
    ↓
Application
    ↓
Domain + Matching
    ↑
DOCX Adapter

Baseline Store
    ↓
Domain
```

Module rules:

- `domain.py` — immutable value models, enums, invariants. No Qt, no
  python-docx, no lxml, no filesystem/storage imports, no network.
  Prefer `@dataclass(frozen=True)` with `__post_init__` validation.
- `matching.py` — deterministic pure engine. Inputs: `Document`,
  `Sequence[CheckItem]`, optional cancellation callback. Outputs: `CheckResult`
  values. No Qt, python-docx, filesystem I/O, network I/O, persistent
  storage, or presentation logic.
- `docx_adapter.py` — the only production module that knows python-docx,
  OOXML, lxml and Word package internals. Library objects must not escape it.
- `baseline_store.py` — owns persistence. No Qt imports (lazy path lookup is
  the only exception pattern already established).
- `application.py` — coordinates use cases (import, verify, baseline
  load/save, invalidation, failure translation). No QWidget logic.
- `ui/` — widgets, labels, filters/search, worker lifecycle, UI-only
  localization. Must not redefine domain semantics.
- `__main__.py` — composition root only.

Do not add a generic repository layer, DI framework, plugin system, internal
service bus or protocol framework without a concrete requirement.

## 5. Domain invariants

`CheckStatus` has exactly three values:

```text
CONFIGURED | MISSING | STRUCK_OUT
```

`UNRESOLVED` is **not** a fourth status. It is a separate dimension:

```text
Resolution.RESOLVED   → status is set
Resolution.UNRESOLVED → status is None
```

Description comparison is an independent, orthogonal dimension:

```text
ComparisonState: SAME | DIFFERENT | NOT_COMPARED
```

`CONFIGURED + DIFFERENT` is a valid result; never convert a description
difference into MISSING or UNRESOLVED unless another rule independently
requires it.

`MISSING` means no qualifying evidence was found in the supported checked
scope; it does not prove physical absence of the function. Never fabricate
evidence or source location for MISSING.

Keep **all** qualifying evidence occurrences. Do not silently discard
contradictions. `primary_evidence_id` is only an initial UI selection aid, not
evidence priority.

Do not invent confidence percentages or "PASS/通过" semantics in results.

## 6. DOCX / OOXML principles

The selected ingestion stack is python-docx 1.2.0 plus focused OOXML/lxml
access; do not replace it without explicit authorization and new evidence.

- Effective strike resolves through: run direct formatting → character style
  chain → paragraph style chain → default paragraph style (the style marked
  `w:default="1"`, not an assumed name) → docDefaults → default off.
- Unknown formatting must remain unknown (invalid strike value, orphan style
  reference, broken chain, cycle, unresolved double-strike). Never silently
  map unknown strike to `False`.
- Preserve hyperlink-contained runs in document order; do not regress to
  `paragraph.runs` only.
- Known unsupported structures (tracked revisions, text boxes, content
  controls, field codes, footnote/endnote references, smart tags, `altChunk`,
  nested/invalid hyperlinks, excluded header/footer content) must force
  `Coverage.LIMITED`, never disappear silently. Coverage is not a
  CheckStatus.
- Tables: do not concatenate separate cell paragraphs; merged cells appear
  once at the master location; nested tables preserve ancestor coordinates.
- Never modify the source document.

## 7. Deterministic matching principles

The approved normalization allowlist is conservative and fixed:

```text
N1: ASCII space / tab / U+3000 runs → one ASCII space
N2: line-break characters inside one block → one ASCII space
N3: selected full-width punctuation → ASCII equivalent
```

Rejected (must remain rejected unless a future decision revisits them):
ideographic full stop → ASCII, full-width digits/letters → ASCII, case
folding, NFKC, numeric/unit equivalence, negation/operator folding, general
punctuation stripping. Engineering meaning must stay distinct:
`2s != 3s`, `24V != 12V`, `开启 != 不开启`, `允许 != 禁止`, `> != <`,
`CAN != can`.

Normalized matching must retain raw-source traceability with half-open
`[start, end)` offsets; never replace stored raw text with normalized text.

Requirement spans associate forward from the matched detection phrase only;
never join across paragraph or table-cell boundaries. Unsafe association
stays explicit (`requirement-span-association-uncertain`,
`no-associated-requirement-content`).

Strike coverage is `NONE | FULL | PARTIAL | UNKNOWN` evaluated over the
associated requirement span. Classification:

```text
consistent active evidence            → RESOLVED / CONFIGURED
all qualifying evidence fully struck  → RESOLVED / STRUCK_OUT
no qualifying evidence                → RESOLVED / MISSING
partial strike / unknown strike / active+struck coexistence /
conflicting active key values / ambiguous function identity
                                      → UNRESOLVED / status=None
```

No fuzzy matching and no semantic matching in v0.1.

Cancellation is cooperative: the checkpoint belongs immediately before each
`(CheckItem, DocumentBlock)` candidate-search unit. A cancelled run must never
return a misleading partial completed result set.

## 8. UI and concurrency principles

The GUI thread owns all `QWidget` mutations; workers never touch widgets.
Pattern: `QObject` worker moved to a `QThread`, results handed back via
Signals. Verification cancellation uses `threading.Event` polled by matching;
never `QThread.terminate()` for normal cancellation.

Async operations carry a monotonic generation token; a result is applied only
if its generation still matches and it belongs to the current document
snapshot. Late stale results must be ignored. Keep strong references to all
running `QThread` objects; never destroy a running thread.

On window close with workers running: request cancellation, request event-loop
quit, ignore the close while any owned `QThread` is running, and retry the
close via `QTimer.singleShot(0, self.close)` when the last worker finishes.
No `processEvents()` spin loops in `closeEvent()`, no indefinite
`thread.wait()` on the UI thread.

UI lifecycle states: `EMPTY / IMPORTING / READY / VERIFYING / COMPLETED /
CANCELLED / FAILED`. Action enablement derives from state; never expose an
enabled Cancel for an operation that cannot be cancelled.

Result presentation invariants: `total = configured + missing + struck_out +
unresolved`; description-difference count is orthogonal. Default ordering:
UNRESOLVED → MISSING → STRUCK_OUT → CONFIGURED+DIFFERENT → remaining
CONFIGURED, preserving baseline order within groups. `仅异常` includes
MISSING, STRUCK_OUT, UNRESOLVED and CONFIGURED+DIFFERENT. Filters/search
must not recompute verification. UI uses human-facing Chinese labels while
domain tokens stay stable.

Any input change that changes result meaning (new document, baseline change,
item edit/enable/disable/delete, new run) must invalidate existing results; a
stale background completion must not restore them.

## 9. Persistence principles

One local baseline, UTF-8 JSON, `schemaVersion = 1`, stable `item_id` /
`alias_id` / baseline identity (identity is never derived from
code/name/detection phrase). Stored at
`QStandardPaths.AppDataLocation / baseline.json` with `baseline.json.bak`
backup; never user data beside the executable.

Atomic save uses the validated two-temp-file, copy-not-move algorithm:

```text
1. create parent directory
2. create temp-new in same directory
3. write UTF-8 JSON; flush + fsync temp-new
4. if primary exists: create temp-backup; copy primary → temp-backup;
   flush + fsync; atomic replace temp-backup → baseline.json.bak
5. atomic replace temp-new → baseline.json
```

Invariant: never move the existing primary away before the new primary is
successfully installed.

Recovery: primary valid → load it; primary missing/invalid + backup valid →
expose backup with `source="backup"`; both invalid/missing → explicit failure;
unsupported schema → explicit failure (distinct from corruption, on load
**and** save). Never silently overwrite corrupt primary data during load.

Strict validation of all persisted fields; no silent coercion of malformed
JSON. Disabled items are persisted but excluded from verification; empty
`expected_description` is allowed; duplicate code is rejected; duplicate name
and overlapping detection phrases are flagged; delete requires explicit
confirmation.

## 10. Validation and evidence discipline

Evidence categories must never be conflated:

```text
unit test          ≠ historical validation
Windows CI         ≠ clean-machine deployment
synthetic fixture  ≠ historical evidence
proposed threshold ≠ approved threshold
demo smoke check   ≠ deployment validation
```

Documentation may claim `PASS` only with actual evidence (test suite, CI run,
observed manual run); otherwise use `FAIL`, `NOT RUN`, `NOT MEASURED` or
`DEFERRED`. Ground truth for validation must be labelled independently of
checker output — never circular.

## 11. Scope-control rules

The MVP excludes: LLM/AI classification, fuzzy/semantic matching, vector
databases, RAG, confidence scores, cloud sync, shared servers, microservices,
plugins, Word automation, editing customer DOCX, automatic updaters,
multi-baseline/template frameworks and baseline history/versioning.

Future capabilities must first be recorded in `spec.md` (Future Features),
then scheduled in `plan.md` and `tasks.md`, **before** implementation. Agents
must not silently implement future features. For the current v0.1 internal
demo milestone, Task 6 historical measurement, Task 7 formal deployment
validation and any V0.2 feature require explicit owner authorization to
start.

## 12. Change-governance rules

- Changing matching policy requires: a focused regression test reproducing
  the concern, comparison against `spec.md` semantics, and an explicit policy
  decision — never a silent redefinition.
- Changing the DOCX stack, persistence contract, domain status/resolution
  model or threading model requires an explicit owner decision recorded in
  the canonical docs.
- Quality gates before any task is considered done: full `pytest`, `ruff
  check`, `ruff format --check`, `mypy src`, `pip check`, `git diff --check`;
  CI green on macOS and Windows (Python 3.13).
- Work proceeds on bounded branches with focused commits; PRs are not
  auto-merged.

## 13. Core principle

When uncertain, preserve evidence and expose uncertainty.
