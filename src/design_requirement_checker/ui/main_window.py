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

import difflib
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
    QStackedWidget,
    QTabBar,
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
from design_requirement_checker.ui import style
from design_requirement_checker.ui.checklist_page import ChecklistPage
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


def _cell_path_text(location: DocumentLocation) -> str:
    """One-based table-cell path of a location, without the paragraph index."""
    cells = [*location.ancestor_path]
    if location.cell is not None:
        cells.append(location.cell)
    return " › ".join(
        f"表{c.table_index + 1} · 行{c.row_index + 1} · 单元格{c.column_index + 1}" for c in cells
    )


def format_location(location: DocumentLocation) -> str:
    """Human-readable one-based location; domain coordinates are zero-based."""
    if location.part == "body":
        return f"正文 · 段{location.paragraph_index + 1}"
    return f"{_cell_path_text(location)} · 段{location.paragraph_index + 1}"


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


def _description_diff_html(expected: str, actual: str) -> str:
    """Presentation-only character-level diff of expected vs actual description.

    Explanation aid for ``ComparisonState.DIFFERENT`` results. It never
    changes comparison semantics — matching already decided DIFFERENT; this
    only shows where the two texts differ. Common text stays plain, text only
    in the expected description is struck through, text only in the actual
    description is highlighted. Uses stdlib ``difflib`` over raw characters
    (Chinese text has no spaces to split on) without any extra normalization
    beyond what matching itself applied.
    """
    matcher = difflib.SequenceMatcher(a=expected, b=actual, autojunk=False)
    pieces: list[str] = []
    for tag, a_start, a_end, b_start, b_end in matcher.get_opcodes():
        if tag == "equal":
            pieces.append(html.escape(expected[a_start:a_end]))
            continue
        if tag in ("delete", "replace"):
            pieces.append(
                f'<span style="color: {style.DIFF_DELETE}; text-decoration: line-through">'
                f"{html.escape(expected[a_start:a_end])}</span>"
            )
        if tag in ("insert", "replace"):
            pieces.append(f"<mark>{html.escape(actual[b_start:b_end])}</mark>")
    return "".join(pieces)


def format_blocks_html(document: Document) -> str:
    """Render document blocks as Qt rich text with strike formatting.

    Consecutive table-cell paragraphs of the same cell are grouped under one
    cell header, and table-cell text is rendered on a tinted background so
    table content is clearly distinguishable from body paragraphs. Every
    paragraph keeps its own line, its own 段 index and its own runs — text is
    never merged across paragraph or cell boundaries (constitution §6). Run
    paragraphs use ``white-space: pre-wrap`` so multiple spaces and tabs from
    the raw block text stay visible (Qt's rich-text engine collapses them in
    plain ``<p>`` elements). The underlying domain text is unchanged.
    """
    if not document.blocks:
        return "<p>文档为空：未发现正文段落或表格内容。</p>"
    parts = [f"<p>{_LEGEND}</p>"]
    blocks = document.blocks
    index = 0
    while index < len(blocks):
        block = blocks[index]
        if block.location.cell is None:
            runs_html = "".join(_format_run_html(run) for run in block.runs) or "（空段落）"
            parts.append(f"<p><b>{html.escape(format_location(block.location))}</b></p>")
            parts.append(f'<p style="white-space: pre-wrap">{runs_html}</p>')
            index += 1
            continue
        # Group consecutive paragraphs of the same table cell (same cell and
        # ancestor path); non-adjacent blocks of one cell are never merged.
        cell_key = (block.location.ancestor_path, block.location.cell)
        group_end = index
        while group_end < len(blocks):
            location = blocks[group_end].location
            if location.cell is None or (location.ancestor_path, location.cell) != cell_key:
                break
            group_end += 1
        parts.append(f"<p><b>{html.escape(_cell_path_text(block.location))}</b></p>")
        for cell_block in blocks[index:group_end]:
            runs_html = "".join(_format_run_html(run) for run in cell_block.runs) or "（空段落）"
            parts.append(
                f'<p style="white-space: pre-wrap; background-color: {style.TABLE_CELL_TINT}">'
                f"<b>段{cell_block.location.paragraph_index + 1}：</b>{runs_html}</p>"
            )
        index = group_end
    return "".join(parts)


#: Explicit UI baseline lifecycle states. These are UI semantics, not
#: persistence provenance tokens.
_BASELINE_LOAD_STATES = (
    "normal",
    "no-baseline",
    "backup",
    "load-error",
    "unsupported-schema",
)

