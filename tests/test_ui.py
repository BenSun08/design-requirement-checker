"""Minimal Qt presentation tests for the Task 2 vertical slice.

The window must render domain values without parsing inside widgets: block
list, one-based locations, strike formatting, LIMITED warnings, and explicit
failure — with only implemented operations enabled.
"""

import os
import threading
import time

import fixture_factory as fixtures
import pytest
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QApplication, QPushButton

from design_requirement_checker.application import (
    ImportFailure,
    VerificationOutcome,
    VerificationState,
    import_document,
)
from design_requirement_checker.domain import (
    BlockType,
    CheckItem,
    CheckResult,
    CheckStatus,
    ComparisonState,
    Coverage,
    Document,
    DocumentBlock,
    DocumentLocation,
    Resolution,
    TableCellCoordinates,
    TextRun,
)
from design_requirement_checker.ui.main_window import (
    MainWindow,
    UiState,
    format_blocks_html,
    format_location,
)


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


def _item(item_id: str = "a", phrase: str = "功能") -> CheckItem:
    return CheckItem(
        item_id=item_id,
        code=item_id.upper(),
        name=f"name-{item_id}",
        detection_phrase=phrase,
        aliases=(),
    )


def _result(
    item_id: str,
    *,
    status: CheckStatus | None,
    resolution: Resolution = Resolution.RESOLVED,
    comparison_state: ComparisonState = ComparisonState.NOT_COMPARED,
) -> CheckResult:
    return CheckResult(
        check_item=_item(item_id, "x"),
        document_id="doc-ui",
        resolution=resolution,
        status=status,
        evidence=(),
        comparison_state=comparison_state,
        comparison_reason="",
        review_reasons=(),
        rule_revision="r1",
    )


@pytest.fixture(scope="module")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    application = QApplication.instance() or QApplication([])
    yield application


class TestEnabledActions:
    def test_only_implemented_actions_are_enabled(self, qapp) -> None:
        window = MainWindow()
        enabled = [
            button.text() for button in window.findChildren(QPushButton) if button.isEnabled()
        ]
        disabled = [
            button.text() for button in window.findChildren(QPushButton) if not button.isEnabled()
        ]
        window.close()
        assert enabled == ["导入 DOCX"]
        assert "开始核查" in disabled
        assert "检查项管理" in disabled


class TestUiLifecycle:
    def test_initial_state_is_empty_with_run_disabled(self, qapp) -> None:
        window = MainWindow()
        assert window.state is UiState.EMPTY
        assert window._run_button.isEnabled() is False
        assert window._cancel_button.isEnabled() is False
        window.close()

    def test_document_ready_enables_run_only_with_check_items(self, qapp) -> None:
        no_items = MainWindow(check_items=())
        no_items.set_document(_document(_block("body:p0", "内容")))
        assert no_items.state is UiState.READY
        assert no_items._run_button.isEnabled() is False
        no_items.close()

        with_items = MainWindow(check_items=(_item(),))
        with_items.set_document(_document(_block("body:p0", "内容")))
        assert with_items.state is UiState.READY
        assert with_items._run_button.isEnabled() is True
        with_items.close()

    def test_verifying_state_disables_run_and_enables_cancel(self, qapp) -> None:
        window = MainWindow(check_items=(_item(),))
        window.set_document(_document(_block("body:p0", "内容")))
        generation = window.start_verification()
        assert generation == window._op_generation
        assert window.state is UiState.VERIFYING
        assert window._run_button.isEnabled() is False
        assert window._cancel_button.isEnabled() is True
        window.close()

    def test_complete_with_matching_generation_applies_results(self, qapp) -> None:
        from design_requirement_checker.matching import verify

        document = _document(_block("body:p0", "功能"))
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        generation = window.start_verification()
        results = verify(document, (_item(),))
        applied = window.complete_verification(generation, results)
        assert applied is True
        assert window.state is UiState.COMPLETED
        assert len(window.results) == 1
        window.close()

    def test_stale_completion_is_ignored(self, qapp) -> None:
        window = MainWindow(check_items=(_item(),))
        window.set_document(_document(_block("body:p0", "内容")))
        stale_generation = window.start_verification()
        # A newer operation (new document) invalidates the running one.
        window.set_document(_document(_block("body:p0", "其他")))
        applied = window.complete_verification(stale_generation, ())
        assert applied is False
        assert window.state is UiState.READY
        assert window.results == ()
        window.close()

    def test_cancellation_is_not_completed_and_clears_results(self, qapp) -> None:
        window = MainWindow(check_items=(_item(),))
        window.set_document(_document(_block("body:p0", "内容")))
        window.start_verification()
        window.cancel_verification()
        assert window.state is not UiState.COMPLETED
        assert window.results == ()
        assert window._cancel_button.isEnabled() is False
        window.close()

    def test_failure_is_not_completed(self, qapp) -> None:
        window = MainWindow(check_items=(_item(),))
        window.set_document(_document(_block("body:p0", "内容")))
        window.start_verification()
        window.fail_verification("boom")
        assert window.state is UiState.FAILED
        assert window.state is not UiState.COMPLETED
        assert window.results == ()
        window.close()

    def test_new_document_clears_existing_results(self, qapp) -> None:
        from design_requirement_checker.matching import verify

        document = _document(_block("body:p0", "功能"))
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        generation = window.start_verification()
        window.complete_verification(generation, verify(document, (_item(),)))
        assert window.state is UiState.COMPLETED
        window.set_document(_document(_block("body:p0", "其他")))
        assert window.state is UiState.READY
        assert window.results == ()
        window.close()


