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

**2026-09-19 execution record:** Task 1 S6 (deterministic rules and scale
validation) executed as a bounded spike on the macOS development machine — see
[technical-spikes.md](technical-spikes.md). It established, with hand-labelled
test evidence in isolated spike code (`tests/s6_probe.py`,
`tests/test_spike_s6_rules.py`, `tests/test_spike_s6_scale.py`): the exact
normalization allowlist (N1–N3 approved, R1–R7 explicitly rejected), raw ↔
normalized offset mapping, the forward-only requirement-span association rule
with explicit uncertainty reasons (`requirement-span-association-uncertain`,
`no-associated-requirement-content`), strike evaluation over the requirement
span, the confirmed truth table (CONFIGURED / STRUCK_OUT / MISSING / UNRESOLVED
with status unset), repeated/conflicting evidence behavior, description
comparison as an independent dimension, verification-level vs
configuration-level ambiguity, scale viability (3,000 blocks × 100 items ≈
1.1 s; ≈ 0.13 MB transient peak), per-(CheckItem, block) cancellation
checkpoints and determinism. No production matching code was written;
`matching.py` remains a placeholder and Task 3 stays a separate pending slice.

**2026-09-20 execution record:** Task 3 (deterministic verification) executed
as one bounded production slice. The production domain models (CheckItem,
CheckItemAlias, CheckResult, CheckStatus, Resolution, ComparisonState,
MatchType, StrikeCoverage, MatchEvidence) and the pure matching engine now
implement exactly the validated S6 contract: the N1–N3 normalization allowlist
with raw-offset traceability (R1–R7 rejected transformations kept as negative
tests), exact/normalized/alias detection from configured phrases only,
forward-only requirement-span association with the S6 uncertainty reasons,
strike coverage over the requirement span, the confirmed truth table with
UNRESOLVED keeping status unset, retained repeated/conflicting/ambiguous
evidence, independent SAME/DIFFERENT/NOT_COMPARED comparison, per-(CheckItem,
block) cancellation checkpoints and deterministic ordering. `application.py`
exposes `verify_document` with an explicit completed/cancelled lifecycle; a
cancelled run never yields a completed result set. 245 tests pass, including a
synthetic-DOCX → ingestion → verification composition test; no fuzzy/semantic
matching, no confidence scores, no fourth status, no Task 4 UI or Task 5
persistence was pulled forward.

**2026-09-21 remediation:** Task 3 cancellation checkpoint semantics remediated.
The checkpoint now occurs immediately before each (CheckItem, block) candidate
search rather than in a batch ahead of the matching work; cross-item ambiguity
and requirement-span association still run after all of a block's candidates
are collected. No matching policy changed. 246 tests pass.

