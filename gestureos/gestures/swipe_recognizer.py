"""Velocity and direction based horizontal swipe recognition."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from gestureos.gestures.hand_landmark_data import HandLandmarkData


@dataclass(frozen=True)
class SwipeResult:
    name: str = "Unknown"
    velocity: float = 0.0


class SwipeRecognizer:
    """Recognize intentional horizontal motion from a recent centroid trail."""

    def __init__(
        self,
        min_displacement: float = 0.18,
        min_velocity: float = 0.5,
        min_duration: float = 0.1,
        max_duration: float = 0.7,
        direction_ratio: float = 0.8,
        cooldown: float = 0.6,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.min_displacement = min_displacement
        self.min_velocity = min_velocity
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.direction_ratio = direction_ratio
        self.cooldown = cooldown
        self._clock = clock
        self._history: deque[tuple[float, float, float]] = deque(maxlen=45)
        self._last_swipe_time = float("-inf")

    def update(self, landmarks: HandLandmarkData | None) -> SwipeResult:
        now = self._clock()
        if landmarks is None:
            self.reset()
            return SwipeResult()

        x, y = landmarks.get_centroid()
        self._history.append((now, x, y))
        while self._history and now - self._history[0][0] > self.max_duration:
            self._history.popleft()
        if len(self._history) < 3 or now - self._last_swipe_time < self.cooldown:
            return SwipeResult()

        start_time, start_x, start_y = self._history[0]
        duration = now - start_time
        if duration < self.min_duration:
            return SwipeResult()
        displacement_x = x - start_x
        displacement_y = y - start_y
        velocity = displacement_x / duration
        if (
            abs(displacement_x) < self.min_displacement
            or abs(velocity) < self.min_velocity
            or abs(displacement_x) < 2.0 * abs(displacement_y)
        ):
            return SwipeResult()

        deltas = [
            second[1] - first[1]
            for first, second in zip(self._history, list(self._history)[1:])
            if abs(second[1] - first[1]) >= 0.005
        ]
        direction = 1 if displacement_x > 0 else -1
        consistent = sum(1 for delta in deltas if delta * direction > 0)
        if not deltas or consistent / len(deltas) < self.direction_ratio:
            return SwipeResult()

        name = "Swipe Right" if direction > 0 else "Swipe Left"
        self._last_swipe_time = now
        self._history.clear()
        return SwipeResult(name=name, velocity=abs(velocity))

    def reset(self) -> None:
        self._history.clear()
