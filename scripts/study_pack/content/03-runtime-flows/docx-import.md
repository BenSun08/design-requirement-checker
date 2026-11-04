# DOCX import: preserve responsiveness and the input snapshot

![Import](../assets/docx-import.svg)

`MainWindow._start_import` increments the operation generation, clears results
and enters IMPORTING. It creates an `ImportWorker` and `QThread`; `_wire_worker`
moves the worker to that thread and connects `started` to `run`.
MainWindow never parses Word packages on the GUI thread.

The worker calls `application.import_document`, which translates `DocxReadError`
into `ImportFailure`. The adapter reads bytes once, computes a SHA-256 identity
and opens the package from those same bytes. It returns frozen domain values,
not live python-docx/lxml objects. A normal `finished` signal carries either
`Document` or expected `ImportFailure`, plus the generation.

The GUI callback retires the correct operation and rejects a completion if the
window is closing or the generation is stale. An older import cannot overwrite
a newer document. Unexpected exceptions use the worker's `failed` signal.
Import has **no cooperative cancel**; asking the thread to quit does not stop
an in-progress parser call. Close must wait asynchronously for it to finish.

References: [[src/design_requirement_checker/ui/main_window.py::MainWindow._start_import]],
[[src/design_requirement_checker/ui/workers.py::ImportWorker.run]],
[[src/design_requirement_checker/docx_adapter.py::read_document]].
Next: [verification](verification.html).
