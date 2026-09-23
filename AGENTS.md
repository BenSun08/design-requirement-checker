# AGENTS.md

## Purpose

Operating manual for AI coding agents working on this repository: a local
desktop **Design Requirement Checker** for engineering `.docx` documents.

This file tells you *how to work*. It deliberately does **not** restate
product requirements, domain truth tables, OOXML rules, normalization tables,
persistence contracts or the roadmap — those live in the canonical docs below.
Restating them here is how drift begins.

## 1. Read before coding

In order:

1. [docs/constitution.md](docs/constitution.md) — principles, architectural
   boundaries, domain invariants, quality and scope governance.
2. [docs/spec.md](docs/spec.md) — what the product is: requirements, domain
   semantics, UX behavior, current limitations, future features.
3. [docs/plan.md](docs/plan.md) — how it is built: stack, key decisions,
   milestones, validation evidence, roadmap.
4. [docs/tasks.md](docs/tasks.md) — what work exists: completed, deferred,
   backlog, definition of ready/done.

When documents conflict, authority is:

```text
constitution > spec > plan > tasks
```

`README.md` is a landing page, not an authority. `prototype/` is a historical
browser UX mock — a reference, never production behavior.

Documentation is English-only and canonical. Do not reintroduce translated
doc mirrors. Chinese belongs in UI labels, examples and business-domain
terminology.

## 2. Architecture boundaries (do not violate)

```text
PySide6 UI → Application → Domain + Matching ← DOCX Adapter
                                    ↑
                              Baseline Store
```

- `domain.py` — frozen value models, enums, invariants. No Qt, no
  python-docx, no lxml, no filesystem, no storage, no network.
- `matching.py` — pure deterministic engine. No Qt, no I/O, no presentation
  logic.
- `docx_adapter.py` — the **only** module that may know python-docx, OOXML,
  lxml and Word package internals. Library objects must not escape it.
- `baseline_store.py` — the **only** persistence boundary.
- `application.py` — use-case orchestration and failure translation. No
  QWidget logic.
- `ui/` — widgets, labels, filters/search, worker lifecycle, UI-only
  localization. Never redefine domain semantics here.
- `__main__.py` — composition root only.

Do not add a generic repository layer, DI framework, plugin system, internal
service bus, protocol framework, services or sidecars without a concrete
requirement and an owner decision.

## 3. Domain invariants (concise "do not violate" list)

- `CheckStatus` is exactly `CONFIGURED | MISSING | STRUCK_OUT`. `UNRESOLVED`
  is a `Resolution` value, **not** a fourth status.
  `RESOLVED → status set; UNRESOLVED → status is None`.
- Description comparison (`SAME | DIFFERENT | NOT_COMPARED`) is independent
  and orthogonal. `CONFIGURED + DIFFERENT` is valid; never downgrade a
  difference to MISSING/UNRESOLVED without an independent rule requiring it.
- `MISSING` means "no qualifying evidence in the checked scope", never proof
  of absence. Never fabricate evidence or a source location for MISSING.
- Retain **all** qualifying evidence. Never discard contradictions.
  `primary_evidence_id` is a UI selection aid, not authority.
- No confidence percentages, no PASS/通过 semantics.
- Unknown formatting stays unknown (`unknown ≠ false`). Unsupported detected
  structures force `Coverage.LIMITED`; they never vanish silently. Coverage is
  not a CheckStatus.
- Never modify the source `.docx`.

Full semantics: [docs/constitution.md §5–§7](docs/constitution.md).

## 4. Matching policy changes

Do not change matching policy casually. If behavior looks wrong:

1. reproduce it with a focused regression test;
2. compare against `docs/spec.md` §5–§6 and `docs/plan.md` §4;
3. report the policy conflict to the owner;
4. never silently redefine semantics.

The normalization allowlist, raw↔normalized offset mapping, forward-only
requirement-span rule, strike-coverage classification and cooperative
cancellation checkpoint are contract, not preference. Details:
[docs/constitution.md §7](docs/constitution.md).

## 5. Qt / threading rules

