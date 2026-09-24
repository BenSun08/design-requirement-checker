"""Single CheckItem editor dialog (Task 5, T5.5).

Used by ChecklistDialog for both Add and Edit flows. Preserves stable
item_id on edit (UUID generated only for truly new items). Alias IDs
survive edit when their text content remains unchanged — new/changed
aliases get a fresh UUID. Validation errors block save; per-field
warnings appear inline but do not block.
"""

from __future__ import annotations

import uuid
from collections import defaultdict, deque
from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)

from design_requirement_checker.domain import CheckItem, CheckItemAlias


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

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Required fields
        self._code_edit = QLineEdit(existing.code if existing else "")
        self._code_edit.setPlaceholderText("必填，例如 SYS-001")
        form.addRow("编号 *", self._code_edit)

        self._name_edit = QLineEdit(existing.name if existing else "")
        self._name_edit.setPlaceholderText("必填，例如 门控制")
        form.addRow("功能名称 *", self._name_edit)

        self._phrase_edit = QLineEdit(existing.detection_phrase if existing else "")
        self._phrase_edit.setPlaceholderText("必填，用于文档内检测")
        form.addRow("检测短语 *", self._phrase_edit)

        self._category_edit = QLineEdit(existing.category if existing else "")
        form.addRow("类别", self._category_edit)

        # Multi-line plain-text editor: real engineering descriptions are
        # long; a single-line QLineEdit forces truncating review and makes
        # pasting/reading multi-paragraph text impractical.
        self._expected_edit = QPlainTextEdit(existing.expected_description if existing else "")
        self._expected_edit.setPlaceholderText("选填，可粘贴多行期望描述")
        self._expected_edit.setMinimumHeight(96)
        form.addRow("期望描述", self._expected_edit)

        self._notes_edit = QLineEdit(existing.notes if existing else "")
        form.addRow("备注", self._notes_edit)

        self._enabled_check = QCheckBox("启用此项")
        self._enabled_check.setChecked(True if existing is None else existing.enabled)
        form.addRow("", self._enabled_check)

        # Aliases — one per line
        alias_text = ""
        if existing:
            alias_text = "\n".join(a.text for a in existing.aliases)
        self._aliases_edit = QTextEdit(alias_text)
        self._aliases_edit.setPlaceholderText("每行一个别名，可留空")
        self._aliases_edit.setMaximumHeight(120)
        form.addRow("别名 (每行一个)", self._aliases_edit)

        self._warning_label = QLabel("")
        self._warning_label.setStyleSheet("color: #856404;")
        self._warning_label.setWordWrap(True)
        form.addRow("", self._warning_label)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self.setLayout(form)

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
            QMessageBox.warning(self, "必填字段缺失", f"请填写：{'、'.join(missing)}")
            return

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
            notes=self._notes_edit.text().strip(),
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
