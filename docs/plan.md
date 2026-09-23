# Design Requirement Checker — Engineering Plan

This document records how the product is built and evolved: technology
choices, architecture, lasting technical decisions, completed milestones,
validation evidence, deferred work and the roadmap. Detailed product
requirements live in [spec.md](spec.md); non-negotiable invariants in
[constitution.md](constitution.md); the actionable work list in
[tasks.md](tasks.md).

## 1. Current state

The repository is at **v0.1 Internal Demo** (2026-09-23). Production Tasks
2–5 are implemented and merged to `main`: real DOCX ingestion, deterministic
verification, the Qt review workspace, and baseline management with local
persistence. Task 6 exists as evaluation *tooling only* — no historical
measurement has been performed. Task 7 formal deployment validation is
deferred.

The `prototype/` directory is a historical browser mock kept for UX
reference; it is not production code and not the production UI.

## 2. Technical stack

| Concern | Choice |
|---|---|
| Language / runtime | Python 3.13 (development, CI and packaged runtime) |
| UI | PySide6 / Qt Widgets (one local desktop process; no QML, no embedded web engine) |
| DOCX access | python-docx 1.2.0 + focused OOXML/lxml access |
| Persistence | UTF-8 JSON via `QStandardPaths.AppDataLocation` |
| Testing | pytest (with `pytest-qt` for widget tests) |
| Lint / format / types | Ruff, Ruff format, mypy (strict on `src`) |
| Packaging | PyInstaller 6.22.3, **onedir**, `console=False` |
| Production target | Windows 10 / 11 x64, standard user, no admin |
| Development / CI platforms | macOS and Windows (Python 3.13) |

Direct development dependencies are pinned in `pyproject.toml`. Pins are not
a cross-platform transitive lock or an offline dependency bundle.

## 3. Architecture

One local desktop process with the boundaries defined in
[constitution.md §4](constitution.md):

```text
ui/            Qt Widgets, worker lifecycle, presentation only
application.py use-case orchestration, invalidation, failure translation
domain.py      frozen value models, enums, invariants (no I/O, no Qt)
matching.py    pure deterministic engine (no I/O, no Qt)
docx_adapter.py  the only python-docx / OOXML / lxml boundary
baseline_store.py  the only persistence boundary
__main__.py    composition root
```

Background work uses `QObject` workers on `QThread`s with signal handoff and
`threading.Event` cooperative cancellation. There is no sidecar, HTTP
service, plugin system or generic repository layer, and none is planned.

## 4. Key technical decisions

Only lasting decisions are recorded here. The detailed original spike
transcripts are preserved in Git history (see the pre-consolidation
`docs/technical-spikes.md` at commit `e85a44f` and earlier).

| Decision | Selected approach | Evidence | Known limitation |
|---|---|---|---|
| Application stack | Python + PySide6 / Qt Widgets, one local process | Owner decision (2026-09-10) after a five-option comparison; Electron/Tauri/.NET/sidecar variants rejected on maintained-language count, footprint and 8 h/week sustainability | Qt model/view learning curve; packaging needs desktop testing |
| DOCX extraction | python-docx 1.2.0 + focused OOXML/lxml access | S1/S2 spike (2026-09-18, macOS, synthetic fixtures): high-level APIs omit hyperlink-contained runs and obscure style inheritance | Unsupported detected structures yield LIMITED coverage; encrypted DOCX validated only as a container-format failure path |
| Strike resolution | Full inheritance chain, `w:default="1"` default style, tri-state unknown | S1/S2 + Task 2 remediation | Unresolved double-strike semantics stay unknown |
| Matching | Deterministic rule engine, N1–N3 normalization allowlist, forward-only requirement spans, span-level strike coverage | S6 spike (2026-09-19): hand-labelled rule tests, scale 3,000 blocks × 100 items ≈ 1.1 s, ≈ 0.13 MB transient peak, per-(item, block) cancellation checkpoints, determinism | No cross-paragraph/cell joining; association uncertainty is explicit, not resolved |
| Status model | 3 `CheckStatus` values + separate `Resolution` (UNRESOLVED ⇒ status unset) | Owner-confirmed product rule; enforced as a domain invariant | — |
| Persistence | UTF-8 JSON, `schemaVersion = 1`, two-temp-file atomic save, `.bak` recovery, strict validation | Persistence spike (2026-09-20, corrected 2026-09-22; 56 spike tests): SQLite and single-temp alternatives rejected for failure-phase risk | Backup/replacement behavior untested against the real distribution format |
| Packaging | PyInstaller onedir, built on a Windows runner via a manually triggered workflow | `build-windows.yml` builds and uploads the artifact | An artifact is not deployment evidence; owner smoke check only |
| Concurrency | QThread workers + signals, `threading.Event` cancel, generation token for stale suppression | Task 4 (13 subtasks) + teardown-segfault fix: never destroy a running QThread | Windows DPI/IME behavior unvalidated |

