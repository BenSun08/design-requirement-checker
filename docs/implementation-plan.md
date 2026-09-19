# Design Requirement Checker — Implementation Plan

**2026-09-11 execution note:** The owner separately approved and the repository now
contains the basic desktop skeleton. See [verification](skeleton-verification.md).
The task descriptions below remain the broader plan; the skeleton does not
complete Task 1 or Task 2. Their references to absent source describe the state
before this initialization slice.

**2026-09-18 execution records:** Task 1 S1/S2 spikes executed (macOS, synthetic
fixtures) — see [technical-spikes.md](technical-spikes.md). Task 2 first DOCX
vertical slice executed on the same day: domain value models, the validated
python-docx 1.2.0 + focused OOXML adapter, import coordination and a minimal
Qt document view, test-first. A same-day remediation slice fixed
ingestion/coverage defects found in review: hyperlink-wrapped runs are
extracted (previously silent loss), first-page/even-page header and footer
variants and table-only header/footer content are detected, known unsupported
structures (field codes, footnote/endnote references, `w:altChunk`, smart
tags, nested hyperlinks) force LIMITED instead of silent COMPLETE, the
default paragraph style is resolved from the `w:default="1"` marker rather
than an assumed "Normal" id, read failures carry distinct categories
(file-access-error / invalid-or-unreadable-document / unexpected-parser-error),
and the preview preserves whitespace (`white-space: pre-wrap`). Matching,
baseline persistence, background execution and Windows validation remain
future tasks.

[简体中文版](../docs-zh/implementation-plan.md)

**Status:** updated after owner confirmation; planning artifact, not authorization to execute.
**Goal:** deliver a local DOCX checker on Windows 10/11 x64 that ordinary users can use without administrator/installation privileges.
**Tech Stack:** **Python + PySide6 / Qt Widgets — selected by owner.** DOCX library, local storage, dependency versions and packaging tool require within-stack validation.
**Architecture:** one local desktop process. Python application/domain/adapters are independent of the Qt presentation. Background work keeps the UI responsive; no sidecar, HTTP service, QML or embedded web frontend.
**Spec:** [product-spec.md](product-spec.md), [domain-model.md](domain-model.md), [ux-spec.md](ux-spec.md).
**Capacity:** approximately eight hours/week, single-developer workflow.

**Platform boundaries:** macOS and Windows are development and CI platforms. The
production runtime remains Windows 10/11 x64, and Windows artifacts are built on
Windows only. The initial package is a PyInstaller onedir portable bundle; no
macOS-to-Windows cross-compilation is supported.

This revision supersedes the earlier eight-week plan's stack-selection tasks. It records confirmed rules and task/acceptance boundaries without pretending that untested library APIs, versions or Windows deployment choices are finalized. Production source is not created by this update. Before execution, review the relevant probe evidence and authorize a bounded slice; expand its exact interfaces and commands using the validated dependencies.

## Current state and global constraints

- Existing production code is a desktop skeleton alongside the historical browser mock. The repository has one shared Python source tree for macOS and Windows development; neither is Python parser or Windows deployment evidence.
- Production target is Windows 10 and Windows 11 x64, with no administrator/installation privileges. No user-installed Python/Qt/Office prerequisite. Exact Windows builds and compatible runtime versions are S3 inputs.
- Initial distribution, extraction/installation, first launch and checking must be completely offline; original documents must remain unchanged. No target-side online bootstrapper, pip install, activation or dependency download.
- GitHub Actions validates Python 3.13 on macOS and Windows. The manual Windows-only build workflow creates a PyInstaller onedir artifact; CI packaging is an input to S3, not completion of S3.
- Future persistent baseline/configuration/log paths are platform adapters selected through Qt `QStandardPaths`; the domain and application layers remain OS-independent and the executable directory is not a writable-data location.
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
| C Technical readiness | Cross-platform CI and the initial PyInstaller onedir configuration exist. S1/S2/S3/S6 evidence remains pending; a CI artifact does not prove clean-machine offline deployment. |
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
| `pyproject.toml`, `.github/workflows/` and `packaging/windows/` | Shared development/CI dependencies, test/quality commands and Windows-only PyInstaller onedir packaging |

Do not create a generic repository layer, protocol framework or internal plugin system. Public contracts follow the domain spec; library-specific objects do not escape the document adapter. Persistence stores baseline data, not mock source fixtures. A source hierarchy proposal does not authorize scaffolding it.

## Task 1 — Validation evidence and Windows feasibility

**Artifacts:** synthetic fixture set, independent expected labels and bounded probe notes; update technical-spikes.md with observed results only after execution.

- [ ] Establish the approved development/build environment, preserving company Python 3.8; record whether an isolated newer interpreter is permitted and verify candidate dependency compatibility before installing anything.
- [ ] Prepare normal/table/mixed-run/full/partial/inherited-strike and contradictory-evidence fixtures, plus sanitized representative samples.
- [x] Run S1/S2 to select the Python DOCX access strategy and establish source/coverage behavior. Executed 2026-09-18 on the macOS development machine with synthetic fixtures and independent labels; evidence and limitations recorded in [technical-spikes.md](technical-spikes.md). Selected: python-docx 1.2.0 + focused OOXML/XML access; unknown formatting preserved; merged-cell/tracked-revision/excluded-structure hazards made explicit. Windows/S3 and real-document evidence remain open.
- [ ] Run S3 on both Windows target families as a standard user; test portable distribution first and record policy restrictions.
- [ ] Run S6 for transformation allowlist, specific detection phrases, requirement-span association and performance/cancellation limits.
- [ ] Validate one-baseline storage/recovery and choose a user-writable path/format.
- [ ] Record versions, failures, unsupported features and next bounded slice. Do not claim a passed probe from documentation review.

