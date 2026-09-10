# Design Requirement Checker

**Python + PySide6 / Qt Widgets desktop skeleton.** Production stack is selected;
DOCX ingestion, matching, persistence and Windows distribution remain pending.

## Desktop development

The current development baseline is **Python 3.13** in an isolated environment.
This is not the final Windows deployment runtime decision. Do not replace the
company Python 3.8 installation or change its PATH/file associations.

macOS / Linux development shell:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m design_requirement_checker
```

Windows PowerShell, only on a development machine with an approved Python 3.13:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m design_requirement_checker
```

These commands install developer dependencies and may need network access. They
are not end-user distribution instructions. End-user delivery must bundle its
validated runtime for fully offline operation without administrator privileges.

The window contains a title, an initialization notice and a split workspace.
Future import/check/manage buttons are disabled. It reads no DOCX, generates no
results and stores no baseline. `prototype/` remains a separate historical mock.

## Source layout

- `src/design_requirement_checker/__main__.py`: startup and Qt composition.
- `src/design_requirement_checker/ui/main_window.py`: minimal desktop window.
- `domain.py`, `application.py`, `matching.py`, `docx_adapter.py`, `baseline_store.py`
  inside the package: documented responsibility boundaries only; no business APIs yet.
- `tests/test_startup.py`: real Qt startup/show/close smoke test in a subprocess.
- `tests/fixtures/`: conventions for future synthetic fixtures and independent labels.
- `pyproject.toml`: package metadata and pinned direct development dependencies.

## Development checks

After installing the development extras:

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src
.venv/bin/python -m pip check
git diff --check
```

On Windows use the executables in `.venv\Scripts` instead of `.venv/bin`.
The startup test sets `QT_QPA_PLATFORM=offscreen` for its child process only.
These checks do not establish DOCX accuracy or Windows deployment readiness.
See [skeleton verification](docs/skeleton-verification.md) for observed evidence.

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
- [Technical spikes](docs/technical-spikes.md): bounded proposals, not executed experiments.
- [Delivery roadmap](docs/delivery-roadmap.md): technology-neutral milestones.
- [Prototype verification](docs/prototype-verification.md): observed checks and limitations.

## File boundaries

`prototype/index.html` — markup; `styles.css` — presentation; `mock-data.js` — 11 fixtures; `app.js` — disposable interactions. This is not the production architecture. Production checklist configuration must be data, not fixtures embedded in source.

## Review gate

The owner selected Python + PySide6 / Qt Widgets and approved the basic skeleton. Technical-spike evidence is still pending for document ingestion, matching, storage and no-admin offline Windows packaging. See the implementation plan for subsequent slices; this skeleton does not complete those slices.
