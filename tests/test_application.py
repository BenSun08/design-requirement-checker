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
    CheckResult,
    CheckStatus,
    ComparisonState,
    Coverage,
    Document,
    DocumentBlock,
    DocumentLocation,
    MatchType,
    Resolution,
    StrikeCoverage,
    TextRun,
)
from design_requirement_checker.matching import RULE_REVISION


class TestGNTableVerification:
    @staticmethod
    def _verify(
        path, expected_description: str = "采集ON信号，延时30min；停止驱动（D30）"
    ) -> CheckResult:  # type: ignore[no-untyped-def]
        document = import_document(path)
        assert isinstance(document, Document)
        item = CheckItem(
            item_id="gn36",
            code="FD-GN36",
            name="票机延时退电功能",
            detection_phrase="票机延时",
            expected_description=expected_description,
        )
        (result,) = verify_document(document, (item,)).results
        return result

    @pytest.mark.parametrize(
        ("delay", "comparison"),
        [("30min", ComparisonState.SAME), ("15min", ComparisonState.DIFFERENT)],
    )
    def test_compares_full_description_in_own_section(self, tmp_path, delay, comparison) -> None:
        actual = f"采集ON信号，延时{delay}；停止驱动（D30）"
        path = fixtures.build_gn_requirements(tmp_path / "gn.docx", ((actual, False),))
        result = self._verify(path)

        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is comparison
        (evidence,) = [e for e in result.evidence if e.match_type is MatchType.TABLE_DESCRIPTION]
        assert evidence.block_id == "t0r1c2:table-cell:p0"
        assert evidence.raw_text == actual
        assert evidence.requirement_span == (0, len(actual))
        assert evidence.evidence_id == result.primary_evidence_id
        assert any(
            e.block_id == "t1r1c1:table-cell:p0" and e.match_type is MatchType.EXPECTED_DESCRIPTION
            for e in result.evidence
        )

    def test_missing_header_stops_at_next_gn_heading(self, tmp_path) -> None:
        path = fixtures.build_gn_requirements(
            tmp_path / "gn.docx", (("延时15min", False),), description_header="说明"
        )
        result = self._verify(path)

        assert result.resolution is Resolution.UNRESOLVED
        assert result.status is None
        assert result.review_reasons == ("uncertain-function-table",)
        assert all(e.match_type is not MatchType.TABLE_DESCRIPTION for e in result.evidence)

    def test_struck_description_determines_status_with_active_heading(self, tmp_path) -> None:
        path = fixtures.build_gn_requirements(tmp_path / "gn.docx", (("延时30min", True),))
        result = self._verify(path)

        assert result.status is CheckStatus.STRUCK_OUT
        (evidence,) = [e for e in result.evidence if e.match_type is MatchType.TABLE_DESCRIPTION]
        assert evidence.strike_coverage is StrikeCoverage.FULL
        assert any(e.match_type is MatchType.FUNCTION_NAME for e in result.evidence)

    @pytest.mark.parametrize(
        ("delay", "comparison"),
        [("30min", ComparisonState.SAME), ("15min", ComparisonState.DIFFERENT)],
    )
    def test_complete_active_description_survives_struck_clause(
        self, tmp_path, delay, comparison
    ) -> None:
        leading = f"采集ON信号，延时{delay}；"
        old = "旧说明：等待45min再重试；"
        trailing = "停止驱动（D30）"
        path = fixtures.build_gn_description_runs(
            tmp_path / "gn.docx", ((leading, False), (old, True), (trailing, False))
        )
        result = self._verify(path)

        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is comparison
        assert result.review_reasons == ("partial-strike-active-description",)
        (evidence,) = [e for e in result.evidence if e.match_type is MatchType.TABLE_DESCRIPTION]
        assert evidence.strike_coverage is StrikeCoverage.PARTIAL
        assert evidence.raw_text == leading + old + trailing
        assert evidence.active_description_spans == (
            (0, len(leading)),
            (len(leading + old), len(leading + old + trailing)),
        )

    @pytest.mark.parametrize("separator", ["；", "，"])
    def test_exact_description_survives_an_inline_struck_replacement(
        self, tmp_path, separator
    ) -> None:
        leading = f"收到启用信号后延时30min{separator}"
        old = "控制期间持续供电"
        current = "控制期间允许待机"
        path = fixtures.build_gn_description_runs(
            tmp_path / "gn.docx", ((leading, False), (old, True), (current, False))
        )
        result = self._verify(path, leading + current)

        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is ComparisonState.SAME
        assert result.review_reasons == ("partial-strike-active-description",)
        (evidence,) = [e for e in result.evidence if e.match_type is MatchType.TABLE_DESCRIPTION]
        assert evidence.raw_text == leading + old + current
        assert evidence.description_source_text == leading + current
        assert evidence.active_description_spans == (
            (0, len(leading)),
            (len(leading + old), len(leading + old + current)),
        )

    def test_inline_replacement_keeps_separately_struck_whitespace(self, tmp_path) -> None:
        path = fixtures.build_gn_description_runs(
            tmp_path / "gn.docx",
            (
                ("收到启用信号；", False),
                ("控制期间持续供电", True),
                (" ", False),
                (" ", True),
                ("控制期间允许待机", False),
            ),
        )
        result = self._verify(path, "收到启用信号； 控制期间允许待机")

        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is ComparisonState.SAME

    @pytest.mark.parametrize(
        "runs",
        [
            (("采集", False), ("未", True), ("ON信号，延时30min；停止驱动（D30）", False)),
            (("未", True), ("采集ON信号，延时30min；停止驱动（D30）", False)),
            (("采集ON信号，延时3", False), (".", True), ("0min；停止驱动（D30）", False)),
            (("采集ON信号，延时", False), ("30min", True), ("；停止驱动（D30）", False)),
            (("采集ON信号，延时30min；停止驱动（", False), ("D30", True), ("）", False)),
            (
                ("采集ON信号，延时30min；", False),
                ("旧说明；", True),
                ("停止驱动（D31）", False),
            ),
        ],
    )
    def test_partial_strike_remains_unresolved_if_description_cannot_be_established(
        self, tmp_path, runs
    ) -> None:
        result = self._verify(fixtures.build_gn_description_runs(tmp_path / "gn.docx", runs))

        assert result.status is None
        assert result.resolution is Resolution.UNRESOLVED
        assert result.comparison_state is ComparisonState.NOT_COMPARED
        assert result.review_reasons == ("partial-strike",)

    def test_struck_whitespace_preserves_the_original_separator(self, tmp_path) -> None:
        path = fixtures.build_gn_description_runs(
            tmp_path / "gn.docx",
            (("采集ON信号，延时30", False), (" ", True), ("min；停止驱动（D30）", False)),
        )
        expected = "采集ON信号，延时30 min；停止驱动（D30）"
        result = self._verify(path, expected)

        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is ComparisonState.SAME
        (evidence,) = [e for e in result.evidence if e.match_type is MatchType.TABLE_DESCRIPTION]
        assert evidence.description_source_text == expected
        assert evidence.strike_coverage is StrikeCoverage.PARTIAL

    def test_partial_strike_without_baseline_description_stays_unresolved(self, tmp_path) -> None:
        path = fixtures.build_gn_description_runs(
            tmp_path / "gn.docx",
            (("旧说明；", True), ("采集ON信号，延时30min；停止驱动（D30）", False)),
        )
        result = self._verify(path, "")
        assert result.resolution is Resolution.UNRESOLVED
        assert result.review_reasons == ("partial-strike",)

    @pytest.mark.parametrize(("struck", "number"), [("３．", "0"), ("3.", "０")])
    def test_mixed_width_decimal_point_does_not_split_a_quantity(
        self, tmp_path, struck, number
    ) -> None:
        active = f"{number}min；停止驱动"
        path = fixtures.build_gn_description_runs(
            tmp_path / "gn.docx", ((struck, True), (active, False))
        )
        result = self._verify(path, active)

        assert result.resolution is Resolution.UNRESOLVED
        assert result.review_reasons == ("partial-strike",)

    def test_surviving_parameters_still_conflict_with_other_active_rows(self, tmp_path) -> None:
        path = fixtures.build_gn_description_runs(
            tmp_path / "gn.docx",
            (("旧说明：延时15min；", True), ("采集ON信号，延时30min；停止驱动（D30）", False)),
            (("采集ON信号，延时15min；停止驱动（D30）", False),),
        )
        result = self._verify(path)

        assert result.status is None
        assert "conflicting-key-parameters" in result.review_reasons

    def test_swapped_parameter_values_in_active_clauses_are_a_conflict(self, tmp_path) -> None:
        expected = "启动延时30min；关机延时15min"
        path = fixtures.build_gn_description_runs(
            tmp_path / "gn.docx",
            (("旧说明；", True), (expected, False)),
            (("启动延时15min；关机延时30min", False),),
        )
        result = self._verify(path, expected)

        assert result.status is None
        assert result.resolution is Resolution.UNRESOLVED
        assert result.review_reasons == ("conflicting-key-parameters",)

    def test_partial_description_cannot_restore_a_struck_heading_identity(self, tmp_path) -> None:
        path = fixtures.build_gn_description_runs(
            tmp_path / "gn.docx",
            (("旧说明；", True), ("采集ON信号，延时30min；停止驱动（D30）", False)),
            heading_struck=True,
            row_name="无标识",
        )
        result = self._verify(path)

        assert result.resolution is Resolution.UNRESOLVED
        assert result.review_reasons == ("partial-strike",)

    def test_conflicting_table_rows_are_both_retained(self, tmp_path) -> None:
        path = fixtures.build_gn_requirements(
            tmp_path / "gn.docx", (("延时30min", True), ("延时15min", False))
        )
        result = self._verify(path)

        assert result.resolution is Resolution.UNRESOLVED
        assert result.review_reasons == ("active-and-struck-coexist",)
        table_evidence = [e for e in result.evidence if e.match_type is MatchType.TABLE_DESCRIPTION]
        assert [e.strike_coverage for e in table_evidence] == [
            StrikeCoverage.FULL,
            StrikeCoverage.NONE,
        ]

    @pytest.mark.parametrize(
        ("delay", "comparison"),
        [("30min", ComparisonState.SAME), ("15min", ComparisonState.DIFFERENT)],
    )
    def test_complete_active_row_can_coexist_with_a_fully_struck_row(
        self, tmp_path, delay, comparison
    ) -> None:
        actual = f"采集ON信号，延时{delay}；停止驱动（D30）"
        path = fixtures.build_gn_requirements(
            tmp_path / "gn.docx", (("旧条款，延时60min", True), (actual, False))
        )
        result = self._verify(path)

        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is comparison
        assert result.review_reasons == ("struck-rows-with-active-description",)
        struck, active = [e for e in result.evidence if e.match_type is MatchType.TABLE_DESCRIPTION]
        assert struck.strike_coverage is StrikeCoverage.FULL
        assert active.description_source_text == actual
        assert result.primary_evidence_id == active.evidence_id

    def test_fully_struck_row_does_not_hide_conflicting_active_rows(self, tmp_path) -> None:
        path = fixtures.build_gn_requirements(
            tmp_path / "gn.docx",
            (
                ("旧条款，延时60min", True),
                ("采集ON信号，延时30min；停止驱动（D30）", False),
                ("采集ON信号，延时15min；停止驱动（D30）", False),
            ),
        )
        result = self._verify(path)

        assert result.resolution is Resolution.UNRESOLVED
        assert result.status is None
        assert "conflicting-key-parameters" in result.review_reasons

    def test_struck_row_exception_requires_all_live_rows_in_the_table_to_align(
        self, tmp_path
    ) -> None:
        path = fixtures.build_gn_requirements(
            tmp_path / "gn.docx",
            (
                ("旧条款，延时60min", True),
                ("采集ON信号，延时30min；停止驱动（D30）", False),
                ("采集ON信号，延时30min；停止驱动（D31）", False),
            ),
        )
        result = self._verify(path)

        assert result.resolution is Resolution.UNRESOLVED
        assert result.review_reasons == ("active-and-struck-coexist",)

    def test_struck_row_exception_does_not_override_another_function_table(self, tmp_path) -> None:
        expected = "延时30min后允许输出"
        path = fixtures.build_gn_description_runs(
            tmp_path / "gn.docx",
            (("旧条款", True),),
            ((expected, False),),
            next_section_rows=((("延时30min后禁止输出", False),),),
        )
        result = self._verify(path, expected)

        assert result.resolution is Resolution.UNRESOLVED
        assert result.review_reasons == ("active-and-struck-coexist",)

    def test_struck_row_exception_requires_a_live_heading_identity(self, tmp_path) -> None:
        expected = "延时30min后允许输出"
        path = fixtures.build_gn_description_runs(
            tmp_path / "gn.docx",
            (("旧条款", True),),
            ((expected, False),),
            heading_struck=True,
            row_name="无标识",
        )
        result = self._verify(path, expected)

        assert result.resolution is Resolution.UNRESOLVED
        assert result.review_reasons == ("active-and-struck-coexist",)

    def test_struck_row_exception_requires_more_than_a_bare_identity(self, tmp_path) -> None:
        path = fixtures.build_gn_requirements(
            tmp_path / "gn.docx", (("延时30min后关闭输出", True), ("票机延时", False))
        )
        result = self._verify(path, "票机延时")

        assert result.resolution is Resolution.UNRESOLVED
        assert result.review_reasons == ("active-and-struck-coexist",)

    @pytest.mark.parametrize(
        ("separator", "expected_signal", "comparison"),
        [
            ("\n", "D13", ComparisonState.SAME),
            (" ", "D13", ComparisonState.SAME),
            ("\n", "D14", ComparisonState.DIFFERENT),
            ("", "D13", ComparisonState.DIFFERENT),
        ],
    )
    def test_compares_all_paragraphs_in_one_description_cell(
        self, tmp_path, separator, expected_signal, comparison
    ) -> None:
        clauses = (
            "1. 采集伸出开关（D7）有效，发送按下信号；",
            "2. 采集伸出开关（D7）无效，发送未按下信号；",
            "3. 采集收回开关（D13）有效，发送按下信号；",
            "4. 采集收回开关（D13）无效，发送未按下信号。",
        )
        path = fixtures.build_gn_requirements(
            tmp_path / "gn.docx",
            ((clauses[0], False),),
            extra_paragraphs=(
                (clauses[1], False),
                ("", False),
                (clauses[2], False),
                (clauses[3], False),
            ),
        )
        expected = separator.join(clauses).replace("D13", expected_signal)
        result = self._verify(path, expected)

        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is comparison
        (cell,) = [e for e in result.evidence if e.match_type is MatchType.TABLE_DESCRIPTION]
        assert result.primary_evidence_id == cell.evidence_id
        assert cell.description_source_text == "\n".join((*clauses[:2], "", *clauses[2:]))
        assert cell.raw_text == clauses[0]
        assert cell.requirement_span == (0, len(clauses[0]))
        assert [block.block_id for block in cell.additional_cell_paragraphs] == [
            "t0r1c2:table-cell:p1",
            "t0r1c2:table-cell:p2",
            "t0r1c2:table-cell:p3",
            "t0r1c2:table-cell:p4",
        ]

    @pytest.mark.parametrize(
        ("first_struck", "second_struck", "coverage", "status", "reasons"),
        [
            (True, True, StrikeCoverage.FULL, CheckStatus.STRUCK_OUT, ()),
            (True, False, StrikeCoverage.PARTIAL, None, ("partial-strike",)),
            (False, None, StrikeCoverage.UNKNOWN, None, ("unknown-strike-formatting",)),
        ],
    )
    def test_multi_paragraph_cell_retains_strike_evidence(
        self, tmp_path, first_struck, second_struck, coverage, status, reasons
    ) -> None:
        path = fixtures.build_gn_requirements(
            tmp_path / "gn.docx",
            (("延时30min；", first_struck),),
            extra_paragraphs=(("停止驱动D30", second_struck),),
        )
        result = self._verify(path)

        assert result.status is status
        assert result.review_reasons == reasons
        assert result.comparison_state is ComparisonState.NOT_COMPARED
        (cell,) = [e for e in result.evidence if e.match_type is MatchType.TABLE_DESCRIPTION]
        assert cell.strike_coverage is coverage
        assert cell.description_source_text == "延时30min；\n停止驱动D30"
        (second,) = cell.additional_cell_paragraphs
        assert second.runs[0].effective_strike is second_struck

    def test_description_never_joins_cells_in_separate_rows(self, tmp_path) -> None:
        path = fixtures.build_gn_requirements(
            tmp_path / "gn.docx", (("延时30min；", False), ("停止驱动D30", False))
        )
        result = self._verify(path, "延时30min；\n停止驱动D30")

        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is ComparisonState.DIFFERENT
        assert [
            evidence.description_source_text
            for evidence in result.evidence
            if evidence.match_type is MatchType.TABLE_DESCRIPTION
        ] == ["延时30min；", "停止驱动D30"]

    def test_grid_before_does_not_move_the_description_to_the_remarks(self, tmp_path) -> None:
        result = self._verify(
            fixtures.build_gn_grid_table(tmp_path / "gn.docx", "leading-omission")
        )

        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is ComparisonState.SAME
        (description,) = [e for e in result.evidence if e.match_type is MatchType.TABLE_DESCRIPTION]
        assert description.block_id == "t0r1c1:table-cell:p0"
        assert description.raw_text == "采集ON信号，延时30min；停止驱动（D30）"

    @pytest.mark.parametrize("layout", ["excluded-cell", "merged-header"])
    def test_ambiguous_description_grid_requires_review(self, tmp_path, layout) -> None:
        result = self._verify(fixtures.build_gn_grid_table(tmp_path / "gn.docx", layout))

        assert result.resolution is Resolution.UNRESOLVED
        assert result.review_reasons == ("uncertain-function-table",)
        assert all(e.match_type is not MatchType.TABLE_DESCRIPTION for e in result.evidence)
        (candidate,) = [
            e for e in result.evidence if e.match_type is MatchType.EXPECTED_DESCRIPTION
        ]
        assert candidate.block_id == "t0r1c1:table-cell:p0"


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


