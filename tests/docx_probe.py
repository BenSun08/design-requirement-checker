"""Exploratory DOCX probe for the S1/S2 technical spike.

NOT the production parser. This module exists only to produce repeatable
decision evidence for the strategy "python-docx + focused OOXML/XML access":

- python-docx provides package opening, paragraph/table/cell structure and
  run objects (``Run.text``, ``Run.font`` direct formatting values);
- focused lxml access resolves what the python-docx API cannot see: the
  style-inheritance chain (``basedOn``), ``docDefaults``, merged-cell grid
  geometry, tracked-revision markup, orphan style references and excluded
  structures (content controls, text boxes, headers/footers).

Conservative rules enforced here (product-spec policy):
- effective strike is resolved from run rPr -> character style chain ->
  paragraph style chain -> docDefaults -> default off;
- anything unresolvable (invalid values, orphan references, broken chains,
  double strike pending a product decision) stays ``None`` (unknown) and is
  never silently converted to ``False``;
- tracked revisions, excluded structures and hidden merged-cell continuation
  content produce explicit LIMITED reasons instead of silent loss.

Offsets are Python code-point indices with half-open [start, end) ranges,
matching the domain-model invariant (Python ``str`` counts code points).
"""

from dataclasses import dataclass
from pathlib import Path

from docx import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

_ON = {"true", "1", "on"}
_OFF = {"false", "0", "off"}
_WHITESPACE = {" ", "\t", "\n", "\r", "\u00a0", "\u3000"}
_REVISION_TAGS = (qn("w:ins"), qn("w:del"), qn("w:moveFrom"), qn("w:moveTo"))
# Element types that terminate a style-chain walk.
_INVALID = object()


@dataclass(frozen=True)
class ProbeRun:
    text: str
    start: int
    end: int
    strike: bool | None
    strike_origin: str
    strike_reason: str
    double_strike: bool | None


@dataclass(frozen=True)
class ProbeBlock:
    block_id: str
    part: str
    paragraph_index: int
    table_path: tuple[tuple[int, int, int], ...]
    raw_text: str
    runs: tuple[ProbeRun, ...]
    limited_reasons: tuple[str, ...]


@dataclass(frozen=True)
class ProbeDocument:
    filename: str
    coverage: str
    coverage_reasons: tuple[str, ...]
    blocks: tuple[ProbeBlock, ...]
    error: str | None


@dataclass(frozen=True)
class NormalizedText:
    """Conservative whitespace-collapsed text with lossless raw-span mapping.

    The transformation allowlist here is probe-level (whitespace runs collapse
    to one ASCII space; leading/trailing whitespace is dropped). The final
    production allowlist remains an S6 output.
    """

    text: str
    segments: tuple[tuple[int, int, int, int], ...]

    def map_span(self, norm_start: int, norm_end: int) -> tuple[int, int]:
        """Map a half-open normalized span back to the original raw span."""
        if not 0 <= norm_start < norm_end <= len(self.text):
            raise ValueError(f"invalid normalized span [{norm_start}, {norm_end})")
        first = last = None
        for norm_lo, norm_hi, raw_lo, _raw_hi in self.segments:
            if norm_lo <= norm_start < norm_hi:
                first = (norm_lo, raw_lo)
            if norm_lo < norm_end <= norm_hi:
                last = (norm_lo, raw_lo)
        if first is None or last is None:
            raise ValueError("span not covered by normalization segments")
        raw_start = first[1] + (norm_start - first[0])
        raw_end = last[1] + (norm_end - last[0])
        return (raw_start, raw_end)


def normalize(text: str) -> NormalizedText:
    """Collapse whitespace runs to single spaces and keep a raw-offset map."""
    norm_chars: list[str] = []
    spans: list[tuple[int, int]] = []  # raw span per emitted normalized char
    i = 0
    length = len(text)
    while i < length:
        if text[i] in _WHITESPACE:
            run_start = i
            while i < length and text[i] in _WHITESPACE:
                i += 1
            if norm_chars and i < length:
                norm_chars.append(" ")
                spans.append((run_start, i))
        else:
            norm_chars.append(text[i])
            spans.append((i, i + 1))
            i += 1
    segments: list[tuple[int, int, int, int]] = []
    for k, (norm_char, (raw_lo, raw_hi)) in enumerate(zip(norm_chars, spans)):
        last_is_contiguous = bool(segments) and (
            segments[-1][1] - segments[-1][0] == segments[-1][3] - segments[-1][2]
        )
        if norm_char == " " and raw_hi - raw_lo > 1:
            # A collapsed whitespace run covers several raw chars but one
            # normalized char: it must remain a standalone segment.
            segments.append((k, k + 1, raw_lo, raw_hi))
        elif last_is_contiguous and segments[-1][3] == raw_lo and norm_char != " ":
            n_lo, _n_hi, r_lo, _r_hi = segments[-1]
            segments[-1] = (n_lo, k + 1, r_lo, raw_hi)  # extend contiguous non-ws run
        else:
            segments.append((k, k + 1, raw_lo, raw_hi))
    return NormalizedText("".join(norm_chars), tuple(segments))


