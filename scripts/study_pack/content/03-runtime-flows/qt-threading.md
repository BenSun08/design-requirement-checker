# Qt worker ownership and signal handoff

![Thread lifecycle](../assets/qt-threading.svg)

A `QThread` object controls an operating-system thread; the `QObject` worker
is moved to it so its `run` work can execute off the GUI thread. Widgets remain
owned by the GUI thread. Workers emit values instead of mutating widgets.

`_wire_worker` records three ownership relationships: all active threads,
generation → thread, and thread → worker. Keeping just the mutable “current
worker” pointer is insufficient: an old operation can still be retiring after
a new one starts. The maps preserve the exact objects until termination.

Worker terminal signals also connect to `thread.quit` with DirectConnection,
which is safe because `quit` is thread-safe. `thread.finished` arranges deferred
deletions and calls `_on_thread_finished` for that captured thread. This
callback calls `thread.wait()` **after finished was emitted** to join the final
termination tail, then releases ownership. It is not the prohibited blocking
wait for running work inside `closeEvent`; it remains an unbounded API call
whose safety relies on receiving the terminal signal first.

Generation checks protect logical freshness. Ownership maps protect object
lifetime. Neither substitutes for the other.

References: [[src/design_requirement_checker/ui/main_window.py::MainWindow._wire_worker]],
[[src/design_requirement_checker/ui/main_window.py::MainWindow._on_thread_finished]],
[[tests/test_ui.py]]. Next: [shutdown](shutdown.html).
