"""Tracks whether gesture processing is active."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


class ActivationService(QObject):
    changed = pyqtSignal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def activate(self) -> None:
        self._set_active(True)

    def deactivate(self) -> None:
        self._set_active(False)

    def _set_active(self, active: bool) -> None:
        if self._active != active:
            self._active = active
            self.changed.emit(active)

