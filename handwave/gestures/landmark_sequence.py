"""Local record/replay format for normalized hand landmark sequences.

Records normalized landmark data only — never raw camera frames or video.
Each frame stores exactly what the live recognition pipeline already extracts
from MediaPipe (see ``HandState``/``HandLandmarkData``), so a recorded
sequence can be replayed through the same ``GestureEngine.recognize_hands``
used live.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from handwave.gestures.hand_landmark_data import HandLandmarkData
from handwave.gestures.hand_state import HandState

SCHEMA_VERSION = 1


class _RawPoint:
    """Minimal x/y/z carrier accepted by ``HandLandmarkData.__init__``."""

    __slots__ = ("x", "y", "z")

    def __init__(self, x: float, y: float, z: float) -> None:
        self.x, self.y, self.z = x, y, z


@dataclass(frozen=True)
class LandmarkFrame:
    """One frame's worth of already-extracted, normalized hand data."""

    timestamp: float
    hands: tuple[HandState, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "hands": [
                {
                    "handedness": hand.handedness,
                    "handedness_confidence": hand.handedness_confidence,
                    "landmarks": [[p.x, p.y, p.z] for p in hand.landmarks.get_landmarks()],
                }
                for hand in self.hands
            ],
        }

    @classmethod
    def from_data(cls, data: object) -> "LandmarkFrame":
        if not isinstance(data, dict):
            raise ValueError("Frame data must be an object")
        allowed = {"timestamp", "hands"}
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"Unknown frame fields: {', '.join(sorted(unknown))}")
        if "timestamp" not in data:
            raise ValueError("Frame is missing a timestamp")
        timestamp = float(data["timestamp"])
        raw_hands = data.get("hands", [])
        if not isinstance(raw_hands, list):
            raise ValueError("Frame 'hands' must be a list")
        hands = []
        for raw_hand in raw_hands:
            if not isinstance(raw_hand, dict) or "landmarks" not in raw_hand:
                raise ValueError("Each hand entry needs a 'landmarks' field")
            points = raw_hand["landmarks"]
            if len(points) != 21 or any(len(point) != 3 for point in points):
                raise ValueError("Each hand needs exactly 21 [x, y, z] landmarks")
            landmarks = HandLandmarkData([_RawPoint(p[0], p[1], p[2]) for p in points])
            hands.append(
                HandState(
                    landmarks=landmarks,
                    timestamp=timestamp,
                    handedness=raw_hand.get("handedness"),
                    handedness_confidence=float(raw_hand.get("handedness_confidence", 0.0)),
                )
            )
        return cls(timestamp=timestamp, hands=tuple(hands))


@dataclass(frozen=True)
class LandmarkSequence:
    """A recorded sequence: schema version, metadata, and ordered frames."""

    frames: tuple[LandmarkFrame, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "metadata": {
                "content": "normalized hand landmark data, not camera footage",
                **self.metadata,
            },
            "frames": [frame.to_dict() for frame in self.frames],
        }

    @classmethod
    def from_data(cls, data: object) -> "LandmarkSequence":
        if not isinstance(data, dict):
            raise ValueError("Sequence data must be an object")
        version = data.get("schema_version")
        if version != SCHEMA_VERSION:
            raise ValueError(f"Unsupported landmark sequence schema version: {version!r}")
        raw_frames = data.get("frames")
        if not isinstance(raw_frames, list):
            raise ValueError("Sequence 'frames' must be a list")
        frames = tuple(LandmarkFrame.from_data(item) for item in raw_frames)
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("Sequence 'metadata' must be an object")
        return cls(frames=frames, metadata=metadata)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "LandmarkSequence":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_data(raw)


class LandmarkRecorder:
    """Accumulates frames of already-extracted hand state during a live session."""

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self._frames: list[LandmarkFrame] = []
        self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        self._recording = True
        self._frames = []

    def record_frame(self, hands: list[HandState], timestamp: float | None = None) -> None:
        if not self._recording:
            return
        self._frames.append(
            LandmarkFrame(timestamp=self._clock() if timestamp is None else timestamp, hands=tuple(hands))
        )

    def stop(self, metadata: dict[str, Any] | None = None) -> LandmarkSequence:
        self._recording = False
        sequence = LandmarkSequence(frames=tuple(self._frames), metadata=metadata or {})
        self._frames = []
        return sequence
