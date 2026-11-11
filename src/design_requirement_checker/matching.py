"""Pure deterministic verification: detection, evidence and classification.

Uses the normalization allowlist and forward-only paragraph spans from the
Task 3 contract, plus independent field matching and GN description-table
association. Each piece of evidence keeps a raw span in one document block.
Inputs and outputs are domain values only.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from itertools import pairwise

from design_requirement_checker.domain import (
    RULE_REVISION,
    CheckItem,
    CheckResult,
    CheckStatus,
    ComparisonState,
    Document,
    DocumentBlock,
    MatchEvidence,
    MatchType,
    Resolution,
    StrikeCoverage,
    TableCellCoordinates,
)

# --- normalization allowlist (S6: N1/N2/N3 only; nothing else) --------------

_WS_CHARS = frozenset(" \t\u3000")
_BREAK_CHARS = frozenset("\n\r\v\f")
_PUNCT_MAP = {
    "（": "(",
    "）": ")",
    "：": ":",
    "；": ";",
    "，": ",",
    "？": "?",
    "！": "!",
    "．": ".",
}
#: Boundary delimiters recognized in normalized text. '、' and '。' are
#: deliberately NOT normalized (rejected R1) but are recognized as boundaries.
_BOUNDARY_CHARS = frozenset(";.!? ,、。")
_SENTENCE_END_CHARS = frozenset(".!?。")
_GN_HEADING = re.compile(r"^ *GN[0-9]+ *:")
_TABLE_LOCATOR = "function-table-locator"
_OVERLAPPING_IDENTITY = "overlapping-identity-hit"
#: Match-method reporting preference: exact → normalized → alias.
_TYPE_RANK = {
    MatchType.EXACT: 0,
    MatchType.NORMALIZED: 1,
    MatchType.ALIAS: 2,
    MatchType.FUNCTION_NAME: 0,
    MatchType.EXPECTED_DESCRIPTION: 0,
}


class VerificationCancelled(Exception):
    """Raised at a cancellation checkpoint; never yields a completed run."""


@dataclass(frozen=True)
class NormalizedText:
    """Normalized text plus per-character raw source spans (traceability)."""

    text: str
    char_sources: tuple[tuple[int, int], ...]


def normalize(raw: str) -> NormalizedText:
    """Apply the S6 allowlist to one block's raw text.

    N1/N2 collapse runs of spaces/tabs/ideographic spaces/line breaks to one
    ASCII space (within one block only — blocks are never joined); N3 maps the
    approved fullwidth ASCII punctuation. Everything else — digits, units,
    letter case, negation, operators, ideographic punctuation — is preserved
    verbatim. The stored source text is never replaced.
    """
    out: list[str] = []
    sources: list[tuple[int, int]] = []
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch in _WS_CHARS or ch in _BREAK_CHARS:
            j = i
            while j < n and (raw[j] in _WS_CHARS or raw[j] in _BREAK_CHARS):
                j += 1
            out.append(" ")
            sources.append((i, j))
            i = j
        elif ch in _PUNCT_MAP:
            out.append(_PUNCT_MAP[ch])
            sources.append((i, i + 1))
            i += 1
        else:
            out.append(ch)
            sources.append((i, i + 1))
            i += 1
    return NormalizedText("".join(out), tuple(sources))


def map_span(norm: NormalizedText, start: int, end: int) -> tuple[int, int]:
    """Map a normalized half-open span back to the exact raw span."""
    if start < 0 or end > len(norm.char_sources) or start >= end:
        raise ValueError("normalized span out of range")
    return (norm.char_sources[start][0], norm.char_sources[end - 1][1])


def _active_rules(text: str) -> tuple[str, ...]:
    """Which allowlist rules actually change ``text`` (N1/N2/N3, fixed order)."""
    norm = normalize(text)
    rules: set[str] = set()
    for index, (raw_start, raw_end) in enumerate(norm.char_sources):
        piece = text[raw_start:raw_end]
        char = norm.text[index]
        if piece == char:
            continue
        if char == " ":
            if any(c in _WS_CHARS for c in piece):
                rules.add("N1")
            if any(c in _BREAK_CHARS for c in piece):
                rules.add("N2")
        else:
            rules.add("N3")
    return tuple(rule for rule in ("N1", "N2", "N3") if rule in rules)


# --- value tokens -----------------------------------------------------------

_VALUE_TOKEN_RE = re.compile(
    r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?) ?"
    r"(km/h|kHz|MHz|mV|kW|ms|min|mm|cm|km|Hz|V|A|W|h|m|s|%)"
)
_STANDALONE_QUANTITY = re.compile(
    rf"(?<![A-Za-z0-9_.+\-]){_VALUE_TOKEN_RE.pattern}(?![A-Za-z0-9_])", re.ASCII
)


def _value_tokens(normalized_text: str) -> frozenset[str]:
    return frozenset(f"{number}{unit}" for number, unit in _VALUE_TOKEN_RE.findall(normalized_text))


def _description_signature(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Keep the literal structure and the standalone quantities in source order."""
    parts: list[str] = []
    values: list[str] = []
    end = 0
    for quantity in _STANDALONE_QUANTITY.finditer(text):
        parts.extend((text[end : quantity.start()], text[quantity.end(1) : quantity.end()]))
        values.append(quantity[1])
        end = quantity.end()
    parts.append(text[end:])
    return tuple(parts), tuple(values)


