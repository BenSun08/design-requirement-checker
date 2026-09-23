"""Exercise the real startup path without requiring an interactive desktop."""

import os
import subprocess
import sys
from pathlib import Path

from design_requirement_checker.baseline_store import save_baseline
from design_requirement_checker.domain import CheckItem

_TESTS_DIR = str(Path(__file__).resolve().parent)


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


class TestImportWorkflowStaysAlive:
    """HOTFIX H4 — reproduce the reported user workflow end-to-end.

    Start with a valid persisted PRIMARY baseline, import a real DOCX
    through the background ImportWorker, wait for completion, run
    verification, and confirm the process never exits unexpectedly. This
    runs the real production composition in a subprocess so an unhandled
    exception (the kind PyInstaller surfaces as a startup dialog) fails
    the run.
    """

    def test_startup_then_import_then_verify_keeps_process_alive(self, tmp_path) -> None:
        baseline_path = tmp_path / "baseline.json"
        # Detection phrase matches text produced by fixture_factory.build_normal.
        item = CheckItem(
            item_id="a",
            code="A",
            name="name-a",
            detection_phrase="plain body paragraph one",
            aliases=(),
        )
        save_baseline(baseline_path, (item,), "bid-import-1")
        docx_path = tmp_path / "sample.docx"

        script = f"""
import os, sys
sys.path.insert(0, {os.path.join(_TESTS_DIR)!r})
from pathlib import Path
import fixture_factory
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import design_requirement_checker.__main__ as entry

docx_file = Path(os.environ["TEST_DOCX_PATH"])
fixture_factory.build_normal(docx_file)

baseline_file = Path(os.environ["TEST_BASELINE_PATH"])
entry.default_path = lambda: baseline_file

app = QApplication([])
created = []
stage = {{"name": "startup"}}
failure = []

def find_window():
    for w in app.topLevelWidgets():
        if w.isVisible():
            return w
    return None

def step_import():
    try:
        window = find_window()
        assert window is not None
        assert window._baseline_load_state == "normal"
        window._start_import(str(docx_file))
        assert window.state.name == "IMPORTING"
        stage["name"] = "importing"
        QTimer.singleShot(50, poll_ready)
    except Exception as exc:  # noqa: BLE001
        failure.append(("import", repr(exc)))
        app.quit()

def poll_ready():
    try:
        window = find_window()
        if window.state.name != "READY":
            QTimer.singleShot(50, poll_ready)
            return
        assert window._document is not None
        stage["name"] = "ready"
        window._on_run_clicked()
        assert window.state.name == "VERIFYING"
        stage["name"] = "verifying"
        QTimer.singleShot(50, poll_completed)
    except Exception as exc:  # noqa: BLE001
        failure.append((stage["name"], repr(exc)))
        app.quit()

def poll_completed():
    try:
        window = find_window()
        if window.state.name != "COMPLETED":
            QTimer.singleShot(50, poll_completed)
            return
        assert len(window._results) == 1
        assert window._results[0].status.name == "CONFIGURED"
        stage["name"] = "completed"
        # Close first, then quit — the same order the proven startup test
        # uses, so teardown matches the existing Windows-clean pattern.
        window.close()
    except Exception as exc:  # noqa: BLE001
        failure.append((stage["name"], repr(exc)))
        window = find_window()
        if window is not None:
            window.close()
    app.quit()

QTimer.singleShot(150, step_import)
rc = entry.main([])
assert not failure, f"workflow failed at {{failure}}"
assert stage["name"] == "completed", stage["name"]
print("WORKFLOW-OK rc=", rc)
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            env={
                **os.environ,
                "QT_QPA_PLATFORM": "offscreen",
                "TEST_BASELINE_PATH": str(baseline_path),
                "TEST_DOCX_PATH": str(docx_path),
            },
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "WORKFLOW-OK" in result.stdout


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
