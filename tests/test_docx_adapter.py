"""DOCX adapter extraction tests (Task 2 vertical slice).

Expected values are hand-written labels from fixture_factory.py and the
S1/S2-validated extraction rules (docs/technical-spikes.md): effective-strike
chain resolution preserving unknowns, stable block locations, merged cells
extracted once, explicit LIMITED warnings, and immutable input bytes.
"""

import hashlib

import fixture_factory as fixtures
import pytest

from design_requirement_checker.docx_adapter import DocxReadError, read_document
from design_requirement_checker.domain import (
    BlockType,
    Coverage,
    Document,
    TableCellCoordinates,
)


def _sha256(path) -> str:  # type: ignore[no-untyped-def]
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def normal(tmp_path_factory: pytest.TempPathFactory):
    return fixtures.build_normal(tmp_path_factory.mktemp("a-normal") / "normal.docx")


@pytest.fixture(scope="module")
def table(tmp_path_factory: pytest.TempPathFactory):
    return fixtures.build_table(tmp_path_factory.mktemp("a-table") / "table.docx")


@pytest.fixture(scope="module")
def nested_merged(tmp_path_factory: pytest.TempPathFactory):
    return fixtures.build_nested_merged(tmp_path_factory.mktemp("a-nested") / "nested.docx")


@pytest.fixture(scope="module")
def strike_matrix(tmp_path_factory: pytest.TempPathFactory):
    return fixtures.build_strike_matrix(tmp_path_factory.mktemp("a-strike") / "strike.docx")


@pytest.fixture(scope="module")
def docdefaults(tmp_path_factory: pytest.TempPathFactory):
    return fixtures.build_docdefaults_strike(
        tmp_path_factory.mktemp("a-docdefaults") / "docdefaults.docx"
    )


@pytest.fixture(scope="module")
def tracked(tmp_path_factory: pytest.TempPathFactory):
    return fixtures.build_tracked_revisions(tmp_path_factory.mktemp("a-tracked") / "tracked.docx")


@pytest.fixture(scope="module")
def excluded(tmp_path_factory: pytest.TempPathFactory):
    return fixtures.build_excluded_parts(tmp_path_factory.mktemp("a-excluded") / "excluded.docx")


@pytest.fixture(scope="module")
def empty(tmp_path_factory: pytest.TempPathFactory):
    return fixtures.build_empty(tmp_path_factory.mktemp("a-empty") / "empty.docx")


class TestBodyExtraction:
    def test_paragraph_texts_and_split_run_offsets(self, normal) -> None:
        document = read_document(normal)
        assert isinstance(document, Document)
        assert [block.text for block in document.blocks] == [
            "plain body paragraph one",
            "Hello bold world",
            "AlphaBeta",
            "A  B\tC",
            "",
        ]
        split = document.blocks[1].runs
        assert [(run.text, run.start_offset, run.end_offset) for run in split] == [
            ("Hello ", 0, 6),
            ("bold", 6, 10),
            (" world", 10, 16),
        ]
        adjacent = document.blocks[2].runs
        assert [(run.text, run.start_offset, run.end_offset) for run in adjacent] == [
            ("Alpha", 0, 5),
            ("Beta", 5, 9),
        ]

    def test_body_block_types_and_locations(self, normal) -> None:
        document = read_document(normal)
        first = document.blocks[0]
        assert first.block_type is BlockType.PARAGRAPH
        assert first.block_id == "body:p0"
        assert first.location.part == "body"
        assert first.location.paragraph_index == 0
        assert first.location.cell is None
        assert first.location.ancestor_path == ()

    def test_undecorated_runs_resolve_false_not_unknown(self, normal) -> None:
        document = read_document(normal)
        for block in document.blocks:
            for run in block.runs:
                assert run.effective_strike is False
                assert run.strike_reason == ""
                assert run.strike_origin == "default-off"

    def test_coverage_complete_for_ordinary_document(self, normal) -> None:
        document = read_document(normal)
        assert document.coverage is Coverage.COMPLETE
        assert document.warnings == ()


