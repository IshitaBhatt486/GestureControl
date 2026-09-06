from unittest.mock import MagicMock

from PyQt6.QtCore import QObject, QSettings, Qt, pyqtSignal
from PyQt6.QtWidgets import QBoxLayout

from gestureos.config.settings_manager import SettingsManager
from gestureos.ui.main_window import MainWindow
from gestureos.vision.camera_manager import PipelineMetrics


class FakeCamera(QObject):
    frame_ready = pyqtSignal(object)
    started = pyqtSignal()
    stopped = pyqtSignal()
    error = pyqtSignal(str)
    recognition_updated = pyqtSignal(str, str, str)
    diagnostics_updated = pyqtSignal(object)
    confidence_updated = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.start_camera = MagicMock()
        self.stop_camera = MagicMock()


class FakeClapDetector(QObject):
    double_clap = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.start = MagicMock()
        self.stop = MagicMock()


def test_start_stop_and_close_to_tray(qtbot):
    camera = FakeCamera()
    window = MainWindow(camera_manager=camera)
    qtbot.addWidget(window)

    qtbot.mouseClick(window.start_button, Qt.MouseButton.LeftButton)
    camera.start_camera.assert_called_once()

    camera.started.emit()
    assert window.stop_button.isEnabled()
    window.stop_camera()
    camera.stop_camera.assert_called_once()

    window.show()
    window.close()
    assert not window.isVisible()
    assert camera.stop_camera.call_count == 1
    assert window.tray_icon.isVisible()
    window.exit_application()


def test_close_keeps_recognition_running_and_tray_can_reopen(qtbot):
    camera = FakeCamera()
    window = MainWindow(camera_manager=camera)
    qtbot.addWidget(window)
    window.show()
    window.start_camera()
    camera.started.emit()

    window.close()
    assert not window.isVisible()
    camera.stop_camera.assert_not_called()
    assert window.activation.is_active
    assert "Active" in window.tray_icon.toolTip()

    window.open_action.trigger()
    assert window.isVisible()
    window.exit_application()


def test_tray_enable_disable_and_exit(qtbot):
    camera = FakeCamera()
    window = MainWindow(camera_manager=camera)
    qtbot.addWidget(window)

    window.enable_action.trigger()
    camera.start_camera.assert_called_once()
    camera.started.emit()
    assert not window.enable_action.isEnabled()
    assert window.disable_action.isEnabled()

    window.disable_action.trigger()
    camera.stop_camera.assert_called_once()
    camera.stopped.emit()
    assert window.enable_action.isEnabled()
    assert not window.disable_action.isEnabled()
    assert "Paused" in window.tray_icon.toolTip()

    window.exit_action.trigger()
    assert window._exit_requested
    assert camera.stop_camera.call_count == 2
    assert not window.tray_icon.isVisible()


def test_double_clap_toggles_recognition_and_feedback(qtbot):
    camera = FakeCamera()
    clap = FakeClapDetector()
    window = MainWindow(camera_manager=camera, clap_detector=clap)
    qtbot.addWidget(window)

    clap.double_clap.emit()
    camera.start_camera.assert_called_once()
    camera.started.emit()
    assert window.status_text.text() == "Recognition Enabled"

    clap.double_clap.emit()
    camera.stop_camera.assert_called_once()
    camera.stopped.emit()
    assert window.status_text.text() == "Recognition Disabled"
    window.exit_application()
    clap.stop.assert_called_once()


def test_gesture_history_and_action_log_update_together(qtbot):
    camera = FakeCamera()
    window = MainWindow(camera_manager=camera)
    qtbot.addWidget(window)

    camera.recognition_updated.emit("Peace Sign", "Unknown", "")
    camera.recognition_updated.emit("Peace Sign", "Peace Sign", "Peace Sign")
    camera.recognition_updated.emit("Peace Sign", "Peace Sign", "")

    assert "Raw  Peace Sign" in window.live_gesture.text()
    assert window.gesture_history.count() == 1
    assert "Peace Sign" in window.gesture_history.item(0).text()
    assert window.action_log.count() == 1
    window.exit_application()


def test_activity_panels_remain_bounded(qtbot):
    window = MainWindow(camera_manager=FakeCamera())
    qtbot.addWidget(window)
    for index in range(window.MAX_LOG_ITEMS + 10):
        window.update_activity(f"Raw {index}", f"Stable {index}", f"Action {index}")
    assert window.gesture_history.count() == window.MAX_LOG_ITEMS
    assert window.action_log.count() == window.MAX_LOG_ITEMS
    window.exit_application()


