"""Desktop entry point; compose the UI without loading document adapters."""

import sys

from PySide6.QtWidgets import QApplication

from design_requirement_checker.ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv if argv is None else argv)
    if not isinstance(app, QApplication):
        raise RuntimeError("Desktop startup requires QApplication")
    app.setApplicationName("Design Requirement Checker")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