def _process_until(qapp, predicate, timeout_ms: int = 2000) -> bool:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


class TestBackgroundImport:
    def test_start_import_sets_importing_state(self, qapp) -> None:
        window = MainWindow()
        window._start_import("/fake/path.docx")
        assert window.state is UiState.IMPORTING
        assert window._import_button.isEnabled() is False
        assert window._run_button.isEnabled() is False
        assert window._cancel_button.isEnabled() is True
        window.close()

    def test_matching_generation_applies_import_success(self, qapp) -> None:
        window = MainWindow()
        window._op_generation = 5
        window._state = UiState.IMPORTING
        document = _document(_block("body:p0", "内容"))
        applied = window._on_import_finished(document, 5)
        assert applied is True
        assert window.state is UiState.READY
        window.close()

    def test_stale_import_finish_is_ignored(self, qapp) -> None:
        window = MainWindow()
        window._op_generation = 2  # current operation
        document_a = _document(_block("body:p0", "A"))
        applied = window._on_import_finished(document_a, 1)  # stale
        assert applied is False
        window.close()

    def test_import_failure_sets_failed_state(self, qapp) -> None:
        window = MainWindow()
        window._op_generation = 1
        window._state = UiState.IMPORTING
        failure = ImportFailure("broken.docx", "invalid-or-unreadable-document", "boom")
        applied = window._on_import_finished(failure, 1)
        assert applied is True
        assert window.state is UiState.FAILED
        assert window.results == ()
        window.close()

    def test_import_runs_off_ui_thread(self, qapp, tmp_path) -> None:
        path = fixtures.build_normal(tmp_path / "normal.docx")
        window = MainWindow()
        window._start_import(str(path))
        assert window.state is UiState.IMPORTING
        assert _process_until(qapp, lambda: window.state is UiState.READY)
        assert "normal.docx" in window._summary_label.text()
        window.close()

    def test_late_stale_background_import_does_not_replace_current(
        self, qapp, tmp_path, monkeypatch
    ) -> None:
        import design_requirement_checker.application as app_mod

        path_a = str(tmp_path / "a.docx")
        path_b = str(fixtures.build_normal(tmp_path / "b.docx"))
        a_release = threading.Event()

        def fake_import(path):
            if path == path_a:
                a_release.wait(timeout=5)
                return ImportFailure("a.docx", "file-access-error", "stale")
            return import_document(path)

        monkeypatch.setattr(app_mod, "import_document", fake_import)

        window = MainWindow()
        window._start_import(path_a)  # A blocks
        window._start_import(path_b)  # B completes fast
        assert _process_until(qapp, lambda: window.state is UiState.READY)
        assert "b.docx" in window._summary_label.text()
        a_release.set()  # let the stale A finish
        _process_until(qapp, lambda: True, timeout_ms=500)  # drain queued signals
        # A must not replace B.
        assert "b.docx" in window._summary_label.text()
        window.close()


def _completed_outcome(document: Document) -> VerificationOutcome:
    from design_requirement_checker.matching import verify

    results = verify(document, (_item(),))
    return VerificationOutcome(
        document_id=document.document_id,
        coverage=document.coverage,
        coverage_warnings=document.warnings,
        state=VerificationState.COMPLETED,
        results=results,
    )


