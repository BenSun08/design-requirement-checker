# Design Requirement Checker — Implementation Plan

**2026-09-11 execution note:** The owner separately approved and the repository now
contains the basic desktop skeleton. See [verification](skeleton-verification.md).
The task descriptions below remain the broader plan; the skeleton does not
complete Task 1 or Task 2. Their references to absent source describe the state
before this initialization slice.

[简体中文版](../docs-zh/implementation-plan.md)

**Status:** updated after owner confirmation; planning artifact, not authorization to execute.
**Goal:** deliver a local DOCX checker on Windows 10/11 x64 that ordinary users can use without administrator/installation privileges.
**Tech Stack:** **Python + PySide6 / Qt Widgets — selected by owner.** DOCX library, local storage, dependency versions and packaging tool require within-stack validation.
**Architecture:** one local desktop process. Python application/domain/adapters are independent of the Qt presentation. Background work keeps the UI responsive; no sidecar, HTTP service, QML or embedded web frontend.
**Spec:** [product-spec.md](product-spec.md), [domain-model.md](domain-model.md), [ux-spec.md](ux-spec.md).
**Capacity:** approximately eight hours/week, single-developer workflow.

This revision supersedes the earlier eight-week plan's stack-selection tasks. It records confirmed rules and task/acceptance boundaries without pretending that untested library APIs, versions or Windows deployment choices are finalized. Production source is not created by this update. Before execution, review the relevant probe evidence and authorize a bounded slice; expand its exact interfaces and commands using the validated dependencies.

## Current state and global constraints

- Existing code is a browser mock only. Verification in prototype-verification.md is historical; it is not Python parser or Windows evidence.
- Production target is Windows 10 and Windows 11 x64, with no administrator/installation privileges. No user-installed Python/Qt/Office prerequisite. Exact Windows builds and compatible runtime versions are S3 inputs.
- Initial distribution, extraction/installation, first launch and checking must be completely offline; original documents must remain unchanged. No target-side online bootstrapper, pip install, activation or dependency download.
- One locally maintained baseline. Required id/code/name/detectionPhrase, optional expectedDescription, explicit aliases/category/notes/enabled. No automatic phrase extractor or order-template framework.
- Three CheckStatus values plus separate UNRESOLVED resolution/status unset. Active/deleted coexistence, partial/unknown strike, ambiguous identity and conflicting active key values are unresolved.
- Keep all qualifying occurrences. A single established function with a changed expected value can be CONFIGURED + DIFFERENT; no expected description/unsupported comparison is NOT_COMPARED.
- Body/table/cell paragraphs supported; reconstruct within-paragraph runs only. Excluded/unsupported scope is visible as LIMITED, distinct from failed parsing and MISSING.
- No fuzzy/AI, document editing, Word automation, auto-update infrastructure, plugins or shared services in MVP.

## Execution gates

| Gate | State / requirement |
|---|---|
| A Product rules | Owner confirmed items 1–7; do not ask again for the same policy. Validate transformation and requirement-span details against fixtures. |
| B Production stack | Closed: Python + PySide6 Qt Widgets selected. No finalist comparison or automatic fallback to another framework. |
| C Technical readiness | S1/S2/S3/S6 evidence pending. Record exact library/runtime/storage/packager choices and known gaps before dependent slices. |
| D Execution authorization | This documentation update starts no probes or production code. Obtain authorization for the next bounded work package. |
| E Pilot | Labelled fixture/historical validation and no-admin Windows deployment must pass; owner agrees release thresholds. |

## Proposed source responsibilities

Paths below are planned, not existing files. Keep the small module structure; split only when a real responsibility grows.

