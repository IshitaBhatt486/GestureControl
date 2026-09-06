"""Render deterministic GestureOS screenshots for the documentation."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication

from gestureos.config.settings_manager import SettingsManager
from gestureos.ui.main_window import MainWindow
from gestureos.ui.settings_dialog import SettingsDialog
from gestureos.vision.camera_manager import PipelineMetrics


class DemoCamera(QObject):
    frame_ready = pyqtSignal(object)
    started = pyqtSignal()
    stopped = pyqtSignal()
    error = pyqtSignal(str)
    recognition_updated = pyqtSignal(str, str, str)
    diagnostics_updated = pyqtSignal(object)
    confidence_updated = pyqtSignal(float)

    is_running = False

    def start_camera(self) -> None:
        self.is_running = True
        self.started.emit()

    def stop_camera(self) -> None:
        self.is_running = False
        self.stopped.emit()

    def update_settings(self, settings) -> None:
        pass


class DemoClapDetector(QObject):
    double_clap = pyqtSignal()
    error = pyqtSignal(str)
    started = pyqtSignal()
    stopped = pyqtSignal()

    def start(self) -> None:
        self.started.emit()

    def stop(self) -> None:
        self.stopped.emit()


def demo_frame() -> np.ndarray:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    for row in range(frame.shape[0]):
        shade = int(12 + 22 * row / frame.shape[0])
        frame[row, :] = (shade, shade + 4, shade + 10)
    points = [
        (320, 390), (285, 350), (255, 310), (225, 270), (195, 230),
        (300, 300), (285, 235), (280, 175), (275, 120),
        (330, 290), (330, 215), (330, 145), (330, 85),
        (360, 300), (375, 230), (380, 170), (385, 120),
        (390, 325), (420, 275), (440, 230), (455, 190),
    ]
    connections = [(index, index + 1) for index in range(1, 4)]
    connections += [(5, 6), (6, 7), (7, 8), (9, 10), (10, 11), (11, 12)]
    connections += [(13, 14), (14, 15), (15, 16), (17, 18), (18, 19), (19, 20)]
    connections += [(0, 1), (0, 5), (0, 17), (5, 9), (9, 13), (13, 17)]
    for first, second in connections:
        cv2.line(frame, points[first], points[second], (85, 210, 150), 3, cv2.LINE_AA)
    for point in points:
        cv2.circle(frame, point, 6, (80, 235, 165), -1, cv2.LINE_AA)
    cv2.putText(frame, "DOCUMENTATION PREVIEW", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (180, 190, 205), 2, cv2.LINE_AA)
    return frame


def save_widget(widget, path: Path) -> None:
    QApplication.processEvents()
    if not widget.grab().save(str(path), "PNG"):
        raise RuntimeError(f"Unable to save screenshot: {path}")


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "docs" / "images"
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    font_root = Path(__file__).resolve().parents[1] / ".venv" / "Lib" / "site-packages" / "matplotlib" / "mpl-data" / "fonts" / "ttf"
    QFontDatabase.addApplicationFont(str(font_root / "DejaVuSans.ttf"))
    QFontDatabase.addApplicationFont(str(font_root / "DejaVuSansMono.ttf"))

    with tempfile.TemporaryDirectory() as temporary:
        settings = SettingsManager(Path(temporary) / "settings.json")
        camera = DemoCamera()
        microphone = DemoClapDetector()
        window = MainWindow(
            camera_manager=camera,
            clap_detector=microphone,
            settings_manager=settings,
        )
        window.setStyleSheet(
            window.styleSheet()
            .replace("'Segoe UI'", "'DejaVu Sans'")
            .replace("'Consolas'", "'DejaVu Sans Mono'")
        )
        window.resize(1240, 820)
        window.show()
        microphone.start()
        camera.start_camera()
        camera.frame_ready.emit(demo_frame())
        window.live_gesture.setText("Raw  Open Palm\nStable  Open Palm")
        window.diagnostics_page.update_gesture("Open Palm", "Open Palm")
        window.gesture_history.addItem("12:34:56   Open Palm")
        window.action_log.addItem("12:34:56   Open Palm")
        camera.confidence_updated.emit(0.94)
        camera.diagnostics_updated.emit(PipelineMetrics(
            camera_fps=30.1,
            recognition_fps=28.7,
            latency_ms=34.8,
            cpu_percent=11.6,
            memory_mb=184.3,
            dropped_frames=3,
            active_threads=3,
        ))
        save_widget(window, output / "dashboard-dark.png")

        window.pages.setCurrentIndex(1)
        save_widget(window, output / "diagnostics-dark.png")

        window.pages.setCurrentIndex(0)
        window.toggle_theme()
        save_widget(window, output / "dashboard-light.png")

        dialog = SettingsDialog(settings.settings, window)
        dialog.setStyleSheet(window.styleSheet())
        dialog.show()
        save_widget(dialog, output / "settings-light.png")
        dialog.close()
        window.hide()
        window.deleteLater()
        QApplication.processEvents()

    app.quit()


if __name__ == "__main__":
    main()
