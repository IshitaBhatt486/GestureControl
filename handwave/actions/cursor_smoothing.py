"""Low-latency adaptive smoothing for normalized cursor positions."""

from __future__ import annotations

import math


SMOOTHING_PRESETS = {
    # min_cutoff, beta: higher smoothing reduces resting jitter more strongly.
    "low": (3.5, 0.04),
    "medium": (2.0, 0.02),
    "high": (1.0, 0.01),
}


class OneEuroFilter2D:
    """One Euro filter: adaptive cutoff keeps fast intentional motion responsive."""

    def __init__(self, level: str = "medium") -> None:
        if level not in SMOOTHING_PRESETS:
            raise ValueError("Cursor smoothing must be low, medium, or high")
        self.level = level
        self.min_cutoff, self.beta = SMOOTHING_PRESETS[level]
        self._position: tuple[float, float] | None = None
        self._derivative = (0.0, 0.0)
        self._timestamp: float | None = None

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def update(self, x: float, y: float, timestamp: float) -> tuple[float, float]:
        if self._position is None or self._timestamp is None:
            self._position, self._timestamp = (x, y), timestamp
            return self._position
        dt = max(1e-3, timestamp - self._timestamp)
        raw_dx, raw_dy = (x-self._position[0])/dt, (y-self._position[1])/dt
        derivative_alpha = self._alpha(1.0, dt)
        dx = derivative_alpha*raw_dx + (1-derivative_alpha)*self._derivative[0]
        dy = derivative_alpha*raw_dy + (1-derivative_alpha)*self._derivative[1]
        cutoff = self.min_cutoff + self.beta * math.hypot(dx, dy)
        alpha = self._alpha(cutoff, dt)
        self._position = (alpha*x + (1-alpha)*self._position[0], alpha*y + (1-alpha)*self._position[1])
        self._derivative, self._timestamp = (dx, dy), timestamp
        return self._position

    def reset(self) -> None:
        self._position = None; self._derivative = (0.0, 0.0); self._timestamp = None