class TestStrikeResolution:
    def test_direct_and_partial_strike(self, strike_matrix) -> None:
        document = read_document(strike_matrix)
        states = [
            [(run.effective_strike, run.strike_origin, run.strike_reason) for run in block.runs]
            for block in document.blocks
        ]
        assert states[0] == [(True, "direct", "")]
        assert states[1] == [(False, "direct", "")]
        assert states[2] == [
            (False, "default-off", ""),
            (True, "direct", ""),
            (False, "default-off", ""),
        ]

    def test_style_inheritance_and_override(self, strike_matrix) -> None:
        document = read_document(strike_matrix)
        inherited = document.blocks[3].runs[0]
        assert (inherited.effective_strike, inherited.strike_origin) == (True, "paragraph-style")
        override = document.blocks[4].runs[0]
        assert (override.effective_strike, override.strike_origin) == (False, "direct")

    def test_double_strike_stays_unknown_with_reason(self, strike_matrix) -> None:
        document = read_document(strike_matrix)
        run = document.blocks[5].runs[0]
        assert run.effective_strike is None
        assert run.strike_reason == "double-strike"
        assert run.double_strike is True

    def test_invalid_strike_value_stays_unknown(self, strike_matrix) -> None:
        document = read_document(strike_matrix)
        run = document.blocks[6].runs[0]
        assert run.effective_strike is None
        assert run.strike_origin == "direct"
        assert run.strike_reason == "invalid-strike-value"

    def test_orphan_style_reference_stays_unknown(self, strike_matrix) -> None:
        document = read_document(strike_matrix)
        run = document.blocks[7].runs[0]
        assert run.effective_strike is None
        assert run.strike_origin == "character-style"
        assert run.strike_reason == "orphan-style-reference"

    def test_docdefaults_resolution_and_override(self, docdefaults) -> None:
        document = read_document(docdefaults)
        plain = document.blocks[0].runs[0]
        assert (plain.effective_strike, plain.strike_origin) == (True, "doc-defaults")
        off = document.blocks[1].runs[0]
        assert (off.effective_strike, off.strike_origin) == (False, "direct")


class TestTablesAndLocations:
    def test_table_cell_blocks_and_local_paragraph_indices(self, table) -> None:
        document = read_document(table)
        assert [block.block_id for block in document.blocks] == [
            "body:p0",
            "t0r0c0:table-cell:p0",
            "t0r0c1:table-cell:p0",
            "t0r1c0:table-cell:p0",
            "t0r1c1:table-cell:p0",
            "t0r1c1:table-cell:p1",
            "body:p1",
        ]
        assert [block.text for block in document.blocks] == [
            "intro",
            "r0c0",
            "r0c1",
            "r1c0",
            "cell para A",
            "cell para B",
            "outro",
        ]
        second_cell_para = document.blocks[5]
        assert second_cell_para.block_type is BlockType.TABLE_CELL_PARAGRAPH
        assert second_cell_para.location.paragraph_index == 1
        assert second_cell_para.location.cell == TableCellCoordinates(0, 1, 1)
        assert second_cell_para.location.ancestor_path == ()
        assert document.coverage is Coverage.COMPLETE

    def test_merged_cells_extracted_once_at_master_position(self, nested_merged) -> None:
        document = read_document(nested_merged)
        ids = [block.block_id for block in document.blocks]
        # The gridSpan master occupies grid columns 0-1 and is extracted once
        # at column 0; no separate block exists for the covered column.
        assert "t0r0c0:table-cell:p0" in ids
        assert "t0r0c1:table-cell:p0" not in ids
        h_merge = document.blocks[ids.index("t0r0c0:table-cell:p0")]
        assert h_merge.text == "H-MERGE"
        assert h_merge.location.cell == TableCellCoordinates(0, 0, 0)
        # The vMerge master is extracted at its own position; the continuation
        # row below it produces no block.
        assert "t0r1c2:table-cell:p0" in ids
        assert "t0r2c2:table-cell:p0" not in ids

    def test_nested_table_block_carries_ancestor_path(self, nested_merged) -> None:
        document = read_document(nested_merged)
        ids = [block.block_id for block in document.blocks]
        nested = document.blocks[ids.index("t0r2c1>t0r0c0:table-cell:p0")]
        assert nested.text == "NESTED-CELL"
        assert nested.location.cell == TableCellCoordinates(0, 0, 0)
        assert nested.location.ancestor_path == (TableCellCoordinates(0, 2, 1),)
        # python-docx appends a trailing empty paragraph after the nested table.
        trailing = document.blocks[ids.index("t0r2c1:table-cell:p1")]
        assert trailing.text == ""

    def test_hidden_vmerge_continuation_reports_limited(self, nested_merged) -> None:
        document = read_document(nested_merged)
        all_text = "\n".join(block.text for block in document.blocks)
        assert "HIDDEN-CONT" not in all_text
        assert document.coverage is Coverage.LIMITED
        assert "merged-cell-continuation-content-excluded" in document.warnings

    def test_block_count_is_stable(self, nested_merged) -> None:
        document = read_document(nested_merged)
        assert len(document.blocks) == 9


