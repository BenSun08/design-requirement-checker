"""Task 3 production matching tests (docs/domain-model.md, merged S6 evidence).

Expected spans, statuses and reasons are independent labels derived from the
product/domain documents and the merged S6 record — never from implementation
output. Raw offsets are zero-based half-open code-point ranges over the
fixture strings written here.
"""

from collections.abc import Sequence

import pytest

from design_requirement_checker.domain import (
    BlockType,
    CheckItem,
    CheckItemAlias,
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
from design_requirement_checker.matching import (
    VerificationCancelled,
    map_span,
    normalize,
    verify,
)

PHRASE = "2门控制增加开关门延时"
EXPECTED = "2门控制增加开关门延时2s功能"
DOC_SENTENCE = "2门控制增加开关门延时3s功能"


def make_run(text: str, start: int, strike: bool | None = False) -> TextRun:
    return TextRun(
        text=text,
        start_offset=start,
        end_offset=start + len(text),
        effective_strike=strike,
        strike_origin="run-direct" if strike is not None else "default-off",
        strike_reason="" if strike is not None else "test-unknown-formatting",
    )


def make_block(block_index: int, parts: Sequence[tuple[str, bool | None]]) -> DocumentBlock:
    runs: list[TextRun] = []
    offset = 0
    for text, strike in parts:
        if not text:
            continue
        runs.append(make_run(text, offset, strike))
        offset += len(text)
    location = DocumentLocation(
        document_id="doc-t3",
        block_id=f"body:p{block_index}",
        block_type=BlockType.PARAGRAPH,
        part="body",
        paragraph_index=block_index,
    )
    return DocumentBlock(
        block_id=f"body:p{block_index}",
        block_type=BlockType.PARAGRAPH,
        text="".join(run.text for run in runs),
        runs=tuple(runs),
        location=location,
    )


def make_document(*blocks: DocumentBlock) -> Document:
    return Document(
        document_id="doc-t3",
        filename="t3.docx",
        content_fingerprint="t3-fingerprint",
        blocks=tuple(blocks),
        coverage=Coverage.COMPLETE,
    )


def make_item(
    item_id: str,
    detection_phrase: str,
    expected_description: str = "",
    aliases: Sequence[str] = (),
    name: str = "",
    enabled: bool = True,
) -> CheckItem:
    return CheckItem(
        item_id=item_id,
        code=item_id.upper(),
        name=name or f"name-{item_id}",
        detection_phrase=detection_phrase,
        expected_description=expected_description,
        aliases=tuple(
            CheckItemAlias(alias_id=f"{item_id}-alias-{index}", text=text)
            for index, text in enumerate(aliases)
        ),
        enabled=enabled,
    )


def verify_one(item: CheckItem, *blocks: DocumentBlock) -> CheckResult:
    results = verify(make_document(*blocks), (item,))
    assert len(results) == 1
    return results[0]


class TestNormalizationAllowlist:
    def test_whitespace_runs_collapse_to_single_space(self) -> None:
        assert normalize("A  B").text == "A B"
        assert normalize("A\t　 B").text == "A B"

    def test_line_breaks_within_block_become_space(self) -> None:
        assert normalize("A\nB\r\nC").text == "A B C"

    def test_fullwidth_ascii_punctuation_maps_one_to_one(self) -> None:
        assert normalize("（：；，？！．）").text == "(:;,?!.)"

    def test_rejected_transformations_stay_verbatim(self) -> None:
        # R1 ideographic full stop, R2 fullwidth digits/letters, R3 case.
        assert normalize("。").text == "。"
        assert normalize("２s").text == "２s"
        assert normalize("ＣＡＮ１").text == "ＣＡＮ１"
        assert normalize("CAN1").text == "CAN1"
        assert normalize("can1").text == "can1"

    def test_engineering_meaning_is_preserved(self) -> None:
        pairs = [
            ("2s", "3s"),
            ("24V", "12V"),
            ("开启", "不开启"),
            ("允许", "禁止"),
            (">5km/h", "<5km/h"),
            ("CAN1", "CAN2"),
            ("２s", "2s"),
            ("CAN", "can"),
        ]
        for left, right in pairs:
            assert normalize(left).text != normalize(right).text, (left, right)

    def test_mapping_invariants_on_mixed_text(self) -> None:
        raw = "2门 延时（3s）\t功能。"
        result = normalize(raw)
        assert result.text == "2门 延时(3s) 功能。"
        sources = result.char_sources
        assert len(sources) == len(result.text)
        assert sources[0][0] == 0
        assert sources[-1][1] == len(raw)
        for prev, cur in zip(sources, sources[1:]):
            assert prev[1] == cur[0]


class TestRawNormalizedOffsetMapping:
    def test_exact_span_maps_identity(self) -> None:
        result = normalize(DOC_SENTENCE)
        assert map_span(result, 0, 11) == (0, 11)

    def test_collapsed_run_maps_to_whole_raw_run(self) -> None:
        assert map_span(normalize("A  B"), 0, 3) == (0, 4)

    def test_normalized_span_maps_across_tab(self) -> None:
        raw = "2门控制增加开关门延时\t3s功能"
        result = normalize(raw)
        assert result.text == "2门控制增加开关门延时 3s功能"
        assert map_span(result, 9, 14) == (9, 14)
        assert raw[9:14] == "延时\t3s"

    def test_normalized_match_over_punctuation_and_line_break(self) -> None:
        raw = "（延时\n2s）"
        result = normalize(raw)
        assert result.text == "(延时 2s)"
        assert map_span(result, 0, 7) == (0, 7)


class TestExactDetection:
    def test_exact_phrase_present_qualifies(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED, name="2门控制延时")
        result = verify_one(item, make_block(0, [(DOC_SENTENCE, False)]))
        assert result.resolution is Resolution.RESOLVED
        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is ComparisonState.DIFFERENT
        (evidence,) = result.evidence
        assert evidence.matched_term == PHRASE
        assert evidence.match_type is MatchType.EXACT
        assert evidence.matched_span == (0, 11)
        assert evidence.requirement_span == (0, 15)
        assert evidence.strike_coverage is StrikeCoverage.NONE
        assert evidence.transformations == ()
        assert evidence.ambiguous is False
        assert evidence.block_id == "body:p0"
        assert evidence.location.paragraph_index == 0

    def test_phrase_absent_is_missing(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        result = verify_one(item, make_block(0, [("1门控制增加开关门延时3s功能", False)]))
        assert result.resolution is Resolution.RESOLVED
        assert result.status is CheckStatus.MISSING
        assert result.evidence == ()

    def test_broad_related_wording_not_accepted(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        result = verify_one(item, make_block(0, [("本车具备2门控制相关功能，详见附录。", False)]))
        assert result.status is CheckStatus.MISSING

    def test_similar_neighbouring_function_not_accepted(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        b0 = make_block(0, [("2门控制增加开门延时3s功能", False)])  # 开门, not 开关门
        b1 = make_block(1, [("2门控制增加开关延时3s功能", False)])  # 开关, not 开关门
        assert verify_one(item, b0, b1).status is CheckStatus.MISSING

    def test_display_name_is_not_a_detector(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED, name="2门控制延时")
        result = verify_one(item, make_block(0, [("支持2门控制延时。", False)]))
        assert result.status is CheckStatus.MISSING


class TestNormalizedMatching:
    def test_whitespace_variant_matches_normalized(self) -> None:
        item = make_item("a", "A B功能", "A B功能2s")
        result = verify_one(item, make_block(0, [("A  B功能2s", False)]))
        assert result.status is CheckStatus.CONFIGURED
        (evidence,) = result.evidence
        assert evidence.match_type is MatchType.NORMALIZED
        assert evidence.matched_span == (0, 6)  # raw span includes both spaces
        assert "A  B功能"[0:6] == "A  B功能"
        assert evidence.transformations == ("N1",)

    def test_line_break_variant_matches_normalized(self) -> None:
        item = make_item("a", "A B功能", "")
        result = verify_one(item, make_block(0, [("A\nB功能", False)]))
        (evidence,) = result.evidence
        assert evidence.match_type is MatchType.NORMALIZED
        assert evidence.matched_span == (0, 5)  # raw span includes the line break
        assert evidence.transformations == ("N2",)

    def test_fullwidth_punctuation_variant_matches_normalized(self) -> None:
        item = make_item("a", "延时（3s）", "")
        result = verify_one(item, make_block(0, [("延时(3s)", False)]))
        (evidence,) = result.evidence
        assert evidence.match_type is MatchType.NORMALIZED
        assert evidence.matched_span == (0, 6)
        assert evidence.transformations == ("N3",)

    def test_raw_text_is_never_replaced_by_normalized_text(self) -> None:
        item = make_item("a", "A B功能", "")
        block = make_block(0, [("A  B功能", False)])
        (evidence,) = verify_one(item, block).evidence
        assert evidence.raw_text == "A  B功能"
        assert block.text[evidence.matched_span[0] : evidence.matched_span[1]] == "A  B功能"


class TestAliases:
    def test_alias_hit_establishes_identity(self) -> None:
        item = make_item("dr-006", PHRASE, "", aliases=("两门延时功能",))
        result = verify_one(item, make_block(0, [("两门延时功能，延时3s。", False)]))
        assert result.status is CheckStatus.CONFIGURED
        (evidence,) = result.evidence
        assert evidence.matched_term == "两门延时功能"
        assert evidence.match_type is MatchType.ALIAS
        assert evidence.alias_id == "dr-006-alias-0"

    def test_alias_does_not_imply_description_equality(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED, aliases=("两门延时功能",))
        result = verify_one(item, make_block(0, [("两门延时功能3s", False)]))
        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is ComparisonState.DIFFERENT  # never auto-SAME

    def test_multiple_aliases_are_retained(self) -> None:
        item = make_item("dr-006", PHRASE, "", aliases=("两门延时功能", "双门延时"))
        b0 = make_block(0, [("两门延时功能3s", False)])
        b1 = make_block(1, [("双门延时3s", False)])
        result = verify_one(item, b0, b1)
        assert result.status is CheckStatus.CONFIGURED
        assert [e.matched_term for e in result.evidence] == ["两门延时功能", "双门延时"]

    def test_alias_and_canonical_in_same_document(self) -> None:
        item = make_item("dr-006", PHRASE, "", aliases=("两门延时功能",))
        b0 = make_block(0, [(DOC_SENTENCE, False)])
        b1 = make_block(1, [("两门延时功能3s", False)])
        result = verify_one(item, b0, b1)
        assert [(e.matched_term, e.match_type) for e in result.evidence] == [
            (PHRASE, MatchType.EXACT),
            ("两门延时功能", MatchType.ALIAS),
        ]


class TestRequirementSpanAssociation:
    def test_value_in_same_clause_associates(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        (evidence,) = verify_one(item, make_block(0, [(DOC_SENTENCE, False)])).evidence
        assert evidence.requirement_span == (0, 15)
        assert evidence.requirement_text == DOC_SENTENCE

    def test_value_after_comma_is_not_associated(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        result = verify_one(item, make_block(0, [("2门控制增加开关门延时，延时时间为3s。", False)]))
        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is ComparisonState.NOT_COMPARED
        assert result.comparison_reason == "requirement-span-association-uncertain"
        (evidence,) = result.evidence
        assert evidence.requirement_span == (0, 11)

    def test_semicolon_separated_requirements_do_not_cross_associate(self) -> None:
        item1 = make_item("dr-006", PHRASE, EXPECTED)
        item2 = make_item("dr-007", "1门控制增加开关门延时", "1门控制增加开关门延时2s功能")
        block = make_block(0, [("2门控制增加开关门延时3s功能；1门控制增加开关门延时5s功能", False)])
        r1, r2 = verify(make_document(block), (item1, item2))
        assert r1.status is CheckStatus.CONFIGURED and r2.status is CheckStatus.CONFIGURED
        (e1,) = r1.evidence
        (e2,) = r2.evidence
        assert e1.requirement_span == (0, 15)  # 5s must not leak into item 1
        assert e2.requirement_span == (16, 31)  # 3s must not leak into item 2
        assert r1.comparison_state is ComparisonState.DIFFERENT
        assert r2.comparison_state is ComparisonState.DIFFERENT

    def test_comma_separated_functions_in_one_sentence(self) -> None:
        item_a = make_item("a", "A功能延时", "A功能延时2s")
        item_b = make_item("b", "B功能延时", "B功能延时2s")
        block = make_block(0, [("A功能延时2s，B功能延时3s。", False)])
        ra, rb = verify(make_document(block), (item_a, item_b))
        assert ra.evidence[0].requirement_span == (0, 7)
        assert rb.evidence[0].requirement_span == (8, 15)

    def test_decimal_value_stays_inside_span(self) -> None:
        item = make_item("a", "A功能延时", "A功能延时2s")
        (evidence,) = verify_one(item, make_block(0, [("A功能延时2.5s。", False)])).evidence
        assert evidence.requirement_span == (0, 9)
        assert evidence.requirement_text == "A功能延时2.5s"

    def test_thousands_separator_stays_inside_span(self) -> None:
        item = make_item("a", "A功能延时", "A功能延时2s")
        (evidence,) = verify_one(item, make_block(0, [("A功能延时1,000ms。", False)])).evidence
        assert evidence.requirement_span == (0, 12)
        assert evidence.requirement_text == "A功能延时1,000ms"

    def test_phrase_at_paragraph_end_without_requirement(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        result = verify_one(item, make_block(0, [("系统说明如下。2门控制增加开关门延时", False)]))
        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is ComparisonState.NOT_COMPARED
        assert result.comparison_reason == "no-associated-requirement-content"
        (evidence,) = result.evidence
        assert evidence.matched_span == (7, 18)
        assert evidence.requirement_span == (7, 18)

    def test_multiple_plausible_values_are_not_grabbed(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        block = make_block(0, [("2门控制增加开关门延时，周期10ms，延时3s。", False)])
        result = verify_one(item, block)
        assert result.comparison_state is ComparisonState.NOT_COMPARED
        assert result.comparison_reason == "requirement-span-association-uncertain"

    def test_value_preceding_phrase_is_not_associated(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        result = verify_one(item, make_block(0, [("延时3s的2门控制增加开关门延时。", False)]))
        assert result.comparison_state is ComparisonState.NOT_COMPARED
        assert result.comparison_reason == "no-associated-requirement-content"
        (evidence,) = result.evidence
        assert evidence.matched_span == (5, 16)

    def test_association_never_crosses_blocks(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        b0 = make_block(0, [(PHRASE, False)])
        b1 = make_block(1, [("3s功能", False)])
        result = verify_one(item, b0, b1)
        (evidence,) = result.evidence
        assert evidence.requirement_span == (0, 11)  # nothing taken from block 1


class TestStrikeTruthTable:
    def test_fully_struck_requirement_is_struck_out(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        result = verify_one(item, make_block(0, [(DOC_SENTENCE, True)]))
        assert result.resolution is Resolution.RESOLVED
        assert result.status is CheckStatus.STRUCK_OUT
        assert result.comparison_state is ComparisonState.NOT_COMPARED
        assert result.comparison_reason == "evidence-struck"
        assert result.evidence[0].strike_coverage is StrikeCoverage.FULL

    def test_partial_strike_on_value_is_unresolved(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        result = verify_one(item, make_block(0, [(PHRASE, False), ("3s功能", True)]))
        assert result.resolution is Resolution.UNRESOLVED
        assert result.status is None
        assert "partial-strike" in result.review_reasons
        assert result.evidence[0].strike_coverage is StrikeCoverage.PARTIAL

    def test_struck_phrase_with_active_qualifier_is_unresolved(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        result = verify_one(item, make_block(0, [(PHRASE, True), ("3s功能", False)]))
        assert result.resolution is Resolution.UNRESOLVED
        assert "partial-strike" in result.review_reasons

    def test_unknown_formatting_is_unresolved(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        result = verify_one(item, make_block(0, [(DOC_SENTENCE, None)]))
        assert result.resolution is Resolution.UNRESOLVED
        assert "unknown-strike-formatting" in result.review_reasons
        assert result.evidence[0].strike_coverage is StrikeCoverage.UNKNOWN

    def test_active_and_struck_coexistence_is_unresolved(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        b0 = make_block(0, [(DOC_SENTENCE, False)])
        b1 = make_block(1, [(DOC_SENTENCE, True)])
        result = verify_one(item, b0, b1)
        assert result.resolution is Resolution.UNRESOLVED
        assert "active-and-struck-coexist" in result.review_reasons
        assert [e.strike_coverage for e in result.evidence] == [
            StrikeCoverage.NONE,
            StrikeCoverage.FULL,
        ]

    def test_strike_is_evaluated_over_span_not_whole_paragraph(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        block = make_block(0, [(DOC_SENTENCE + "。", False), ("无关内容", True)])
        result = verify_one(item, block)
        assert result.status is CheckStatus.CONFIGURED
        assert result.evidence[0].strike_coverage is StrikeCoverage.NONE


class TestRepeatedAndConflictingEvidence:
    def test_consistent_repeats_resolve_configured(self) -> None:
        item = make_item("dr-006", PHRASE, "2门控制增加开关门延时2s功能")
        b0 = make_block(0, [("2门控制增加开关门延时2s功能", False)])
        b1 = make_block(1, [("2门控制增加开关门延时2s功能", False)])
        result = verify_one(item, b0, b1)
        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is ComparisonState.SAME
        assert len(result.evidence) == 2  # both inspectable

    def test_conflicting_active_values_are_unresolved(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        b0 = make_block(0, [("2门控制增加开关门延时2s功能", False)])
        b1 = make_block(1, [("2门控制增加开关门延时3s功能", False)])
        result = verify_one(item, b0, b1)
        assert result.resolution is Resolution.UNRESOLVED
        assert result.status is None
        assert "conflicting-key-parameters" in result.review_reasons
        assert len(result.evidence) == 2  # both retained, neither dropped

    def test_bare_mention_plus_valued_occurrence(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        b0 = make_block(0, [(PHRASE, False)])  # bare mention
        b1 = make_block(1, [("2门控制增加开关门延时2s功能", False)])
        result = verify_one(item, b0, b1)
        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is ComparisonState.SAME
        assert result.evidence[0].comparison_blocker == "no-associated-requirement-content"
        assert result.evidence[1].comparison_blocker == ""

    def test_same_values_but_different_texts_is_mixed(self) -> None:
        item = make_item("dr-006", PHRASE, "2门控制增加开关门延时2s功能")
        b0 = make_block(0, [("2门控制增加开关门延时2s功能", False)])
        b1 = make_block(1, [("2门控制增加开关门延时2s功能（可选）。", False)])
        result = verify_one(item, b0, b1)
        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is ComparisonState.NOT_COMPARED
        assert result.comparison_reason == "mixed-comparison-occurrences"


class TestDescriptionComparison:
    def test_matching_description_is_same(self) -> None:
        item = make_item("dr-006", PHRASE, "2门控制增加开关门延时2s功能")
        result = verify_one(item, make_block(0, [("2门控制增加开关门延时2s功能", False)]))
        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is ComparisonState.SAME
        assert result.comparison_reason == ""

    def test_changed_value_is_configured_different(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        result = verify_one(item, make_block(0, [(DOC_SENTENCE, False)]))
        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is ComparisonState.DIFFERENT

    def test_empty_expected_description_is_not_compared(self) -> None:
        item = make_item("dr-006", PHRASE, "")
        result = verify_one(item, make_block(0, [(DOC_SENTENCE, False)]))
        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is ComparisonState.NOT_COMPARED
        assert result.comparison_reason == "expected-description-empty"

    def test_alias_hit_with_matching_text_is_same(self) -> None:
        item = make_item("dr-006", PHRASE, "两门延时功能2s", aliases=("两门延时功能",))
        result = verify_one(item, make_block(0, [("两门延时功能2s", False)]))
        assert result.status is CheckStatus.CONFIGURED
        assert result.comparison_state is ComparisonState.SAME  # text equality only

    def test_missing_has_nothing_to_compare(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        result = verify_one(item, make_block(0, [("无关内容", False)]))
        assert result.comparison_state is ComparisonState.NOT_COMPARED
        assert result.comparison_reason == "nothing-to-compare"

    def test_unresolved_result_is_not_compared(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        b0 = make_block(0, [(DOC_SENTENCE, False)])
        b1 = make_block(1, [(DOC_SENTENCE, True)])
        result = verify_one(item, b0, b1)
        assert result.comparison_state is ComparisonState.NOT_COMPARED
        assert result.comparison_reason == "result-unresolved"

    def test_same_evidence_three_comparison_outcomes(self) -> None:
        block = make_block(0, [(DOC_SENTENCE, False)])
        empty = make_item("i1", PHRASE, "")
        matching = make_item("i2", PHRASE, DOC_SENTENCE)
        differing = make_item("i3", PHRASE, EXPECTED)
        r1, r2, r3 = verify(make_document(block), (empty, matching, differing))
        assert [r.status for r in (r1, r2, r3)] == [CheckStatus.CONFIGURED] * 3
        assert [r.comparison_state for r in (r1, r2, r3)] == [
            ComparisonState.NOT_COMPARED,
            ComparisonState.SAME,
            ComparisonState.DIFFERENT,
        ]


class TestAmbiguousFunctionIdentity:
    def test_overlapping_phrases_across_items_are_unresolved(self) -> None:
        broad = make_item("broad", "门控制延时", "")
        specific = make_item("specific", "2门控制延时", "")
        block = make_block(0, [("具备2门控制延时功能", False)])
        r1, r2 = verify(make_document(block), (broad, specific))
        assert r1.resolution is Resolution.UNRESOLVED
        assert r2.resolution is Resolution.UNRESOLVED
        assert "ambiguous-function-identity" in r1.review_reasons
        assert "ambiguous-function-identity" in r2.review_reasons
        assert r1.evidence[0].ambiguous is True
        assert r2.evidence[0].ambiguous is True

    def test_identical_phrases_on_two_items_are_configuration_level(self) -> None:
        item1 = make_item("x", PHRASE, "")
        item2 = make_item("y", PHRASE, "")
        block = make_block(0, [(DOC_SENTENCE, False)])
        r1, r2 = verify(make_document(block), (item1, item2))
        # Duplicate configured text is a Task 5 baseline-validation concern;
        # verification resolves each item normally.
        assert (r1.resolution, r1.status) == (Resolution.RESOLVED, CheckStatus.CONFIGURED)
        assert (r2.resolution, r2.status) == (Resolution.RESOLVED, CheckStatus.CONFIGURED)
        assert r1.evidence[0].ambiguous is False

    def test_clean_evidence_elsewhere_resolves_despite_ambiguity(self) -> None:
        broad = make_item("broad", "门控制延时", "")
        specific = make_item("specific", "2门控制延时", "")
        b0 = make_block(0, [("具备2门控制延时功能", False)])  # ambiguous overlap
        b1 = make_block(1, [("门控制延时已单独说明", False)])  # clean for broad only
        r1, r2 = verify(make_document(b0, b1), (broad, specific))
        assert (r1.resolution, r1.status) == (Resolution.RESOLVED, CheckStatus.CONFIGURED)
        assert len(r1.evidence) == 2  # ambiguous evidence retained, not discarded
        assert [e.ambiguous for e in r1.evidence] == [True, False]
        assert (r2.resolution, r2.status) == (Resolution.UNRESOLVED, None)


class TestTruthTable:
    @pytest.mark.parametrize(
        ("blocks", "expected_resolution", "expected_status"),
        [
            ([make_block(0, [(DOC_SENTENCE, False)])], Resolution.RESOLVED, CheckStatus.CONFIGURED),
            ([make_block(0, [(DOC_SENTENCE, True)])], Resolution.RESOLVED, CheckStatus.STRUCK_OUT),
            ([make_block(0, [("无关内容", False)])], Resolution.RESOLVED, CheckStatus.MISSING),
            (
                [make_block(0, [(PHRASE, False), ("3s功能", True)])],
                Resolution.UNRESOLVED,
                None,
            ),
            ([make_block(0, [(DOC_SENTENCE, None)])], Resolution.UNRESOLVED, None),
            (
                [make_block(0, [(DOC_SENTENCE, False)]), make_block(1, [(DOC_SENTENCE, True)])],
                Resolution.UNRESOLVED,
                None,
            ),
            (
                [
                    make_block(0, [("2门控制增加开关门延时2s功能", False)]),
                    make_block(1, [("2门控制增加开关门延时3s功能", False)]),
                ],
                Resolution.UNRESOLVED,
                None,
            ),
        ],
    )
    def test_confirmed_classification_rules(
        self,
        blocks: list[DocumentBlock],
        expected_resolution: Resolution,
        expected_status: CheckStatus | None,
    ) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        result = verify_one(item, *blocks)
        assert result.resolution is expected_resolution
        assert result.status is expected_status
        assert result.rule_revision == "task3-v1"


class TestDeterminismAndOrdering:
    def test_repeated_runs_are_equal_and_source_ordered(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        blocks = tuple(make_block(index, [(DOC_SENTENCE, False)]) for index in range(4))
        document = make_document(*blocks)
        first = verify(document, (item,))
        second = verify(document, (item,))
        assert first == second
        (result,) = first
        spans = [e.matched_span for e in result.evidence]
        assert len(spans) == 4
        block_ids = [e.block_id for e in result.evidence]
        assert block_ids == ["body:p0", "body:p1", "body:p2", "body:p3"]

    def test_results_follow_input_item_order(self) -> None:
        block = make_block(0, [(DOC_SENTENCE, False)])
        items = tuple(make_item(f"item-{index}", PHRASE, "") for index in range(3))
        results = verify(make_document(block), items)
        assert [r.check_item.item_id for r in results] == ["item-0", "item-1", "item-2"]


class TestCancellation:
    def test_checkpoint_runs_once_per_item_and_block(self) -> None:
        calls = {"n": 0}

        def never_cancel() -> bool:
            calls["n"] += 1
            return False

        blocks = tuple(make_block(index, [("无关内容", False)]) for index in range(3))
        items = tuple(make_item(f"item-{index}", PHRASE, "") for index in range(2))
        results = verify(make_document(*blocks), items, cancel_check=never_cancel)
        assert len(results) == 2
        assert calls["n"] == 6  # one checkpoint per (item, block)

    def test_cancellation_stops_without_results(self) -> None:
        calls = {"n": 0}

        def cancel_after_five() -> bool:
            calls["n"] += 1
            return calls["n"] > 5

        blocks = tuple(make_block(index, [("无关内容", False)]) for index in range(3))
        items = tuple(make_item(f"item-{index}", PHRASE, "") for index in range(2))
        with pytest.raises(VerificationCancelled):
            verify(make_document(*blocks), items, cancel_check=cancel_after_five)
        assert calls["n"] == 6  # stopped at the first checkpoint after the request
