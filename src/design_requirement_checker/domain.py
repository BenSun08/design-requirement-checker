"""UI-independent domain value models and invariants (docs/domain-model.md).

This module owns document-snapshot values for the ingestion slice: blocks,
runs with effective strike, stable locations and honest coverage. It must
stay free of Qt, filesystem, Office and adapter dependencies. Offsets are
zero-based Unicode code-point indices with half-open ``[start, end)`` ranges.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Literal

Part = Literal["body", "table-cell"]

#: Declared extraction scope of the current slice; COMPLETE/LIMITED coverage
#: is relative to this scope, not to every Word feature.
SUPPORTED_SCOPE: tuple[str, ...] = ("body-paragraphs", "table-cell-paragraphs")


class BlockType(Enum):
    PARAGRAPH = "paragraph"
    TABLE_CELL_PARAGRAPH = "table-cell-paragraph"


class Coverage(Enum):
    COMPLETE = "complete"
    LIMITED = "limited"


class IngestionState(Enum):
    """A Document value only exists for a successfully read snapshot."""

    READY = "ready"


@dataclass(frozen=True)
class TableCellCoordinates:
    """Zero-based grid coordinates of a table cell (merged-cell master)."""

    table_index: int
    row_index: int
    column_index: int

    def __post_init__(self) -> None:
        if min(self.table_index, self.row_index, self.column_index) < 0:
            raise ValueError("cell indexes must be non-negative")


@dataclass(frozen=True)
class TextRun:
    """A reconstructed run with its effective strike over raw block text.

    ``effective_strike`` is ``None`` for unknown formatting; unknown values
    always carry a non-empty ``strike_reason`` and are never silently false.
    """

    text: str
    start_offset: int
    end_offset: int
    effective_strike: bool | None
    strike_origin: str = "default-off"
    strike_reason: str = ""
    double_strike: bool | None = None

    def __post_init__(self) -> None:
        if self.start_offset < 0 or self.end_offset < self.start_offset:
            raise ValueError("run offsets must satisfy 0 <= start <= end")
        if self.end_offset - self.start_offset != len(self.text):
            raise ValueError("run offsets must match the code-point length of its text")
        if (self.effective_strike is None) == (not self.strike_reason):
            raise ValueError("strike_reason must be present exactly when strike is unknown")
        if not self.strike_origin:
            raise ValueError("strike_origin must be non-empty")


@dataclass(frozen=True)
class DocumentLocation:
    """Stable location of a block within one identified document snapshot.

    Coordinates are zero-based internally; presentation converts them to
    one-based values. ``paragraph_index`` is local to the containing body or
    cell. Table-cell locations carry the immediate cell plus the ancestor
    cell path for nested tables (outermost first).
    """

    document_id: str
    block_id: str
    block_type: BlockType
    part: Part
    paragraph_index: int
    cell: TableCellCoordinates | None = None
    ancestor_path: tuple[TableCellCoordinates, ...] = ()

    def __post_init__(self) -> None:
        if not self.document_id or not self.block_id:
            raise ValueError("document_id and block_id must be non-empty")
        if self.paragraph_index < 0:
            raise ValueError("paragraph_index must be non-negative")
        if self.part == "body":
            if self.block_type is not BlockType.PARAGRAPH:
                raise ValueError("part 'body' requires block type PARAGRAPH")
            if self.cell is not None:
                raise ValueError("a body location must not carry cell coordinates")
        elif self.part == "table-cell":
            if self.block_type is not BlockType.TABLE_CELL_PARAGRAPH:
                raise ValueError("part 'table-cell' requires block type TABLE_CELL_PARAGRAPH")
            if self.cell is None:
                raise ValueError("a table-cell location requires cell coordinates")
        else:
            raise ValueError(f"unsupported part: {self.part!r}")


@dataclass(frozen=True)
class DocumentBlock:
    """One paragraph block: raw reconstructed text plus its runs.

    Text never crosses paragraph or cell boundaries. Runs are contiguous and
    concatenate exactly to ``text``.
    """

    block_id: str
    block_type: BlockType
    text: str
    runs: tuple[TextRun, ...]
    location: DocumentLocation

    def __post_init__(self) -> None:
        if not self.block_id:
            raise ValueError("block_id must be non-empty")
        if self.location.block_id != self.block_id or self.location.block_type is not (
            self.block_type
        ):
            raise ValueError("block identity must match its location")
        if self.text != "".join(run.text for run in self.runs):
            raise ValueError("block text must equal the concatenation of its runs")
        offset = 0
        for run in self.runs:
            if run.start_offset != offset:
                raise ValueError("runs must be contiguous from offset zero")
            offset = run.end_offset
        if offset != len(self.text):
            raise ValueError("runs must cover the whole block text")


@dataclass(frozen=True)
class Document:
    """An immutable input snapshot with honest coverage (docs/domain-model.md).

    ``coverage`` is COMPLETE only when nothing in the declared scope was
    excluded; otherwise LIMITED with at least one warning. Warnings are
    stable reason tokens, kept sorted and deduplicated.
    """

    document_id: str
    filename: str
    content_fingerprint: str
    blocks: tuple[DocumentBlock, ...]
    coverage: Coverage
    warnings: tuple[str, ...] = ()
    supported_scope: tuple[str, ...] = SUPPORTED_SCOPE
    ingestion_state: IngestionState = IngestionState.READY

    def __post_init__(self) -> None:
        if not self.document_id or not self.filename or not self.content_fingerprint:
            raise ValueError("document_id, filename and fingerprint must be non-empty")
        block_ids = [block.block_id for block in self.blocks]
        if len(set(block_ids)) != len(block_ids):
            raise ValueError("block ids must be unique within a document")
        for block in self.blocks:
            if block.location.document_id != self.document_id:
                raise ValueError("every block location must reference this document")
        if self.coverage is Coverage.COMPLETE and self.warnings:
            raise ValueError("a COMPLETE document must not carry warnings")
        if self.coverage is Coverage.LIMITED and not self.warnings:
            raise ValueError("a LIMITED document requires at least one warning")
        object.__setattr__(self, "warnings", tuple(sorted(set(self.warnings))))
