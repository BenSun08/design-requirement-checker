"""Task 6 — measured-report rendering (generic infrastructure).

Turns harness results + metrics into a Markdown report skeleton. Rendering is
separate from metric math (validation/metrics.py) and from evaluation
(validation/harness.py). The renderer refuses to produce a report from a run
whose only documents are synthetic: synthetic corpora validate the tooling,
they are not historical evidence.
"""

from __future__ import annotations

from typing import Any

from validation.metrics import Metrics

#: sanitizationState values that do not count as historical evidence.
NON_HISTORICAL = {"synthetic"}


def is_historical_run(results: dict[str, Any]) -> bool:
    """True when at least one evaluated document is real/sanitized/local-only.

    The harness records per-document provenance via the labels file; a run
    over a purely synthetic corpus must never be rendered as a measured
    historical report. Missing provenance fails closed (treated as not
    historical).
    """
    docs = results.get("documents", [])
    return any(d.get("sanitizationState", "synthetic") not in NON_HISTORICAL for d in docs)


def _metric_row(name: str, entry: dict[str, Any]) -> str:
    return f"| {name} | {entry.get('display', 'N/A (0/0)')} |"


def render_report(results: dict[str, Any], metrics: Metrics) -> str:
    """Render the measured-report Markdown from one harness run.

    Raises ValueError for non-historical runs.
    """
    if not is_historical_run(results):
        raise ValueError(
            "refusing to render a historical validation report from a purely "
            "synthetic corpus — synthetic fixtures are not historical evidence"
        )
    payload = metrics.as_dict()
    metadata = results.get("metadata", {})
    lines: list[str] = ["# Task 6 — Historical Validation Report", ""]

    lines += [
        "## Dataset",
        "",
        f"- Documents: {metadata.get('documentCount', 'unknown')}",
        f"- Labelled cases (included): {payload['totals']['includedCases']['display']}",
        f"- Excluded cases: {payload['totals']['excludedCases']['display']}",
        f"- Baseline revision: {results.get('baselineId', 'unknown')}",
        f"- Rule revision: {metadata.get('ruleRevision', 'unknown')}",
        f"- Validation schema: v{metadata.get('validationSchemaVersion', '?')}",
        f"- Git commit: {metadata.get('gitCommit', 'unknown')}",
        f"- Run timestamp (UTC): {metadata.get('timestampUtc', 'unknown')} "
        "(metadata only; never part of pass/fail)",
        "",
        "### Coverage distribution",
        "",
        "| Document | Coverage | Warnings |",
        "|---|---|---|",
    ]
    for doc in results.get("documents", []):
        warnings = ", ".join(doc.get("coverageWarnings", [])) or "—"
        lines.append(f"| {doc['documentId']} | {doc['coverage']} | {warnings} |")

    presence = payload["presence"]
    lines += [
        "",
        "## Confusion counts (binary presence; UNRESOLVED kept separate)",
        "",
        "| Count | Value |",
        "|---|---|",
        f"| true positive | {presence['truePositive']['numerator']} |",
        f"| false positive | {presence['falsePositive']['numerator']} |",
        f"| true negative | {presence['trueNegative']['numerator']} |",
        f"| false negative | {presence['falseNegative']['numerator']} |",
        (f"| observed UNRESOLVED | {payload['unresolved']['observedUnresolved']['numerator']} |"),
        f"| excluded from metrics | {payload['totals']['excludedCases']['numerator']} |",
        "",
        "## Metrics (numerator / denominator)",
        "",
        "| Metric | Value |",
        "|---|---|",
        _metric_row("precision", presence["precision"]),
        _metric_row("recall", presence["recall"]),
        _metric_row("status accuracy", payload["status"]["accuracy"]),
        _metric_row("strike accuracy", payload["strike"]["accuracy"]),
        _metric_row("comparison accuracy", payload["comparison"]["accuracy"]),
        _metric_row("unresolved rate", payload["unresolved"]["unresolvedRate"]),
        _metric_row("LIMITED documents", payload["coverage"]["limitedDocuments"]),
        _metric_row(
            "unsupported-warning rate", payload["coverage"]["unsupportedWarningDocumentRate"]
        ),
        "",
    ]

    review = payload["reviewTime"]
    lines += ["## Review-time change", ""]
    if review.get("status") == "MEASURED":
        lines += [
            f"- Status: MEASURED ({review.get('manualOnlySamples', 0)} manual-only / "
            f"{review.get('toolAssistedSamples', 0)} tool-assisted samples)",
            f"- Procedure: {review.get('procedure', 'not recorded')}",
        ]
    else:
        lines.append("- NOT MEASURED — no real review-timing study has been recorded.")

    incorrect = [
        c
        for c in results.get("cases", [])
        if c.get("includeInMetrics", True) and not all(c["correct"].values())
    ]
    lines += ["", "## Errors / discrepancies", ""]
    if not incorrect:
        lines.append("No incorrect cases in this run.")
    else:
        lines += [
            "| Case | Expected | Observed | Category | Root cause | Action |",
            "|---|---|---|---|---|---|",
        ]
        for case in incorrect:
            expected = f"{case['expected']['resolution']}"
            if case["expected"]["status"]:
                expected += f"/{case['expected']['status']}"
            observed = f"{case['observed']['resolution']}"
            if case["observed"]["status"]:
                observed += f"/{case['observed']['status']}"
            category = case.get("discrepancyCategory") or "UNCLASSIFIED"
            lines.append(
                f"| {case['documentId']} / {case['itemId']} | {expected} | {observed} "
                f"| {category} |  |  |"
            )
    lines += [
        "",
        "_Classification (EXTRACTION / MATCHING / NORMALIZATION / CONFIGURATION /",
        "POLICY / UNSUPPORTED_SCOPE / LABEL_ERROR) is a human review step; the",
        "renderer only shows what the review has recorded._",
        "",
    ]
    return "\n".join(lines)
