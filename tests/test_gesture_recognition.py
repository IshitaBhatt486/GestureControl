from types import SimpleNamespace
from unittest.mock import patch

from handwave.gestures.custom_gesture import CustomGestureDefinition, CustomGestureMatcher, extension_vector
from handwave.gestures.gesture_engine import GestureEngine
from handwave.gestures.hand_landmark_data import HandLandmarkData


def _point(x, y):
    return SimpleNamespace(x=x, y=y, z=0.0)


def _pose(extended, thumb_up=False, thumb_down=False, bend=0.04):
    points = [_point(0.5, 0.9) for _ in range(21)]
    if "thumb" in extended:
        if thumb_up:
            points[2:5] = [_point(0.35, 0.72), _point(0.35, 0.52), _point(0.35, 0.30)]
        elif thumb_down:
            points[2:5] = [_point(0.35, 0.60), _point(0.35, 0.72), _point(0.35, 0.84)]
        else:
            points[2:5] = [_point(0.42, 0.72), _point(0.30, 0.60), _point(0.18, 0.48)]
    else:
        points[2:5] = [_point(0.42, 0.72), _point(0.30, 0.72), _point(0.30, 0.82)]

    for name, offset, x in zip(
        ("index", "middle", "ring", "pinky"), (5, 9, 13, 17), (0.35, 0.45, 0.55, 0.65)
    ):
        if name in extended:
            points[offset : offset + 4] = [
                _point(x, 0.72), _point(x, 0.57), _point(x, 0.42), _point(x + bend, 0.27)
            ]
        else:
            points[offset : offset + 4] = [
                _point(x, 0.72), _point(x, 0.58), _point(x + 0.10, 0.58), _point(x + 0.14, 0.68)
            ]
    return HandLandmarkData(points)


def _engine():
    with patch("handwave.gestures.gesture_engine.mp.solutions.hands.Hands"):
        return GestureEngine()


def test_recognizes_all_supported_gestures():
    engine = _engine()
    cases = {
        "Open Palm": _pose({"thumb", "index", "middle", "ring", "pinky"}),
        "Fist": _pose(set()),
        "Thumbs Up": _pose({"thumb"}, thumb_up=True),
        "Thumbs Down": _pose({"thumb"}, thumb_down=True),
        "Peace Sign": _pose({"index", "middle"}),
        "Pointing Up": _pose({"index"}),
    }
    for expected, landmarks in cases.items():
        detection = engine.detect_gesture(landmarks)
        assert detection.name == expected
        assert 0.0 < detection.confidence <= 1.0


def test_unlisted_pattern_and_sideways_thumb_are_unknown():
    engine = _engine()
    assert engine.detect_gesture(_pose({"middle"})).name == "Unknown"
    assert engine.detect_gesture(_pose({"thumb"})).name == "Unknown"
    assert engine.detect_gesture(None).confidence == 0.0


def test_confidence_updates_with_live_joint_geometry():
    engine = _engine()
    straight = engine.detect_gesture(_pose({"index"}, bend=0.0))
    less_straight = engine.detect_gesture(_pose({"index"}, bend=0.04))
    assert straight.name == less_straight.name == "Pointing Up"
    assert straight.confidence != less_straight.confidence


def test_builtin_gesture_wins_over_a_similar_custom_gesture():
    """Built-in gestures must never regress when a custom gesture is registered."""
    open_palm = _pose({"thumb", "index", "middle", "ring", "pinky"})
    conflicting = CustomGestureDefinition(
        name="Copycat", representative_scores=extension_vector(open_palm), tolerance=0.3
    )
    engine = _engine()
    engine.custom_matcher = CustomGestureMatcher([conflicting])

    assert engine.detect_gesture(open_palm).name == "Open Palm"


def test_custom_gesture_fills_in_when_builtin_is_unknown():
    unknown_pose = _pose({"middle"})
    salute = CustomGestureDefinition(
        name="Salute", representative_scores=extension_vector(unknown_pose), tolerance=0.05
    )
    engine = _engine()
    engine.custom_matcher = CustomGestureMatcher([salute])

    detection = engine.detect_gesture(unknown_pose)
    assert detection.name == "Salute"
    assert detection.confidence > 0.0


def test_without_a_custom_matcher_unknown_poses_stay_unknown():
    engine = _engine()
    assert engine.custom_matcher is None
    assert engine.detect_gesture(_pose({"middle"})).name == "Unknown"