# --- occurrence collection ---------------------------------------------------


@dataclass(frozen=True)
class _Candidate:
    """One (item, span) candidate before association and classification."""

    item: CheckItem
    term: str
    alias_id: str
    match_type: MatchType
    norm_span: tuple[int, int]


@dataclass(frozen=True)
class _Occurrence:
    """One qualifying candidate with its evaluation inputs (internal value)."""

    block_index: int
    item: CheckItem
    term: str
    alias_id: str
    match_type: MatchType
    transformations: tuple[str, ...]
    raw_match_span: tuple[int, int]
    raw_requirement_span: tuple[int, int]
    requirement_text: str
    strike_coverage: StrikeCoverage
    value_tokens: frozenset[str]
    comparison_blocker: str
    ambiguous: bool
    active_table_heading: bool = False


def _find_all(haystack: str, needle: str) -> list[tuple[int, int]]:
    """Non-overlapping left-to-right occurrences of needle in haystack."""
    if not needle:
        return []
    hits: list[tuple[int, int]] = []
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx < 0:
            return hits
        hits.append((idx, idx + len(needle)))
        start = idx + len(needle)


def _is_boundary(norm_text: str, k: int) -> bool:
    """Boundary delimiter at k; '.'/',' between digits (2.5s, 1,000ms) are not."""
    ch = norm_text[k]
    if ch not in _BOUNDARY_CHARS:
        return False
    if ch in ".,":
        before = norm_text[k - 1].isdigit() if k > 0 else False
        after = norm_text[k + 1].isdigit() if k + 1 < len(norm_text) else False
        if before and after:
            return False
    return True


def _strike_coverage(block: DocumentBlock, raw_span: tuple[int, int]) -> StrikeCoverage:
    """Strike coverage over the requirement span (never the whole paragraph)."""
    start, end = raw_span
    pieces: list[bool | None] = []
    for run in block.runs:
        if max(start, run.start_offset) < min(end, run.end_offset):
            pieces.append(run.effective_strike)
    if not pieces or any(piece is None for piece in pieces):
        return StrikeCoverage.UNKNOWN
    if all(piece is True for piece in pieces):
        return StrikeCoverage.FULL
    if all(piece is False for piece in pieces):
        return StrikeCoverage.NONE
    return StrikeCoverage.PARTIAL


_CLAUSE_SEPARATORS = _SENTENCE_END_CHARS | {";"}
_STRIKE_WHITESPACE = "".join(_WS_CHARS | _BREAK_CHARS)


def _is_clause_separator(text: str, index: int) -> bool:
    char = _PUNCT_MAP.get(text[index], text[index])
    if char not in _CLAUSE_SEPARATORS:
        return False
    before, after = text[max(index - 1, 0) : index], text[index + 1 : index + 2]
    if char in ".。" and before.isdigit() and after.isdigit():
        return False
    if (
        char == "."
        and before.isascii()
        and (before.isalnum() or before == "_")
        and after.isascii()
        and (after.isalnum() or after == "_")
    ):
        return False  # Decimal point or separator inside an ASCII identifier.
    return char != "!" or _PUNCT_MAP.get(after, after) != "="


