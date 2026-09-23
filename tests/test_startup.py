"""Exercise the real startup path without requiring an interactive desktop."""

import os
import subprocess
import sys
from pathlib import Path

from design_requirement_checker.baseline_store import save_baseline
from design_requirement_checker.domain import CheckItem


def _item(item_id: str = "a") -> CheckItem:
    return CheckItem(
        item_id=item_id,
        code=item_id.upper(),
        name=f"name-{item_id}",
        detection_phrase=f"功能{item_id.upper()}",
        aliases=(),
    )


def _run_startup_script(tmp_path: Path, assertions: str) -> subprocess.CompletedProcess[str]:
    """Run production ``main()`` in a subprocess with the baseline path
    redirected to ``tmp_path`` (never the developer's real AppData) and the
    given post-startup assertions executed against the created MainWindow.
    """
    script = f"""
import os
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import design_requirement_checker.__main__ as entry

baseline_file = Path(os.environ["TEST_BASELINE_PATH"])
entry.default_path = lambda: baseline_file

app = QApplication([])
created = []

def close_window():
    for window in app.topLevelWidgets():
        if window.isVisible():
            created.append(window)
            window.close()
    app.quit()

QTimer.singleShot(100, close_window)
assert entry.main([]) == 0
assert len(created) == 1, "Startup must show one main window"
window = created[0]
{assertions}
print("STARTUP-OK")
"""
    return subprocess.run(
        [sys.executable, "-c", script],
        env={
            **os.environ,
            "QT_QPA_PLATFORM": "offscreen",
            "TEST_BASELINE_PATH": str(tmp_path / "baseline.json"),
        },
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestPersistedBaselineStartupComposition:
    """HOTFIX H3 — integration regression across the composition boundary.

    The unit tests separately proved that ``load_baseline_from`` returns
    source="primary" and that the UI handles no-baseline/backup/errors, but
    the boundary between them (``__main__.main`` feeding the source token
    into ``MainWindow.apply_baseline_load``) crashed on every normal
    restart with a persisted baseline. These tests exercise the real
    production path end-to-end in a subprocess with a temp baseline file.
    """

    def test_valid_primary_baseline_starts_without_crash(self, tmp_path) -> None:
        baseline_path = tmp_path / "baseline.json"
        items = (_item("a"), _item("b"))
        save_baseline(baseline_path, items, "bid-startup-1")

        result = _run_startup_script(
            tmp_path,
            """
assert window._baseline_load_state == "normal", window._baseline_load_state
assert window._baseline_banner.isHidden()
assert [i.item_id for i in window._check_items] == ["a", "b"]
assert window._baseline_id == "bid-startup-1"
""",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "STARTUP-OK" in result.stdout

    def test_backup_recovery_startup_shows_warning(self, tmp_path) -> None:
        baseline_path = tmp_path / "baseline.json"
        backup_path = tmp_path / "baseline.json.bak"
        # Primary corrupt, backup valid → recovery from backup.
        baseline_path.write_text("{ not json", encoding="utf-8")
        save_baseline(backup_path, (_item("a"),), "bid-startup-2")

        result = _run_startup_script(
            tmp_path,
            """
assert window._baseline_load_state == "backup", window._baseline_load_state
assert not window._baseline_banner.isHidden()
assert "已从备份基准恢复" in window._baseline_banner.text()
assert len(window._check_items) == 1
assert window._baseline_id == "bid-startup-2"
""",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "STARTUP-OK" in result.stdout

    def test_first_launch_no_baseline_startup(self, tmp_path) -> None:
        # No baseline.json and no .bak → ordinary first-use state.
        result = _run_startup_script(
            tmp_path,
            """
assert window._baseline_load_state == "no-baseline", window._baseline_load_state
assert window._baseline_banner.isHidden()
assert window._check_items == ()
""",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "STARTUP-OK" in result.stdout


def test_startup_shows_window_and_exits_when_closed() -> None:
    # Catch a missing show(), broken composition, or event loop that never exits.
    script = """
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPushButton
from design_requirement_checker.__main__ import main

app = QApplication([])
observed = []
enabled_actions = []
filter_labels = {"全部", "已配置", "未配置", "已划除", "待人工核查", "仅异常"}
def inspect_and_close():
    windows = [w for w in app.topLevelWidgets() if w.isVisible()]
    observed.extend(windows)
    for window in windows:
        enabled_actions.extend(
            button.text() for button in window.findChildren(QPushButton)
            if button.isEnabled() and button.text() not in filter_labels
        )
        window.close()
    app.quit()

QTimer.singleShot(100, inspect_and_close)
assert main([]) == 0
assert len(observed) == 1, "Startup must show one main window"
assert sorted(enabled_actions) == ["导入 DOCX", "检查项管理"], \\
       "Only implemented operations may be enabled"
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
