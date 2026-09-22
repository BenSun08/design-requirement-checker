"""Application coordination: import and deterministic verification.

Use cases here coordinate domain values, the DOCX adapter and the pure
matching rules without touching widgets. Baseline persistence and the Qt
review workspace remain future slices (docs/implementation-plan.md).
"""

from __future__ import annotations

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
from design_requirement_checker.matching import VerificationCancelled, normalize
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


# ---------------------------------------------------------------------------
# Baseline cross-item validation (Task 5, T5.2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BaselineValidationIssue:
    """One validation error or warning.

    ``kind`` is a stable token like ``"duplicate-code"``, ``"duplicate-name"``,
    ``"phrase-collision"``, or ``"phrase-overlap"`` so presentation layers can
    render consistent messaging. ``item_ids`` lists the CheckItems involved.
    """

    kind: str
    message: str
    item_ids: tuple[str, ...]


@dataclass(frozen=True)
class BaselineValidationResult:
    """Errors and warnings from baseline-level validation."""

    errors: tuple[BaselineValidationIssue, ...]
    warnings: tuple[BaselineValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors


def validate_baseline(items: Sequence[CheckItem]) -> BaselineValidationResult:
    """Cross-item baseline validation (outside matching, outside persistence).

    Hard errors block save:

      - duplicate ``code`` across items

    Warnings surface but do not block save:

      - duplicate ``name`` across items
      - same or overlapping configured phrases (detection_phrase or alias
        text) across items, compared after the S6 normalize allowlist from
        ``matching.normalize``

    Disabled items are validated the same as enabled items — their presence
    in the persisted baseline is still meaningful. Duplicates inside the same
    item (e.g. detection_phrase equals an alias) are warned but do not block.

    Returns a deterministic, stable-order result.
    """
    errors: list[BaselineValidationIssue] = []
    warnings: list[BaselineValidationIssue] = []

    # --- Duplicate code (error) ---
    code_to_ids: dict[str, list[str]] = {}
    for item in items:
        code_to_ids.setdefault(item.code, []).append(item.item_id)
    for code, ids in code_to_ids.items():
        if len(ids) > 1:
            ids_sorted = tuple(sorted(ids))
            errors.append(
                BaselineValidationIssue(
                    kind="duplicate-code",
                    message=f"检查项编号重复：{code}，涉及 {len(ids)} 项",
                    item_ids=ids_sorted,
                )
            )

    # --- Duplicate name (warning) ---
    name_to_ids: dict[str, list[str]] = {}
    for item in items:
        name_to_ids.setdefault(item.name, []).append(item.item_id)
    for name, ids in name_to_ids.items():
        if len(ids) > 1:
            ids_sorted = tuple(sorted(ids))
            warnings.append(
                BaselineValidationIssue(
                    kind="duplicate-name",
                    message=f"功能名称重复：{name}，涉及 {len(ids)} 项",
                    item_ids=ids_sorted,
                )
            )

    # --- Phrase collisions and overlaps (warning) ---
    # Build per-item list of (normalized_phrase, raw_phrase, item_id, phrase_role)
    # phrase_role is "detection" or "alias-N" for distinguishing which slot it came from.
    phrases_per_item: dict[str, list[tuple[str, str, str]]] = {}
    for item in items:
        n_det = normalize(item.detection_phrase).text
        entries: list[tuple[str, str, str]] = [(n_det, item.detection_phrase, item.item_id)]
        for idx, alias in enumerate(item.aliases):
            n_alias = normalize(alias.text).text
            entries.append((n_alias, alias.text, item.item_id))
        phrases_per_item[item.item_id] = entries

    # Compare phrases across pairs of items (i1 < i2 to avoid double-count).
    item_ids_sorted = sorted(phrases_per_item.keys())
    seen_collision_pairs: set[tuple[str, ...]] = set()
    seen_overlap_pairs: set[tuple[str, ...]] = set()

    for idx_a in range(len(item_ids_sorted)):
        for idx_b in range(idx_a + 1, len(item_ids_sorted)):
            id_a = item_ids_sorted[idx_a]
            id_b = item_ids_sorted[idx_b]
            for n_a, raw_a, _ in phrases_per_item[id_a]:
                for n_b, raw_b, _ in phrases_per_item[id_b]:
                    if not n_a or not n_b:
                        continue
                    if n_a == n_b:
                        key = tuple(sorted((id_a, id_b)))
                        if key not in seen_collision_pairs:
                            seen_collision_pairs.add(key)
                            warnings.append(
                                BaselineValidationIssue(
                                    kind="phrase-collision",
                                    message=(
                                        f"检测短语重复：项 {id_a}（{raw_a!r}）"
                                        f"与项 {id_b}（{raw_b!r}）"
                                    ),
                                    item_ids=key,
                                )
                            )
                    elif n_a in n_b or n_b in n_a:
                        key = tuple(sorted((id_a, id_b)))
                        if key not in seen_overlap_pairs:
                            seen_overlap_pairs.add(key)
                            warnings.append(
                                BaselineValidationIssue(
                                    kind="phrase-overlap",
                                    message=(
                                        f"检测短语重叠：项 {id_a}（{raw_a!r}）"
                                        f"与项 {id_b}（{raw_b!r}）"
                                    ),
                                    item_ids=key,
                                )
                            )

    # Also warn same-item phrase duplicates (detection equals one of its aliases).
    for item in items:
        normalized_phrases_in_item: dict[str, str] = {}  # normalized → first raw
        n_det = normalize(item.detection_phrase).text
        if n_det:
            normalized_phrases_in_item[n_det] = item.detection_phrase
        for alias in item.aliases:
            n_a = normalize(alias.text).text
            if n_a and n_a in normalized_phrases_in_item:
                warnings.append(
                    BaselineValidationIssue(
                        kind="phrase-self-collision",
                        message=(
                            f"项 {item.item_id} 内部短语重复："
                            f"{normalized_phrases_in_item[n_a]!r} 与 {alias.text!r}"
                        ),
                        item_ids=(item.item_id,),
                    )
                )
            elif n_a:
                normalized_phrases_in_item[n_a] = alias.text

    # Stable deterministic ordering: errors first by item_ids, then warnings by kind
    # then item_ids.
    errors.sort(key=lambda e: (e.item_ids, e.kind))
    warnings.sort(key=lambda w: (w.kind, w.item_ids))

    return BaselineValidationResult(
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
