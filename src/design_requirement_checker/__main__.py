"""Desktop entry point; compose the UI with baseline loading (Task 5)."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from design_requirement_checker.application import load_baseline_from
from design_requirement_checker.baseline_store import default_path
from design_requirement_checker.ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv if argv is None else argv)
    if not isinstance(app, QApplication):
        raise RuntimeError("Desktop startup requires QApplication")
    app.setApplicationName("Design Requirement Checker")

    # --- Load baseline from AppDataLocation; never blocks startup. ---
    baseline_path = default_path()
    load_result = load_baseline_from(baseline_path)

    if load_result.ok:
        items = load_result.items or ()
        baseline_id = load_result.baseline_id or ""
    else:
        items = ()
        baseline_id = ""

    # On success source is "primary" / "backup" / "no-baseline"; on failure
    # "load-error" / "unsupported-schema". The window records the condition
    # explicitly and shows the matching banner — no error-string parsing.
    window = MainWindow(check_items=items, baseline_id=baseline_id)
    window.apply_baseline_load(load_result.source, error=load_result.error)

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
