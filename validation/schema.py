"""Task 6 historical-validation data contract (schemaVersion 1).

This module defines the *ground-truth* side of the historical validation:
an anonymous document manifest plus per-document, per-CheckItem independent
human labels. It is deliberately separate from the production domain models:

- Ground truth is conceptually independent of checker output. These types are
  never constructed from ``CheckResult`` values and the production
  ``CheckResult`` invariants are not reused as the only validator here —
  validation is implemented explicitly in this module.
- Tokens are stable machine strings aligned with the domain vocabulary
  (RESOLVED/UNRESOLVED, CONFIGURED/MISSING/STRUCK_OUT, SAME/DIFFERENT/
  NOT_COMPARED, NONE/FULL/PARTIAL/UNKNOWN, COMPLETE/LIMITED) so metric code
  never depends on presentation-only Chinese labels.

Ground-truth separation rule (must not be violated):

    historical/sanitized DOCX -> independent human label -> this schema
    -> run current checker -> prediction -> compare

Copying checker output into an expected label is circular validation and is
forbidden (see validation/README.md).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Current validation schema version. Bump only with an explicit contract change.
SCHEMA_VERSION = 1

#: Allowed machine tokens (uppercase, stable, presentation-independent).
RESOLUTIONS = ("RESOLVED", "UNRESOLVED")
STATUSES = ("CONFIGURED", "MISSING", "STRUCK_OUT")
COMPARISONS = ("SAME", "DIFFERENT", "NOT_COMPARED")
STRIKE_COVERAGES = ("NONE", "FULL", "PARTIAL", "UNKNOWN")
COVERAGES = ("COMPLETE", "LIMITED")
#: sanitizationState values: "sanitized" = confidential content removed or
#: replaced; "synthetic" = fabricated document, NOT historical evidence;
#: "local-only" = real document kept outside Git, referenced by path.
SANITIZATION_STATES = ("sanitized", "synthetic", "local-only")


class ValidationSchemaError(ValueError):
    """A validation manifest or label file violates the Task 6 contract.

    ``code`` is a stable machine token so callers (and tests) can distinguish
    failure classes without matching message text.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _require_str(data: dict[str, Any], field: str, *, where: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value:
        raise ValidationSchemaError(
            "missing-or-invalid-field", f"{where}: field {field!r} must be a non-empty string"
        )
    return value


def _optional_str(data: dict[str, Any], field: str, *, where: str) -> str:
    value = data.get(field, "")
    if not isinstance(value, str):
        raise ValidationSchemaError(
            "missing-or-invalid-field", f"{where}: field {field!r} must be a string"
        )
    return value


def _require_enum(data: dict[str, Any], field: str, allowed: tuple[str, ...], *, where: str) -> str:
    value = _require_str(data, field, where=where)
    if value not in allowed:
        raise ValidationSchemaError(
            "unknown-token", f"{where}: field {field!r} value {value!r} not in {list(allowed)}"
        )
    return value


def _optional_enum(
    data: dict[str, Any], field: str, allowed: tuple[str, ...], *, where: str
) -> str | None:
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or value not in allowed:
        raise ValidationSchemaError(
            "unknown-token", f"{where}: field {field!r} value {value!r} not in {list(allowed)}"
        )
    return value


# ---------------------------------------------------------------------------
# Per-item ground truth
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ItemLabel:
    """Independent human ground truth for one (document, CheckItem) pair."""

    item_id: str
    expected_resolution: str  # RESOLVED | UNRESOLVED
    expected_status: str | None  # CONFIGURED | MISSING | STRUCK_OUT, None iff UNRESOLVED
    expected_comparison: str | None  # SAME | DIFFERENT | NOT_COMPARED, None = not labelled
    expected_strike: str | None  # optional independently labelled strike condition
    expected_coverage: str | None  # optional document-level relevance note per item
    include_in_metrics: bool
    exclusion_reason: str
    notes: str


def parse_item_label(data: Any, *, where: str) -> ItemLabel:
    """Parse and validate one label entry. Raises ValidationSchemaError."""
    if not isinstance(data, dict):
        raise ValidationSchemaError("invalid-entry", f"{where}: label entry must be an object")
    item_id = _require_str(data, "itemId", where=where)
    resolution = _require_enum(data, "expectedResolution", RESOLUTIONS, where=where)
    status = _optional_enum(data, "expectedStatus", STATUSES, where=where)
    comparison = _optional_enum(data, "expectedComparison", COMPARISONS, where=where)
    strike = _optional_enum(data, "expectedStrike", STRIKE_COVERAGES, where=where)
    coverage = _optional_enum(data, "expectedCoverage", COVERAGES, where=where)

    # Ground-truth invariants, validated independently of production CheckResult:
    if resolution == "UNRESOLVED" and status is not None:
        raise ValidationSchemaError(
            "unresolved-with-status", f"{where}: UNRESOLVED must not carry expectedStatus"
        )
    if resolution == "RESOLVED" and status is None:
        raise ValidationSchemaError(
            "resolved-without-status", f"{where}: RESOLVED requires one expectedStatus"
        )

    include = data.get("includeInMetrics", True)
    if not isinstance(include, bool):
        raise ValidationSchemaError("invalid-entry", f"{where}: includeInMetrics must be boolean")
    exclusion_reason = _optional_str(data, "exclusionReason", where=where)
    if not include and not exclusion_reason:
        raise ValidationSchemaError(
            "exclusion-without-reason",
            f"{where}: includeInMetrics=false requires a non-empty exclusionReason",
        )
    notes = _optional_str(data, "notes", where=where)
    return ItemLabel(
        item_id=item_id,
        expected_resolution=resolution,
        expected_status=status,
        expected_comparison=comparison,
        expected_strike=strike,
        expected_coverage=coverage,
        include_in_metrics=include,
        exclusion_reason=exclusion_reason,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Per-document label file
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DocumentLabels:
    """Independently labelled ground truth for one document."""

    document_id: str
    document_file: str
    labelled_by: str
    sanitization_state: str
    notes: str
    labels: tuple[ItemLabel, ...]


def parse_document_labels(data: Any, *, source: str = "<memory>") -> DocumentLabels:
    """Parse and validate one labels file (schemaVersion 1)."""
    where = f"labels[{source}]"
    if not isinstance(data, dict):
        raise ValidationSchemaError("invalid-entry", f"{where}: top level must be an object")
    _require_schema_version(data, where=where)
    document_id = _require_str(data, "documentId", where=where)
    document_file = _require_str(data, "documentFile", where=where)
    labelled_by = _require_str(data, "labelledBy", where=where)
    sanitization = _require_enum(data, "sanitizationState", SANITIZATION_STATES, where=where)
    notes = _optional_str(data, "notes", where=where)

    raw_labels = data.get("labels")
    if not isinstance(raw_labels, list):
        raise ValidationSchemaError("invalid-entry", f"{where}: labels must be a list")
    labels: list[ItemLabel] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw_labels):
        label = parse_item_label(entry, where=f"{where}.labels[{index}]")
        if label.item_id in seen:
            raise ValidationSchemaError(
                "duplicate-item",
                f"{where}: duplicate itemId {label.item_id!r} for document {document_id!r}",
            )
        seen.add(label.item_id)
        labels.append(label)
    return DocumentLabels(
        document_id=document_id,
        document_file=document_file,
        labelled_by=labelled_by,
        sanitization_state=sanitization,
        notes=notes,
        labels=tuple(labels),
    )


def load_document_labels(path: Path) -> DocumentLabels:
    """Read and validate one labels JSON file (UTF-8)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationSchemaError("invalid-json", f"{path}: {exc}") from exc
    return parse_document_labels(data, source=str(path))


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DocumentEntry:
    """One document referenced by the validation manifest."""

    document_id: str
    document_file: str  # path relative to the manifest file
    labels_file: str  # path relative to the manifest file
    notes: str


@dataclass(frozen=True)
class ValidationManifest:
    """Top-level Task 6 validation manifest (schemaVersion 1)."""

    baseline_file: str  # path relative to the manifest file (production baseline.json)
    documents: tuple[DocumentEntry, ...]
    notes: str


def _require_schema_version(data: dict[str, Any], *, where: str) -> None:
    version = data.get("schemaVersion")
    if not isinstance(version, int) or isinstance(version, bool):
        raise ValidationSchemaError(
            "invalid-schema-version", f"{where}: schemaVersion must be an integer"
        )
    if version != SCHEMA_VERSION:
        raise ValidationSchemaError(
            "unsupported-schema-version",
            f"{where}: unsupported schemaVersion {version} (expected {SCHEMA_VERSION})",
        )


def parse_manifest(data: Any, *, source: str = "<memory>") -> ValidationManifest:
    """Parse and validate one manifest object."""
    where = f"manifest[{source}]"
    if not isinstance(data, dict):
        raise ValidationSchemaError("invalid-entry", f"{where}: top level must be an object")
    _require_schema_version(data, where=where)
    baseline_file = _require_str(data, "baselineFile", where=where)
    notes = _optional_str(data, "notes", where=where)

    raw_docs = data.get("documents")
    if not isinstance(raw_docs, list) or not raw_docs:
        raise ValidationSchemaError("invalid-entry", f"{where}: documents must be a non-empty list")
    entries: list[DocumentEntry] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(raw_docs):
        entry_where = f"{where}.documents[{index}]"
        if not isinstance(entry, dict):
            raise ValidationSchemaError("invalid-entry", f"{entry_where}: must be an object")
        document_id = _require_str(entry, "documentId", where=entry_where)
        if document_id in seen_ids:
            raise ValidationSchemaError(
                "duplicate-document", f"{where}: duplicate documentId {document_id!r}"
            )
        seen_ids.add(document_id)
        entries.append(
            DocumentEntry(
                document_id=document_id,
                document_file=_require_str(entry, "documentFile", where=entry_where),
                labels_file=_require_str(entry, "labelsFile", where=entry_where),
                notes=_optional_str(entry, "notes", where=entry_where),
            )
        )
    return ValidationManifest(baseline_file=baseline_file, documents=tuple(entries), notes=notes)


def load_manifest(path: Path) -> ValidationManifest:
    """Read and validate a manifest JSON file, then cross-check its labels.

    Cross-checks performed here (require both files together):
      - every referenced labels file parses under the label contract;
      - documentId agreement between manifest entry and labels file;
      - global (document_id, item_id) uniqueness.
    """
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationSchemaError("invalid-json", f"{path}: {exc}") from exc
    manifest = parse_manifest(data, source=str(path))
    base = path.parent
    seen_pairs: set[tuple[str, str]] = set()
    for entry in manifest.documents:
        labels = load_document_labels(base / entry.labels_file)
        if labels.document_id != entry.document_id:
            raise ValidationSchemaError(
                "document-id-mismatch",
                f"manifest document {entry.document_id!r} disagrees with labels "
                f"documentId {labels.document_id!r}",
            )
        for label in labels.labels:
            pair = (entry.document_id, label.item_id)
            if pair in seen_pairs:
                raise ValidationSchemaError(
                    "duplicate-label",
                    f"duplicate (documentId, itemId) pair: {pair[0]} / {pair[1]}",
                )
            seen_pairs.add(pair)
    return manifest
