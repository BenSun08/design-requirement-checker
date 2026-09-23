"""Task 6 T6.2 — deterministic historical-validation harness.

Evaluates the *production* checker (``import_document`` -> ``verify_document``)
against independently labelled ground truth and records per-case comparison
data. Matching logic is never duplicated here: the only production entry
points used are the application use cases and the baseline store loader.

The harness is pure evaluation tooling (validation/), not product runtime.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from design_requirement_checker.application import (
    ImportFailure,
    VerificationState,
    import_document,
    load_baseline_from,
    verify_document,
)
from design_requirement_checker.domain import RULE_REVISION, CheckResult
from validation.schema import (
    DocumentLabels,
    ValidationManifest,
    load_document_labels,
    load_manifest,
)

#: Sentinel for "this dimension was not evaluated" (not labelled, or not
#: applicable given the observed/expected resolution).
NOT_EVALUATED = "NOT_EVALUATED"


def _token(value: str) -> str:
    """Convert a domain enum value (e.g. ``struck-out``) to the stable
    uppercase validation token (``STRUCK_OUT``)."""
    return value.upper().replace("-", "_")


@dataclass(frozen=True)
class CaseRecord:
    """One (document, item) comparison between ground truth and prediction."""

    document_id: str
    item_id: str
    include_in_metrics: bool
    exclusion_reason: str
    expected_resolution: str
    expected_status: str | None
    expected_comparison: str | None
    expected_strike: str | None
    expected_coverage: str | None
    observed_resolution: str
    observed_status: str | None
    observed_comparison: str
    observed_strike: str
    observed_coverage: str
    observed_review_reasons: tuple[str, ...]
    observed_comparison_reason: str
    correct_resolution: bool
    correct_status: bool
    correct_comparison: bool
    correct_strike: bool
    notes: str


def _observed_strike(result: CheckResult) -> str:
    """Derive the observed strike condition of a result for comparison.

    This is a presentation of evidence, not a new classification: MISSING has
    no evidence, STRUCK_OUT means every qualifying occurrence is fully struck,
    CONFIGURED means active evidence, and UNRESOLVED reports the primary
    evidence's coverage when available.
    """
    if result.status is not None:
        if result.status.value == "missing":
            return "NONE"
        if result.status.value == "struck-out":
            return "FULL"
        if result.status.value == "configured":
            return "NONE"
    if result.evidence:
        primary = next(
            (e for e in result.evidence if e.evidence_id == result.primary_evidence_id),
            result.evidence[0],
        )
        return primary.strike_coverage.value.upper()
    return NOT_EVALUATED


def compare_case(
    labels: DocumentLabels,
    label_item_id: str,
    expected_by_item: dict[str, Any],
    results_by_item: dict[str, CheckResult],
    observed_coverage: str,
) -> CaseRecord:
    """Compare one independent label with the production prediction."""
    label = expected_by_item[label_item_id]
    result = results_by_item.get(label_item_id)
    if result is None:
        # The item was not part of the verification (e.g. disabled in the
        # baseline). Record an explicit non-result instead of guessing.
        observed_resolution = "NOT_VERIFIED"
        observed_status = None
        observed_comparison = NOT_EVALUATED
        observed_strike = NOT_EVALUATED
    else:
        observed_resolution = _token(result.resolution.value)
        observed_status = _token(result.status.value) if result.status else None
        observed_comparison = _token(result.comparison_state.value)
        observed_strike = _observed_strike(result)

    correct_resolution = observed_resolution == label.expected_resolution
    # Status is only meaningful when both sides are RESOLVED.
    if label.expected_resolution == "RESOLVED" and observed_resolution == "RESOLVED":
        correct_status = observed_status == label.expected_status
    else:
        correct_status = correct_resolution
    # Comparison is only evaluated when independently labelled.
    if label.expected_comparison is not None and observed_resolution == "RESOLVED":
        correct_comparison = observed_comparison == label.expected_comparison
    else:
        correct_comparison = True
    # Strike is only evaluated when independently labelled.
    if label.expected_strike is not None and observed_strike != NOT_EVALUATED:
        correct_strike = observed_strike == label.expected_strike
    else:
        correct_strike = True

    return CaseRecord(
        document_id=labels.document_id,
        item_id=label_item_id,
        include_in_metrics=label.include_in_metrics,
        exclusion_reason=label.exclusion_reason,
        expected_resolution=label.expected_resolution,
        expected_status=label.expected_status,
        expected_comparison=label.expected_comparison,
        expected_strike=label.expected_strike,
        expected_coverage=label.expected_coverage,
        observed_resolution=observed_resolution,
        observed_status=observed_status,
        observed_comparison=observed_comparison,
        observed_strike=observed_strike,
        observed_coverage=observed_coverage,
        observed_review_reasons=result.review_reasons if result else (),
        observed_comparison_reason=result.comparison_reason if result else "",
        correct_resolution=correct_resolution,
        correct_status=correct_status,
        correct_comparison=correct_comparison,
        correct_strike=correct_strike,
        notes=label.notes,
    )


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def reproducibility_metadata(
    manifest: ValidationManifest,
    case_count: int,
    excluded_count: int,
) -> dict[str, Any]:
    """Run metadata for reproducibility. Never used for pass/fail behavior."""
    return {
        "gitCommit": _git_sha(),
        "ruleRevision": RULE_REVISION,
        "validationSchemaVersion": 1,
        "documentCount": len(manifest.documents),
        "labelledCaseCount": case_count,
        "excludedCaseCount": excluded_count,
        "timestampUtc": datetime.now(UTC).isoformat(),
        "pythonVersion": sys.version,
        "platform": platform.platform(),
    }


def run_validation(manifest_path: Path) -> dict[str, Any]:
    """Evaluate the whole manifest; returns the machine-readable result dict.

    Raises ``RuntimeError`` when a referenced document cannot be imported or
    the baseline cannot be loaded — a failed run is never reported as an
    all-missing measurement.
    """
    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path)
    base = manifest_path.parent

    baseline = load_baseline_from(base / manifest.baseline_file)
    if not baseline.ok or baseline.items is None:
        raise RuntimeError(f"baseline load failed: {baseline.error}")
    check_items = baseline.items

    cases: list[CaseRecord] = []
    document_reports: list[dict[str, Any]] = []
    for entry in manifest.documents:
        labels = load_document_labels(base / entry.labels_file)
        doc_result = import_document(base / entry.document_file)
        if isinstance(doc_result, ImportFailure):
            raise RuntimeError(
                f"document import failed for {entry.document_id}: "
                f"{doc_result.reason} ({doc_result.detail})"
            )
        outcome = verify_document(doc_result, check_items)
        if outcome.state is not VerificationState.COMPLETED:
            raise RuntimeError(
                f"verification did not complete for {entry.document_id}: {outcome.state.value}"
            )
        observed_coverage = doc_result.coverage.value.upper()
        results_by_item = {r.check_item.item_id: r for r in outcome.results}
        expected_by_item = {label.item_id: label for label in labels.labels}

        unknown = sorted(set(expected_by_item) - {i.item_id for i in check_items})
        if unknown:
            raise RuntimeError(
                f"labels for {entry.document_id} reference items missing from "
                f"the baseline: {unknown}"
            )
        not_verified = sorted(set(expected_by_item) - set(results_by_item))
        if not_verified:
            raise RuntimeError(
                f"labels for {entry.document_id} reference items that produce no "
                f"verification result (disabled or missing): {not_verified}"
            )

        for label in labels.labels:
            cases.append(
                compare_case(
                    labels,
                    label.item_id,
                    expected_by_item,
                    results_by_item,
                    observed_coverage,
                )
            )
        document_reports.append(
            {
                "documentId": entry.document_id,
                "coverage": observed_coverage,
                "coverageWarnings": list(doc_result.warnings),
                "labelledCases": len(labels.labels),
            }
        )

    case_count = len(cases)
    excluded_count = sum(1 for c in cases if not c.include_in_metrics)
    return {
        "metadata": reproducibility_metadata(manifest, case_count, excluded_count),
        "baselineId": baseline.baseline_id,
        "documents": document_reports,
        "cases": [_case_to_dict(c) for c in cases],
    }


def _case_to_dict(case: CaseRecord) -> dict[str, Any]:
    return {
        "documentId": case.document_id,
        "itemId": case.item_id,
        "includeInMetrics": case.include_in_metrics,
        "exclusionReason": case.exclusion_reason,
        "expected": {
            "resolution": case.expected_resolution,
            "status": case.expected_status,
            "comparison": case.expected_comparison,
            "strike": case.expected_strike,
            "coverage": case.expected_coverage,
        },
        "observed": {
            "resolution": case.observed_resolution,
            "status": case.observed_status,
            "comparison": case.observed_comparison,
            "strike": case.observed_strike,
            "coverage": case.observed_coverage,
            "reviewReasons": list(case.observed_review_reasons),
            "comparisonReason": case.observed_comparison_reason,
        },
        "correct": {
            "resolution": case.correct_resolution,
            "status": case.correct_status,
            "comparison": case.correct_comparison,
            "strike": case.correct_strike,
        },
        # Discrepancy classification is a human review step (T6.6); the
        # harness only leaves the placeholder here.
        "discrepancyCategory": "",
        "notes": case.notes,
    }


def write_results(results: dict[str, Any], out_path: Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
