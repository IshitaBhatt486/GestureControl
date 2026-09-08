import json

import pytest

from handwave.gestures.hand_landmark_data import HandLandmarkData
from handwave.gestures.hand_state import HandState
from handwave.gestures.landmark_sequence import (
    SCHEMA_VERSION,
    LandmarkFrame,
    LandmarkRecorder,
    LandmarkSequence,
)


class _Point:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


def _hand(handedness=None):
    points = [_Point(0.5, 0.5) for _ in range(21)]
    return HandState(landmarks=HandLandmarkData(points), timestamp=0.0, handedness=handedness)


def test_frame_round_trips_through_dict():
    frame = LandmarkFrame(timestamp=1.5, hands=(_hand("Left"),))
    restored = LandmarkFrame.from_data(frame.to_dict())
    assert restored.timestamp == 1.5
    assert len(restored.hands) == 1
    assert restored.hands[0].handedness == "Left"
    assert len(restored.hands[0].landmarks.get_landmarks()) == 21


def test_frame_rejects_wrong_landmark_count():
    with pytest.raises(ValueError):
        LandmarkFrame.from_data({"timestamp": 0.0, "hands": [{"landmarks": [[0, 0, 0]] * 20}]})


def test_frame_rejects_missing_timestamp():
    with pytest.raises(ValueError):
        LandmarkFrame.from_data({"hands": []})


def test_frame_rejects_unknown_fields():
    with pytest.raises(ValueError):
        LandmarkFrame.from_data({"timestamp": 0.0, "hands": [], "bogus": True})


def test_frame_rejects_non_dict():
    with pytest.raises(ValueError):
        LandmarkFrame.from_data("not a dict")


def test_sequence_round_trips_through_dict_with_metadata():
    sequence = LandmarkSequence(
        frames=(LandmarkFrame(timestamp=0.0, hands=(_hand(),)),),
        metadata={"gesture_name": "Salute"},
    )
    restored = LandmarkSequence.from_data(sequence.to_dict())
    assert len(restored.frames) == 1
    assert restored.metadata["gesture_name"] == "Salute"
    assert "content" in restored.metadata  # never-camera-footage disclaimer preserved


def test_sequence_save_and_load_round_trip(tmp_path):
    path = tmp_path / "sequence.json"
    sequence = LandmarkSequence(frames=(LandmarkFrame(timestamp=0.0, hands=(_hand(),)),))
    sequence.save(path)

    loaded = LandmarkSequence.load(path)
    assert len(loaded.frames) == 1
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == SCHEMA_VERSION


def test_malformed_sequence_missing_frames_key_is_rejected():
    with pytest.raises(ValueError):
        LandmarkSequence.from_data({"schema_version": SCHEMA_VERSION})


def test_malformed_sequence_wrong_schema_version_is_rejected():
    with pytest.raises(ValueError):
        LandmarkSequence.from_data({"schema_version": 999, "frames": []})


def test_malformed_sequence_non_dict_is_rejected():
    with pytest.raises(ValueError):
        LandmarkSequence.from_data("not a dict")


def test_two_hand_sequence_serializes_both_hands():
    frame = LandmarkFrame(timestamp=0.0, hands=(_hand("Left"), _hand("Right")))
    restored = LandmarkFrame.from_data(frame.to_dict())
    assert [hand.handedness for hand in restored.hands] == ["Left", "Right"]


def test_recorder_collects_frames_only_while_recording():
    recorder = LandmarkRecorder(clock=lambda: 1.0)
    recorder.record_frame([_hand()])  # ignored: not recording yet
    recorder.start()
    assert recorder.is_recording
    recorder.record_frame([_hand()], timestamp=0.5)
    recorder.record_frame([_hand()], timestamp=1.0)
    sequence = recorder.stop()

    assert not recorder.is_recording
    assert len(sequence.frames) == 2
    assert sequence.frames[0].timestamp == 0.5


def test_recorder_uses_injected_clock_when_timestamp_omitted():
    recorder = LandmarkRecorder(clock=lambda: 42.0)
    recorder.start()
    recorder.record_frame([_hand()])
    sequence = recorder.stop()
    assert sequence.frames[0].timestamp == 42.0


def test_recorder_metadata_is_attached_to_the_stopped_sequence():
    recorder = LandmarkRecorder()
    recorder.start()
    recorder.record_frame([_hand()], timestamp=0.0)
    sequence = recorder.stop(metadata={"gesture_name": "Wave"})
    assert sequence.metadata["gesture_name"] == "Wave"


def test_starting_a_new_recording_discards_previous_unsaved_frames():
    recorder = LandmarkRecorder()
    recorder.start()
    recorder.record_frame([_hand()], timestamp=0.0)
    recorder.start()  # restart before stop()
    recorder.record_frame([_hand()], timestamp=1.0)
    sequence = recorder.stop()
    assert len(sequence.frames) == 1
    assert sequence.frames[0].timestamp == 1.0
