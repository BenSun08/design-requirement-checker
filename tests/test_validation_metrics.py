"""Task 6 T6.3 — metric definition tests.

Every assertion checks independently expected numerators/denominators; no
expectation is derived by calling the metric code itself.
"""

from __future__ import annotations

from typing import Any

from validation.metrics import Metric, compute_metrics


def _case(
    expected_status: str | None,
    observed_status: str | None,
    *,
    expected_resolution: str = "RESOLVED",
    observed_resolution: str = "RESOLVED",
    expected_comparison: str | None = None,
    observed_comparison: str = "NOT_COMPARED",
    correct_comparison: bool | None = None,
    expected_strike: str | None = None,
    observed_strike: str = "NONE",
    correct_strike: bool | None = None,
    include: bool = True,
    coverage: str = "COMPLETE",
) -> dict[str, Any]:
    return {
        "documentId": "doc",
        "itemId": "item",
        "includeInMetrics": include,
        "exclusionReason": "" if include else "test exclusion",
        "expected": {
            "resolution": expected_resolution,
            "status": expected_status,
            "comparison": expected_comparison,
            "strike": expected_strike,
            "coverage": None,
        },
        "observed": {
            "resolution": observed_resolution,
            "status": observed_status,
            "comparison": observed_comparison,
            "strike": observed_strike,
            "coverage": coverage,
            "reviewReasons": [],
            "comparisonReason": "",
        },
        "correct": {
            "resolution": observed_resolution == expected_resolution,
            "status": observed_status == expected_status,
            "comparison": (
                observed_comparison == expected_comparison
                if correct_comparison is None
                else correct_comparison
            ),
            "strike": (
                observed_strike == expected_strike if correct_strike is None else correct_strike
            ),
        },
        "discrepancyCategory": "",
        "notes": "",
    }


def _payload(cases: list[dict[str, Any]], documents: list[dict[str, Any]] | None = None) -> dict:
    return compute_metrics({"cases": cases, "documents": documents or []}).as_dict()


# ---------------------------------------------------------------------------
# Metric primitive
# ---------------------------------------------------------------------------


def test_metric_zero_denominator_is_na() -> None:
    metric = Metric(0, 0)
    assert metric.value is None
    assert metric.display == "N/A (0/0)"


def test_metric_display_includes_denominator() -> None:
    assert Metric(49, 50).display == "49/50 = 98.0%"
    assert Metric(18, 20).display == "18/20 = 90.0%"
    assert Metric(7, 120).display == "7/120 = 5.8%"


# ---------------------------------------------------------------------------
# Presence precision / recall
# ---------------------------------------------------------------------------


def test_precision_recall_basic_counts() -> None:
    cases = [
        _case("CONFIGURED", "CONFIGURED"),  # TP
        _case("STRUCK_OUT", "STRUCK_OUT"),  # TP (struck text is still "present")
        _case("MISSING", "MISSING"),  # TN
        _case("MISSING", "CONFIGURED"),  # FP
        _case("CONFIGURED", "MISSING"),  # FN
    ]
    presence = _payload(cases)["presence"]
    assert presence["truePositive"]["numerator"] == 2
    assert presence["trueNegative"]["numerator"] == 1
    assert presence["falsePositive"]["numerator"] == 1
    assert presence["falseNegative"]["numerator"] == 1
    assert presence["precision"]["numerator"] == 2
    assert presence["precision"]["denominator"] == 3  # TP + FP
    assert presence["recall"]["numerator"] == 2
    assert presence["recall"]["denominator"] == 3  # TP + FN


def test_unresolved_never_counted_negative() -> None:
    """UNRESOLVED on either side is excluded from the binary presence table."""
    cases = [
        _case("CONFIGURED", "CONFIGURED"),
        _case("MISSING", "MISSING"),
        _case(None, None, expected_resolution="UNRESOLVED", observed_resolution="UNRESOLVED"),
        _case("CONFIGURED", None, observed_resolution="UNRESOLVED"),
        _case(None, "MISSING", expected_resolution="UNRESOLVED"),
    ]
    payload = _payload(cases)
    presence = payload["presence"]
    assert presence["truePositive"]["numerator"] == 1
    assert presence["trueNegative"]["numerator"] == 1
    assert presence["falsePositive"]["numerator"] == 0
    assert presence["falseNegative"]["numerator"] == 0
    unresolved = payload["unresolved"]
    assert unresolved["expectedUnresolved"]["numerator"] == 2
    assert unresolved["observedUnresolved"]["numerator"] == 2
    assert unresolved["unresolvedRate"]["denominator"] == 5


def test_zero_denominator_precision_not_100() -> None:
    """No predicted positives -> precision is N/A, not a perfect score."""
    payload = _payload([_case("CONFIGURED", "MISSING")])  # FN only
    presence = payload["presence"]
    assert presence["precision"]["display"] == "N/A (0/0)"
    assert presence["recall"]["numerator"] == 0
    assert presence["recall"]["denominator"] == 1


# ---------------------------------------------------------------------------
# Status / strike / comparison accuracy
# ---------------------------------------------------------------------------