class TestCoverageHonesty:
    def test_tracked_revisions_limited_and_revision_text_excluded(self, tracked) -> None:
        document = read_document(tracked)
        assert [block.text for block in document.blocks] == ["kept ", "clean paragraph"]
        all_text = "\n".join(block.text for block in document.blocks)
        assert "INSERTED" not in all_text
        assert "REMOVED" not in all_text
        assert document.coverage is Coverage.LIMITED
        assert "tracked-revisions-unsupported" in document.warnings

    def test_excluded_structures_report_limited_and_are_absent(self, excluded) -> None:
        document = read_document(excluded)
        assert document.coverage is Coverage.LIMITED
        for reason in (
            "header-content-not-checked",
            "footer-content-not-checked",
            "content-control-content-excluded",
            "textbox-content-excluded",
        ):
            assert reason in document.warnings
        all_text = "\n".join(block.text for block in document.blocks)
        for absent in ("HEADER TEXT", "FOOTER TEXT", "SDT PARA", "TEXTBOX TEXT"):
            assert absent not in all_text
        assert document.blocks[0].text == "visible body"
        assert document.blocks[1].text == "host "

    def test_empty_document_is_complete_not_failed(self, empty) -> None:
        document = read_document(empty)
        assert document.blocks == ()
        assert document.coverage is Coverage.COMPLETE
        assert document.warnings == ()

    def test_malformed_file_fails_explicitly(self, tmp_path) -> None:
        path = fixtures.build_malformed(tmp_path / "malformed.docx")
        with pytest.raises(DocxReadError) as excinfo:
            read_document(path)
        assert str(excinfo.value)


class TestImmutabilityAndIdentity:
    def test_original_bytes_unchanged_and_fingerprint_identity(self, normal) -> None:
        before = _sha256(normal)
        document = read_document(normal)
        assert _sha256(normal) == before
        assert document.content_fingerprint == before
        assert document.document_id == f"sha256:{before}"
        assert document.filename == normal.name

    def test_locations_stable_across_repeated_reads(self, nested_merged) -> None:
        first = read_document(nested_merged)
        second = read_document(nested_merged)
        assert [block.block_id for block in first.blocks] == [
            block.block_id for block in second.blocks
        ]
        assert [block.text for block in first.blocks] == [block.text for block in second.blocks]
        assert first.document_id == second.document_id

    def test_all_readable_fixtures_satisfy_run_invariants(self, tmp_path) -> None:
        builders = (
            fixtures.build_normal,
            fixtures.build_table,
            fixtures.build_nested_merged,
            fixtures.build_strike_matrix,
            fixtures.build_docdefaults_strike,
            fixtures.build_tracked_revisions,
            fixtures.build_excluded_parts,
            fixtures.build_empty,
        )
        for index, builder in enumerate(builders):
            document = read_document(builder(tmp_path / f"f{index}.docx"))
            for block in document.blocks:
                assert block.text == "".join(run.text for run in block.runs)
                offset = 0
                for run in block.runs:
                    assert run.start_offset == offset
                    offset = run.end_offset
                assert offset == len(block.text)
