"""Minimal desktop workspace: import and inspect a real DOCX document.

This slice (Task 2) shows filename, coverage warnings and document blocks
with effective-strike formatting. Parsing stays outside widgets: the window
only calls the application-layer import use case and renders the returned
domain values. Verification, checklist management and background execution
remain unimplemented and stay disabled.

Task 4 adds an explicit UI lifecycle (UiState), an operation-generation token
that prevents stale background outcomes from becoming current, and injected
in-memory CheckItems. Background import/verification workers arrive in later
Task 4 subtasks; the state transitions here are the foundation they build on.
"""

from __future__ import annotations

import html
import threading
from collections.abc import Sequence
from enum import Enum
from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, QThread
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from design_requirement_checker.application import (
    VerificationOutcome,
    VerificationState,
)
from design_requirement_checker.domain import (
    CheckItem,
    CheckResult,
    Coverage,
    Document,
    DocumentLocation,
    TextRun,
)
from design_requirement_checker.ui.workers import ImportWorker, VerificationWorker

if TYPE_CHECKING:
    from design_requirement_checker.application import ImportFailure

_LEGEND = "图例：<s>删除线</s>＝已划线文本；〔…〕＝删除线状态未知；其余为未划线原文。"


class UiState(Enum):
    """UI lifecycle states driving action availability."""

    EMPTY = "empty"
    IMPORTING = "importing"
    READY = "ready"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


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
    def __init__(self, check_items: Sequence[CheckItem] = ()) -> None:
        super().__init__()
        self.setWindowTitle("设计需求核查工具")
        self.resize(1100, 720)
        self.setMinimumSize(760, 480)

        self._check_items: tuple[CheckItem, ...] = tuple(check_items)
        self._document: Document | None = None
        self._results: tuple[CheckResult, ...] = ()
        self._state: UiState = UiState.EMPTY
        #: Monotonic operation generation; workers complete only when their
        #: generation still matches, so stale outcomes never become current.
        self._op_generation: int = 0

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
            "后台核查与检查项管理在后续任务中实现。"
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)

        actions = QHBoxLayout()
        self._import_button = QPushButton("导入 DOCX")
        self._import_button.clicked.connect(self._on_import_clicked)
        actions.addWidget(self._import_button)
        self._run_button = QPushButton("开始核查")
        self._run_button.setEnabled(False)
        self._run_button.clicked.connect(self._on_run_clicked)
        actions.addWidget(self._run_button)
        self._cancel_button = QPushButton("取消核查")
        self._cancel_button.setEnabled(False)
        self._cancel_button.clicked.connect(self._on_cancel_clicked)
        actions.addWidget(self._cancel_button)
        self._manage_button = QPushButton("检查项管理")
        self._manage_button.setEnabled(False)
        actions.addWidget(self._manage_button)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setVisible(False)
        actions.addWidget(self._progress)
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
        self._thread: QThread | None = None
        self._worker: ImportWorker | VerificationWorker | None = None
        self._active_threads: list[QThread] = []
        self._cancel_event: threading.Event | None = None
        self._update_actions()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._stop_worker()
        super().closeEvent(event)

    def _stop_worker(self) -> None:
        """Quit every running background thread; blocks briefly for clean exit."""
        for thread in list(self._active_threads):
            thread.quit()
            thread.wait(2000)
        self._active_threads.clear()
        self._thread = None
        self._worker = None
        # Drain queued worker-finished signals so they don't fire after close.
        QCoreApplication.processEvents()

    # --- public lifecycle API ----------------------------------------------

    @property
    def state(self) -> UiState:
        return self._state

    @property
    def results(self) -> tuple[CheckResult, ...]:
        return self._results

    @property
    def has_check_items(self) -> bool:
        return bool(self._check_items)

    def set_document(self, document: Document) -> None:
        """Replace the current document; clears results and invalidates ops."""
        self._op_generation += 1
        self._document = document
        self._results = ()
        self._state = UiState.READY
        self._show_document(document)
        self._update_actions()

    def start_verification(self) -> int:
        """Begin a verification run; returns the operation generation token."""
        self._op_generation += 1
        self._state = UiState.VERIFYING
        self._results = ()
        self._update_actions()
        return self._op_generation

    def complete_verification(self, generation: int, results: Sequence[CheckResult]) -> bool:
        """Apply results only if the generation is still current."""
        if generation != self._op_generation:
            return False
        self._results = tuple(results)
        self._state = UiState.COMPLETED
        self._update_actions()
        return True

    def cancel_verification(self) -> None:
        """Mark the run cancelled; results stay empty, never completed."""
        self._state = UiState.CANCELLED
        self._results = ()
        self._update_actions()

    def fail_verification(self, message: str) -> None:
        """Mark the run failed; results stay empty, never completed."""
        self._state = UiState.FAILED
        self._results = ()
        self.statusBar().showMessage(f"核查失败：{message}")
        self._update_actions()

    # --- action enablement --------------------------------------------------

    def _update_actions(self) -> None:
        s = self._state
        self._import_button.setEnabled(s not in (UiState.IMPORTING, UiState.VERIFYING))
        can_run = self._document is not None and self.has_check_items
        runnable_states = (
            UiState.READY,
            UiState.COMPLETED,
            UiState.CANCELLED,
            UiState.FAILED,
        )
        self._run_button.setEnabled(can_run and s in runnable_states)
        self._cancel_button.setEnabled(s in (UiState.IMPORTING, UiState.VERIFYING))
        self._manage_button.setEnabled(False)

    # --- background import --------------------------------------------------

    def _on_import_clicked(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self, "选择 DOCX 文件", "", "Word 文档 (*.docx)"
        )
        if not path:
            return
        self._start_import(path)

    def _start_import(self, path: str) -> None:
        """Run import off the UI thread; stale completions are discarded."""
        self._op_generation += 1
        generation = self._op_generation
        self._state = UiState.IMPORTING
        self._results = ()
        self._progress.setVisible(True)
        self.statusBar().showMessage("正在读取文档…")
        self._update_actions()

        self._thread = QThread()
        self._worker = ImportWorker(path, generation)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_import_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(
            lambda: (
                self._active_threads.remove(self._thread)
                if self._thread in self._active_threads
                else None
            )
        )
        self._active_threads.append(self._thread)
        self._thread.start()

    def _on_import_finished(self, outcome: Document | ImportFailure, generation: int) -> bool:
        """Apply the import outcome only if its generation is still current."""
        if generation != self._op_generation:
            return False
        self._progress.setVisible(False)
        self._thread = None
        self._worker = None
        self.show_import_outcome(outcome)
        return True

    def show_import_outcome(self, outcome: Document | ImportFailure) -> None:
        """Display an import outcome; parsing happens outside this window."""
        from design_requirement_checker.application import ImportFailure

        if isinstance(outcome, ImportFailure):
            self._show_failure(outcome)
        else:
            self.set_document(outcome)

    # --- background verification -------------------------------------------

    def _on_run_clicked(self) -> None:
        if self._document is None or not self._check_items:
            return
        generation = self.start_verification()
        self._cancel_event = threading.Event()
        self._progress.setVisible(True)
        self.statusBar().showMessage("正在核查…")

        self._thread = QThread()
        self._worker = VerificationWorker(
            self._document, self._check_items, self._cancel_event, generation
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_verification_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(
            lambda: (
                self._active_threads.remove(self._thread)
                if self._thread in self._active_threads
                else None
            )
        )
        self._active_threads.append(self._thread)
        self._thread.start()

    def _on_cancel_clicked(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()

    def _on_verification_finished(self, outcome: VerificationOutcome, generation: int) -> bool:
        """Apply a verification outcome only if it is still current.

        Stale outcomes (wrong generation or a document that is no longer
        current) are discarded. A cancelled run never carries results.
        """
        if generation != self._op_generation:
            return False
        if self._document is None or outcome.document_id != self._document.document_id:
            return False
        self._progress.setVisible(False)
        self._thread = None
        self._worker = None
        if outcome.state is VerificationState.CANCELLED:
            self.cancel_verification()
        elif outcome.state is VerificationState.COMPLETED:
            self.complete_verification(generation, outcome.results)
        else:  # VerificationState.FAILED
            self.fail_verification("verification failed")
        return True

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
        self._document = None
        self._results = ()
        self._state = UiState.FAILED
        self._summary_label.setText(f"导入失败：{failure.filename}")
        self._warnings_label.setText("")
        self._warnings_label.setVisible(False)
        self._blocks_view.setHtml(
            f"<p>无法读取所选文件（原因：{html.escape(failure.reason)}）。</p>"
            f"<p>{html.escape(failure.detail)}</p>"
        )
        self.statusBar().showMessage(f"导入失败：{failure.filename}")
        self._update_actions()
