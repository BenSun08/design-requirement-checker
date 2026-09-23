# Design Requirement Checker

A local, offline desktop application that checks engineering `.docx`
documents (《设计开发要求》) against an engineer-maintained checklist
baseline and presents deterministic, evidence-backed results for human
engineering review.

## Status

**v0.1 Internal Demo Ready** (2026-09-23).

This is *not* a production or pilot release: formal historical accuracy
measurement (Task 6) and clean-machine / no-admin / offline Windows
deployment validation (Task 7) are **deferred** by the owner. See
[docs/plan.md](docs/plan.md) and [docs/tasks.md](docs/tasks.md) for the
exact evidence and deferred items.

## What it does

- Import a local `.docx` (file dialog; source bytes are never modified).
- Maintain one local checklist baseline: add/edit/disable/delete items with
  code, name, detection phrase, aliases, expected description, category and
  notes; stable IDs survive restarts.
- Run deterministic verification: exact / normalized (conservative
  allowlist) / alias detection with full evidence retention.
- Classify each enabled item as 已配置 (CONFIGURED), 未配置 (MISSING),
  已划除 (STRUCK_OUT), or 待人工核查 (UNRESOLVED — ambiguous/conflicting
  evidence with status deliberately unset), with an independent
  expected-vs-actual description comparison (SAME / DIFFERENT / NOT_COMPARED).
- Review results in a Qt workspace: summary counts, priority ordering,
  filters, search, multi-evidence detail and reconstructed source context.
- Persist the baseline atomically as local JSON with backup recovery.
- Honest scope: unsupported Word structures force a visible LIMITED-coverage
  notice; failures never become an all-missing report; a text match is never
  engineering acceptance.

## Quick start

Run from source (development machine, Python 3.13):

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m design_requirement_checker
```

On Windows, substitute `py -3.13 -m venv .venv` and
`.\.venv\Scripts\python.exe` for the interpreter paths.

Demo workflow: 检查项管理 → add items → 保存基准 → 导入 DOCX → 开始核查 →
review exceptions → inspect evidence and source context → decide.

For the packaged Windows artifact, extract the **whole**
`DesignRequirementChecker/` directory and launch
`DesignRequirementChecker.exe`; no Python installation is required or
intended for end users.

The baseline is stored at `QStandardPaths.AppDataLocation / baseline.json`
(per-user AppData on Windows), never beside the executable, and survives
application replacement.

## Architecture

One local desktop process; boundaries are normative in
[docs/constitution.md](docs/constitution.md):

```text
PySide6 UI (ui/)
    ↓
Application (application.py)
    ↓
Domain (domain.py) + Matching (matching.py)
    ↑
DOCX Adapter (docx_adapter.py — the only python-docx/OOXML boundary)

Baseline Store (baseline_store.py — the only persistence boundary)
    ↓
Domain
```

`__main__.py` is the composition root. Import and verification run off the
UI thread on `QThread` workers with cooperative cancellation and stale-result
suppression.

## Development

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy src
.venv/bin/python -m pip check
git diff --check
```

GitHub Actions CI runs these checks on `macos-latest` and `windows-latest`
with Python 3.13. Debug by selecting the `.venv` interpreter in VS Code /
Cursor and launching the `design_requirement_checker` module
(`.vscode/launch.json` is shared and interpreter-path-free).

macOS and Windows are development and CI platforms; the production runtime
target is Windows 10/11 x64 only.

## Windows build

Windows artifacts are built **on Windows** via the manually triggered
`build-windows.yml` workflow (no macOS-to-Windows cross-compilation). The
package is a PyInstaller **onedir** bundle (`console=False`) carrying its own
Python 3.13, Qt and native runtime: end users need no Python, Qt, pip,
administrator privileges or network access. The company's existing Python 3.8
installation remains untouched.

A built artifact is *not* deployment evidence: clean-machine, standard-user,
fully offline validation on both Windows families is deferred Task 7 work.

## Documentation

Canonical project documentation (English; authority order
constitution > spec > plan > tasks):

- [docs/constitution.md](docs/constitution.md) — non-negotiable engineering
  principles, architecture boundaries, domain invariants and governance.
- [docs/spec.md](docs/spec.md) — product specification: requirements, domain
  semantics, UX behavior, current limitations and future features.
- [docs/plan.md](docs/plan.md) — engineering plan: stack, key decisions,
  completed milestones, validation evidence and roadmap.
- [docs/tasks.md](docs/tasks.md) — actionable work list: completed, deferred
  and backlog items with ready/done definitions.

[AGENTS.md](AGENTS.md) is the operating manual for AI coding agents.

`prototype/` is a historical browser UX mock only — not production behavior.
Open `prototype/index.html` in a current browser; all results there are
fixtures.

## Current limitations

- No measured historical accuracy (no independently labelled corpus supplied).
- No formal clean-machine / no-admin / offline Windows deployment matrix.
- No drag-and-drop import (file dialog only); no report export.
- No fuzzy, semantic or LLM matching (deterministic rules only, by design).
- No automatic joining of requirement text across paragraphs or table cells.
- Unsupported Word structures produce LIMITED coverage rather than results.
- No automatic engineering approval — a human reviewer decides.

Full list in [docs/spec.md §13](docs/spec.md); backlog in
[docs/tasks.md](docs/tasks.md).
