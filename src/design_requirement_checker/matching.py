"""Pure deterministic verification: detection, evidence and classification.

Implements the Task 3 contract validated by the merged S6 spike
(docs/technical-spikes.md, "Executed evidence — S6"): the exact normalization
allowlist (N1/N2/N3) with raw-offset traceability, configured-phrase/alias
detection, forward-only requirement-span association, strike coverage over the
requirement span, the confirmed resolution truth table and the independent
expected-description comparison. Inputs and outputs are domain values only;
this module must stay free of Qt, python-docx and filesystem dependencies.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

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
#: Match-method reporting preference: exact → normalized → alias.
_TYPE_RANK = {MatchType.EXACT: 0, MatchType.NORMALIZED: 1, MatchType.ALIAS: 2}


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


# --- value tokens (conflict detection only, never comparison) ---------------

_VALUE_TOKEN_RE = re.compile(
    r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?) ?"
    r"(km/h|kHz|MHz|mV|kW|ms|min|mm|cm|km|Hz|V|A|W|h|m|s|%)"
)


def _value_tokens(normalized_text: str) -> frozenset[str]:
    return frozenset(f"{number}{unit}" for number, unit in _VALUE_TOKEN_RE.findall(normalized_text))


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
    norm_span: tuple[int, int]
    raw_requirement_span: tuple[int, int]
    requirement_text: str
    strike_coverage: StrikeCoverage
    value_tokens: frozenset[str]
    comparison_blocker: str
    ambiguous: bool


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


def _collect_block(
    items: Sequence[CheckItem], block: DocumentBlock, block_index: int
) -> list[_Occurrence]:
    norm = normalize(block.text)

    # Candidate collection: one entry per (item, raw span), keeping the best
    # match method (exact → normalized → alias) for reporting.
    best: dict[tuple[str, tuple[int, int]], _Candidate] = {}
    for item in items:
        terms: list[tuple[str, str, MatchType]] = [(item.detection_phrase, "", MatchType.EXACT)]
        terms.extend((alias.text, alias.alias_id, MatchType.ALIAS) for alias in item.aliases)
        for term, alias_id, configured_type in terms:
            term_norm = normalize(term).text
            for norm_start, norm_end in _find_all(norm.text, term_norm):
                raw_span = map_span(norm, norm_start, norm_end)
                if configured_type is MatchType.ALIAS:
                    match_type = MatchType.ALIAS
                elif block.text[raw_span[0] : raw_span[1]] == term:
                    match_type = MatchType.EXACT
                else:
                    match_type = MatchType.NORMALIZED
                candidate = _Candidate(item, term, alias_id, match_type, (norm_start, norm_end))
                key = (item.item_id, raw_span)
                current = best.get(key)
                if current is None or _TYPE_RANK[match_type] < _TYPE_RANK[current.match_type]:
                    best[key] = candidate

    ordered = sorted(best.items(), key=lambda pair: (pair[0][1], pair[1].term))

    # Ambiguity: one raw span claimed by different term texts across items —
    # the text cannot safely establish which function identity applies.
    # Identical term texts on several items are a baseline-validation (Task 5)
    # configuration defect, not verification ambiguity.
    ambiguous: set[tuple[str, tuple[int, int]]] = set()
    for i, (left_key, left) in enumerate(ordered):
        for right_key, right in ordered[i + 1 :]:
            if left_key[0] == right_key[0] or left.term == right.term:
                continue
            left_start, left_end = left_key[1]
            right_start, right_end = right_key[1]
            if left_start < right_end and right_start < left_end:
                ambiguous.add(left_key)
                ambiguous.add(right_key)

    # Requirement-span association: forward only, to the earliest boundary
    # delimiter, next qualifying match start or block end (S6 rule).
    match_starts = [candidate.norm_span[0] for _, candidate in ordered]
    occurrences: list[_Occurrence] = []
    for (item_id, raw_span), candidate in ordered:
        norm_start, norm_end = candidate.norm_span
        end = len(norm.text)
        k = norm_end
        while k < len(norm.text):
            if _is_boundary(norm.text, k):
                end = k
                break
            k += 1
        for other_start in match_starts:
            if norm_end <= other_start < end:
                end = other_start
        requirement_text = norm.text[norm_start:end]
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
        occurrences.append(
            _Occurrence(
                block_index=block_index,
                item=candidate.item,
                term=candidate.term,
                alias_id=candidate.alias_id,
                match_type=candidate.match_type,
                transformations=transformations,
                raw_match_span=raw_span,
                norm_span=candidate.norm_span,
                raw_requirement_span=(
                    norm.char_sources[norm_start][0],
                    norm.char_sources[end - 1][1],
                ),
                requirement_text=requirement_text,
                strike_coverage=_strike_coverage(
                    block,
                    (
                        norm.char_sources[norm_start][0],
                        norm.char_sources[end - 1][1],
                    ),
                ),
                value_tokens=_value_tokens(requirement_text),
                comparison_blocker=_association_blocker(
                    candidate.item, norm.text, candidate.norm_span, end
                ),
                ambiguous=(item_id, raw_span) in ambiguous,
            )
        )
    return occurrences


# --- classification ----------------------------------------------------------


def _classify(
    item: CheckItem, occurrences: Sequence[_Occurrence], document: Document
) -> CheckResult:
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
        )
        for index, occurrence in enumerate(occurrences)
    )

    def result(
        resolution: Resolution,
        status: CheckStatus | None,
        comparison_state: ComparisonState,
        comparison_reason: str,
        review_reasons: tuple[str, ...],
    ) -> CheckResult:
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
            primary_evidence_id=evidence[0].evidence_id if evidence else "",
        )

    if not occurrences:
        return result(
            Resolution.RESOLVED,
            CheckStatus.MISSING,
            ComparisonState.NOT_COMPARED,
            "nothing-to-compare",
            (),
        )
    clean = [o for o in occurrences if not o.ambiguous]
    if not clean:
        return result(
            Resolution.UNRESOLVED,
            None,
            ComparisonState.NOT_COMPARED,
            "result-unresolved",
            ("ambiguous-function-identity",),
        )
    active = [o for o in clean if o.strike_coverage is StrikeCoverage.NONE]
    struck = [o for o in clean if o.strike_coverage is StrikeCoverage.FULL]
    reasons: list[str] = []
    if any(o.strike_coverage is StrikeCoverage.PARTIAL for o in clean):
        reasons.append("partial-strike")
    if any(o.strike_coverage is StrikeCoverage.UNKNOWN for o in clean):
        reasons.append("unknown-strike-formatting")
    if active and struck:
        reasons.append("active-and-struck-coexist")
    if active:
        value_sets = [o.value_tokens for o in active if o.value_tokens]
        if len(value_sets) >= 2 and any(v != value_sets[0] for v in value_sets[1:]):
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
            (),
        )
    expected_norm = normalize(item.expected_description).text
    matched = [o.requirement_text == expected_norm for o in comparable]
    if all(matched):
        state, reason = ComparisonState.SAME, ""
    elif not any(matched):
        state, reason = ComparisonState.DIFFERENT, ""
    else:
        state, reason = ComparisonState.NOT_COMPARED, "mixed-comparison-occurrences"
    return result(Resolution.RESOLVED, CheckStatus.CONFIGURED, state, reason, ())


def verify(
    document: Document,
    check_items: Sequence[CheckItem],
    cancel_check: Callable[[], bool] | None = None,
) -> tuple[CheckResult, ...]:
    """Run the deterministic rules over the document for the given items.

    A cancellation checkpoint is evaluated once per (item, block) pair before
    that pair's evidence is collected; a True flag raises VerificationCancelled
    so no partial result list can masquerade as a completed run. Results follow
    input item order; evidence keeps stable source order (block, then span).
    """
    by_item: dict[str, list[_Occurrence]] = {item.item_id: [] for item in check_items}
    for block_index, block in enumerate(document.blocks):
        for item in check_items:
            if cancel_check is not None and cancel_check():
                raise VerificationCancelled("verification cancelled at a checkpoint")
        for occurrence in _collect_block(check_items, block, block_index):
            by_item[occurrence.item.item_id].append(occurrence)
    results: list[CheckResult] = []
    for item in check_items:
        occurrences = sorted(by_item[item.item_id], key=lambda o: (o.block_index, o.raw_match_span))
        results.append(_classify(item, occurrences, document))
    return tuple(results)
