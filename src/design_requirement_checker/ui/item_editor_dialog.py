"""Single CheckItem editor dialog (Task 5, T5.5).

Used by ChecklistPage for both Add and Edit flows. Preserves stable
item_id on edit (UUID generated only for truly new items). Alias IDs
survive edit when their text content remains unchanged — new/changed
aliases get a fresh UUID. Required-field errors appear inline (prototype
``#formError``) and block save.
"""

from __future__ import annotations

import uuid
from collections import defaultdict, deque
from collections.abc import Sequence

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from design_requirement_checker.domain import CheckItem, CheckItemAlias
from design_requirement_checker.ui import style


class ItemEditorDialog(QDialog):
    """Add or edit one CheckItem.

    ``existing`` is ``None`` for Add, a CheckItem for Edit. On successful
    Save, :meth:`candidate` returns the new/modified immutable CheckItem;
    otherwise ``None``.
    """

    def __init__(
        self,
        existing: CheckItem | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._existing = existing
        self._candidate: CheckItem | None = None

        if existing is None:
            self.setWindowTitle("新增检查项")
            self._item_id = uuid.uuid4().hex
        else:
            self.setWindowTitle("编辑检查项")
            self._item_id = existing.item_id  # preserve stable ID

        # Large enough for long engineering descriptions, and resizable so
        # the user can enlarge it for pasting/reading multi-line text.
        self.resize(760, 640)
        self.setMinimumSize(560, 520)

        # Prototype form structure: labels sit above their inputs; 编号 and
        # 分类 share one row (.form-grid). 检测短语 is production-only — it
        # is the phrase the matcher searches for, so the editor must
        # collect it (the prototype matches on the name instead).
        body = QVBoxLayout(self)
        body.setContentsMargins(24, 20, 24, 20)
        body.setSpacing(8)

        self._code_edit = QLineEdit(existing.code if existing else "")
        self._code_edit.setPlaceholderText("必填，例如 SYS-001")
        self._category_edit = QLineEdit(existing.category if existing else "")
        grid = QHBoxLayout()
        grid.setSpacing(15)
        grid.addLayout(self._field("编号 *", self._code_edit), 1)
        grid.addLayout(self._field("分类", self._category_edit), 1)
        body.addLayout(grid)

        self._name_edit = QLineEdit(existing.name if existing else "")
        self._name_edit.setPlaceholderText("必填，例如 门控制")
        body.addLayout(self._field("功能名称 *", self._name_edit))

        self._phrase_edit = QLineEdit(existing.detection_phrase if existing else "")
        self._phrase_edit.setPlaceholderText("必填，用于文档内检测")
        body.addLayout(self._field("检测短语 *", self._phrase_edit))

        # Multi-line plain-text editor: real engineering descriptions are
        # long; a single-line QLineEdit forces truncating review and makes
        # pasting/reading multi-paragraph text impractical.
        self._expected_edit = QPlainTextEdit(existing.expected_description if existing else "")
        self._expected_edit.setPlaceholderText("选填，可粘贴多行期望描述")
        self._expected_edit.setMinimumHeight(96)
        expected_column = self._field("预期要求", self._expected_edit)
        hint = QLabel("留空时仅核查功能是否出现，不比较描述。")
        hint.setStyleSheet(f"color: {style.MUTED}; font-size: 12px;")
        expected_column.addWidget(hint)
        body.addLayout(expected_column, 2)

        # Aliases — one per line
        alias_text = ""
        if existing:
            alias_text = "\n".join(a.text for a in existing.aliases)
        self._aliases_edit = QTextEdit(alias_text)
        self._aliases_edit.setPlaceholderText("每行一个别名，可留空")
        self._aliases_edit.setMaximumHeight(120)
        body.addLayout(self._field("别名（每行一个）", self._aliases_edit), 1)

        # Prototype 备注 is a small textarea — notes can span lines.
        self._notes_edit = QPlainTextEdit(existing.notes if existing else "")
        self._notes_edit.setMaximumHeight(72)
        body.addLayout(self._field("备注", self._notes_edit))

        self._enabled_check = QCheckBox("启用此检查项")
        self._enabled_check.setChecked(True if existing is None else existing.enabled)
        body.addWidget(self._enabled_check)

        # Prototype #formError — inline alert text, empty when there is
        # nothing to report.
        self._error_label = QLabel("")
        self._error_label.setStyleSheet(f"color: {style.ERROR_TEXT};")
        self._error_label.setWordWrap(True)
        body.addWidget(self._error_label)

        # Prototype .dialog-actions — 取消 plus the primary 保存检查项.
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setText("保存检查项")
        style.mark_primary(save_button)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        body.addWidget(buttons)

    @staticmethod
    def _field(label_text: str, field: QWidget) -> QVBoxLayout:
        """One prototype form field: the label above its input."""
        column = QVBoxLayout()
        column.setSpacing(3)
        column.addWidget(QLabel(label_text))
        column.addWidget(field)
        return column

    def candidate(self) -> CheckItem | None:
        return self._candidate

    # ------------------------------------------------------------------
    # Save flow
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        # --- Required field validation (local, not baseline-wide) ---
        missing: list[str] = []
        if not self._code_edit.text().strip():
            missing.append("编号")
        if not self._name_edit.text().strip():
            missing.append("功能名称")
        if not self._phrase_edit.text().strip():
            missing.append("检测短语")
        if missing:
            # Inline alert (prototype #formError) — no modal needed.
            self._error_label.setText(f"请填写：{'、'.join(missing)}")
            return
        self._error_label.setText("")

        # --- Build candidate aliases ---
        raw_aliases = [
            line.strip() for line in self._aliases_edit.toPlainText().splitlines() if line.strip()
        ]
        aliases = self._build_aliases(raw_aliases)

        # --- Build candidate item ---
        self._candidate = CheckItem(
            item_id=self._item_id,
            code=self._code_edit.text().strip(),
            name=self._name_edit.text().strip(),
            detection_phrase=self._phrase_edit.text().strip(),
            aliases=aliases,
            category=self._category_edit.text().strip(),
            expected_description=self._expected_edit.toPlainText().strip(),
            enabled=self._enabled_check.isChecked(),
            notes=self._notes_edit.toPlainText().strip(),
        )
        self.accept()

    def _build_aliases(self, new_texts: Sequence[str]) -> tuple[CheckItemAlias, ...]:
        """Preserve ``alias_id`` *and* ``notes`` for aliases whose text is unchanged.

        A plain edit of ``category`` or ``name`` must never silently drop
        alias metadata — every alias that stays in the editor with the
        same text keeps its existing identity and notes verbatim. New
        alias texts get a fresh ``alias_id`` and empty notes (the UI
        currently does not expose alias-note editing, so ``notes=""``
        is acceptable for genuinely-new aliases).

        Duplicate alias texts are matched occurrence-by-occurrence: the
        editor keeps one line per alias, so the Nth ``"X"`` line maps to
        the Nth existing ``"X"`` alias. ``["X"(id1), "X"(id2)]`` therefore
        survives an edit as two distinct aliases — never collapsed onto
        one object, never silently deduplicated, and never given a
        duplicated ``alias_id``. Removing a line removes that occurrence.
        """
        if self._existing is None:
            return tuple(
                CheckItemAlias(alias_id=uuid.uuid4().hex, text=t, notes="") for t in new_texts
            )

        # text → pending existing aliases in source order; one occurrence
        # is consumed (popleft) per identical editor line, so duplicate
        # texts keep their individual identities and notes.
        existing_by_text: dict[str, deque[CheckItemAlias]] = defaultdict(deque)
        for alias in self._existing.aliases:
            existing_by_text[alias.text].append(alias)

        result: list[CheckItemAlias] = []
        for t in new_texts:
            pending = existing_by_text.get(t)
            if pending:
                result.append(pending.popleft())
            else:
                result.append(CheckItemAlias(alias_id=uuid.uuid4().hex, text=t, notes=""))
        return tuple(result)