def _separate_struck_clause(text: str, start: int, end: int) -> bool:
    """Require a complete clause and leave a separator between surviving clauses."""
    before = text[:start].rstrip(_STRIKE_WHITESPACE)
    after = text[end:].lstrip(_STRIKE_WHITESPACE)
    left_edge = len(before)
    right_edge = len(text) - len(after)
    fragment = text[start:end]
    first = end - len(fragment.lstrip(_STRIKE_WHITESPACE))
    last = start + len(fragment.rstrip(_STRIKE_WHITESPACE)) - 1
    if not any(char.isalnum() for char in fragment):
        return False
    left_boundary = not before or _is_clause_separator(text, left_edge - 1)
    right_boundary = not after or _is_clause_separator(text, right_edge)
    return (
        (left_boundary or _is_clause_separator(text, first))
        and (right_boundary or _is_clause_separator(text, last))
        and (left_boundary or right_boundary)
    )


def _inline_clause_replacement(text: str, start: int, end: int, next_strike: int) -> bool:
    """Recognize the start of the same Chinese clause in adjacent old and live text."""
    before = text[:start].rstrip(_STRIKE_WHITESPACE)
    if before and before[-1] not in ",，" and not _is_clause_separator(text, len(before) - 1):
        return False
    old = text[start:end].lstrip(_STRIKE_WHITESPACE)
    current = text[end:next_strike].lstrip(_STRIKE_WHITESPACE)
    # Two literal Han characters anchor the restarted clause. Isolated
    # negations, operators and fragments of a quantity cannot be anchors.
    lead = old[:2]
    return (
        re.fullmatch(r"[\u3400-\u4dbf\u4e00-\u9fff]{2}", lead) is not None
        and current.startswith(lead)
        and not any(_is_clause_separator(text, index) for index in range(start, end))
    )


def _is_bare_identity(item: CheckItem, text: str) -> bool:
    terms = (item.detection_phrase, item.name, *(alias.text for alias in item.aliases))
    return any(text == normalize(term).text for term in terms)


def _active_description_spans(
    block: DocumentBlock,
    occurrence: _Occurrence,
    expected: str,
) -> tuple[tuple[int, int], ...]:
    """Prove the surviving description against the baseline and retain raw offsets."""
    if (
        occurrence.strike_coverage is not StrikeCoverage.PARTIAL
        or occurrence.comparison_blocker
        or occurrence.ambiguous
        or not expected.strip(_STRIKE_WHITESPACE)
    ):
        return ()
    if occurrence.match_type is not MatchType.TABLE_DESCRIPTION and (
        _strike_coverage(block, occurrence.raw_match_span) is not StrikeCoverage.NONE
    ):
        return ()
    start, end = occurrence.raw_requirement_span
    raw = block.text[start:end]
    struck: list[tuple[int, int]] = []
    for run in block.runs:
        left = max(start, run.start_offset) - start
        right = min(end, run.end_offset) - start
        if run.effective_strike is not True or left >= right:
            continue
        if struck and struck[-1][1] == left:
            struck[-1] = (struck[-1][0], right)
        else:
            struck.append((left, right))

    active: list[tuple[int, int]] = []
    cursor = 0
    has_inline_replacement = False
    # Whitespace-only strikes remain in the projection, including between
    # the old clause and its active replacement.
    substantive = [
        (left, right) for left, right in struck if raw[left:right].strip(_STRIKE_WHITESPACE)
    ]
    for (left, right), (next_strike, _) in pairwise([*substantive, (len(raw), len(raw))]):
        if not _separate_struck_clause(raw, left, right):
            if not _inline_clause_replacement(raw, left, right, next_strike):
                return ()
            has_inline_replacement = True
        if cursor < left:
            active.append((start + cursor, start + left))
        cursor = right
    if cursor < len(raw):
        active.append((start + cursor, end))

    surviving = normalize("".join(block.text[left:right] for left, right in active)).text
    if _is_bare_identity(occurrence.item, surviving):
        return ()
    if has_inline_replacement:
        return tuple(active) if surviving == expected else ()
    surviving_structure, _ = _description_signature(surviving)
    expected_structure, _ = _description_signature(expected)
    return tuple(active) if surviving_structure == expected_structure else ()