**Acceptance:** every agreed case has actual expected-versus-observed evidence or an explicit gap. No-admin failures are blockers to deployment readiness. S4 IPC is retired; S5 round-trip editing is deferred. If scope exceeds a timebox, report and replan rather than growing a hidden production engine.

## Task 2 — First vertical slice: open and inspect a real DOCX

**Files:** domain.py, docx_adapter.py, application.py, ui/main_window.py, __main__.py; tests/test_domain.py, tests/test_docx_adapter.py, tests/test_application.py and relevant fixtures. Bootstrap package/test configuration inside this slice using Task 1 decisions.

**Consumes:** local file selection and immutable input bytes. **Produces:** Document with paragraph blocks, original runs/effective strike, stable snapshot locations and coverage warnings, or an explicit failure.

- [x] Write fixture assertions for paragraph text, table/cell origin, split runs, style inheritance, unsupported structures and malformed inputs. Done 2026-09-18 in tests/test_domain.py, tests/test_docx_adapter.py, tests/test_application.py and tests/test_ui.py with hand-written labels, reusing the spike fixture factory. Remediation (same day) added fixtures for hyperlink-wrapped runs, header/footer variants (including table-only content), a custom default paragraph style, unsupported structures (field codes, footnote/endnote references, `w:altChunk`, smart tags) and the OLE compound-file container of password-protected documents. Encrypted/password-protected DOCX handling remains unvalidated beyond that container-format failure path — see remaining validation.
- [x] Demonstrate tests fail for the absent/incorrect behavior before implementing the adapter. All four new test modules failed on collection (ImportError) before implementation; observed in the Task 2 run log.
- [x] Implement the minimum extraction and domain validation under the confirmed scope; no cross-paragraph/cell matching. domain.py (validated value models), docx_adapter.py (python-docx 1.2.0 + focused OOXML/XML access ported from the validated spike probe), application.py (import_document -> Document or ImportFailure).
- [x] Show selected filename, blocks and formatting in a minimal Qt Widgets window; parsing stays outside widgets. ui/main_window.py renders filename, coverage warnings and blocks with strike markers; it only calls the application use case (import deferred until first use so startup stays adapter-free).
- [x] Check original bytes unchanged, source locations reproducible and LIMITED/failed states distinct from empty successful content. Asserted by test_docx_adapter (sha256 before/after, repeated-read stability) and test_ui (LIMITED warnings, explicit failure, empty document distinct).
- [x] Run focused tests and the configured project checks; review the bounded diff and update documented limitations. 87 tests passed; ruff check, ruff format --check, mypy (strict), pip check and git diff --check all pass. Known limitations: parsing runs on the UI thread during import (background execution is Task 4); Windows and real-document validation pending. Remediation re-ran all gates: 100 tests passed with the same checks green; the Windows PyInstaller workflow was not triggered in the remediation slice and stays pending manual run.

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

**Artifacts:** validated PyInstaller onedir portable package, release notes, data-location/replacement instructions, pilot checklist. The Windows-only CI build supplies a candidate bundle; S3 establishes whether it is deployable.

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

The package pins test/lint/type-check tooling and CI runs it on macOS and Windows. Use focused unit tests, fixture tests, small application/Qt tests, then the full configured checks and `git diff --check`. Do not substitute a passing CI matrix, browser mock test, or PyInstaller artifact for a real DOCX fixture or clean Windows run.

A slice is complete only when its acceptance evidence exists, failures and scope limitations are explicit, documentation matches behavior and the relevant regression checks pass. Pilot additionally requires historical metrics/thresholds and both OS/no-admin deployment evidence. AI, enhanced fuzzy/diff, export, manual approval, Word integration and team features remain separate future decisions.

## Next authorized decision

This update closes technology selection and records product policies. S1/S2 of Task 1 were executed with recorded evidence (2026-09-18, macOS; see [technical-spikes.md](technical-spikes.md)), and Task 2 (first DOCX vertical slice) was executed the same day under owner authorization: real input → real blocks → visible source works end-to-end on the macOS development machine. The next proposed work package is Task 3 (deterministic verification), pending explicit execution authorization. The remaining Task 1 probes (S3, S6, persistence validation) stay pending and require their own authorization and Windows/sample access. No step here re-opens the selected stack or starts the next slice automatically.

## Confirmed Python 3.8 and fully offline environment

The owner reports that company computers currently have **Python 3.8** installed; upgrading it may not be possible. This is an existing-environment fact, not a selected application/build runtime version. Keep that installation and its PATH/file associations unchanged. Targets remain **Windows 10 and Windows 11 x64**, with **no administrator/installation privileges**. **Initial distribution, extraction/installation, first launch and normal checking must be completely offline.**

The planned self-contained package must carry its validated Python/Qt/native dependencies and must not invoke the computer's `python` or require target-side `pip install`, online activation or downloads. S3 must verify execution both alongside unchanged Python 3.8 and on a clean machine without Python, with networking disabled and no cached prerequisites. No packaged build has passed these checks yet.

Development/build environment availability is a separate open item: establish whether an approved isolated/newer interpreter and Windows build machine are available without changing the company installation. Do not assume a Python 3.8 `venv` upgrades the interpreter. If the only permitted build/runtime is 3.8, first evaluate the exact compatible dependency set and maintenance implications; do not silently pin old packages or change the selected stack. Full offline delivery does not establish whether the build machine itself has network access; record that separately and prepare offline build dependencies if needed.
