# Startup: compose before entering the event loop

![Startup](../assets/startup.svg)

[[src/design_requirement_checker/__main__.py::main]] creates or reuses a
`QApplication` and rejects a non-widget application instance. It sets the
application name and applies local styling before asking the store for its
per-user path. Baseline loading is synchronous here; “never blocks startup”
in the source comment means failure does not prevent a window from opening,
not that disk I/O is asynchronous.

`load_baseline_from` returns items, identity, source and an optional error.
The window receives empty items after a failed load, but retains the explicit
failure token. `apply_baseline_load` maps `primary` to normal operation,
`backup` to a recovery banner, `no-baseline` to ordinary first use,
and incompatible/corrupt data to distinct visible failure conditions.
It does not infer failure by counting items or parsing error strings.

Finally `show()` makes the window visible and `app.exec()` runs Qt's event
loop. The entry point returns that exit code.

References: [[src/design_requirement_checker/ui/main_window.py::MainWindow.apply_baseline_load]],
[[tests/test_startup.py]]. Next: [DOCX import](docx-import.html).
