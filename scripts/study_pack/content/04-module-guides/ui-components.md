# Workers, checklist page and item editor

## Purpose and important types

`ImportWorker(QObject)` and `VerificationWorker(QObject)` isolate application
calls from widgets. `ChecklistPage(QWidget)` maintains an editable candidate
list. `ItemEditorDialog(QDialog)` builds one candidate item. `ui/style.py`
centralizes presentation rather than domain meanings.

## Worker functions, inputs and outputs

Each worker's `run` emits exactly one terminal signal. `finished` carries an
outcome and generation; `failed` carries an unexpected error category, detail
and generation. Expected `ImportFailure` and verification cancellation travel
through `finished`. Verification receives a document, item snapshot and
`threading.Event`; `is_set` is passed as the matching cancellation callback.
Import receives only path and generation and has no cooperative cancellation.
`QObject.moveToThread` happens in MainWindow, before the thread starts.

## Editing data flow

The checklist stores a working list separate from the published tuple.
`load_items` refreshes it from the current snapshot. Add/edit/toggle/delete alter
candidates; delete requires confirmation. `_on_save_requested` invokes the save
handler and emits `saved` only after success. Failure leaves candidate rows
available for correction. Closing the management page does not save implicitly.

The editor's `_on_save` validates required fields and builds `CheckItem`.
Existing item identity survives edits. `_build_aliases` uses per-text queues
(`defaultdict` + `deque`) so unchanged duplicate alias lines preserve their
individual IDs and notes occurrence-by-occurrence. New aliases get UUIDs.
`QPlainTextEdit` supports multiline expected descriptions without rich-text
formatting artifacts; empty expected descriptions are allowed.

## Dependencies, invariants and failure modes

Widgets use PySide6, domain values and a save callback, not OOXML. A successful
dialog acceptance produces a candidate, not durable persistence. Collapsing
identical alias text into a dictionary entry would lose identity. Emitting
`saved` before the handler succeeds would hide a disk failure. A standalone
ChecklistPage with no handler does emit `saved`; production supplies a handler.

References: [[src/design_requirement_checker/ui/workers.py::VerificationWorker.run]],
[[src/design_requirement_checker/ui/checklist_page.py::ChecklistPage._on_save_requested]],
[[src/design_requirement_checker/ui/item_editor_dialog.py::ItemEditorDialog._build_aliases]],
[[tests/test_checklist_ui.py]]. Next: [persistence tutorial](../05-concepts/persistence.html).
