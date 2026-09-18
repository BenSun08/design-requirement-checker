"""S2 spike evidence: source locations, coverage and normalization mapping.

Expected block lists, locations, coverage reasons and span mappings are
independent labels derived by hand from the fixture definitions (see
fixture_factory.py) and the documented merged-cell convention:
a gridSpan/vMerge master cell is extracted once at its master grid position;
vMerge continuation cells are skipped, and non-empty continuation content
raises an explicit LIMITED reason.
"""

from pathlib import Path

import fixture_factory as fixtures
import pytest
from docx import Document as DocxDocument
from docx_probe import normalize, probe_docx


@pytest.fixture(scope="session")
def normal(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return fixtures.build_normal(tmp_path_factory.mktemp("s2-normal") / "normal.docx")


@pytest.fixture(scope="session")
def table(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return fixtures.build_table(tmp_path_factory.mktemp("s2-table") / "table.docx")


@pytest.fixture(scope="session")
def nested_merged(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return fixtures.build_nested_merged(tmp_path_factory.mktemp("s2-merged") / "nested-merged.docx")


@pytest.fixture(scope="session")
def excluded(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return fixtures.build_excluded_parts(
        tmp_path_factory.mktemp("s2-excluded") / "excluded-parts.docx"
    )


def test_body_block_locations(normal: Path) -> None:
    blocks = probe_docx(normal).blocks
    assert [(b.block_id, b.part, b.paragraph_index, b.table_path) for b in blocks] == [
        ("body:p0", "body", 0, ()),
        ("body:p1", "body", 1, ()),
        ("body:p2", "body", 2, ()),
        ("body:p3", "body", 3, ()),
        ("body:p4", "body", 4, ()),
    ]


def test_table_and_cell_paragraph_locations(table: Path) -> None:
    blocks = probe_docx(table).blocks
    assert [(b.block_id, b.part, b.paragraph_index, b.table_path, b.raw_text) for b in blocks] == [
        ("body:p0", "body", 0, (), "intro"),
        ("t0r0c0:table-cell:p0", "table-cell", 0, ((0, 0, 0),), "r0c0"),
        ("t0r0c1:table-cell:p0", "table-cell", 0, ((0, 0, 1),), "r0c1"),
        ("t0r1c0:table-cell:p0", "table-cell", 0, ((0, 1, 0),), "r1c0"),
        ("t0r1c1:table-cell:p0", "table-cell", 0, ((0, 1, 1),), "cell para A"),
        ("t0r1c1:table-cell:p1", "table-cell", 1, ((0, 1, 1),), "cell para B"),
        ("body:p1", "body", 1, (), "outro"),
    ]
    # A cell paragraph is a normal block with runs and code-point offsets.
    cell_run = blocks[1].runs[0]
    assert (cell_run.text, cell_run.start, cell_run.end, cell_run.strike) == ("r0c0", 0, 4, False)


def test_cell_paragraphs_are_never_joined(table: Path) -> None:
    blocks = probe_docx(table).blocks
    texts = [b.raw_text for b in blocks]
    assert "cell para A" in texts and "cell para B" in texts
    assert all("cell para Acell para B" != b.raw_text for b in blocks)


def test_merged_cells_extracted_once_at_master(nested_merged: Path) -> None:
    blocks = probe_docx(nested_merged).blocks
    texts = [b.raw_text for b in blocks]
    # gridSpan master and vMerge master each appear exactly once ...
    assert texts.count("H-MERGE") == 1
    assert texts.count("V-MERGE") == 1
    # ... and every block is located at its master grid position.
    assert [(b.block_id, b.paragraph_index, b.table_path, b.raw_text) for b in blocks] == [
        ("t0r0c0:table-cell:p0", 0, ((0, 0, 0),), "H-MERGE"),
        ("t0r0c2:table-cell:p0", 0, ((0, 0, 2),), "r0c2"),
        ("t0r1c0:table-cell:p0", 0, ((0, 1, 0),), "r1c0"),
        ("t0r1c1:table-cell:p0", 0, ((0, 1, 1),), "r1c1"),
        ("t0r1c2:table-cell:p0", 0, ((0, 1, 2),), "V-MERGE"),
        ("t0r2c0:table-cell:p0", 0, ((0, 2, 0),), "r2c0"),
        ("t0r2c1:table-cell:p0", 0, ((0, 2, 1),), "outer-para"),
        # Nested table inside cell (2,1): ancestor path is explicit, and the
        # cell's paragraph index continues after the nested table content.
        ("t0r2c1>t0r0c0:table-cell:p0", 0, ((0, 2, 1), (0, 0, 0)), "NESTED-CELL"),
        ("t0r2c1:table-cell:p1", 1, ((0, 2, 1),), ""),
    ]


def test_naive_cell_api_duplicates_merged_cells(nested_merged: Path) -> None:
    # Observed python-docx hazard that motivates the w:tc-level traversal:
    # Table.rows[i].cells repeats merged cells at every grid position they
    # cover, so naive iteration would extract "H-MERGE"/"V-MERGE" twice.
    table = DocxDocument(str(nested_merged)).tables[0]
    naive = [cell.text for row in table.rows for cell in row.cells]
    assert naive.count("H-MERGE") >= 2
    assert naive.count("V-MERGE") >= 2


def test_hidden_vmerge_continuation_reports_limited(nested_merged: Path) -> None:
    probed = probe_docx(nested_merged)
    # "HIDDEN-CONT" lives in a vMerge continuation cell that Word does not
    # display: it is excluded from blocks but must not disappear silently.
    assert all("HIDDEN-CONT" not in b.raw_text for b in probed.blocks)
    assert probed.coverage == "LIMITED"
    assert probed.coverage_reasons == ("merged-cell-continuation-content-excluded",)


def test_excluded_structures_report_limited_coverage(excluded: Path) -> None:
    probed = probe_docx(excluded)
    assert [(b.block_id, b.raw_text) for b in probed.blocks] == [
        ("body:p0", "visible body"),
        ("body:p1", "host "),
    ]
    # The textbox host run contributes an empty run, not silent text loss.
    assert [(r.text, r.start, r.end) for r in probed.blocks[1].runs] == [
        ("host ", 0, 5),
        ("", 5, 5),
    ]
    assert probed.coverage == "LIMITED"
    assert probed.coverage_reasons == (
        "content-control-content-excluded",
        "footer-content-not-checked",
        "header-content-not-checked",
        "textbox-content-excluded",
    )


def test_excluded_content_is_absent_from_blocks(excluded: Path) -> None:
    blocks = probe_docx(excluded).blocks
    joined = "\n".join(b.raw_text for b in blocks)
    for hidden in ("HEADER TEXT", "FOOTER TEXT", "SDT PARA", "TEXTBOX TEXT"):
        assert hidden not in joined


def test_coverage_is_complete_when_nothing_is_excluded(normal: Path, table: Path) -> None:
    for path in (normal, table):
        probed = probe_docx(path)
        assert probed.coverage == "COMPLETE"
        assert probed.coverage_reasons == ()


def test_run_reconstruction_invariants(
    normal: Path, table: Path, nested_merged: Path, excluded: Path
) -> None:
    for path in (normal, table, nested_merged, excluded):
        for block in probe_docx(path).blocks:
            assert block.raw_text == "".join(r.text for r in block.runs)
            offset = 0
            for run in block.runs:
                assert run.start == offset
                assert run.end == run.start + len(run.text)
                offset = run.end
            assert offset == len(block.raw_text)


def test_conservative_normalization_maps_back_to_raw_spans(normal: Path) -> None:
    block = probe_docx(normal).blocks[3]
    assert block.raw_text == "A  B\tC"
    normalized = normalize(block.raw_text)
    # Whitespace runs collapse to one space; nothing else is transformed.
    assert normalized.text == "A B C"
    # A phrase located in normalized text resolves to exact raw offsets.
    start = normalized.text.find("B C")
    assert start == 2
    raw_start, raw_end = normalized.map_span(start, start + len("B C"))
    assert (raw_start, raw_end) == (3, 6)
    assert block.raw_text[raw_start:raw_end] == "B\tC"
    # Spans that include collapsed whitespace cover the whole whitespace run.
    assert normalized.map_span(0, 3) == (0, 4)
    assert block.raw_text[0:4] == "A  B"
    # A single character maps to its exact raw position.
    assert normalized.map_span(4, 5) == (5, 6)
    assert block.raw_text[5:6] == "C"


def test_locations_stable_across_reprobes(
    normal: Path, table: Path, nested_merged: Path, excluded: Path
) -> None:
    for path in (normal, table, nested_merged, excluded):
        assert probe_docx(path) == probe_docx(path), f"unstable probe output for {path.name}"


def test_block_ids_are_unique(
    normal: Path, table: Path, nested_merged: Path, excluded: Path
) -> None:
    for path in (normal, table, nested_merged, excluded):
        blocks = probe_docx(path).blocks
        assert len({b.block_id for b in blocks}) == len(blocks)
