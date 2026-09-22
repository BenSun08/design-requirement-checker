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

    window = MainWindow(check_items=items, baseline_id=baseline_id)

    # --- Recovery / failure UX ---
    if load_result.ok and load_result.source == "backup":
        # Recovered from backup — show persistent in-window warning.
        window.set_baseline_recovered(
            "已从备份基准恢复 · 主基准文件不可用 · 建议检查文件系统权限"
        )
    elif not load_result.ok:
        # Neither primary nor backup usable — explicit failure.
        window.set_baseline_failure(load_result.error or "未知错误")
    # "no-baseline" / "primary" paths need no extra banner.

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
