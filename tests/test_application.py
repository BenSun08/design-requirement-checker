"""Application-layer coordination tests (Task 2 import, Task 3 verification).

Expected behavior: import returns a domain Document snapshot or an explicit
ImportFailure — never an exception for bad input, never a silently empty
document — and never modifies the original file. Verification returns one
CheckResult per enabled item inside an outcome whose lifecycle distinguishes
completed, cancelled and failed runs (a cancelled run is never a completed
all-MISSING report).
"""

import hashlib

import fixture_factory as fixtures
import pytest

from design_requirement_checker.application import (
    ImportFailure,
    VerificationOutcome,
    VerificationState,
    import_document,
    verify_document,
)
from design_requirement_checker.domain import (
    BlockType,
    CheckItem,
    CheckStatus,
    ComparisonState,
    Coverage,
    Document,
    DocumentBlock,
    DocumentLocation,
    Resolution,
    TextRun,
)
from design_requirement_checker.matching import RULE_REVISION


def _sha256(path) -> str:  # type: ignore[no-untyped-def]
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestImportDocument:
    def test_success_returns_domain_document(self, tmp_path) -> None:
        path = fixtures.build_normal(tmp_path / "normal.docx")
        outcome = import_document(path)
        assert isinstance(outcome, Document)
        assert outcome.filename == "normal.docx"
        assert outcome.coverage is Coverage.COMPLETE
        assert len(outcome.blocks) == 5

    def test_limited_document_carries_warnings(self, tmp_path) -> None:
        path = fixtures.build_excluded_parts(tmp_path / "excluded.docx")
        outcome = import_document(path)
        assert isinstance(outcome, Document)
        assert outcome.coverage is Coverage.LIMITED
        assert outcome.warnings

    def test_malformed_file_returns_explicit_failure(self, tmp_path) -> None:
        path = fixtures.build_malformed(tmp_path / "malformed.docx")
        outcome = import_document(path)
        assert isinstance(outcome, ImportFailure)
        assert outcome.filename == "malformed.docx"
        assert outcome.reason == "invalid-or-unreadable-document"
        assert outcome.detail

    def test_ole_container_returns_explicit_failure(self, tmp_path) -> None:
        # Password-protected Word documents arrive in an OLE compound-file
        # container; the import must fail explicitly, not open as empty.
        path = fixtures.build_ole_container(tmp_path / "protected.docx")
        outcome = import_document(path)
        assert isinstance(outcome, ImportFailure)
        assert outcome.filename == "protected.docx"
        assert outcome.reason == "invalid-or-unreadable-document"

    def test_missing_file_returns_access_failure(self, tmp_path) -> None:
        outcome = import_document(tmp_path / "does-not-exist.docx")
        assert isinstance(outcome, ImportFailure)
        assert outcome.reason == "file-access-error"
        assert outcome.filename == "does-not-exist.docx"

    def test_string_path_is_accepted(self, tmp_path) -> None:
        path = fixtures.build_normal(tmp_path / "normal.docx")
        outcome = import_document(str(path))
        assert isinstance(outcome, Document)

    def test_import_does_not_modify_the_original_file(self, tmp_path) -> None:
        path = fixtures.build_strike_matrix(tmp_path / "strike.docx")
        before = _sha256(path)
        import_document(path)
        assert _sha256(path) == before

    def test_repeated_import_yields_the_same_identity(self, tmp_path) -> None:
        path = fixtures.build_table(tmp_path / "table.docx")
        first = import_document(path)
        second = import_document(path)
        assert isinstance(first, Document)
        assert isinstance(second, Document)
        assert first.document_id == second.document_id
        assert first.content_fingerprint == second.content_fingerprint


def _run(text: str, strike: bool | None = False) -> TextRun:
    return TextRun(
        text=text,
        start_offset=0,
        end_offset=len(text),
        effective_strike=strike,
        strike_origin="run-direct" if strike is not None else "default-off",
        strike_reason="" if strike is not None else "test-unknown-formatting",
    )


def _block(block_id: str, text: str, strike: bool | None = False) -> DocumentBlock:
    location = DocumentLocation(
        document_id="doc-app",
        block_id=block_id,
        block_type=BlockType.PARAGRAPH,
        part="body",
        paragraph_index=int(block_id.removeprefix("body:p")),
    )
    return DocumentBlock(
        block_id=block_id,
        block_type=BlockType.PARAGRAPH,
        text=text,
        runs=(_run(text, strike),),
        location=location,
    )


def _document(*blocks: DocumentBlock) -> Document:
    return Document(
        document_id="doc-app",
        filename="app.docx",
        content_fingerprint="app-fingerprint",
        blocks=blocks,
        coverage=Coverage.COMPLETE,
    )


def _item(item_id: str, phrase: str, *, enabled: bool = True) -> CheckItem:
    return CheckItem(
        item_id=item_id,
        code=item_id.upper(),
        name=f"name-{item_id}",
        detection_phrase=phrase,
        aliases=(),
        enabled=enabled,
    )


