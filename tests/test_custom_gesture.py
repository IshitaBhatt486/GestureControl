import pytest

from handwave.gestures.custom_gesture import (
    CustomGestureDefinition,
    CustomGestureMatcher,
    GestureFrame,
    GestureSample,
    builtin_prototype_vectors,
    combine_detections,
    compute_representative_gesture,
    detect_conflicts,
    evaluate_sample,
    extension_vector,
)
from handwave.gestures.gesture_engine import GestureDetection
from handwave.gestures.hand_landmark_data import HandLandmarkData


class FakeLandmark:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


def _open_palm_landmarks() -> HandLandmarkData:
    """Fully-extended pose using the same joint geometry as test_gesture_recognition."""
    points = [FakeLandmark(0.5, 0.9) for _ in range(21)]
    points[2:5] = [FakeLandmark(0.42, 0.72), FakeLandmark(0.30, 0.60), FakeLandmark(0.18, 0.48)]
    for offset, x in zip((5, 9, 13, 17), (0.35, 0.45, 0.55, 0.65)):
        points[offset : offset + 4] = [
            FakeLandmark(x, 0.72), FakeLandmark(x, 0.57), FakeLandmark(x, 0.42), FakeLandmark(x, 0.27)
        ]
    return HandLandmarkData(points)


def _sample(scores_per_frame, lighting="normal", start=0.0, step=0.05, hand_count=1) -> GestureSample:
    frames = tuple(
        GestureFrame(
            timestamp=start + step * i,
            hand_count=hand_count,
            extension_scores=tuple(scores) if hand_count else (),
            centroid=(0.5, 0.5),
        )
        for i, scores in enumerate(scores_per_frame)
    )
    return GestureSample(frames=frames, lighting=lighting)


def test_extension_vector_matches_open_palm_pattern():
    vector = extension_vector(_open_palm_landmarks())
    assert len(vector) == 5
    assert all(0.0 <= value <= 1.0 for value in vector)


def test_evaluate_sample_accepts_stable_pose():
    sample = _sample([[1.0, 1.0, 1.0, 1.0, 1.0]] * 6)
    result = evaluate_sample(sample)
    assert result.accepted is True
    assert result.reason is None


def test_evaluate_sample_rejects_no_hand_detected():
    sample = _sample([[]] * 5, hand_count=0)
    result = evaluate_sample(sample)
    assert result.accepted is False
    assert result.reason == "hand not detected"


def test_evaluate_sample_rejects_tracking_loss():
    frames = tuple(
        GestureFrame(timestamp=0.05 * i, hand_count=(1 if i % 2 == 0 else 0), extension_scores=(1.0,) * 5 if i % 2 == 0 else ())
        for i in range(10)
    )
    result = evaluate_sample(GestureSample(frames=frames))
    assert result.accepted is False
    assert result.reason == "too much tracking loss"


def test_evaluate_sample_rejects_too_short():
    sample = _sample([[1.0] * 5, [1.0] * 5], step=0.05)
    result = evaluate_sample(sample)
    assert result.accepted is False
    assert result.reason == "gesture too short"


def test_evaluate_sample_rejects_too_long():
    sample = _sample([[1.0] * 5] * 6, step=1.0)
    result = evaluate_sample(sample)
    assert result.accepted is False
    assert result.reason == "gesture too long"


def test_evaluate_sample_rejects_inconsistent_trajectory():
    frames = tuple(
        GestureFrame(timestamp=0.05 * i, hand_count=1, extension_scores=(1.0,) * 5, centroid=(0.5 + 0.05 * i, 0.5))
        for i in range(6)
    )
    result = evaluate_sample(GestureSample(frames=frames))
    assert result.accepted is False
    assert result.reason == "inconsistent trajectory"


def test_evaluate_sample_rejects_major_variation():
    scores = [[1.0, 1.0, 1.0, 1.0, 1.0], [0.0, 1.0, 1.0, 1.0, 1.0]] * 3
    result = evaluate_sample(_sample(scores))
    assert result.accepted is False
    assert result.reason == "major variation"


def test_compute_representative_gesture_from_multiple_samples():
    samples = [
        _sample([[1.0, 0.0, 0.0, 0.0, 0.0]] * 6, lighting="bright"),
        _sample([[0.95, 0.05, 0.0, 0.0, 0.0]] * 6, lighting="dim"),
    ]
    centroid, tolerance = compute_representative_gesture(samples)
    assert len(centroid) == 5
    assert 0.05 <= tolerance <= 0.6


