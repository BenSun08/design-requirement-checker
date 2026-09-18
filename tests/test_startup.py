"""Exercise the real startup path without requiring an interactive desktop."""

import os
import subprocess
import sys


def test_startup_shows_window_and_exits_when_closed() -> None:
    # Catch a missing show(), broken composition, or event loop that never exits.
    script = """
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPushButton
from design_requirement_checker.__main__ import main

app = QApplication([])
observed = []
enabled_actions = []
def inspect_and_close():
    windows = [w for w in app.topLevelWidgets() if w.isVisible()]
    observed.extend(windows)
    for window in windows:
        enabled_actions.extend(
            button for button in window.findChildren(QPushButton) if button.isEnabled()
        )
        window.close()
    app.quit()

QTimer.singleShot(100, inspect_and_close)
assert main([]) == 0
assert len(observed) == 1, "Startup must show one main window"
assert [button.text() for button in enabled_actions] == [
    "导入 DOCX"
], "Only implemented operations may be enabled"
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