- The GUI thread owns all `QWidget` mutations. Workers emit Signals; they
  never touch widgets.
- Cooperative cancellation via `threading.Event`. Never
  `QThread.terminate()` for normal cancellation.
- Async operations carry a monotonic generation token; ignore stale results;
  verification outcomes must also belong to the current document snapshot.
- Keep strong references to running `QThread`s; never destroy one that is
  still running; never identify the current operation through a mutable
  global thread pointer.
- On close with workers running: request cancellation, request loop quit,
  ignore the close while any owned thread runs, retry via
  `QTimer.singleShot(0, self.close)`. No `processEvents()` spin in
  `closeEvent()`, no blocking `thread.wait()` on the UI thread.
- Action enablement derives from UI state; never expose an enabled Cancel for
  an operation that cannot be cancelled.
- Any input change that alters result meaning invalidates existing results;
  a stale background completion must not restore them.

## 6. Persistence rules

One local baseline; UTF-8 JSON; `schemaVersion = 1`; stable
baseline/item/alias IDs (never derived from code/name/phrase);
`QStandardPaths.AppDataLocation / baseline.json` with `.bak` backup; atomic
two-temp-file copy-not-move save (never move the primary away before the new
primary is installed); unsupported schema distinguished from corruption on
load **and** save; never silently overwrite corrupt data or coerce malformed
JSON. Full contract:
[docs/constitution.md §9](docs/constitution.md).

Storage validation stays separate from business validation (duplicate code →
reject; duplicate name / overlapping phrase → flag; empty expected
description → allowed; disabled items persisted but excluded; delete
confirmed).

## 7. Development workflow

For each new task:

1. start from latest `main`;
2. confirm prerequisite PRs are merged and post-merge CI is green;
3. create one bounded branch with a specific name (`docs-consolidation`,
   `task7-windows-pilot`, …) — avoid `dev` / `misc` / `fixes`;
4. read the relevant canonical docs and current code;
5. state the approach briefly;
6. divide the work into small subtasks;
7. add/update tests with each subtask;
8. run focused checks;
9. review the diff;
10. make one focused commit per completed subtask;
11. continue only after each subtask is internally consistent.

Commit discipline: prefer one commit per subtask; message style
`feat(<area>): …` / `fix(<area>): …` / `docs(<area>): …` / `chore(<area>): …`
with a body describing the slice. No empty commits, no unrelated cleanup
mixed into feature commits, no squashing unless explicitly asked.

Do **not** automatically merge the final PR. Do **not** start the next
numbered task before the current one is reviewed/merged unless explicitly
asked to use stacked branches.

## 8. Testing rules

Prefer independently written expected outcomes — never derive a test's
expectation by calling the function under test.

Main suites: `tests/test_domain.py`, `test_docx_adapter.py`,
`test_matching.py`, `test_application.py`, `test_ui.py`,
`test_checklist_ui.py`, `test_baseline_store.py`, `test_startup.py`.
Spike/evidence suites: `tests/test_spike_s1_oxml_fidelity.py`,
`test_spike_s2_locations_coverage.py`, `test_spike_s6_rules.py`,
`test_spike_s6_scale.py`. Validation tooling tests:
`tests/test_validation_metrics.py`.

Use `tests/fixture_factory.py` for deterministic synthetic DOCX cases; where
python-docx cannot construct a case via public APIs, a small documented OOXML
patch is acceptable. For race/thread tests avoid arbitrary sleeps — prefer
`threading.Event`, controlled callbacks, explicit Qt event processing and
deterministic fakes. Test lifecycle state, not merely absence of warnings.

## 9. Required quality gates