# ---------------------------------------------------------------------------
# Task 5, T5.2 — Baseline cross-item validation
# ---------------------------------------------------------------------------


def _vitem(
    item_id: str,
    code: str,
    name: str,
    phrase: str,
    *,
    aliases: tuple = (),
    enabled: bool = True,
) -> CheckItem:
    from design_requirement_checker.domain import CheckItemAlias

    return CheckItem(
        item_id=item_id,
        code=code,
        name=name,
        detection_phrase=phrase,
        aliases=tuple(
            CheckItemAlias(alias_id=f"{item_id}-a{i}", text=t, notes="")
            for i, t in enumerate(aliases)
        ),
        enabled=enabled,
    )


class TestBaselineValidation:
    def test_unique_baseline_no_issues(self) -> None:
        from design_requirement_checker.application import validate_baseline

        items = (
            _vitem("a", "A", "功能A", "检测A"),
            _vitem("b", "B", "功能B", "检测B"),
        )
        result = validate_baseline(items)
        assert result.is_valid
        assert result.errors == ()
        assert result.warnings == ()

    def test_duplicate_code_error(self) -> None:
        from design_requirement_checker.application import validate_baseline

        items = (
            _vitem("a", "DUP", "功能A", "检测A"),
            _vitem("b", "DUP", "功能B", "检测B"),
        )
        result = validate_baseline(items)
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0].kind == "duplicate-code"
        assert set(result.errors[0].item_ids) == {"a", "b"}

    def test_duplicate_name_warning(self) -> None:
        from design_requirement_checker.application import validate_baseline

        items = (
            _vitem("a", "A", "同名", "检测A"),
            _vitem("b", "B", "同名", "检测B"),
        )
        result = validate_baseline(items)
        assert result.is_valid  # warnings don't block
        names = [w.kind for w in result.warnings]
        assert "duplicate-name" in names

    def test_same_phrase_across_items_warning(self) -> None:
        from design_requirement_checker.application import validate_baseline

        items = (
            _vitem("a", "A", "功能A", "相同检测短语"),
            _vitem("b", "B", "功能B", "相同检测短语"),
        )
        result = validate_baseline(items)
        collision_kinds = [w.kind for w in result.warnings]
        assert "phrase-collision" in collision_kinds

    def test_alias_collides_with_other_detection_warning(self) -> None:
        from design_requirement_checker.application import validate_baseline

        items = (
            _vitem("a", "A", "功能A", "检测短语X"),
            _vitem("b", "B", "功能B", "检测短语B", aliases=("检测短语X",)),
        )
        result = validate_baseline(items)
        collision_kinds = [w.kind for w in result.warnings]
        assert "phrase-collision" in collision_kinds

    def test_substring_overlap_warning(self) -> None:
        from design_requirement_checker.application import validate_baseline

        items = (
            _vitem("a", "A", "功能A", "门控制延时"),
            _vitem("b", "B", "功能B", "2门控制增加门控制延时功能"),
        )
        result = validate_baseline(items)
        overlap_kinds = [w.kind for w in result.warnings]
        # Either phrase-collision (after normalize they overlap) or phrase-overlap.
        assert "phrase-overlap" in overlap_kinds or "phrase-collision" in overlap_kinds

    def test_normal_non_overlapping_phrases_no_warning(self) -> None:
        from design_requirement_checker.application import validate_baseline

        items = (
            _vitem("a", "A", "功能A", "2门控制延时"),
            _vitem("b", "B", "功能B", "门锁状态反馈"),
        )
        result = validate_baseline(items)
        phrase_warnings = [
            w for w in result.warnings if w.kind in ("phrase-collision", "phrase-overlap")
        ]
        assert phrase_warnings == []

    def test_disabled_item_still_validated(self) -> None:
        """Disabled items are still part of the persisted baseline and must
        be validated for duplicate code / names / phrases."""
        from design_requirement_checker.application import validate_baseline

        items = (
            _vitem("a", "DUP", "功能A", "检测A", enabled=False),
            _vitem("b", "DUP", "功能B", "检测B", enabled=True),
        )
        result = validate_baseline(items)
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0].kind == "duplicate-code"

    def test_deterministic_stable_ordering(self) -> None:
        from design_requirement_checker.application import validate_baseline

        items_a = (
            _vitem("x", "SAME", "Z", "Z"),
            _vitem("y", "SAME", "Y", "Y"),
        )
        items_b = tuple(reversed(items_a))
        r1 = validate_baseline(items_a)
        r2 = validate_baseline(items_b)
        # Same errors/warnings regardless of input order.
        assert [(e.kind, e.item_ids) for e in r1.errors] == [
            (e.kind, e.item_ids) for e in r2.errors
        ]
        assert [(w.kind, w.item_ids) for w in r1.warnings] == [
            (w.kind, w.item_ids) for w in r2.warnings
        ]


