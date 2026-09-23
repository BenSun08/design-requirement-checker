"""Task 6 T6.3 — precise validation metrics.

Metric math is separated from report rendering and from the evaluation
harness. Every metric carries an explicit numerator and denominator; a
zero-denominator metric is ``N/A`` — never a misleading 100%.

Binary presence interpretation (documented against docs/domain-model.md and
docs/product-spec.md before implementation):

- ground-truth POSITIVE: expectedStatus CONFIGURED or STRUCK_OUT — the
  document evidence says the function's text is present (active or struck);
- ground-truth NEGATIVE: expectedStatus MISSING — no qualifying evidence in
  the checked scope;
- UNRESOLVED on either side NEVER counts as negative: it is a review
  condition with no status (domain model: "UNRESOLVED has no CheckStatus"),
  so it is excluded from the 2x2 table and reported separately
  (unresolved rate, expected-unresolved count).

This matches the product acceptance rule (product-spec.md §Production MVP
acceptance 8 and the fixture-set paragraph): report precision/recall, false
positives/negatives, strike accuracy, and the unresolved rate *separately*,
with denominators.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Ground-truth / prediction tokens treated as "presence positive".
POSITIVE_STATUSES = ("CONFIGURED", "STRUCK_OUT")
#: Token treated as "presence negative".
NEGATIVE_STATUS = "MISSING"


@dataclass(frozen=True)
class Metric:
    """One measured value with explicit numerator/denominator."""

    numerator: int
    denominator: int

    @property
    def value(self) -> float | None:
        if self.denominator == 0:
            return None
        return self.numerator / self.denominator

    @property
    def display(self) -> str:
        if self.denominator == 0:
            return "N/A (0/0)"
        percent = self.numerator / self.denominator * 100
        return f"{self.numerator}/{self.denominator} = {percent:.1f}%"

    def as_dict(self) -> dict[str, Any]:
        return {
            "numerator": self.numerator,
            "denominator": self.denominator,
            "value": self.value,
            "display": self.display,
        }


def _count(numerator: int, denominator: int) -> Metric:
    return Metric(numerator, denominator)


@dataclass(frozen=True)
class Metrics:
    """Computed Task 6 metrics for one validation run."""

    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return self.payload

    def render_text(self) -> str:
        """Human-readable rendering; metric math lives in compute_metrics."""
        lines: list[str] = []
        for group_name, group in self.payload.items():
            lines.append(f"[{group_name}]")
            for metric_name, entry in group.items():
                if isinstance(entry, dict) and "display" in entry:
                    lines.append(f"  {metric_name}: {entry['display']}")
                elif isinstance(entry, dict):
                    inner = ", ".join(f"{k}={v}" for k, v in entry.items())
                    lines.append(f"  {metric_name}: {inner}")
                else:
                    lines.append(f"  {metric_name}: {entry}")
        return "\n".join(lines)


def compute_metrics(results: dict[str, Any]) -> Metrics:
    """Compute all Task 6 metrics from harness result data.

    Only cases with ``includeInMetrics`` true enter the measurements;
    excluded cases are counted but never graded.
    """
    cases = [c for c in results.get("cases", []) if c.get("includeInMetrics", True)]
    excluded = [c for c in results.get("cases", []) if not c.get("includeInMetrics", True)]

    tp = tn = fp = fn = 0
    both_resolved = status_correct = 0
    observed_unresolved = expected_unresolved = 0
    strike_labelled = strike_correct = 0
    comparison_labelled = comparison_correct = 0

    for case in cases:
        expected = case["expected"]
        observed = case["observed"]
        correct = case["correct"]

        exp_res = expected["resolution"]
        obs_res = observed["resolution"]
        if exp_res == "UNRESOLVED":
            expected_unresolved += 1
        if obs_res == "UNRESOLVED":
            observed_unresolved += 1

        # Binary presence table: skip anything UNRESOLVED on either side.
        if exp_res == "RESOLVED" and obs_res == "RESOLVED":
            exp_positive = expected["status"] in POSITIVE_STATUSES
            obs_positive = observed["status"] in POSITIVE_STATUSES
            if exp_positive and obs_positive:
                tp += 1
            elif not exp_positive and not obs_positive:
                tn += 1
            elif not exp_positive and obs_positive:
                fp += 1
            else:
                fn += 1
            both_resolved += 1
            if correct["status"]:
                status_correct += 1

        if expected.get("strike") and observed.get("strike") not in (None, "NOT_EVALUATED"):
            strike_labelled += 1
            if correct["strike"]:
                strike_correct += 1

        if (
            expected.get("comparison")
            and obs_res == "RESOLVED"
            and observed.get("comparison") != "NOT_EVALUATED"
        ):
            comparison_labelled += 1
            if correct["comparison"]:
                comparison_correct += 1

    # Per-document coverage.
    documents = results.get("documents", [])
    doc_count = len(documents)
    limited_docs = sum(1 for d in documents if d.get("coverage") == "LIMITED")
    warned_docs = sum(1 for d in documents if d.get("coverageWarnings"))
    case_count = len(cases)
    limited_cases = sum(1 for c in cases if c["observed"].get("coverage") == "LIMITED")

    payload: dict[str, Any] = {
        "totals": {
            "includedCases": _count(case_count, case_count).as_dict(),
            "excludedCases": _count(len(excluded), case_count + len(excluded)).as_dict(),
        },
        "presence": {
            "definition": (
                "positive = CONFIGURED|STRUCK_OUT, negative = MISSING; "
                "UNRESOLVED excluded from the table and reported separately"
            ),
            "truePositive": _count(tp, tp + tn + fp + fn).as_dict(),
            "trueNegative": _count(tn, tp + tn + fp + fn).as_dict(),
            "falsePositive": _count(fp, tp + tn + fp + fn).as_dict(),
            "falseNegative": _count(fn, tp + tn + fp + fn).as_dict(),
            "precision": _count(tp, tp + fp).as_dict(),
            "recall": _count(tp, tp + fn).as_dict(),
        },
        "status": {
            "accuracy": _count(status_correct, both_resolved).as_dict(),
            "note": "exact status match among cases RESOLVED on both sides",
        },
        "unresolved": {
            "expectedUnresolved": _count(expected_unresolved, case_count).as_dict(),
            "observedUnresolved": _count(observed_unresolved, case_count).as_dict(),
            "unresolvedRate": _count(observed_unresolved, case_count).as_dict(),
        },
        "strike": {
            "accuracy": _count(strike_correct, strike_labelled).as_dict(),
            "note": "only cases with an independently labelled expectedStrike",
        },
        "comparison": {
            "accuracy": _count(comparison_correct, comparison_labelled).as_dict(),
            "note": "only cases with an independently labelled expectedComparison",
        },
        "coverage": {
            "limitedDocuments": _count(limited_docs, doc_count).as_dict(),
            "limitedCaseRate": _count(limited_cases, case_count).as_dict(),
            "unsupportedWarningDocumentRate": _count(warned_docs, doc_count).as_dict(),
        },
        "reviewTime": _review_time(results),
    }
    return Metrics(payload)


def _review_time(results: dict[str, Any]) -> dict[str, Any]:
    """Review-time change is reported ONLY from real measurement data.

    If no timing study has been recorded in the results, the value is
    explicitly NOT MEASURED — never inferred from subjective impressions.
    """
    timing = results.get("reviewTiming")
    if not timing:
        return {
            "status": "NOT MEASURED",
            "manualOnlySamples": 0,
            "toolAssistedSamples": 0,
            "note": "no real review-timing study has been recorded",
        }
    manual = timing.get("manualOnlySeconds", [])
    assisted = timing.get("toolAssistedSeconds", [])

    def _median(values: list[float]) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        mid = len(ordered) // 2
        if len(ordered) % 2:
            return float(ordered[mid])
        return (ordered[mid - 1] + ordered[mid]) / 2

    return {
        "status": "MEASURED",
        "manualOnlySamples": len(manual),
        "toolAssistedSamples": len(assisted),
        "manualOnlyMedianSeconds": _median(manual),
        "toolAssistedMedianSeconds": _median(assisted),
        "procedure": timing.get("procedure", ""),
    }
