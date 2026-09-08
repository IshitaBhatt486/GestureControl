"""Explicit, per-hand snapshot used instead of a single global mutable gesture state.

Keeping each detected hand's data in its own immutable ``HandState`` (rather
than overwriting one shared set of variables) is what prevents a second hand
appearing mid-frame from silently corrupting the first hand's pose, and what
lets two-hand gestures be computed as an explicit relationship between two
independent snapshots instead of accidental cross-talk between globals.
"""

from __future__ import annotations

from dataclasses import dataclass

from handwave.gestures.custom_gesture import FINGERS
from handwave.gestures.hand_landmark_data import HandLandmarkData

HANDEDNESS_CONFIDENCE_THRESHOLD = 0.6

_OPEN_PALM_STATES = {finger: "extended" for finger in FINGERS}
_FIST_STATES = {finger: "folded" for finger in FINGERS}


@dataclass(frozen=True)
class HandState:
    """One detected hand's data for a single frame."""

    landmarks: HandLandmarkData
    timestamp: float
    handedness: str | None = None
    handedness_confidence: float = 0.0
    detection_confidence: float = 1.0

    @property
    def centroid(self) -> tuple[float, float]:
        return self.landmarks.get_centroid()

    @property
    def pose(self) -> str:
        """A coarse static pose label used only for two-hand pose agreement."""
        states = self.landmarks.get_finger_states()
        if states == _OPEN_PALM_STATES:
            return "Open Palm"
        if states == _FIST_STATES:
            return "Fist"
        return "Other"

    @classmethod
    def from_mediapipe(
        cls,
        hand_landmarks: object,
        timestamp: float,
        handedness_classification: object | None = None,
    ) -> "HandState":
        landmarks = HandLandmarkData.from_mediapipe(hand_landmarks)
        label: str | None = None
        score = 0.0
        if handedness_classification is not None:
            # MediaPipe's `multi_handedness[i].classification[0]` carries label/score.
            top = handedness_classification.classification[0]
            score = float(top.score)
            if score >= HANDEDNESS_CONFIDENCE_THRESHOLD:
                label = top.label
        return cls(landmarks=landmarks, timestamp=timestamp, handedness=label, handedness_confidence=score)