def test_status_accuracy_only_resolved_both_sides() -> None:
    cases = [
        _case("CONFIGURED", "STRUCK_OUT"),  # wrong status, both resolved
        _case("MISSING", "MISSING"),  # correct
        _case(None, None, expected_resolution="UNRESOLVED", observed_resolution="UNRESOLVED"),
    ]
    status = _payload(cases)["status"]
    assert status["accuracy"]["numerator"] == 1
    assert status["accuracy"]["denominator"] == 2


def test_strike_accuracy_only_counts_labelled() -> None:
    cases = [
        _case("CONFIGURED", "CONFIGURED", expected_strike="NONE"),
        _case("STRUCK_OUT", "STRUCK_OUT", expected_strike="FULL", observed_strike="FULL"),
        _case("MISSING", "MISSING", expected_strike="PARTIAL", observed_strike="PARTIAL"),
        _case(
            "MISSING",
            "MISSING",
            expected_strike="PARTIAL",
            observed_strike="NONE",
            correct_strike=False,
        ),
        _case("MISSING", "MISSING"),  # strike not labelled -> excluded
    ]
    strike = _payload(cases)["strike"]
    assert strike["accuracy"]["numerator"] == 3
    assert strike["accuracy"]["denominator"] == 4


def test_comparison_accuracy_only_counts_labelled() -> None:
    cases = [
        _case(
            "CONFIGURED",
            "CONFIGURED",
            expected_comparison="DIFFERENT",
            observed_comparison="DIFFERENT",
        ),
        _case(
            "CONFIGURED",
            "CONFIGURED",
            expected_comparison="SAME",
            observed_comparison="DIFFERENT",
            correct_comparison=False,
        ),
        _case("MISSING", "MISSING"),  # not labelled
        # labelled but observed UNRESOLVED -> comparison not evaluated
        _case(
            None,
            None,
            expected_resolution="UNRESOLVED",
            observed_resolution="UNRESOLVED",
            expected_comparison="SAME",
            observed_comparison="NOT_COMPARED",
            correct_comparison=False,
        ),
    ]
    comparison = _payload(cases)["comparison"]
    assert comparison["accuracy"]["numerator"] == 1
    assert comparison["accuracy"]["denominator"] == 2


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


def test_coverage_metrics_per_document_and_per_case() -> None:
    cases = [
        _case("MISSING", "MISSING", coverage="LIMITED"),
        _case("MISSING", "MISSING", coverage="LIMITED"),
        _case("MISSING", "MISSING", coverage="COMPLETE"),
    ]
    documents = [
        {"documentId": "d1", "coverage": "LIMITED", "coverageWarnings": ["tracked-revisions"]},
        {"documentId": "d2", "coverage": "COMPLETE", "coverageWarnings": []},
        {"documentId": "d3", "coverage": "LIMITED", "coverageWarnings": ["text-box"]},
    ]
    coverage = _payload(cases, documents)["coverage"]
    assert coverage["limitedDocuments"]["numerator"] == 2
    assert coverage["limitedDocuments"]["denominator"] == 3
    assert coverage["unsupportedWarningDocumentRate"]["numerator"] == 2
    assert coverage["limitedCaseRate"]["numerator"] == 2
    assert coverage["limitedCaseRate"]["denominator"] == 3


def test_coverage_zero_documents_is_na() -> None:
    coverage = _payload([])["coverage"]
    assert coverage["limitedDocuments"]["display"] == "N/A (0/0)"


# ---------------------------------------------------------------------------
# Exclusion and totals
# ---------------------------------------------------------------------------


def test_excluded_cases_do_not_enter_metrics() -> None:
    cases = [
        _case("CONFIGURED", "CONFIGURED"),
        _case("CONFIGURED", "MISSING", include=False),
    ]
    payload = _payload(cases)
    assert payload["totals"]["includedCases"]["numerator"] == 1
    assert payload["totals"]["excludedCases"]["numerator"] == 1
    assert payload["presence"]["falseNegative"]["numerator"] == 0


# ---------------------------------------------------------------------------
# Review time
# ---------------------------------------------------------------------------


def test_review_time_not_measured_without_evidence() -> None:
    review = _payload([_case("MISSING", "MISSING")])["reviewTime"]
    assert review["status"] == "NOT MEASURED"
    assert review["manualOnlySamples"] == 0


def test_review_time_uses_only_recorded_measurements() -> None:
    results = {
        "cases": [_case("MISSING", "MISSING")],
        "documents": [],
        "reviewTiming": {
            "manualOnlySeconds": [600, 400, 500],
            "toolAssistedSeconds": [120, 180],
            "procedure": "stopwatch study, 3 engineers",
        },
    }
    review = compute_metrics(results).as_dict()["reviewTime"]
    assert review["status"] == "MEASURED"
    assert review["manualOnlySamples"] == 3
    assert review["toolAssistedSamples"] == 2
    assert review["manualOnlyMedianSeconds"] == 500.0
    assert review["toolAssistedMedianSeconds"] == 150.0


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def test_render_text_shows_denominators() -> None:
    metrics = compute_metrics({"cases": [_case("CONFIGURED", "CONFIGURED")], "documents": []})
    text = metrics.render_text()
    assert "1/1 = 100.0%" in text
    assert "N/A (0/0)" in text  # strike/comparison unlabelled