| Proposed path | Responsibility |
|---|---|
| `src/design_requirement_checker/domain.py` | Python value models, invariant checks and result/coverage concepts; no Qt/filesystem imports |
| `src/design_requirement_checker/matching.py` | Pure phrase/alias/normalization, evidence aggregation and classification rules |
| `src/design_requirement_checker/application.py` | Import/verify/cancel orchestration, baseline snapshots and result invalidation |
| `src/design_requirement_checker/docx_adapter.py` | Chosen Python OOXML reader, run/style/source mapping and scope warnings |
| `src/design_requirement_checker/baseline_store.py` | One local baseline load/save/recovery in a user-writable location |
| `src/design_requirement_checker/ui/main_window.py` | Qt Widgets import and split review workspace |
| `src/design_requirement_checker/ui/checklist_dialog.py` | Baseline editing/validation and detectionPhrase field |
| `src/design_requirement_checker/__main__.py` | Application startup/composition only |
| `tests/fixtures/`, `tests/test_domain.py`, `tests/test_matching.py`, `tests/test_docx_adapter.py` | Independent expected outcomes and deterministic tests |
| `tests/test_application.py`, `tests/test_baseline_store.py`, `tests/test_ui.py` | Invalidation/cancellation, save/recovery and focused Qt interactions |
| `pyproject.toml` and selected lock/build configuration | Exact validated versions, test/quality commands and package metadata |

Do not create a generic repository layer, protocol framework or internal plugin system. Public contracts follow the domain spec; library-specific objects do not escape the document adapter. Persistence stores baseline data, not mock source fixtures. A source hierarchy proposal does not authorize scaffolding it.

## Task 1 — Validation evidence and Windows feasibility

**Artifacts:** synthetic fixture set, independent expected labels and bounded probe notes; update technical-spikes.md with observed results only after execution.

- [ ] Establish the approved development/build environment, preserving company Python 3.8; record whether an isolated newer interpreter is permitted and verify candidate dependency compatibility before installing anything.
- [ ] Prepare normal/table/mixed-run/full/partial/inherited-strike and contradictory-evidence fixtures, plus sanitized representative samples.
- [ ] Run S1/S2 to select the Python DOCX access strategy and establish source/coverage behavior.
- [ ] Run S3 on both Windows target families as a standard user; test portable distribution first and record policy restrictions.
- [ ] Run S6 for transformation allowlist, specific detection phrases, requirement-span association and performance/cancellation limits.
- [ ] Validate one-baseline storage/recovery and choose a user-writable path/format.
- [ ] Record versions, failures, unsupported features and next bounded slice. Do not claim a passed probe from documentation review.

**Acceptance:** every agreed case has actual expected-versus-observed evidence or an explicit gap. No-admin failures are blockers to deployment readiness. S4 IPC is retired; S5 round-trip editing is deferred. If scope exceeds a timebox, report and replan rather than growing a hidden production engine.

## Task 2 — First vertical slice: open and inspect a real DOCX

**Files:** domain.py, docx_adapter.py, application.py, ui/main_window.py, __main__.py; tests/test_domain.py, tests/test_docx_adapter.py, tests/test_application.py and relevant fixtures. Bootstrap package/test configuration inside this slice using Task 1 decisions.

**Consumes:** local file selection and immutable input bytes. **Produces:** Document with paragraph blocks, original runs/effective strike, stable snapshot locations and coverage warnings, or an explicit failure.

- [ ] Write fixture assertions for paragraph text, table/cell origin, split runs, style inheritance and unsupported/protected/malformed inputs.
- [ ] Demonstrate tests fail for the absent/incorrect behavior before implementing the adapter.
- [ ] Implement the minimum extraction and domain validation under the confirmed scope; no cross-paragraph/cell matching.
- [ ] Show selected filename, blocks and formatting in a minimal Qt Widgets window; parsing stays outside widgets.
- [ ] Check original bytes unchanged, source locations reproducible and LIMITED/failed states distinct from empty successful content.
- [ ] Run focused tests and the configured project checks; review the bounded diff and update documented limitations.

