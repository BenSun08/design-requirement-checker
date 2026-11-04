# Shutdown: defer close while work is still running

![Shutdown](../assets/shutdown.svg)

`closeEvent` marks closing intent, sets the verification cancellation Event and
requests event-loop quit on every owned thread. If any is still running it
ignores the close and returns to Qt. It does not spin `processEvents`, terminate
a thread forcibly, or block waiting for an import to finish.

An import already executing Python code is unaffected by `quit()` until that
call returns. Verification can stop at its next matching checkpoint. Terminal
callbacks reject UI publication while `_close_requested` is true, but still
clean up their own operation.

When the last owned thread is retired, `_on_thread_finished` schedules
`QTimer.singleShot(0, self.close)`. This queues another close attempt instead of
recursively closing within the signal callback. With no running threads the
next `closeEvent` accepts. The practical limitation is that an indefinitely
blocked importer can delay window closure; no forceful-kill guarantee exists.

References: [[src/design_requirement_checker/ui/main_window.py::MainWindow.closeEvent]],
[[src/design_requirement_checker/ui/main_window.py::MainWindow._finish_operation]],
[[tests/test_ui.py]]. Next: [Qt concepts](../05-concepts/qt-threading.html).
