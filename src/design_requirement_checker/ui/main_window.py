"""Minimal desktop workspace: import and inspect a real DOCX document.

This slice (Task 2) shows filename, coverage warnings and document blocks
with effective-strike formatting. Parsing stays outside widgets: the window
only calls the application-layer import use case and renders the returned
domain values. Verification, checklist management and background execution
remain unimplemented and stay disabled.
"""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from design_requirement_checker.domain import Coverage, Document, DocumentLocation, TextRun

if TYPE_CHECKING:
    from design_requirement_checker.application import ImportFailure

_LEGEND = "图例：<s>删除线</s>＝已划线文本；〔…〕＝删除线状态未知；其余为未划线原文。"


def format_location(location: DocumentLocation) -> str:
    """Human-readable one-based location; domain coordinates are zero-based."""
    if location.part == "body":
        return f"正文 · 段{location.paragraph_index + 1}"
    cells = [*location.ancestor_path]
    if location.cell is not None:
        cells.append(location.cell)
    cell_text = " › ".join(
        f"表{c.table_index + 1} · 行{c.row_index + 1} · 单元格{c.column_index + 1}" for c in cells
    )
    return f"{cell_text} · 段{location.paragraph_index + 1}"


def _format_run_html(run: TextRun) -> str:
    text = html.escape(run.text)
    if not text:
        return ""
    if run.effective_strike is True:
        return f"<s>{text}</s>"
    if run.effective_strike is None:
        return f"〔{text}〕"
    return text


def format_blocks_html(document: Document) -> str:
    """Render document blocks as Qt rich text with strike formatting.

    Run paragraphs use ``white-space: pre-wrap`` so multiple spaces and tabs
    from the raw block text stay visible (Qt's rich-text engine collapses
    them in plain ``<p>`` elements). The underlying domain text is unchanged.
    """
    if not document.blocks:
        return "<p>文档为空：未发现正文段落或表格内容。</p>"
    parts = [f"<p>{_LEGEND}</p>"]
    for block in document.blocks:
        runs_html = "".join(_format_run_html(run) for run in block.runs) or "（空段落）"
        parts.append(f"<p><b>{html.escape(format_location(block.location))}</b></p>")
        parts.append(f'<p style="white-space: pre-wrap">{runs_html}</p>')
    return "".join(parts)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("设计需求核查工具")
        self.resize(1100, 720)
        self.setMinimumSize(760, 480)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        title = QLabel("设计需求核查工具")
        font = title.font()
        font.setPointSize(20)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        notice = QLabel(
            "文档导入与查看已实现：选择 .docx 文件后显示文本块与删除线格式。"
            "自动核查、检查项管理与后台执行尚未实现。"
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)

        actions = QHBoxLayout()
        import_button = QPushButton("导入 DOCX")
        import_button.clicked.connect(self._on_import_clicked)
        actions.addWidget(import_button)
        for text in ("开始核查（待实现）", "检查项管理（待实现）"):
            button = QPushButton(text)
            button.setEnabled(False)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)

        self._summary_label = QLabel("尚未导入文档。")
        self._summary_label.setWordWrap(True)
        self._warnings_label = QLabel("")
        self._warnings_label.setWordWrap(True)
        self._warnings_label.setVisible(False)
        self._blocks_view = QTextBrowser()

        panel = QGroupBox("文档")
        panel_layout = QVBoxLayout(panel)
        panel_layout.addWidget(self._summary_label)
        panel_layout.addWidget(self._warnings_label)
        panel_layout.addWidget(self._blocks_view, 1)
        layout.addWidget(panel, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("尚未导入文档")

    def _on_import_clicked(self) -> None:
        # Deferred import keeps startup composition free of document adapters.
        from design_requirement_checker.application import import_document

        path, _selected_filter = QFileDialog.getOpenFileName(
            self, "选择 DOCX 文件", "", "Word 文档 (*.docx)"
        )
        if not path:
            return
        self.show_import_outcome(import_document(path))

    def show_import_outcome(self, outcome: Document | ImportFailure) -> None:
        """Display an import outcome; parsing happens outside this window."""
        from design_requirement_checker.application import ImportFailure

        if isinstance(outcome, ImportFailure):
            self._show_failure(outcome)
        else:
            self._show_document(outcome)

    def _show_document(self, document: Document) -> None:
        if document.coverage is Coverage.COMPLETE:
            coverage_text = "完全"
        else:
            coverage_text = f"受限（{len(document.warnings)} 项警告）"
        self._summary_label.setText(
            f"文件：{document.filename}｜指纹：{document.content_fingerprint[:12]}…"
            f"｜覆盖范围：{coverage_text}｜文本块：{len(document.blocks)}"
        )
        if document.warnings:
            self._warnings_label.setText("检查范围受限：" + "、".join(document.warnings))
            self._warnings_label.setVisible(True)
        else:
            self._warnings_label.setText("")
            self._warnings_label.setVisible(False)
        self._blocks_view.setHtml(format_blocks_html(document))
        self.statusBar().showMessage(
            f"已导入 {document.filename} · {len(document.blocks)} 个文本块"
            f" · 覆盖范围：{coverage_text}"
        )

    def _show_failure(self, failure: ImportFailure) -> None:
        self._summary_label.setText(f"导入失败：{failure.filename}")
        self._warnings_label.setText("")
        self._warnings_label.setVisible(False)
        self._blocks_view.setHtml(
            f"<p>无法读取所选文件（原因：{html.escape(failure.reason)}）。</p>"
            f"<p>{html.escape(failure.detail)}</p>"
        )
        self.statusBar().showMessage(f"导入失败：{failure.filename}")
