"""OOXML ingestion adapter: python-docx 1.2.0 + focused OOXML/XML access.

Strategy validated by the executed S1/S2 spike (docs/technical-spikes.md):
python-docx opens the package and provides paragraph/table/run structure,
while focused lxml access resolves what its API cannot see — the style
inheritance chain (``w:basedOn``), ``docDefaults``, merged-cell grid
geometry, tracked revisions, orphan style references and excluded
structures (content controls, text boxes, headers/footers).

Conservative policies enforced here (docs/product-spec.md, docs/domain-model.md):
- effective strike resolves run rPr -> character style chain -> paragraph
  style chain -> docDefaults -> default off;
- unresolvable formatting (invalid values, orphan references, broken chains,
  double strike pending a product decision) stays unknown with a reason and
  is never silently converted to False;
- tracked revisions, excluded structures and hidden merged-cell continuation
  content produce explicit LIMITED warnings instead of silent loss;
- merged-cell masters are extracted exactly once at their master grid
  position; vMerge continuations are skipped.

This is the only module where python-docx objects exist. It reads the file
bytes once, never writes, and returns domain values only. Offsets are Python
code-point indices with half-open ``[start, end)`` ranges.
"""

import hashlib
import io
from pathlib import Path
from typing import Any

from docx import Document as open_docx_package
from docx.oxml.ns import qn
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from design_requirement_checker.domain import (
    BlockType,
    Coverage,
    Document,
    DocumentBlock,
    DocumentLocation,
    Part,
    TableCellCoordinates,
    TextRun,
)

_ON = frozenset({"true", "1", "on"})
_OFF = frozenset({"false", "0", "off"})
_REVISION_TAGS = (qn("w:ins"), qn("w:del"), qn("w:moveFrom"), qn("w:moveTo"))


class DocxReadError(Exception):
    """A .docx file could not be read into a document snapshot.

    ``reason`` is a stable token ("unreadable-file" or "file-access-error");
    ``detail`` carries the human-readable diagnostic.
    """

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


class _InvalidStrike:
    """Sentinel for ``w:strike`` values outside the ST_OnOff vocabulary."""


_INVALID_STRIKE = _InvalidStrike()


def _parse_strike_element(rpr: Any) -> bool | None | _InvalidStrike:
    """Read ``w:strike`` from an rPr element; None when absent."""
    if rpr is None:
        return None
    strike = rpr.find(qn("w:strike"))
    if strike is None:
        return None
    val = strike.get(qn("w:val"))
    if val is None:
        return True  # bare <w:strike/> means on
    if val in _ON:
        return True
    if val in _OFF:
        return False
    return _INVALID_STRIKE


class _StyleResolver:
    """Style-table lookups for effective-strike chain resolution."""

    def __init__(self, doc: Any) -> None:
        styles_element = doc.styles.element
        self.style_map: dict[str, Any] = {
            style.get(qn("w:styleId")): style for style in styles_element.findall(qn("w:style"))
        }
        doc_defaults = styles_element.find(qn("w:docDefaults"))
        rpr_default = doc_defaults.find(qn("w:rPrDefault")) if doc_defaults is not None else None
        self.doc_defaults_strike: bool | None | _InvalidStrike = _parse_strike_element(
            rpr_default.find(qn("w:rPr")) if rpr_default is not None else None
        )

    def chain_strike(self, style_id: str) -> tuple[bool | None, str]:
        """Walk a basedOn chain; returns (value, "") or (None, unknown_reason)."""
        visited: set[str] = set()
        current: Any = self.style_map.get(style_id)
        if current is None:
            return (None, "orphan-style-reference")
        while current is not None:
            sid: str | None = current.get(qn("w:styleId"))
            if sid is None or sid in visited:
                return (None, "style-chain-cycle")
            visited.add(sid)
            value = _parse_strike_element(current.find(qn("w:rPr")))
            if isinstance(value, _InvalidStrike):
                return (None, "invalid-strike-value")
            if value is not None:
                return (value, "")
            based_on = current.find(qn("w:basedOn"))
            if based_on is None:
                return (None, "")
            current = self.style_map.get(based_on.get(qn("w:val")))
            if current is None:
                return (None, "broken-style-chain")
        return (None, "")


def _read_direct_strike(run: Any) -> tuple[bool | None, str]:
    """Read the run-level strike via python-docx; classify API failures unknown."""
    try:
        value: bool | None = run.font.strike
    except Exception:
        return (None, "invalid-strike-value")
    return (value, "")


def _read_double_strike(run: Any) -> bool | None:
    try:
        value: bool | None = run.font.double_strike
        return value
    except Exception:
        return None


