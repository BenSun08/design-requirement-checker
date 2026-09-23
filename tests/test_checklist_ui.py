"""Task 5 checklist-management UI regression tests.

Covers the startup baseline conditions (no-baseline / backup / load-error /
unsupported-schema), the checklist management workflows, and candidate
preservation across failed saves. No test writes to real user AppData:
persistence targets are injected via tmp_path + monkeypatched ``default_path``.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from design_requirement_checker.baseline_store import UnsupportedBaselineSchemaError
from design_requirement_checker.domain import (
    BlockType,
    CheckItem,
    CheckItemAlias,
    Coverage,
    Document,
    DocumentBlock,
    DocumentLocation,
    TextRun,
)
from design_requirement_checker.ui.main_window import MainWindow, UiState


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


class TestDuplicateAliasIdentity:
    """R5.9 — duplicate alias texts are matched occurrence-by-occurrence so
    each keeps its own alias_id and notes; editing never collapses them onto
    one object, never duplicates alias_id and never silently deduplicates."""

    @staticmethod
    def _existing_item() -> CheckItem:
        from design_requirement_checker.domain import CheckItemAlias

        return CheckItem(
            item_id="dup",
            code="DUP",
            name="dup-item",
            detection_phrase="功能A",
            aliases=(
                CheckItemAlias(alias_id="id1", text="X", notes="n1"),
                CheckItemAlias(alias_id="id2", text="X", notes="n2"),
            ),
        )

    def test_duplicate_texts_keep_distinct_identities(self, qapp) -> None:
        from design_requirement_checker.ui.item_editor_dialog import ItemEditorDialog

        dialog = ItemEditorDialog(self._existing_item())
        result = dialog._build_aliases(["X", "X"])

        assert [a.alias_id for a in result] == ["id1", "id2"]
        assert [a.notes for a in result] == ["n1", "n2"]

    def test_extra_duplicate_occurrence_gets_new_identity(self, qapp) -> None:
        from design_requirement_checker.ui.item_editor_dialog import ItemEditorDialog

        dialog = ItemEditorDialog(self._existing_item())
        result = dialog._build_aliases(["X", "X", "X"])

        assert [a.alias_id for a in result[:2]] == ["id1", "id2"]
        assert result[2].alias_id not in {"id1", "id2"}  # genuinely new alias
        assert result[2].notes == ""

    def test_removed_duplicate_occurrence_is_dropped(self, qapp) -> None:
        from design_requirement_checker.ui.item_editor_dialog import ItemEditorDialog

        dialog = ItemEditorDialog(self._existing_item())
        result = dialog._build_aliases(["X"])

        # First occurrence consumed; the removed one is gone, not merged.
        assert [a.alias_id for a in result] == ["id1"]
        assert result[0].notes == "n1"

    def test_alias_ids_stay_unique_after_edit(self, qapp) -> None:
        from design_requirement_checker.ui.item_editor_dialog import ItemEditorDialog

        dialog = ItemEditorDialog(self._existing_item())
        result = dialog._build_aliases(["X", "X", "Y"])

        ids = [a.alias_id for a in result]
        assert len(ids) == len(set(ids))  # never duplicate alias_id values


def _run(text: str, strike: bool | None = False) -> TextRun:
    return TextRun(
        text=text,
        start_offset=0,
        end_offset=len(text),
        effective_strike=strike,
        strike_origin="run-direct" if strike is not None else "default-off",
        strike_reason="" if strike is not None else "test-unknown-formatting",
    )


def _block(block_id: str, text: str) -> DocumentBlock:
    para_index = int(block_id.removeprefix("body:p"))
    location = DocumentLocation(
        document_id="doc-ui",
        block_id=block_id,
        block_type=BlockType.PARAGRAPH,
        part="body",
        paragraph_index=para_index,
    )
    return DocumentBlock(
        block_id=block_id,
        block_type=BlockType.PARAGRAPH,
        text=text,
        runs=(_run(text),),
        location=location,
    )


def _document(*blocks: DocumentBlock) -> Document:
    return Document(
        document_id="doc-ui",
        filename="ui.docx",
        content_fingerprint="ui-fingerprint",
        blocks=blocks,
        coverage=Coverage.COMPLETE,
    )


def _doc_one_block() -> Document:
    """Minimal one-block document for verification setup."""
    return _document(_block("body:p0", "功能A"))


def _with_alias(
    item: CheckItem, *, text: str = "alt-phrase", notes: str = "alias note"
) -> CheckItem:
    """Return a copy of ``item`` carrying one stable alias with given notes."""
    alias = CheckItemAlias(alias_id=uuid.uuid4().hex, text=text, notes=notes)
    return CheckItem(
        item_id=item.item_id,
        code=item.code,
        name=item.name,
        detection_phrase=item.detection_phrase,
        aliases=(alias,),
        category=item.category,
        expected_description=item.expected_description,
        enabled=item.enabled,
        notes=item.notes,
    )


class TestChecklistWorkspace:
    """Dialog-level working-copy behavior: rendering, add/edit wiring,
    disable/re-enable and confirmed delete. The dialog only mutates its own
    working copy; save/publish behavior lives in the MainWindow flow tests."""

    def test_empty_baseline_renders_zero_rows(self, qapp) -> None:
        from design_requirement_checker.ui.checklist_dialog import ChecklistDialog

        dialog = ChecklistDialog(())
        assert dialog._table.rowCount() == 0
        assert dialog._count_label.text() == "共 0 项"
        assert dialog.current_items() == ()

    def test_existing_rows_rendered(self, qapp) -> None:
        from design_requirement_checker.ui.checklist_dialog import ChecklistDialog

        dialog = ChecklistDialog((_item("a"), _item("b")))
        assert dialog._table.rowCount() == 2
        assert dialog._count_label.text() == "共 2 项"
        assert dialog._table.item(0, 0).text() == "A"  # code column
        assert dialog._table.item(0, 5).text() == "启用"

    def test_toggle_disable_and_reenable(self, qapp) -> None:
        from design_requirement_checker.ui.checklist_dialog import ChecklistDialog

        dialog = ChecklistDialog((_item("a"),))
        dialog._table.selectRow(0)
        dialog._on_toggle_enabled()
        assert dialog.current_items()[0].enabled is False
        assert dialog._table.item(0, 5).text() == "已禁用"
        dialog._on_toggle_enabled()
        assert dialog.current_items()[0].enabled is True
        assert dialog._table.item(0, 5).text() == "启用"

    def test_delete_cancel_keeps_item(self, qapp) -> None:
        from design_requirement_checker.ui.checklist_dialog import ChecklistDialog

        dialog = ChecklistDialog((_item("a"),))
        dialog._table.selectRow(0)
        with patch(
            "PySide6.QtWidgets.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            dialog._on_delete_selected()
        assert len(dialog.current_items()) == 1

    def test_delete_confirm_removes_item(self, qapp) -> None:
        from design_requirement_checker.ui.checklist_dialog import ChecklistDialog

        dialog = ChecklistDialog((_item("a"),))
        dialog._table.selectRow(0)
        with patch(
            "PySide6.QtWidgets.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            dialog._on_delete_selected()
        assert dialog.current_items() == ()

    def test_add_item_appends_with_fresh_identity(self, qapp) -> None:
        from design_requirement_checker.ui.checklist_dialog import ChecklistDialog

        dialog = ChecklistDialog((_item("a"),))
        fresh = CheckItem(
            item_id="new-id",
            code="B",
            name="name-b",
            detection_phrase="功能B",
            aliases=(),
        )
        editor = MagicMock()
        editor.exec.return_value = QDialog.DialogCode.Accepted
        editor.candidate.return_value = fresh
        with patch(
            "design_requirement_checker.ui.item_editor_dialog.ItemEditorDialog",
            return_value=editor,
        ) as mock_editor:
            dialog._on_add()

        mock_editor.assert_called_once_with(existing=None, parent=dialog)
        assert dialog.current_items() == (_item("a"), fresh)
        assert dialog._table.rowCount() == 2

    def test_edit_selected_replaces_row_keeping_identity(self, qapp) -> None:
        from design_requirement_checker.ui.checklist_dialog import ChecklistDialog

        dialog = ChecklistDialog((_item("a"),))
        edited = CheckItem(
            item_id="a",  # editor preserves the stable item_id
            code="A",
            name="renamed",
            detection_phrase="功能A",
            aliases=(),
        )
        editor = MagicMock()
        editor.exec.return_value = QDialog.DialogCode.Accepted
        editor.candidate.return_value = edited
        dialog._table.selectRow(0)
        with patch(
            "design_requirement_checker.ui.item_editor_dialog.ItemEditorDialog",
            return_value=editor,
        ) as mock_editor:
            dialog._on_edit_selected()

        assert mock_editor.call_args.kwargs["existing"] == _item("a")
        assert dialog.current_items() == (edited,)
        assert dialog._table.rowCount() == 1  # replaced, not appended

    def test_edit_cancelled_keeps_row(self, qapp) -> None:
        from design_requirement_checker.ui.checklist_dialog import ChecklistDialog

        dialog = ChecklistDialog((_item("a"),))
        editor = MagicMock()
        editor.exec.return_value = QDialog.DialogCode.Rejected
        dialog._table.selectRow(0)
        with patch(
            "design_requirement_checker.ui.item_editor_dialog.ItemEditorDialog",
            return_value=editor,
        ):
            dialog._on_edit_selected()
        assert dialog.current_items() == (_item("a"),)

    def test_close_without_save_never_calls_handler(self, qapp) -> None:
        """Closing the dialog (关闭) is not a save: the handler must stay
        untouched so the current baseline/results can never change."""
        from design_requirement_checker.ui.checklist_dialog import ChecklistDialog

        handler = MagicMock(return_value=True)
        dialog = ChecklistDialog((_item("a"),), save_handler=handler)
        dialog.reject()
        handler.assert_not_called()


class TestItemEditorFields:
    """Required-field enforcement and stable identity in the item editor."""

    def test_add_empty_code_blocks_accept(self, qapp) -> None:
        from design_requirement_checker.ui.item_editor_dialog import ItemEditorDialog

        dlg = ItemEditorDialog(existing=None)
        dlg._code_edit.setText("")
        dlg._name_edit.setText("Something")
        dlg._phrase_edit.setText("Something")
        with patch("PySide6.QtWidgets.QMessageBox.warning"):
            dlg._on_save()
        assert dlg.candidate() is None

    def test_add_empty_name_blocks_accept(self, qapp) -> None:
        from design_requirement_checker.ui.item_editor_dialog import ItemEditorDialog

        dlg = ItemEditorDialog(existing=None)
        dlg._code_edit.setText("C1")
        dlg._name_edit.setText("")
        dlg._phrase_edit.setText("Something")
        with patch("PySide6.QtWidgets.QMessageBox.warning"):
            dlg._on_save()
        assert dlg.candidate() is None

    def test_add_empty_phrase_blocks_accept(self, qapp) -> None:
        from design_requirement_checker.ui.item_editor_dialog import ItemEditorDialog

        dlg = ItemEditorDialog(existing=None)
        dlg._code_edit.setText("C1")
        dlg._name_edit.setText("N")
        dlg._phrase_edit.setText("")
        with patch("PySide6.QtWidgets.QMessageBox.warning"):
            dlg._on_save()
        assert dlg.candidate() is None

    def test_add_empty_expected_description_allowed(self, qapp) -> None:
        from design_requirement_checker.ui.item_editor_dialog import ItemEditorDialog

        dlg = ItemEditorDialog(existing=None)
        dlg._code_edit.setText("C1")
        dlg._name_edit.setText("N")
        dlg._phrase_edit.setText("P")
        dlg._expected_edit.setText("")
        dlg._on_save()
        candidate = dlg.candidate()
        assert candidate is not None
        assert candidate.expected_description == ""

    def test_edit_preserves_stable_item_id(self, qapp) -> None:
        from design_requirement_checker.ui.item_editor_dialog import ItemEditorDialog

        existing = _item("keep-id")
        dlg = ItemEditorDialog(existing=existing)
        dlg._name_edit.setText("Renamed")
        dlg._on_save()
        candidate = dlg.candidate()
        assert candidate is not None
        assert candidate.item_id == "keep-id"
        assert candidate.name == "Renamed"


class TestAliasMetadataPreservation:
    """R5.4 — _build_aliases must preserve alias_id AND notes for unchanged
    text; only genuinely new alias texts get a fresh identity."""

    def test_unchanged_alias_preserves_id_and_notes(self, qapp) -> None:
        from design_requirement_checker.ui.item_editor_dialog import ItemEditorDialog

        item = _with_alias(_item("a"), text="alt", notes="keep-me")
        dlg = ItemEditorDialog(existing=item)
        result = dlg._build_aliases(["alt"])
        assert len(result) == 1
        assert result[0].alias_id == item.aliases[0].alias_id
        assert result[0].text == "alt"
        assert result[0].notes == "keep-me"

    def test_new_alias_gets_fresh_id_and_empty_notes(self, qapp) -> None:
        from design_requirement_checker.ui.item_editor_dialog import ItemEditorDialog

        dlg = ItemEditorDialog(existing=_item("a"))  # no existing aliases
        result = dlg._build_aliases(["brand-new"])
        assert len(result) == 1
        assert result[0].text == "brand-new"
        assert result[0].notes == ""

    def test_removed_alias_is_absent(self, qapp) -> None:
        from design_requirement_checker.ui.item_editor_dialog import ItemEditorDialog

        item = _with_alias(_item("a"), text="gone", notes="x")
        dlg = ItemEditorDialog(existing=item)
        assert dlg._build_aliases([]) == ()

    def test_edit_unrelated_field_preserves_all_alias_metadata(self, qapp) -> None:
        from design_requirement_checker.ui.item_editor_dialog import ItemEditorDialog

        item = _with_alias(_item("a"), text="keep-me", notes="note-A")
        dlg = ItemEditorDialog(existing=item)
        # Re-read the alias rows exactly the way _on_save does after editing
        # only category/name — the alias metadata must come through intact.
        raw = [
            line.strip() for line in dlg._aliases_edit.toPlainText().splitlines() if line.strip()
        ]
        new_aliases = dlg._build_aliases(raw)
        assert new_aliases[0].alias_id == item.aliases[0].alias_id
        assert new_aliases[0].text == item.aliases[0].text
        assert new_aliases[0].notes == item.aliases[0].notes

    def test_two_unchanged_aliases_both_preserved(self, qapp) -> None:
        from design_requirement_checker.ui.item_editor_dialog import ItemEditorDialog

        a1 = CheckItemAlias(alias_id="alias-1", text="alt-a", notes="note-a")
        a2 = CheckItemAlias(alias_id="alias-2", text="alt-b", notes="note-b")
        item = CheckItem(
            item_id="i1",
            code="C",
            name="N",
            detection_phrase="功能A",
            aliases=(a1, a2),
        )
        dlg = ItemEditorDialog(existing=item)
        result = dlg._build_aliases(["alt-a", "alt-b"])
        assert result[0].alias_id == "alias-1"
        assert result[0].notes == "note-a"
        assert result[1].alias_id == "alias-2"
        assert result[1].notes == "note-b"


class TestManageButtonEnablement:
    """检查项管理 availability derives from the UI lifecycle state."""

    def test_enabled_when_idle(self, qapp) -> None:
        window = MainWindow(check_items=(_item("a"),))
        window._update_actions()
        assert window._manage_button.isEnabled() is True
        window.close()

    def test_disabled_during_importing(self, qapp) -> None:
        window = MainWindow(check_items=(_item("a"),))
        window._state = UiState.IMPORTING
        window._update_actions()
        assert window._manage_button.isEnabled() is False
        window.close()

    def test_disabled_during_verifying(self, qapp) -> None:
        window = MainWindow(check_items=(_item("a"),))
        window._state = UiState.VERIFYING
        window._update_actions()
        assert window._manage_button.isEnabled() is False
        window.close()


class TestManageDialogWiring:
    """_on_manage_clicked opens the real dialog wired to the real save
    handler and the current snapshot (function-local imports, so the patch
    targets the defining module)."""

    def test_manage_opens_dialog_with_handler_and_current_items(self, qapp) -> None:
        window = MainWindow(check_items=(_item("a"),))
        dialog = MagicMock()
        dialog.exec.return_value = QDialog.DialogCode.Rejected  # close, no save
        with patch(
            "design_requirement_checker.ui.checklist_dialog.ChecklistDialog",
            return_value=dialog,
        ) as mock_dialog:
            window._on_manage_clicked()

        args, kwargs = mock_dialog.call_args
        assert args[0] == (_item("a"),)
        assert kwargs["save_handler"] == window._save_baseline_snapshot
        assert kwargs["parent"] is window
        dialog.exec.assert_called_once()
        assert window._check_items == (_item("a"),)  # reject never publishes
        window.close()


class TestBaselineChangeInvalidatesStaleVerification:
    """A baseline change bumps the operation generation: results are cleared
    and a verification from the old generation can never become current."""

    def test_set_check_items_clears_results_and_bumps_gen(self, qapp) -> None:
        from design_requirement_checker.matching import verify

        window = MainWindow(check_items=(_item("a"),))
        document = _document(_block("body:p0", "功能A"))
        window.set_document(document)
        gen0 = window.start_verification()
        results = verify(document, (_item("a"),))
        window.complete_verification(gen0, results)
        assert len(window.results) == 1
        old_gen = window._op_generation

        window.set_check_items((_item("a"), _item("b", phrase="功能B")), baseline_id="new-bid")
        assert window.results == ()
        assert window._op_generation > old_gen
        assert window._baseline_id == "new-bid"
        window.close()

    def test_stale_verification_discarded_after_baseline_change(self, qapp) -> None:
        from design_requirement_checker.matching import verify

        window = MainWindow(check_items=(_item("a"),))
        document = _document(_block("body:p0", "功能A"))
        window.set_document(document)
        gen0 = window.start_verification()
        # Baseline changes mid-run — the in-flight outcome is now stale.
        window.set_check_items((_item("a"), _item("b", phrase="功能B")))
        results = verify(document, (_item("a"),))
        applied = window.complete_verification(gen0, results)
        assert applied is False
        assert window.results == ()
        window.close()
