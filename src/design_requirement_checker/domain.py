"""UI-independent domain value models and invariants (docs/spec.md §5).

This module owns document-snapshot values for the ingestion slice: blocks,
runs with effective strike, stable locations and honest coverage. It must
stay free of Qt, filesystem, Office and adapter dependencies. Offsets are
zero-based Unicode code-point indices with half-open ``[start, end)`` ranges.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Literal

Part = Literal["body", "table-cell"]

#: Identifier of the deterministic rule set carried by every CheckResult.
#: Bump it whenever the verified rule behavior changes (docs/spec.md §5).
RULE_REVISION = "task3-v1"

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
    """An immutable input snapshot with honest coverage (docs/spec.md §5).

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


class CheckStatus(Enum):
    """Document evidence status; never confidence or approval."""

    CONFIGURED = "configured"
    MISSING = "missing"
    STRUCK_OUT = "struck-out"


class Resolution(Enum):
    """UNRESOLVED is a review condition with status unset, not a fourth status."""

    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


class ComparisonState(Enum):
    """Expected-description comparison; independent of detection and status."""

    SAME = "same"
    DIFFERENT = "different"
    NOT_COMPARED = "not-compared"


class MatchType(Enum):
    """Initial deterministic match methods; FUZZY/MANUAL/SEMANTIC stay reserved."""

    EXACT = "exact"
    NORMALIZED = "normalized"
    ALIAS = "alias"


class StrikeCoverage(Enum):
    """Strike over the matched requirement span, never the whole paragraph."""

    NONE = "none"
    FULL = "full"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CheckItemAlias:
    """An explicitly configured alternative detection phrase of one CheckItem.

    An alias establishes function identity only; it never asserts that the
    expected description is satisfied.
    """

    alias_id: str
    text: str
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.alias_id or not self.text:
            raise ValueError("alias_id and text must be non-empty")


@dataclass(frozen=True)
class CheckItem:
    """Immutable baseline snapshot used for one verification run.

    ``detection_phrase`` is the only configured detector; ``name`` labels the
    item and is never used for matching. Persistence and checklist editing
    belong to later slices.
    """

    item_id: str
    code: str
    name: str
    detection_phrase: str
    aliases: tuple[CheckItemAlias, ...] = ()
    category: str = ""
    expected_description: str = ""
    enabled: bool = True
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.item_id or not self.code or not self.name:
            raise ValueError("item_id, code and name are required")
        if not self.detection_phrase:
            raise ValueError("detection_phrase is required and engineer-maintained")


@dataclass(frozen=True)
class MatchEvidence:
    """One qualifying occurrence with original-document spans.

    All spans are raw half-open code-point ranges into the identified block's
    stored (unnormalized) text. ``comparison_blocker`` carries a stable reason
    token when this occurrence cannot safely take part in description
    comparison; ``ambiguous`` marks spans claimed by different configured term
    texts across items.
    """

    evidence_id: str
    document_id: str
    block_id: str
    location: DocumentLocation
    raw_text: str
    matched_span: tuple[int, int]
    requirement_span: tuple[int, int]
    requirement_text: str
    matched_term: str
    match_type: MatchType
    transformations: tuple[str, ...]
    strike_coverage: StrikeCoverage
    alias_id: str = ""
    ambiguous: bool = False
    comparison_blocker: str = ""

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raise ValueError("evidence_id must be non-empty")
        if self.location.document_id != self.document_id:
            raise ValueError("evidence location must reference its document")
        if self.location.block_id != self.block_id:
            raise ValueError("evidence location must reference its block")
        start, end = self.matched_span
        if not (0 <= start < end <= len(self.raw_text)):
            raise ValueError("matched_span must be a non-empty raw span")
        req_start, req_end = self.requirement_span
        if not (0 <= req_start < req_end <= len(self.raw_text)):
            raise ValueError("requirement_span must be a non-empty raw span")
        if not (req_start <= start and end <= req_end):
            raise ValueError("the matched span must lie inside the requirement span")


@dataclass(frozen=True)
class CheckResult:
    """Verification result for one enabled CheckItem against one document.

    Invariant: RESOLVED carries exactly one CheckStatus; UNRESOLVED carries
    none. Evidence keeps every qualifying occurrence in source order — no
    winner is chosen and no contradictory occurrence is discarded.
    """

    check_item: CheckItem
    document_id: str
    resolution: Resolution
    status: CheckStatus | None
    evidence: tuple[MatchEvidence, ...]
    comparison_state: ComparisonState
    comparison_reason: str
    review_reasons: tuple[str, ...]
    rule_revision: str
    primary_evidence_id: str = ""

    def __post_init__(self) -> None:
        if self.resolution is Resolution.RESOLVED and self.status is None:
            raise ValueError("a RESOLVED result requires exactly one status")
        if self.resolution is Resolution.UNRESOLVED and self.status is not None:
            raise ValueError("an UNRESOLVED result must not carry a status")
        if not self.rule_revision:
            raise ValueError("rule_revision must be non-empty")