class TestBackgroundVerification:
    def test_run_sets_verifying_state(self, qapp) -> None:
        window = MainWindow(check_items=(_item(),))
        window.set_document(_document(_block("body:p0", "功能")))
        window._on_run_clicked()
        assert window.state is UiState.VERIFYING
        assert window._run_button.isEnabled() is False
        assert window._cancel_button.isEnabled() is True
        window.close()

    def test_completed_verification_applied_when_current(self, qapp) -> None:
        document = _document(_block("body:p0", "功能"))
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        window._op_generation = 7
        window._state = UiState.VERIFYING
        outcome = _completed_outcome(document)
        applied = window._on_verification_finished(outcome, 7)
        assert applied is True
        assert window.state is UiState.COMPLETED
        assert len(window.results) == 1
        window.close()

    def test_stale_verification_is_ignored(self, qapp) -> None:
        document = _document(_block("body:p0", "功能"))
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        window._op_generation = 2
        outcome = _completed_outcome(document)
        applied = window._on_verification_finished(outcome, 1)
        assert applied is False
        assert window.results == ()
        window.close()

    def test_verification_for_changed_document_is_ignored(self, qapp) -> None:
        document = _document(_block("body:p0", "功能"))
        other_loc = DocumentLocation(
            document_id="other-doc",
            block_id="body:p0",
            block_type=BlockType.PARAGRAPH,
            part="body",
            paragraph_index=0,
        )
        other_block = DocumentBlock(
            block_id="body:p0",
            block_type=BlockType.PARAGRAPH,
            text="功能",
            runs=(_run("功能"),),
            location=other_loc,
        )
        other = Document(
            document_id="other-doc",
            filename="other.docx",
            content_fingerprint="other-fp",
            blocks=(other_block,),
            coverage=Coverage.COMPLETE,
        )
        window = MainWindow(check_items=(_item(),))
        window.set_document(other)  # current document is "other"
        window._op_generation = 3
        window._state = UiState.VERIFYING
        # outcome references a different document snapshot.
        stale = VerificationOutcome(
            document_id=document.document_id,
            coverage=document.coverage,
            coverage_warnings=(),
            state=VerificationState.COMPLETED,
            results=(),
        )
        applied = window._on_verification_finished(stale, 3)
        assert applied is False
        assert window.results == ()
        window.close()

    def test_cancelled_verification_has_no_results(self, qapp) -> None:
        document = _document(_block("body:p0", "功能"))
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        window._op_generation = 1
        window._state = UiState.VERIFYING
        cancelled = VerificationOutcome(
            document_id=document.document_id,
            coverage=document.coverage,
            coverage_warnings=(),
            state=VerificationState.CANCELLED,
            results=(),
        )
        applied = window._on_verification_finished(cancelled, 1)
        assert applied is True
        assert window.state is UiState.CANCELLED
        assert window.results == ()
        window.close()

    def test_verification_runs_in_background(self, qapp, tmp_path) -> None:
        document = import_document(fixtures.build_normal(tmp_path / "normal.docx"))
        window = MainWindow(check_items=(_item("a", "plain"),))
        window.set_document(document)
        window._on_run_clicked()
        assert window.state is UiState.VERIFYING
        assert _process_until(qapp, lambda: window.state is UiState.COMPLETED)
        assert len(window.results) == 1
        window.close()

    def test_cancel_then_new_run_ignores_late_first_run(self, qapp) -> None:
        document = _document(_block("body:p0", "功能"))
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        # Run 1 starts (generation 1), then is cancelled.
        window._op_generation = 1
        window._state = UiState.VERIFYING
        window._cancel_event = threading.Event()
        window._on_cancel_clicked()
        # Run 2 starts (newer generation).
        window._op_generation = 2
        window._state = UiState.VERIFYING
        # Late run-1 completion must be ignored.
        run1_outcome = VerificationOutcome(
            document_id=document.document_id,
            coverage=document.coverage,
            coverage_warnings=(),
            state=VerificationState.CANCELLED,
            results=(),
        )
        applied = window._on_verification_finished(run1_outcome, 1)
        assert applied is False
        # Run 2's completion still applies.
        run2_outcome = VerificationOutcome(
            document_id=document.document_id,
            coverage=document.coverage,
            coverage_warnings=(),
            state=VerificationState.COMPLETED,
            results=window.results,
        )
        applied2 = window._on_verification_finished(run2_outcome, 2)
        assert applied2 is True
        window.close()


