"""Minimal Qt presentation tests for the Task 2 vertical slice.

The window must render domain values without parsing inside widgets: block
list, one-based locations, strike formatting, LIMITED warnings, and explicit
failure — with only implemented operations enabled.
"""

import threading
import time

import fixture_factory as fixtures
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QPushButton

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
    MatchEvidence,
    MatchType,
    Resolution,
    StrikeCoverage,
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


def _evidence(
    *,
    evidence_id: str = "e1",
    requirement_text: str = "2门控制增加开关门延时3s功能",
    match_type: MatchType = MatchType.EXACT,
    block_id: str = "body:p0",
) -> MatchEvidence:
    # Derive zero-based paragraph index from "body:pN" ids for one-based display.
    para_index = 0
    if block_id.startswith("body:p") and block_id[6:].isdigit():
        para_index = int(block_id[6:])
    return MatchEvidence(
        evidence_id=evidence_id,
        document_id="doc-ui",
        block_id=block_id,
        location=DocumentLocation(
            document_id="doc-ui",
            block_id=block_id,
            block_type=BlockType.PARAGRAPH,
            part="body",
            paragraph_index=para_index,
        ),
        raw_text=requirement_text,
        matched_span=(0, len(requirement_text)),
        requirement_span=(0, len(requirement_text)),
        requirement_text=requirement_text,
        matched_term=requirement_text,
        match_type=match_type,
        transformations=(),
        strike_coverage=StrikeCoverage.NONE,
    )


def _result_with_evidence(
    item_id: str,
    *,
    status: CheckStatus | None,
    comparison_state: ComparisonState = ComparisonState.SAME,
    evidence: tuple[MatchEvidence, ...] = (),
    review_reasons: tuple[str, ...] = (),
    comparison_reason: str = "",
) -> CheckResult:
    return CheckResult(
        check_item=_item(item_id, "x"),
        document_id="doc-ui",
        resolution=Resolution.RESOLVED if status is not None else Resolution.UNRESOLVED,
        status=status,
        evidence=evidence,
        comparison_state=comparison_state,
        comparison_reason=comparison_reason,
        review_reasons=review_reasons,
        rule_revision="r1",
        primary_evidence_id=evidence[0].evidence_id if evidence else "",
    )