**2026-09-21 execution record:** Task 4 (Qt review workspace) executed as 13
reviewable subtasks on branch `task4-qt-review-workspace`. The MainWindow now
owns an explicit `UiState` lifecycle (EMPTY / IMPORTING / READY / VERIFYING /
COMPLETED / CANCELLED / FAILED) that drives action enablement, plus a monotonic
operation-generation token that invalidates stale worker outcomes. DOCX import
and `verify_document` run off the UI thread through small QObject workers on
dedicated QThreads; cancellation uses the existing application callback. The
workspace shell is a QSplitter (result list + detail) under a title/toolbar,
summary+search strip and persistent status/footer. Completed runs display
summary counts (total = configured + missing + struck_out + unresolved;
DIFFERENT is orthogonal) and priority ordering
(UNRESOLVED → MISSING → STRUCK_OUT → CONFIGURED+DIFFERENT → remaining
CONFIGURED). Filters (全部/已配置/未配置/已划除/待人工核查/仅异常) and search
(code/name/category/expected/description) operate on the cached result set
without recomputing verification. The detail pane renders status, comparison
state, expected/actual, match method, review reasons (with UNRESOLVED reason
tokens mapped to Chinese in the UI only), per-status presentation (MISSING
shows a scope-limited message with no fabricated evidence; STRUCK_OUT shows
strike styling plus textual state; NOT_COMPARED shows the human-readable
reason), a multi-evidence selector, and reconstructed prev/current/next block
source context with requirement-span highlighting. LIMITED coverage shows a
persistent "检查范围受限" notice that survives filtering and detail navigation.
Keyboard navigation (Up/Down/Enter, Ctrl+F) is supported. matching.py and
domain.py remain Qt-free; CheckItems are injected via the constructor
(`Sequence[CheckItem]`, default empty → 尚未加载检查项, Run disabled). No
persistence, checklist editor, Task 5, HTTP/sidecar, or generic task framework
was introduced. 317 tests pass (96 in test_ui.py); ruff check, ruff format
--check, mypy (strict), pip check and git diff --check all pass locally. The
prior intermittent teardown segfault for windows that started a background
thread is resolved: `_stop_worker` now retains ownership of any QThread that
has not actually finished (never destroying a running thread), sets the
verification cancel event before quitting, and `_finish_operation` only clears
current thread/worker refs when they still refer to the completing operation.

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
- [x] Run S6 for transformation allowlist, specific detection phrases, requirement-span association and performance/cancellation limits. Executed 2026-09-19 on the macOS development machine with synthetic fixtures and independent labels; evidence in [technical-spikes.md](technical-spikes.md): exact normalization allowlist (N1–N3 approved, R1–R7 rejected with negative tests), raw ↔ normalized offset mapping, forward-only requirement-span association with explicit uncertainty reasons, strike truth table over requirement spans, conflict/ambiguity behavior, comparison independence, scale viability (3,000 blocks / 100 items ≈ 1.1 s), per-(item, block) cancellation checkpoints and determinism, plus composition with real Task 2 ingestion output. Windows/S3 and real-document evidence remain open.
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

- [x] Add tests for exact detectionPhrase, conservative normalization, explicit aliases and original-offset mapping. tests/test_matching.py covers exact/absent/broad/neighbouring/name-only detection, the S6 N1/N2/N3 allowlist with raw-span mapping, the rejected transformations (R1–R7) as negative tests, and alias identity/evidence retention.
- [x] Add truth-table tests: consistent active→CONFIGURED; all qualifying occurrences fully struck→STRUCK_OUT; none in checked scope→MISSING; partial/unknown/mixed/conflicting/ambiguous→UNRESOLVED. Parametrized truth-table test plus dedicated strike, conflict and ambiguity tests; UNRESOLVED keeps status unset (domain invariant enforced in CheckResult).
- [x] Test a specific delay phrase against 2s/3s, broad related phrase ambiguity, empty expected description and alias-without-description-equivalence. The confirmed example resolves CONFIGURED + DIFFERENT (never MISSING); uncertain association yields NOT_COMPARED with the S6 reason tokens.
- [x] Implement only the independently testable supported rules. Retain original text and every occurrence; match ranking does not discard conflicts. matching.py implements the S6 contract (normalization with offset map, forward-only requirement spans, span-level strike coverage, classification, independent comparison); every occurrence is retained in source order and ambiguous evidence is kept with flags.
- [x] Repeat verification with identical inputs/baseline/rules and compare normalized result data, excluding incidental run metadata. Determinism tests assert equal results and stable source ordering across repeated runs at matching and application level.
- [x] Run focused and project checks; add regressions for discovered false matches. 245 tests pass; ruff check, ruff format --check, mypy (strict), pip check and git diff --check all pass. Task 2 ingestion tests remain green; one composition test runs synthetic DOCX → read_document → verify_document.

**Acceptance:** function detection, confidence and description comparison remain separate. No fuzzy or semantic fallback. Uncertain requirement association or unsupported comparison is visible; not presumed correct. No confidence score exists anywhere in the result model (asserted by test). Cancellation is checked once per (CheckItem, block); a cancelled run returns an explicit CANCELLED outcome with no results, never a completed all-MISSING report. Disabled items produce no results. Rule revision `task3-v1` is carried on every CheckResult.