class TestReviewWorkspaceShell:
    def test_workspace_has_splitter_with_result_and_detail_panels(self, qapp) -> None:
        from PySide6.QtWidgets import QListWidget, QSplitter, QTextBrowser

        window = MainWindow(check_items=(_item(),))
        splitter = window.findChild(QSplitter)
        assert splitter is not None
        assert window.findChild(QListWidget) is not None
        assert window.findChild(QTextBrowser) is not None
        window.close()

    def test_summary_and_search_strip_present(self, qapp) -> None:
        from PySide6.QtWidgets import QLineEdit

        window = MainWindow(check_items=(_item(),))
        assert window._summary_label is not None
        assert isinstance(window._search_input, QLineEdit)
        window.close()

    def test_actions_remain_after_shell_rebuild(self, qapp) -> None:
        window = MainWindow(check_items=(_item(),))
        assert window._import_button.text() == "导入 DOCX"
        assert window._run_button.text() == "开始核查"
        assert window._cancel_button.text() == "取消核查"
        assert window._manage_button.text() == "检查项管理"
        window.close()

    def test_document_still_renders_after_import(self, qapp, tmp_path) -> None:
        document = import_document(fixtures.build_normal(tmp_path / "normal.docx"))
        window = MainWindow(check_items=(_item("a", "plain"),))
        window.set_document(document)
        assert "normal.docx" in window._summary_label.text()
        # The document blocks view still exists somewhere in the workspace.
        from PySide6.QtWidgets import QTextBrowser

        browsers = window.findChildren(QTextBrowser)
        assert any(b.toHtml() for b in browsers)
        window.close()

    def test_startup_window_size_is_desktop_target(self, qapp) -> None:
        window = MainWindow()
        assert window.width() >= 1024
        assert window.height() >= 600
        window.close()


class TestSummaryAndOrdering:
    def test_summary_counts_match_domain_states(self, qapp) -> None:
        results = (
            _result("c1", status=CheckStatus.CONFIGURED),
            _result("m1", status=CheckStatus.MISSING),
            _result("s1", status=CheckStatus.STRUCK_OUT),
            _result("u1", status=None, resolution=Resolution.UNRESOLVED),
            _result("c2", status=CheckStatus.CONFIGURED),
        )
        window = MainWindow(check_items=(_item(),))
        summary = window._compute_summary(results)
        assert summary.configured == 2
        assert summary.missing == 1
        assert summary.struck_out == 1
        assert summary.unresolved == 1
        assert summary.total == 5

    def test_different_is_orthogonal_to_total(self, qapp) -> None:
        results = (
            _result(
                "c1", status=CheckStatus.CONFIGURED, comparison_state=ComparisonState.DIFFERENT
            ),
            _result("c2", status=CheckStatus.CONFIGURED, comparison_state=ComparisonState.SAME),
        )
        window = MainWindow(check_items=(_item(),))
        summary = window._compute_summary(results)
        assert summary.total == 2
        assert summary.configured == 2
        assert summary.different == 1

    def test_ordering_priority(self, qapp) -> None:
        configured_same = _result(
            "cs", status=CheckStatus.CONFIGURED, comparison_state=ComparisonState.SAME
        )
        configured_diff = _result(
            "cd", status=CheckStatus.CONFIGURED, comparison_state=ComparisonState.DIFFERENT
        )
        missing = _result("m", status=CheckStatus.MISSING)
        struck = _result("s", status=CheckStatus.STRUCK_OUT)
        unresolved = _result("u", status=None, resolution=Resolution.UNRESOLVED)
        results = (configured_same, configured_diff, missing, struck, unresolved)
        window = MainWindow(check_items=(_item(),))
        ordered = window._order_results(results)
        codes = [r.check_item.code for r in ordered]
        assert codes == ["U", "M", "S", "CD", "CS"]

    def test_original_order_preserved_within_group(self, qapp) -> None:
        a = _result("a", status=CheckStatus.CONFIGURED, comparison_state=ComparisonState.SAME)
        b = _result("b", status=CheckStatus.CONFIGURED, comparison_state=ComparisonState.SAME)
        c = _result("c", status=CheckStatus.CONFIGURED, comparison_state=ComparisonState.SAME)
        window = MainWindow(check_items=(_item(),))
        ordered = window._order_results((c, a, b))
        codes = [r.check_item.code for r in ordered]
        assert codes == ["C", "A", "B"]

    def test_summary_displayed_after_completion(self, qapp) -> None:
        from design_requirement_checker.matching import verify

        document = _document(_block("body:p0", "功能"))
        window = MainWindow(check_items=(_item("a", "功能"),))
        window.set_document(document)
        results = verify(document, (_item("a", "功能"),))
        window.complete_verification(window._op_generation, results)
        assert "全部" in window._summary_label.text()
        window.close()