def test_compute_representative_gesture_requires_at_least_one_sample():
    with pytest.raises(ValueError):
        compute_representative_gesture([])


def test_custom_gesture_definition_validates_fields():
    with pytest.raises(ValueError):
        CustomGestureDefinition(name="", representative_scores=(0.5,) * 5)
    with pytest.raises(ValueError):
        CustomGestureDefinition(name="X", representative_scores=(0.5,) * 4)
    with pytest.raises(ValueError):
        CustomGestureDefinition(name="X", representative_scores=(1.5,) * 5)
    with pytest.raises(ValueError):
        CustomGestureDefinition(name="X", representative_scores=(0.5,) * 5, tolerance=0.0)


def test_custom_gesture_definition_round_trips_through_dict():
    definition = CustomGestureDefinition(name="Salute", representative_scores=(1.0, 0.0, 0.0, 0.0, 0.0), tolerance=0.2)
    restored = CustomGestureDefinition.from_data(definition.to_dict())
    assert restored == definition


def test_from_data_rejects_unknown_fields():
    with pytest.raises(ValueError):
        CustomGestureDefinition.from_data({"name": "X", "representative_scores": [0.5] * 5, "bogus": True})


def test_matcher_recognizes_within_tolerance_and_rejects_outside():
    definition = CustomGestureDefinition(name="Salute", representative_scores=(1.0, 0.0, 0.0, 0.0, 0.0), tolerance=0.2)
    matcher = CustomGestureMatcher([definition])

    close = matcher.match((0.95, 0.05, 0.0, 0.0, 0.0))
    assert close.name == "Salute"
    assert close.confidence > 0.0

    far = matcher.match((0.0, 1.0, 1.0, 1.0, 1.0))
    assert far.name == "Unknown"


def test_matcher_ignores_disabled_gestures():
    definition = CustomGestureDefinition(
        name="Salute", representative_scores=(1.0, 0.0, 0.0, 0.0, 0.0), tolerance=0.2, enabled=False
    )
    matcher = CustomGestureMatcher([definition])
    assert matcher.match((1.0, 0.0, 0.0, 0.0, 0.0)).name == "Unknown"


def test_matcher_picks_nearest_when_multiple_definitions_match():
    near = CustomGestureDefinition(name="Near", representative_scores=(0.9, 0.0, 0.0, 0.0, 0.0), tolerance=0.3)
    far = CustomGestureDefinition(name="Far", representative_scores=(0.5, 0.0, 0.0, 0.0, 0.0), tolerance=0.5)
    matcher = CustomGestureMatcher([far, near])
    assert matcher.match((0.9, 0.0, 0.0, 0.0, 0.0)).name == "Near"


def test_detect_conflicts_flags_similarity_to_builtin_gesture():
    open_palm_like = (1.0, 1.0, 1.0, 1.0, 1.0)
    warnings = detect_conflicts(open_palm_like, existing_custom=[])
    assert any(w.name == "Open Palm" for w in warnings)


def test_detect_conflicts_flags_similarity_to_existing_custom_gesture():
    existing = CustomGestureDefinition(name="Salute", representative_scores=(1.0, 0.0, 0.0, 0.0, 0.0), tolerance=0.2)
    warnings = detect_conflicts((0.98, 0.02, 0.0, 0.0, 0.0), existing_custom=[existing])
    assert any(w.name == "Salute" for w in warnings)


def test_detect_conflicts_empty_when_sufficiently_distinct():
    warnings = detect_conflicts((0.5, 0.5, 0.5, 0.5, 0.5), existing_custom=[])
    assert warnings == []


def test_builtin_prototype_vectors_cover_all_patterns():
    prototypes = builtin_prototype_vectors()
    assert "Open Palm" in prototypes
    assert prototypes["Open Palm"] == (1.0, 1.0, 1.0, 1.0, 1.0)
    assert prototypes["Fist"] == (0.0, 0.0, 0.0, 0.0, 0.0)


def test_combine_detections_prefers_builtin_when_recognized():
    builtin = GestureDetection("Open Palm", 0.9)
    custom = GestureDetection("Salute", 0.95)
    assert combine_detections(builtin, custom) == builtin


def test_combine_detections_falls_back_to_custom_when_builtin_unknown():
    builtin = GestureDetection("Unknown", 0.0)
    custom = GestureDetection("Salute", 0.8)
    assert combine_detections(builtin, custom) == custom
