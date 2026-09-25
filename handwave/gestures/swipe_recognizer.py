"""Classify deliberate finger and open-hand directional swipes."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from handwave.gestures.hand_landmark_data import HandLandmarkData


@dataclass(frozen=True)
class SwipeResult:
    """A motion classification with its physical source, not just a name.

    A ``finger`` swipe is the index-fingertip trajectory while index is the
    only extended finger. A ``hand`` swipe is the centroid trajectory while
    all five fingers are extended. These definitions are intentionally part of
    the result so diagnostics and arbitration do not infer meaning from a
    display name.
    """

    name: str = "Unknown"
    velocity: float = 0.0
    source: str = "none"
    axis: str = "none"

    @property
    def diagnostic(self) -> str:
        return {
            "finger": "Finger: index-tip trajectory, pointing pose",
            "hand": "Hand: centroid trajectory, open-palm pose",
            "none": "None",
        }[self.source]


class SwipeRecognizer:
    """Recognize directional motion with pose-qualified finger/hand sources."""

    def __init__(
        self,
        min_displacement: float = 0.12,
        min_velocity: float = 0.4,
        min_duration: float = 0.08,
        max_duration: float = 0.9,
        direction_ratio: float = 0.65,
        cooldown: float = 0.35,
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
        self._source = "none"

    def update(self, landmarks: HandLandmarkData | None) -> SwipeResult:
        now = self._clock()
        source, point = self._motion_point(landmarks)
        if point is None:
            self.reset()
            return SwipeResult()
        if source != self._source:
            self._history.clear()
            self._source = source
        x, y = point
        self._history.append((now, x, y))
        while self._history and now - self._history[0][0] > self.max_duration:
            self._history.popleft()
        if len(self._history) < 3 or now - self._last_swipe_time < self.cooldown:
            return SwipeResult(source=source)

        start_time, start_x, start_y = self._history[0]
        duration = now - start_time
        if duration < self.min_duration:
            return SwipeResult(source=source)
        dx, dy = x - start_x, y - start_y
        axis, displacement = self._dominant_axis(dx, dy)
        velocity = displacement / duration
        if abs(displacement) < self.min_displacement or abs(velocity) < self.min_velocity:
            return SwipeResult(source=source, axis=axis)
        if not self._is_consistent(axis, 1 if displacement > 0 else -1):
            return SwipeResult(source=source, axis=axis)

        direction = self._direction(axis, displacement)
        prefix = "Finger Swipe" if source == "finger" else "Hand Swipe"
        name = f"{prefix} {direction}" if axis == "vertical" else f"Swipe {direction}"
        self._last_swipe_time = now
        self._history.clear()
        return SwipeResult(name=name, velocity=abs(velocity), source=source, axis=axis)

    @staticmethod
    def _motion_point(landmarks: HandLandmarkData | None) -> tuple[str, tuple[float, float] | None]:
        if landmarks is None:
            return "none", None
        states = landmarks.get_finger_states()
        if states["index"] == "extended" and all(states[finger] == "folded" for finger in ("middle", "ring", "pinky")):
            tip = landmarks.get_landmarks()[8]
            return "finger", (tip.x, tip.y)
        if all(states[finger] == "extended" for finger in ("index", "middle", "ring", "pinky")):
            return "hand", landmarks.get_centroid()
        return "none", None

    @staticmethod
    def _dominant_axis(dx: float, dy: float) -> tuple[str, float]:
        if abs(dx) >= 2.0 * abs(dy):
            return "horizontal", dx
        if abs(dy) >= 2.0 * abs(dx):
            return "vertical", dy
        return "diagonal", 0.0

    def _is_consistent(self, axis: str, direction: int) -> bool:
        if axis not in {"horizontal", "vertical"}:
            return False
        coordinate = 1 if axis == "horizontal" else 2
        deltas = [
            second[coordinate] - first[coordinate]
            for first, second in zip(self._history, list(self._history)[1:])
            if abs(second[coordinate] - first[coordinate]) >= 0.005
        ]
        return bool(deltas) and sum(delta * direction > 0 for delta in deltas) / len(deltas) >= self.direction_ratio

    @staticmethod
    def _direction(axis: str, displacement: float) -> str:
        if axis == "horizontal":
            return "Right" if displacement > 0 else "Left"
        return "Down" if displacement > 0 else "Up"

    def reset(self) -> None:
        self._history.clear()
        self._source = "none"
