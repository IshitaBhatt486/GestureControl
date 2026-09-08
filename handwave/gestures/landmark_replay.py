"""Deterministic replay of a recorded ``LandmarkSequence`` through the exact
same recognition path the live camera pipeline uses.

Deliberately does not reimplement any recognition logic: each frame's hand
states are handed to ``GestureEngine.recognize_hands``, the identical method
``GestureEngine.process`` calls after MediaPipe extraction.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from handwave.gestures.gesture_engine import GestureEngine, GestureResult
from handwave.gestures.landmark_sequence import LandmarkSequence


@dataclass(frozen=True)
class ReplayStep:
    """One replayed frame: how long to wait before it, and its recognition result."""

    frame_index: int
    delay_seconds: float
    result: GestureResult


class LandmarkReplayer:
    """Replays a sequence's frames through ``engine.recognize_hands`` in order."""

    def __init__(self, sequence: LandmarkSequence, engine: GestureEngine, speed: float = 1.0) -> None:
        if speed <= 0:
            raise ValueError("speed must be positive")
        self.sequence = sequence
        self.engine = engine
        self.speed = speed

    def steps(self) -> Iterator[ReplayStep]:
        """Yield each frame's recognition result with the wait time before it.

        The first frame has zero delay; subsequent delays are the recorded
        inter-frame gap divided by ``speed`` (so speed=2 plays twice as fast).
        """
        previous_timestamp: float | None = None
        for index, frame in enumerate(self.sequence.frames):
            delay = 0.0 if previous_timestamp is None else max(0.0, frame.timestamp - previous_timestamp) / self.speed
            previous_timestamp = frame.timestamp
            result = self.engine.recognize_hands(list(frame.hands))
            yield ReplayStep(frame_index=index, delay_seconds=delay, result=result)
