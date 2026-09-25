"""A non-interactive glass marker for HandWave's mapped cursor position."""

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import QPoint, QTimer, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class CursorAssistState(str, Enum):
    IDLE = "idle"
    TRACKING = "tracking"
    GESTURE_DETECTED = "gesture_detected"
    CLICK_READY = "click_ready"
    CALIBRATION = "calibration"


@dataclass(frozen=True)
class CursorAssistMetrics:
    """One-second rolling cost estimate for the overlay only."""
    update_fps: float = 0.0
    render_fps: float = 0.0
    paint_cpu_percent: float = 0.0
    framebuffer_kb: float = 0.0
    last_paint_ms: float = 0.0
    coalesced_updates: int = 0


class CursorAssistOverlay(QWidget):
    """Coalesced 60 FPS, click-through indicator; it never moves the OS cursor."""

    FRAME_INTERVAL_MS = 1000 // 60

    def __init__(self, size: int = 22, opacity: float = 0.72) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        super().__init__(None, flags)
        self._diameter = self._validated_size(size)
        self._opacity = self._validated_opacity(opacity)
        self._pending_position: QPoint | None = None
        self._last_position: QPoint | None = None
        self._state = CursorAssistState.IDLE
        self._pulse_phase = 0.0
        self._metric_started = time.perf_counter()
        self._metric_update_count = self._metric_render_count = self._metric_coalesced = 0
        self._metric_paint_seconds = self._last_paint_ms = 0.0
        self._metrics = CursorAssistMetrics(framebuffer_kb=(self._diameter * self._diameter * 4) / 1024.0)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(self._diameter, self._diameter)
        self.setWindowOpacity(self._opacity)
        self.setAccessibleName("HandWave cursor assist indicator")
        self._frame_timer = QTimer(self)
        self._frame_timer.setInterval(self.FRAME_INTERVAL_MS)
        self._frame_timer.timeout.connect(self._tick)

    @staticmethod
    def _validated_size(value: int) -> int:
        if not 18 <= value <= 24:
            raise ValueError("Cursor assist size must be between 18 and 24 pixels")
        return value

    @staticmethod
    def _validated_opacity(value: float) -> float:
        if not 0.2 <= value <= 1.0:
            raise ValueError("Cursor assist opacity must be between 0.2 and 1.0")
        return value

    def configure(self, *, size: int | None = None, opacity: float | None = None) -> None:
        if size is not None:
            self._diameter = self._validated_size(size)
            self.setFixedSize(self._diameter, self._diameter)
        if opacity is not None:
            self._opacity = self._validated_opacity(opacity)
            self.setWindowOpacity(self._opacity)
        self.update()

    def metrics(self) -> CursorAssistMetrics:
        self._refresh_metrics()
        return self._metrics

    def _framebuffer_kb(self) -> float:
        return (self.width() * self.height() * 4) / 1024.0

    def _refresh_metrics(self) -> None:
        elapsed = time.perf_counter() - self._metric_started
        if elapsed < 1.0:
            return
        self._metrics = CursorAssistMetrics(
            update_fps=self._metric_update_count / elapsed,
            render_fps=self._metric_render_count / elapsed,
            paint_cpu_percent=(self._metric_paint_seconds / elapsed) * 100.0 / max(os.cpu_count() or 1, 1),
            framebuffer_kb=self._framebuffer_kb(),
            last_paint_ms=self._last_paint_ms,
            coalesced_updates=self._metric_coalesced,
        )
        self._metric_started = time.perf_counter()
        self._metric_update_count = self._metric_render_count = self._metric_coalesced = 0
        self._metric_paint_seconds = 0.0

    def update_position(self, global_x: int, global_y: int) -> None:
        """Queue a global desktop coordinate; visual movement is frame-capped."""
        if self._pending_position is not None:
            self._metric_coalesced += 1
        self._metric_update_count += 1
        self._pending_position = QPoint(int(global_x), int(global_y))
        if not self._frame_timer.isActive():
            self._frame_timer.start()
        if not self.isVisible():
            self.show()
            self._tick()

    @property
    def state(self) -> CursorAssistState:
        return self._state

    def set_state(self, state: CursorAssistState | str) -> None:
        """Set a visual-only state; invalid state names are rejected early."""
        self._state = CursorAssistState(state)
        self._pulse_phase = 0.0
        if self._state == CursorAssistState.GESTURE_DETECTED and not self._frame_timer.isActive():
            self._frame_timer.start()
        self.update()

    def hide_overlay(self) -> None:
        self._frame_timer.stop()
        self._pending_position = None
        self.hide()

    def show_overlay(self) -> None:
        """Restore the last marker without activating the overlay window."""
        if self._last_position is not None and not self.isVisible():
            self.show()

    def _tick(self) -> None:
        moved = self._paint_latest_position()
        if self._state == CursorAssistState.GESTURE_DETECTED:
            self._pulse_phase = (self._pulse_phase + .055) % 1.0
            self.update()
        elif not moved and self._pending_position is None:
            self._frame_timer.stop()

    def _paint_latest_position(self) -> bool:
        if self._pending_position is None:
            return False
        position, self._pending_position = self._pending_position, None
        if position == self._last_position:
            return False
        radius = self._diameter // 2
        self.move(position.x() - radius, position.y() - radius)
        self._last_position = position
        self.update()
        return True

    def paintEvent(self, event) -> None:  # noqa: N802
        started = time.perf_counter()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        inset = 1
        # Layered translucent fills give a glass appearance without a costly
        # per-frame blur effect or a screenshot/readback of the desktop.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(226, 232, 240, 66))
        painter.drawEllipse(self.rect().adjusted(inset, inset, -inset, -inset))
        painter.setBrush(QColor(255, 255, 255, 38))
        painter.drawEllipse(self.rect().adjusted(4, 3, -7, -8))
        painter.setPen(QPen(QColor(255, 255, 255, 145), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(self.rect().adjusted(inset, inset, -inset, -inset))
        ring_color = QColor(147, 197, 253, 95)
        if self._state == CursorAssistState.TRACKING:
            ring_color = QColor(147, 197, 253, 145)
        elif self._state == CursorAssistState.CLICK_READY:
            ring_color = QColor(110, 231, 183, 175)
        elif self._state == CursorAssistState.CALIBRATION:
            ring_color = QColor(96, 165, 250, 225)
        elif self._state == CursorAssistState.GESTURE_DETECTED:
            pulse = int(105 + 65 * (0.5 + 0.5 * math.sin(self._pulse_phase * math.tau)))
            ring_color = QColor(196, 181, 253, pulse)
            painter.setPen(QPen(ring_color, 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(self.rect().adjusted(-2, -2, 1, 1))
        painter.setPen(QPen(ring_color, 2 if self._state != CursorAssistState.IDLE else 1))
        painter.drawEllipse(self.rect().adjusted(0, 0, -1, -1))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 180))
        center = self.rect().center()
        painter.drawEllipse(center, 2, 2)
        painter.end()
        self._metric_render_count += 1
        self._last_paint_ms = (time.perf_counter() - started) * 1000.0
        self._metric_paint_seconds += self._last_paint_ms / 1000.0
        self._refresh_metrics()