Before finishing a task or PR:

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pip check
git diff --check
```

Focused suites are fine during work:

```bash
python -m pytest tests/test_baseline_store.py -q
python -m pytest tests/test_application.py -q
python -m pytest tests/test_ui.py -q
```

CI must stay green on `macos-latest` / Python 3.13 and `windows-latest` /
Python 3.13. Green Windows CI is source-level evidence only — **not**
clean-machine deployment proof.

## 10. Packaging rules

Target: Windows 10/11 x64, PyInstaller **onedir**, `console=False`. Build
Windows artifacts on Windows; never claim macOS-to-Windows cross-compilation.
The shipped app must not depend on the company's Python 3.8: do not upgrade
company Python, modify system PATH, require target-side `pip install`, online
activation/downloads, or administrator privileges. Real no-admin/offline
deployment is a separate validation gate (deferred Task 7).

## 11. Scope control

The MVP excludes: LLM/AI classification, fuzzy or semantic matching, vector
databases, RAG, confidence scores, cloud sync, shared servers, microservices,
plugins, Word automation, editing customer DOCX, automatic updaters,
multi-baseline/template frameworks, baseline history/versioning.

Do not introduce any of these while implementing another task. Future
capabilities must first be recorded in `docs/spec.md` §14, then phased in
`docs/plan.md` §8 and scheduled in `docs/tasks.md`, **before**
implementation.

Security / data: the app is local and offline by design. No telemetry, no
network calls, no cloud storage, no automatic external fetches. Avoid
exposing full internal tracebacks in normal end-user UI.

Performance: expected scale is tens–hundreds of items and hundreds–a few
thousand blocks (already demonstrated near 3,000 × 100). Do not prematurely
optimize with multiprocessing, databases, caches or service processes.

## 12. Current milestone: v0.1 Internal Demo

Tasks 2–5 are implemented on `main`:

```text
Task 2 — real DOCX ingestion
Task 3 — deterministic verification
Task 4 — Qt review workspace
Task 5 — baseline management and persistence
```

Task 6 historical measurement and Task 7 formal deployment validation are
**intentionally deferred by the owner** for this milestone. Task 6 evaluation
tooling exists under `validation/` but has produced no measured metrics — no
independently labelled corpus has been supplied. Status and evidence:
[docs/plan.md §6–§7](docs/plan.md).

Default agent work for this milestone:

```text
bug fixes
small demo usability fixes
documentation maintenance
```

Agents must **not** automatically start:

```text
Task 6 (historical measurement / corpus work)
Task 7 (formal deployment validation)
V0.2 features (export, fuzzy/semantic matching, multi-baseline, …)
```

without explicit owner authorization.

## 13. Review expectations

When judging whether a task/PR is ready, do not rely only on green CI, commit
messages or docs — inspect the actual implementation. For concurrency, verify
lifecycle semantics. For persistence, inspect the exact failure phases. For
matching, compare code against independently labelled tests and the domain
rules. For UI, verify stale state cannot survive transitions. Look for tests
that accidentally miss the dangerous phase.

## 14. Documentation discipline

Update docs only with observed facts. Never claim `PASS`, `validated`,
`complete` or `verified` for work that was not actually run; use `PASS`,
`FAIL`, `NOT RUN`, `NOT MEASURED` or `DEFERRED` appropriately. Keep these
distinctions explicit:

```text
source-level CI ≠ packaging artifact ≠ clean-machine deployment evidence
```

When behavior changes, update the canonical doc that owns the statement —
semantics in `spec.md`, decisions/milestones in `plan.md`, work status in
`tasks.md`, invariants in `constitution.md`. Do not add a fifth project-level
doc, a docs generator or a documentation dependency without authorization.

## 15. Final report format

After completing a task, report:

**Commits** — subtask, commit SHA, commit message.

**Implementation** — what actually changed.

**Validation** — `PASS` / `FAIL` / `NOT RUN` for: focused tests, full pytest,
ruff, format, mypy, pip check, `git diff --check`, macOS CI, Windows CI,
manual GUI validation, Windows deployment validation.

**Known limitations** — explicit.

**Next slice** — recommend one bounded slice only; do not implement it unless
explicitly authorized.

## 16. Core principle

When uncertain, preserve evidence and expose uncertainty.

```text
unknown ≠ false
unsupported ≠ complete
cancelled ≠ completed
different ≠ missing
stale ≠ current
green CI ≠ deployment validated
```
