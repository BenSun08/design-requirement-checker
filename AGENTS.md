# AGENTS.md

## Purpose

This repository implements a local desktop **Design Requirement Checker** for engineering `.docx` documents.

Coding agents must preserve:

1. **Traceability** — every result must be explainable from source evidence.
2. **Determinism** — identical inputs and rule revision must produce identical outputs.
3. **Explicit uncertainty** — unsupported, ambiguous, conflicting, or partially known cases must never be silently converted into confident results.

Do not add AI, fuzzy matching, hidden heuristics, services, or generic frameworks unless a future task explicitly authorizes them.

---

## 1. Read Before Coding

Before implementing any task, read:

```text
docs/product-spec.md
docs/domain-model.md
docs/ux-spec.md
docs/implementation-plan.md
docs/delivery-roadmap.md
docs/technical-spikes.md
```

Use the English documents as implementation authority. Keep `docs-zh/` mirrors synchronized when relevant.

The browser prototype under `prototype/` is a UX reference only. It is not production behavior.

---

## 2. Architecture

Keep the architecture small:

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

Main production modules:

```text
src/design_requirement_checker/domain.py
src/design_requirement_checker/matching.py
src/design_requirement_checker/application.py
src/design_requirement_checker/docx_adapter.py
src/design_requirement_checker/baseline_store.py
src/design_requirement_checker/ui/main_window.py
src/design_requirement_checker/ui/workers.py
src/design_requirement_checker/__main__.py
```

Task 5 may add:

```text
src/design_requirement_checker/ui/checklist_dialog.py
```

Do not add a generic repository layer, DI framework, plugin system, internal service bus, or protocol framework without a concrete requirement.

---

## 3. Dependency Rules

### `domain.py`

Must not import:

```text
PySide6
python-docx
lxml
filesystem adapters
database/storage implementations
```

It owns immutable value models, enums, invariants, and stable result concepts.

Prefer:

```python
@dataclass(frozen=True)
```

Use `__post_init__` to reject invalid state immediately.

### `matching.py`

Must remain free of:

```text
Qt
python-docx
filesystem I/O
network I/O
persistent storage
```

Inputs:

```text
Document
Sequence[CheckItem]
optional cancellation callback
```

Outputs:

```text
CheckResult values
```

Do not move presentation logic into matching.

### `docx_adapter.py`

This is the only production module that should know about:

```text
python-docx
OOXML
lxml
Word package internals
```

Library objects must not escape this adapter.

Never modify the source `.docx`.

### `application.py`

Coordinates use cases:

```text
import document
verify document
load/save baseline
invalidate stale results
translate adapter/storage failures into application outcomes
```

Do not put QWidget logic here.

### `ui/`

Owns widgets, labels, filters/search, worker lifecycle, user interaction, and UI-only localization.

Do not redefine domain semantics in the UI.

### `__main__.py`

Composition root only:

```text
create QApplication
compose dependencies
create MainWindow
show it
start app.exec()
```

---

## 4. Domain Semantics That Must Not Drift

### Status vs resolution

`CheckStatus` has exactly:

```text
CONFIGURED
MISSING
STRUCK_OUT
```

`UNRESOLVED` is not a fourth status.

Instead:

```text
Resolution.RESOLVED
Resolution.UNRESOLVED
```

Invariant:

```text
RESOLVED   → status is set
UNRESOLVED → status is None
```

Do not add `CheckStatus.UNRESOLVED`.

### Description comparison is independent

Comparison states:

```text
SAME
DIFFERENT
NOT_COMPARED
```

A result may validly be:

```text
CONFIGURED + DIFFERENT
```

Do not convert a description difference into MISSING or UNRESOLVED unless another rule independently requires it.

### MISSING meaning

`MISSING` means no qualifying evidence was found in the supported checked scope.

It does not prove physical absence of the function.

Use scoped UI wording such as:

```text
在已检查范围内未找到匹配证据
```

Never fabricate evidence or source location for MISSING.

### Evidence retention

Keep all qualifying occurrences.

Do not silently discard contradictions.

`primary_evidence_id` is only an initial UI selection aid, not evidence priority.

---

## 5. Matching Contract

Do not change Task 3 matching policy casually.

If behavior appears wrong:

1. reproduce it with a focused regression test;
2. compare against `docs/domain-model.md` and `docs/technical-spikes.md`;
3. report the policy conflict;
4. do not silently redefine semantics in a later task.

### Normalization allowlist

Approved:

```text
N1: ASCII space / tab / U+3000 runs → one ASCII space
N2: line-break characters inside one block → one ASCII space
N3: selected full-width punctuation → ASCII equivalent
```

Rejected:

