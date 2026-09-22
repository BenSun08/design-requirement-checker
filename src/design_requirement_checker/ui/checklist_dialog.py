"""Checklist management dialog (Task 5).

This slice delivers the shell: a QTableWidget rendering the current baseline
with code/name/category/detection_phrase/expected_description/enabled columns
and a toolbar with Add button. Edit / enable-disable / delete / save flow land
in later T5.x subtasks. The dialog is Qt-only; it talks to MainWindow via a
returned immutable CheckItem tuple, never touches JSON or matching directly.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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


class ChecklistDialog(QDialog):
    """View and manage the current baseline.

    ``items`` is the immutable snapshot passed from MainWindow on open.
    Subtasks T5.5–T5.8 will wire up editing, persistence, and result
    invalidation; this shell only renders. Closing with QDialog.Accepted
    returns the current internal items tuple.
    """

    def __init__(self, items: Sequence[CheckItem], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("检查项管理")
        self.resize(1040, 640)
        self.setMinimumSize(800, 480)

        # Working copy — edited items replace entries by item_id (T5.5).
        self._items: list[CheckItem] = list(items)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(12)

        header = QLabel("检查基准 — 可在后续版本中新增/编辑/删除检查项")
        header.setWordWrap(True)
        outer.addWidget(header)

        # Toolbar
        toolbar = QHBoxLayout()
        self._add_button = QPushButton("新增检查项")
        self._add_button.setEnabled(False)  # T5.5 will wire this
        toolbar.addWidget(self._add_button)
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
        outer.addWidget(self._table, 1)

        # Footer
        footer = QHBoxLayout()
        count = QLabel(f"共 {len(self._items)} 项")
        footer.addWidget(count)
        footer.addStretch()
        self._close_button = QPushButton("关闭")
        self._close_button.clicked.connect(self.reject)
        footer.addWidget(self._close_button)
        outer.addLayout(footer)

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

    def current_items(self) -> tuple[CheckItem, ...]:
        """Return the current working snapshot (immutable tuple)."""
        return tuple(self._items)
