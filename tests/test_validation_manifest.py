"""Task 6 T6.1 — validation contract / manifest tests.

These cover the ground-truth schema itself: valid parsing, strict rejection of
malformed labels, Unicode handling and stable round-trip parsing. They use
plain dicts and temp files only — no production CheckResult is involved,
because ground truth is conceptually independent of checker output.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from validation.schema import (
    ValidationManifest,
    ValidationSchemaError,
    load_document_labels,
    load_manifest,
    parse_document_labels,
    parse_manifest,
)

VALID_LABELS: dict[str, Any] = {
    "schemaVersion": 1,
    "documentId": "hist-001",
    "documentFile": "corpus-local/hist-001.docx",
    "labelledBy": "independent-human",
    "sanitizationState": "sanitized",
    "notes": "示例文档",
    "labels": [
        {
            "itemId": "door-delay",
            "expectedResolution": "RESOLVED",
            "expectedStatus": "CONFIGURED",
            "expectedComparison": "DIFFERENT",
            "expectedStrike": "NONE",
            "expectedCoverage": "COMPLETE",
            "includeInMetrics": True,
            "notes": "2门控制延时功能存在，要求值为 3s，基线期望 2s",
        },
        {
            "itemId": "absent-func",
            "expectedResolution": "RESOLVED",
            "expectedStatus": "MISSING",
            "includeInMetrics": True,
        },
        {
            "itemId": "struck-func",
            "expectedResolution": "RESOLVED",
            "expectedStatus": "STRUCK_OUT",
            "expectedStrike": "FULL",
            "includeInMetrics": True,
        },
        {
            "itemId": "ambiguous-func",
            "expectedResolution": "UNRESOLVED",
            "includeInMetrics": False,
            "exclusionReason": "active and struck evidence coexist; not safely labelable",
        },
    ],
}


def _labels(**overrides: Any) -> dict[str, Any]:
    data = copy.deepcopy(VALID_LABELS)
    data.update(overrides)
    return data


def _first_label(**overrides: Any) -> dict[str, Any]:
    data = copy.deepcopy(VALID_LABELS)
    data["labels"][0].update(overrides)
    return data


def test_valid_manifest_parses() -> None:
    parsed = parse_document_labels(VALID_LABELS)
    assert parsed.document_id == "hist-001"
    assert parsed.labelled_by == "independent-human"
    assert parsed.sanitization_state == "sanitized"
    assert len(parsed.labels) == 4
    configured = parsed.labels[0]
    assert configured.expected_status == "CONFIGURED"
    assert configured.expected_comparison == "DIFFERENT"
    assert configured.expected_strike == "NONE"
    assert configured.expected_coverage == "COMPLETE"
    unresolved = parsed.labels[3]
    assert unresolved.expected_resolution == "UNRESOLVED"
    assert unresolved.expected_status is None
    assert unresolved.include_in_metrics is False
    assert unresolved.exclusion_reason


def test_unicode_notes_preserved() -> None:
    parsed = parse_document_labels(VALID_LABELS)
    assert parsed.notes == "示例文档"
    assert parsed.labels[0].notes == "2门控制延时功能存在，要求值为 3s，基线期望 2s"


def test_optional_fields_default() -> None:
    parsed = parse_document_labels(VALID_LABELS)
    minimal = parsed.labels[1]
    assert minimal.expected_comparison is None
    assert minimal.expected_strike is None
    assert minimal.expected_coverage is None
    assert minimal.notes == ""
    assert minimal.include_in_metrics is True


@pytest.mark.parametrize("status", ["CONFIGURED", "MISSING", "STRUCK_OUT"])
def test_resolved_requires_status(status: str) -> None:
    data = _first_label(expectedResolution="RESOLVED", expectedStatus=status)
    parsed = parse_document_labels(data)
    assert parsed.labels[0].expected_status == status


def test_resolved_without_status_rejected() -> None:
    data = _first_label(expectedResolution="RESOLVED")
    data["labels"][0].pop("expectedStatus")
    with pytest.raises(ValidationSchemaError, match="RESOLVED requires") as excinfo:
        parse_document_labels(data)
    assert excinfo.value.code == "resolved-without-status"


def test_unresolved_with_status_rejected() -> None:
    data = _first_label(expectedResolution="UNRESOLVED", expectedStatus="CONFIGURED")
    with pytest.raises(ValidationSchemaError, match="must not carry") as excinfo:
        parse_document_labels(data)
    assert excinfo.value.code == "unresolved-with-status"


def test_unresolved_without_status_accepted() -> None:
    data = _first_label(expectedResolution="UNRESOLVED")
    data["labels"][0].pop("expectedStatus")
    parsed = parse_document_labels(data)
    assert parsed.labels[0].expected_status is None


def test_unknown_status_token_rejected() -> None:
    data = _first_label(expectedStatus="PARTIAL")
    with pytest.raises(ValidationSchemaError) as excinfo:
        parse_document_labels(data)
    assert excinfo.value.code == "unknown-token"


def test_unknown_comparison_token_rejected() -> None:
    data = _first_label(expectedComparison="SIMILAR")
    with pytest.raises(ValidationSchemaError) as excinfo:
        parse_document_labels(data)
    assert excinfo.value.code == "unknown-token"


def test_unknown_resolution_token_rejected() -> None:
    data = _first_label(expectedResolution="PENDING")
    with pytest.raises(ValidationSchemaError) as excinfo:
        parse_document_labels(data)
    assert excinfo.value.code == "unknown-token"


def test_presentation_label_never_accepted_as_token() -> None:
    data = _first_label(expectedStatus="已配置")
    with pytest.raises(ValidationSchemaError) as excinfo:
        parse_document_labels(data)
    assert excinfo.value.code == "unknown-token"


def test_missing_item_identity_rejected() -> None:
    data = _labels()
    data["labels"][0].pop("itemId")
    with pytest.raises(ValidationSchemaError) as excinfo:
        parse_document_labels(data)
    assert excinfo.value.code == "missing-or-invalid-field"


def test_missing_document_identity_rejected() -> None:
    data = _labels()
    data.pop("documentId")
    with pytest.raises(ValidationSchemaError) as excinfo:
        parse_document_labels(data)
    assert excinfo.value.code == "missing-or-invalid-field"


def test_missing_labelled_by_rejected() -> None:
    data = _labels()
    data.pop("labelledBy")
    with pytest.raises(ValidationSchemaError):
        parse_document_labels(data)


def test_duplicate_item_id_rejected() -> None:
    data = _labels()
    data["labels"].append(copy.deepcopy(data["labels"][0]))
    with pytest.raises(ValidationSchemaError, match="duplicate itemId") as excinfo:
        parse_document_labels(data)
    assert excinfo.value.code == "duplicate-item"


def test_exclusion_without_reason_rejected() -> None:
    data = _first_label(includeInMetrics=False)
    with pytest.raises(ValidationSchemaError, match="exclusionReason") as excinfo:
        parse_document_labels(data)
    assert excinfo.value.code == "exclusion-without-reason"


def test_inclusion_does_not_require_reason() -> None:
    parsed = parse_document_labels(VALID_LABELS)
    assert parsed.labels[0].exclusion_reason == ""


def test_bad_sanitization_state_rejected() -> None:
    data = _labels(sanitizationState="confidential")
    with pytest.raises(ValidationSchemaError) as excinfo:
        parse_document_labels(data)
    assert excinfo.value.code == "unknown-token"


def test_unsupported_schema_version_rejected() -> None:
    data = _labels(schemaVersion=2)
    with pytest.raises(ValidationSchemaError) as excinfo:
        parse_document_labels(data)
    assert excinfo.value.code == "unsupported-schema-version"


def test_missing_schema_version_rejected() -> None:
    data = _labels()
    data.pop("schemaVersion")
    with pytest.raises(ValidationSchemaError) as excinfo:
        parse_document_labels(data)
    assert excinfo.value.code == "invalid-schema-version"


def test_bool_schema_version_rejected() -> None:
    data = _labels(schemaVersion=True)
    with pytest.raises(ValidationSchemaError) as excinfo:
        parse_document_labels(data)
    assert excinfo.value.code == "invalid-schema-version"


def test_labels_must_be_list() -> None:
    data = _labels(labels="not-a-list")
    with pytest.raises(ValidationSchemaError):
        parse_document_labels(data)


def test_load_document_labels_from_file(tmp_path: Path) -> None:
    path = tmp_path / "hist-001.json"
    path.write_text(json.dumps(VALID_LABELS, ensure_ascii=False), encoding="utf-8")
    parsed = load_document_labels(path)
    assert parsed.document_id == "hist-001"


def test_load_document_labels_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ValidationSchemaError) as excinfo:
        load_document_labels(path)
    assert excinfo.value.code == "invalid-json"


# ---------------------------------------------------------------------------
# Manifest level
# ---------------------------------------------------------------------------


def _write_corpus(tmp_path: Path) -> Path:
    """Lay out a minimal valid corpus: manifest + one labels file."""
    labels_dir = tmp_path / "labels"
    labels_dir.mkdir()
    (labels_dir / "hist-001.json").write_text(
        json.dumps(VALID_LABELS, ensure_ascii=False), encoding="utf-8"
    )
    manifest = {
        "schemaVersion": 1,
        "baselineFile": "corpus-local/baseline.json",
        "notes": "测试用清单",
        "documents": [
            {
                "documentId": "hist-001",
                "documentFile": "corpus-local/hist-001.docx",
                "labelsFile": "labels/hist-001.json",
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def test_valid_manifest_loads(tmp_path: Path) -> None:
    manifest = load_manifest(_write_corpus(tmp_path))
    assert isinstance(manifest, ValidationManifest)
    assert manifest.baseline_file == "corpus-local/baseline.json"
    assert len(manifest.documents) == 1
    assert manifest.documents[0].document_id == "hist-001"


def test_manifest_duplicate_document_rejected(tmp_path: Path) -> None:
    path = _write_corpus(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["documents"].append(copy.deepcopy(data["documents"][0]))
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValidationSchemaError, match="duplicate documentId") as excinfo:
        load_manifest(path)
    assert excinfo.value.code == "duplicate-document"


def test_manifest_duplicate_pair_across_documents(tmp_path: Path) -> None:
    path = _write_corpus(tmp_path)
    labels_dir = tmp_path / "labels"
    second = copy.deepcopy(VALID_LABELS)
    second["documentId"] = "hist-002"
    (labels_dir / "hist-002.json").write_text(json.dumps(second), encoding="utf-8")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["documents"].append(
        {
            "documentId": "hist-002",
            "documentFile": "corpus-local/hist-002.docx",
            "labelsFile": "labels/hist-002.json",
        }
    )
    path.write_text(json.dumps(data), encoding="utf-8")
    # Same itemId in two different documents is allowed (pairs differ).
    manifest = load_manifest(path)
    assert len(manifest.documents) == 2


def test_manifest_document_id_mismatch_rejected(tmp_path: Path) -> None:
    path = _write_corpus(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["documents"][0]["documentId"] = "hist-999"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValidationSchemaError, match="disagrees") as excinfo:
        load_manifest(path)
    assert excinfo.value.code == "document-id-mismatch"


def test_manifest_empty_documents_rejected(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"schemaVersion": 1, "baselineFile": "b.json", "documents": []}),
        encoding="utf-8",
    )
    with pytest.raises(ValidationSchemaError):
        load_manifest(manifest_path)


def test_manifest_missing_labels_file_rejected(tmp_path: Path) -> None:
    path = _write_corpus(tmp_path)
    (tmp_path / "labels" / "hist-001.json").unlink()
    with pytest.raises((ValidationSchemaError, OSError, json.JSONDecodeError)):
        load_manifest(path)


def test_parse_manifest_rejects_missing_baseline_reference() -> None:
    with pytest.raises(ValidationSchemaError) as excinfo:
        parse_manifest(
            {"schemaVersion": 1, "documents": [{"documentId": "hist-001"}]},
            source="inline",
        )
    assert excinfo.value.code == "missing-or-invalid-field"


def test_committed_example_files_are_valid() -> None:
    """The shipped example manifest/label files must satisfy the contract."""
    repo_root = Path(__file__).resolve().parents[1]
    labels = load_document_labels(repo_root / "validation" / "labels" / "example.json")
    assert labels.document_id == "hist-001"
    manifest = load_manifest(repo_root / "validation" / "manifest.example.json")
    assert manifest.documents[0].document_id == labels.document_id


def test_stable_parsing_is_deterministic() -> None:
    first = parse_document_labels(VALID_LABELS)
    second = parse_document_labels(VALID_LABELS)
    assert first == second
