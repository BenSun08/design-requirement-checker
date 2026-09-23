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
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QThread, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSplitter,
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
    CheckStatus,
    ComparisonState,
    Coverage,
    Document,
    DocumentBlock,
    DocumentLocation,
    MatchEvidence,
    MatchType,
    Resolution,
    TextRun,
)
from design_requirement_checker.ui.workers import ImportWorker, VerificationWorker

if TYPE_CHECKING:
    from design_requirement_checker.application import ImportFailure

_LEGEND = "图例：<s>删除线</s>＝已划线文本；〔…〕＝删除线状态未知；其余为未划线原文。"

_COMPARISON_LABELS = {
    ComparisonState.SAME: "描述一致",
    ComparisonState.DIFFERENT: "描述有差异",
    ComparisonState.NOT_COMPARED: "未比较描述",
}

_MATCH_TYPE_LABELS = {
    MatchType.EXACT: "精确匹配",
    MatchType.NORMALIZED: "规范化匹配",
    MatchType.ALIAS: "别名匹配",
}

# UI-only mapping of stable UNRESOLVED reason tokens to Chinese text.
_REASON_LABELS: dict[str, str] = {
    "partial-strike": "部分划线",
    "unknown-strike-formatting": "划线格式未知",
    "active-and-struck-coexist": "生效与划线共存",
    "conflicting-key-parameters": "关键参数冲突",
    "ambiguous-function-identity": "功能身份歧义",
}

# UI-only mapping for comparison_reason tokens. Domain tokens are left
# unchanged; this only affects what the reviewer reads.
_COMPARISON_REASON_LABELS: dict[str, str] = {
    "expected-description-empty": "未设置期望描述",
    "nothing-to-compare": "没有可比较的实际需求",
    "evidence-struck": "匹配证据已被划除",
    "result-unresolved": "核查结果存在不确定项",
    "requirement-span-association-uncertain": "无法可靠确定需求描述范围",
    "no-associated-requirement-content": "未找到与检测短语关联的需求内容",
    "mixed-comparison-occurrences": "多处证据的描述比较结果不一致",
}


@dataclass(frozen=True)
class ResultSummary:
    """Counts derived from domain states; 描述有差异 is orthogonal to total."""

    total: int
    configured: int
    missing: int
    struck_out: int
    unresolved: int
    different: int


def _result_group(result: CheckResult) -> int:
    """Stable sort key for result ordering (lower sorts first).

    1. UNRESOLVED → 2. MISSING → 3. STRUCK_OUT → 4. CONFIGURED+DIFFERENT
    → 5. remaining CONFIGURED.
    """
    if result.resolution is Resolution.UNRESOLVED:
        return 0
    if result.status is CheckStatus.MISSING:
        return 1
    if result.status is CheckStatus.STRUCK_OUT:
        return 2
    if (
        result.status is CheckStatus.CONFIGURED
        and result.comparison_state is ComparisonState.DIFFERENT
    ):
        return 3
    return 4


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


def _format_block_with_highlight(
    block: DocumentBlock, highlight_span: tuple[int, int] | None
) -> str:
    """Render a block with strike formatting and an optional highlighted span."""
    chars: list[tuple[str, bool | None]] = []
    for run in block.runs:
        for ch in run.text:
            chars.append((ch, run.effective_strike))
    segments: list[tuple[str, bool | None, bool]] = []
    cur_text = ""
    cur_strike: bool | None = False
    cur_hl = False
    for i, (ch, strike) in enumerate(chars):
        hl = bool(highlight_span and highlight_span[0] <= i < highlight_span[1])
        if cur_text and (strike != cur_strike or hl != cur_hl):
            segments.append((cur_text, cur_strike, cur_hl))
            cur_text = ""
        cur_text += ch
        cur_strike = strike
        cur_hl = hl
    if cur_text:
        segments.append((cur_text, cur_strike, cur_hl))
    rendered = ""
    for text, strike, hl in segments:
        piece = html.escape(text)
        if strike is True:
            piece = f"<s>{piece}</s>"
        elif strike is None:
            piece = f"〔{piece}〕"
        if hl:
            piece = f"<mark>{piece}</mark>"
        rendered += piece
    return rendered or "（空段落）"


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


