"""Desktop monitor discovery and cursor-target geometry.

This module deliberately does not move the system cursor.  It supplies the
same native-pixel rectangle to calibration previews and to any future cursor
controller, including Windows desktops with negative monitor coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PyQt6.QtGui import QGuiApplication


@dataclass(frozen=True)
class MonitorGeometry:
    identifier: str
    x: int
    y: int
    width: int
    height: int
    primary: bool = False

    def __post_init__(self) -> None:
        if not self.identifier or self.width <= 0 or self.height <= 0:
            raise ValueError("A monitor needs an identifier and positive dimensions")


@dataclass(frozen=True)
class MonitorLayout:
    monitors: tuple[MonitorGeometry, ...]

    @classmethod
    def current(cls) -> "MonitorLayout":
        """Read the active Qt desktop; an app must exist before calling this."""
        app = QGuiApplication.instance()
        if app is None:
            raise RuntimeError("QGuiApplication is required to inspect monitors")
        return cls.from_screens(app.screens())

    @classmethod
    def from_screens(cls, screens: Iterable[object]) -> "MonitorLayout":
        monitors = []
        for index, screen in enumerate(screens):
            geometry = screen.availableGeometry()
            name = screen.name() or f"display-{index + 1}"
            monitors.append(MonitorGeometry(name, geometry.x(), geometry.y(), geometry.width(), geometry.height(), screen == QGuiApplication.primaryScreen()))
        if not monitors:
            raise RuntimeError("No monitors detected")
        if not any(monitor.primary for monitor in monitors):
            monitors[0] = MonitorGeometry(**{**monitors[0].__dict__, "primary": True})
        return cls(tuple(monitors))

    @property
    def primary(self) -> MonitorGeometry:
        return next(monitor for monitor in self.monitors if monitor.primary)

    @property
    def fingerprint(self) -> str:
        return ";".join(f"{m.identifier}:{m.x},{m.y},{m.width},{m.height}" for m in self.monitors)

    def target(self, mode: str, monitor_id: str | None = None) -> MonitorGeometry:
        if mode == "primary":
            if monitor_id:
                selected = next((monitor for monitor in self.monitors if monitor.identifier == monitor_id), None)
                if selected is not None:
                    return selected
            return self.primary
        if mode != "all":
            raise ValueError("Target mode must be primary or all")
        left = min(monitor.x for monitor in self.monitors)
        top = min(monitor.y for monitor in self.monitors)
        right = max(monitor.x + monitor.width for monitor in self.monitors)
        bottom = max(monitor.y + monitor.height for monitor in self.monitors)
        return MonitorGeometry("all-monitors", left, top, right - left, bottom - top)
