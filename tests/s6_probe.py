"""S6 spike probe: deterministic detection, normalization and classification rules.

Exploratory validation code for Task 1/S6, kept isolated from ``src/`` exactly
like ``docx_probe.py``. It is NOT the production matching engine; it validates
the rules Task 3 must implement against hand-labelled fixtures
(test_spike_s6_rules.py / test_spike_s6_scale.py).

Validated rule set (docs/constitution.md §7, docs/spec.md §5–§6):
- normalization allowlist N1 whitespace-run collapse, N2 within-block line
  breaks -> single space, N3 fullwidth ASCII punctuation -> ASCII; nothing else;
- matching in normalized space with raw span mapping (traceability);
- requirement span: forward clause extension from the match start to the next
  boundary (delimiter or next qualifying match start); no backward extension;
- strike evaluated over the requirement span, not the whole paragraph;
- value tokens (number + fixed unit) used only for conflict detection;
- one span claimed by different term texts across items is UNRESOLVED;
  identical term texts on several items are a baseline-validation (Task 5)
  configuration defect, not verification ambiguity;
- detection, resolution and description comparison stay independent; no score.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from design_requirement_checker.domain import (
    BlockType,
    DocumentBlock,
    DocumentLocation,
    TextRun,
)

# --- normalization allowlist ------------------------------------------------

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
#: Span-boundary delimiters recognized in normalized text. '、' and '。' are
#: ideographic punctuation that is deliberately NOT text-normalized (rejected
#: transformations R1/R2), but both are recognized as delimiters here.
_BOUNDARY_CHARS = frozenset(";.!? ,、。")
_SENTENCE_END_CHARS = frozenset(".!?。")


class SpikeCancelled(Exception):
    """Raised at a cancellation checkpoint; never yields a completed run."""


@dataclass(frozen=True)
class NormalizedText:
    """Normalized text plus per-character raw source spans (traceability)."""

    text: str
    char_sources: tuple[tuple[int, int], ...]


def normalize(raw: str) -> NormalizedText:
    """Apply the S6 allowlist to one block's raw text.

    N1/N2: any run of spaces/tabs/ideographic spaces/line breaks becomes one
    ASCII space (within this block only — blocks are never joined). N3 maps
    fullwidth ASCII punctuation to its ASCII counterpart. Everything else,
    including ideographic '。', fullwidth digits/letters and letter case, is
    preserved verbatim.
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


# --- value tokens (conflict detection only) ---------------------------------

_VALUE_TOKEN_RE = re.compile(
    r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?) ?"
    r"(km/h|kHz|MHz|mV|kW|ms|min|mm|cm|km|Hz|V|A|W|h|m|s|%)"
)


def value_tokens(normalized_text: str) -> frozenset[str]:
    """Engineering value tokens (number + unit) inside normalized text.

    Used ONLY to detect conflicting key parameters between occurrences; the
    tokens never replace the text in comparisons. One collapsed space between
    number and unit is tolerated ('3 s' -> '3s'); text itself is unchanged.
    """
    return frozenset(f"{number}{unit}" for number, unit in _VALUE_TOKEN_RE.findall(normalized_text))


# --- spike fixtures ----------------------------------------------------------

_SPIKE_DOC_ID = "s6-spike"


@dataclass(frozen=True)
class S6CheckItem:
    """In-memory CheckItem-like fixture; no persistence, no production model."""

    item_id: str
    detection_phrase: str
    expected_description: str = ""
    aliases: tuple[str, ...] = ()
    name: str = ""  # display only — never used for detection


def make_item(
    item_id: str,
    detection_phrase: str,
    expected_description: str = "",
    aliases: Sequence[str] = (),
    name: str = "",
) -> S6CheckItem:
    if not detection_phrase:
        raise ValueError("detection_phrase is required")
    return S6CheckItem(
        item_id=item_id,
        detection_phrase=detection_phrase,
        expected_description=expected_description,
        aliases=tuple(aliases),
        name=name or f"name-{item_id}",
    )


