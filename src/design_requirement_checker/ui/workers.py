"""Background workers for import and verification (Task 4).

Workers are QObjects moved to QThreads. They never touch widgets; they call
the application use cases and emit results with the operation generation so
the UI can discard stale outcomes. Cancellation uses a threading.Event that
the matching engine polls through its cancel_check callback.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal


class ImportWorker(QObject):
    """Runs import_document off the UI thread; emits (outcome, generation)."""

    finished = Signal(object, int)

    def __init__(self, path: str | Path, generation: int) -> None:
        super().__init__()
        self._path = path
        self._generation = generation

    def run(self) -> None:
        from design_requirement_checker.application import import_document

        outcome = import_document(self._path)
        self.finished.emit(outcome, self._generation)