**Acceptance:** real input→real block→visible source works. No matching yet. Unrecognized formatting is not silently active text; unsupported content does not disappear without a scope warning.

## Task 3 — Deterministic verification

**Files:** matching.py, domain.py, application.py; tests/test_matching.py and labelled matching fixtures.

**Consumes:** Document snapshot plus enabled CheckItem snapshot/rule revision. **Produces:** one CheckResult per enabled item, with all evidence, resolution/status, comparison state and reasons; coverage remains run-level.

- [ ] Add tests for exact detectionPhrase, conservative normalization, explicit aliases and original-offset mapping.
- [ ] Add truth-table tests: consistent active→CONFIGURED; all qualifying occurrences fully struck→STRUCK_OUT; none in checked scope→MISSING; partial/unknown/mixed/conflicting/ambiguous→UNRESOLVED.
- [ ] Test a specific delay phrase against 2s/3s, broad related phrase ambiguity, empty expected description and alias-without-description-equivalence.
- [ ] Implement only the independently testable supported rules. Retain original text and every occurrence; match ranking does not discard conflicts.
- [ ] Repeat verification with identical inputs/baseline/rules and compare normalized result data, excluding incidental run metadata.
- [ ] Run focused and project checks; add regressions for discovered false matches.

**Acceptance:** function detection, confidence and description comparison remain separate. No fuzzy or semantic fallback. Uncertain requirement association or unsupported comparison is visible; not presumed correct.

## Task 4 — Qt review workspace

**Files:** ui/main_window.py, application.py; tests/test_ui.py and tests/test_application.py.

- [ ] Build import/run/progress/cancel, totals, status/unresolved filters, exception shortcut and search.
- [ ] Implement list/detail selection with expected/actual comparison, every evidence occurrence, strike spans and nearby source context.
- [ ] Show LIMITED coverage persistently; MISSING text must refer to checked scope. Failed/cancelled runs cannot masquerade as completed results.
- [ ] Invalidate results on document/baseline changes and prevent obsolete background results from becoming current.
- [ ] Keep widgets on the UI thread and test cancellation/lifecycle behavior. Use the simplest validated background approach without a core server.
- [ ] Verify keyboard navigation/focus, Chinese input, long descriptions and DPI on Windows; inspect screenshots at target desktop sizes.

**Acceptance:** configured + different versus unresolved conflicts are distinguishable; total = configured + missing + struck-out + unresolved; comparison differences are an independent count. Missing has no invented evidence. Use the browser as layout reference only.

## Task 5 — Baseline management and persistence

**Files:** baseline_store.py, ui/checklist_dialog.py, application.py; tests/test_baseline_store.py and tests/test_ui.py.

- [ ] Test load/save/restart, invalid schema/data, interrupted save/recovery, write denial and preserving the prior baseline on failure.
- [ ] Implement the selected data format in the validated user-writable location, separate from the program directory.
- [ ] Add/edit code/name/detectionPhrase/category/expectedDescription/aliases/notes/enabled; reject duplicate codes, flag duplicate names/overlapping phrases.
- [ ] Provide disable and confirmed delete; preserve stable IDs. Empty expectedDescription remains permitted.
- [ ] Save one baseline; invalidate results; reload after restart. No customer/order template selector or synchronization.
- [ ] Check backup/replacement behavior with the distribution format and no elevation.

**Acceptance:** engineers can maintain the baseline without editing source; current-order enabled items determine the run; failures never silently discard edits or corrupt the saved baseline.

## Task 6 — Historical validation and release readiness

**Artifacts:** sanitized labelled corpus, measured validation report, regression fixtures, known limitations.

- [ ] Label examples independently of checker outputs and include ambiguous/unsupported cases.
- [ ] Measure precision/recall, false positives/negatives, strike accuracy, unresolved rate, coverage/unsupported rate and review-time change, with denominators.
- [ ] Classify discrepancies as extraction, matching, normalization, configuration, policy or unsupported-scope failures.
- [ ] Fix agreed high-impact failures with regression tests; do not reduce validation time to meet an arbitrary date.
- [ ] Agree release thresholds and pilot scope with the owner before declaring readiness.

