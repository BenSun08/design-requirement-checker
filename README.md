# Design Requirement Checker

**Python + PySide6 / Qt Widgets desktop application.** Document ingestion is
implemented as a validated vertical slice: import a real `.docx`, view its
blocks with effective-strike formatting and honest coverage warnings. The DOCX
access strategy is backed by executed S1/S2 spike evidence. Deterministic
verification (Task 3) is implemented as a pure matching engine on the
validated S6 rule contract. The Qt review workspace (Task 4) is implemented:
background import/verification, cancellation, stale-outcome suppression,
summary counts, ordering, filters, search, result detail, multi-evidence
navigation, source context, LIMITED coverage notice and keyboard navigation.
Baseline management and persistence (Task 5) is implemented. Windows
distribution (Task 7) remains pending.

## Development platforms

The same Python + PySide6 source tree supports development, execution, testing,
and debugging on **macOS and Windows**. The selected development interpreter is
Python 3.13. This does not change the company's existing Python 3.8 installation:
do not upgrade it or change its PATH/file associations.

### macOS

Create an isolated environment and install the editable project with development
tools:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

Run the desktop application:

```sh
.venv/bin/python -m design_requirement_checker
```

Run all checks:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy src
.venv/bin/python -m pip check
git diff --check
```

### Windows

On a development machine with an approved Python 3.13, use PowerShell to create
an isolated environment and install the editable project with development tools:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Run the desktop application:

```powershell
.\.venv\Scripts\python.exe -m design_requirement_checker
```

Run all checks:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Dependency installation may need network access on development machines. These
commands are not end-user distribution instructions.

### Debugging

Open the repository in VS Code or Cursor, select the interpreter from the local
`.venv`, and launch **Design Requirement Checker**. The shared
`.vscode/launch.json` starts the `design_requirement_checker` module and contains
no developer-specific or operating-system-specific interpreter path.

The window provides a title bar with 导入 DOCX / 开始核查 / 取消核查 /
检查项管理, a summary and search
strip, a QSplitter with the result list and detail pane, and a persistent
status/footer. Import and verification run off the UI thread with
indeterminate progress. Completed runs show summary counts and priority
ordering; filters (全部/已配置/未配置/已划除/待人工核查/仅异常) and search
(code/name/category/expected/description) operate on cached results. The
detail pane shows status, comparison state, expected/actual, match method,
reasons, all evidence occurrences and reconstructed source context.
At startup the baseline is loaded from `QStandardPaths.AppDataLocation /
baseline.json`; 检查项管理 opens a checklist workspace for adding, editing,
enabling/disabling and confirmed-deleting items with stable identities, and
saving one local baseline (atomic two-temp-file save with `.bak` backup
recovery). Missing, backup-recovered, corrupt and unsupported-schema
baselines are shown as explicit, distinct startup conditions. `prototype/`
remains a separate historical mock.

## Source layout

- `src/design_requirement_checker/__main__.py`: startup and Qt composition.
- `src/design_requirement_checker/domain.py`: validated document-snapshot value
  models (blocks, runs, locations, coverage) plus the verification models
  (CheckItem, CheckResult, MatchEvidence and the status/resolution/comparison
  contracts); no Qt/filesystem imports.
- `src/design_requirement_checker/docx_adapter.py`: OOXML ingestion via
  python-docx 1.2.0 + focused OOXML/XML access; the only module touching
  python-docx objects; returns domain values.
- `src/design_requirement_checker/matching.py`: pure deterministic verification
  implementing the validated S6 contract (normalization allowlist with raw-span
  traceability, exact/normalized/alias detection, requirement-span association,
  strike coverage, classification and comparison); domain values in and out.
- `src/design_requirement_checker/application.py`: import coordination
  (`import_document` → Document or explicit ImportFailure) and verification
  coordination (`verify_document` → VerificationOutcome with an explicit
  completed/cancelled lifecycle).
- `src/design_requirement_checker/ui/main_window.py`: Qt review workspace
  (title/toolbar, summary+search strip, QSplitter result list/detail, status);
  owns the UiState lifecycle and operation-generation stale-outcome token;
  delegates import/verification to background workers.
- `src/design_requirement_checker/ui/workers.py`: small QObject workers
  (ImportWorker, VerificationWorker) that run application use cases off the
  UI thread and emit results via signals.
- `baseline_store.py` inside the package: documented responsibility boundary
  only; no business APIs yet.
- `tests/test_domain.py`, `tests/test_docx_adapter.py`, `tests/test_application.py`,
  `tests/test_matching.py`, `tests/test_ui.py`, `tests/test_startup.py`: Task 2/Task 3
  vertical-slice tests with hand-written expected labels.
- `tests/fixture_factory.py`, `tests/docx_probe.py`, `tests/test_spike_s1_oxml_fidelity.py`,
  `tests/test_spike_s2_locations_coverage.py`: S1/S2 spike — deterministic synthetic
  DOCX fixtures, exploratory python-docx + OOXML probe, and evidence tests with
  independent expected labels (see `docs/technical-spikes.md`). Not production code.
- `tests/s6_probe.py`, `tests/test_spike_s6_rules.py`, `tests/test_spike_s6_scale.py`:
  S6 spike evidence for the deterministic rules Task 3 implements. Not production code.
- `tests/fixtures/`: conventions for future synthetic fixtures and independent labels.
- `pyproject.toml`: package metadata and pinned direct development dependencies.

## CI validation

GitHub Actions runs the same test, lint, format, type, and dependency checks on
`macos-latest` and `windows-latest` using Python 3.13. The startup test sets
`QT_QPA_PLATFORM=offscreen` for its child process only; normal application runs
retain the platform's native Qt display behavior.

## Production target and Windows packaging

The production runtime target is **Windows 10/11 x64 only**. macOS is a supported
development and CI platform; it is not a Windows cross-compilation host. Windows
executables are built on a Windows runner through the manually triggered
`build-windows.yml` workflow.

The initial packaging strategy is PyInstaller **onedir**. The workflow uploads
the complete `dist/DesignRequirementChecker/` directory as an artifact, including
`DesignRequirementChecker.exe` and the application-private Python, Qt, and native
runtime files. PyInstaller 6.22.3 is pinned because the current release supports
Python 3.13, PySide6, and a Windows x64 wheel; Python and PySide6 remain at their
existing repository versions. The intended end-user package requires no
separately installed Python, Qt, pip, administrator privileges, or network access.

Creating an artifact in GitHub Actions does not prove Windows 10/11 deployment
readiness. The bundle still requires clean-machine, standard-user, fully offline
testing on both supported Windows families, including tests alongside the
unchanged company Python 3.8 installation and on a machine without Python.

Future persistent baseline, configuration, and log data must use a user-writable
platform location supplied by Qt's `QStandardPaths` (for example Application
Support on macOS and AppData on Windows). Runtime data must not be stored beside
the executable. Persistence itself is not implemented in this infrastructure PR.

See [skeleton verification](docs/skeleton-verification.md) for the earlier local
framework evidence.

## Open the prototype

Double-click `prototype/index.html` in a current Edge/Chrome browser. No package installation, build, server, Python, Node, Office or network connection is required for this route. Keep the four files in `prototype/` together.

Optional local preview server, from the project root:

```sh
python3 -m http.server 8765 --bind 127.0.0.1
```

On Windows with Python already installed, use `py -m http.server 8765 --bind 127.0.0.1`. Open [local preview](http://127.0.0.1:8765/prototype/). Python here is an optional static-file server, not a selected product dependency.

Choose **使用示例文档**, then **开始模拟核查**. Alternatively select/drag one `.docx`; only its name is used. All results and context are fixtures. Baseline edits are session-only and reset on refresh. New or materially edited items have no matching fixture and use an explicitly labelled missing demonstration, not a real document conclusion.

Review `2门控制延时` for `2s → 3s`, `昼行灯状态判断` for deletion formatting, `GAG客户电动导板` for missing evidence, and `侧标志灯功能` for alias evidence. Try filters/search and 检查项管理. No real document parser/matcher, persistence, report export or production installer exists.

## Documents

- [Product specification](docs/product-spec.md): requirements, edge cases, Q1–Q9 and acceptance criteria.
- [Domain model](docs/domain-model.md): technology-neutral concepts and invariants.
- [UX specification](docs/ux-spec.md): workflows, states and review route.
- [Technology options](docs/technology-options.md): five options, ordinal matrix and provisional recommendation with primary references.
- [Technical spikes](docs/technical-spikes.md): S1/S2 and S6 executed with recorded evidence; S3 and persistence validation still planned.
- [Delivery roadmap](docs/delivery-roadmap.md): technology-neutral milestones.
- [Prototype verification](docs/prototype-verification.md): observed checks and limitations.

## File boundaries

`prototype/index.html` — markup; `styles.css` — presentation; `mock-data.js` — 11 fixtures; `app.js` — disposable interactions. This is not the production architecture. Production checklist configuration must be data, not fixtures embedded in source.

## Review gate

The owner selected Python + PySide6 / Qt Widgets and approved the shared
development, CI, and Windows packaging foundation. The S1/S2 document-ingestion
spike has been executed (macOS; python-docx 1.2.0 + focused OOXML access
selected — see the technical-spike evidence), and the Task 2 vertical slice
implements real DOCX import and viewing end-to-end; a review-driven remediation
slice closed its ingestion/coverage gaps (hyperlink-wrapped runs, header/footer
variants, unsupported-structure detection, default-style resolution, error
categories, preview whitespace — see the technical-spike evidence). The S6
spike validated the deterministic rules, and the Task 3 slice implements the
production matching engine on exactly that contract (deterministic detection,
evidence, classification and comparison, with cancellation and a
completed/cancelled run lifecycle). The Task 4 slice implements the Qt review
workspace (background import/verification, cancellation, stale-outcome
suppression, summary counts, ordering, filters, search, result detail,
multi-evidence, source context, LIMITED notice and keyboard navigation), all
on the UI thread with workers off-thread, matching.py and domain.py remaining
Qt-free. Baseline management and persistence (Task 5) is implemented: a JSON
baseline at `QStandardPaths.AppDataLocation/baseline.json` with two-temp-file
atomic saves, `.bak` backup recovery, strict schema validation, stable
baseline/item/alias identities, unsupported-schema write protection and an
explicit checklist-management workspace. Real Windows no-admin/offline
deployment evidence (Task 7) is still pending — green GitHub Actions Windows
CI is source-level CI evidence, not clean-machine deployment evidence. See
the implementation plan for subsequent slices.
