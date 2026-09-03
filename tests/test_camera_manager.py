from unittest.mock import MagicMock, patch

import numpy as np
from gestureos.config.settings_manager import AppSettings
from gestureos.vision.camera_manager import CameraWorker, GestureWorker, LatestFrameBuffer


def test_worker_releases_camera(qtbot):
    stop_event = MagicMock()
    stop_event.is_set.side_effect = [False, True]
    capture = MagicMock()
    capture.isOpened.return_value = True
    capture.read.return_value = (True, np.zeros((8, 8, 3), dtype=np.uint8))
    worker = CameraWorker(0, stop_event)

    with patch("gestureos.vision.camera_manager.cv2.VideoCapture", return_value=capture):
        worker.run()

    capture.release.assert_called_once()


def test_worker_reports_camera_open_error(qtbot):
    capture = MagicMock()
    capture.isOpened.return_value = False
    worker = CameraWorker(0, MagicMock())

    with patch("gestureos.vision.camera_manager.cv2.VideoCapture", return_value=capture):
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

    with patch("gestureos.vision.camera_manager.GestureEngine", return_value=engine):
        worker.run()

    engine.close.assert_called_once()
