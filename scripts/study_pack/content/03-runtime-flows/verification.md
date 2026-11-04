# Verification: a completed run is all-or-nothing

![Verification](../assets/verification.svg)

`_on_run_clicked` captures the document and baseline tuple, creates a fresh
`threading.Event` and starts a `VerificationWorker` with the new generation.
The application filters disabled items before invoking `matching.verify`.

For each block the matcher normalizes text, then checks cancellation immediately
before each item's candidate search. It associates candidates only after all
items have been searched in that block. Finally it builds one result for each
input item, retaining all qualifying evidence in stable source order.

Cancellation raises `VerificationCancelled`. The application translates that
to a CANCELLED outcome with **no results**, avoiding a partial report that
looks complete. Unexpected exceptions travel through `worker.failed`.

On success, `_on_verification_finished` checks both generation and document ID
before publishing. A baseline edit increments generation too, so the same
DOCX with a changed baseline cannot accept an old outcome. Filtering/search
then operates on cached results without rerunning matching.

References: [[src/design_requirement_checker/application.py::verify_document]],
[[src/design_requirement_checker/matching.py::verify]],
[[src/design_requirement_checker/ui/main_window.py::MainWindow._on_verification_finished]].
Next: [matching tutorial](../05-concepts/deterministic-matching.html).
