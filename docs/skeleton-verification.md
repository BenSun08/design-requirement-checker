# Desktop skeleton verification — 2026-09-11

The owner approved basic directories, package configuration, startup and a minimal
Qt Widgets window. This is a separate initialization slice; it does not complete
Task 1 or the real-DOCX vertical slice in implementation-plan.md.

## Observed environment and checks

- Development host: macOS; isolated Python 3.13.7 virtual environment.
- PySide6 / Qt 6.11.2; pytest 9.1.1; Ruff 0.16.6; mypy 2.3.1.
- Editable package installation and ordinary Python wheel build succeeded.
- Startup smoke test: 1 passed. It invokes the real entry point, observes one
  visible window, checks unavailable actions and closes the window/event loop.
  The test first failed because the application package did not exist.
- Ruff lint/format, strict mypy and pip dependency consistency checks passed.
- Offscreen 1100 × 720 window image inspected: Chinese labels are legible, the
  initialization notice and disabled controls are visible, and both workspace
  panels fit without clipping. Rendering uses Qt's native widget styling.
- Qt offscreen rendering reported a missing generic Sans Serif font alias and
  used platform font fallback. Windows fonts/DPI still require native testing.

## Boundaries

The five business modules contain responsibility documentation only. No DOCX
library, baseline format, domain contract or matching rule is selected by this
scaffold. The historical browser mock remains unchanged.

Python 3.13 is the narrow current development baseline, not proof of a supported
Windows release runtime. Direct dependencies are pinned in pyproject.toml;
this is not a cross-platform transitive lock or an offline dependency bundle.
The wheel contains Python code and is not a self-contained Windows executable.

No native Windows, no-admin, fully offline first-launch, historical-corpus,
parser-fidelity or matching-accuracy validation has run. Company Python 3.8 and
its environment must remain unchanged. No commit, push or release was performed.
