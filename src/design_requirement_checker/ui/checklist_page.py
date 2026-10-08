"""Checklist management page (T2 shell / Task 5 logic).

Editable baseline workspace, extracted verbatim from the former modal
``ChecklistDialog`` so it can live as a primary application section (the
检查项管理 navigation tab) instead of a modal utility. The page renders the
current snapshot in a ``QTableWidget``, lets the reviewer Add/Edit items via
``ItemEditorDialog``, and hands the updated immutable tuple to a save handler
on 保存基准. The handler (wired by MainWindow) validates and persists; only
when it reports success does this page emit ``saved``. On validation or
persistence failure the page stays open with the candidate rows intact, so an
unsuccessful save never silently discards the reviewer's edits. Save /
persistence / result invalidation live in MainWindow — this page only mutates
its own in-memory working copy. Qt-only: never touches JSON or matching
directly.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from design_requirement_checker.domain import CheckItem
from design_requirement_checker.ui import style

_COLUMN_HEADERS = (
    "编号",
    "功能名称",
    "分类",
    "检测短语",
    "预期要求",
    "状态",
    "操作",
)

#: Column indexes tests and row actions rely on.
_STATUS_COLUMN = 5
_ACTIONS_COLUMN = 6


class ChecklistPage(QWidget):
    """View and manage the current baseline in-memory working copy.

    ``items`` is the immutable snapshot passed from MainWindow on activation.
    ``save_handler`` receives the candidate snapshot when the reviewer
    requests a save; it must return ``True`` only after validation and
    persistence both succeeded — only then is ``saved`` emitted. Without a
    handler (stand-alone use) Save simply emits ``saved``. ``close_requested``
    mirrors the former dialog 关闭 path: it never calls the save handler, so
    the current baseline and results can never change by leaving.
    """

    saved = Signal()
    close_requested = Signal()

    def __init__(
        self,
        items: Sequence[CheckItem],
        parent: QWidget | None = None,
        save_handler: Callable[[tuple[CheckItem, ...]], bool] | None = None,
    ) -> None:
        super().__init__(parent)
        self._items: list[CheckItem] = list(items)
        self._save_handler = save_handler

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 18, 24, 18)
        outer.setSpacing(12)

        # Prototype .management-title — heading + subtitle on the left,
        # the primary 新增检查项 action on the right.
        title_row = QHBoxLayout()
        title_column = QVBoxLayout()
        title_column.setSpacing(2)
        title = QLabel("检查项管理")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSizeF(14)
        title.setFont(title_font)
        subtitle = QLabel("维护核查基准。保存后持久化到本地基准文件。")
        subtitle.setStyleSheet(f"color: {style.MUTED}; font-size: 12px;")
        title_column.addWidget(title)
        title_column.addWidget(subtitle)
        title_row.addLayout(title_column)
        title_row.addStretch()
        self._add_button = QPushButton("新增检查项")
        style.mark_primary(self._add_button)
        self._add_button.clicked.connect(self._on_add)
        title_row.addWidget(self._add_button)
        outer.addLayout(title_row)

        # Prototype .management-note — both sentences are production-true:
        # a baseline change invalidates results; disabled items are excluded
        # from verification.
        notice = QLabel("基准变更后需重新核查。禁用的检查项不计入核查结果。")
        notice.setWordWrap(True)
        notice.setStyleSheet(
            f"background-color: {style.INFO_BG};"
            f"border: 1px solid {style.INFO_BORDER};"
            f"color: {style.TEXT}; padding: 10px 14px;"
        )
        outer.addWidget(notice)

        # Table — prototype column structure (编号/功能名称/分类/预期要求/
        # 状态/操作) plus the production 检测短语 column. 备注 stays in the
        # item editor. Every row carries its own 编辑/禁用|启用/删除 buttons.
        self._table = QTableWidget(len(self._items), len(_COLUMN_HEADERS))
        self._table.setHorizontalHeaderLabels(_COLUMN_HEADERS)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        hdr = self._table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._populate_table()
        self._table.doubleClicked.connect(lambda _index: self._on_edit_selected())
        outer.addWidget(self._table, 1)

        # Footer — production-only: the prototype has no persistence, so it
        # has no save action. 保存基准 runs the handler (validate → persist →
        # publish); 返回文档核查 never saves.
        footer = QHBoxLayout()
        self._count_label = QLabel(f"共 {len(self._items)} 项")
        footer.addWidget(self._count_label)
        footer.addStretch()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存基准")
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("返回文档核查")
        buttons.accepted.connect(self._on_save_requested)
        buttons.rejected.connect(self._on_close_requested)
        footer.addWidget(buttons)
        outer.addLayout(footer)

    # --- working-copy sync ---------------------------------------------------

    def load_items(self, items: Sequence[CheckItem]) -> None:
        """Reset the working copy to a new baseline snapshot.

        Called by MainWindow when the current baseline changed since this
        page was last synced (identity check on the immutable tuple), so a
        re-activation never resurrectes a stale candidate over a saved one.
        """
        self._items = list(items)
        self._refresh_table()

    def _on_save_requested(self) -> None:
        """Handle 保存基准 without discarding the candidate on failure.

        ``saved`` is emitted only when the handler reports a fully successful
        validate+persist cycle. On failure the handler has already shown the
        reason; the candidate rows remain visible and editable. Without a
        handler the page emits ``saved`` directly (stand-alone usage).
        """
        if self._save_handler is None:
            self.saved.emit()
            return
        if self._save_handler(self.current_items()):
            self.saved.emit()

    def _on_close_requested(self) -> None:
        """返回/关闭 without saving — the handler is never touched."""
        self.close_requested.emit()

    def _populate_table(self) -> None:
        """Rebuild all rows (prototype .management table).

        Columns: 编号 | 功能名称 | 分类 | 检测短语 | 预期要求 | 状态 | 操作.
        The 状态 cell keeps the item_id in its UserRole data. Disabled rows
        render muted (prototype .disabled-row). The 操作 cell carries the
        row's own 编辑 / 禁用|启用 / 删除 buttons; the row index captured at
        build time is always in sync because every mutation rebuilds the
        table through :meth:`_refresh_table`.
        """
        self._table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            cells = (
                item.code,
                item.name,
                item.category or "未分类",
                item.detection_phrase,
                item.expected_description or "未设置 · 仅核查名称",
                "启用" if item.enabled else "禁用",
            )
            for column, text in enumerate(cells):
                cell = QTableWidgetItem(text)
                if column == _STATUS_COLUMN:
                    cell.setData(Qt.ItemDataRole.UserRole, item.item_id)
                if not item.enabled:
                    cell.setForeground(QBrush(QColor(style.MUTED)))
                self._table.setItem(row, column, cell)
            self._table.setCellWidget(row, _ACTIONS_COLUMN, self._build_row_actions(row))

    def _build_row_actions(self, row: int) -> QWidget:
        """The per-row 编辑 / 禁用|启用 / 删除 buttons (prototype td buttons)."""
        actions = QWidget()
        layout = QHBoxLayout(actions)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        item = self._items[row]
        small = "padding: 2px 8px; font-size: 12px;"
        edit_button = QPushButton("编辑")
        edit_button.setStyleSheet(small)
        edit_button.clicked.connect(lambda _checked=False, r=row: self._edit_row(r))
        layout.addWidget(edit_button)
        toggle_button = QPushButton("禁用" if item.enabled else "启用")
        toggle_button.setStyleSheet(small)
        toggle_button.clicked.connect(lambda _checked=False, r=row: self._toggle_row(r))
        layout.addWidget(toggle_button)
        delete_button = QPushButton("删除")
        delete_button.setStyleSheet(small)
        delete_button.clicked.connect(lambda _checked=False, r=row: self._delete_row(r))
        layout.addWidget(delete_button)
        return actions

    def _edit_row(self, row: int) -> None:
        if 0 <= row < self._table.rowCount():
            self._table.selectRow(row)
            self._on_edit_selected()

    def _toggle_row(self, row: int) -> None:
        if 0 <= row < self._table.rowCount():
            self._table.selectRow(row)
            self._on_toggle_enabled()

    def _delete_row(self, row: int) -> None:
        if 0 <= row < self._table.rowCount():
            self._table.selectRow(row)
            self._on_delete_selected()

    def _refresh_table(self) -> None:
        self._populate_table()
        self._count_label.setText(f"共 {len(self._items)} 项")

    def current_items(self) -> tuple[CheckItem, ...]:
        """Return the current working snapshot (immutable tuple)."""
        return tuple(self._items)

    # ------------------------------------------------------------------
    # Add / edit
    # ------------------------------------------------------------------

    def _item_at_row(self, row: int) -> CheckItem | None:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    def _selected_row(self) -> int:
        row = self._table.currentRow()
        return row if row >= 0 else -1

    def _on_add(self) -> None:
        from design_requirement_checker.ui.item_editor_dialog import ItemEditorDialog

        dialog = ItemEditorDialog(existing=None, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        candidate = dialog.candidate()
        if candidate is None:
            return
        self._items.append(candidate)
        self._refresh_table()

    def _on_edit_selected(self) -> None:
        row = self._selected_row()
        existing = self._item_at_row(row)
        if existing is None:
            return
        from design_requirement_checker.ui.item_editor_dialog import ItemEditorDialog

        dialog = ItemEditorDialog(existing=existing, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        candidate = dialog.candidate()
        if candidate is None:
            return
        self._items[row] = candidate
        self._refresh_table()

    def _on_toggle_enabled(self) -> None:
        row = self._selected_row()
        existing = self._item_at_row(row)
        if existing is None:
            return
        self._items[row] = CheckItem(
            item_id=existing.item_id,
            code=existing.code,
            name=existing.name,
            detection_phrase=existing.detection_phrase,
            aliases=existing.aliases,
            category=existing.category,
            expected_description=existing.expected_description,
            enabled=not existing.enabled,
            notes=existing.notes,
        )
        self._refresh_table()

    def _on_delete_selected(self) -> None:
        row = self._selected_row()
        existing = self._item_at_row(row)
        if existing is None:
            return
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定删除检查项 “{existing.code} · {existing.name}” 吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply is not QMessageBox.StandardButton.Yes:
            return
        del self._items[row]
        self._refresh_table()