def _association_blocker(
    item: CheckItem, norm_text: str, norm_span: tuple[int, int], norm_req_end: int
) -> str:
    """Uncertainty rules for comparing this occurrence's requirement span.

    Rule 1: the span carries no value while the expected description does and
    the enclosing sentence beyond the span does -> association uncertain.
    Rule 2: the span never extended past the matched phrase while the expected
    description differs from the bare phrase -> no requirement content.
    """
    if not item.expected_description:
        return ""
    span_text = norm_text[norm_span[0] : norm_req_end]
    if not _value_tokens(span_text):
        expected_norm = normalize(item.expected_description).text
        if _value_tokens(expected_norm):
            sentence_end = norm_req_end
            while sentence_end < len(norm_text) and norm_text[sentence_end] not in (
                _SENTENCE_END_CHARS
            ):
                sentence_end += 1
            if _value_tokens(norm_text[norm_req_end:sentence_end]):
                return "requirement-span-association-uncertain"
        if norm_req_end == norm_span[1] and expected_norm != span_text:
            return "no-associated-requirement-content"
    return ""


def _search_terms(item: CheckItem) -> tuple[tuple[str, str, MatchType, str], ...]:
    terms: list[tuple[str, str, MatchType]] = [(item.detection_phrase, "", MatchType.EXACT)]
    terms.extend((alias.text, alias.alias_id, MatchType.ALIAS) for alias in item.aliases)
    terms.extend(
        (term, "", field)
        for term, field in (
            (item.name, MatchType.FUNCTION_NAME),
            (item.expected_description, MatchType.EXPECTED_DESCRIPTION),
        )
        if term.strip()
    )
    return tuple((term, alias_id, kind, normalize(term).text) for term, alias_id, kind in terms)


def _collect_candidates(
    item: CheckItem,
    norm: NormalizedText,
    raw_text: str,
    terms: Sequence[tuple[str, str, MatchType, str]],
) -> list[_Candidate]:
    """Search one item and block after its cancellation checkpoint.

    Each field can report the same raw span. Phrase and alias hits share
    a field and keep the best match method.
    """
    best: dict[tuple[MatchType, tuple[int, int]], _Candidate] = {}
    for term, alias_id, configured_type, term_norm in terms:
        for norm_start, norm_end in _find_all(norm.text, term_norm):
            raw_span = map_span(norm, norm_start, norm_end)
            match_type = configured_type
            if match_type is MatchType.EXACT and raw_text[raw_span[0] : raw_span[1]] != term:
                match_type = MatchType.NORMALIZED
            candidate = _Candidate(item, term, alias_id, match_type, (norm_start, norm_end))
            field = MatchType.EXACT if configured_type is MatchType.ALIAS else configured_type
            key = (field, raw_span)
            current = best.get(key)
            if current is None or _TYPE_RANK[match_type] < _TYPE_RANK[current.match_type]:
                best[key] = candidate
    return list(best.values())


