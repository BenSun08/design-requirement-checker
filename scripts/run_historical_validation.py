#!/usr/bin/env python3
"""Task 6 historical-validation runner.

Usage:
    python scripts/run_historical_validation.py validation/manifest.json \
        [--out validation/reports/latest-results.json]

Loads the ground-truth manifest, runs the production checker
(import_document -> verify_document) over every referenced document, compares
predictions with the independent labels and writes machine-readable per-case
results. Exit code is 0 when the evaluation completed (regardless of metric
values — pass/fail thresholds are an owner decision, see
validation/release-readiness-proposal.md) and 1 on any contract/run failure.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from validation.harness import run_validation, write_results  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="path to validation/manifest.json")
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "validation" / "reports" / "latest-results.json",
        help="where to write the machine-readable results",
    )
    args = parser.parse_args(argv)
    try:
        results = run_validation(args.manifest)
    except Exception as exc:  # explicit failure, never a silent all-missing run
        print(f"VALIDATION RUN FAILED: {exc}", file=sys.stderr)
        return 1
    write_results(results, args.out)
    metadata = results["metadata"]
    print(
        f"evaluated {metadata['labelledCaseCount']} labelled case(s) across "
        f"{metadata['documentCount']} document(s); "
        f"{metadata['excludedCaseCount']} excluded; results -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
