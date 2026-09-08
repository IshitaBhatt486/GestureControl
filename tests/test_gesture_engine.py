from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from handwave.gestures.gesture_engine import GestureEngine


def _landmarks():
    point = SimpleNamespace(x=0.5, y=0.5, z=0.0)
    return SimpleNamespace(landmark=[point] * 21)


def _engine_with_results(results, times=(1.0, 1.04)):
    hands = MagicMock()
    hands.process.side_effect = results
    with patch("handwave.gestures.gesture_engine.mp.solutions.hands.Hands", return_value=hands) as factory:
        engine = GestureEngine(clock=iter(times).__next__)
    return engine, hands, factory


def test_configures_up_to_two_hands_and_draws_green_landmarks_and_connections():
    landmarks = _landmarks()
    engine, _, factory = _engine_with_results(
        [SimpleNamespace(multi_hand_landmarks=[landmarks])], times=(1.0,)
    )
    engine._drawing = MagicMock()
    frame = np.zeros((100, 160, 3), dtype=np.uint8)

    with patch("handwave.gestures.gesture_engine.cv2.putText") as put_text:
        _, result = engine.process(frame)

    assert factory.call_args.kwargs["max_num_hands"] == 2
    assert len(landmarks.landmark) == 21
    engine._drawing.draw_landmarks.assert_called_once_with(
        frame,
        landmarks,
        engine._connections,
        engine.LANDMARK_STYLE,
        engine.CONNECTION_STYLE,
    )
    assert engine.LANDMARK_STYLE.color == (0, 255, 0)
    assert engine.CONNECTION_STYLE.color == (0, 255, 0)
    assert result.hands_detected == 1
    assert put_text.call_args_list[0].args[1] == "Hand detected"


def test_reports_hand_loss_and_recovers_while_updating_fps():
    landmarks = _landmarks()
    engine, _, _ = _engine_with_results(
        [
            SimpleNamespace(multi_hand_landmarks=[landmarks]),
            SimpleNamespace(multi_hand_landmarks=None),
            SimpleNamespace(multi_hand_landmarks=[landmarks]),
        ],
        times=(1.0, 1.04, 1.08),
    )
    engine._drawing = MagicMock()
    frame = np.zeros((100, 160, 3), dtype=np.uint8)

    with patch("handwave.gestures.gesture_engine.cv2.putText") as put_text:
        first = engine.process(frame.copy())[1]
        lost = engine.process(frame.copy())[1]
        recovered = engine.process(frame.copy())[1]

    statuses = [
        call.args[1]
        for call in put_text.call_args_list
        if call.args[1] in {"Hand detected", "No hand detected"}
    ]
    assert statuses == ["Hand detected", "No hand detected", "Hand detected"]
    assert first.fps == 0.0
    assert lost.fps > 20
    assert recovered.hands_detected == 1
    assert recovered.fps > 20
    assert recovered.landmarks is not None
    overlay_text = [call.args[1] for call in put_text.call_args_list]
    assert "Thumb: folded" in overlay_text
    assert "Pinky: folded" in overlay_text


def test_close_releases_mediapipe_resources():
    engine, hands, _ = _engine_with_results([], times=())
    engine.close()
    hands.close.assert_called_once_with()
