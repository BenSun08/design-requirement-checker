"""S6 spike evidence: deterministic detection, normalization, spans and classification.

All expected spans, tokens, statuses and reasons below are independent labels
derived by hand from docs/product-spec.md, docs/domain-model.md and the S6
allowlist design — never copied from probe output. Raw offsets are zero-based
half-open code-point ranges over the fixture strings written here.
"""

from pathlib import Path

import fixture_factory as fixtures
import pytest
from s6_probe import (
    make_block,
    make_item,
    normalize,
    verify,
)

from design_requirement_checker.docx_adapter import read_document

PHRASE = "2门控制增加开关门延时"
EXPECTED = "2门控制增加开关门延时2s功能"
DOC_SENTENCE = "2门控制增加开关门延时3s功能"


def one(item, *blocks):  # type: ignore[no-untyped-def]
    results = verify([item], list(blocks))
    assert len(results) == 1
    return results[0]


class TestNormalizationAllowlist:
    def test_whitespace_runs_collapse_to_single_space(self) -> None:
        assert normalize("A  B").text == "A B"
        assert normalize("A  B").char_sources == ((0, 1), (1, 3), (3, 4))
        # tab + ideographic space + ASCII space form one collapsed run
        assert normalize("A\t　 B").text == "A B"
        assert normalize("A\t　 B").char_sources == ((0, 1), (1, 4), (4, 5))

    def test_line_breaks_within_block_become_space(self) -> None:
        result = normalize("A\nB\r\nC")
        assert result.text == "A B C"
        assert result.char_sources == ((0, 1), (1, 2), (2, 3), (3, 5), (5, 6))

    def test_fullwidth_ascii_punctuation_maps_one_to_one(self) -> None:
        result = normalize("（：；，？！．）")
        assert result.text == "(:;,?!.)"
        assert result.char_sources == tuple((i, i + 1) for i in range(8))

    def test_rejected_transformations_stay_verbatim(self) -> None:
        # R1 ideographic full stop, R2 fullwidth digits/letters, R3 case.
        assert normalize("。").text == "。"
        assert normalize("２s").text == "２s"
        assert normalize("ＣＡＮ１").text == "ＣＡＮ１"
        assert normalize("CAN1").text == "CAN1"
        assert normalize("can1").text == "can1"

    def test_engineering_meaning_is_preserved(self) -> None:
        # None of these pairs may become equal under the allowlist.
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
        # monotonic, non-overlapping, covering every raw code point exactly once
        assert sources[0][0] == 0
        assert sources[-1][1] == len(raw)
        for prev, cur in zip(sources, sources[1:]):
            assert prev[1] == cur[0]


class TestRawNormalizedOffsetMapping:
    def test_exact_span_maps_identity(self) -> None:
        result = normalize(DOC_SENTENCE)
        assert result.char_sources == tuple((i, i + 1) for i in range(15))
        # phrase occupies normalized [0, 11) -> raw (0, 11)
        from s6_probe import map_span

        assert map_span(result, 0, 11) == (0, 11)

    def test_normalized_span_maps_across_collapsed_whitespace(self) -> None:
        raw = "2门控制增加开关门延时\t3s功能"
        result = normalize(raw)
        assert result.text == "2门控制增加开关门延时 3s功能"
        from s6_probe import map_span

        # normalized term 延时+space+3s occupies normalized [9, 14) -> raw (9, 14)
        assert map_span(result, 9, 14) == (9, 14)
        assert raw[9:14] == "延时\t3s"

    def test_normalized_match_over_punctuation_and_line_break(self) -> None:
        raw = "（延时\n2s）"
        result = normalize(raw)
        assert result.text == "(延时 2s)"
        from s6_probe import map_span

        assert map_span(result, 0, 7) == (0, 7)

    def test_collapsed_run_maps_to_whole_raw_run(self) -> None:
        from s6_probe import map_span

        result = normalize("A  B")
        assert map_span(result, 0, 3) == (0, 4)