class TestVerifyDocument:
    def test_completed_run_has_one_result_per_enabled_item(self) -> None:
        document = _document(_block("body:p0", "2门控制增加开关门延时3s功能"))
        items = (
            _item("a", "2门控制增加开关门延时"),
            _item("b", "不存在的功能"),
            _item("c", "2门控制增加开关门延时", enabled=False),
        )
        outcome = verify_document(document, items)
        assert isinstance(outcome, VerificationOutcome)
        assert outcome.state is VerificationState.COMPLETED
        assert [r.check_item.item_id for r in outcome.results] == ["a", "b"]  # disabled excluded
        assert outcome.results[0].status is CheckStatus.CONFIGURED
        assert outcome.results[1].status is CheckStatus.MISSING
        assert all(r.rule_revision == RULE_REVISION for r in outcome.results)

    def test_outcome_carries_document_identity_and_coverage(self) -> None:
        document = _document(_block("body:p0", "内容"))
        outcome = verify_document(document, (_item("a", "功能"),))
        assert outcome.document_id == "doc-app"
        assert outcome.coverage is Coverage.COMPLETE
        assert outcome.coverage_warnings == ()

    def test_limited_document_still_produces_results(self) -> None:
        document = Document(
            document_id="doc-app",
            filename="app.docx",
            content_fingerprint="app-fingerprint",
            blocks=(_block("body:p0", "2门控制增加开关门延时3s功能"),),
            coverage=Coverage.LIMITED,
            warnings=("tracked-revisions-unsupported",),
        )
        outcome = verify_document(document, (_item("a", "2门控制增加开关门延时"),))
        assert outcome.state is VerificationState.COMPLETED
        assert outcome.coverage is Coverage.LIMITED
        assert outcome.coverage_warnings == ("tracked-revisions-unsupported",)
        assert outcome.results[0].status is CheckStatus.CONFIGURED

    def test_cancellation_is_not_a_completed_run(self) -> None:
        document = _document(
            _block("body:p0", "内容一"), _block("body:p1", "内容二"), _block("body:p2", "内容三")
        )
        calls = {"n": 0}

        def cancel_after_two() -> bool:
            calls["n"] += 1
            return calls["n"] > 2

        outcome = verify_document(document, (_item("a", "功能"),), cancel_check=cancel_after_two)
        assert outcome.state is VerificationState.CANCELLED
        assert outcome.results == ()  # never a partial completed result set

    def test_cancelled_run_is_distinct_from_all_missing(self) -> None:
        document = _document(_block("body:p0", "无关内容"))
        completed = verify_document(document, (_item("a", "功能"),))
        assert completed.state is VerificationState.COMPLETED
        assert completed.results[0].resolution is Resolution.RESOLVED
        assert completed.results[0].status is CheckStatus.MISSING

        def cancel_now() -> bool:
            return True

        cancelled = verify_document(document, (_item("a", "功能"),), cancel_check=cancel_now)
        assert cancelled.state is VerificationState.CANCELLED
        assert cancelled.results == ()

    def test_repeated_verification_is_deterministic(self) -> None:
        document = _document(
            _block("body:p0", "2门控制增加开关门延时3s功能"),
            _block("body:p1", "2门控制增加开关门延时3s功能"),
        )
        items = (_item("a", "2门控制增加开关门延时"), _item("b", "不存在"))
        first = verify_document(document, items)
        second = verify_document(document, items)
        assert first == second

    def test_composition_with_real_ingestion(self, tmp_path) -> None:
        # Task 2 -> Task 3: synthetic DOCX -> read_document -> verify_document.
        path = fixtures.build_requirement_strike(tmp_path / "requirement-strike.docx")
        document = import_document(path)
        assert isinstance(document, Document)
        items = (
            CheckItem(
                item_id="a",
                code="A",
                name="A功能",
                detection_phrase="A功能增加延时",
                expected_description="A功能增加延时2s",
                aliases=(),
                enabled=True,
            ),
            CheckItem(
                item_id="b",
                code="B",
                name="B功能",
                detection_phrase="B功能增加延时",
                expected_description="B功能增加延时2s",
                aliases=(),
                enabled=True,
            ),
            CheckItem(
                item_id="c",
                code="C",
                name="C功能",
                detection_phrase="C功能增加延时",
                expected_description="C功能增加延时2s",
                aliases=(),
                enabled=True,
            ),
        )
        outcome = verify_document(document, items)
        assert outcome.state is VerificationState.COMPLETED
        by_id = {r.check_item.item_id: r for r in outcome.results}
        assert by_id["a"].status is CheckStatus.CONFIGURED
        assert by_id["a"].comparison_state is ComparisonState.DIFFERENT
        assert by_id["b"].resolution is Resolution.UNRESOLVED
        assert "partial-strike" in by_id["b"].review_reasons
        assert by_id["c"].status is CheckStatus.STRUCK_OUT
        assert by_id["c"].comparison_reason == "evidence-struck"

    def test_empty_baseline_completes_with_no_results(self) -> None:
        document = _document(_block("body:p0", "内容"))
        outcome = verify_document(document, ())
        assert outcome.state is VerificationState.COMPLETED
        assert outcome.results == ()

    def test_outcome_rejects_results_without_completion(self) -> None:
        document = _document(_block("body:p0", "内容"))
        completed = verify_document(document, (_item("a", "功能"),))
        with pytest.raises(ValueError, match="completed"):
            VerificationOutcome(
                document_id="doc-app",
                coverage=Coverage.COMPLETE,
                coverage_warnings=(),
                state=VerificationState.CANCELLED,
                results=completed.results,
            )
