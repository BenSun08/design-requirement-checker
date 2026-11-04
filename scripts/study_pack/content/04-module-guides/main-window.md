# ui/main_window.py — the desktop review coordinator

## Purpose and libraries

`MainWindow(QMainWindow)` owns widgets, state transitions, result selection,
worker lifetime and baseline publication. Qt's event loop owns widget mutations.
`QThread`, `QTimer` and `threading.Event` support background work without moving
UI policy into workers. `difflib.SequenceMatcher` highlights textual changes
for presentation; it is not a fuzzy matcher used to classify requirements.

## Important types and functions

`UiState` controls actions; `ResultSummary` represents displayed counts.
`_start_import`, `_on_run_clicked` and `_wire_worker` launch work.
`_on_import_finished` and `_on_verification_finished` reject stale outcomes.
`_on_thread_finished` retires exact thread/worker ownership. `closeEvent` defers
closure. `_save_baseline_snapshot` persists candidates; `set_check_items`
publishes a new baseline and invalidates results.

## Inputs, outputs and data flow

Inputs include user actions, immutable snapshots and worker terminal signals.
Outputs are visible state, selected evidence, source context and use-case calls.
`_filtered_results` searches cached results; summary totals continue to represent
the entire run. `_source_context_html` reconstructs neighbouring blocks, while
HTML escaping protects display of literal engineering text.

## Important invariants and design reasons

Generation protects freshness; verification also checks document ID. Thread →
worker ownership survives clearing the current-operation pointer. MISSING shows
no invented source context. Coverage notices remain visible while filtering.
Description differences do not become missing items. A baseline save publishes
only after persistence, then increments generation to invalidate late workers.

## Failure modes

A stale callback must clean up its own thread without clearing a newer one.
Dropping the last worker reference before thread retirement risks native crashes.
`quit` stops a thread event loop, not a synchronous parser already running.
The source currently joins the termination tail after `finished`; close itself
does not block. UI imports store path/error types, an existing coupling called
out on the dependency page.

References: [[src/design_requirement_checker/ui/main_window.py::MainWindow]],
[[src/design_requirement_checker/ui/main_window.py::_description_diff_html]], [[tests/test_ui.py]].
Next: [thread lifecycle](../03-runtime-flows/qt-threading.html).