```text
ideographic full stop → ASCII full stop
full-width digits/letters → ASCII
case folding
NFKC
numeric/unit equivalence
negation/operator folding
general punctuation stripping
```

Engineering meaning must remain distinct:

```text
2s != 3s
24V != 12V
开启 != 不开启
允许 != 禁止
> != <
CAN != can
```

### Source mapping

Normalized matching must retain raw source traceability.

Offsets use half-open ranges:

```text
[start, end)
```

Never replace stored raw text with normalized text.

### Requirement spans

Associate forward from the matched detection phrase only.

Do not join across paragraph or table-cell boundaries.

Unsafe association must remain explicit:

```text
requirement-span-association-uncertain
no-associated-requirement-content
```

### Strike coverage

Possible values:

```text
NONE
FULL
PARTIAL
UNKNOWN
```

Core classification:

```text
consistent active evidence
→ RESOLVED / CONFIGURED

all qualifying evidence fully struck
→ RESOLVED / STRUCK_OUT

no qualifying evidence
→ RESOLVED / MISSING

partial strike
unknown strike
active + struck coexistence
conflicting active key values
ambiguous function identity
→ UNRESOLVED / status=None
```

### Cancellation

Cancellation is cooperative.

The checkpoint belongs immediately before each `(CheckItem, DocumentBlock)` candidate-search unit.

A cancelled run must never return a misleading partial completed result set.

---

## 6. DOCX / OOXML Rules

Selected ingestion stack:

```text
python-docx 1.2.0
+
focused OOXML/lxml access
```

Do not replace it without explicit authorization and new evidence.

### Effective strike

Resolve through:

```text
run direct formatting
→ character style chain
→ paragraph style chain
→ default paragraph style
→ docDefaults
→ default off
```

Do not assume the default paragraph style is named `Normal`; use the style marked `w:default="1"`.

### Unknown formatting

Unknown must remain unknown.

Examples:

```text
invalid strike value
orphan style reference
broken style chain
style cycle
unresolved double-strike semantics
```

Never silently map unknown strike to `False`.

### Hyperlinks

Do not regress to `paragraph.runs` only. Preserve hyperlink-contained runs in document order.

### Unsupported structures

Known unsupported structures must force `Coverage.LIMITED` rather than disappear silently.

Examples:

```text
tracked revisions
text boxes
content controls
field-code structures
footnote/endnote references
smart tags
altChunk
nested/invalid hyperlink structures
excluded header/footer content
```

Coverage is not a CheckStatus.

### Tables

Do not concatenate separate cell paragraphs.

Merged cells should be represented once at the master location.

Nested tables must preserve source coordinates/ancestor paths.

---

## 7. Qt Threading Rules

The GUI thread owns all `QWidget` mutations.

Do not update widgets from worker threads.

Current pattern:

```text
QObject worker
→ moved to QThread
→ worker emits Signal
→ GUI-thread handler updates widgets
```

### Worker rules

Workers should:

- call application-layer use cases;
- return domain/application values;
- emit one terminal success/failure signal;
- never touch widgets.

Expected `ImportFailure` values are normal outcomes, not worker crashes.

### Cooperative cancellation

Verification uses:

```python
threading.Event
```

The UI sets it and matching polls `cancel_event.is_set`.

Do not use `QThread.terminate()` for normal cancellation.

### Stale-operation protection

Async operations carry a monotonic generation token.

Before applying an outcome:

```text
generation == current generation
```

Verification outcomes must also belong to the current document snapshot.

Late stale results must be ignored.

### Thread ownership

Keep strong references to all running `QThread` objects.

Never destroy a running QThread.

Do not identify a finishing thread through a mutable global/current thread pointer.

### Window close

If workers are running:

```text
request cancellation where available
request thread event-loop quit
ignore close while any owned QThread is running
retain strong ownership
```

When the last worker actually finishes, retry close asynchronously, e.g.:

```python
QTimer.singleShot(0, self.close)
```

Do not spin `processEvents()` inside `closeEvent()`.

Do not block the UI thread indefinitely with `thread.wait()`.

---

## 8. UI State Rules

Current lifecycle:

```text
EMPTY
IMPORTING
READY
VERIFYING
COMPLETED
CANCELLED
FAILED
```

Action enablement should derive from state.

Examples:

```text
no document
→ Run disabled

document + no CheckItems
→ Run disabled

READY + CheckItems
→ Run enabled

VERIFYING
→ Run disabled
→ Cancel enabled
```

Do not expose an enabled Cancel control for an operation that cannot actually be cancelled.

---

## 9. Result Presentation

Summary invariant:

```text
total =
configured +
missing +
struck_out +
unresolved
```

Description-difference count is orthogonal.

Default ordering:

```text
1. UNRESOLVED
2. MISSING
3. STRUCK_OUT
4. CONFIGURED + DIFFERENT
5. remaining CONFIGURED
```

