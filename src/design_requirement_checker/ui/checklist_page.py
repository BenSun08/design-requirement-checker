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

_COLUMN_HEADERS = (
    "编号",
    "名称",
    "类别",
    "检测短语",
    "期望描述",
    "启用",
    "备注",
)


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
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(12)

        header = QLabel("编辑检查基准：新增、修改或调整每项的启用状态后点击“保存基准”以持久化。")
        header.setWordWrap(True)
        outer.addWidget(header)

        # Toolbar
        toolbar = QHBoxLayout()
        self._add_button = QPushButton("新增检查项")
        self._add_button.clicked.connect(self._on_add)
        toolbar.addWidget(self._add_button)
        self._edit_button = QPushButton("编辑")
        self._edit_button.clicked.connect(self._on_edit_selected)
        toolbar.addWidget(self._edit_button)
        self._toggle_button = QPushButton("切换启用/禁用")
        self._toggle_button.clicked.connect(self._on_toggle_enabled)
        toolbar.addWidget(self._toggle_button)
        self._delete_button = QPushButton("删除")
        self._delete_button.clicked.connect(self._on_delete_selected)
        toolbar.addWidget(self._delete_button)
        toolbar.addStretch()
        outer.addLayout(toolbar)

        # Table
        self._table = QTableWidget(len(self._items), len(_COLUMN_HEADERS))
        self._table.setHorizontalHeaderLabels(_COLUMN_HEADERS)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        hdr = self._table.horizontalHeader()
        hdr.setStretchLastSection(True)
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._populate_table()
        self._table.doubleClicked.connect(lambda _index: self._on_edit_selected())
        outer.addWidget(self._table, 1)

        # Footer
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
        self._table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            self._table.setItem(row, 0, QTableWidgetItem(item.code))
            self._table.setItem(row, 1, QTableWidgetItem(item.name))
            self._table.setItem(row, 2, QTableWidgetItem(item.category))
            self._table.setItem(row, 3, QTableWidgetItem(item.detection_phrase))
            self._table.setItem(row, 4, QTableWidgetItem(item.expected_description))
            enabled_text = "启用" if item.enabled else "已禁用"
            cell = QTableWidgetItem(enabled_text)
            cell.setData(Qt.ItemDataRole.UserRole, item.item_id)
            self._table.setItem(row, 5, cell)
            self._table.setItem(row, 6, QTableWidgetItem(item.notes))

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