def make_block(block_index: int, parts: Sequence[tuple[str, bool | None]]) -> DocumentBlock:
    """Build a real domain DocumentBlock from (text, strike) run parts.

    ``strike`` is True/False for resolved formatting and None for unknown;
    the domain requires a reason exactly when strike is unknown.
    """
    runs: list[TextRun] = []
    offset = 0
    for text, strike in parts:
        if not text:
            continue
        runs.append(
            TextRun(
                text=text,
                start_offset=offset,
                end_offset=offset + len(text),
                effective_strike=strike,
                strike_origin="run-direct" if strike is not None else "default-off",
                strike_reason="" if strike is not None else "spike-unknown-formatting",
            )
        )
        offset += len(text)
    location = DocumentLocation(
        document_id=_SPIKE_DOC_ID,
        block_id=f"body:p{block_index}",
        block_type=BlockType.PARAGRAPH,
        part="body",
        paragraph_index=block_index,
    )
    return DocumentBlock(
        block_id=f"body:p{block_index}",
        block_type=BlockType.PARAGRAPH,
        text="".join(r.text for r in runs),
        runs=tuple(runs),
        location=location,
    )


# --- occurrence collection and association -----------------------------------

_TYPE_RANK = {"EXACT": 0, "NORMALIZED": 1, "ALIAS": 2}


@dataclass(frozen=True)
class Occurrence:
    """One qualifying candidate with its spans and evaluation inputs."""

    block_index: int
    term: str
    term_kind: str  # "detection-phrase" | "alias"
    match_type: str  # "EXACT" | "NORMALIZED" | "ALIAS"
    raw_match_span: tuple[int, int]
    raw_requirement_span: tuple[int, int]
    strike_coverage: str  # "NONE" | "FULL" | "PARTIAL" | "UNKNOWN"
    value_tokens: frozenset[str]
    requirement_text: str  # normalized requirement-span text (display/compare)
    comparison_blocker: str = ""  # non-empty when this occurrence cannot compare
    ambiguous: bool = False


@dataclass(frozen=True)
class S6Result:
    """Spike-level result: identity/resolution/status/comparison stay separate."""

    item_id: str
    resolution: str  # "RESOLVED" | "UNRESOLVED"
    status: str | None  # "CONFIGURED" | "MISSING" | "STRUCK_OUT" | None
    comparison_state: str  # "SAME" | "DIFFERENT" | "NOT_COMPARED"
    comparison_reason: str
    reasons: tuple[str, ...]
    occurrences: tuple[Occurrence, ...]


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


def _strike_coverage(block: DocumentBlock, raw_span: tuple[int, int]) -> str:
    """Strike coverage over the requirement span (never the whole paragraph)."""
    start, end = raw_span
    pieces: list[bool | None] = []
    for run in block.runs:
        lo = max(start, run.start_offset)
        hi = min(end, run.end_offset)
        if lo < hi:
            pieces.append(run.effective_strike)
    if not pieces:
        return "UNKNOWN"
    if any(p is None for p in pieces):
        return "UNKNOWN"
    if all(p is True for p in pieces):
        return "FULL"
    if all(p is False for p in pieces):
        return "NONE"
    return "PARTIAL"


@dataclass
class _Working:
    """Mutable working state while collecting one block's occurrences."""

    item: S6CheckItem
    term: str
    term_kind: str
    norm_span: tuple[int, int]
    raw_span: tuple[int, int]
    match_type: str = "NORMALIZED"
    norm_req_span: tuple[int, int] = (0, 0)
    raw_req_span: tuple[int, int] = (0, 0)
    strike_coverage: str = "NONE"
    value_tokens: frozenset[str] = frozenset()
    requirement_text: str = ""
    comparison_blocker: str = ""
    ambiguous: bool = False


