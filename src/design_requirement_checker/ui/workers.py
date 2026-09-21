"""Background workers for import and verification (Task 4).

Workers are QObjects moved to QThreads. They never touch widgets; they call
the application use cases and emit results with the operation generation so
the UI can discard stale outcomes. Cancellation uses a threading.Event that
the matching engine polls through its cancel_check callback.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from design_requirement_checker.domain import CheckItem, Document


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


class VerificationWorker(QObject):
    """Runs verify_document off the UI thread; emits (outcome, generation).

    ``cancel_event`` is set by the UI to request cancellation; the matching
    engine polls it through the cancel_check callback.
    """

    finished = Signal(object, int)

    def __init__(
        self,
        document: Document,
        check_items: Sequence[CheckItem],
        cancel_event: threading.Event,
        generation: int,
    ) -> None:
        super().__init__()
        self._document = document
        self._check_items = check_items
        self._cancel_event = cancel_event
        self._generation = generation

    def run(self) -> None:
        from design_requirement_checker.application import verify_document

        outcome = verify_document(
            self._document,
            self._check_items,
            cancel_check=self._cancel_event.is_set,
        )
        self.finished.emit(outcome, self._generation)
