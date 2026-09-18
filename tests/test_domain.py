"""Domain value-model invariants (docs/domain-model.md).

Expected behavior is written by hand from the domain model document, not from
implementation output: half-open code-point offsets, contiguous runs, unknown
strike always carrying a reason, coverage honesty, and location coherence.
"""

import pytest

from design_requirement_checker.domain import (
    BlockType,
    Coverage,
    Document,
    DocumentBlock,
    DocumentLocation,
    TableCellCoordinates,
    TextRun,
)


def make_run(
    text: str,
    start: int,
    strike: bool | None = False,
    *,
    origin: str = "default-off",
    reason: str = "",
) -> TextRun:
    return TextRun(
        text=text,
        start_offset=start,
        end_offset=start + len(text),
        effective_strike=strike,
        strike_origin=origin,
        strike_reason=reason,
    )


def make_block(
    doc_id: str,
    block_id: str,
    part: str,
    paragraph_index: int,
    runs: tuple[TextRun, ...],
    *,
    text: str | None = None,
    cell: TableCellCoordinates | None = None,
    ancestors: tuple[TableCellCoordinates, ...] = (),
) -> DocumentBlock:
    block_type = BlockType.PARAGRAPH if part == "body" else BlockType.TABLE_CELL_PARAGRAPH
    location = DocumentLocation(
        document_id=doc_id,
        block_id=block_id,
        block_type=block_type,
        part=part,
        paragraph_index=paragraph_index,
        cell=cell,
        ancestor_path=ancestors,
    )
    return DocumentBlock(
        block_id=block_id,
        block_type=block_type,
        text="".join(run.text for run in runs) if text is None else text,
        runs=runs,
        location=location,
    )


def make_document(
    blocks: tuple[DocumentBlock, ...],
    *,
    coverage: Coverage = Coverage.COMPLETE,
    warnings: tuple[str, ...] = (),
    doc_id: str = "d1",
) -> Document:
    return Document(
        document_id=doc_id,
        filename="sample.docx",
        content_fingerprint=doc_id.removeprefix("sha256:"),
        blocks=blocks,
        coverage=coverage,
        warnings=warnings,
    )


def make_cell_block(
    doc_id: str,
    block_id: str,
    paragraph_index: int,
    runs: tuple[TextRun, ...],
    *,
    cell: TableCellCoordinates | None = TableCellCoordinates(0, 0, 0),
    ancestors: tuple[TableCellCoordinates, ...] = (),
) -> DocumentBlock:
    return make_block(
        doc_id, block_id, "table-cell", paragraph_index, runs, cell=cell, ancestors=ancestors
    )


class TestTextRun:
    def test_offsets_must_be_half_open_code_points(self) -> None:
        with pytest.raises(ValueError, match="offset"):
            TextRun(text="ab", start_offset=0, end_offset=3, effective_strike=False)

    def test_negative_start_offset_rejected(self) -> None:
        with pytest.raises(ValueError, match="offset"):
            TextRun(text="ab", start_offset=-1, end_offset=1, effective_strike=False)

    def test_unknown_strike_requires_a_reason(self) -> None:
        with pytest.raises(ValueError, match="reason"):
            TextRun(text="ab", start_offset=0, end_offset=2, effective_strike=None)

    def test_unknown_strike_with_reason_is_valid(self) -> None:
        run = TextRun(
            text="ab",
            start_offset=0,
            end_offset=2,
            effective_strike=None,
            strike_origin="direct",
            strike_reason="invalid-strike-value",
        )
        assert run.effective_strike is None
        assert run.strike_reason == "invalid-strike-value"

    def test_resolved_strike_must_not_carry_a_reason(self) -> None:
        with pytest.raises(ValueError, match="reason"):
            TextRun(
                text="ab",
                start_offset=0,
                end_offset=2,
                effective_strike=True,
                strike_origin="direct",
                strike_reason="invalid-strike-value",
            )


class TestDocumentBlock:
    def test_runs_must_be_contiguous_from_zero(self) -> None:
        runs = (make_run("ab", 0), make_run("cd", 3))
        with pytest.raises(ValueError, match="contiguous"):
            make_block("d1", "body:p0", "body", 0, runs)

    def test_text_must_equal_run_concatenation(self) -> None:
        runs = (make_run("ab", 0), make_run("cd", 2))
        with pytest.raises(ValueError, match="text"):
            make_block("d1", "body:p0", "body", 0, runs, text="abcdx")

    def test_empty_paragraph_block_is_valid(self) -> None:
        block = make_block("d1", "body:p0", "body", 0, ())
        assert block.text == ""
        assert block.runs == ()

    def test_block_must_match_its_location_identity(self) -> None:
        runs = (make_run("ab", 0),)
        location = DocumentLocation(
            document_id="d1",
            block_id="body:p9",
            block_type=BlockType.PARAGRAPH,
            part="body",
            paragraph_index=0,
        )
        with pytest.raises(ValueError, match="identity"):
            DocumentBlock(
                block_id="body:p0",
                block_type=BlockType.PARAGRAPH,
                text="ab",
                runs=runs,
                location=location,
            )


