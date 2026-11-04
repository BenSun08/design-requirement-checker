# Reading order: follow an input through the implementation

1. [[docs/constitution.md]] and [[docs/spec.md]]: establish the contract before reading algorithms.
2. [[src/design_requirement_checker/domain.py::Document]] and
   [[src/design_requirement_checker/domain.py::CheckResult]]: read fields and invariants.
3. [[src/design_requirement_checker/__main__.py::main]]: see the composition root.
4. [[src/design_requirement_checker/application.py::import_document]] then
   [[src/design_requirement_checker/docx_adapter.py::read_document]]: follow bytes to values.
5. [[src/design_requirement_checker/matching.py::normalize]],
   [[src/design_requirement_checker/matching.py::_associate_candidates]], and
   [[src/design_requirement_checker/matching.py::_classify]]: explain each rule with an example.
6. [[src/design_requirement_checker/application.py::verify_document]]: distinguish run outcome from item status.
7. [[src/design_requirement_checker/ui/main_window.py::MainWindow._wire_worker]] and
   [[src/design_requirement_checker/ui/workers.py::VerificationWorker.run]]: trace signal wiring.
8. [[src/design_requirement_checker/ui/main_window.py::MainWindow._on_verification_finished]] and
   [[src/design_requirement_checker/ui/main_window.py::MainWindow.closeEvent]]: freshness and shutdown.
9. [[src/design_requirement_checker/ui/item_editor_dialog.py::ItemEditorDialog._build_aliases]] and
   [[src/design_requirement_checker/ui/main_window.py::MainWindow._save_baseline_snapshot]]: candidate identity and publication.
10. [[src/design_requirement_checker/baseline_store.py::save_baseline]] and
    [[src/design_requirement_checker/baseline_store.py::load_baseline]]: inspect every failure phase.

At each stop, write down inputs, outputs, one invariant and one failure case.
Then find the corresponding suite in the [repository map](../01-overview/repository-map.html).
Do not try to memorize every UI layout helper before understanding the state transitions.