class TestPureFormatting:
    def test_body_location_is_one_based(self) -> None:
        location = DocumentLocation(
            document_id="d",
            block_id="body:p2",
            block_type=BlockType.PARAGRAPH,
            part="body",
            paragraph_index=2,
        )
        assert format_location(location) == "正文 · 段3"

    def test_table_cell_location_is_one_based(self) -> None:
        location = DocumentLocation(
            document_id="d",
            block_id="t0r2c1:table-cell:p0",
            block_type=BlockType.TABLE_CELL_PARAGRAPH,
            part="table-cell",
            paragraph_index=0,
            cell=TableCellCoordinates(0, 2, 1),
        )
        assert format_location(location) == "表1 · 行3 · 单元格2 · 段1"

    def test_nested_cell_location_shows_ancestor_path(self) -> None:
        location = DocumentLocation(
            document_id="d",
            block_id="t0r2c1>t0r0c0:table-cell:p0",
            block_type=BlockType.TABLE_CELL_PARAGRAPH,
            part="table-cell",
            paragraph_index=0,
            cell=TableCellCoordinates(0, 0, 0),
            ancestor_path=(TableCellCoordinates(0, 2, 1),),
        )
        assert format_location(location) == "表1 · 行3 · 单元格2 › 表1 · 行1 · 单元格1 · 段1"

    def test_strike_and_unknown_formatting_markers(self, tmp_path) -> None:
        document = import_document(fixtures.build_strike_matrix(tmp_path / "strike.docx"))
        html = format_blocks_html(document)
        assert "图例" in html
        assert "<s>direct strike</s>" in html
        assert "<s>gone </s>" in html
        assert "〔maybe〕" in html
        assert "〔dbl〕" in html
        assert "〔orphan〕" in html

    def test_preview_preserves_meaningful_whitespace(self, tmp_path) -> None:
        # Raw block text such as "A  B\tC" must survive the HTML preview:
        # the paragraph style keeps Qt's rich-text engine from collapsing
        # runs of spaces.
        document = import_document(fixtures.build_normal(tmp_path / "normal.docx"))
        html = format_blocks_html(document)
        assert 'style="white-space: pre-wrap"' in html
        rendered = QTextDocument()
        rendered.setHtml(html)
        assert "A  B\tC" in rendered.toPlainText()

    def test_empty_document_renders_explicit_empty_state(self, tmp_path) -> None:
        document = import_document(fixtures.build_empty(tmp_path / "empty.docx"))
        html = format_blocks_html(document)
        assert "文档为空" in html


class TestWindowDisplay:
    def test_document_outcome_populates_summary_and_blocks(self, qapp, tmp_path) -> None:
        window = MainWindow()
        document = import_document(fixtures.build_normal(tmp_path / "normal.docx"))
        window.show_import_outcome(document)
        assert "normal.docx" in window._summary_label.text()
        assert "完全" in window._summary_label.text()
        assert "文本块：5" in window._summary_label.text()
        assert "plain body paragraph one" in window._detail_view.toPlainText()
        assert window._warnings_label.isHidden() is True
        window.close()

    def test_limited_outcome_shows_warnings(self, qapp, tmp_path) -> None:
        window = MainWindow()
        document = import_document(fixtures.build_excluded_parts(tmp_path / "excluded.docx"))
        window.show_import_outcome(document)
        assert "受限" in window._summary_label.text()
        assert window._warnings_label.isHidden() is False
        assert "header-content-not-checked" in window._warnings_label.text()
        window.close()

    def test_failure_outcome_shows_explicit_error(self, qapp) -> None:
        window = MainWindow()
        failure = ImportFailure(
            filename="broken.docx",
            reason="invalid-or-unreadable-document",
            detail="BadZipFile: File is not a zip file",
        )
        window.show_import_outcome(failure)
        assert "导入失败" in window._summary_label.text()
        assert "broken.docx" in window._summary_label.text()
        assert "BadZipFile" in window._detail_view.toPlainText()
        assert window._warnings_label.isHidden() is True
        window.close()

    def test_empty_document_is_distinct_from_failure(self, qapp, tmp_path) -> None:
        window = MainWindow()
        document = import_document(fixtures.build_empty(tmp_path / "empty.docx"))
        window.show_import_outcome(document)
        assert "导入失败" not in window._summary_label.text()
        assert "文本块：0" in window._summary_label.text()
        assert "文档为空" in window._detail_view.toPlainText()
        window.close()