class TestDocumentLocation:
    def test_body_location_rejects_cell_coordinates(self) -> None:
        with pytest.raises(ValueError, match="body"):
            DocumentLocation(
                document_id="d1",
                block_id="body:p0",
                block_type=BlockType.PARAGRAPH,
                part="body",
                paragraph_index=0,
                cell=TableCellCoordinates(0, 0, 0),
            )

    def test_table_cell_location_requires_cell_coordinates(self) -> None:
        with pytest.raises(ValueError, match="table-cell"):
            DocumentLocation(
                document_id="d1",
                block_id="t0r0c0:table-cell:p0",
                block_type=BlockType.TABLE_CELL_PARAGRAPH,
                part="table-cell",
                paragraph_index=0,
                cell=None,
            )

    def test_part_must_agree_with_block_type(self) -> None:
        with pytest.raises(ValueError, match="part"):
            DocumentLocation(
                document_id="d1",
                block_id="body:p0",
                block_type=BlockType.TABLE_CELL_PARAGRAPH,
                part="body",
                paragraph_index=0,
            )

    def test_paragraph_index_must_be_non_negative(self) -> None:
        with pytest.raises(ValueError, match="paragraph"):
            DocumentLocation(
                document_id="d1",
                block_id="body:p0",
                block_type=BlockType.PARAGRAPH,
                part="body",
                paragraph_index=-1,
            )

    def test_cell_coordinates_must_be_non_negative(self) -> None:
        with pytest.raises(ValueError, match="index"):
            TableCellCoordinates(table_index=0, row_index=-1, column_index=0)


class TestDocument:
    def test_snapshot_holds_blocks_and_identity(self) -> None:
        blocks = (
            make_block("d1", "body:p0", "body", 0, (make_run("hello", 0),)),
            make_cell_block("d1", "t0r0c0:table-cell:p0", 0, (make_run("cell", 0),)),
        )
        document = make_document(blocks)
        assert document.document_id == "d1"
        assert document.filename == "sample.docx"
        assert document.coverage is Coverage.COMPLETE
        assert len(document.blocks) == 2
        assert document.blocks[1].location.part == "table-cell"
        assert document.blocks[1].location.cell == TableCellCoordinates(0, 0, 0)
        assert document.blocks[0].location.paragraph_index == 0

    def test_nested_cell_location_keeps_ancestor_path(self) -> None:
        outer = TableCellCoordinates(0, 2, 1)
        inner = TableCellCoordinates(0, 0, 0)
        block = make_cell_block(
            "d1",
            "t0r2c1>t0r0c0:table-cell:p0",
            0,
            (make_run("deep", 0),),
            cell=inner,
            ancestors=(outer,),
        )
        document = make_document((block,))
        location = document.blocks[0].location
        assert location.ancestor_path == (outer,)
        assert location.cell == inner

    def test_duplicate_block_ids_rejected(self) -> None:
        blocks = (
            make_block("d1", "body:p0", "body", 0, (make_run("a", 0),)),
            make_block("d1", "body:p0", "body", 1, (make_run("b", 0),)),
        )
        with pytest.raises(ValueError, match="unique"):
            make_document(blocks)

    def test_location_must_reference_the_same_document(self) -> None:
        blocks = (make_block("other", "body:p0", "body", 0, (make_run("a", 0),)),)
        with pytest.raises(ValueError, match="reference"):
            make_document(blocks, doc_id="d1")

    def test_complete_document_forbids_warnings(self) -> None:
        blocks = (make_block("d1", "body:p0", "body", 0, (make_run("a", 0),)),)
        with pytest.raises(ValueError, match="warning"):
            make_document(blocks, coverage=Coverage.COMPLETE, warnings=("x",))

    def test_limited_document_requires_warnings(self) -> None:
        blocks = (make_block("d1", "body:p0", "body", 0, (make_run("a", 0),)),)
        with pytest.raises(ValueError, match="warning"):
            make_document(blocks, coverage=Coverage.LIMITED, warnings=())

    def test_empty_document_is_valid_and_complete(self) -> None:
        document = make_document(())
        assert document.blocks == ()
        assert document.coverage is Coverage.COMPLETE
        assert document.warnings == ()

    def test_limited_document_with_warnings_is_valid(self) -> None:
        blocks = (make_block("d1", "body:p0", "body", 0, (make_run("a", 0),)),)
        document = make_document(
            blocks, coverage=Coverage.LIMITED, warnings=("tracked-revisions-unsupported",)
        )
        assert document.coverage is Coverage.LIMITED
        assert document.warnings == ("tracked-revisions-unsupported",)
