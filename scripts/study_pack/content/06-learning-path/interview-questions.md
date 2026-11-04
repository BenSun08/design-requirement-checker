# Interview questions: explain a decision with evidence

Use this rubric: name the concrete problem, trace the relevant function, state
the invariant, and describe a test that would catch the dangerous failure.
Avoid claiming historical accuracy or deployment readiness from synthetic tests.

<details><summary>Walk through a DOCX import without freezing the GUI.</summary><p>Cover _start_import, QObject.moveToThread, thread.started, application.import_document, byte fingerprinting, adapter conversion, immutable Document, finished signal, generation guard and exact-thread cleanup. Explain that parsing is off-thread and import cancellation is not implemented.</p></details>

<details><summary>How do you make a deterministic matcher explainable?</summary><p>Use a conservative normalization allowlist, raw offset mapping, explicit detection phrases/aliases, bounded requirement spans, retained evidence and independent result dimensions. Cite normalize, map_span, _associate_candidates and _classify plus independently written expected outcomes.</p></details>

<details><summary>Design a regression test for stale imports.</summary><p>Block A on an Event; start and finish B; confirm B is current while A remains owned; release A; wait for A's actual finished signal and ownership cleanup; assert B still remains. Always release blocking fakes in finally so failure paths cannot hang teardown.</p></details>

<details><summary>Explain the persistence failure after backup succeeds but primary replacement fails.</summary><p>The old primary remains intact because it was copied, not moved. Backup may now be a valid copy of that old primary. The new temporary file is cleaned up when possible, the UI reports failure and does not publish the candidate. Test the exact replacement phase rather than blanket-mocking every file operation.</p></details>

<details><summary>Why isn't difflib evidence of fuzzy requirement matching?</summary><p>SequenceMatcher is used by MainWindow to highlight textual differences for review. The production matching engine does not import it and uses approved deterministic rules. Presentation similarity cannot alter CheckStatus or Resolution.</p></details>

<details><summary>What does green Windows CI prove, and what remains unknown?</summary><p>It proves the checks that actually ran against source in the CI environment. It does not prove clean-machine, standard-user, offline company deployment, endpoint-policy behavior, DPI/IME behavior or historical business accuracy. Those need their own recorded evidence.</p></details>

References: [[src/design_requirement_checker/ui/main_window.py::_description_diff_html]],
[[tests/test_ui.py]], [[tests/test_baseline_store.py]], [[docs/tasks.md]].
Return to [Start Here](start-here.html) to revisit any weak explanation.