## Task 4 — Qt review workspace

**Files:** ui/main_window.py, application.py; tests/test_ui.py and tests/test_application.py.

- [x] Build import/run/progress/cancel, totals, status/unresolved filters, exception shortcut and search. Import and verification run on background QThreads; indeterminate progress and Cancel button are wired; summary counts, six filters and search are implemented.
- [x] Implement list/detail selection with expected/actual comparison, every evidence occurrence, strike spans and nearby source context. Multi-evidence selector, expected/actual, match method, review reasons and reconstructed prev/current/next block context with span highlighting are present.
- [x] Show LIMITED coverage persistently; MISSING text must refer to checked scope. "检查范围受限" notice survives filter and detail navigation; MISSING wording is scoped to the checked range.
- [x] Invalidate results on document/baseline changes and prevent obsolete background results from becoming current. Operation-generation token plus document-id match gates worker completion; cancelled runs show no final counts.
- [x] Keep widgets on the UI thread and test cancellation/lifecycle behavior. Workers emit only signals; UI applies results on the UI thread.
- [ ] Verify keyboard navigation/focus, Chinese input, long descriptions and DPI on Windows; inspect screenshots at target desktop sizes. Keyboard navigation and focus tested on macOS; Windows DPI/screenshot inspection remains pending.

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

This update closes technology selection and records product policies. S1/S2 of Task 1 were executed with recorded evidence (2026-09-18, macOS; see [technical-spikes.md](technical-spikes.md)), and Task 2 (first DOCX vertical slice) was executed the same day under owner authorization: real input → real blocks → visible source works end-to-end on the macOS development machine. S6 of Task 1 (deterministic rules and scale validation) was executed 2026-09-19 with recorded evidence: the deterministic rules Task 3 needs are established without inventing product policy. Task 3 (deterministic verification) was executed 2026-09-20 under owner
authorization: the production matching engine implements exactly the validated
S6 contract, with 245 passing tests including a real-ingestion composition
test. Task 4 (Qt review workspace) was executed 2026-09-21 under owner
authorization as 13 reviewable subtasks: the full review workspace
(background import/verification, cancellation, stale-outcome suppression,
summary counts, ordering, filters, search, result detail, multi-evidence,
source context, LIMITED notice, keyboard navigation) is implemented with 317
passing tests and all local quality gates green. The next proposed work
package is Task 5 (baseline management and persistence), pending explicit
execution authorization. The remaining Task 1 probes (S3, persistence validation) stay pending and require their own authorization and Windows/sample access. No step here re-opens the selected stack or starts the next slice automatically.

## Confirmed Python 3.8 and fully offline environment

The owner reports that company computers currently have **Python 3.8** installed; upgrading it may not be possible. This is an existing-environment fact, not a selected application/build runtime version. Keep that installation and its PATH/file associations unchanged. Targets remain **Windows 10 and Windows 11 x64**, with **no administrator/installation privileges**. **Initial distribution, extraction/installation, first launch and normal checking must be completely offline.**

The planned self-contained package must carry its validated Python/Qt/native dependencies and must not invoke the computer's `python` or require target-side `pip install`, online activation or downloads. S3 must verify execution both alongside unchanged Python 3.8 and on a clean machine without Python, with networking disabled and no cached prerequisites. No packaged build has passed these checks yet.

Development/build environment availability is a separate open item: establish whether an approved isolated/newer interpreter and Windows build machine are available without changing the company installation. Do not assume a Python 3.8 `venv` upgrades the interpreter. If the only permitted build/runtime is 3.8, first evaluate the exact compatible dependency set and maintenance implications; do not silently pin old packages or change the selected stack. Full offline delivery does not establish whether the build machine itself has network access; record that separately and prepare offline build dependencies if needed.