def _parse_strike_element(rpr: object) -> bool | None:
    """Read w:strike from an rPr element; None when absent, _INVALID when unparseable."""
    if rpr is None:
        return None
    strike = rpr.find(qn("w:strike"))  # type: ignore[union-attr]
    if strike is None:
        return None
    val = strike.get(qn("w:val"))
    if val is None:
        return True  # bare <w:strike/> means on
    if val in _ON:
        return True
    if val in _OFF:
        return False
    return _INVALID  # type: ignore[return-value]


class _StyleResolver:
    def __init__(self, doc: object) -> None:
        self.styles_element = doc.styles.element  # type: ignore[attr-defined]
        self.style_map = {
            style.get(qn("w:styleId")): style
            for style in self.styles_element.findall(qn("w:style"))
        }
        doc_defaults = self.styles_element.find(qn("w:docDefaults"))
        rpr_default = doc_defaults.find(qn("w:rPrDefault")) if doc_defaults is not None else None
        self.doc_defaults_strike = _parse_strike_element(
            rpr_default.find(qn("w:rPr")) if rpr_default is not None else None
        )

    def chain_strike(self, style_id: str) -> tuple[bool | None, str]:
        """Walk a basedOn chain; returns (value, unknown_reason)."""
        visited: set[str] = set()
        current = self.style_map.get(style_id)
        if current is None:
            return (None, "orphan-style-reference")
        while current is not None:
            sid = current.get(qn("w:styleId"))
            if sid in visited:
                return (None, "style-chain-cycle")
            visited.add(sid)
            value = _parse_strike_element(current.find(qn("w:rPr")))
            if value is _INVALID:
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


def _read_direct_strike(run: object) -> tuple[bool | None, str]:
    """Read the run-level strike via python-docx; classify API failures as unknown."""
    try:
        value = run.font.strike  # type: ignore[attr-defined]
    except Exception:
        return (None, "invalid-strike-value")
    return (value, "")


def _read_double_strike(run: object) -> bool | None:
    try:
        return run.font.double_strike  # type: ignore[attr-defined]
    except Exception:
        return None


def _resolve_strike(
    run: object,
    paragraph_style_id: str | None,
    resolver: _StyleResolver,
) -> tuple[bool | None, str, str]:
    """Return (effective_strike, origin, unknown_reason)."""
    direct, reason = _read_direct_strike(run)
    double = _read_double_strike(run)
    if reason:
        return (None, "direct", reason)
    value: bool | None = None
    origin = "default-off"
    if direct is not None:
        value, origin = direct, "direct"
    else:
        rpr = run._r.find(qn("w:rPr"))  # type: ignore[attr-defined]
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
        if value is None and resolver.doc_defaults_strike is not None:
            if resolver.doc_defaults_strike is _INVALID:
                return (None, "doc-defaults", "invalid-strike-value")
            value, origin = resolver.doc_defaults_strike, "doc-defaults"
    if value is None:
        # The chain resolved without defining strike: OOXML defaults it to off.
        value = False
    # Double strike: reliably detectable, but whether it counts as deletion
    # formatting is an open product question. Conservative: unknown unless
    # single strike is explicitly True.
    if double is True and value is not True:
        return (None, origin, "double-strike")
    return (value, origin, "")


def _paragraph_style_id(paragraph: Paragraph, resolver: _StyleResolver) -> str | None:
    ppr = paragraph._p.find(qn("w:pPr"))
    pstyle = ppr.find(qn("w:pStyle")) if ppr is not None else None
    if pstyle is not None:
        return pstyle.get(qn("w:val"))
    default_style = resolver.style_map.get("Normal")
    return default_style.get(qn("w:styleId")) if default_style is not None else None