def _association_blocker(
    item: S6CheckItem, norm_text: str, norm_span: tuple[int, int], norm_req_end: int
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
    if not value_tokens(span_text):
        expected_norm = normalize(item.expected_description).text
        if value_tokens(expected_norm):
            sentence_end = norm_req_end
            while sentence_end < len(norm_text) and norm_text[sentence_end] not in (
                _SENTENCE_END_CHARS
            ):
                sentence_end += 1
            if value_tokens(norm_text[norm_req_end:sentence_end]):
                return "requirement-span-association-uncertain"
        if norm_req_end == norm_span[1]:
            if normalize(item.expected_description).text != span_text:
                return "no-associated-requirement-content"
    return ""


def _collect_block(
    items: Sequence[S6CheckItem], block: DocumentBlock, block_index: int
) -> list[_Working]:
    norm = normalize(block.text)
    best: dict[tuple[str, tuple[int, int]], _Working] = {}
    for item in items:
        terms: list[tuple[str, str]] = [(item.detection_phrase, "detection-phrase")]
        terms.extend((alias, "alias") for alias in item.aliases)
        for term, kind in terms:
            term_norm = normalize(term).text
            for ns, ne in _find_all(norm.text, term_norm):
                raw_span = map_span(norm, ns, ne)
                if kind == "alias":
                    match_type = "ALIAS"
                elif block.text[raw_span[0] : raw_span[1]] == term:
                    match_type = "EXACT"
                else:
                    match_type = "NORMALIZED"
                entry = _Working(
                    item=item,
                    term=term,
                    term_kind=kind,
                    norm_span=(ns, ne),
                    raw_span=raw_span,
                    match_type=match_type,
                )
                key = (item.item_id, raw_span)
                current = best.get(key)
                if current is None or _TYPE_RANK[match_type] < _TYPE_RANK[current.match_type]:
                    best[key] = entry
    working = list(best.values())

    # Ambiguity: one raw span claimed by different term texts across items —
    # the text cannot safely establish which function identity applies.
    # Identical term texts shared by several items are NOT verification
    # ambiguity (the text genuinely contains the phrase for each item); the
    # duplicate configuration itself is a baseline-validation (Task 5) defect.
    for i, left in enumerate(working):
        for right in working[i + 1 :]:
            if left.item.item_id == right.item.item_id:
                continue
            if left.term == right.term:
                continue
            ls, le = left.raw_span
            rs, re_ = right.raw_span
            if ls < re_ and rs < le:
                left.ambiguous = True
                right.ambiguous = True

    # requirement-span association: forward to next boundary or next match start
    starts = [w.norm_span[0] for w in working]
    for w in working:
        s, e = w.norm_span
        end = len(norm.text)
        k = e
        while k < len(norm.text):
            if _is_boundary(norm.text, k):
                end = k
                break
            k += 1
        for other_start in starts:
            if other_start >= e and other_start < end:
                end = other_start
        w.norm_req_span = (s, end)
        w.raw_req_span = (norm.char_sources[s][0], norm.char_sources[end - 1][1])
        w.requirement_text = norm.text[s:end]
        w.strike_coverage = _strike_coverage(block, w.raw_req_span)
        w.value_tokens = value_tokens(w.requirement_text)
        w.comparison_blocker = _association_blocker(w.item, norm.text, w.norm_span, end)

    return working


def _classify(item: S6CheckItem, occs: list[Occurrence]) -> S6Result:
    if not occs:
        return S6Result(
            item_id=item.item_id,
            resolution="RESOLVED",
            status="MISSING",
            comparison_state="NOT_COMPARED",
            comparison_reason="nothing-to-compare",
            reasons=(),
            occurrences=(),
        )
    clean = [o for o in occs if not o.ambiguous]
    if not clean:
        return S6Result(
            item_id=item.item_id,
            resolution="UNRESOLVED",
            status=None,
            comparison_state="NOT_COMPARED",
            comparison_reason="result-unresolved",
            reasons=("ambiguous-function-identity",),
            occurrences=tuple(occs),
        )

    active = [o for o in clean if o.strike_coverage == "NONE"]
    struck = [o for o in clean if o.strike_coverage == "FULL"]
    reasons: list[str] = []
    if any(o.strike_coverage == "PARTIAL" for o in clean):
        reasons.append("partial-strike")
    if any(o.strike_coverage == "UNKNOWN" for o in clean):
        reasons.append("unknown-strike-formatting")
    if active and struck:
        reasons.append("active-and-struck-coexist")
    if active:
        value_sets = [o.value_tokens for o in active if o.value_tokens]
        if len(value_sets) >= 2 and any(v != value_sets[0] for v in value_sets[1:]):
            reasons.append("conflicting-key-parameters")
    if reasons:
        return S6Result(
            item_id=item.item_id,
            resolution="UNRESOLVED",
            status=None,
            comparison_state="NOT_COMPARED",
            comparison_reason="result-unresolved",
            reasons=tuple(reasons),
            occurrences=tuple(occs),
        )

    if struck and not active:
        return S6Result(
            item_id=item.item_id,
            resolution="RESOLVED",
            status="STRUCK_OUT",
            comparison_state="NOT_COMPARED",
            comparison_reason="evidence-struck",
            reasons=(),
            occurrences=tuple(occs),
        )

    # status == CONFIGURED (active evidence exists); comparison is independent
    if not item.expected_description:
        comparison_state, comparison_reason = "NOT_COMPARED", "expected-description-empty"
    else:
        comparable = [o for o in active if not o.comparison_blocker]
        if not comparable:
            comparison_state = "NOT_COMPARED"
            comparison_reason = active[0].comparison_blocker or "mixed-comparison-occurrences"
        else:
            expected_norm = normalize(item.expected_description).text
            matched = [o.requirement_text == expected_norm for o in comparable]
            if all(matched):
                comparison_state, comparison_reason = "SAME", ""
            elif not any(matched):
                comparison_state, comparison_reason = "DIFFERENT", ""
            else:
                comparison_state, comparison_reason = "NOT_COMPARED", "mixed-comparison-occurrences"
    return S6Result(
        item_id=item.item_id,
        resolution="RESOLVED",
        status="CONFIGURED",
        comparison_state=comparison_state,
        comparison_reason=comparison_reason,
        reasons=(),
        occurrences=tuple(occs),
    )


def verify(
    items: Sequence[S6CheckItem],
    blocks: Sequence[DocumentBlock],
    cancel_check: Callable[[], bool] | None = None,
) -> list[S6Result]:
    """Run the spike rules over all items and blocks (evidence, not production).

    A cancellation checkpoint is evaluated once per (item, block) pair; when it
    returns True, ``SpikeCancelled`` is raised so no misleading completed run
    is ever produced.
    """
    by_item: dict[str, list[Occurrence]] = {item.item_id: [] for item in items}
    for block_index, block in enumerate(blocks):
        for item in items:
            if cancel_check is not None and cancel_check():
                raise SpikeCancelled("verification cancelled at a checkpoint")
        for w in _collect_block(items, block, block_index):
            by_item[w.item.item_id].append(
                Occurrence(
                    block_index=block_index,
                    term=w.term,
                    term_kind=w.term_kind,
                    match_type=w.match_type,
                    raw_match_span=w.raw_span,
                    raw_requirement_span=w.raw_req_span,
                    strike_coverage=w.strike_coverage,
                    value_tokens=w.value_tokens,
                    requirement_text=w.requirement_text,
                    comparison_blocker=w.comparison_blocker,
                    ambiguous=w.ambiguous,
                )
            )
    results = []
    for item in items:
        occs = sorted(by_item[item.item_id], key=lambda o: (o.block_index, o.raw_match_span))
        results.append(_classify(item, occs))
    return results


# --- synthetic scale generator ------------------------------------------------


def generate_scale_document(
    blocks_n: int, items_n: int, hits_per_item: int = 2
) -> tuple[list[S6CheckItem], list[DocumentBlock]]:
    """Deterministic synthetic document approximating representative scale.

    Each item's detection phrase is embedded exactly ``hits_per_item`` times,
    each time as its own clause with the value 3s, so occurrence counts and
    classifications are known by construction (CONFIGURED + DIFFERENT).
    """
    items = [
        make_item(f"item-{j}", f"功能{j}增加延时", f"功能{j}增加延时2s功能") for j in range(items_n)
    ]
    embeds: dict[int, list[str]] = {}
    for j in range(items_n):
        for k in range(hits_per_item):
            idx = (j * 37 + k * 101 + 3) % blocks_n
            embeds.setdefault(idx, []).append(f"功能{j}增加延时3s功能。")
    blocks = []
    for i in range(blocks_n):
        filler = (
            f"第{i:05d}段通用工程说明：本段描述整车电气架构分区、线束走向、"
            "接插件选型与常规工程约束，供规模探测使用。"
        )
        text = filler + "".join(embeds.get(i, []))
        blocks.append(make_block(i, [(text, False)]))
    return items, blocks


def measure_scale(blocks_n: int, items_n: int) -> dict[str, float]:
    """Wall-clock measurement helper used when recording spike evidence."""
    items, blocks = generate_scale_document(blocks_n, items_n)
    started = time.perf_counter()
    verify(items, blocks)
    return {"wall_seconds": time.perf_counter() - started, "blocks": blocks_n, "items": items_n}