class TestEnabledActions:
    _FILTERS = {"全部", "已配置", "未配置", "已划除", "待人工核查", "仅异常"}

    def test_only_implemented_actions_are_enabled(self, qapp) -> None:
        window = MainWindow()
        buttons = window.findChildren(QPushButton)
        enabled = [b.text() for b in buttons if b.isEnabled() and b.text() not in self._FILTERS]
        disabled = [
            b.text() for b in buttons if not b.isEnabled() and b.text() not in self._FILTERS
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
        # Cancel is not offered during import (no cooperative cancellation).
        assert window._cancel_button.isEnabled() is False
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
        thread_a = window._thread
        # Let A's worker reach a_release.wait() so set() actually wakes it.
        time.sleep(0.2)
        qapp.processEvents()
        window._start_import(path_b)  # B completes fast
        assert _process_until(qapp, lambda: window.state is UiState.READY)
        assert "b.docx" in window._summary_label.text()
        a_release.set()  # let the stale A finish
        _process_until(qapp, lambda: True, timeout_ms=500)  # drain queued signals
        # A must not replace B.
        assert "b.docx" in window._summary_label.text()
        # Wait for A's thread to exit so close() doesn't leave it running.
        thread_a.quit()
        deadline = time.time() + 3.0
        while thread_a.isRunning() and time.time() < deadline:
            qapp.processEvents()
            time.sleep(0.01)
        qapp.processEvents()
        window.close()

    def test_stale_import_does_not_clear_current_thread_refs(
        self, qapp, tmp_path, monkeypatch
    ) -> None:
        from PySide6.QtCore import QThread

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
        thread_a = window._thread
        # Let A's worker reach a_release.wait() so set() actually wakes it.
        time.sleep(0.2)
        qapp.processEvents()
        window._start_import(path_b)  # B completes fast; replaces current refs
        assert _process_until(qapp, lambda: window.state is UiState.READY)
        # B's normal completion clears the current refs.
        assert window._thread is None
        a_release.set()  # let the stale A finish
        _process_until(qapp, lambda: True, timeout_ms=800)  # drain queued signals
        # Stale A must not have overwritten B's document.
        assert "b.docx" in window._summary_label.text()
        # A's worker has finished and (via direct connection) quit its thread.
        # Wait for the thread to actually exit before removing its reference.
        thread_a.quit()
        deadline = time.time() + 3.0
        while thread_a.isRunning() and time.time() < deadline:
            qapp.processEvents()
            time.sleep(0.01)
        assert not thread_a.isRunning()
        qapp.processEvents()  # drain thread.finished -> _on_thread_finished

        # Simulate a newer operation holding the current thread/worker refs.
        newer_thread = QThread()
        window._thread = newer_thread
        window._worker = object()
        window._op_generation = 99
        # A late A finish with a stale generation must not clear current refs
        # and must return False.
        a_failure = ImportFailure("a.docx", "file-access-error", "stale")
        applied = window._on_import_finished(a_failure, 1)
        assert applied is False
        assert window._thread is newer_thread
        # A's thread was already removed by its finished signal.
        assert thread_a not in window._active_threads
        window.close()

    def test_on_thread_finished_removes_exact_thread(self, qapp) -> None:
        from PySide6.QtCore import QThread

        window = MainWindow()
        t1 = QThread()
        t2 = QThread()
        window._active_threads = [t1, t2]
        window._on_thread_finished(t1)
        assert window._active_threads == [t2]
        window._on_thread_finished(t2)
        assert window._active_threads == []
        # A thread not in the set is a no-op.
        window._on_thread_finished(t1)
        assert window._active_threads == []
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


class TestWorkerFailure:
    def test_import_worker_emits_failed_on_exception(self, qapp, monkeypatch) -> None:
        import design_requirement_checker.application as app_mod

        def boom(_path):
            raise RuntimeError("parser exploded")

        monkeypatch.setattr(app_mod, "import_document", boom)
        from design_requirement_checker.ui.workers import ImportWorker

        worker = ImportWorker("/fake.docx", 3)
        received: list[tuple[str, str, int]] = []
        worker.failed.connect(lambda c, d, g: received.append((c, d, g)))
        worker.run()
        assert len(received) == 1
        category, detail, generation = received[0]
        assert category == "import-error"
        assert "parser exploded" in detail
        assert generation == 3
        # Full traceback must not leak into the detail string.
        assert "Traceback" not in detail

    def test_verification_worker_emits_failed_on_exception(self, qapp, monkeypatch) -> None:
        import design_requirement_checker.application as app_mod

        def boom(_doc, _items, cancel_check=None):
            raise RuntimeError("matcher exploded")

        monkeypatch.setattr(app_mod, "verify_document", boom)
        from design_requirement_checker.ui.workers import VerificationWorker

        document = _document(_block("body:p0", "功能"))
        cancel = threading.Event()
        worker = VerificationWorker(document, (_item(),), cancel, 5)
        received: list[tuple[str, str, int]] = []
        worker.failed.connect(lambda c, d, g: received.append((c, d, g)))
        worker.run()
        assert len(received) == 1
        category, detail, generation = received[0]
        assert category == "verification-error"
        assert "matcher exploded" in detail
        assert generation == 5
        assert "Traceback" not in detail

    def test_import_exception_drives_ui_failed_state(self, qapp, monkeypatch) -> None:
        import design_requirement_checker.application as app_mod

        def boom(_path):
            raise RuntimeError("cannot read")

        monkeypatch.setattr(app_mod, "import_document", boom)
        window = MainWindow()
        window._start_import("/fake.docx")
        assert _process_until(qapp, lambda: window.state is UiState.FAILED)
        assert window._progress.isVisible() is False
        assert window.results == ()
        # Thread must have terminated (no longer running).
        assert window._thread is None or not window._thread.isRunning()
        window.close()

    def test_verification_exception_drives_ui_failed_state(self, qapp, monkeypatch) -> None:
        import design_requirement_checker.application as app_mod

        def boom(_doc, _items, cancel_check=None):
            raise RuntimeError("matcher broken")

        monkeypatch.setattr(app_mod, "verify_document", boom)
        document = _document(_block("body:p0", "功能"))
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        window._on_run_clicked()
        assert _process_until(qapp, lambda: window.state is UiState.FAILED)
        assert window._progress.isVisible() is False
        assert window.results == ()
        assert window._thread is None or not window._thread.isRunning()
        window.close()

    def test_import_failure_is_not_treated_as_worker_exception(self, qapp) -> None:
        """An expected ImportFailure stays on the normal finished path."""
        window = MainWindow()
        window._op_generation = 1
        window._state = UiState.IMPORTING
        failure = ImportFailure("broken.docx", "file-access-error", "denied")
        applied = window._on_import_finished(failure, 1)
        assert applied is True
        assert window.state is UiState.FAILED
        window.close()


class TestDeferredClose:
    """close must never be accepted while any QThread is still running."""

    def test_long_running_import_defers_close_until_thread_finishes(
        self, qapp, tmp_path, monkeypatch
    ) -> None:
        """Section A: close during a blocking import must be deferred."""
        import design_requirement_checker.application as app_mod

        path_a = str(tmp_path / "a.docx")
        release = threading.Event()

        def fake_import(path):
            if path == path_a:
                release.wait(timeout=5)
                return import_document(path)
            return import_document(path)

        monkeypatch.setattr(app_mod, "import_document", fake_import)

        window = MainWindow()
        window.show()
        window._start_import(path_a)
        thread = window._thread
        assert thread is not None
        # Let the worker actually enter import_document before testing close.
        time.sleep(0.1)
        qapp.processEvents()
        assert thread.isRunning()

        # FIRST close attempt: must be ignored because thread is running.
        window.close()
        assert window.isVisible(), "window must stay alive while thread runs"
        assert window._close_requested is True
        assert thread in window._active_threads

        # Release the import and let its thread finish via direct-connection quit.
        release.set()
        # Wait for thread exit with GIL-releasing poll.
        deadline = time.time() + 5.0
        while thread.isRunning() and time.time() < deadline:
            qapp.processEvents()
            time.sleep(0.02)
        assert not thread.isRunning()
        # Drain thread.finished which triggers _on_thread_finished → deferred close retry.
        assert _process_until(qapp, lambda: not window.isVisible(), timeout_ms=2000)
        assert window._active_threads == []

    def test_close_during_verification_sets_cancel_and_defers(self, qapp, monkeypatch) -> None:
        """Section B: close during verification sets cooperative cancel and
        defers the actual close until the worker terminates."""
        import design_requirement_checker.application as app_mod

        release = threading.Event()

        def fake_verify(doc, items, cancel_check=None):
            # Cooperative: check cancel each tick.
            for _ in range(20):
                if cancel_check is not None and cancel_check():
                    break
                time.sleep(0.05)
            else:
                release.wait(timeout=5)
            from design_requirement_checker.matching import _completed_outcome

            return _completed_outcome(doc)

        monkeypatch.setattr(app_mod, "verify_document", fake_verify)

        document = _document(_block("body:p0", "功能"))
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        window.show()
        window._on_run_clicked()
        thread = window._thread
        assert thread is not None
        time.sleep(0.1)
        qapp.processEvents()
        assert thread.isRunning()

        FIRST_CANCEL_EVENT = window._cancel_event

        window.close()
        assert window.isVisible(), "window must defer close while thread runs"
        # Cooperative cancellation was set before quit.
        assert FIRST_CANCEL_EVENT.is_set()
        assert window._close_requested is True

        # Worker should see cancel and exit promptly without needing release.
        assert _process_until(qapp, lambda: not window.isVisible(), timeout_ms=4000)
        assert window._active_threads == []
        assert thread not in window._thread_for_generation.values()

    def test_close_without_running_workers_accepts_immediately(self, qapp) -> None:
        """Section C: close with no active workers behaves normally."""
        window = MainWindow()
        window.show()
        window.close()
        assert not window.isVisible()
        # Close request was set; that's fine for a window being torn down.
        assert window._close_requested is True

    def test_last_running_thread_triggers_final_close(self, qapp) -> None:
        """Section D: with two owned threads where only one remains running,
        the window stays pending-close until that last thread exits."""
        from PySide6.QtCore import QThread

        window = MainWindow()
        window.show()

        # Simulate two owned threads, one finished, one still running.
        t_done = QThread()
        t_done.start()
        t_done.quit()
        assert t_done.wait(2000)
        # Clean up the finished thread's bookkeeping as if its handler ran.
        window._on_thread_finished(t_done)

        t_alive = QThread()
        t_alive.start()
        t_alive.finished.connect(lambda th=t_alive: window._on_thread_finished(th))
        window._active_threads = [t_alive]
        window._close_requested = True

        # closeEvent should ignore because t_alive is still running.
        window.close()
        assert window.isVisible()
        assert t_alive.isRunning()

        # Now t_alive finishes; its finished signal fires _on_thread_finished.
        t_alive.quit()
        assert t_alive.wait(2000)
        qapp.processEvents()
        # With no threads left and close_requested, the deferred retry should
        # accept and the window disappears.
        assert _process_until(qapp, lambda: not window.isVisible(), timeout_ms=2000)

    def test_final_cleanup_removes_thread_from_all_ownership_structures(
        self, qapp, tmp_path, monkeypatch
    ) -> None:
        """Section E: after final worker completion, no ownership structure
        holds a reference to the finished thread."""
        import design_requirement_checker.application as app_mod

        path_a = str(tmp_path / "a.docx")
        release = threading.Event()

        def fake_import(path):
            if path == path_a:
                release.wait(timeout=5)
                return import_document(path)
            return import_document(path)

        monkeypatch.setattr(app_mod, "import_document", fake_import)

        window = MainWindow()
        window._start_import(path_a)
        thread = window._thread
        assert thread is not None
        gen = [g for g, t in window._thread_for_generation.items() if t is thread]
        assert gen, "thread must be registered in _thread_for_generation"

        # Trigger close request while still running.
        window.show()
        window.close()
        assert window._close_requested is True

        # Finish the worker, let close retry.
        release.set()
        deadline = time.time() + 5.0
        while thread.isRunning() and time.time() < deadline:
            qapp.processEvents()
            time.sleep(0.02)
        assert not thread.isRunning()
        assert _process_until(qapp, lambda: not window.isVisible(), timeout_ms=2000)

        # All ownership structures must be clean for this thread.
        assert thread not in window._active_threads
        assert thread not in window._thread_for_generation.values()
        assert window._thread_for_generation == {}
        assert window._active_threads == []


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


def _window_with_results(qapp, results):
    window = MainWindow(check_items=(_item(),))
    window.set_document(_document(_block("body:p0", "x")))
    window._results = results
    window._state = UiState.COMPLETED
    window._populate_results()
    window._update_summary()
    return window


class TestFiltersAndSearch:
    def _results(self):
        return (
            _result("cfg", status=CheckStatus.CONFIGURED, comparison_state=ComparisonState.SAME),
            _result(
                "cfg-diff",
                status=CheckStatus.CONFIGURED,
                comparison_state=ComparisonState.DIFFERENT,
            ),
            _result("miss", status=CheckStatus.MISSING),
            _result("struck", status=CheckStatus.STRUCK_OUT),
            _result("unres", status=None, resolution=Resolution.UNRESOLVED),
        )

    def test_all_filter_shows_everything(self, qapp) -> None:
        window = _window_with_results(qapp, self._results())
        window._set_filter("全部")
        assert window._result_list.count() == 5
        window.close()

    def test_configured_filter(self, qapp) -> None:
        window = _window_with_results(qapp, self._results())
        window._set_filter("已配置")
        assert window._result_list.count() == 2
        window.close()

    def test_missing_filter(self, qapp) -> None:
        window = _window_with_results(qapp, self._results())
        window._set_filter("未配置")
        assert window._result_list.count() == 1
        window.close()

    def test_struck_out_filter(self, qapp) -> None:
        window = _window_with_results(qapp, self._results())
        window._set_filter("已划除")
        assert window._result_list.count() == 1
        window.close()

    def test_unresolved_filter(self, qapp) -> None:
        window = _window_with_results(qapp, self._results())
        window._set_filter("待人工核查")
        assert window._result_list.count() == 1
        window.close()

    def test_exception_filter_includes_abnormal_only(self, qapp) -> None:
        window = _window_with_results(qapp, self._results())
        window._set_filter("仅异常")
        # MISSING, STRUCK_OUT, UNRESOLVED, CONFIGURED+DIFFERENT → 4
        assert window._result_list.count() == 4
        window.close()

    def test_result_rows_expose_status_and_difference(self, qapp) -> None:
        window = _window_with_results(qapp, self._results())
        texts = [window._result_list.item(i).text() for i in range(window._result_list.count())]
        # Each row contains code, name, and a readable status.
        joined = " | ".join(texts)
        assert "CFG" in joined and "已配置" in joined
        assert "MISS" in joined and "未配置" in joined
        assert "STRUCK" in joined and "已划除" in joined
        assert "UNRES" in joined and "待人工核查" in joined
        # The DIFFERENT result appends the difference hint.
        diff_row = next(t for t in texts if "CFG-DIFF" in t)
        assert "已配置" in diff_row
        assert "描述有差异" in diff_row
        # A non-different configured row must NOT carry the difference hint.
        same_row = next(t for t in texts if t.startswith("CFG") and "DIFF" not in t)
        assert "描述有差异" not in same_row
        window.close()

    def test_summary_stays_stable_while_filtering(self, qapp) -> None:
        window = _window_with_results(qapp, self._results())
        before = window._summary_label.text()
        window._set_filter("未配置")
        assert window._summary_label.text() == before
        window.close()

    def test_search_matches_code_name_category_expected(self, qapp) -> None:
        results = (
            _result("alpha", status=CheckStatus.CONFIGURED),
            _result("beta", status=CheckStatus.MISSING),
        )
        # Give the alpha item a category and expected description.
        results = (
            CheckResult(
                check_item=CheckItem(
                    item_id="alpha",
                    code="ALPHA",
                    name="alpha-name",
                    detection_phrase="x",
                    category="cat-alpha",
                    expected_description="door-delay",
                ),
                document_id="doc-ui",
                resolution=Resolution.RESOLVED,
                status=CheckStatus.CONFIGURED,
                evidence=(),
                comparison_state=ComparisonState.SAME,
                comparison_reason="",
                review_reasons=(),
                rule_revision="r1",
            ),
            _result("beta", status=CheckStatus.MISSING),
        )
        window = _window_with_results(qapp, results)
        window._search_input.setText("cat-alpha")
        assert window._result_list.count() == 1
        window._search_input.setText("door-delay")
        assert window._result_list.count() == 1
        window._search_input.setText("beta")
        assert window._result_list.count() == 1
        window.close()

    def test_no_visible_results_shows_empty_state(self, qapp) -> None:
        window = _window_with_results(qapp, self._results())
        window._search_input.setText("zzz-no-match")
        assert window._result_list.count() == 1
        assert "无匹配" in window._result_list.item(0).text()
        window.close()

    def test_clear_search_resets(self, qapp) -> None:
        window = _window_with_results(qapp, self._results())
        window._search_input.setText("zzz")
        assert window._result_list.count() == 1
        window._search_input.clear()
        assert window._result_list.count() == 5
        window.close()


class TestResultDetail:
    def test_detail_shows_code_name_category(self, qapp) -> None:
        item = CheckItem(
            item_id="a",
            code="R-001",
            name="门控延时",
            detection_phrase="x",
            category="门禁",
            expected_description="2门控制增加开关门延时2s功能",
        )
        result = CheckResult(
            check_item=item,
            document_id="doc-ui",
            resolution=Resolution.RESOLVED,
            status=CheckStatus.CONFIGURED,
            evidence=(_evidence(),),
            comparison_state=ComparisonState.SAME,
            comparison_reason="",
            review_reasons=(),
            rule_revision="r1",
            primary_evidence_id="e1",
        )
        window = MainWindow(check_items=(_item(),))
        window._show_detail(result)
        text = window._detail_view.toPlainText()
        assert "R-001" in text
        assert "门控延时" in text
        assert "门禁" in text
        window.close()

    def test_status_mapping_configured(self, qapp) -> None:
        result = _result_with_evidence("a", status=CheckStatus.CONFIGURED, evidence=(_evidence(),))
        window = MainWindow(check_items=(_item(),))
        window._show_detail(result)
        assert "已配置" in window._detail_view.toPlainText()
        window.close()

    def test_status_mapping_missing(self, qapp) -> None:
        result = _result("m", status=CheckStatus.MISSING)
        window = MainWindow(check_items=(_item(),))
        window._show_detail(result)
        assert "未配置" in window._detail_view.toPlainText()
        window.close()

    def test_status_mapping_struck_out(self, qapp) -> None:
        result = _result_with_evidence("s", status=CheckStatus.STRUCK_OUT, evidence=(_evidence(),))
        window = MainWindow(check_items=(_item(),))
        window._show_detail(result)
        assert "已划除" in window._detail_view.toPlainText()
        window.close()

    def test_status_mapping_unresolved(self, qapp) -> None:
        result = _result("u", status=None, resolution=Resolution.UNRESOLVED)
        window = MainWindow(check_items=(_item(),))
        window._show_detail(result)
        assert "待人工核查" in window._detail_view.toPlainText()
        window.close()

    def test_comparison_state_mappings(self, qapp) -> None:
        window = MainWindow(check_items=(_item(),))
        diff = _result_with_evidence(
            "d",
            status=CheckStatus.CONFIGURED,
            comparison_state=ComparisonState.DIFFERENT,
            evidence=(_evidence(),),
        )
        window._show_detail(diff)
        assert "描述有差异" in window._detail_view.toPlainText()
        nc = _result_with_evidence(
            "n",
            status=CheckStatus.CONFIGURED,
            comparison_state=ComparisonState.NOT_COMPARED,
            evidence=(_evidence(),),
        )
        window._show_detail(nc)
        assert "未比较描述" in window._detail_view.toPlainText()
        window.close()

    def test_comparison_reason_tokens_are_localized(self, qapp) -> None:
        tokens = {
            "expected-description-empty": "未设置期望描述",
            "nothing-to-compare": "没有可比较的实际需求",
            "evidence-struck": "匹配证据已被划除",
            "result-unresolved": "核查结果存在不确定项",
            "requirement-span-association-uncertain": "无法可靠确定需求描述范围",
            "no-associated-requirement-content": "未找到与检测短语关联的需求内容",
            "mixed-comparison-occurrences": "多处证据的描述比较结果不一致",
        }
        window = MainWindow(check_items=(_item(),))
        for token, label in tokens.items():
            result = _result_with_evidence(
                "r",
                status=CheckStatus.CONFIGURED,
                comparison_state=ComparisonState.DIFFERENT,
                evidence=(_evidence(),),
                comparison_reason=token,
            )
            window._show_detail(result)
            text = window._detail_view.toPlainText()
            assert label in text
            # Raw stable token must not leak into the UI text.
            assert token not in text
        window.close()

    def test_expected_and_actual_text_shown(self, qapp) -> None:
        item = CheckItem(
            item_id="a",
            code="A",
            name="n",
            detection_phrase="x",
            expected_description="2门控制增加开关门延时2s功能",
        )
        ev = _evidence(requirement_text="2门控制增加开关门延时3s功能")
        result = CheckResult(
            check_item=item,
            document_id="doc-ui",
            resolution=Resolution.RESOLVED,
            status=CheckStatus.CONFIGURED,
            evidence=(ev,),
            comparison_state=ComparisonState.DIFFERENT,
            comparison_reason="delay differs",
            review_reasons=(),
            rule_revision="r1",
            primary_evidence_id="e1",
        )
        window = MainWindow(check_items=(_item(),))
        window._show_detail(result)
        text = window._detail_view.toPlainText()
        assert "2门控制增加开关门延时2s功能" in text
        assert "2门控制增加开关门延时3s功能" in text
        window.close()

    def test_match_method_label(self, qapp) -> None:
        result = _result_with_evidence(
            "a",
            status=CheckStatus.CONFIGURED,
            evidence=(_evidence(match_type=MatchType.NORMALIZED),),
        )
        window = MainWindow(check_items=(_item(),))
        window._show_detail(result)
        assert "规范化匹配" in window._detail_view.toPlainText()
        window.close()

    def test_never_shows_passed_or_confidence(self, qapp) -> None:
        result = _result_with_evidence("a", status=CheckStatus.CONFIGURED, evidence=(_evidence(),))
        window = MainWindow(check_items=(_item(),))
        window._show_detail(result)
        text = window._detail_view.toPlainText().lower()
        assert "pass" not in text
        assert "通过" not in window._detail_view.toPlainText()
        assert "confidence" not in text
        window.close()

    def test_unresolved_reason_tokens_mapped_to_chinese(self, qapp) -> None:
        result = _result_with_evidence(
            "u",
            status=None,
            review_reasons=("partial-strike", "ambiguous-function-identity"),
        )
        window = MainWindow(check_items=(_item(),))
        window._show_detail(result)
        text = window._detail_view.toPlainText()
        assert "partial-strike" not in text
        assert "ambiguous-function-identity" not in text
        # Chinese mapped text should appear (at least non-empty reason text).
        assert "核查原因" in text
        window.close()


class TestStatusSpecificPresentation:
    def test_missing_shows_scoped_message_and_no_fake_actual(self, qapp) -> None:
        result = _result("m", status=CheckStatus.MISSING)
        window = MainWindow(check_items=(_item(),))
        window._show_detail(result)
        text = window._detail_view.toPlainText()
        assert "在已检查范围内未找到匹配证据" in text
        assert "实际需求" not in text
        assert "匹配方式" not in text
        window.close()

    def test_struck_out_shows_textual_state_and_strike(self, qapp) -> None:
        result = _result_with_evidence(
            "s",
            status=CheckStatus.STRUCK_OUT,
            evidence=(_evidence(requirement_text="门控延时功能"),),
        )
        window = MainWindow(check_items=(_item(),))
        window._show_detail(result)
        text = window._detail_view.toPlainText()
        html = window._detail_view.toHtml()
        assert "已划除" in text
        assert "门控延时功能" in text
        assert "line-through" in html
        window.close()

    def test_not_compared_shows_reason_not_same_or_different(self, qapp) -> None:
        result = _result_with_evidence(
            "n",
            status=CheckStatus.CONFIGURED,
            comparison_state=ComparisonState.NOT_COMPARED,
            evidence=(_evidence(),),
            comparison_reason="no-parameter-overlap",
        )
        window = MainWindow(check_items=(_item(),))
        window._show_detail(result)
        text = window._detail_view.toPlainText()
        assert "未比较描述" in text
        assert "no-parameter-overlap" in text
        assert "描述一致" not in text
        assert "描述有差异" not in text
        window.close()


class TestMultiEvidence:
    def test_evidence_selector_shows_all_occurrences(self, qapp) -> None:
        ev1 = _evidence(evidence_id="e1", requirement_text="第一处需求")
        ev2 = _evidence(evidence_id="e2", requirement_text="第二处需求")
        result = _result_with_evidence(
            "a",
            status=CheckStatus.CONFIGURED,
            evidence=(ev1, ev2),
        )
        window = MainWindow(check_items=(_item(),))
        window._show_detail(result)
        text = window._detail_view.toPlainText()
        assert "证据 1" in text
        assert "证据 2" in text
        window.close()

    def test_selecting_evidence_updates_actual_text(self, qapp) -> None:
        ev1 = _evidence(evidence_id="e1", requirement_text="第一处需求")
        ev2 = _evidence(evidence_id="e2", requirement_text="第二处需求")
        result = _result_with_evidence(
            "a",
            status=CheckStatus.CONFIGURED,
            evidence=(ev1, ev2),
        )
        window = MainWindow(check_items=(_item(),))
        window._show_detail(result)
        assert "第一处需求" in window._detail_view.toPlainText()
        window._select_evidence(1)
        text = window._detail_view.toPlainText()
        assert "第二处需求" in text
        assert "第一处需求" not in text
        window.close()

    def test_match_method_label_per_evidence(self, qapp) -> None:
        ev1 = _evidence(evidence_id="e1", match_type=MatchType.EXACT)
        ev2 = _evidence(evidence_id="e2", match_type=MatchType.ALIAS)
        result = _result_with_evidence(
            "a",
            status=CheckStatus.CONFIGURED,
            evidence=(ev1, ev2),
        )
        window = MainWindow(check_items=(_item(),))
        window._show_detail(result)
        assert "精确匹配" in window._detail_view.toPlainText()
        window._select_evidence(1)
        assert "别名匹配" in window._detail_view.toPlainText()
        window.close()

    def test_evidence_location_shown(self, qapp) -> None:
        ev = _evidence(evidence_id="e1", block_id="body:p3")
        result = _result_with_evidence(
            "a",
            status=CheckStatus.CONFIGURED,
            evidence=(ev,),
        )
        window = MainWindow(check_items=(_item(),))
        window._show_detail(result)
        assert "段4" in window._detail_view.toPlainText()
        window.close()

    def test_no_confidence_score_in_detail(self, qapp) -> None:
        ev = _evidence()
        result = _result_with_evidence(
            "a",
            status=CheckStatus.CONFIGURED,
            evidence=(ev,),
        )
        window = MainWindow(check_items=(_item(),))
        window._show_detail(result)
        text = window._detail_view.toPlainText().lower()
        assert "confidence" not in text
        assert "%" not in window._detail_view.toPlainText()
        window.close()


class TestSourceContext:
    def _doc_with_three_blocks(self):
        return Document(
            document_id="doc-ui",
            filename="ui.docx",
            content_fingerprint="fp",
            blocks=(
                _block("body:p0", "前文段落"),
                _block("body:p1", "门控延时功能已配置"),
                _block("body:p2", "后文段落"),
            ),
            coverage=Coverage.COMPLETE,
        )

    def test_context_shows_prev_current_next_blocks(self, qapp) -> None:
        document = self._doc_with_three_blocks()
        ev = MatchEvidence(
            evidence_id="e1",
            document_id="doc-ui",
            block_id="body:p1",
            location=DocumentLocation(
                document_id="doc-ui",
                block_id="body:p1",
                block_type=BlockType.PARAGRAPH,
                part="body",
                paragraph_index=1,
            ),
            raw_text="门控延时功能已配置",
            matched_span=(0, 6),
            requirement_span=(0, 6),
            requirement_text="门控延时",
            matched_term="门控延时",
            match_type=MatchType.EXACT,
            transformations=(),
            strike_coverage=StrikeCoverage.NONE,
        )
        result = _result_with_evidence("a", status=CheckStatus.CONFIGURED, evidence=(ev,))
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        window._show_detail(result)
        text = window._detail_view.toPlainText()
        assert "前文段落" in text
        assert "门控延时功能已配置" in text
        assert "后文段落" in text
        window.close()

    def test_current_block_location_is_one_based(self, qapp) -> None:
        document = self._doc_with_three_blocks()
        ev = MatchEvidence(
            evidence_id="e1",
            document_id="doc-ui",
            block_id="body:p1",
            location=DocumentLocation(
                document_id="doc-ui",
                block_id="body:p1",
                block_type=BlockType.PARAGRAPH,
                part="body",
                paragraph_index=1,
            ),
            raw_text="门控延时功能已配置",
            matched_span=(0, 6),
            requirement_span=(0, 6),
            requirement_text="门控延时",
            matched_term="门控延时",
            match_type=MatchType.EXACT,
            transformations=(),
            strike_coverage=StrikeCoverage.NONE,
        )
        result = _result_with_evidence("a", status=CheckStatus.CONFIGURED, evidence=(ev,))
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        window._show_detail(result)
        assert "段2" in window._detail_view.toPlainText()
        window.close()

    def test_requirement_span_highlighted(self, qapp) -> None:
        document = self._doc_with_three_blocks()
        ev = MatchEvidence(
            evidence_id="e1",
            document_id="doc-ui",
            block_id="body:p1",
            location=DocumentLocation(
                document_id="doc-ui",
                block_id="body:p1",
                block_type=BlockType.PARAGRAPH,
                part="body",
                paragraph_index=1,
            ),
            raw_text="门控延时功能已配置",
            matched_span=(0, 4),
            requirement_span=(0, 4),
            requirement_text="门控延时",
            matched_term="门控延时",
            match_type=MatchType.EXACT,
            transformations=(),
            strike_coverage=StrikeCoverage.NONE,
        )
        result = _result_with_evidence("a", status=CheckStatus.CONFIGURED, evidence=(ev,))
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        window._show_detail(result)
        html = window._detail_view.toHtml()
        assert "background" in html or "mark" in html
        window.close()

    def test_missing_has_no_source_context(self, qapp) -> None:
        document = self._doc_with_three_blocks()
        result = _result("m", status=CheckStatus.MISSING)
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        window._show_detail(result)
        text = window._detail_view.toPlainText()
        assert "前文段落" not in text
        assert "后文段落" not in text
        window.close()


class TestLimitedCoverage:
    def _limited_doc(self):
        return Document(
            document_id="doc-ui",
            filename="ui.docx",
            content_fingerprint="fp",
            blocks=(_block("body:p0", "功能"),),
            coverage=Coverage.LIMITED,
            warnings=("页眉未解析",),
        )

    def test_limited_notice_visible_with_completed_results(self, qapp) -> None:
        document = self._limited_doc()
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        results = (
            _result_with_evidence("a", status=CheckStatus.CONFIGURED, evidence=(_evidence(),)),
        )
        window.complete_verification(window._op_generation, results)
        assert window._warnings_label.isHidden() is False
        assert "检查范围受限" in window._warnings_label.text()
        window.close()

    def test_limited_notice_visible_with_missing(self, qapp) -> None:
        document = self._limited_doc()
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        missing = _result("m", status=CheckStatus.MISSING)
        window.complete_verification(window._op_generation, (missing,))
        window._show_detail(missing)
        assert window._warnings_label.isHidden() is False
        assert "在已检查范围内" in window._detail_view.toPlainText()
        window.close()

    def test_filters_do_not_hide_coverage_notice(self, qapp) -> None:
        document = self._limited_doc()
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        results = (
            _result_with_evidence("a", status=CheckStatus.CONFIGURED, evidence=(_evidence(),)),
        )
        window.complete_verification(window._op_generation, results)
        window._set_filter("仅异常")
        assert window._warnings_label.isHidden() is False
        window.close()

    def test_detail_navigation_does_not_hide_coverage_notice(self, qapp) -> None:
        document = self._limited_doc()
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        ev1 = _evidence(evidence_id="e1")
        ev2 = _evidence(evidence_id="e2", requirement_text="第二处")
        results = (_result_with_evidence("a", status=CheckStatus.CONFIGURED, evidence=(ev1, ev2)),)
        window.complete_verification(window._op_generation, results)
        window._show_detail(results[0])
        window._select_evidence(1)
        assert window._warnings_label.isHidden() is False
        window.close()


class TestKeyboardNavigation:
    def test_down_arrow_moves_selection(self, qapp) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        document = _document(_block("body:p0", "x"))
        results = (
            _result_with_evidence("a", status=CheckStatus.CONFIGURED, evidence=(_evidence(),)),
            _result_with_evidence("b", status=CheckStatus.MISSING),
            _result_with_evidence("c", status=CheckStatus.STRUCK_OUT, evidence=(_evidence(),)),
        )
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        window.complete_verification(window._op_generation, results)
        window._result_list.setCurrentRow(0)
        QTest.keyClick(window._result_list, Qt.Key_Down)
        assert window._result_list.currentRow() == 1
        window.close()

    def test_up_arrow_moves_selection(self, qapp) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        document = _document(_block("body:p0", "x"))
        results = (
            _result_with_evidence("a", status=CheckStatus.CONFIGURED, evidence=(_evidence(),)),
            _result_with_evidence("b", status=CheckStatus.MISSING),
        )
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        window.complete_verification(window._op_generation, results)
        window._result_list.setCurrentRow(1)
        QTest.keyClick(window._result_list, Qt.Key_Up)
        assert window._result_list.currentRow() == 0
        window.close()

    def test_enter_activates_result(self, qapp) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        document = _document(_block("body:p0", "x"))
        results = (
            _result_with_evidence("a", status=CheckStatus.CONFIGURED, evidence=(_evidence(),)),
            _result_with_evidence("b", status=CheckStatus.MISSING),
        )
        window = MainWindow(check_items=(_item(),))
        window.set_document(document)
        window.complete_verification(window._op_generation, results)
        # Ordering: MISSING (b) is row 0, CONFIGURED (a) is row 1.
        window._result_list.setCurrentRow(1)
        QTest.keyClick(window._result_list, Qt.Key_Return)
        assert "已配置" in window._detail_view.toPlainText()
        window.close()

    def test_ctrl_f_focuses_search(self, qapp) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        window = MainWindow(check_items=(_item(),))
        window.show()
        window._result_list.setFocus()
        qapp.processEvents()
        QTest.keyClick(window, Qt.Key_F, Qt.ControlModifier)
        qapp.processEvents()
        assert window._search_input.hasFocus()
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