#: Map application-layer ``BaselineLoadResult.source`` tokens onto UI states.
#: Persistence provenance ("primary" / "backup" / "no-baseline" from
#: BaselineLoadSource) plus the application failure tokens ("load-error" /
#: "unsupported-schema") are translated here, at the composition boundary,
#: so the UI never parses strings and "primary" — the ordinary successful
#: case — becomes UI state "normal" instead of being rejected.
_BASELINE_SOURCE_TO_UI_STATE = {
    "primary": "normal",
    "no-baseline": "no-baseline",
    "backup": "backup",
    "load-error": "load-error",
    "unsupported-schema": "unsupported-schema",
}


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
        #: Startup baseline UI lifecycle state — never inferred from banner
        #: text or item counts. Valid values: normal / no-baseline / backup /
        #: load-error / unsupported-schema. Persistence provenance tokens
        #: (e.g. "primary") are mapped to UI states by apply_baseline_load(),
        #: not stored here directly.
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
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())
        root.addWidget(self._build_nav())

        # --- pages: workspace (文档核查) and management (检查项管理) ---
        self._pages = QStackedWidget()
        self._pages.addWidget(self._build_workspace_page())
        self._management_page = ChecklistPage(
            self._check_items, save_handler=self._save_baseline_snapshot
        )
        # Leaving the management section never saves; a fully persisted save
        # is announced via `saved` (publishing already happened in the
        # handler, which ran validation + persistence before returning).
        self._management_page.close_requested.connect(self._on_management_close)
        self._management_page.saved.connect(self._on_management_saved)
        self._pages.addWidget(self._management_page)
        #: Identity of the baseline snapshot the management page last loaded.
        #: A different object (set_check_items installs a new tuple) means
        #: the page's working copy must be re-synced on next activation;
        #: identical object means unsaved candidates survive tab switches.
        self._management_source: tuple[CheckItem, ...] | None = self._check_items
        root.addWidget(self._pages, 1)
        self._nav_tabs.currentChanged.connect(self._on_nav_changed)

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

    # --- shell: header, navigation, pages (prototype parity) ----------------

    def _build_header(self) -> QWidget:
        """Prototype header: DR mark, product name, domain subtitle.

        The prototype's 交互原型/模拟数据 badge is deliberately absent —
        production reads real documents and verifies real requirements.
        """
        header = QWidget()
        header.setObjectName("appHeader")
        header.setStyleSheet(f"background: {style.CARD}; border-bottom: 1px solid {style.BORDER};")
        row = QHBoxLayout(header)
        row.setContentsMargins(24, 12, 24, 12)
        row.setSpacing(style.SPACING_CARD)
        mark = QLabel("DR")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setStyleSheet(
            f"background: {style.PRIMARY}; color: {style.CARD};"
            " font-weight: 700; border-radius: 4px; padding: 10px 8px;"
        )
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("Design Requirement Checker")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSizeF(13.5)
        title.setFont(title_font)
        subtitle = QLabel("设计开发要求核查 · 驱动模块")
        subtitle.setStyleSheet(f"color: {style.MUTED};")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        row.addWidget(mark)
        row.addLayout(titles)
        row.addStretch()
        local_badge = QLabel("本地")
        local_badge.setStyleSheet(
            f"color: {style.MUTED}; border: 1px solid {style.BORDER};"
            f"background: {style.PANEL_HEADING}; border-radius: 3px; padding: 6px 9px;"
        )
        row.addWidget(local_badge)
        return header

    def _build_nav(self) -> QWidget:
        """Prototype nav: 文档核查 / 检查项管理 (N) + local-run note."""
        nav = QWidget()
        nav.setObjectName("appNav")
        nav.setStyleSheet(f"background: {style.CARD}; border-bottom: 1px solid {style.BORDER};")
        row = QHBoxLayout(nav)
        row.setContentsMargins(16, 0, 24, 0)
        row.setSpacing(0)
        self._nav_tabs = QTabBar()
        self._nav_tabs.setExpanding(False)
        self._nav_tabs.setDrawBase(False)
        self._nav_tabs.addTab("文档核查")
        self._nav_tabs.addTab(self._management_tab_text())
        row.addWidget(self._nav_tabs)
        row.addStretch()
        note = QLabel("本地运行 · 不上传文件")
        note.setStyleSheet(f"color: {style.MUTED};")
        row.addWidget(note)
        return nav

    def _management_tab_text(self) -> str:
        """Nav label with the current baseline size (all items counted)."""
        return f"检查项管理 ({len(self._check_items)})"

    def _build_workspace_page(self) -> QWidget:
        """The 文档核查 page: notices, document bar, empty/work areas."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # Persistent startup/recovery banner (backup / load error / schema).
        self._baseline_banner = QLabel("")
        self._baseline_banner.setWordWrap(True)
        self._baseline_banner.setVisible(False)
        layout.addWidget(self._baseline_banner)

        # LIMITED coverage notice — compact card, never buried or hidden.
        self._warnings_label = QLabel("")
        self._warnings_label.setWordWrap(True)
        self._warnings_label.setVisible(False)
        self._warnings_label.setStyleSheet(
            f"background: {style.WARNING_BG}; color: {style.WARNING_TEXT};"
            f"border: 1px solid {style.WARNING_BORDER}; border-radius: 4px; padding: 8px 12px;"
        )
        layout.addWidget(self._warnings_label)

        # --- document bar (prototype document-bar) ---
        bar = QWidget()
        bar.setObjectName("documentBar")
        bar.setStyleSheet(
            f"background: {style.CARD}; border: 1px solid {style.BORDER}; border-radius: 4px;"
        )
        bar_row = QHBoxLayout(bar)
        bar_row.setContentsMargins(16, 12, 16, 12)
        bar_row.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(2)
        caption = QLabel("当前文档")
        caption.setStyleSheet(f"color: {style.MUTED};")
        self._doc_name_label = QLabel("尚未选择文档")
        name_font = self._doc_name_label.font()
        name_font.setBold(True)
        self._doc_name_label.setFont(name_font)
        self._doc_name_label.setWordWrap(True)
        self._doc_state_label = QLabel("等待导入")
        self._doc_state_label.setWordWrap(True)
        self._doc_state_label.setStyleSheet(f"color: {style.MUTED};")
        left.addWidget(caption)
        left.addWidget(self._doc_name_label)
        left.addWidget(self._doc_state_label)
        bar_row.addLayout(left)
        bar_row.addStretch()

        actions = QVBoxLayout()
        actions.setSpacing(style.SPACING)
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(style.SPACING)
        self._import_button = QPushButton("选择 DOCX")
        self._import_button.clicked.connect(self._on_import_clicked)
        buttons_row.addWidget(self._import_button)
        self._run_button = QPushButton("开始核查")
        self._run_button.setEnabled(False)
        style.mark_primary(self._run_button)
        self._run_button.clicked.connect(self._on_run_clicked)
        buttons_row.addWidget(self._run_button)
        self._cancel_button = QPushButton("取消核查")
        self._cancel_button.setEnabled(False)
        self._cancel_button.clicked.connect(self._on_cancel_clicked)
        buttons_row.addWidget(self._cancel_button)
        actions.addLayout(buttons_row)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setVisible(False)
        actions.addWidget(self._progress)
        bar_row.addLayout(actions)
        layout.addWidget(bar)

        # Document info line: filename | fingerprint | coverage | blocks.
        self._summary_label = QLabel("尚未导入文档。")
        self._summary_label.setWordWrap(True)
        self._summary_label.setStyleSheet(f"color: {style.MUTED};")
        self._summary_label.setVisible(False)
        layout.addWidget(self._summary_label)

        # Empty import state vs the review work area.
        self._workspace_stack = QStackedWidget()
        self._workspace_stack.addWidget(self._build_empty_state())
        self._workspace_stack.addWidget(self._build_work_area())
        layout.addWidget(self._workspace_stack, 1)
        return page

    def _build_empty_state(self) -> QWidget:
        """Prototype dropzone look — without drag/drop and without any mock
        使用示例文档 action (production parses the real file)."""
        card = QWidget()
        card.setObjectName("emptyStateCard")
        card.setStyleSheet(
            f"background: {style.CARD}; border: 2px dashed #adbdd0; border-radius: 5px;"
        )
        outer = QVBoxLayout(card)
        outer.setContentsMargins(54, 40, 54, 40)
        outer.setSpacing(10)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        symbol = QLabel("W")
        symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        symbol.setStyleSheet(
            f"background: {style.PRIMARY_LIGHT}; color: {style.PRIMARY};"
            f"border: 1px solid #bfd0e7; padding: 14px 20px;"
            " font-size: 28px; font-weight: 600;"
        )
        outer.addWidget(symbol, 0, Qt.AlignmentFlag.AlignCenter)
        title = QLabel("导入《设计开发要求》")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSizeF(15)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        outer.addWidget(title)
        instruction = QLabel("点击下方按钮选择 .docx 文件（本地解析 · 不上传文件）")
        instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instruction.setWordWrap(True)
        instruction.setStyleSheet(f"color: {style.MUTED};")
        outer.addWidget(instruction)
        self._empty_import_button = QPushButton("选择 DOCX 文件")
        style.mark_primary(self._empty_import_button)
        self._empty_import_button.clicked.connect(self._on_import_clicked)
        outer.addWidget(self._empty_import_button, 0, Qt.AlignmentFlag.AlignCenter)
        self._empty_caption = QLabel()
        self._empty_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_caption.setWordWrap(True)
        self._empty_caption.setStyleSheet(f"color: {style.MUTED}; font-size: 12px;")
        self._empty_caption.setText(self._empty_state_caption())
        outer.addWidget(self._empty_caption)
        return card

    def _empty_state_caption(self) -> str:
        """Honest baseline summary — no mock claims, no result promises."""
        if self._check_items:
            return f"{len(self._check_items)} 个检查项 · 本地核查"
        return "尚未配置检查基准 — 切换到 “检查项管理” 新增"

    def _build_summary_cards(self) -> QWidget:
        """Prototype .summary: one white bar of count cards + orthogonality note.

        检查项总数 = 已配置 + 未配置 + 已划除 + 待人工核查; 描述差异 is
        counted separately and never folded into the total (constitution §5).
        """
        bar = QWidget()
        bar.setObjectName("summaryBar")
        bar.setStyleSheet(f"background: {style.CARD}; border: 1px solid {style.BORDER};")
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(24)
        self._summary_card_values: dict[str, QLabel] = {}
        stats = (
            ("total", "检查项总数", style.TEXT),
            ("configured", "已配置", style.CONFIGURED),
            ("missing", "未配置", style.MISSING),
            ("struck_out", "已划除", style.STRUCK_OUT),
            ("unresolved", "待人工核查", style.UNRESOLVED),
            ("different", "描述差异", style.DIFFERENCE),
        )
        for key, caption_text, color in stats:
            stat = QWidget()
            stat_row = QHBoxLayout(stat)
            stat_row.setContentsMargins(0, 0, 0, 0)
            stat_row.setSpacing(6)
            value = QLabel("0")
            value_font = value.font()
            value_font.setBold(True)
            value_font.setPointSizeF(13)
            value.setFont(value_font)
            value.setStyleSheet(f"color: {color};")
            caption = QLabel(caption_text)
            caption.setStyleSheet(f"color: {style.MUTED};")
            stat_row.addWidget(value)
            stat_row.addWidget(caption)
            row.addWidget(stat)
            self._summary_card_values[key] = value
        row.addStretch()
        note = QLabel("描述差异与配置状态独立统计")
        note.setStyleSheet(f"color: {style.MUTED}; font-size: 12px;")
        row.addWidget(note)
        bar.setVisible(False)
        return bar

    def _build_work_area(self) -> QWidget:
        """Summary cards, filters, search and the result/detail splitter."""
        area = QWidget()
        layout = QVBoxLayout(area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Result summary cards (prototype .summary) — visible with results.
        self._summary_cards_row = self._build_summary_cards()
        layout.addWidget(self._summary_cards_row)

        # Filter buttons + search.
        self._current_filter = "全部"
        self._filter_buttons: dict[str, QPushButton] = {}
        filter_row = QHBoxLayout()
        for name in ("全部", "仅异常", "已配置", "未配置", "已划除", "待人工核查"):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setChecked(name == "全部")
            btn.clicked.connect(lambda _checked=False, n=name: self._set_filter(n))
            self._filter_buttons[name] = btn
            filter_row.addWidget(btn)
        filter_row.addStretch()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索：编号 / 名称 / 类别 / 期望描述")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._populate_results)
        filter_row.addWidget(self._search_input)
        layout.addLayout(filter_row)

        # Result list (left) + detail (right) inside one bordered review
        # card (prototype .workspace-grid). The splitter keeps both panes
        # user-resizable — a production affordance the browser grid lacks.
        self._splitter = QSplitter()
        self._splitter.setObjectName("workspaceGrid")
        list_pane = QWidget()
        list_pane.setObjectName("listPane")
        list_layout = QVBoxLayout(list_pane)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(0)
        pane_heading = QWidget()
        pane_heading.setObjectName("paneHeading")
        heading_row = QHBoxLayout(pane_heading)
        heading_row.setContentsMargins(16, 10, 16, 10)
        pane_title = QLabel("检查项")
        pane_title.setObjectName("paneTitle")
        pane_title.setStyleSheet(f"color: {style.MUTED}; font-size: 12px; font-weight: 600;")
        self._visible_count_label = QLabel("")
        self._visible_count_label.setStyleSheet(f"color: {style.MUTED}; font-size: 12px;")
        heading_row.addWidget(pane_title)
        heading_row.addStretch()
        heading_row.addWidget(self._visible_count_label)
        list_layout.addWidget(pane_heading)
        self._result_list = QListWidget()
        self._result_list.setMinimumWidth(300)
        list_layout.addWidget(self._result_list, 1)

        detail_pane = QWidget()
        detail_layout = QVBoxLayout(detail_pane)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(0)
        self._detail_view = QTextBrowser()
        self._detail_view.setOpenExternalLinks(False)
        self._detail_view.document().setDocumentMargin(20)
        self._detail_view.anchorClicked.connect(self._on_evidence_anchor)
        detail_layout.addWidget(self._detail_view, 1)

        self._splitter.addWidget(list_pane)
        self._splitter.addWidget(detail_pane)
        self._splitter.setStretchFactor(0, 2)
        self._splitter.setStretchFactor(1, 3)
        self._splitter.setSizes((500, 750))
        layout.addWidget(self._splitter, 1)
        self._result_list.currentItemChanged.connect(self._on_result_selected)
        return area

    # --- navigation (prototype: tabs, not a modal utility) -----------------

    def _on_nav_changed(self, index: int) -> None:
        self._pages.setCurrentIndex(index)
        if index == 1:
            self._sync_management_page()

    def _sync_management_page(self) -> None:
        """Re-sync the management working copy only when the baseline moved.

        ``set_check_items`` installs a new immutable tuple, so identity is the
        cheap dirty check: same object → the page may hold unsaved candidates
        that survive tab switches; different object → the working copy is
        stale and must be rebuilt from the current snapshot.
        """
        if self._management_source is not self._check_items:
            self._management_page.load_items(self._check_items)
            self._management_source = self._check_items

    def _on_management_close(self) -> None:
        """返回文档核查 — leaving the section never publishes anything."""
        self._nav_tabs.setCurrentIndex(0)

    def _on_management_saved(self) -> None:
        """A save fully succeeded (handler already published + persisted).

        Mark the page as synced with the just-installed snapshot so the next
        activation keeps it instead of rebuilding the identical tuple.
        """
        self._management_source = self._check_items

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
        self._visible_count_label.setText("")
        self._update_summary()
        self._show_document(document)
        self._update_actions()

    def start_verification(self) -> int:
        """Begin a verification run; returns the operation generation token."""
        self._op_generation += 1
        self._state = UiState.VERIFYING
        self._results = ()
        self._update_summary()
        self._set_doc_state("正在核查…")
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
        self._set_doc_state("核查完成")
        self._update_actions()
        return True

    # --- Baseline startup / recovery UX (Task 5) -------------------------

    def apply_baseline_load(self, source: str, error: str | None = None) -> None:
        """Translate the startup load source into a UI state and show its banner.

        ``source`` is the application-layer ``BaselineLoadResult.source``
        token — persistence provenance (``primary`` / ``backup`` /
        ``no-baseline``) or an application failure token (``load-error`` /
        ``unsupported-schema``) — passed explicitly; the UI never infers the
        condition from error strings or item counts. The token is mapped to
        a UI lifecycle state via ``_BASELINE_SOURCE_TO_UI_STATE``: a
        successful ``primary`` load is the ordinary case and becomes UI
        state ``normal`` with no banner. Unknown tokens still raise
        ``ValueError``.
        """
        if source not in _BASELINE_SOURCE_TO_UI_STATE:
            raise ValueError(f"unknown baseline load source: {source!r}")
        state = _BASELINE_SOURCE_TO_UI_STATE[source]
        self._baseline_load_state = state
        if state == "backup":
            self.set_baseline_recovered(
                "已从备份基准恢复 · 主基准文件不可用 · 建议检查文件系统权限"
            )
        elif state == "load-error":
            self.set_baseline_failure(error or "未知错误")
        elif state == "unsupported-schema":
            self._baseline_banner.setStyleSheet(
                f"background-color: {style.ERROR_BG}; color: {style.ERROR_TEXT}; padding: 6px 10px;"
            )
            self._baseline_banner.setText(
                "当前基准文件由不兼容的较新版本创建。\n"
                "本版本不会覆盖该文件。\n"
                "请使用兼容版本打开，或先人工备份/移走该文件。"
            )
            self._baseline_banner.setVisible(True)
            self.statusBar().showMessage("检查基准不兼容")
        # normal (from "primary") / no-baseline: no banner, ordinary experience.

    def set_baseline_recovered(self, message: str) -> None:
        """Show a persistent warning that the baseline came from backup."""
        self._baseline_banner.setStyleSheet(
            f"background-color: {style.WARNING_BG}; color: {style.WARNING_TEXT}; padding: 6px 10px;"
        )
        self._baseline_banner.setText(message)
        self._baseline_banner.setVisible(True)

    def set_baseline_failure(self, message: str) -> None:
        """Show an explicit compatibility / load failure banner."""
        self._baseline_banner.setStyleSheet(
            f"background-color: {style.ERROR_BG}; color: {style.ERROR_TEXT}; padding: 6px 10px;"
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
        """Rebuild the visible result rows; never recomputes verification.

        Prototype .result-list behavior: the still-visible selection is kept
        when it survives a filter/search change, otherwise the first visible
        row is selected so the detail pane always shows a current result.
        """
        previous = self._result_list.currentItem()
        previous_result = previous.data(Qt.ItemDataRole.UserRole) if previous is not None else None
        self._result_list.clear()
        visible = self._filtered_results()
        self._visible_count_label.setText(f"显示 {len(visible)} / {len(self._results)}")
        if not visible:
            self._result_list.addItem("无匹配结果")
            self._detail_view.setHtml(
                f'<p style="color: {style.MUTED}">没有符合条件的检查项。</p>'
                f'<p style="color: {style.MUTED}">调整筛选或搜索词可重新显示结果。</p>'
            )
            return
        keep_row: int | None = None
        if isinstance(previous_result, CheckResult):
            keep_row = next((i for i, r in enumerate(visible) if r is previous_result), None)
        for result in visible:
            item = result.check_item
            parts = [item.code, item.name, self._status_text(result)]
            if result.comparison_state is ComparisonState.DIFFERENT:
                parts.append(_COMPARISON_LABELS[ComparisonState.DIFFERENT])
            label = " · ".join(parts)
            list_item = QListWidgetItem(label)
            list_item.setData(Qt.ItemDataRole.UserRole, result)
            self._result_list.addItem(list_item)
            row = self._build_result_row(result)
            list_item.setSizeHint(row.sizeHint())
            self._result_list.setItemWidget(list_item, row)
        # Auto-select: keep the still-visible selection, else the first row.
        self._result_list.setCurrentRow(keep_row if keep_row is not None else 0)

    def _build_result_row(self, result: CheckResult) -> QWidget:
        """Prototype .result-row: code·category / bold name / difference hint
        on the left, colored status on the right.

        The QListWidgetItem keeps carrying the same plain text (code · name ·
        status · 描述有差异) for accessibility and keyboard navigation; this
        widget only changes how the row is presented.
        """
        item = result.check_item
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)
        # 3px selection bar (prototype .result-row.selected inset); styled
        # on selection changes via _style_row_selection.
        bar = QWidget()
        bar.setObjectName("selectionBar")
        bar.setFixedWidth(3)
        bar.setStyleSheet("background: transparent;")
        layout.addWidget(bar, 0, Qt.AlignmentFlag.AlignTop)
        left = QVBoxLayout()
        left.setSpacing(2)
        code_text = item.code if not item.category else f"{item.code} · {item.category}"
        code_label = QLabel(code_text)
        code_label.setStyleSheet(f"color: {style.MUTED}; font-size: 11px;")
        name_label = QLabel(item.name)
        name_font = name_label.font()
        name_font.setBold(True)
        name_label.setFont(name_font)
        left.addWidget(code_label)
        left.addWidget(name_label)
        if result.comparison_state is ComparisonState.DIFFERENT:
            diff_label = QLabel(_COMPARISON_LABELS[ComparisonState.DIFFERENT])
            diff_label.setStyleSheet(
                f"color: {style.DIFFERENCE}; font-size: 12px; font-weight: 600;"
            )
            left.addWidget(diff_label)
        layout.addLayout(left, 1)
        status_text = self._status_text(result)
        status_label = QLabel(status_text)
        status_label.setStyleSheet(style.status_badge_style(status_text))
        layout.addWidget(status_label, 0, Qt.AlignmentFlag.AlignTop)
        return row

    def _style_row_selection(
        self, current: QListWidgetItem | None, previous: QListWidgetItem | None
    ) -> None:
        """Move the prototype's blue selection bar between rows (visual only)."""
        for item, selected in ((previous, False), (current, True)):
            if item is None:
                continue
            row = self._result_list.itemWidget(item)
            if row is None:
                continue
            bar = row.findChild(QWidget, "selectionBar")
            if bar is not None:
                bar.setStyleSheet(
                    f"background: {style.PRIMARY};" if selected else "background: transparent;"
                )

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
        self, current: QListWidgetItem | None, previous: QListWidgetItem | None
    ) -> None:
        if self._close_requested or current is None:
            return
        self._style_row_selection(current, previous)
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
        """Render the selected result as the prototype .detail-pane.

        Structure: detail-title (name/code/category + status), metadata line
        (匹配方式 / 证据数 / 描述比较), the two-column .comparison block
        (预期要求 vs 实际内容), an amber diff banner for 描述有差异, the
        comparison/review reason lines, the .evidence section and the
        .context prev/current/next block. Every displayed value still comes
        from the domain result — this method only changes presentation.
        """
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
        status_text = self._status_text(result)
        status_color = style.STATUS_COLORS.get(status_text, style.MUTED)

        # .detail-title — name and code/category on the left, status right.
        code_line = html.escape(item.code)
        if item.category:
            code_line += f" / {html.escape(item.category)}"
        parts: list[str] = [
            '<table width="100%" cellspacing="0" cellpadding="0" border="0"><tr>'
            f'<td valign="top"><h3>{html.escape(item.name)}</h3>'
            f'<p style="color: {style.MUTED}; font-size: 12px">{code_line}</p></td>'
            f'<td width="1" align="right" valign="top">'
            "<p><b>"
            f'<span style="color: {status_color}; font-size: 13px">{status_text}</span>'
            "</b></p>"
            "</td></tr></table>"
        ]

        # .metadata — one muted line; only the pieces that apply to this
        # result (a MISSING result shows neither 匹配方式 nor 证据数).
        meta: list[str] = []
        if match_method:
            meta.append(f"匹配方式 <b>{match_method}</b>")
        if evidence:
            meta.append(f"证据 <b>{len(evidence)} 处</b>")
        meta.append(f"描述比较 <b>{comparison_text}</b>")
        parts.append(f'<p style="color: {style.MUTED}; font-size: 12px">{" · ".join(meta)}</p>')

        # .comparison — expected vs actual side by side.
        expected_cell = (
            f'<p style="color: {style.MUTED}; font-size: 12px"><b>预期要求 · 检查基准</b></p>'
            f"<p>期望描述：{html.escape(item.expected_description)}</p>"
        )
        actual_raw = ""
        if result.comparison_state is ComparisonState.DIFFERENT and selected is not None:
            # DIFFERENT results must explain themselves: the raw readable
            # actual text plus a where-do-they-differ rendering. The raw
            # requirement slice is the source text — never the normalized
            # comparison form (presentation only; matching is unchanged).
            req_start, req_end = selected.requirement_span
            actual_raw = selected.raw_text[req_start:req_end]
            actual_body = f"<p>实际描述：{html.escape(actual_raw)}</p>"
        elif result.status is CheckStatus.MISSING:
            actual_body = (
                "<p>在已检查范围内未找到匹配证据。</p><p>请人工确认文档是否使用了其他表述。</p>"
            )
        elif actual_text:
            if result.status is CheckStatus.STRUCK_OUT:
                actual_body = f"<p>实际需求：<s>{html.escape(actual_text)}</s></p>"
            else:
                actual_body = f"<p>实际需求：{html.escape(actual_text)}</p>"
        else:
            actual_body = "<p>无证据内容可显示。</p>"
        actual_cell = (
            f'<p style="color: {style.MUTED}; font-size: 12px"><b>实际内容 · 检测文档</b></p>'
            f"{actual_body}"
        )
        parts.append(
            '<table width="100%" cellspacing="0" cellpadding="10" border="1"><tr>'
            f'<td width="50%" valign="top">{expected_cell}</td>'
            f'<td width="50%" valign="top" bgcolor="{style.PANEL_TINT}">{actual_cell}</td>'
            "</tr></table>"
        )

        # .diff-banner — where the two descriptions differ, in place.
        if result.comparison_state is ComparisonState.DIFFERENT and selected is not None:
            parts.append(
                '<table width="100%" cellspacing="0" cellpadding="10" border="0"><tr>'
                f'<td bgcolor="{style.WARNING_BG}"><b>差异详情：</b>'
                f"{_description_diff_html(item.expected_description, actual_raw)}"
                "<br>功能已出现但描述不同，请人工核实订单要求。</td></tr></table>"
            )

        if result.comparison_reason:
            reason_text = _COMPARISON_REASON_LABELS.get(
                result.comparison_reason, result.comparison_reason
            )
            parts.append(
                f'<p style="color: {style.MUTED}">比较原因：{html.escape(reason_text)}</p>'
            )
        if result.review_reasons:
            reasons = "".join(
                f"<li>{html.escape(_REASON_LABELS.get(r, r))}</li>" for r in result.review_reasons
            )
            parts.append(f"<p>核查原因：</p><ul>{reasons}</ul>")

        # .evidence — occurrence links, position, and the review caveat.
        parts.append("<p><b>匹配证据</b></p>")
        if result.status is CheckStatus.MISSING:
            parts.append(
                "<p>未配置是检测结果，不代表已确认无需配置。</p>"
                f'<p style="color: {style.MUTED}">没有匹配证据，因此不显示虚构的原文位置。</p>'
            )
        elif evidence:
            if len(evidence) > 1:
                links = " ".join(
                    f'<a href="evidence:{i}">证据 {i + 1}</a>' for i in range(len(evidence))
                )
                parts.append(f"<p>{links}</p>")
            if selected is not None:
                parts.append(f"<p>位置：{html.escape(format_location(selected.location))}</p>")
            parts.append(
                f'<p style="color: {style.MUTED}; font-size: 12px">'
                "匹配方式不等于工程结论，请人工核实。</p>"
            )

        if selected is not None and result.status is not CheckStatus.MISSING:
            parts.append(self._source_context_html(selected))

        self._detail_view.setHtml("".join(parts))

    def _source_context_html(self, evidence: MatchEvidence) -> str:
        """Rebuild the prototype .context block from the current document.

        Three bordered rows — 上一段 (muted), 当前 (tinted, requirement span
        highlighted) and 下一段 (muted) — under a 原文上下文 heading that
        repeats the caveat: this is a reconstructed excerpt, not a Word page
        rendering.
        """
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
        current = blocks[idx]
        parts = [
            "<p><b>原文上下文</b>　"
            f'<span style="color: {style.MUTED}; font-size: 12px">'
            f"{html.escape(format_location(current.location))} · 重建摘录，非 Word 页面</span></p>"
        ]
        rows: list[str] = []
        if idx > 0:
            prev = blocks[idx - 1]
            rows.append(
                f"<td><p"
                f' style="color: {style.MUTED}; font-size: 11px">上一段 · '
                f"{html.escape(format_location(prev.location))}</p>"
                f'<p style="white-space: pre-wrap">'
                f"{_format_block_with_highlight(prev, None)}</p></td>"
            )
        rows.append(
            f'<td bgcolor="{style.CONTEXT_CURRENT}">'
            f'<p style="color: {style.MUTED}; font-size: 11px">当前 · 匹配位置</p>'
            f'<p style="white-space: pre-wrap">'
            f"{_format_block_with_highlight(current, span)}</p></td>"
        )
        if idx < len(blocks) - 1:
            nxt = blocks[idx + 1]
            rows.append(
                f"<td><p"
                f' style="color: {style.MUTED}; font-size: 11px">下一段 · '
                f"{html.escape(format_location(nxt.location))}</p>"
                f'<p style="white-space: pre-wrap">'
                f"{_format_block_with_highlight(nxt, None)}</p></td>"
            )
        parts.append(
            '<table width="100%" cellspacing="0" cellpadding="10" border="1"><tr>'
            + "</tr><tr>".join(rows)
            + "</tr></table>"
        )
        return "".join(parts)

    def _update_summary(self) -> None:
        """Refresh the summary cards; hide them whenever results are cleared.

        Called after every results transition — completion shows current
        counts, and every path that empties ``_results`` (new run,
        cancellation, failure, baseline change, new document, import
        failure) must hide stale counts: a stale background completion may
        never restore them.
        """
        if not self._results:
            self._summary_cards_row.setVisible(False)
            return
        s = self._compute_summary(self._results)
        for key, value in (
            ("total", s.total),
            ("configured", s.configured),
            ("missing", s.missing),
            ("struck_out", s.struck_out),
            ("unresolved", s.unresolved),
            ("different", s.different),
        ):
            self._summary_card_values[key].setText(str(value))
        self._summary_cards_row.setVisible(True)

    def cancel_verification(self) -> None:
        """Mark the run cancelled; results stay empty, never completed."""
        self._state = UiState.CANCELLED
        self._results = ()
        self._update_summary()
        self._set_doc_state("已取消核查 — 可重新核查")
        self._update_actions()

    def fail_verification(self, message: str) -> None:
        """Mark the run failed; results stay empty, never completed."""
        self._state = UiState.FAILED
        self._results = ()
        self._update_summary()
        self._set_doc_state("核查失败")
        self.statusBar().showMessage(f"核查失败：{message}")
        self._update_actions()

    # --- action enablement --------------------------------------------------

    def _update_actions(self) -> None:
        s = self._state
        idle_for_ui = s not in (UiState.IMPORTING, UiState.VERIFYING)
        self._import_button.setEnabled(idle_for_ui)
        self._empty_import_button.setEnabled(idle_for_ui)
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
        # The management section is available whenever no background work is
        # running (same rule the former modal entry button carried).
        self._nav_tabs.setTabEnabled(1, idle_for_ui)
        # Empty import state vs the review work area. A first import keeps
        # the empty card visible (with a busy document bar); an import
        # failure must show its reason in the detail view instead.
        show_empty = self._document is None and s is not UiState.FAILED
        self._workspace_stack.setCurrentIndex(0 if show_empty else 1)

    def _set_doc_state(self, text: str) -> None:
        """Update the document-bar run-state line (导入/核查 lifecycle)."""
        self._doc_state_label.setText(text)

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
        self._update_summary()
        self._progress.setVisible(True)
        self._set_doc_state("正在导入…")
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

        ``QThread.finished`` is emitted just *before* the OS thread terminates,
        so this queued handler can run while the thread is still executing its
        final instructions. Join that remainder here — bounded to microseconds
        because ``finished`` was already emitted, unlike an unbounded
        close-time wait — so an empty ``_active_threads`` guarantees every
        owned thread has fully terminated and is safe to destroy. Releasing a
        still-terminating QThread for destruction fast-fails the whole process
        on Windows (0xC0000409).

        After cleanup, if a deferred close is pending and no threads remain,
        schedule a non-reentrant close retry on the UI event loop.
        """
        thread.wait()
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
        """Activate the checklist management section (nav tab).

        The embedded page keeps its candidate working copy across tab
        switches; it calls into :meth:`_save_baseline_snapshot` on 保存基准
        and publishes only through that handler. Validation errors, declined
        warnings, persistence failures and declined destructive-recovery
        confirmations all leave the candidate intact — a failed save never
        silently discards edits. The current baseline and results are mutated
        only after persistence succeeds. Leaving the section (返回文档核查)
        never saves.
        """
        self._sync_management_page()
        self._nav_tabs.setCurrentIndex(1)

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
        self._nav_tabs.setTabText(1, self._management_tab_text())
        self._empty_caption.setText(self._empty_state_caption())
        self._results = ()
        self._update_summary()
        self._result_list.clear()
        self._visible_count_label.setText("")
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
            self._update_summary()
            self._set_doc_state("导入失败")
            self._summary_label.setText("导入失败：出现意外错误")
            self._summary_label.setVisible(True)
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
        self._doc_name_label.setText(document.filename)
        self._set_doc_state("已导入 · 尚未核查")
        self._summary_label.setText(
            f"文件：{document.filename}｜指纹：{document.content_fingerprint[:12]}…"
            f"｜覆盖范围：{coverage_text}｜文本块：{len(document.blocks)}"
        )
        self._summary_label.setVisible(True)
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
        self._update_summary()
        self._state = UiState.FAILED
        self._set_doc_state("导入失败")
        self._summary_label.setText(f"导入失败：{failure.filename}")
        self._summary_label.setVisible(True)
        self._warnings_label.setText("")
        self._warnings_label.setVisible(False)
        self._detail_view.setHtml(
            f"<p>无法读取所选文件（原因：{html.escape(failure.reason)}）。</p>"
            f"<p>{html.escape(failure.detail)}</p>"
        )
        self.statusBar().showMessage(f"导入失败：{failure.filename}")
        self._update_actions()