def _resolve_strike(
    run: Any, paragraph_style_id: str | None, resolver: _StyleResolver
) -> tuple[bool | None, str, str]:
    """Return (effective_strike, origin, unknown_reason)."""
    direct, direct_reason = _read_direct_strike(run)
    double = _read_double_strike(run)
    if direct_reason:
        return (None, "direct", direct_reason)
    value: bool | None = None
    origin = "default-off"
    if direct is not None:
        value, origin = direct, "direct"
    else:
        rpr = run._r.find(qn("w:rPr"))
        rstyle = rpr.find(qn("w:rStyle")) if rpr is not None else None
        if rstyle is not None:
            char_value, char_reason = resolver.chain_strike(rstyle.get(qn("w:val")))
            if char_reason:
                return (None, "character-style", char_reason)
            if char_value is not None:
                value, origin = char_value, "character-style"
        if value is None and paragraph_style_id is not None:
            para_value, para_reason = resolver.chain_strike(paragraph_style_id)
            if para_reason:
                return (None, "paragraph-style", para_reason)
            if para_value is not None:
                value, origin = para_value, "paragraph-style"
        if value is None:
            doc_default = resolver.doc_defaults_strike
            if isinstance(doc_default, _InvalidStrike):
                return (None, "doc-defaults", "invalid-strike-value")
            if doc_default is not None:
                value, origin = doc_default, "doc-defaults"
    if value is None:
        # The chain resolved without defining strike: OOXML defaults it to off.
        value = False
    # Double strike is reliably detectable, but whether it counts as deletion
    # formatting is an open product question. Conservative: unknown unless
    # single strike is explicitly True.
    if double is True and value is not True:
        return (None, origin, "double-strike")
    return (value, origin, "")


def _paragraph_style_id(paragraph: Paragraph, resolver: _StyleResolver) -> str | None:
    ppr = paragraph._p.find(qn("w:pPr"))
    pstyle = ppr.find(qn("w:pStyle")) if ppr is not None else None
    if pstyle is not None:
        style_id: str | None = pstyle.get(qn("w:val"))
        return style_id
    default_style = resolver.style_map.get("Normal")
    if default_style is None:
        return None
    default_id: str | None = default_style.get(qn("w:styleId"))
    return default_id


def _block_id(
    part: Part, cell: TableCellCoordinates | None, ancestor_path: tuple[TableCellCoordinates, ...]
) -> str:
    cells = [*ancestor_path]
    if cell is not None:
        cells.append(cell)
    prefix = ">".join(f"t{c.table_index}r{c.row_index}c{c.column_index}" for c in cells)
    return f"{prefix + ':' if prefix else ''}{part}:p"


def _collect_paragraph(
    document_id: str,
    paragraph: Paragraph,
    part: Part,
    cell: TableCellCoordinates | None,
    ancestor_path: tuple[TableCellCoordinates, ...],
    paragraph_index: int,
    resolver: _StyleResolver,
    blocks: list[DocumentBlock],
    warnings: list[str],
) -> None:
    p_el: Any = paragraph._p
    if any(p_el.findall(f".//{tag}") for tag in _REVISION_TAGS):
        warnings.append("tracked-revisions-unsupported")
    if p_el.findall(f".//{qn('w:txbxContent')}"):
        warnings.append("textbox-content-excluded")
    if p_el.findall(f".//{qn('w:sdt')}"):
        warnings.append("content-control-content-excluded")
    style_id = _paragraph_style_id(paragraph, resolver)
    runs: list[TextRun] = []
    offset = 0
    for run in paragraph.runs:
        text: str = run.text
        strike, origin, reason = _resolve_strike(run, style_id, resolver)
        runs.append(
            TextRun(
                text=text,
                start_offset=offset,
                end_offset=offset + len(text),
                effective_strike=strike,
                strike_origin=origin,
                strike_reason=reason,
                double_strike=_read_double_strike(run),
            )
        )
        offset += len(text)
    block_type = BlockType.PARAGRAPH if part == "body" else BlockType.TABLE_CELL_PARAGRAPH
    block_id = _block_id(part, cell, ancestor_path) + str(paragraph_index)
    location = DocumentLocation(
        document_id=document_id,
        block_id=block_id,
        block_type=block_type,
        part=part,
        paragraph_index=paragraph_index,
        cell=cell,
        ancestor_path=ancestor_path,
    )
    blocks.append(
        DocumentBlock(
            block_id=block_id,
            block_type=block_type,
            text="".join(run.text for run in paragraph.runs),
            runs=tuple(runs),
            location=location,
        )
    )


def _cell_has_text(tc: Any) -> bool:
    return any((node.text or "").strip() != "" for node in tc.findall(f".//{qn('w:t')}"))