def test_diagnostics_panel_displays_pipeline_metrics(qtbot):
    camera = FakeCamera()
    window = MainWindow(camera_manager=camera)
    qtbot.addWidget(window)

    camera.diagnostics_updated.emit(PipelineMetrics(
        camera_fps=29.8,
        recognition_fps=24.3,
        latency_ms=41.7,
        cpu_percent=12.4,
        memory_mb=188.2,
        dropped_frames=7,
        active_threads=3,
    ))

    text = window.diagnostics.text()
    assert "29.8" in text
    assert "24.3" in text
    assert "41.7 ms" in text
    assert "12.4%" in text
    assert "188.2 MB" in text
    assert "7" in text
    assert window.diagnostics_page._values["threads"].text() == "3"
    assert window.diagnostics_page._values["latency"].text() == "41.7 ms"
    window.exit_application()


def test_confidence_display_tracks_recognition_signal(qtbot):
    camera = FakeCamera()
    window = MainWindow(camera_manager=camera)
    qtbot.addWidget(window)

    camera.confidence_updated.emit(0.873)

    assert window.confidence_bar.value() == 87
    assert window.confidence_label.text() == "Confidence  87%"
    window.exit_application()


def test_diagnostics_page_tracks_current_gesture_and_pipeline_status(qtbot):
    camera = FakeCamera()
    window = MainWindow(camera_manager=camera)
    qtbot.addWidget(window)

    camera.started.emit()
    camera.recognition_updated.emit("Peace Sign", "Peace Sign", "")

    assert window.diagnostics_page.live_status.text() == "●  LIVE"
    assert window.diagnostics_page.current_gesture.text() == "Peace Sign"
    assert "Raw  Peace Sign" in window.diagnostics_page.gesture_detail.text()

    camera.stopped.emit()
    assert window.diagnostics_page.live_status.text() == "●  PAUSED"
    assert window.diagnostics_page.current_gesture.text() == "No gesture detected"
    window.exit_application()


def test_theme_toggle_persists_and_responsive_layout_reflows(qtbot, tmp_path):
    settings = SettingsManager(tmp_path / "settings.json")
    window = MainWindow(camera_manager=FakeCamera(), settings_manager=settings)
    qtbot.addWidget(window)
    window.show()

    assert window._theme_mode == "dark"
    window.theme_button.click()
    assert window._theme_mode == "light"
    assert SettingsManager(settings.path).settings.theme == "light"

    window.resize(800, 700)
    qtbot.wait(10)
    assert window._content_layout.direction() == QBoxLayout.Direction.TopToBottom
    window.resize(1200, 700)
    qtbot.wait(10)
    assert window._content_layout.direction() == QBoxLayout.Direction.LeftToRight
    window.exit_application()


def test_first_run_onboarding_is_persisted(qtbot, tmp_path):
    onboarding_settings = QSettings(str(tmp_path / "onboarding.ini"), QSettings.Format.IniFormat)
    window = MainWindow(camera_manager=FakeCamera(), onboarding_settings=onboarding_settings)
    qtbot.addWidget(window)

    assert window.show_onboarding_if_needed()
    assert window.onboarding_dialog is not None
    window.onboarding_dialog.finish()
    assert onboarding_settings.value("onboarding/completed", False, type=bool)
    assert not window.show_onboarding_if_needed()
    window.exit_application()


def test_status_animation_and_tray_mode_work_together(qtbot):
    camera = FakeCamera()
    window = MainWindow(camera_manager=camera)
    qtbot.addWidget(window)
    window.show()
    camera.started.emit()
    assert window._status_pulse.state().name == "Running"

    window.close()
    assert not window.isVisible()
    assert window.activation.is_active
    assert window.tray_icon.isVisible()
    window.open_from_tray()
    assert window.isVisible()
    window.exit_application()


def test_camera_retry_waits_for_worker_teardown(qtbot, monkeypatch):
    camera = FakeCamera()
    window = MainWindow(camera_manager=camera)
    qtbot.addWidget(window)
    monkeypatch.setattr("gestureos.ui.main_window.QMessageBox.warning", lambda *args: None)

    camera.error.emit("Camera disconnected")
    assert not window.start_button.isEnabled()
    window.start_camera()
    camera.start_camera.assert_not_called()

    camera.stopped.emit()
    assert window.start_button.isEnabled()
    assert window.start_button.text() == "Retry Camera"
    window.start_button.click()
    camera.start_camera.assert_called_once()
    window.exit_application()


def test_accessibility_names_and_keyboard_shortcuts(qtbot):
    window = MainWindow(camera_manager=FakeCamera())
    qtbot.addWidget(window)

    assert window.preview.accessibleName() == "Live camera preview"
    assert window.confidence_bar.accessibleName() == "Gesture confidence"
    assert window.pages.accessibleName() == "GestureOS pages"
    assert window.enable_action.shortcut().toString() == "Alt+E"
    assert window.settings_action.shortcut().toString() == "Ctrl+,"
    window.diagnostics_action.trigger()
    assert window.pages.currentIndex() == 1
    window.exit_application()
