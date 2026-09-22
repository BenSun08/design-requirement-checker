"""Task 5 checklist-management UI regression tests.

Covers the startup baseline conditions (no-baseline / backup / load-error /
unsupported-schema) and the checklist management workflows added in Task 5.
No test writes to real user AppData: persistence targets are injected via
tmp_path + monkeypatched ``default_path``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from design_requirement_checker.baseline_store import UnsupportedBaselineSchemaError
from design_requirement_checker.domain import CheckItem
from design_requirement_checker.ui.main_window import MainWindow


def _item(item_id: str = "a", phrase: str = "功能") -> CheckItem:
    return CheckItem(
        item_id=item_id,
        code=item_id.upper(),
        name=f"name-{item_id}",
        detection_phrase=phrase,
        aliases=(),
    )


def _accepted_dialog(items: tuple[CheckItem, ...]) -> MagicMock:
    """A ChecklistDialog stand-in that returns ``items`` on accept."""
    dialog = MagicMock()
    dialog.exec.return_value = QDialog.DialogCode.Accepted
    dialog.current_items.return_value = items
    return dialog


def _run_manage_flow(
    window: MainWindow,
    items: tuple[CheckItem, ...],
    tmp_path,
    *,
    save_side_effect: Exception | None = None,
):
    """Drive _on_manage_clicked with a stubbed dialog + clean validation.

    Patch targets are the defining modules because _on_manage_clicked uses
    function-local imports. Returns the ``save_baseline_to`` mock so tests
    can assert call counts or configure side effects via ``save_side_effect``.
    """
    with (
        patch(
            "design_requirement_checker.ui.checklist_dialog.ChecklistDialog",
            return_value=_accepted_dialog(items),
        ),
        patch(
            "design_requirement_checker.baseline_store.default_path",
            return_value=tmp_path / "baseline.json",
        ),
        patch(
            "design_requirement_checker.application.validate_baseline",
            return_value=MagicMock(errors=(), warnings=()),
        ),
        patch(
            "design_requirement_checker.application.save_baseline_to",
            side_effect=save_side_effect,
        ) as save_mock,
    ):
        window._on_manage_clicked()
    return save_mock


class TestStartupLoadStates:
    """R5.7 — NO_BASELINE / BACKUP / LOAD_ERROR / UNSUPPORTED_SCHEMA stay
    distinct and drive explicit behavior."""

    def test_constructor_rejects_unknown_state(self, qapp) -> None:
        with pytest.raises(ValueError, match="unknown baseline_load_state"):
            MainWindow(baseline_load_state="bogus")

    def test_apply_baseline_load_rejects_unknown_source(self, qapp) -> None:
        window = MainWindow()
        with pytest.raises(ValueError, match="unknown baseline load source"):
            window.apply_baseline_load("bogus")
        window.close()

    def test_no_baseline_allows_first_save_without_confirmation(self, qapp, tmp_path) -> None:
        window = MainWindow(baseline_load_state="no-baseline")
        window.apply_baseline_load("no-baseline")
        assert window._baseline_banner.isHidden()
        assert window._baseline_load_state == "no-baseline"

        new_items = (_item("a"), _item("b"))
        with patch("PySide6.QtWidgets.QMessageBox.question") as mock_question:
            mock_save = _run_manage_flow(window, new_items, tmp_path)

        mock_question.assert_not_called()  # no destructive confirmation
        mock_save.assert_called_once()
        assert window._check_items == new_items
        assert window._baseline_load_state == "normal"
        window.close()

    def test_backup_state_shows_banner_and_save_clears_it(self, qapp, tmp_path) -> None:
        window = MainWindow(baseline_load_state="backup")
        window.apply_baseline_load("backup")
        assert not window._baseline_banner.isHidden()
        assert "已从备份基准恢复" in window._baseline_banner.text()

        new_items = (_item("a"),)
        _run_manage_flow(window, new_items, tmp_path)

        # Successful save installs a new primary: recovery banner cleared.
        assert window._check_items == new_items
        assert window._baseline_load_state == "normal"
        assert window._baseline_banner.isHidden()
        window.close()

    def test_unsupported_schema_banner_and_save_refused(self, qapp, tmp_path) -> None:
        window = MainWindow(baseline_load_state="unsupported-schema")
        window.apply_baseline_load("unsupported-schema")
        assert not window._baseline_banner.isHidden()
        assert "不兼容的较新版本" in window._baseline_banner.text()
        assert "本版本不会覆盖该文件" in window._baseline_banner.text()

        new_items = (_item("a"),)
        with patch("PySide6.QtWidgets.QMessageBox.critical") as mock_critical:
            mock_save = _run_manage_flow(
                window,
                new_items,
                tmp_path,
                save_side_effect=UnsupportedBaselineSchemaError("unsupported schemaVersion: 999"),
            )

        mock_save.assert_called_once()  # attempted, store refused
        # Compat-specific failure, not a generic disk error.
        # QMessageBox.critical(parent, title, text) → title is args[1].
        titles = [call.args[1] for call in mock_critical.call_args_list]
        assert "基准版本不兼容" in titles
        # Nothing published; compatibility state and banner persist.
        assert window._check_items == ()
        assert window._baseline_load_state == "unsupported-schema"
        assert not window._baseline_banner.isHidden()
        window.close()

    def test_load_error_save_requires_confirmation_and_no_blocks(self, qapp, tmp_path) -> None:
        window = MainWindow(baseline_load_state="load-error")
        window.apply_baseline_load("load-error", error="两份文件均无法读取")
        assert not window._baseline_banner.isHidden()
        assert "检查基准加载失败" in window._baseline_banner.text()

        new_items = (_item("a"),)
        with patch(
            "PySide6.QtWidgets.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ) as mock_question:
            mock_save = _run_manage_flow(window, new_items, tmp_path)

        mock_question.assert_called_once()  # destructive replacement is explicit
        prompt = mock_question.call_args.args[2]
        assert "当前基准无法读取" in prompt
        mock_save.assert_not_called()
        assert window._check_items == ()
        assert window._baseline_load_state == "load-error"
        assert not window._baseline_banner.isHidden()
        window.close()

    def test_load_error_save_confirmed_yes_proceeds(self, qapp, tmp_path) -> None:
        window = MainWindow(baseline_load_state="load-error")
        window.apply_baseline_load("load-error", error="两份文件均无法读取")

        new_items = (_item("a"),)
        with patch(
            "PySide6.QtWidgets.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ) as mock_question:
            mock_save = _run_manage_flow(window, new_items, tmp_path)

        mock_question.assert_called_once()
        mock_save.assert_called_once()
        assert window._check_items == new_items
        assert window._baseline_load_state == "normal"
        assert window._baseline_banner.isHidden()
        window.close()

    def test_normal_state_save_needs_no_confirmation(self, qapp, tmp_path) -> None:
        window = MainWindow(check_items=(_item("a"),))
        assert window._baseline_load_state == "normal"
        with patch("PySide6.QtWidgets.QMessageBox.question") as mock_question:
            _run_manage_flow(window, (_item("a"), _item("b")), tmp_path)
        mock_question.assert_not_called()
        assert window._check_items == (_item("a"), _item("b"))
        window.close()