def _associate_candidates(
    candidates: Sequence[_Candidate],
    norm: NormalizedText,
    block: DocumentBlock,
    block_index: int,
) -> list[_Occurrence]:
    """Cross-item ambiguity, requirement-span association and evidence values.

    Runs after every item's candidates for the block have been collected, so
    overlapping phrases across items can be detected. Ordering follows the raw
    span (via the equivalent normalized span) then term text.
    """
    ordered = sorted(candidates, key=lambda c: (c.norm_span, c.term))
    identity = [c for c in ordered if c.match_type is not MatchType.EXPECTED_DESCRIPTION]

    # Identical terms within the same field are baseline-validation warnings.
    # An overlap across items and fields can claim the same source identity.
    ambiguous: set[tuple[str, tuple[int, int]]] = set()
    for i, left in enumerate(identity):
        for right in identity[i + 1 :]:
            same_field = (left.match_type is MatchType.FUNCTION_NAME) == (
                right.match_type is MatchType.FUNCTION_NAME
            )
            if left.item.item_id == right.item.item_id or (same_field and left.term == right.term):
                continue
            left_raw = map_span(norm, left.norm_span[0], left.norm_span[1])
            right_raw = map_span(norm, right.norm_span[0], right.norm_span[1])
            if left_raw[0] < right_raw[1] and right_raw[0] < left_raw[1]:
                ambiguous.add((left.item.item_id, left_raw))
                ambiguous.add((right.item.item_id, right_raw))

    # Requirement-span association: forward only, to the earliest boundary
    # delimiter, next qualifying match start or block end (S6 rule).
    match_starts = [candidate.norm_span[0] for candidate in identity]
    occurrences: list[_Occurrence] = []
    for candidate in ordered:
        norm_start, norm_end = candidate.norm_span
        raw_span = map_span(norm, norm_start, norm_end)
        description_hit = candidate.match_type is MatchType.EXPECTED_DESCRIPTION
        end = norm_end
        if not description_hit:
            end = len(norm.text)
            for k in range(norm_end, len(norm.text)):
                if _is_boundary(norm.text, k):
                    end = k
                    break
            for other_start in match_starts:
                if norm_end <= other_start < end:
                    end = other_start
        requirement_text = norm.text[norm_start:end]
        raw_requirement_span = (
            norm.char_sources[norm_start][0],
            norm.char_sources[end - 1][1],
        )
        transformations = (
            ()
            if candidate.match_type is MatchType.EXACT
            else tuple(
                dict.fromkeys(
                    _active_rules(block.text[raw_span[0] : raw_span[1]])
                    + _active_rules(candidate.term)
                )
            )
        )
        if description_hit:
            blocker = "unassociated-expected-description"
        elif candidate.match_type is MatchType.FUNCTION_NAME and any(
            other.item.item_id == candidate.item.item_id
            and other.match_type is not MatchType.FUNCTION_NAME
            and norm_start < other.norm_span[1]
            and other.norm_span[0] < norm_end
            and (other.item.item_id, map_span(norm, *other.norm_span)) not in ambiguous
            for other in identity
        ):
            # The same occurrence can report both identity fields. Compare
            # the configured phrase span once to avoid conflicting slices.
            blocker = _OVERLAPPING_IDENTITY
        else:
            blocker = _association_blocker(candidate.item, norm.text, candidate.norm_span, end)
        occurrences.append(
            _Occurrence(
                block_index=block_index,
                item=candidate.item,
                term=candidate.term,
                alias_id=candidate.alias_id,
                match_type=candidate.match_type,
                transformations=transformations,
                raw_match_span=raw_span,
                raw_requirement_span=raw_requirement_span,
                requirement_text=requirement_text,
                strike_coverage=_strike_coverage(block, raw_requirement_span),
                value_tokens=_value_tokens(requirement_text),
                comparison_blocker=blocker,
                ambiguous=(candidate.item.item_id, raw_span) in ambiguous,
            )
        )
    return occurrences


# --- structured function sections --------------------------------------------


def _description_blocks(document: Document, start: int, end: int) -> tuple[list[int], bool]:
    """Locate one description column and keep each source paragraph separate."""
    blocks = document.blocks
    headers: set[TableCellCoordinates] = set()
    for block in blocks[start:end]:
        location = block.location
        cell = location.cell
        if (
            cell is not None
            and not location.ancestor_path
            and cell.row_index == 0
            and block.text.strip() == "功能描述"
        ):
            headers.add(cell)
    if len(headers) != 1:
        return [], True

    (header,) = headers
    table_index, column = header.table_index, header.column_index
    if header.column_span != 1 or table_index in document.limited_table_indices:
        return [], True
    rows: dict[int, list[int]] = {}
    populated_rows: set[int] = set()
    uncertain = False
    for index in range(start, end):
        block = blocks[index]
        location = block.location
        cell = location.cell
        if cell is None:
            continue
        top_cell = location.ancestor_path[0] if location.ancestor_path else cell
        if top_cell.table_index != table_index:
            # A later unlabelled table could be a separate continuation.
            uncertain |= top_cell.table_index > table_index and bool(block.text.strip())
            continue
        if top_cell.row_index == 0:
            continue
        if block.text.strip():
            populated_rows.add(top_cell.row_index)
        if top_cell.column_index == column:
            paragraphs = rows.setdefault(top_cell.row_index, [])
            if block.text.strip():
                paragraphs.append(index)
                uncertain |= (
                    bool(location.ancestor_path) or top_cell.column_span != 1 or len(paragraphs) > 1
                )

    descriptions = [index for paragraphs in rows.values() for index in paragraphs]
    return descriptions, uncertain or not descriptions or bool(populated_rows - rows.keys())


