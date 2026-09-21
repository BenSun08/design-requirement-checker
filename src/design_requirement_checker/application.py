"""Application coordination: import and deterministic verification.

Use cases here coordinate domain values, the DOCX adapter and the pure
matching rules without touching widgets. Baseline persistence and the Qt
review workspace remain future slices (docs/implementation-plan.md).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from design_requirement_checker.docx_adapter import DocxReadError, read_document
from design_requirement_checker.domain import (
    CheckItem,
    CheckResult,
    Coverage,
    Document,
)
from design_requirement_checker.matching import VerificationCancelled
from design_requirement_checker.matching import verify as run_matching


@dataclass(frozen=True)
class ImportFailure:
    """An explicit import failure; never a silently empty document."""

    filename: str
    reason: str  # stable token, e.g. "unreadable-file"
    detail: str  # human-readable diagnostic from the adapter


def import_document(path: str | Path) -> Document | ImportFailure:
    """Import a local DOCX file into an immutable document snapshot.

    The file itself is never modified. Any read failure returns an explicit
    ImportFailure instead of raising or producing an empty document.
    """
    file_path = Path(path)
    try:
        return read_document(file_path)
    except DocxReadError as exc:
        return ImportFailure(filename=file_path.name, reason=exc.reason, detail=exc.detail)


class VerificationState(Enum):
    """Run lifecycle; cancelled/failed is never a completed missing report."""

    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True)
class VerificationOutcome:
    """The outcome of one verification run against one document snapshot.

    Results exist only for a COMPLETED run; coverage context is carried so
    presentation can keep absence claims scoped to the checked document.
    """

    document_id: str
    coverage: Coverage
    coverage_warnings: tuple[str, ...]
    state: VerificationState
    results: tuple[CheckResult, ...]

    def __post_init__(self) -> None:
        if self.state is not VerificationState.COMPLETED and self.results:
            raise ValueError("only a completed run may carry results")


def verify_document(
    document: Document,
    check_items: Sequence[CheckItem],
    cancel_check: Callable[[], bool] | None = None,
) -> VerificationOutcome:
    """Verify the enabled check items against a document snapshot.

    Disabled items produce no results. Cancellation is checked once per
    (item, block) pair inside the matching engine; a cancelled run returns an
    explicit CANCELLED outcome with no results rather than a partial or
    all-MISSING completed report.
    """
    enabled = tuple(item for item in check_items if item.enabled)
    try:
        results = run_matching(document, enabled, cancel_check)
    except VerificationCancelled:
        return VerificationOutcome(
            document_id=document.document_id,
            coverage=document.coverage,
            coverage_warnings=document.warnings,
            state=VerificationState.CANCELLED,
            results=(),
        )
    return VerificationOutcome(
        document_id=document.document_id,
        coverage=document.coverage,
        coverage_warnings=document.warnings,
        state=VerificationState.COMPLETED,
        results=results,
    )
