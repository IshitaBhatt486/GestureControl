"""Non-blocking handoff from gesture recognition to OS action execution."""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActionCommand:
    """One ordered OS-side effect queued by the recognition pipeline."""

    name: str
    callback: Callable[[], None]


class ActionQueue:
    """Thread-safe FIFO action queue with an explicit drain-and-close boundary."""

    _STOP = object()

    def __init__(self) -> None:
        self._queue: queue.Queue[ActionCommand | object] = queue.Queue()
        self._lock = threading.Lock()
        self._closed = False

    def submit(self, name: str, callback: Callable[[], None]) -> None:
        """Enqueue without waiting for the action to execute."""
        with self._lock:
            if self._closed:
                return
            self._queue.put_nowait(ActionCommand(name, callback))

    def close(self) -> None:
        """Reject new work and place a sentinel after every accepted command."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._queue.put_nowait(self._STOP)

    def next_command(self) -> ActionCommand | None:
        item = self._queue.get()
        return None if item is self._STOP else item


class ActionWorker(QObject):
    """Drain actions on a dedicated thread so OS calls never stall recognition."""

    stopped = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, actions: ActionQueue) -> None:
        super().__init__()
        self.actions = actions

    @pyqtSlot()
    def run(self) -> None:
        try:
            while True:
                command = self.actions.next_command()
                if command is None:
                    break
                try:
                    command.callback()
                    logger.info("Executed queued action %s", command.name)
                except Exception:
                    # Action failures were non-fatal before the queue was introduced.
                    logger.exception("Queued action failed: %s", command.name)
        finally:
            self.stopped.emit()