class TestBaselineLifecycle:
    def _vitem(
        self,
        item_id: str,
        code: str,
        name: str,
        phrase: str,
        *,
        enabled: bool = True,
    ) -> CheckItem:
        return CheckItem(
            item_id=item_id,
            code=code,
            name=name,
            detection_phrase=phrase,
            aliases=(),
            enabled=enabled,
        )

    # --- Load ---

    def test_load_from_missing_file_is_not_a_failure(self, tmp_path) -> None:
        from design_requirement_checker.application import load_baseline_from

        result = load_baseline_from(tmp_path / "no_such.json")
        assert result.items == ()  # empty = normal first launch
        assert result.baseline_id == ""
        assert result.source == "no-baseline"
        assert result.error is None
        assert result.ok

    def test_load_from_corrupt_file_reports_error(self, tmp_path) -> None:
        from design_requirement_checker.application import load_baseline_from

        bad = tmp_path / "corrupt.json"
        bad.write_text("not json", encoding="utf-8")
        result = load_baseline_from(bad)
        assert not result.ok
        assert result.items is None
        assert result.error is not None

    def test_load_from_valid_roundtrip(self, tmp_path) -> None:
        from design_requirement_checker.application import (
            load_baseline_from,
            save_baseline_to,
        )

        items = (
            self._vitem("a", "A", "功能A", "检测A"),
            self._vitem("b", "B", "功能B", "检测B"),
        )
        path = tmp_path / "baseline.json"
        save_baseline_to(path, items, "bid-1")
        result = load_baseline_from(path)
        assert result.ok
        assert result.items == items
        assert result.baseline_id == "bid-1"
        assert result.source == "primary"

    # --- Save ---

    def test_save_returns_validation_with_warnings(self, tmp_path) -> None:
        from design_requirement_checker.application import save_baseline_to

        items = (
            self._vitem("a", "A", "同名", "检测A"),
            self._vitem("b", "B", "同名", "检测B"),
        )
        path = tmp_path / "baseline.json"
        result = save_baseline_to(path, items, "bid-2")
        assert result.is_valid
        assert len(result.warnings) == 1
        assert result.warnings[0].kind == "duplicate-name"
        # File actually written
        assert path.exists()

    def test_save_blocks_on_validation_errors(self, tmp_path) -> None:
        from design_requirement_checker.application import save_baseline_to

        items = (
            self._vitem("a", "DUP", "功能A", "检测A"),
            self._vitem("b", "DUP", "功能B", "检测B"),
        )
        path = tmp_path / "baseline.json"
        import pytest

        with pytest.raises(ValueError, match="validation errors block save"):
            save_baseline_to(path, items, "bid-3")
        # Nothing written
        assert not path.exists()

    def test_persistence_failure_preserves_no_baseline(self, tmp_path, monkeypatch) -> None:
        """If the atomic save fails, no baseline file is left behind."""
        import design_requirement_checker.baseline_store as bs
        from design_requirement_checker.application import save_baseline_to

        original = bs._phase_replace

        def _failing_replace(src, dst, *, phase):
            if phase == 2:
                raise OSError("disk full")
            return original(src, dst, phase=phase)

        monkeypatch.setattr(bs, "_phase_replace", _failing_replace)

        items = (self._vitem("a", "A", "功能A", "检测A"),)
        path = tmp_path / "baseline.json"
        import pytest

        with pytest.raises(OSError, match="disk full"):
            save_baseline_to(path, items, "bid-4")
        assert not path.exists()

    def test_save_then_load_preserves_stable_ids(self, tmp_path) -> None:
        from design_requirement_checker.application import (
            load_baseline_from,
            save_baseline_to,
        )

        items = (self._vitem("keep-me", "A", "功能A", "检测A"),)
        path = tmp_path / "baseline.json"
        save_baseline_to(path, items, "bid-5")
        result = load_baseline_from(path)
        assert result.items[0].item_id == "keep-me"
