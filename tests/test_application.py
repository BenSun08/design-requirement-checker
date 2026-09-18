"""Application-layer import coordination tests (Task 2 vertical slice).

Expected behavior: import returns a domain Document snapshot or an explicit
ImportFailure — never an exception for bad input, never a silently empty
document — and never modifies the original file.
"""

import hashlib

import fixture_factory as fixtures

from design_requirement_checker.application import ImportFailure, import_document
from design_requirement_checker.domain import Coverage, Document


def _sha256(path) -> str:  # type: ignore[no-untyped-def]
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestImportDocument:
    def test_success_returns_domain_document(self, tmp_path) -> None:
        path = fixtures.build_normal(tmp_path / "normal.docx")
        outcome = import_document(path)
        assert isinstance(outcome, Document)
        assert outcome.filename == "normal.docx"
        assert outcome.coverage is Coverage.COMPLETE
        assert len(outcome.blocks) == 5

    def test_limited_document_carries_warnings(self, tmp_path) -> None:
        path = fixtures.build_excluded_parts(tmp_path / "excluded.docx")
        outcome = import_document(path)
        assert isinstance(outcome, Document)
        assert outcome.coverage is Coverage.LIMITED
        assert outcome.warnings

    def test_malformed_file_returns_explicit_failure(self, tmp_path) -> None:
        path = fixtures.build_malformed(tmp_path / "malformed.docx")
        outcome = import_document(path)
        assert isinstance(outcome, ImportFailure)
        assert outcome.filename == "malformed.docx"
        assert outcome.reason == "unreadable-file"
        assert outcome.detail

    def test_missing_file_returns_access_failure(self, tmp_path) -> None:
        outcome = import_document(tmp_path / "does-not-exist.docx")
        assert isinstance(outcome, ImportFailure)
        assert outcome.reason == "file-access-error"
        assert outcome.filename == "does-not-exist.docx"

    def test_string_path_is_accepted(self, tmp_path) -> None:
        path = fixtures.build_normal(tmp_path / "normal.docx")
        outcome = import_document(str(path))
        assert isinstance(outcome, Document)

    def test_import_does_not_modify_the_original_file(self, tmp_path) -> None:
        path = fixtures.build_strike_matrix(tmp_path / "strike.docx")
        before = _sha256(path)
        import_document(path)
        assert _sha256(path) == before

    def test_repeated_import_yields_the_same_identity(self, tmp_path) -> None:
        path = fixtures.build_table(tmp_path / "table.docx")
        first = import_document(path)
        second = import_document(path)
        assert isinstance(first, Document)
        assert isinstance(second, Document)
        assert first.document_id == second.document_id
        assert first.content_fingerprint == second.content_fingerprint
