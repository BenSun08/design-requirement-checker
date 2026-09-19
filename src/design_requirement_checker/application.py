"""Import coordination: local DOCX file -> domain snapshot or explicit failure.

Use cases here coordinate domain values and the DOCX adapter without touching
widgets. Verification, cancellation and baseline orchestration remain future
slices (docs/implementation-plan.md).
"""

from dataclasses import dataclass
from pathlib import Path

from design_requirement_checker.docx_adapter import DocxReadError, read_document
from design_requirement_checker.domain import Document


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