def _associate_table_descriptions(
    item: CheckItem,
    occurrences: Sequence[_Occurrence],
    document: Document,
    sections: Sequence[tuple[int, int, bool]],
) -> tuple[list[_Occurrence], bool]:
    located = [
        replace(occurrence, comparison_blocker=_TABLE_LOCATOR)
        if occurrence.match_type is not MatchType.EXPECTED_DESCRIPTION
        and any(start <= occurrence.block_index < end for start, end, _ in sections)
        else occurrence
        for occurrence in occurrences
    ]
    uncertain = False
    for start, end, shared in sections:
        if shared:
            uncertain = True
            continue
        indices, uncertain_section = _description_blocks(document, start + 1, end)
        uncertain |= uncertain_section
        heading = document.blocks[start]
        heading_active = any(
            occurrence.block_index == start
            and occurrence.match_type is not MatchType.EXPECTED_DESCRIPTION
            and not occurrence.ambiguous
            and _strike_coverage(heading, occurrence.raw_match_span) is StrikeCoverage.NONE
            for occurrence in occurrences
        )
        for index in indices:
            block = document.blocks[index]
            normalized = normalize(block.text).text
            span = (0, len(block.text))
            coverage = _strike_coverage(block, span)
            located.append(
                _Occurrence(
                    block_index=index,
                    item=item,
                    term=block.text,
                    alias_id="",
                    match_type=MatchType.TABLE_DESCRIPTION,
                    transformations=_active_rules(block.text),
                    raw_match_span=span,
                    raw_requirement_span=span,
                    requirement_text=normalized,
                    strike_coverage=coverage,
                    value_tokens=_value_tokens(normalized),
                    comparison_blocker="inactive-function-table-heading"
                    if coverage is StrikeCoverage.PARTIAL and not heading_active
                    else "",
                    ambiguous=False,
                    active_table_heading=heading_active,
                )
            )
    return located, uncertain


# --- classification ----------------------------------------------------------


def _conflicting_active_values(active: Sequence[_Occurrence], baseline: str | None) -> bool:
    value_sets = {
        o.value_tokens
        for o in active
        if o.value_tokens and o.comparison_blocker != _OVERLAPPING_IDENTITY
    }
    if len(value_sets) > 1:
        return True
    if baseline is None:
        return False

    # Projected descriptions already align to the baseline, so each
    # corresponding parameter can be compared in its original position.
    expected_structure, _ = _description_signature(baseline)
    aligned_values: set[tuple[str, ...]] = set()
    for occurrence in active:
        if not occurrence.comparison_blocker:
            structure, values = _description_signature(occurrence.requirement_text)
            if structure == expected_structure:
                aligned_values.add(values)
    return len(aligned_values) > 1


def _struck_rows_have_active_descriptions(
    document: Document,
    active: Sequence[_Occurrence],
    struck: Sequence[_Occurrence],
    baseline: str,
) -> bool:
    """Apply the exception only to evidence in a single actively identified GN table."""
    if (
        not active
        or not baseline.strip(_STRIKE_WHITESPACE)
        or _is_bare_identity(active[0].item, baseline)
    ):
        return False
    table_indices: set[int] = set()
    for occurrence in (*active, *struck):
        cell = document.blocks[occurrence.block_index].location.cell
        if (
            occurrence.match_type is not MatchType.TABLE_DESCRIPTION
            or not occurrence.active_table_heading
            or cell is None
        ):
            return False
        table_indices.add(cell.table_index)
    expected_structure, _ = _description_signature(baseline)
    return len(table_indices) == 1 and all(
        not occurrence.comparison_blocker
        and not _is_bare_identity(occurrence.item, occurrence.requirement_text)
        and _description_signature(occurrence.requirement_text)[0] == expected_structure
        for occurrence in active
    )


