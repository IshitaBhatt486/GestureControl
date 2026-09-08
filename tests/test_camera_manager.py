from unittest.mock import MagicMock, patch

import numpy as np
from handwave.config.settings_manager import AppSettings
from handwave.gestures.gesture_engine import GestureResult
from handwave.gestures.two_hand_recognizer import TwoHandDetection
from handwave.vision.camera_manager import CameraManager, CameraWorker, GestureWorker, LatestFrameBuffer


def test_worker_releases_camera(qtbot):
    stop_event = MagicMock()
    stop_event.is_set.side_effect = [False, True]
    capture = MagicMock()
    capture.isOpened.return_value = True
    capture.read.return_value = (True, np.zeros((8, 8, 3), dtype=np.uint8))
    worker = CameraWorker(0, stop_event)

    with patch("handwave.vision.camera_manager.cv2.VideoCapture", return_value=capture):
        worker.run()

    capture.release.assert_called_once()


def test_worker_reports_camera_open_error(qtbot):
    capture = MagicMock()
    capture.isOpened.return_value = False
    worker = CameraWorker(0, MagicMock())

    with patch("handwave.vision.camera_manager.cv2.VideoCapture", return_value=capture):
        with qtbot.waitSignal(worker.error) as signal:
            worker.run()

    assert "Could not open webcam" in signal.args[0]
    capture.release.assert_called_once()


def test_gesture_worker_releases_engine(qtbot):
    stop_event = MagicMock()
    stop_event.is_set.side_effect = [False, True]
    buffer = LatestFrameBuffer()
    buffer.put(np.zeros((8, 8, 3), dtype=np.uint8))
    engine = MagicMock()
    gesture = MagicMock(name="Unknown", landmarks=None)
    gesture.name = "Unknown"
    engine.process.return_value = (np.zeros((8, 8, 3), dtype=np.uint8), gesture)
    worker = GestureWorker(buffer, stop_event, AppSettings(overlay_enabled=False))

    with patch("handwave.gestures.gesture_engine.GestureEngine", return_value=engine):
        worker.run()

    engine.close.assert_called_once()


def test_two_hand_gesture_takes_priority_over_static_gesture_in_arbitration(qtbot):
    stop_event = MagicMock()
    stop_event.is_set.side_effect = [False, True]
    buffer = LatestFrameBuffer()
    buffer.put(np.zeros((8, 8, 3), dtype=np.uint8))
    engine = MagicMock()
    gesture = GestureResult(
        hands_detected=2,
        name="Open Palm",
        landmarks=None,
        two_hand=TwoHandDetection(name="Both Palms Open", confidence=0.9, hands_detected=2),
    )
    engine.process.return_value = (np.zeros((8, 8, 3), dtype=np.uint8), gesture)
    worker = GestureWorker(buffer, stop_event, AppSettings(overlay_enabled=False))
    worker.action_mapper = MagicMock()
    worker.action_mapper.execute.return_value = True

    with patch("handwave.gestures.gesture_engine.GestureEngine", return_value=engine):
        worker.run()

    worker.action_mapper.execute.assert_called_once_with("Both Palms Open")


def test_hands_detected_and_per_hand_poses_reach_pipeline_metrics(qtbot):
    stop_event = MagicMock()
    stop_event.is_set.side_effect = [False, True]
    buffer = LatestFrameBuffer()
    buffer.put(np.zeros((8, 8, 3), dtype=np.uint8))
    engine = MagicMock()
    gesture = GestureResult(
        hands_detected=2,
        name="Unknown",
        landmarks=None,
        two_hand=TwoHandDetection(name="Unknown", hands_detected=2, left_pose="Peace Sign", right_pose="Open Palm"),
    )
    engine.process.return_value = (np.zeros((8, 8, 3), dtype=np.uint8), gesture)
    worker = GestureWorker(buffer, stop_event, AppSettings(overlay_enabled=False))
    metrics = []
    worker.metrics_ready.connect(metrics.append)

    with patch("handwave.gestures.gesture_engine.GestureEngine", return_value=engine):
        worker.run()

    assert metrics[0].hands_detected == 2
    assert metrics[0].left_hand_pose == "Peace Sign"
    assert metrics[0].right_hand_pose == "Open Palm"


def test_apply_profile_settings_updates_running_worker_without_recreating_it():
    manager = CameraManager()
    worker = MagicMock()
    manager._gesture_worker = worker
    profile_settings = AppSettings(gesture_cooldown=2.5)

    manager.apply_profile_settings(profile_settings)

    assert manager.settings is profile_settings
    worker.action_mapper.apply_settings.assert_called_once_with(
        cooldown=2.5,
        gesture_bindings=profile_settings.gesture_bindings,
        enabled_gestures=profile_settings.enabled_gestures,
    )


def test_apply_profile_settings_before_start_only_updates_pending_settings():
    manager = CameraManager()
    profile_settings = AppSettings(gesture_cooldown=3.0)

    manager.apply_profile_settings(profile_settings)  # no gesture worker yet; must not raise

    assert manager.settings is profile_settings


def test_stop_camera_requests_shutdown_without_waiting_on_threads():
    manager = CameraManager()
    manager._capture_thread = MagicMock()
    manager._gesture_thread = MagicMock()
    manager._action_thread = MagicMock()
    manager._buffer = MagicMock()

    manager.stop_camera()

    assert manager._stop_event.is_set()
    manager._buffer.close.assert_called_once_with()
    manager._capture_thread.wait.assert_not_called()
    manager._gesture_thread.wait.assert_not_called()
    manager._action_thread.wait.assert_not_called()