Preserve baseline order within each group.

`仅异常` includes:

```text
MISSING
STRUCK_OUT
UNRESOLVED
CONFIGURED + DIFFERENT
```

Filters/search must not recompute verification.

Use human-facing Chinese labels in UI while preserving stable domain tokens.

Do not invent:

```text
confidence %
通过
PASS
```

---

## 10. Baseline Persistence Contract

Task 5 must implement the validated persistence contract before checklist editing depends on it.

Selected format:

```text
UTF-8 JSON
schemaVersion = 1
one baseline
stable item_id
stable alias_id
```

Expected path:

```text
QStandardPaths.AppDataLocation / baseline.json
```

Backup:

```text
baseline.json.bak
```

Do not store user baseline data beside the executable.

### Atomic save

Use the validated two-temp-file, copy-not-move algorithm:

```text
1. create parent directory
2. create temp-new in same directory
3. write UTF-8 JSON
4. flush + fsync temp-new

5. if primary exists:
   a. create temp-backup
   b. copy primary → temp-backup
   c. flush + fsync temp-backup
   d. atomic replace temp-backup → baseline.json.bak

6. atomic replace temp-new → baseline.json
```

Critical invariant:

> Never move the existing primary away before the new primary is successfully installed.

Do not revert to:

```text
primary → .bak
temp → primary
```

because final replace failure can leave the primary path absent.

### Recovery

Expected behavior:

```text
primary valid
→ load primary

primary missing/invalid + backup valid
→ expose backup with source="backup"

both invalid/missing
→ explicit failure

unsupported schema
→ explicit failure
```

Do not silently overwrite corrupt primary data during load.

### Strict validation

Persist and validate:

```text
item_id
code
name
detection_phrase
category
expected_description
enabled
notes

alias_id
text
notes
```

Do not silently coerce malformed JSON.

Stable IDs must survive restart and edits.

Do not derive identity from code/name/detection phrase.

---

## 11. Task 5 Cross-Item Validation

Keep storage validation separate from business validation.

Planned policy:

```text
duplicate code
→ reject

duplicate name
→ flag/warn

overlapping detection phrases
→ flag/warn
```

Empty `expected_description` is allowed.

Disabled items are persisted but excluded from verification.

Delete must be explicitly confirmed.

---

## 12. Result Invalidation

Any input change that changes result meaning must invalidate existing results.

Examples:

```text
new document imported
baseline changed
CheckItem edited
CheckItem enabled/disabled
CheckItem deleted
new verification started
```

A stale background completion must not restore invalidated results.

---

## 13. Testing Rules

Prefer independent expected outcomes.

Do not derive test expectations by calling the production function being tested.

Main test suites:

```text
tests/test_domain.py
tests/test_docx_adapter.py
tests/test_matching.py
tests/test_application.py
tests/test_ui.py
tests/test_startup.py
```

Spike/evidence suites:

```text
tests/test_spike_s1_oxml_fidelity.py
tests/test_spike_s2_locations_coverage.py
tests/test_spike_s6_rules.py
tests/test_spike_s6_scale.py
```

Task 5 should add:

```text
tests/test_baseline_store.py
```

Use `tests/fixture_factory.py` for deterministic synthetic DOCX cases.

When python-docx cannot construct a case via public APIs, a small documented OOXML patch is acceptable.

For race/thread tests, avoid arbitrary sleeps when possible. Prefer:

```text
threading.Event
controlled callbacks
explicit Qt event processing
deterministic fakes
```

Test lifecycle state, not merely absence of warnings.

---

## 14. Required Quality Gates