def _classify(
    item: CheckItem,
    occurrences: Sequence[_Occurrence],
    document: Document,
    uncertain_table: bool,
) -> CheckResult:
    expected_norm = normalize(item.expected_description).text
    evidence = tuple(
        MatchEvidence(
            evidence_id=f"{item.item_id}@{occurrence.block_index}:{index}",
            document_id=document.document_id,
            block_id=document.blocks[occurrence.block_index].block_id,
            location=document.blocks[occurrence.block_index].location,
            raw_text=document.blocks[occurrence.block_index].text,
            matched_span=occurrence.raw_match_span,
            requirement_span=occurrence.raw_requirement_span,
            requirement_text=occurrence.requirement_text,
            matched_term=occurrence.term,
            match_type=occurrence.match_type,
            transformations=occurrence.transformations,
            strike_coverage=occurrence.strike_coverage,
            alias_id=occurrence.alias_id,
            ambiguous=occurrence.ambiguous,
            comparison_blocker=occurrence.comparison_blocker,
            active_description_spans=_active_description_spans(
                document.blocks[occurrence.block_index], occurrence, expected_norm
            ),
        )
        for index, occurrence in enumerate(occurrences)
    )
    primary = next((e for e in evidence if e.match_type is MatchType.TABLE_DESCRIPTION), None)
    if primary is None:
        primary = next(
            (e for e in evidence if e.match_type is not MatchType.EXPECTED_DESCRIPTION),
            evidence[0] if evidence else None,
        )

    def result(
        resolution: Resolution,
        status: CheckStatus | None,
        comparison_state: ComparisonState,
        comparison_reason: str,
        review_reasons: tuple[str, ...],
    ) -> CheckResult:
        initial = primary
        if status is CheckStatus.CONFIGURED and primary and not primary.can_compare_description:
            initial = next((e for e in evidence if e.can_compare_description), primary)
        return CheckResult(
            check_item=item,
            document_id=document.document_id,
            resolution=resolution,
            status=status,
            evidence=evidence,
            comparison_state=comparison_state,
            comparison_reason=comparison_reason,
            review_reasons=review_reasons,
            rule_revision=RULE_REVISION,
            primary_evidence_id=initial.evidence_id if initial else "",
        )

    if not occurrences:
        return result(
            Resolution.RESOLVED,
            CheckStatus.MISSING,
            ComparisonState.NOT_COMPARED,
            "nothing-to-compare",
            (),
        )
    qualifying = [
        (o, e)
        for o, e in zip(occurrences, evidence, strict=True)
        if o.match_type is not MatchType.EXPECTED_DESCRIPTION
        and o.comparison_blocker != _TABLE_LOCATOR
    ]
    if not qualifying:
        return result(
            Resolution.UNRESOLVED,
            None,
            ComparisonState.NOT_COMPARED,
            "result-unresolved",
            ("uncertain-function-table" if uncertain_table else "expected-description-only",),
        )
    clean = [(o, e) for o, e in qualifying if not o.ambiguous]
    reasons = ["uncertain-function-table"] if uncertain_table else []
    if not clean:
        reasons.append("ambiguous-function-identity")
        return result(
            Resolution.UNRESOLVED,
            None,
            ComparisonState.NOT_COMPARED,
            "result-unresolved",
            tuple(reasons),
        )
    active = [o for o, _ in clean if o.strike_coverage is StrikeCoverage.NONE]
    struck = [o for o, _ in clean if o.strike_coverage is StrikeCoverage.FULL]
    if any(
        o.strike_coverage is StrikeCoverage.PARTIAL and not e.active_description_spans
        for o, e in clean
    ):
        reasons.append("partial-strike")
    if any(o.strike_coverage is StrikeCoverage.UNKNOWN for o, _ in clean):
        reasons.append("unknown-strike-formatting")
    projected = False
    for o, e in clean:
        if e.active_description_spans:
            text = normalize(e.description_source_text).text
            active.append(replace(o, requirement_text=text, value_tokens=_value_tokens(text)))
            projected = True
    reminders = ("partial-strike-active-description",) if projected else ()
    struck_rows_explained = False
    if active and struck:
        struck_rows_explained = _struck_rows_have_active_descriptions(
            document, active, struck, expected_norm
        )
        if struck_rows_explained:
            reminders = (*reminders, "struck-rows-with-active-description")
        else:
            reasons.append("active-and-struck-coexist")
    conflict_baseline = expected_norm if projected or struck_rows_explained else None
    if _conflicting_active_values(active, conflict_baseline):
        reasons.append("conflicting-key-parameters")
    if reasons:
        return result(
            Resolution.UNRESOLVED,
            None,
            ComparisonState.NOT_COMPARED,
            "result-unresolved",
            tuple(reasons),
        )
    if struck and not active:
        return result(
            Resolution.RESOLVED,
            CheckStatus.STRUCK_OUT,
            ComparisonState.NOT_COMPARED,
            "evidence-struck",
            (),
        )

    # Status CONFIGURED (active evidence exists); comparison is independent.
    if not item.expected_description:
        return result(
            Resolution.RESOLVED,
            CheckStatus.CONFIGURED,
            ComparisonState.NOT_COMPARED,
            "expected-description-empty",
            (),
        )
    comparable = [o for o in active if not o.comparison_blocker]
    if not comparable:
        return result(
            Resolution.RESOLVED,
            CheckStatus.CONFIGURED,
            ComparisonState.NOT_COMPARED,
            active[0].comparison_blocker or "mixed-comparison-occurrences",
            reminders,
        )
    matched = [o.requirement_text == expected_norm for o in comparable]
    if all(matched):
        state, reason = ComparisonState.SAME, ""
    elif not any(matched):
        state, reason = ComparisonState.DIFFERENT, ""
    else:
        state, reason = ComparisonState.NOT_COMPARED, "mixed-comparison-occurrences"
    return result(Resolution.RESOLVED, CheckStatus.CONFIGURED, state, reason, reminders)