## 5. Completed milestones

**Task 1 — technical validation (spikes).** S1/S2 (DOCX fidelity, locations,
coverage), S6 (deterministic rules and scale) and the persistence-validation
spike executed on macOS with synthetic fixtures and hand-written expected
labels. Result: the ingestion, matching and persistence contracts were
selected before production code. Caveat: S3 (Windows deployment) was never
executed; all spike evidence is synthetic-fixture evidence.

**Task 2 — real DOCX ingestion.** Domain value models, the validated
python-docx + OOXML adapter, `import_document` with categorized failures,
and a minimal Qt document view. A same-day remediation pass closed ingestion
gaps: hyperlink-wrapped runs extracted, header/footer variants detected,
known unsupported structures force LIMITED, default style resolved from
`w:default="1"`, distinct read-failure categories, whitespace-preserving
preview. 100 tests.

**Task 3 — deterministic verification.** Production `matching.py` plus the
verification domain models, implementing exactly the validated S6 contract:
allowlist normalization with raw-offset traceability, exact/normalized/alias
detection from configured phrases only, forward-only spans with explicit
uncertainty reasons, span-level strike coverage, the confirmed truth table,
retained conflicting evidence, independent comparison, cooperative
cancellation, deterministic ordering, rule revision `task3-v1`. 245 tests; a
later remediation moved the cancellation checkpoint to immediately before
each (item, block) candidate search without changing matching policy.

**Task 4 — Qt review workspace.** 13 reviewable subtasks: `UiState`
lifecycle driving enablement, monotonic operation-generation token,
off-thread import/verification workers, QSplitter list/detail workspace,
summary counts with the total invariant, priority ordering, six filters plus
search over cached results, multi-evidence selector, reconstructed source
context with span highlighting, persistent LIMITED notice, keyboard
navigation, scoped MISSING wording. 317 tests. A teardown-segfault fix
established the "never destroy a running QThread" ownership rule.

**Task 5 — baseline management and persistence.** `baseline_store.py` with
the two-temp-file atomic save, `.bak` recovery, strict `schemaVersion = 1`
validation and `UnsupportedBaselineSchemaError` on both load and save; the
checklist and item-editor dialogs with stable item/alias identities,
duplicate-code rejection and name/phrase overlap warnings; explicit startup
baseline conditions; result invalidation with stale suppression. 493 tests
after a 12-commit remediation pass.

**Task 6 — evaluation tooling only.** `validation/` (schema, harness,
metrics, report renderer, README workflow) plus
`scripts/run_historical_validation.py`, self-tested against synthetic
fixtures. 552 tests. **The task is BLOCKED, not complete**: no independently
labelled historical corpus has been supplied, so every metric is NOT
MEASURED (denominator 0) and thresholds remain proposals with PENDING OWNER
APPROVAL.