def _collect_table(
    table: Table,
    ancestor_path: tuple[TableCellCoordinates, ...],
    table_index: int,
    resolver: _StyleResolver,
    document_id: str,
    blocks: list[DocumentBlock],
    warnings: list[str],
) -> None:
    """Traverse ``w:tc`` elements directly (``row.cells`` duplicates merged cells).

    Merged-cell convention: a gridSpan master is extracted once at its starting
    grid column; a vMerge master is extracted once at its (row, col); vMerge
    continuation cells are skipped, and non-empty continuation content raises
    an explicit warning because Word does not display it.
    """
    for row_index, tr in enumerate(table._tbl.findall(qn("w:tr"))):
        column_cursor = 0
        for tc in tr.findall(qn("w:tc")):
            tc_pr = tc.find(qn("w:tcPr"))
            grid_span = 1
            v_merge = None
            if tc_pr is not None:
                span_el = tc_pr.find(qn("w:gridSpan"))
                if span_el is not None:
                    span_value: str | None = span_el.get(qn("w:val"))
                    grid_span = int(span_value) if span_value else 1
                v_merge = tc_pr.find(qn("w:vMerge"))
            is_continuation = v_merge is not None and (
                v_merge.get(qn("w:val")) in (None, "continue")
            )
            if is_continuation:
                if _cell_has_text(tc):
                    warnings.append("merged-cell-continuation-content-excluded")
                column_cursor += grid_span
                continue
            cell = TableCellCoordinates(
                table_index=table_index, row_index=row_index, column_index=column_cursor
            )
            cell_parent = _Cell(tc, table)
            paragraph_index = 0
            nested_index = 0
            for child in tc:
                if child.tag == qn("w:p"):
                    _collect_paragraph(
                        document_id,
                        Paragraph(child, cell_parent),
                        "table-cell",
                        cell,
                        ancestor_path,
                        paragraph_index,
                        resolver,
                        blocks,
                        warnings,
                    )
                    paragraph_index += 1
                elif child.tag == qn("w:tbl"):
                    _collect_table(
                        Table(child, cell_parent),
                        (*ancestor_path, cell),
                        nested_index,
                        resolver,
                        document_id,
                        blocks,
                        warnings,
                    )
                    nested_index += 1
                elif child.tag == qn("w:sdt"):
                    warnings.append("content-control-content-excluded")
            column_cursor += grid_span


def _collect_body(
    doc: Any,
    document_id: str,
    resolver: _StyleResolver,
    blocks: list[DocumentBlock],
    warnings: list[str],
) -> None:
    body = doc.element.body
    paragraph_index = 0
    table_index = 0
    for child in body:
        if child.tag == qn("w:p"):
            _collect_paragraph(
                document_id,
                Paragraph(child, doc._body),
                "body",
                None,
                (),
                paragraph_index,
                resolver,
                blocks,
                warnings,
            )
            paragraph_index += 1
        elif child.tag == qn("w:tbl"):
            _collect_table(
                Table(child, doc._body), (), table_index, resolver, document_id, blocks, warnings
            )
            table_index += 1
        elif child.tag == qn("w:sdt"):
            warnings.append("content-control-content-excluded")


def _collect_header_footer_warnings(doc: Any, warnings: list[str]) -> None:
    for section in doc.sections:
        for container, label in ((section.header, "header"), (section.footer, "footer")):
            if container.is_linked_to_previous:
                continue  # no explicit part of its own in this section
            if any(paragraph.text.strip() for paragraph in container.paragraphs):
                warnings.append(f"{label}-content-not-checked")


def read_document(path: Path) -> Document:
    """Read a .docx file without modifying it; raise DocxReadError on failure."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise DocxReadError("file-access-error", f"{type(exc).__name__}: {exc}") from exc
    fingerprint = hashlib.sha256(data).hexdigest()
    document_id = f"sha256:{fingerprint}"
    try:
        package = open_docx_package(io.BytesIO(data))
        warnings: list[str] = []
        blocks: list[DocumentBlock] = []
        resolver = _StyleResolver(package)
        _collect_body(package, document_id, resolver, blocks, warnings)
        _collect_header_footer_warnings(package, warnings)
    except Exception as exc:
        raise DocxReadError("unreadable-file", f"{type(exc).__name__}: {exc}"[:200]) from exc
    unique_warnings = sorted(set(warnings))
    coverage = Coverage.LIMITED if unique_warnings else Coverage.COMPLETE
    return Document(
        document_id=document_id,
        filename=path.name,
        content_fingerprint=fingerprint,
        blocks=tuple(blocks),
        coverage=coverage,
        warnings=tuple(unique_warnings),
    )
