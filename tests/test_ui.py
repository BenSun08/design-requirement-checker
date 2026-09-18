"""Minimal Qt presentation tests for the Task 2 vertical slice.

The window must render domain values without parsing inside widgets: block
list, one-based locations, strike formatting, LIMITED warnings, and explicit
failure — with only implemented operations enabled.
"""

import os

import fixture_factory as fixtures
import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from design_requirement_checker.application import ImportFailure, import_document
from design_requirement_checker.domain import (
    BlockType,
    DocumentLocation,
    TableCellCoordinates,
)
from design_requirement_checker.ui.main_window import (
    MainWindow,
    format_blocks_html,
    format_location,
)


@pytest.fixture(scope="module")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    application = QApplication.instance() or QApplication([])
    yield application


class TestEnabledActions:
    def test_only_implemented_actions_are_enabled(self, qapp) -> None:
        window = MainWindow()
        enabled = [
            button.text() for button in window.findChildren(QPushButton) if button.isEnabled()
        ]
        disabled = [
            button.text() for button in window.findChildren(QPushButton) if not button.isEnabled()
        ]
        window.close()
        assert enabled == ["导入 DOCX"]
        assert "开始核查（待实现）" in disabled
        assert "检查项管理（待实现）" in disabled


class TestPureFormatting:
    def test_body_location_is_one_based(self) -> None:
        location = DocumentLocation(
            document_id="d",
            block_id="body:p2",
            block_type=BlockType.PARAGRAPH,
            part="body",
            paragraph_index=2,
        )
        assert format_location(location) == "正文 · 段3"

    def test_table_cell_location_is_one_based(self) -> None:
        location = DocumentLocation(
            document_id="d",
            block_id="t0r2c1:table-cell:p0",
            block_type=BlockType.TABLE_CELL_PARAGRAPH,
            part="table-cell",
            paragraph_index=0,
            cell=TableCellCoordinates(0, 2, 1),
        )
        assert format_location(location) == "表1 · 行3 · 单元格2 · 段1"

    def test_nested_cell_location_shows_ancestor_path(self) -> None:
        location = DocumentLocation(
            document_id="d",
            block_id="t0r2c1>t0r0c0:table-cell:p0",
            block_type=BlockType.TABLE_CELL_PARAGRAPH,
            part="table-cell",
            paragraph_index=0,
            cell=TableCellCoordinates(0, 0, 0),
            ancestor_path=(TableCellCoordinates(0, 2, 1),),
        )
        assert format_location(location) == "表1 · 行3 · 单元格2 › 表1 · 行1 · 单元格1 · 段1"

    def test_strike_and_unknown_formatting_markers(self, tmp_path) -> None:
        document = import_document(fixtures.build_strike_matrix(tmp_path / "strike.docx"))
        html = format_blocks_html(document)
        assert "图例" in html
        assert "<s>direct strike</s>" in html
        assert "<s>gone </s>" in html
        assert "〔maybe〕" in html
        assert "〔dbl〕" in html
        assert "〔orphan〕" in html

    def test_empty_document_renders_explicit_empty_state(self, tmp_path) -> None:
        document = import_document(fixtures.build_empty(tmp_path / "empty.docx"))
        html = format_blocks_html(document)
        assert "文档为空" in html


class TestWindowDisplay:
    def test_document_outcome_populates_summary_and_blocks(self, qapp, tmp_path) -> None:
        window = MainWindow()
        document = import_document(fixtures.build_normal(tmp_path / "normal.docx"))
        window.show_import_outcome(document)
        assert "normal.docx" in window._summary_label.text()
        assert "完全" in window._summary_label.text()
        assert "文本块：5" in window._summary_label.text()
        assert "plain body paragraph one" in window._blocks_view.toPlainText()
        assert window._warnings_label.isHidden() is True
        window.close()

    def test_limited_outcome_shows_warnings(self, qapp, tmp_path) -> None:
        window = MainWindow()
        document = import_document(fixtures.build_excluded_parts(tmp_path / "excluded.docx"))
        window.show_import_outcome(document)
        assert "受限" in window._summary_label.text()
        assert window._warnings_label.isHidden() is False
        assert "header-content-not-checked" in window._warnings_label.text()
        window.close()

    def test_failure_outcome_shows_explicit_error(self, qapp) -> None:
        window = MainWindow()
        failure = ImportFailure(
            filename="broken.docx",
            reason="unreadable-file",
            detail="PackageNotFoundError: bad zip file",
        )
        window.show_import_outcome(failure)
        assert "导入失败" in window._summary_label.text()
        assert "broken.docx" in window._summary_label.text()
        assert "PackageNotFoundError" in window._blocks_view.toPlainText()
        assert window._warnings_label.isHidden() is True
        window.close()

    def test_empty_document_is_distinct_from_failure(self, qapp, tmp_path) -> None:
        window = MainWindow()
        document = import_document(fixtures.build_empty(tmp_path / "empty.docx"))
        window.show_import_outcome(document)
        assert "导入失败" not in window._summary_label.text()
        assert "文本块：0" in window._summary_label.text()
        assert "文档为空" in window._blocks_view.toPlainText()
        window.close()
