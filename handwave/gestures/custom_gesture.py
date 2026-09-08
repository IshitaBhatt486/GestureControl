"""Static custom gestures: recording quality control, a lightweight nearest-
centroid matcher, and conflict detection — all built on the same normalized
finger-extension representation the built-in recognizer already uses.

Scope for this implementation (documented limitation): only **static** custom
gestures are supported end to end. The data model below (``GestureFrame``,
``GestureSample``) already carries per-frame timestamps and centroids so that
motion and two-hand gestures can be added later without changing the storage
format or the built-in/custom coexistence path, but no motion- or two-hand-
specific matching is implemented yet.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from statistics import pstdev
from typing import Any

from handwave.gestures.hand_landmark_data import HandLandmarkData

FINGERS: tuple[str, ...] = ("thumb", "index", "middle", "ring", "pinky")

MIN_SAMPLE_DURATION = 0.2
MAX_SAMPLE_DURATION = 3.0
MAX_TRAJECTORY_MOTION = 0.12
MAX_POSE_VARIANCE = 0.16
MIN_DETECTED_FRACTION = 0.8

MIN_TOLERANCE = 0.05
MAX_TOLERANCE = 0.6
TOLERANCE_MARGIN = 1.3

DEFAULT_CONFLICT_THRESHOLD = 0.18


def extension_vector(landmarks: HandLandmarkData) -> tuple[float, ...]:
    """The same finger-extension scores the built-in recognizer already computes."""
    scores = landmarks.get_finger_extension_scores()
    return tuple(scores[finger] for finger in FINGERS)


def builtin_prototype_vectors() -> dict[str, tuple[float, ...]]:
    """Approximate continuous prototypes for the built-in categorical gesture patterns."""
    from handwave.gestures.gesture_engine import GestureEngine

    return {
        name: tuple(1.0 if pattern[finger] == "extended" else 0.0 for finger in FINGERS)
        for name, pattern in GestureEngine.GESTURE_PATTERNS.items()
    }


def _distance(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


@dataclass(frozen=True)
class GestureFrame:
    """One recorded frame; the unit both quality control and matching build on."""

    timestamp: float
    hand_count: int
    extension_scores: tuple[float, ...] = ()
    centroid: tuple[float, float] | None = None
    handedness: str | None = None

    def __post_init__(self) -> None:
        if self.hand_count < 0:
            raise ValueError("hand_count cannot be negative")
        if self.hand_count > 0 and len(self.extension_scores) != len(FINGERS):
            raise ValueError(f"extension_scores must have {len(FINGERS)} values when a hand is detected")

    @classmethod
    def from_landmarks(cls, timestamp: float, landmarks: HandLandmarkData | None, hand_count: int = 1) -> "GestureFrame":
        if landmarks is None:
            return cls(timestamp=timestamp, hand_count=0)
        return cls(
            timestamp=timestamp,
            hand_count=hand_count,
            extension_scores=extension_vector(landmarks),
            centroid=landmarks.get_centroid(),
        )


@dataclass(frozen=True)
class GestureSample:
    """One repetition of the gesture recorded under one lighting condition."""

    frames: tuple[GestureFrame, ...]
    lighting: str = "normal"

    def __post_init__(self) -> None:
        if self.lighting not in {"bright", "normal", "dim"}:
            raise ValueError("lighting must be 'bright', 'normal', or 'dim'")

    @property
    def duration(self) -> float:
        if len(self.frames) < 2:
            return 0.0
        return self.frames[-1].timestamp - self.frames[0].timestamp

    @property
    def detected_frames(self) -> tuple[GestureFrame, ...]:
        return tuple(frame for frame in self.frames if frame.hand_count >= 1)

    @property
    def representative_scores(self) -> tuple[float, ...] | None:
        detected = self.detected_frames
        if not detected:
            return None
        return tuple(
            sum(frame.extension_scores[i] for frame in detected) / len(detected)
            for i in range(len(FINGERS))
        )


@dataclass(frozen=True)
class SampleQuality:
    accepted: bool
    reason: str | None = None


def evaluate_sample(sample: GestureSample) -> SampleQuality:
    """Reject samples that would make a poor training example for a static gesture."""
    if not sample.frames:
        return SampleQuality(False, "hand not detected")

    detected = sample.detected_frames
    detected_fraction = len(detected) / len(sample.frames)
    if detected_fraction == 0:
        return SampleQuality(False, "hand not detected")
    if detected_fraction < MIN_DETECTED_FRACTION:
        return SampleQuality(False, "too much tracking loss")

    duration = sample.duration
    if duration < MIN_SAMPLE_DURATION:
        return SampleQuality(False, "gesture too short")
    if duration > MAX_SAMPLE_DURATION:
        return SampleQuality(False, "gesture too long")

    centroids = [frame.centroid for frame in detected if frame.centroid is not None]
    if len(centroids) >= 2:
        origin = centroids[0]
        motion = max(_distance((x, y, 0), (origin[0], origin[1], 0)) for x, y in centroids)
        if motion > MAX_TRAJECTORY_MOTION:
            return SampleQuality(False, "inconsistent trajectory")

    if len(detected) >= 2:
        per_finger = list(zip(*(frame.extension_scores for frame in detected)))
        variance = max(pstdev(values) for values in per_finger)
        if variance > MAX_POSE_VARIANCE:
            return SampleQuality(False, "major variation")

    return SampleQuality(True, None)


def compute_representative_gesture(samples: list[GestureSample]) -> tuple[tuple[float, ...], float]:
    """Average accepted samples into a centroid, and derive an acceptable-variation tolerance."""
    vectors = [sample.representative_scores for sample in samples if sample.representative_scores is not None]
    if not vectors:
        raise ValueError("At least one accepted sample is required to build a gesture")
    centroid = tuple(sum(v[i] for v in vectors) / len(vectors) for i in range(len(FINGERS)))
    if len(vectors) == 1:
        tolerance = MIN_TOLERANCE
    else:
        max_distance = max(_distance(v, centroid) for v in vectors)
        tolerance = min(MAX_TOLERANCE, max(MIN_TOLERANCE, max_distance * TOLERANCE_MARGIN))
    return centroid, tolerance


@dataclass(frozen=True)
class ConflictWarning:
    name: str
    distance: float


def detect_conflicts(
    candidate_scores: tuple[float, ...],
    existing_custom: list["CustomGestureDefinition"],
    threshold: float = DEFAULT_CONFLICT_THRESHOLD,
) -> list[ConflictWarning]:
    """Compare a candidate gesture against built-in prototypes and existing custom gestures."""
    warnings: list[ConflictWarning] = []
    for name, prototype in builtin_prototype_vectors().items():
        distance = _distance(candidate_scores, prototype)
        if distance <= threshold:
            warnings.append(ConflictWarning(name, distance))
    for definition in existing_custom:
        distance = _distance(candidate_scores, definition.representative_scores)
        if distance <= threshold:
            warnings.append(ConflictWarning(definition.name, distance))
    return sorted(warnings, key=lambda warning: warning.distance)


@dataclass(frozen=True)
class GestureDetection:
    name: str = "Unknown"
    confidence: float = 0.0


@dataclass(frozen=True)
class CustomGestureDefinition:
    """A validated, serializable static custom gesture recognition parameter set."""

    gesture_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    representative_scores: tuple[float, ...] = ()
    tolerance: float = MIN_TOLERANCE
    enabled: bool = True
    sample_count: int = 0
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not isinstance(self.gesture_id, str) or not self.gesture_id:
            raise ValueError("gesture_id must be a non-empty string")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Custom gesture name must be non-empty")
        if len(self.representative_scores) != len(FINGERS):
            raise ValueError(f"representative_scores must have {len(FINGERS)} values")
        if any(not 0.0 <= value <= 1.0 for value in self.representative_scores):
            raise ValueError("representative_scores values must be between 0 and 1")
        if not MIN_TOLERANCE <= float(self.tolerance) <= MAX_TOLERANCE:
            raise ValueError(f"tolerance must be between {MIN_TOLERANCE} and {MAX_TOLERANCE}")
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        if self.sample_count < 0:
            raise ValueError("sample_count cannot be negative")
        object.__setattr__(self, "representative_scores", tuple(float(v) for v in self.representative_scores))
        object.__setattr__(self, "tolerance", float(self.tolerance))

    def to_dict(self) -> dict[str, Any]:
        return {
            "gesture_id": self.gesture_id,
            "name": self.name,
            "representative_scores": list(self.representative_scores),
            "tolerance": self.tolerance,
            "enabled": self.enabled,
            "sample_count": self.sample_count,
            "created_at": self.created_at,
        }

    @classmethod
    def from_data(cls, data: object) -> "CustomGestureDefinition":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValueError("Custom gesture configuration must be an object")
        allowed = set(cls.__dataclass_fields__)
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"Unknown custom gesture fields: {', '.join(sorted(unknown))}")
        kwargs = dict(data)
        if "representative_scores" in kwargs:
            kwargs["representative_scores"] = tuple(kwargs["representative_scores"])
        return cls(**kwargs)


class CustomGestureMatcher:
    """Nearest-centroid classifier over enabled custom gesture definitions."""

    def __init__(self, definitions: list[CustomGestureDefinition]) -> None:
        self._definitions = [definition for definition in definitions if definition.enabled]

    def match(self, scores: tuple[float, ...]) -> GestureDetection:
        best: tuple[CustomGestureDefinition, float] | None = None
        for definition in self._definitions:
            distance = _distance(scores, definition.representative_scores)
            if distance > definition.tolerance:
                continue
            if best is None or distance < best[1]:
                best = (definition, distance)
        if best is None:
            return GestureDetection()
        definition, distance = best
        confidence = max(0.0, 1.0 - distance / definition.tolerance)
        return GestureDetection(definition.name, confidence)


def combine_detections(builtin: GestureDetection, custom: GestureDetection) -> GestureDetection:
    """Merge built-in and custom results: built-in wins whenever it recognizes anything.

    Rationale: built-in gestures are deterministic and validated across the whole
    user base, so they take priority over a per-user custom gesture whenever both
    would otherwise fire for the same pose. Custom gestures only fill in poses the
    built-in recognizer treats as "Unknown".
    """
    if builtin.name != "Unknown":
        return builtin
    return custom