def verify(
    document: Document,
    check_items: Sequence[CheckItem],
    cancel_check: Callable[[], bool] | None = None,
) -> tuple[CheckResult, ...]:
    """Run the deterministic rules over the document for the given items.

    A cancellation checkpoint is evaluated once per (item, block) pair
    immediately before that item's candidate search; a True flag raises
    VerificationCancelled so no partial result list can masquerade as a
    completed run. Cross-item ambiguity and requirement-span association run
    after all items' candidates for a block are collected. Results follow input
    item order; evidence keeps stable source order (block, then span).
    """
    by_item: dict[str, list[_Occurrence]] = {item.item_id: [] for item in check_items}
    item_terms = [(item, _search_terms(item)) for item in check_items]
    heading_owners: dict[int, set[str]] = {}
    for block_index, block in enumerate(document.blocks):
        norm = normalize(block.text)
        candidates: list[_Candidate] = []
        for item, terms in item_terms:
            if cancel_check is not None and cancel_check():
                raise VerificationCancelled("verification cancelled at a checkpoint")
            candidates.extend(_collect_candidates(item, norm, block.text, terms))
        if block.location.part == "body" and _GN_HEADING.match(norm.text):
            heading_owners[block_index] = {
                candidate.item.item_id
                for candidate in candidates
                if candidate.match_type is not MatchType.EXPECTED_DESCRIPTION
            }
        for occurrence in _associate_candidates(candidates, norm, block, block_index):
            by_item[occurrence.item.item_id].append(occurrence)
    sections: dict[str, list[tuple[int, int, bool]]] = {}
    for start, end in pairwise([*heading_owners, len(document.blocks)]):
        owners = heading_owners[start]
        for item_id in owners:
            sections.setdefault(item_id, []).append((start, end, len(owners) > 1))

    results: list[CheckResult] = []
    for item in check_items:
        occurrences, uncertain_table = _associate_table_descriptions(
            item, by_item[item.item_id], document, sections.get(item.item_id, ())
        )
        occurrences.sort(key=lambda o: (o.block_index, o.raw_match_span))
        results.append(_classify(item, occurrences, document, uncertain_table))
    return tuple(results)