#: Explicit startup baseline conditions. Mirrors the failure/success tokens of
#: application.BaselineLoadResult.source so the UI never parses error strings.
_BASELINE_LOAD_STATES = (
    "normal",
    "no-baseline",
    "backup",
    "load-error",
    "unsupported-schema",
)


class MainWindow(QMainWindow):
    def __init__(
        self,
        check_items: Sequence[CheckItem] = (),
        baseline_id: str = "",
        baseline_load_state: str | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("设计需求核查工具")
        self.resize(1440, 900)
        self.setMinimumSize(1024, 600)

        self._check_items: tuple[CheckItem, ...] = tuple(check_items)
        self._baseline_id: str = baseline_id
        #: Startup baseline condition, passed explicitly by the composition
        #: root from BaselineLoadResult.source — never inferred from banner
        #: text or item counts. Valid values: normal / no-baseline / backup /
        #: load-error / unsupported-schema.
        if baseline_load_state is None:
            baseline_load_state = "normal" if check_items else "no-baseline"
        if baseline_load_state not in _BASELINE_LOAD_STATES:
            raise ValueError(f"unknown baseline_load_state: {baseline_load_state!r}")
        self._baseline_load_state: str = baseline_load_state
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
            "导入 DOCX 文档后可执行后台核查，查看结果列表与详情。点击 “检查项管理” 可编辑基准内容。"
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
        self._manage_button.clicked.connect(self._on_manage_clicked)
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
        self._baseline_banner = QLabel("")
        self._baseline_banner.setWordWrap(True)
        self._baseline_banner.setVisible(False)

        # Summary + search strip.
        strip = QHBoxLayout()
        strip.addWidget(self._summary_label)
        strip.addWidget(self._warnings_label)
        strip.addStretch()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索：编号 / 名称 / 类别 / 期望描述")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._populate_results)
        strip.addWidget(self._search_input)
        layout.addLayout(strip)
        layout.addWidget(self._baseline_banner)

        # Filter buttons.
        self._current_filter = "全部"
        self._filter_buttons: dict[str, QPushButton] = {}
        filter_row = QHBoxLayout()
        for name in ("全部", "已配置", "未配置", "已划除", "待人工核查", "仅异常"):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setChecked(name == "全部")
            btn.clicked.connect(lambda _checked=False, n=name: self._set_filter(n))
            self._filter_buttons[name] = btn
            filter_row.addWidget(btn)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Result list (left) + detail (right).
        self._splitter = QSplitter()
        self._result_list = QListWidget()
        self._result_list.setMinimumWidth(240)
        self._detail_view = QTextBrowser()
        self._detail_view.setOpenExternalLinks(False)
        self._detail_view.anchorClicked.connect(self._on_evidence_anchor)
        self._splitter.addWidget(self._result_list)
        self._splitter.addWidget(self._detail_view)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 3)
        layout.addWidget(self._splitter, 1)
        self._result_list.currentItemChanged.connect(self._on_result_selected)

        self.setCentralWidget(central)
        self._search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self._search_shortcut.activated.connect(self._search_input.setFocus)
        if self._check_items:
            self.statusBar().showMessage(f"已加载 {len(self._check_items)} 项检查基准")
        else:
            self.statusBar().showMessage("尚未加载检查基准 — 点击检查项管理以配置")
        self._thread: QThread | None = None
        self._worker: ImportWorker | VerificationWorker | None = None
        self._active_threads: list[QThread] = []
        #: Thread owned by each operation generation, so a stale completion can
        #: still quit exactly its own thread without touching current refs.
        self._thread_for_generation: dict[int, QThread] = {}
        self._cancel_event: threading.Event | None = None
        self._close_requested = False
        self._detail_result: CheckResult | None = None
        self._evidence_index: int = 0
        self._update_actions()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Never accept close while any owned QThread is still running.

        Cooperative verification cancellation is requested before quit; import
        has no cooperative cancel so we simply ask its thread to quit its
        event loop. If any thread is still alive we ignore the close and rely
        on _on_thread_finished scheduling a deferred retry when the last thread
        exits. No processEvents() pumping from inside closeEvent.
        """
        self._close_requested = True
        # Cooperative cancellation for verification work (Task 3).
        if self._cancel_event is not None:
            self._cancel_event.set()
        # Ask each thread to quit its event loop. quit() is thread-safe; the
        # worker thread stops its own event loop via DirectConnection.
        for thread in list(self._active_threads):
            thread.quit()
        # If any thread is still actually running (import has no cooperative
        # cancel, quit() only affects the event loop, not the currently
        # executing import_document call), defer the close.
        if any(t.isRunning() for t in self._active_threads):
            event.ignore()
            return
        event.accept()

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
        self._result_list.clear()
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
        self._populate_results()
        self._update_summary()
        self._update_actions()
        return True

    # --- Baseline startup / recovery UX (Task 5) -------------------------

    def apply_baseline_load(self, source: str, error: str | None = None) -> None:
        """Record the startup baseline condition and show its banner.

        ``source`` is the application-layer ``BaselineLoadResult.source``
        token, passed explicitly — the UI never infers the condition from
        error strings or item counts.
        """
        if source not in _BASELINE_LOAD_STATES:
            raise ValueError(f"unknown baseline load source: {source!r}")
        self._baseline_load_state = source
        if source == "backup":
            self.set_baseline_recovered(
                "已从备份基准恢复 · 主基准文件不可用 · 建议检查文件系统权限"
            )
        elif source == "load-error":
            self.set_baseline_failure(error or "未知错误")
        elif source == "unsupported-schema":
            self._baseline_banner.setStyleSheet(
                "background-color: #f8d7da; color: #842029; padding: 6px 10px;"
            )
            self._baseline_banner.setText(
                "当前基准文件由不兼容的较新版本创建。\n"
                "本版本不会覆盖该文件。\n"
                "请使用兼容版本打开，或先人工备份/移走该文件。"
            )
            self._baseline_banner.setVisible(True)
            self.statusBar().showMessage("检查基准不兼容")
        # normal / no-baseline: no banner, ordinary first-use experience.

    def set_baseline_recovered(self, message: str) -> None:
        """Show a persistent warning that the baseline came from backup."""
        self._baseline_banner.setStyleSheet(
            "background-color: #fff3cd; color: #856404; padding: 6px 10px;"
        )
        self._baseline_banner.setText(message)
        self._baseline_banner.setVisible(True)

    def set_baseline_failure(self, message: str) -> None:
        """Show an explicit compatibility / load failure banner."""
        self._baseline_banner.setStyleSheet(
            "background-color: #f8d7da; color: #842029; padding: 6px 10px;"
        )
        self._baseline_banner.setText(
            f"检查基准加载失败：{message}\n请检查 AppData 目录权限或重新配置基准。"
        )
        self._baseline_banner.setVisible(True)
        self.statusBar().showMessage("检查基准加载失败")

    def clear_baseline_banner(self) -> None:
        """Hide the baseline banner; used after a successful recovery save."""
        self._baseline_banner.clear()
        self._baseline_banner.setVisible(False)

    # --- result summary & ordering -----------------------------------------

    @staticmethod
    def _compute_summary(results: Sequence[CheckResult]) -> ResultSummary:
        configured = sum(1 for r in results if r.status is CheckStatus.CONFIGURED)
        missing = sum(1 for r in results if r.status is CheckStatus.MISSING)
        struck_out = sum(1 for r in results if r.status is CheckStatus.STRUCK_OUT)
        unresolved = sum(1 for r in results if r.resolution is Resolution.UNRESOLVED)
        different = sum(1 for r in results if r.comparison_state is ComparisonState.DIFFERENT)
        return ResultSummary(
            total=configured + missing + struck_out + unresolved,
            configured=configured,
            missing=missing,
            struck_out=struck_out,
            unresolved=unresolved,
            different=different,
        )

    @staticmethod
    def _order_results(results: Sequence[CheckResult]) -> tuple[CheckResult, ...]:
        """Order by review priority; original order is stable within a group."""
        return tuple(sorted(results, key=_result_group))

    def _populate_results(self) -> None:
        self._result_list.clear()
        visible = self._filtered_results()
        if not visible:
            self._result_list.addItem("无匹配结果")
            self._detail_view.clear()
            return
        for result in visible:
            item = result.check_item
            parts = [item.code, item.name, self._status_text(result)]
            if result.comparison_state is ComparisonState.DIFFERENT:
                parts.append(_COMPARISON_LABELS[ComparisonState.DIFFERENT])
            label = " · ".join(parts)
            list_item = QListWidgetItem(label)
            list_item.setData(Qt.ItemDataRole.UserRole, result)
            self._result_list.addItem(list_item)

    def _set_filter(self, name: str) -> None:
        self._current_filter = name
        for btn_name, btn in self._filter_buttons.items():
            btn.setChecked(btn_name == name)
        self._populate_results()

    def _filtered_results(self) -> tuple[CheckResult, ...]:
        """Apply active filter and search; never recomputes verification."""
        results = list(self._order_results(self._results))
        f = self._current_filter
        if f == "已配置":
            results = [r for r in results if r.status is CheckStatus.CONFIGURED]
        elif f == "未配置":
            results = [r for r in results if r.status is CheckStatus.MISSING]
        elif f == "已划除":
            results = [r for r in results if r.status is CheckStatus.STRUCK_OUT]
        elif f == "待人工核查":
            results = [r for r in results if r.resolution is Resolution.UNRESOLVED]
        elif f == "仅异常":
            results = [r for r in results if self._is_exception(r)]
        query = self._search_input.text().strip().lower()
        if query:
            results = [r for r in results if self._matches_search(r, query)]
        return tuple(results)

    @staticmethod
    def _is_exception(result: CheckResult) -> bool:
        return (
            result.status in (CheckStatus.MISSING, CheckStatus.STRUCK_OUT)
            or result.resolution is Resolution.UNRESOLVED
            or (
                result.status is CheckStatus.CONFIGURED
                and result.comparison_state is ComparisonState.DIFFERENT
            )
        )

    @staticmethod
    def _matches_search(result: CheckResult, query: str) -> bool:
        item = result.check_item
        haystack = " ".join(
            (item.code, item.name, item.category, item.expected_description)
        ).lower()
        return query in haystack

    # --- result detail ------------------------------------------------------

    def _on_result_selected(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if self._close_requested or current is None:
            return
        result = current.data(Qt.ItemDataRole.UserRole)
        if isinstance(result, CheckResult):
            self._show_detail(result)

    @staticmethod
    def _status_text(result: CheckResult) -> str:
        if result.resolution is Resolution.UNRESOLVED:
            return "待人工核查"
        if result.status is CheckStatus.CONFIGURED:
            return "已配置"
        if result.status is CheckStatus.MISSING:
            return "未配置"
        if result.status is CheckStatus.STRUCK_OUT:
            return "已划除"
        return "未知"

    def _show_detail(self, result: CheckResult) -> None:
        self._detail_result = result
        self._evidence_index = 0
        self._render_detail()

    def _select_evidence(self, index: int) -> None:
        if self._detail_result is None:
            return
        if 0 <= index < len(self._detail_result.evidence):
            self._evidence_index = index
            self._render_detail()

    def _on_evidence_anchor(self, url: QUrl) -> None:
        scheme, _, value = url.toString().partition(":")
        if scheme == "evidence" and value.isdigit():
            self._select_evidence(int(value))

    def _render_detail(self) -> None:
        result = self._detail_result
        if result is None:
            return
        item = result.check_item
        evidence = result.evidence
        selected = (
            evidence[self._evidence_index] if 0 <= self._evidence_index < len(evidence) else None
        )
        actual_text = selected.requirement_text if selected is not None else ""
        match_method = (
            _MATCH_TYPE_LABELS.get(selected.match_type, "") if selected is not None else ""
        )
        comparison_text = _COMPARISON_LABELS.get(result.comparison_state, "未比较描述")

        parts: list[str] = [
            f"<h3>{html.escape(item.code)} · {html.escape(item.name)}</h3>",
            f"<p>类别：{html.escape(item.category)}</p>",
            f"<p>状态：{self._status_text(result)}</p>",
            f"<p>描述比较：{comparison_text}</p>",
            f"<p>期望描述：{html.escape(item.expected_description)}</p>",
        ]
        if result.status is CheckStatus.MISSING:
            parts.append("<p>在已检查范围内未找到匹配证据</p>")
        if actual_text:
            if result.status is CheckStatus.STRUCK_OUT:
                parts.append(f"<p>实际需求：<s>{html.escape(actual_text)}</s></p>")
            else:
                parts.append(f"<p>实际需求：{html.escape(actual_text)}</p>")
        if match_method:
            parts.append(f"<p>匹配方式：{match_method}</p>")
        if selected is not None:
            parts.append(f"<p>位置：{html.escape(format_location(selected.location))}</p>")
        if result.comparison_reason:
            reason_text = _COMPARISON_REASON_LABELS.get(
                result.comparison_reason, result.comparison_reason
            )
            parts.append(f"<p>比较原因：{html.escape(reason_text)}</p>")
        if result.review_reasons:
            reasons = "".join(
                f"<li>{html.escape(_REASON_LABELS.get(r, r))}</li>" for r in result.review_reasons
            )
            parts.append(f"<p>核查原因：</p><ul>{reasons}</ul>")

        if len(evidence) > 1:
            links = " ".join(
                f'<a href="evidence:{i}">证据 {i + 1}</a>' for i in range(len(evidence))
            )
            parts.append(f"<p>证据：{links}</p>")

        if selected is not None and result.status is not CheckStatus.MISSING:
            parts.append(self._source_context_html(selected))

        self._detail_view.setHtml("".join(parts))

    def _source_context_html(self, evidence: MatchEvidence) -> str:
        """Rebuild prev/current/next block context from the current document."""
        if self._document is None:
            return ""
        blocks = self._document.blocks
        idx = next(
            (i for i, b in enumerate(blocks) if b.block_id == evidence.block_id),
            None,
        )
        if idx is None:
            return ""
        span = evidence.requirement_span
        parts = ["<hr><p>源文本上下文（重建文本，非 Word 页面渲染）</p>"]
        if idx > 0:
            prev = blocks[idx - 1]
            parts.append(f"<p><i>上一段：{html.escape(format_location(prev.location))}</i></p>")
            parts.append(
                f'<p style="white-space: pre-wrap">{_format_block_with_highlight(prev, None)}</p>'
            )
        current = blocks[idx]
        parts.append(f"<p><b>当前：{html.escape(format_location(current.location))}</b></p>")
        parts.append(
            f'<p style="white-space: pre-wrap">{_format_block_with_highlight(current, span)}</p>'
        )
        if idx < len(blocks) - 1:
            nxt = blocks[idx + 1]
            parts.append(f"<p><i>下一段：{html.escape(format_location(nxt.location))}</i></p>")
            parts.append(
                f'<p style="white-space: pre-wrap">{_format_block_with_highlight(nxt, None)}</p>'
            )
        return "".join(parts)

    def _update_summary(self) -> None:
        if not self._results:
            return
        s = self._compute_summary(self._results)
        self._summary_label.setText(
            f"全部 {s.total} · 已配置 {s.configured} · 未配置 {s.missing}"
            f" · 已划除 {s.struck_out} · 待人工核查 {s.unresolved}"
            f" · 描述有差异 {s.different}"
        )

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
        idle_for_ui = s not in (UiState.IMPORTING, UiState.VERIFYING)
        self._import_button.setEnabled(idle_for_ui)
        can_run = self._document is not None and self.has_check_items
        runnable_states = (
            UiState.READY,
            UiState.COMPLETED,
            UiState.CANCELLED,
            UiState.FAILED,
        )
        self._run_button.setEnabled(can_run and s in runnable_states)
        # Cancel only applies to verification; import has no cooperative cancel.
        self._cancel_button.setEnabled(s is UiState.VERIFYING)
        # Manage baseline is allowed whenever no background work is running.
        self._manage_button.setEnabled(idle_for_ui)

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

        thread = QThread()
        worker = ImportWorker(path, generation)
        self._thread = thread
        self._worker = worker
        self._wire_worker(thread, worker, generation, self._on_import_finished)
        thread.start()

    def _wire_worker(
        self,
        thread: QThread,
        worker: ImportWorker | VerificationWorker,
        generation: int,
        finished_handler: Callable[..., bool],
    ) -> None:
        """Connect a worker to its thread with stable captured references.

        All ``thread.finished`` handlers capture the specific ``thread``/
        ``worker`` locals so a stale operation's cleanup never touches the
        current operation's objects. The thread is also registered by
        generation so handlers can quit exactly their own thread.
        """
        self._thread_for_generation[generation] = thread
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(finished_handler)
        worker.failed.connect(self._on_worker_failed)
        # quit() is thread-safe; use DirectConnection so the worker thread
        # stops its own event loop without waiting for the UI thread.
        worker.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.failed.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda t=thread: self._on_thread_finished(t))
        self._active_threads.append(thread)

    def _on_thread_finished(self, thread: QThread) -> None:
        """Remove exactly the thread that finished from every ownership
        structure, by identity so stale-generation handlers can't block cleanup.

        After cleanup, if a deferred close is pending and no threads remain,
        schedule a non-reentrant close retry on the UI event loop.
        """
        if thread in self._active_threads:
            self._active_threads.remove(thread)
        # Clean thread_for_generation by identity in case the generation-based
        # pop was already consumed by a stale handler path.
        dead = [g for g, t in self._thread_for_generation.items() if t is thread]
        for g in dead:
            self._thread_for_generation.pop(g, None)
        if self._close_requested and not self._active_threads:
            # Non-reentrant: don't call self.close() directly from inside a
            # signal handler that itself is fired from QThread.finished.
            QTimer.singleShot(0, self.close)

    def _finish_operation(self, generation: int) -> None:
        """Quit and forget the thread owned by one operation generation.

        Safe for both current and stale completions: only the thread registered
        for ``generation`` is quit, and ``self._thread``/``self._worker`` are
        cleared only when they still refer to this operation.
        """
        thread = self._thread_for_generation.pop(generation, None)
        if thread is not None:
            thread.quit()
        if self._thread is thread:
            self._thread = None
            self._worker = None

    def _on_import_finished(self, outcome: Document | ImportFailure, generation: int) -> bool:
        """Apply the import outcome only if its generation is still current."""
        self._finish_operation(generation)
        if self._close_requested or generation != self._op_generation:
            return False
        self._progress.setVisible(False)
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

        thread = QThread()
        worker = VerificationWorker(
            self._document, self._check_items, self._cancel_event, generation
        )
        self._thread = thread
        self._worker = worker
        self._wire_worker(thread, worker, generation, self._on_verification_finished)
        thread.start()

    def _on_cancel_clicked(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()

    def _on_manage_clicked(self) -> None:
        """Open the checklist management workspace.

        The dialog keeps its candidate working copy and stays open until a
        save fully succeeds: it calls back into :meth:`_save_baseline_snapshot`
        on 保存基准 and only closes when that returns True. Validation
        errors, declined warnings, persistence failures and declined
        destructive-recovery confirmations all leave the dialog open with
        the candidate intact — a failed save never silently discards edits.
        The current baseline and results are mutated only after persistence
        succeeds.
        """
        from design_requirement_checker.ui.checklist_dialog import ChecklistDialog

        dialog = ChecklistDialog(
            self._check_items,
            parent=self,
            save_handler=self._save_baseline_snapshot,
        )
        dialog.exec()

    def _save_baseline_snapshot(self, new_items: tuple[CheckItem, ...]) -> bool:
        """Validate → confirm → persist → publish one candidate snapshot.

        Returns True only when the snapshot was persisted AND published;
        the checklist dialog closes only on that True. Any earlier failure
        leaves the current baseline, results and load state untouched.
        """
        from design_requirement_checker.application import save_baseline_to, validate_baseline
        from design_requirement_checker.baseline_store import (
            UnsupportedBaselineSchemaError,
            default_path,
        )

        validation = validate_baseline(new_items)

        # --- Validation errors block save entirely ---
        if validation.errors:
            from PySide6.QtWidgets import QMessageBox

            msg = "；".join(e.message for e in validation.errors)
            QMessageBox.critical(
                self,
                "检查基准无法保存",
                f"存在硬错误必须修复后才能保存：\n{msg}",
            )
            self.statusBar().showMessage("基准校验未通过 — 未保存")
            return False

        # --- Warnings are visible but do not block ---
        if validation.warnings:
            from PySide6.QtWidgets import QMessageBox

            warn_text = "\n".join(f"· {w.message}" for w in validation.warnings)
            reply = QMessageBox.warning(
                self,
                "基准存在警告",
                f"以下警告不会阻止保存，但建议人工复核：\n\n{warn_text}\n\n仍要保存吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply is not QMessageBox.StandardButton.Yes:
                self.statusBar().showMessage("已取消保存")
                return False

        # --- Destructive replacement over a damaged primary is explicit ---
        if self._baseline_load_state == "load-error":
            from PySide6.QtWidgets import QMessageBox

            reply = QMessageBox.question(
                self,
                "确认替换损坏的基准",
                "当前基准无法读取。\n继续保存将创建新的基准并替换损坏的主文件。\n是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply is not QMessageBox.StandardButton.Yes:
                self.statusBar().showMessage("已取消保存")
                return False

        # --- Persist first; only after success do we publish ---
        try:
            import uuid

            baseline_path = default_path()
            # Generate identity exactly once — on the very first save.
            baseline_id = self._baseline_id or uuid.uuid4().hex
            save_baseline_to(baseline_path, new_items, baseline_id)
        except UnsupportedBaselineSchemaError:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self,
                "基准版本不兼容",
                "现有基准文件由不兼容的较新版本创建，本版本不会覆盖该文件。\n"
                "请使用兼容版本打开，或先人工备份/移走该文件后再保存。",
            )
            self.statusBar().showMessage("基准版本不兼容 — 未保存")
            return False
        except (OSError, ValueError) as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self,
                "基准保存失败",
                f"磁盘写入错误：{exc}\n\n旧基准和核查结果未受影响。",
            )
            self.statusBar().showMessage("基准保存失败 — 未变更")
            return False

        # --- Publish: mutate snapshot + invalidate stale results ---
        self.set_check_items(new_items, baseline_id)
        # A successful save installs a new primary: recovery/first-launch
        # conditions end here and the window operates from a normal baseline.
        if self._baseline_load_state in ("backup", "load-error", "no-baseline"):
            self._baseline_load_state = "normal"
            self.clear_baseline_banner()
        self.statusBar().showMessage("检查基准已变更 — 请重新核查以生成新结果")
        return True

    def set_check_items(
        self,
        items: tuple[CheckItem, ...],
        baseline_id: str = "",
    ) -> None:
        """Publish a new baseline snapshot and invalidate existing results.

        Called after a successful save (T5.8) or after startup load (T5.7).
        Increments the op generation so any in-flight verification workers
        are discarded on completion. Clears results + detail view but keeps
        the document and current state (READY if a document exists, EMPTY
        otherwise).
        """
        self._op_generation += 1
        self._check_items = items
        if baseline_id:
            self._baseline_id = baseline_id
        self._results = ()
        self._result_list.clear()
        self._detail_view.clear()
        if self._document is not None:
            self._state = UiState.READY
        else:
            self._state = UiState.EMPTY
        self._update_actions()

    def _on_verification_finished(self, outcome: VerificationOutcome, generation: int) -> bool:
        """Apply a verification outcome only if it is still current.

        Stale outcomes (wrong generation or a document that is no longer
        current) are discarded. A cancelled run never carries results.
        """
        self._finish_operation(generation)
        if self._close_requested or generation != self._op_generation:
            return False
        if self._document is None or outcome.document_id != self._document.document_id:
            return False
        self._progress.setVisible(False)
        if outcome.state is VerificationState.CANCELLED:
            self.cancel_verification()
        elif outcome.state is VerificationState.COMPLETED:
            self.complete_verification(generation, outcome.results)
        else:  # VerificationState.FAILED
            self.fail_verification("verification failed")
        return True

    def _on_worker_failed(self, category: str, detail: str, generation: int) -> bool:
        """Handle an unexpected worker exception; never shows partial results."""
        self._finish_operation(generation)
        if self._close_requested or generation != self._op_generation:
            return False
        self._progress.setVisible(False)
        if category == "import-error":
            self._state = UiState.FAILED
            self._document = None
            self._results = ()
            self._summary_label.setText("导入失败：出现意外错误")
            self._detail_view.setHtml(f"<p>无法读取所选文件：{html.escape(detail)}</p>")
            self.statusBar().showMessage("导入失败")
            self._update_actions()
        else:
            self.fail_verification(detail)
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
        self._detail_view.setHtml(format_blocks_html(document))
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
        self._detail_view.setHtml(
            f"<p>无法读取所选文件（原因：{html.escape(failure.reason)}）。</p>"
            f"<p>{html.escape(failure.detail)}</p>"
        )
        self.statusBar().showMessage(f"导入失败：{failure.filename}")
        self._update_actions()