def _probe_paragraph(
    paragraph: Paragraph,
    part: str,
    table_path: tuple[tuple[int, int, int], ...],
    paragraph_index: int,
    resolver: _StyleResolver,
) -> ProbeBlock:
    p_el = paragraph._p
    limited: list[str] = []
    if any(p_el.findall(f".//{tag}") for tag in _REVISION_TAGS):
        limited.append("tracked-revisions-unsupported")
    if p_el.findall(f".//{qn('w:txbxContent')}"):
        limited.append("textbox-content-excluded")
    if p_el.findall(f".//{qn('w:sdt')}"):
        limited.append("content-control-content-excluded")
    style_id = _paragraph_style_id(paragraph, resolver)
    runs: list[ProbeRun] = []
    offset = 0
    for run in paragraph.runs:
        strike, origin, reason = _resolve_strike(run, style_id, resolver)
        runs.append(
            ProbeRun(
                text=run.text,
                start=offset,
                end=offset + len(run.text),
                strike=strike,
                strike_origin=origin,
                strike_reason=reason,
                double_strike=_read_double_strike(run),
            )
        )
        offset += len(run.text)
    location = ">".join(f"t{t}r{r}c{c}" for t, r, c in table_path)
    block_id = f"{location + ':' if location else ''}{part}:p{paragraph_index}"
    return ProbeBlock(
        block_id=block_id,
        part=part,
        paragraph_index=paragraph_index,
        table_path=table_path,
        raw_text="".join(run.text for run in paragraph.runs),
        runs=tuple(runs),
        limited_reasons=tuple(limited),
    )


def _cell_has_text(tc: object) -> bool:
    return any(
        (node.text or "").strip() != ""
        for node in tc.findall(f".//{qn('w:t')}")  # type: ignore[arg-type]
    )


def _probe_table(
    table: Table,
    table_path: tuple[tuple[int, int, int], ...],
    table_index: int,
    resolver: _StyleResolver,
    blocks: list[ProbeBlock],
    limited: list[str],
) -> None:
    """Traverse w:tc elements directly (row.cells duplicates merged cells).

    Merged-cell convention: a gridSpan master is extracted once at its starting
    grid column; a vMerge master is extracted once at its (row, col); vMerge
    continuation cells are skipped, and non-empty continuation content raises
    an explicit LIMITED reason because Word does not display it.
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
                    grid_span = int(span_el.get(qn("w:val")))
                v_merge = tc_pr.find(qn("w:vMerge"))
            is_continuation = v_merge is not None and (
                v_merge.get(qn("w:val")) in (None, "continue")
            )
            if is_continuation:
                if _cell_has_text(tc):
                    limited.append("merged-cell-continuation-content-excluded")
                column_cursor += grid_span
                continue
            cell = _Cell(tc, table)
            cell_path = table_path + ((table_index, row_index, column_cursor),)
            paragraph_index = 0
            nested_index = 0
            for child in tc:
                if child.tag == qn("w:p"):
                    blocks.append(
                        _probe_paragraph(
                            Paragraph(child, cell),
                            "table-cell",
                            cell_path,
                            paragraph_index,
                            resolver,
                        )
                    )
                    paragraph_index += 1
                elif child.tag == qn("w:tbl"):
                    _probe_table(
                        Table(child, cell), cell_path, nested_index, resolver, blocks, limited
                    )
                    nested_index += 1
                elif child.tag == qn("w:sdt"):
                    limited.append("content-control-content-excluded")
            column_cursor += grid_span


def probe_docx(path: Path) -> ProbeDocument:
    """Read a .docx file without modifying it and return probe observations."""
    try:
        doc = DocxDocument(str(path))
    except Exception as exc:  # malformed/protected input must fail explicitly
        return ProbeDocument(
            filename=path.name,
            coverage="FAILED",
            coverage_reasons=(f"open-failed:{type(exc).__name__}",),
            blocks=(),
            error=f"{type(exc).__name__}: {exc}"[:200],
        )
    doc_reasons: list[str] = []
    blocks: list[ProbeBlock] = []
    resolver = _StyleResolver(doc)
    for section in doc.sections:
        for container, label in ((section.header, "header"), (section.footer, "footer")):
            if container.is_linked_to_previous:
                continue  # no explicit part of its own in this section
            if any(paragraph.text.strip() for paragraph in container.paragraphs):
                doc_reasons.append(f"{label}-content-not-checked")
    body = doc.element.body
    paragraph_index = 0
    table_index = 0
    for child in body:
        if child.tag == qn("w:p"):
            blocks.append(
                _probe_paragraph(Paragraph(child, doc._body), "body", (), paragraph_index, resolver)
            )
            paragraph_index += 1
        elif child.tag == qn("w:tbl"):
            _probe_table(Table(child, doc._body), (), table_index, resolver, blocks, doc_reasons)
            table_index += 1
        elif child.tag == qn("w:sdt"):
            doc_reasons.append("content-control-content-excluded")
    block_reasons = [reason for block in blocks for reason in block.limited_reasons]
    reasons = tuple(sorted(set(doc_reasons + block_reasons)))
    return ProbeDocument(
        filename=path.name,
        coverage="LIMITED" if reasons else "COMPLETE",
        coverage_reasons=reasons,
        blocks=tuple(blocks),
        error=None,
    )