**Demo closeout (2026-09-23).** Owner decision to stop formal validation for
this milestone and close as v0.1 Internal Demo. Documentation-only slice:
status/evidence/runbook docs written and de-drifted, `pyproject` description
updated. No tag, no GitHub Release.

## 6. Validation evidence summary

| Evidence | State |
|---|---|
| Repository test suite (552 tests, independent expected labels) | PASS |
| Ruff check / format, strict mypy on `src`, `pip check`, `git diff --check` | PASS |
| GitHub Actions CI, macOS 3.13 + Windows 3.13 | PASS |
| Windows PyInstaller onedir artifact build (`build-windows.yml`) | AVAILABLE |
| Owner manual run of the downloaded exe on a company computer | PASS — demo smoke check only |
| Historical measured precision / recall / strike accuracy / unresolved rate | NOT MEASURED |
| Clean-machine Win10/Win11, no-admin, offline, Python-3.8-coexistence matrix | NOT RUN |
| DPI / Chinese-input / long-description matrices on Windows | NOT RUN |
| Release thresholds | NOT APPROVED (proposal only) |

The owner smoke check recorded no OS version, admin status, network state,
endpoint-policy state or Python presence, and none may be inferred from it.

## 7. Deferred release validation

Deferred by the owner for the v0.1 internal-demo milestone — prerequisites
before any production/pilot readiness claim, not deleted requirements:

- Independently labelled historical corpus and Task 6 measurement
  (precision/recall, false positives/negatives, strike accuracy, unresolved
  and coverage rates, review-time change, all with denominators).
- Discrepancy classification (extraction / matching / normalization /
  configuration / policy / unsupported-scope) and agreed high-impact fixes.
- Owner-agreed release thresholds and pilot scope.
- Task 7 / S3: repeated clean Windows 10 and 11 x64 deployments as a
  standard user with no developer runtimes; fully offline transfer,
  extraction, first launch and checking; Python 3.8 present/unchanged and
  Python absent; enterprise endpoint-protection behavior; app
  replacement/upgrade preserving baseline data; error-log location.
- Existing manual gaps: Windows DPI matrix, Chinese-input validation,
  long-description layout, target-size screenshots.

The deployment matrix to satisfy: Win10 x64, Win11 x64, company Python 3.8
installed, no Python installed, network disabled, standard non-admin user,
Chinese paths, long paths, endpoint protection, real company DOCX files.
Goal: copy → unzip → double-click → works, with no administrator, internet,
Python, pip, Qt or Office automation.

## 8. Future roadmap

Feature definitions live in [spec.md §14](spec.md); the actionable backlog in
[tasks.md](tasks.md). Phasing only:

```text
Milestone A — v0.1 Internal Demo        DONE (2026-09-23)
Milestone B — production validation      DEFERRED by owner
              (Task 6 measurement, Task 7 deployment, thresholds)
V0.2 — usability & review enhancements   CANDIDATE (not scheduled)
              export, enhanced diff, fuzzy candidates, manual confirmation,
              improved preview, drag-and-drop, multi-baseline, versions
Future — AI / collaboration capabilities UNCOMMITTED
              semantic/LLM fallback, RAG, generated corrections, DOCX
              editing, Word integration, team sync, cloud baselines
```

## 9. Release strategy

No release tag, GitHub Release or pilot distribution exists for v0.1. The
distribution model for the demo is: manually trigger `build-windows.yml`,
download the onedir artifact, distribute the whole extracted
`DesignRequirementChecker/` directory.

Formal release requires, in order: an independently labelled corpus and
measured metrics, owner-approved thresholds, Task 7 deployment evidence on
both Windows families, and explicit owner release authorization. Merging,
publishing and tagging each require their own authorization.

Capacity remains a single developer at roughly eight hours per week; each
working session should end with one reviewable result or an explicit gap.
Schedule estimates are made after measuring, never derived from the
historical mock.
