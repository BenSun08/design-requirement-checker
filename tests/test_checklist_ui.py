"""Task 5 checklist-management UI regression tests.

Covers the startup baseline conditions (no-baseline / backup / load-error /
unsupported-schema), the checklist management workflows, and candidate
preservation across failed saves. No test writes to real user AppData:
persistence targets are injected via tmp_path + monkeypatched ``default_path``.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from design_requirement_checker.baseline_store import UnsupportedBaselineSchemaError
from design_requirement_checker.domain import CheckItem
from design_requirement_checker.ui.main_window import MainWindow


def _item(item_id: str = "a", phrase: str = "功能A") -> CheckItem:
    return CheckItem(
        item_id=item_id,
        code=item_id.upper(),
        name=f"name-{item_id}",
        detection_phrase=phrase,
        aliases=(),
    )


def _save_via_dialog(
    window: MainWindow,
    candidate_items: tuple[CheckItem, ...],
    tmp_path,
    *,
    save_side_effect: Exception | None = None,
    mock_save: bool = True,
):
    """Open the real ChecklistDialog wired to the window save handler and
    press 保存基准 once.

    Persistence is redirected to ``tmp_path``. By default
    ``application.save_baseline_to`` is mocked (``save_side_effect`` injects
    a failure); with ``mock_save=False`` the real application+store stack
    runs against ``tmp_path`` so the persisted file itself can be asserted.
    Returns ``(dialog, save_mock, accepted)`` where ``save_mock`` is None
    when the real stack was used and ``accepted`` records whether the
    dialog closed via accept().
    """
    from design_requirement_checker.ui.checklist_dialog import ChecklistDialog

    def _run() -> tuple[object, list[bool]]:
        dialog = ChecklistDialog(
            window._check_items,
            parent=window,
            save_handler=window._save_baseline_snapshot,
        )
        dialog._items = list(candidate_items)
        accepted: list[bool] = []
        dialog.accepted.connect(lambda: accepted.append(True))
        dialog._on_save_requested()
        return dialog, accepted

    with patch(
        "design_requirement_checker.baseline_store.default_path",
        return_value=tmp_path / "baseline.json",
    ):
        if mock_save:
            with patch(
                "design_requirement_checker.application.save_baseline_to",
                side_effect=save_side_effect,
            ) as save_mock:
                dialog, accepted = _run()
            return dialog, save_mock, accepted
        save_mock = None
        dialog, accepted = _run()
        return dialog, save_mock, accepted


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

        new_items = (_item("a"),)
        with patch("PySide6.QtWidgets.QMessageBox.question") as mock_question:
            _dialog, mock_save, accepted = _save_via_dialog(window, new_items, tmp_path)

        mock_question.assert_not_called()  # no destructive confirmation
        mock_save.assert_called_once()
        assert accepted == [True]
        assert window._check_items == new_items
        assert window._baseline_load_state == "normal"
        window.close()

    def test_backup_state_shows_banner_and_save_clears_it(self, qapp, tmp_path) -> None:
        window = MainWindow(baseline_load_state="backup")
        window.apply_baseline_load("backup")
        assert not window._baseline_banner.isHidden()
        assert "已从备份基准恢复" in window._baseline_banner.text()

        new_items = (_item("a"),)
        _dialog, _mock_save, accepted = _save_via_dialog(window, new_items, tmp_path)

        # Successful save installs a new primary: recovery banner cleared.
        assert accepted == [True]
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
            _dialog, mock_save, accepted = _save_via_dialog(
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
        assert accepted == []  # dialog stays open
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
            _dialog, mock_save, accepted = _save_via_dialog(window, new_items, tmp_path)

        mock_question.assert_called_once()  # destructive replacement is explicit
        prompt = mock_question.call_args.args[2]
        assert "当前基准无法读取" in prompt
        mock_save.assert_not_called()
        assert accepted == []
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
            _dialog, mock_save, accepted = _save_via_dialog(window, new_items, tmp_path)

        mock_question.assert_called_once()
        mock_save.assert_called_once()
        assert accepted == [True]
        assert window._check_items == new_items
        assert window._baseline_load_state == "normal"
        assert window._baseline_banner.isHidden()
        window.close()

    def test_normal_state_save_needs_no_confirmation(self, qapp, tmp_path) -> None:
        window = MainWindow(check_items=(_item("a"),))
        assert window._baseline_load_state == "normal"
        with patch("PySide6.QtWidgets.QMessageBox.question") as mock_question:
            _dialog, _mock_save, accepted = _save_via_dialog(
                window, (_item("a"), _item("b", phrase="功能B")), tmp_path
            )
        mock_question.assert_not_called()
        assert accepted == [True]
        assert window._check_items == (_item("a"), _item("b", phrase="功能B"))
        window.close()


class TestCandidatePreservation:
    """R5.8 — failed validation/persistence keeps the dialog open with the
    candidate intact; the current baseline and results never change."""

    def test_dialog_accepts_only_when_handler_succeeds(self, qapp) -> None:
        from design_requirement_checker.ui.checklist_dialog import ChecklistDialog

        accepted: list[bool] = []

        dialog = ChecklistDialog((_item("a"),), save_handler=lambda _items: False)
        dialog.accepted.connect(lambda: accepted.append(True))
        dialog._on_save_requested()
        assert accepted == []
        assert dialog.result() != QDialog.DialogCode.Accepted
        assert len(dialog.current_items()) == 1  # candidate rows remain

        dialog2 = ChecklistDialog((_item("a"),), save_handler=lambda _items: True)
        dialog2.accepted.connect(lambda: accepted.append(True))
        dialog2._on_save_requested()
        assert accepted == [True]
        assert dialog2.result() == QDialog.DialogCode.Accepted

    def test_duplicate_code_blocks_save_and_candidate_remains(self, qapp, tmp_path) -> None:
        window = MainWindow(check_items=(_item("a"),))
        dup = CheckItem(
            item_id="dup-1",
            code="A",  # same code as _item("a")
            name="other-name",
            detection_phrase="功能X",
            aliases=(),
        )
        candidate = (_item("a"), dup)

        with patch("PySide6.QtWidgets.QMessageBox.critical") as mock_critical:
            _dialog, mock_save, accepted = _save_via_dialog(window, candidate, tmp_path)

        mock_save.assert_not_called()  # validation error blocks persistence
        mock_critical.assert_called_once()  # reason shown
        assert accepted == []  # dialog stays open with candidate
        assert window._check_items == (_item("a"),)  # current baseline untouched
        window.close()

    def test_warning_declined_keeps_candidate_and_dialog_open(self, qapp, tmp_path) -> None:
        # Same detection phrase on both items → overlap warning (not error).
        window = MainWindow(check_items=(_item("a"),))
        candidate = (_item("a"), _item("b", phrase="功能A"))

        with (
            patch(
                "PySide6.QtWidgets.QMessageBox.warning",
                return_value=QMessageBox.StandardButton.No,
            ) as mock_warning,
            patch("design_requirement_checker.application.save_baseline_to") as mock_save,
        ):
            _dialog, _unused, accepted = _save_via_dialog(window, candidate, tmp_path)

        mock_warning.assert_called_once()
        mock_save.assert_not_called()
        assert accepted == []
        assert window._check_items == (_item("a"),)
        window.close()

    def test_disk_failure_keeps_candidate_and_current_state(self, qapp, tmp_path) -> None:
        from design_requirement_checker.matching import verify

        existing = (_item("a"),)
        document = _doc_one_block()
        window = MainWindow(check_items=existing)
        window.set_document(document)
        gen0 = window.start_verification()
        window.complete_verification(gen0, verify(document, existing))
        assert len(window.results) == 1
        gen_before = window._op_generation

        candidate = (_item("a"), _item("b", phrase="功能B"))
        with patch("PySide6.QtWidgets.QMessageBox.critical"):
            _dialog, mock_save, accepted = _save_via_dialog(
                window,
                candidate,
                tmp_path,
                save_side_effect=OSError("disk full"),
            )

        mock_save.assert_called_once()
        assert accepted == []  # candidate still open
        assert window._check_items == existing  # current baseline unchanged
        assert len(window.results) == 1  # results unchanged
        assert window._op_generation == gen_before  # no invalidation
        window.close()

    def test_successful_save_publishes_and_closes_dialog(self, qapp, tmp_path) -> None:
        from design_requirement_checker.matching import verify

        existing = (_item("a"),)
        document = _doc_one_block()
        window = MainWindow(check_items=existing)
        window.set_document(document)
        gen0 = window.start_verification()
        window.complete_verification(gen0, verify(document, existing))
        assert len(window.results) == 1

        candidate = (_item("a"), _item("b", phrase="功能B"))
        # Real application+store stack against tmp_path: prove real persistence.
        _dialog, save_mock, accepted = _save_via_dialog(
            window, candidate, tmp_path, mock_save=False
        )

        assert save_mock is None
        assert accepted == [True]
        assert window._check_items == candidate  # published
        assert window.results == ()  # invalidated
        assert (tmp_path / "baseline.json").exists()  # persisted via real store
        window.close()


def _doc_one_block():
    """Minimal one-block document for verification setup."""
    from design_requirement_checker.domain import (
        BlockType,
        Coverage,
        Document,
        DocumentBlock,
        DocumentLocation,
        TextRun,
    )

    text = "功能A"
    location = DocumentLocation(
        document_id="doc-ui",
        block_id="body:p0",
        block_type=BlockType.PARAGRAPH,
        part="body",
        paragraph_index=0,
    )
    block = DocumentBlock(
        block_id="body:p0",
        block_type=BlockType.PARAGRAPH,
        text=text,
        runs=(
            TextRun(
                text=text,
                start_offset=0,
                end_offset=len(text),
                effective_strike=False,
                strike_origin="run-direct",
                strike_reason="",
            ),
        ),
        location=location,
    )
    return Document(
        document_id="doc-ui",
        filename="ui.docx",
        content_fingerprint="ui-fingerprint",
        blocks=(block,),
        coverage=Coverage.COMPLETE,
    )
