# Save: persist the candidate before publishing it

![Persistence](../assets/baseline-persistence.svg)

Checklist editing produces a candidate tuple. MainWindow validates cross-item
rules and presents warnings before calling `application.save_baseline_to`.
When startup reported `load-error`, MainWindow also requires explicit confirmation
before replacing a damaged primary. That use case validates again at its boundary, then delegates disk work to
`baseline_store.save_baseline`.

The store writes UTF-8 JSON to a same-directory temp-new file, flushes it and
calls `fsync`. If the old primary is valid, it copies it into a separate
temp-backup, flushes/fsyncs that file and atomically installs `.bak`. Only then
does `os.replace` install temp-new as the primary. The old primary is never
moved away first. A corrupt primary is not copied over a recoverable backup.
An unsupported schema raises a distinct error and prevents replacement.

After successful return, `set_check_items` publishes the tuple and invalidates
old results. On failure the candidate remains editable and the old in-memory
snapshot remains current. A final-primary-replace failure may already have
updated `.bak` to a valid copy of the old primary: “failure leaves both files
byte-identical” is **not** a general promise of this algorithm.

References: [[src/design_requirement_checker/ui/main_window.py::MainWindow._save_baseline_snapshot]],
[[src/design_requirement_checker/baseline_store.py::save_baseline]],
[[tests/test_baseline_store.py]]. Next: [persistence tutorial](../05-concepts/persistence.html).