class TestDetectionPhraseBehaviour:
    def test_exact_phrase_present_qualifies(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED, name="2门控制延时")
        block = make_block(0, [(DOC_SENTENCE, False)])
        result = one(item, block)
        assert result.resolution == "RESOLVED"
        assert result.status == "CONFIGURED"
        assert result.comparison_state == "DIFFERENT"
        (occ,) = result.occurrences
        assert occ.term == PHRASE
        assert occ.term_kind == "detection-phrase"
        assert occ.match_type == "EXACT"
        assert occ.raw_match_span == (0, 11)
        assert occ.raw_requirement_span == (0, 15)
        assert occ.value_tokens == frozenset({"3s"})
        assert occ.strike_coverage == "NONE"
        assert occ.ambiguous is False

    def test_phrase_absent_is_missing(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        block = make_block(0, [("1门控制增加开关门延时3s功能", False)])
        result = one(item, block)
        assert result.resolution == "RESOLVED"
        assert result.status == "MISSING"
        assert result.occurrences == ()
        assert result.comparison_state == "NOT_COMPARED"

    def test_broad_related_wording_not_accepted(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        block = make_block(0, [("本车具备2门控制相关功能，详见附录。", False)])
        assert one(item, block).status == "MISSING"

    def test_similar_neighbouring_function_not_accepted(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        b0 = make_block(0, [("2门控制增加开门延时3s功能", False)])  # 开门, not 开关门
        b1 = make_block(1, [("2门控制增加开关延时3s功能", False)])  # 开关, not 开关门
        result = one(item, b0, b1)
        assert result.status == "MISSING"
        assert result.occurrences == ()

    def test_display_name_is_not_a_detector(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED, name="2门控制延时")
        block = make_block(0, [("支持2门控制延时。", False)])  # display name only
        assert one(item, block).status == "MISSING"


class TestAliases:
    def test_alias_hit_establishes_identity(self) -> None:
        item = make_item("dr-006", PHRASE, "", aliases=("两门延时功能",))
        block = make_block(0, [("两门延时功能，延时3s。", False)])
        result = one(item, block)
        assert result.status == "CONFIGURED"
        (occ,) = result.occurrences
        assert occ.term == "两门延时功能"
        assert occ.term_kind == "alias"
        assert occ.match_type == "ALIAS"

    def test_alias_does_not_imply_description_equality(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED, aliases=("两门延时功能",))
        block = make_block(0, [("两门延时功能3s", False)])
        result = one(item, block)
        assert result.status == "CONFIGURED"
        assert result.comparison_state == "DIFFERENT"  # never auto-SAME from an alias

    def test_multiple_aliases_are_retained(self) -> None:
        item = make_item("dr-006", PHRASE, "", aliases=("两门延时功能", "双门延时"))
        b0 = make_block(0, [("两门延时功能3s", False)])
        b1 = make_block(1, [("双门延时3s", False)])
        result = one(item, b0, b1)
        assert result.status == "CONFIGURED"
        assert [o.term for o in result.occurrences] == ["两门延时功能", "双门延时"]

    def test_alias_and_canonical_in_same_document(self) -> None:
        item = make_item("dr-006", PHRASE, "", aliases=("两门延时功能",))
        b0 = make_block(0, [(DOC_SENTENCE, False)])
        b1 = make_block(1, [("两门延时功能3s", False)])
        result = one(item, b0, b1)
        assert result.status == "CONFIGURED"
        assert [(o.term, o.term_kind, o.match_type) for o in result.occurrences] == [
            (PHRASE, "detection-phrase", "EXACT"),
            ("两门延时功能", "alias", "ALIAS"),
        ]


class TestRequirementSpanAssociation:
    def test_value_in_same_clause_associates(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        block = make_block(0, [(DOC_SENTENCE, False)])
        (occ,) = one(item, block).occurrences
        assert occ.raw_requirement_span == (0, 15)
        assert occ.value_tokens == frozenset({"3s"})

    def test_value_after_comma_is_not_associated(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        block = make_block(0, [("2门控制增加开关门延时，延时时间为3s。", False)])
        result = one(item, block)
        assert result.status == "CONFIGURED"
        assert result.comparison_state == "NOT_COMPARED"
        assert result.comparison_reason == "requirement-span-association-uncertain"
        (occ,) = result.occurrences
        assert occ.raw_requirement_span == (0, 11)
        assert occ.value_tokens == frozenset()

    def test_semicolon_separated_requirements_do_not_cross_associate(self) -> None:
        item1 = make_item("dr-006", PHRASE, "2门控制增加开关门延时2s功能")
        item2 = make_item("dr-007", "1门控制增加开关门延时", "1门控制增加开关门延时2s功能")
        block = make_block(0, [("2门控制增加开关门延时3s功能；1门控制增加开关门延时5s功能", False)])
        r1, r2 = verify([item1, item2], [block])
        assert r1.status == "CONFIGURED" and r2.status == "CONFIGURED"
        (o1,) = r1.occurrences
        (o2,) = r2.occurrences
        assert o1.raw_requirement_span == (0, 15)
        assert o1.value_tokens == frozenset({"3s"})  # 5s must not leak into item 1
        assert o2.raw_requirement_span == (16, 31)
        assert o2.value_tokens == frozenset({"5s"})  # 3s must not leak into item 2
        assert r1.comparison_state == "DIFFERENT" and r2.comparison_state == "DIFFERENT"

    def test_comma_separated_functions_in_one_sentence(self) -> None:
        item_a = make_item("a", "A功能延时", "A功能延时2s")
        item_b = make_item("b", "B功能延时", "B功能延时2s")
        block = make_block(0, [("A功能延时2s，B功能延时3s。", False)])
        ra, rb = verify([item_a, item_b], [block])
        (oa,) = ra.occurrences
        (ob,) = rb.occurrences
        assert oa.raw_requirement_span == (0, 7)
        assert oa.value_tokens == frozenset({"2s"})
        assert ob.raw_requirement_span == (8, 15)
        assert ob.value_tokens == frozenset({"3s"})
        # single-item configuration keeps the same boundary behaviour
        (ra_only,) = verify([item_a], [block])
        assert ra_only.occurrences[0].raw_requirement_span == (0, 7)

    def test_repeated_phrase_with_different_values_conflicts(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        b0 = make_block(0, [("2门控制增加开关门延时2s功能", False)])
        b1 = make_block(1, [("2门控制增加开关门延时3s功能", False)])
        result = one(item, b0, b1)
        assert result.resolution == "UNRESOLVED"
        assert result.status is None
        assert "conflicting-key-parameters" in result.reasons
        assert len(result.occurrences) == 2  # both retained, neither dropped

    def test_phrase_at_paragraph_end_without_requirement(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        block = make_block(0, [("系统说明如下。2门控制增加开关门延时", False)])
        result = one(item, block)
        assert result.status == "CONFIGURED"
        assert result.comparison_state == "NOT_COMPARED"
        assert result.comparison_reason == "no-associated-requirement-content"
        (occ,) = result.occurrences
        assert occ.raw_match_span == (7, 18)
        assert occ.raw_requirement_span == (7, 18)

    def test_multiple_plausible_values_are_not_grabbed(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        block = make_block(0, [("2门控制增加开关门延时，周期10ms，延时3s。", False)])
        result = one(item, block)
        assert result.comparison_state == "NOT_COMPARED"
        assert result.comparison_reason == "requirement-span-association-uncertain"
        (occ,) = result.occurrences
        assert occ.value_tokens == frozenset()  # neither 10ms nor 3s was seized

    def test_value_preceding_phrase_is_not_associated(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        block = make_block(0, [("延时3s的2门控制增加开关门延时。", False)])
        result = one(item, block)
        assert result.comparison_state == "NOT_COMPARED"
        assert result.comparison_reason == "no-associated-requirement-content"
        (occ,) = result.occurrences
        assert occ.raw_match_span == (5, 16)
        assert occ.value_tokens == frozenset()  # the earlier 3s was not seized

    def test_decimal_value_stays_inside_span(self) -> None:
        item = make_item("a", "A功能延时", "A功能延时2s")
        block = make_block(0, [("A功能延时2.5s。", False)])
        (occ,) = one(item, block).occurrences
        assert occ.raw_requirement_span == (0, 9)
        assert occ.value_tokens == frozenset({"2.5s"})


class TestStrikeEvaluation:
    def test_fully_struck_requirement_is_struck_out(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        block = make_block(0, [(DOC_SENTENCE, True)])
        result = one(item, block)
        assert result.resolution == "RESOLVED"
        assert result.status == "STRUCK_OUT"
        assert result.comparison_state == "NOT_COMPARED"
        assert result.comparison_reason == "evidence-struck"
        assert result.occurrences[0].strike_coverage == "FULL"

    def test_partial_strike_on_value_is_unresolved(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        block = make_block(0, [(PHRASE, False), ("3s功能", True)])
        result = one(item, block)
        assert result.resolution == "UNRESOLVED"
        assert result.status is None
        assert "partial-strike" in result.reasons
        assert result.occurrences[0].strike_coverage == "PARTIAL"

    def test_struck_phrase_with_active_qualifier_is_unresolved(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        block = make_block(0, [(PHRASE, True), ("3s功能", False)])
        result = one(item, block)
        assert result.resolution == "UNRESOLVED"
        assert "partial-strike" in result.reasons

    def test_unknown_formatting_is_unresolved(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        block = make_block(0, [(DOC_SENTENCE, None)])
        result = one(item, block)
        assert result.resolution == "UNRESOLVED"
        assert "unknown-strike-formatting" in result.reasons

    def test_active_and_struck_coexistence_is_unresolved(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        b0 = make_block(0, [(DOC_SENTENCE, False)])
        b1 = make_block(1, [(DOC_SENTENCE, True)])
        result = one(item, b0, b1)
        assert result.resolution == "UNRESOLVED"
        assert "active-and-struck-coexist" in result.reasons
        assert [o.strike_coverage for o in result.occurrences] == ["NONE", "FULL"]

    def test_strike_is_evaluated_over_span_not_whole_paragraph(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        block = make_block(0, [(DOC_SENTENCE + "。", False), ("无关内容", True)])
        result = one(item, block)
        assert result.status == "CONFIGURED"  # struck text outside the span is irrelevant
        assert result.occurrences[0].strike_coverage == "NONE"


class TestRepeatedEvidence:
    def test_consistent_repeats_resolve_configured(self) -> None:
        item = make_item("dr-006", PHRASE, "2门控制增加开关门延时2s功能")
        b0 = make_block(0, [("2门控制增加开关门延时2s功能", False)])
        b1 = make_block(1, [("2门控制增加开关门延时2s功能", False)])
        result = one(item, b0, b1)
        assert result.status == "CONFIGURED"
        assert result.comparison_state == "SAME"
        assert len(result.occurrences) == 2  # both inspectable

    def test_bare_mention_plus_valued_occurrence(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        b0 = make_block(0, [(PHRASE, False)])  # bare mention, no requirement content
        b1 = make_block(1, [("2门控制增加开关门延时2s功能", False)])
        result = one(item, b0, b1)
        assert result.status == "CONFIGURED"  # no value conflict
        assert result.comparison_state == "SAME"  # decided by the comparable occurrence
        assert result.occurrences[0].comparison_blocker == "no-associated-requirement-content"
        assert result.occurrences[1].comparison_blocker == ""

    def test_same_values_but_different_texts_is_mixed(self) -> None:
        item = make_item("dr-006", PHRASE, "2门控制增加开关门延时2s功能")
        b0 = make_block(0, [("2门控制增加开关门延时2s功能", False)])
        b1 = make_block(1, [("2门控制增加开关门延时2s功能（可选）。", False)])
        result = one(item, b0, b1)
        assert result.status == "CONFIGURED"  # values agree
        assert result.comparison_state == "NOT_COMPARED"  # texts disagree
        assert result.comparison_reason == "mixed-comparison-occurrences"


class TestTruthTable:
    @pytest.mark.parametrize(
        ("blocks", "expected_resolution", "expected_status"),
        [
            ([make_block(0, [(DOC_SENTENCE, False)])], "RESOLVED", "CONFIGURED"),
            ([make_block(0, [(DOC_SENTENCE, True)])], "RESOLVED", "STRUCK_OUT"),
            ([make_block(0, [("无关内容", False)])], "RESOLVED", "MISSING"),
            ([make_block(0, [(PHRASE, False), ("3s功能", True)])], "UNRESOLVED", None),
            ([make_block(0, [(DOC_SENTENCE, None)])], "UNRESOLVED", None),
            (
                [make_block(0, [(DOC_SENTENCE, False)]), make_block(1, [(DOC_SENTENCE, True)])],
                "UNRESOLVED",
                None,
            ),
            (
                [
                    make_block(0, [("2门控制增加开关门延时2s功能", False)]),
                    make_block(1, [("2门控制增加开关门延时3s功能", False)]),
                ],
                "UNRESOLVED",
                None,
            ),
        ],
    )
    def test_confirmed_classification_rules(
        self, blocks: list, expected_resolution: str, expected_status: str | None
    ) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        result = one(item, *blocks)
        assert result.resolution == expected_resolution
        assert result.status == expected_status


class TestDescriptionComparison:
    def test_matching_description_is_same(self) -> None:
        item = make_item("dr-006", PHRASE, "2门控制增加开关门延时2s功能")
        block = make_block(0, [("2门控制增加开关门延时2s功能", False)])
        result = one(item, block)
        assert (result.status, result.comparison_state, result.comparison_reason) == (
            "CONFIGURED",
            "SAME",
            "",
        )

    def test_changed_value_is_configured_different(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        block = make_block(0, [(DOC_SENTENCE, False)])
        result = one(item, block)
        assert (result.status, result.comparison_state) == ("CONFIGURED", "DIFFERENT")

    def test_empty_expected_description_is_not_compared(self) -> None:
        item = make_item("dr-006", PHRASE, "")
        block = make_block(0, [(DOC_SENTENCE, False)])
        result = one(item, block)
        assert result.status == "CONFIGURED"
        assert result.comparison_state == "NOT_COMPARED"
        assert result.comparison_reason == "expected-description-empty"

    def test_alias_hit_with_matching_text_is_same(self) -> None:
        item = make_item("dr-006", PHRASE, "两门延时功能2s", aliases=("两门延时功能",))
        block = make_block(0, [("两门延时功能2s", False)])
        result = one(item, block)
        assert result.status == "CONFIGURED"
        assert result.comparison_state == "SAME"  # text equality, independent of alias

    def test_missing_has_nothing_to_compare(self) -> None:
        item = make_item("dr-006", PHRASE, EXPECTED)
        result = one(item, make_block(0, [("无关内容", False)]))
        assert result.comparison_state == "NOT_COMPARED"
        assert result.comparison_reason == "nothing-to-compare"


class TestDetectionResolutionComparisonIndependence:
    def test_same_evidence_three_comparison_outcomes(self) -> None:
        block = make_block(0, [(DOC_SENTENCE, False)])
        empty = make_item("i1", PHRASE, "")
        matching = make_item("i2", PHRASE, DOC_SENTENCE)
        differing = make_item("i3", PHRASE, EXPECTED)
        r1, r2, r3 = verify([empty, matching, differing], [block])
        # identical detection and status; only the comparison dimension changes
        assert [r.status for r in (r1, r2, r3)] == ["CONFIGURED"] * 3
        assert [r.comparison_state for r in (r1, r2, r3)] == [
            "NOT_COMPARED",
            "SAME",
            "DIFFERENT",
        ]

    def test_no_score_or_confidence_is_produced(self) -> None:
        import dataclasses

        from s6_probe import S6Result

        field_names = {f.name for f in dataclasses.fields(S6Result)}
        assert not field_names & {"score", "confidence", "similarity"}


class TestAmbiguousFunctionIdentity:
    def test_overlapping_phrases_across_items_are_unresolved(self) -> None:
        item1 = make_item("broad", "门控制延时", "")
        item2 = make_item("specific", "2门控制延时", "")
        block = make_block(0, [("具备2门控制延时功能", False)])
        r1, r2 = verify([item1, item2], [block])
        assert r1.resolution == "UNRESOLVED" and r2.resolution == "UNRESOLVED"
        assert "ambiguous-function-identity" in r1.reasons
        assert "ambiguous-function-identity" in r2.reasons
        assert r1.occurrences[0].ambiguous is True
        assert r2.occurrences[0].ambiguous is True

    def test_identical_phrases_on_two_items_are_configuration_level(self) -> None:
        item1 = make_item("x", PHRASE, "")
        item2 = make_item("y", PHRASE, "")
        block = make_block(0, [(DOC_SENTENCE, False)])
        r1, r2 = verify([item1, item2], [block])
        # The text genuinely contains the phrase for both items, so there is no
        # textual interpretation ambiguity. Duplicate detection phrases are a
        # checklist configuration defect that baseline validation (Task 5) must
        # flag; verification itself resolves each item normally.
        assert (r1.resolution, r1.status) == ("RESOLVED", "CONFIGURED")
        assert (r2.resolution, r2.status) == ("RESOLVED", "CONFIGURED")
        assert r1.occurrences[0].ambiguous is False

    def test_non_overlapping_matches_in_one_block_resolve(self) -> None:
        item_a = make_item("a", "A功能", "")
        item_b = make_item("b", "B功能", "")
        block = make_block(0, [("A功能与B功能并存", False)])
        ra, rb = verify([item_a, item_b], [block])
        assert ra.status == "CONFIGURED" and rb.status == "CONFIGURED"
        assert ra.occurrences[0].ambiguous is False

    def test_clean_evidence_elsewhere_resolves_despite_ambiguity(self) -> None:
        item1 = make_item("broad", "门控制延时", "")
        item2 = make_item("specific", "2门控制延时", "")
        b0 = make_block(0, [("具备2门控制延时功能", False)])  # ambiguous overlap
        b1 = make_block(1, [("门控制延时已单独说明", False)])  # clean for item1 only
        r1, r2 = verify([item1, item2], [b0, b1])
        assert (r1.resolution, r1.status) == ("RESOLVED", "CONFIGURED")
        assert len(r1.occurrences) == 2
        assert [o.ambiguous for o in r1.occurrences] == [True, False]
        assert (r2.resolution, r2.status) == ("UNRESOLVED", None)
        assert "ambiguous-function-identity" in r2.reasons


@pytest.fixture(scope="module")
def requirement_strike(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return fixtures.build_requirement_strike(
        tmp_path_factory.mktemp("s6-docx") / "requirement-strike.docx"
    )


class TestDocxComposition:
    def test_rules_compose_with_real_ingestion(self, requirement_strike: Path) -> None:
        document = read_document(requirement_strike)
        assert document.coverage.name == "COMPLETE"
        items = [
            make_item("a", "A功能增加延时", "A功能增加延时2s"),
            make_item("b", "B功能增加延时", "B功能增加延时2s"),
            make_item("c", "C功能增加延时", "C功能增加延时2s"),
        ]
        results = verify(items, list(document.blocks))
        by_id = {r.item_id: r for r in results}
        assert (by_id["a"].status, by_id["a"].comparison_state) == ("CONFIGURED", "DIFFERENT")
        assert by_id["b"].resolution == "UNRESOLVED"
        assert "partial-strike" in by_id["b"].reasons
        assert by_id["c"].status == "STRUCK_OUT"
        assert by_id["c"].comparison_reason == "evidence-struck"
