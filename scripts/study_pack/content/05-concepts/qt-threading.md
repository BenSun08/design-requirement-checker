# Qt threading: lifetime and freshness are different problems

## GUI thread, QObject and QThread

The GUI thread runs the event loop and owns widgets. A `QThread` controls another
thread; it is not itself the parsing task. The task is a `QObject` worker moved
with `moveToThread`. Connecting `thread.started` to `worker.run` begins the
application call there. Signals carry values back to GUI handlers without worker
code touching `QWidget`s. The project uses Python callables as signal receivers;
not every receiver has an explicit `@Slot` decorator.

## Cooperative cancellation

MainWindow sets a `threading.Event`; VerificationWorker passes `Event.is_set`
to the application; matching polls it before each item/block candidate search.
A requested cancel becomes CANCELLED with no result tuple. `QThread.terminate`
could interrupt arbitrary code while resources are half-updated, so it is not
used. Import does not expose this checkpoint and cannot be cancelled normally.

## Generation tokens

Imagine import A starts, then import B starts and completes. A's late signal
still has A's old token. The GUI rejects it even though its parser succeeded.
Verification additionally checks the document identity. Editing a baseline
increments the generation too: a result for old checklist inputs is stale even
when the document ID matches.

## Ownership and deferred close

The generation → thread map chooses which operation to retire. The thread →
worker map holds its worker strongly until thread termination. Dropping the
current pointer does not free a retiring worker. `finished` triggers retirement,
and the last retirement schedules close via `QTimer.singleShot(0, self.close)`.
Close itself returns to the event loop while running work finishes.

References: [[src/design_requirement_checker/ui/main_window.py::MainWindow._wire_worker]],
[[src/design_requirement_checker/ui/main_window.py::MainWindow._on_verification_finished]],
[[src/design_requirement_checker/ui/workers.py::VerificationWorker]], [[tests/test_ui.py]].
Next: [shutdown trace](../03-runtime-flows/shutdown.html).
