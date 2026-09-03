"""Temporal smoothing for frame-by-frame gesture recognition."""

from __future__ import annotations

import time
from collections import Counter, deque
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class FilteredGesture:
    raw_gesture: str
    stable_gesture: str


class GestureFilter:
    """Require a rolling majority to persist before changing stable output."""

    def __init__(
        self,
        persistence_seconds: float = 0.5,
        history_seconds: float = 1.0,
        max_frames: int = 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if persistence_seconds < 0 or history_seconds <= 0 or max_frames <= 0:
            raise ValueError("Gesture filter timing and history limits must be positive")
        self.persistence_seconds = persistence_seconds
        self.history_seconds = history_seconds
        self._clock = clock
        self._history: deque[tuple[float, str]] = deque(maxlen=max_frames)
        self._candidate = "Unknown"
        self._candidate_since: float | None = None
        self._stable = "Unknown"

    def update(self, raw_gesture: str | None) -> FilteredGesture:
        """Add one frame and return its raw and filtered gesture names."""
        now = self._clock()
        raw = raw_gesture or "Unknown"
        self._history.append((now, raw))
        cutoff = now - self.history_seconds
        while self._history and self._history[0][0] < cutoff:
            self._history.popleft()

        votes = Counter(gesture for _, gesture in self._history)
        majority, count = votes.most_common(1)[0]
        if count <= len(self._history) / 2:
            majority = "Unknown"

        if majority != self._candidate:
            self._candidate = majority
            self._candidate_since = now
        elif self._candidate_since is None:
            self._candidate_since = now

        if (
            self._candidate != self._stable
            and self._candidate_since is not None
            and now - self._candidate_since >= self.persistence_seconds
        ):
            self._stable = self._candidate

        return FilteredGesture(raw_gesture=raw, stable_gesture=self._stable)

    def reset(self) -> None:
        """Clear all temporal state, for example when the camera restarts."""
        self._history.clear()
        self._candidate = "Unknown"
        self._candidate_since = None
        self._stable = "Unknown"
