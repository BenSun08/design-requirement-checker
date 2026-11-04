# Focused call and use graphs

These are **Pyan3 static uses graphs restricted to callable symbols**. Edges
include inferred calls and references to functions/classes, sometimes including
type annotations. They are not execution traces, counts, or proof that an edge
runs on every path. Attribute dispatch and Qt signal delivery may be missed.
Each diagram is generated from current source; data fields and constants are
removed to keep it readable.

## Application: choose a use case

![Application calls](call-graph.svg)

`import_document`, `verify_document`, `load_baseline_from` and
`save_baseline_to` are separate entry points. With a module-focused analysis,
external callees may be absent; the dependency graph supplies that wider context.
See [[src/design_requirement_checker/application.py]].

## Matching: collect before classifying

![Matching calls](calls-matching.svg)

Read `verify` → `_collect_candidates` → `_associate_candidates` → `_classify`.
Cross-item association needs all candidates for one block before it can detect
overlap. `normalize` and `map_span` preserve traceability.
See [[src/design_requirement_checker/matching.py::verify]].

## DOCX ingestion: traverse and resolve

![DOCX calls](calls-docx-adapter.svg)

`read_document` invokes body and header/footer collection. Table collection
recurses into nested tables; paragraph collection resolves each run's effective
strike. Follow [[src/design_requirement_checker/docx_adapter.py::read_document]].

## Baseline store: separate load and save

![Store calls](calls-baseline-store.svg)

`load_baseline` attempts primary then backup unless schema incompatibility
must stop recovery. `save_baseline` validates the old primary before copying it
to the backup; `_phase_replace` marks failure-injection points in tests.
See [[src/design_requirement_checker/baseline_store.py::save_baseline]].

## UI worker lifecycle: intentionally selected functions

![UI lifecycle calls](calls-ui-worker.svg)

Only import, verification, cancellation, completion and retirement entry points
are shown. Widget construction, rendering and most helpers are omitted.
The missing causal connection `thread.started → worker.run` is a Qt signal,
not a direct Python call; see the explicit
[thread lifecycle diagram](../03-runtime-flows/qt-threading.html).
All other methods remain available in the [MainWindow guide](../04-module-guides/main-window.html).
