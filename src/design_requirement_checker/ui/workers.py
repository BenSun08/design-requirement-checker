"""Background workers for import and verification (Task 4).

Workers are QObjects moved to QThreads. They never touch widgets; they call
the application use cases and emit results with the operation generation so
the UI can discard stale outcomes. Cancellation uses a threading.Event that
the matching engine polls through its cancel_check callback.

Every ``run`` terminates through exactly one terminal signal:

* ``finished`` for the normal outcome (Document/ImportFailure or
  VerificationOutcome), and
* ``failed`` for unexpected exceptions raised by the application use case.

An expected ``ImportFailure`` is the normal import outcome and therefore
travels on ``finished``; it is never converted into a worker failure.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from design_requirement_checker.domain import CheckItem, Document


class ImportWorker(QObject):
    """Runs import_document off the UI thread.

    Emits ``(outcome, generation)`` on success and ``(category, detail,
    generation)`` on an unexpected exception.
    """

    finished = Signal(object, int)
    failed = Signal(str, str, int)

    def __init__(self, path: str | Path, generation: int) -> None:
        super().__init__()
        self._path = path
        self._generation = generation

    def run(self) -> None:
        from design_requirement_checker.application import import_document

        try:
            outcome = import_document(self._path)
        except Exception as exc:  # noqa: BLE001 - surface unexpected errors to UI
            self.failed.emit("import-error", str(exc), self._generation)
            return
        self.finished.emit(outcome, self._generation)


class VerificationWorker(QObject):
    """Runs verify_document off the UI thread.

    ``cancel_event`` is set by the UI to request cancellation; the matching
    engine polls it through the cancel_check callback. Cancellation is
    reported through the normal ``finished`` path as
    ``VerificationState.CANCELLED``, never through ``failed``.
    """

    finished = Signal(object, int)
    failed = Signal(str, str, int)

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

        try:
            outcome = verify_document(
                self._document,
                self._check_items,
                cancel_check=self._cancel_event.is_set,
            )
        except Exception as exc:  # noqa: BLE001 - surface unexpected errors to UI
            self.failed.emit("verification-error", str(exc), self._generation)
            return
        self.finished.emit(outcome, self._generation)