## Task 7 — No-admin Windows distribution and pilot

**Artifacts:** validated portable or permitted per-user package, release notes, data-location/replacement instructions, pilot checklist. Exact build files follow the S3 packager decision.

- [ ] Repeat deployment on clean Windows 10 and 11 x64 without administrator/installation privileges or developer runtimes.
- [ ] Verify launch, file selection/drop, offline checking, baseline persistence, Chinese/long paths, DPI and error-log location.
- [ ] Verify app replacement/upgrade/removal does not silently erase baseline data. Document intentional removal separately.
- [ ] Record IT policy/endpoint-protection behavior; do not require disabling controls or elevation to pass.
- [ ] Test offline transfer, extraction/installation and first launch with networking disabled and no cached prerequisites. Include Python 3.8 present/unchanged and Python absent; no target-side downloads, pip install or online activation.
- [ ] Deliver pilot instructions and known limitations only after release authorization; no automatic publishing, merge or release tag implied.

**Acceptance:** ordinary users can use the chosen distribution on both OS families; no Python/Qt installation prerequisite; offline checking passes; data survives application replacement. Unsupported Windows builds or execution policies are explicit blockers rather than hidden exceptions.

## Schedule and review cadence

The former eight-week outline is an initial planning reference, not a reliable commitment. Task 1 has several probes whose combined effort can exceed one eight-hour week. Estimate subsequent slices after measuring it; do not allocate only one week to all fidelity/packaging uncertainty. Each working session should end with one reviewable result or explicit gap. Keep focused branches/PRs, tests and documentation updates; merging/publishing requires its own authorization.

## Verification and definition of done

Choose and pin test/lint/type-check tooling when package configuration is created; no executable project checks currently exist for production. Once configured, use focused unit tests, fixture tests, small application/Qt tests, then full agreed checks and `git diff --check`. Do not substitute a browser mock test for a real DOCX fixture or clean Windows run.

A slice is complete only when its acceptance evidence exists, failures and scope limitations are explicit, documentation matches behavior and the relevant regression checks pass. Pilot additionally requires historical metrics/thresholds and both OS/no-admin deployment evidence. AI, enhanced fuzzy/diff, export, manual approval, Word integration and team features remain separate future decisions.

## Next authorized decision

This update closes technology selection and records product policies. The next proposed work package is Task 1 (bounded S1/S2/S3/S6 and persistence validation), pending explicit execution authorization and required Windows/sample access. It does not re-open the selected stack or start production scaffolding automatically.

## Confirmed Python 3.8 and fully offline environment

The owner reports that company computers currently have **Python 3.8** installed; upgrading it may not be possible. This is an existing-environment fact, not a selected application/build runtime version. Keep that installation and its PATH/file associations unchanged. Targets remain **Windows 10 and Windows 11 x64**, with **no administrator/installation privileges**. **Initial distribution, extraction/installation, first launch and normal checking must be completely offline.**

The planned self-contained package must carry its validated Python/Qt/native dependencies and must not invoke the computer's `python` or require target-side `pip install`, online activation or downloads. S3 must verify execution both alongside unchanged Python 3.8 and on a clean machine without Python, with networking disabled and no cached prerequisites. No packaged build has passed these checks yet.

Development/build environment availability is a separate open item: establish whether an approved isolated/newer interpreter and Windows build machine are available without changing the company installation. Do not assume a Python 3.8 `venv` upgrades the interpreter. If the only permitted build/runtime is 3.8, first evaluate the exact compatible dependency set and maintenance implications; do not silently pin old packages or change the selected stack. Full offline delivery does not establish whether the build machine itself has network access; record that separately and prepare offline build dependencies if needed.