Before finishing a task/PR:

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pip check
git diff --check
```

Run focused suites too, e.g.:

```bash
python -m pytest tests/test_baseline_store.py -q
python -m pytest tests/test_application.py -q
python -m pytest tests/test_ui.py -q
```

CI must remain green on:

```text
macos-latest / Python 3.13
windows-latest / Python 3.13
```

Green Windows CI is not proof of clean-machine/no-admin deployment.

---

## 15. Windows Packaging Rules

Target:

```text
Windows 10/11 x64
PyInstaller
onedir
console=False
```

Build Windows artifacts on Windows.

Do not claim macOS-to-Windows cross-compilation.

The target application must not depend on the company's installed Python 3.8.

Do not:

```text
upgrade company Python
modify system PATH
require target-side pip install
require online activation/download
require administrator privileges
```

Real no-admin/offline deployment is a separate validation gate.

---

## 16. Development Workflow

For each new task:

1. start from latest `main`;
2. confirm prerequisite PRs are merged;
3. confirm post-merge CI is green;
4. create one bounded task branch;
5. read the relevant docs and current code;
6. state the approach briefly;
7. divide work into small subtasks;
8. add/update tests with each subtask;
9. run focused checks;
10. review the diff;
11. make one focused commit per completed subtask;
12. continue only after the subtask is internally consistent.

Do not automatically merge the final PR.

Do not start the next numbered task before the current task is reviewed/merged unless explicitly asked to use stacked branches.

---

## 17. Commit Discipline

Prefer one commit per subtask.

Example Task 5 history:

```text
feat(task5): implement production baseline store
feat(task5): add baseline validation rules
feat(task5): add application baseline lifecycle
feat(task5): add checklist management workspace
feat(task5): add checklist item editing
feat(task5): add enable disable and delete flows
feat(task5): add baseline recovery UX
feat(task5): integrate baseline changes with verification
chore(task5): complete validation and docs
```

If no code change is required:

```text
SKIPPED — already satisfied
```

Do not create empty commits.

Do not mix unrelated cleanup into feature commits.

Do not squash during implementation unless explicitly asked.

---

## 18. Branch Discipline

Use bounded branch names:

```text
task5-baseline-management
task6-historical-validation
task7-windows-pilot
```

Avoid generic long-lived names such as:

```text
dev
misc
fixes
```

unless explicitly chosen by the owner.

---

## 19. Documentation Discipline

Update docs only with observed facts.

Do not claim:

```text
PASS
validated
complete
verified
```

for work that was not actually run.

Use:

```text
PASS
FAIL
NOT RUN
```

where appropriate.

Keep these distinctions explicit:

```text
source-level CI
≠
packaging artifact
≠
clean-machine deployment evidence
```

---

## 20. Scope Control

MVP excludes:

```text
LLM/AI classification
fuzzy matching
semantic matching
vector database
RAG
confidence scores
cloud sync
shared server
microservices
plugins
Word automation
editing customer DOCX
automatic updater
multi-baseline customer/template framework
baseline history/version system
```

Do not introduce these while implementing another task.

---

## 21. Performance / Simplicity

Expected scale:

```text
tens to low hundreds of CheckItems
hundreds to a few thousand DocumentBlocks
```

Existing deterministic matching has already been demonstrated around:

```text
3000 blocks × 100 items
```

Do not optimize prematurely with multiprocessing, databases, caches, or service processes unless measurements show a real need.

---

## 22. Security / Data Handling

The application is local/offline by design.

Do not add:

```text
telemetry
network calls
cloud storage
automatic external fetches
```

Never modify the source DOCX.

Avoid exposing full internal tracebacks directly in normal end-user UI.

---

## 23. PR Review Expectations

When reviewing whether a task/PR is ready:

Do not rely only on green CI, commit messages, or docs.

Inspect the actual implementation.

For concurrency, verify lifecycle semantics.

For persistence, inspect exact failure phases.

For matching, compare code with independently labelled tests and domain rules.

For UI, verify stale state cannot survive transitions.

Look for tests that accidentally miss the dangerous phase.

---

## 24. Final Report Format

After completing a task, report:

### Commits

```text
subtask
commit SHA
commit message
```

### Implementation

State what actually changed.

### Validation

Use:

```text
PASS
FAIL
NOT RUN
```

for relevant gates:

```text
focused tests
full pytest
ruff
format
mypy
pip check
git diff --check
macOS CI
Windows CI
manual GUI validation
Windows deployment validation
```

### Known limitations

Be explicit.

### Next slice

Recommend the next bounded slice only.

Do not implement it unless explicitly authorized.

---

## 25. Current Milestone: v0.1 Internal Demo

Tasks 2–5 are implemented on `main`:

```text
Task 2 — real DOCX ingestion
Task 3 — deterministic verification
Task 4 — Qt review workspace
Task 5 — baseline management and persistence
```

Task 6 historical measurement and Task 7 formal deployment validation are
**intentionally deferred by the owner** for this milestone. Task 6 evaluation
tooling exists under `validation/` but has produced no measured metrics (no
independently labelled corpus supplied). See `docs/demo-readiness.md`.

Future agent default work for this milestone:

```text
bug fixes
small demo usability fixes
documentation maintenance
```

Agents must NOT automatically start:

```text
Task 6 (historical measurement / corpus work)
Task 7 (formal deployment validation)
V0.2 features (export, fuzzy/semantic matching, multi-baseline, etc.)
```

without explicit owner authorization.

All architecture, domain, matching, DOCX, threading, UI, persistence and
quality rules in sections 1–24 remain unchanged.

---

## 26. Core Principle

When uncertain, preserve evidence and expose uncertainty.

```text
unknown ≠ false
unsupported ≠ complete
cancelled ≠ completed
different ≠ missing
stale ≠ current
green CI ≠ deployment validated
```
