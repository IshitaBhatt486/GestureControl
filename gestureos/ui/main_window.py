"""Polished GestureOS desktop dashboard and tray controller."""

from __future__ import annotations

import logging

import cv2
from PyQt6.QtCore import QPropertyAnimation, QSettings, QTime, Qt, pyqtSlot
from PyQt6.QtGui import QAction, QCloseEvent, QColor, QIcon, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from gestureos.config.settings_manager import SettingsManager
from gestureos.services.activation_service import ActivationService
from gestureos.services.clap_detector import ClapDetector
from gestureos.ui.onboarding import OnboardingDialog
from gestureos.vision.camera_manager import CameraManager

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Application dashboard, activity timeline, onboarding, and tray lifecycle."""

    MAX_LOG_ITEMS = 50

    def __init__(
        self,
        camera_manager: CameraManager | None = None,
        clap_detector: ClapDetector | None = None,
        settings_manager: SettingsManager | None = None,
        onboarding_settings: QSettings | None = None,
    ) -> None:
        super().__init__()
        self.settings_manager = settings_manager or SettingsManager()
        self.camera = camera_manager or CameraManager(settings=self.settings_manager.settings)
        self.activation = ActivationService()
        self.clap_detector = clap_detector or ClapDetector()
        self.onboarding_settings = onboarding_settings or QSettings("GestureOS", "GestureOS")
        self.onboarding_dialog: OnboardingDialog | None = None
        self._exit_requested = False
        self._last_stable_gesture = "Unknown"
        self._active_icon = self._make_status_icon("#34d399")
        self._paused_icon = self._make_status_icon("#64748b")
        self._build_ui()
        self._build_tray()
        self._connect_signals()

    @staticmethod
    def _make_status_icon(color: str) -> QIcon:
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#0f172a"))
        painter.setBrush(QColor(color))
        painter.drawEllipse(4, 4, 24, 24)
        painter.end()
        return QIcon(pixmap)

    def _build_ui(self) -> None:
        self.setWindowTitle("GestureOS")
        self.resize(1180, 760)
        self.setMinimumSize(920, 620)
        self.setStyleSheet(self._theme())

        brand = QLabel("GestureOS")
        brand.setObjectName("brand")
        tagline = QLabel("Touchless media control")
        tagline.setObjectName("tagline")
        brand_layout = QVBoxLayout()
        brand_layout.setSpacing(0)
        brand_layout.addWidget(brand)
        brand_layout.addWidget(tagline)

        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        self.status_text = QLabel("Recognition Disabled")
        self.status_text.setObjectName("statusText")
        status_layout = QHBoxLayout()
        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_text)

        header = QHBoxLayout()
        header.addLayout(brand_layout)
        header.addStretch()
        header.addLayout(status_layout)

        self.preview = QLabel("Camera preview is paused")
        self.preview.setObjectName("preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(560, 420)

        self.start_button = QPushButton("Enable Recognition")
        self.start_button.setObjectName("primaryButton")
        self.stop_button = QPushButton("Pause")
        self.stop_button.setEnabled(False)
        controls = QHBoxLayout()
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addStretch()

        camera_card = QFrame()
        camera_card.setObjectName("card")
        camera_layout = QVBoxLayout(camera_card)
        camera_layout.setContentsMargins(14, 14, 14, 14)
        camera_layout.addWidget(self.preview, 1)
        camera_layout.addLayout(controls)

        self.live_gesture = QLabel("Waiting for recognition data")
        self.live_gesture.setObjectName("liveGesture")
        self.gesture_history = QListWidget()
        self.gesture_history.setObjectName("activityList")
        self.gesture_history.setAccessibleName("Gesture history")
        self.action_log = QListWidget()
        self.action_log.setObjectName("activityList")
        self.action_log.setAccessibleName("Action log")

        sidebar = QFrame()
        sidebar.setObjectName("card")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(18, 18, 18, 18)
        side_layout.addWidget(QLabel("LIVE GESTURE", objectName="sectionLabel"))
        side_layout.addWidget(self.live_gesture)
        side_layout.addSpacing(12)
        side_layout.addWidget(QLabel("GESTURE HISTORY", objectName="sectionLabel"))
        side_layout.addWidget(self.gesture_history, 1)
        side_layout.addWidget(QLabel("ACTION LOG", objectName="sectionLabel"))
        side_layout.addWidget(self.action_log, 1)

        content = QHBoxLayout()
        content.setSpacing(18)
        content.addWidget(camera_card, 3)
        content.addWidget(sidebar, 2)

        layout = QVBoxLayout()
        layout.setContentsMargins(26, 22, 26, 24)
        layout.setSpacing(18)
        layout.addLayout(header)
        layout.addLayout(content, 1)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self._status_effect = QGraphicsOpacityEffect(self.status_dot)
        self.status_dot.setGraphicsEffect(self._status_effect)
        self._status_pulse = QPropertyAnimation(self._status_effect, b"opacity", self)
        self._status_pulse.setDuration(900)
        self._status_pulse.setStartValue(1.0)
        self._status_pulse.setEndValue(0.35)
        self._status_pulse.setLoopCount(-1)
        self._set_status("Recognition Disabled", "#64748b")

    @staticmethod
    def _theme() -> str:
        return """
            QMainWindow, QWidget { background: #080d18; color: #e5e7eb; font-family: 'Segoe UI'; }
            QLabel#brand { font-size: 27px; font-weight: 700; color: #f8fafc; }
            QLabel#tagline { color: #718096; font-size: 12px; }
            QLabel#statusText { font-size: 13px; font-weight: 600; color: #cbd5e1; }
            QLabel#statusDot { font-size: 18px; }
            QFrame#card { background: #111827; border: 1px solid #1e293b; border-radius: 14px; }
            QLabel#preview { background: #050914; border: 1px solid #1e293b; border-radius: 10px;
                             color: #64748b; font-size: 16px; }
            QLabel#sectionLabel { color: #64748b; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
            QLabel#liveGesture { background: #0b1220; border: 1px solid #1f3347; border-radius: 9px;
                                 color: #6ee7b7; padding: 13px; font-size: 15px; font-weight: 600; }
            QListWidget#activityList { background: #0b1220; border: 1px solid #1e293b; border-radius: 9px;
                                       padding: 5px; outline: none; color: #cbd5e1; }
            QListWidget#activityList::item { padding: 7px 6px; border-bottom: 1px solid #162033; }
            QPushButton { background: #1e293b; color: #e2e8f0; border: 1px solid #334155;
                          border-radius: 8px; padding: 9px 16px; font-weight: 600; }
            QPushButton:hover { background: #293548; border-color: #475569; }
            QPushButton:disabled { color: #526078; background: #141c2b; border-color: #1e293b; }
            QPushButton#primaryButton { background: #10b981; color: #04120d; border-color: #34d399; }
            QPushButton#primaryButton:hover { background: #34d399; }
            QMenu { background: #111827; color: #e5e7eb; border: 1px solid #334155; padding: 6px; }
            QMenu::item { padding: 7px 28px 7px 10px; border-radius: 5px; }
            QMenu::item:selected { background: #1f3a37; color: #6ee7b7; }
            QDialog#onboarding { background: #0f172a; color: #e5e7eb; }
            QLabel#eyebrow { color: #34d399; font-size: 10px; font-weight: 700; }
            QLabel#onboardingTitle { color: #f8fafc; font-size: 25px; font-weight: 700; margin-top: 8px; }
            QLabel#onboardingCopy { color: #94a3b8; font-size: 15px; line-height: 1.5; }
        """

    def _build_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self._paused_icon, self)
        self.tray_icon.setToolTip("GestureOS — Paused")
        self.tray_menu = QMenu(self)
        self.open_action = QAction("Open GestureOS", self)
        self.enable_action = QAction("Enable Recognition", self)
        self.disable_action = QAction("Disable Recognition", self)
        self.startup_action = QAction("Launch at Windows Startup", self, checkable=True)
        self.startup_action.setChecked(self.settings_manager.settings.startup_enabled)
        self.exit_action = QAction("Exit", self)
        self.disable_action.setEnabled(False)
        for action in (self.open_action, None, self.enable_action, self.disable_action, None, self.startup_action, None, self.exit_action):
            self.tray_menu.addSeparator() if action is None else self.tray_menu.addAction(action)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self.start_camera)
        self.stop_button.clicked.connect(self.stop_camera)
        self.camera.frame_ready.connect(self.update_frame)
        self.camera.started.connect(self._camera_started)
        self.camera.stopped.connect(self._camera_stopped)
        self.camera.error.connect(self._camera_error)
        if hasattr(self.camera, "recognition_updated"):
            self.camera.recognition_updated.connect(self.update_activity)
        self.open_action.triggered.connect(self.open_from_tray)
        self.enable_action.triggered.connect(self.start_camera)
        self.disable_action.triggered.connect(self.stop_camera)
        self.startup_action.toggled.connect(self._set_startup_enabled)
        self.exit_action.triggered.connect(self.exit_application)
        self.tray_icon.activated.connect(self._tray_activated)
        self.clap_detector.double_clap.connect(self.toggle_recognition)
        self.clap_detector.error.connect(self._clap_error)

    def show_onboarding_if_needed(self) -> bool:
        if self.onboarding_settings.value("onboarding/completed", False, type=bool):
            return False
        self.onboarding_dialog = OnboardingDialog(self)
        self.onboarding_dialog.completed.connect(self._complete_onboarding)
        self.onboarding_dialog.open()
        return True

    @pyqtSlot()
    def _complete_onboarding(self) -> None:
        self.onboarding_settings.setValue("onboarding/completed", True)
        self.onboarding_settings.sync()

    @pyqtSlot(str, str, str)
    def update_activity(self, raw: str, stable: str, action: str) -> None:
        self.live_gesture.setText(f"Raw  {raw}\nStable  {stable}")
        timestamp = QTime.currentTime().toString("HH:mm:ss")
        if stable != "Unknown" and stable != self._last_stable_gesture:
            self._prepend_bounded(self.gesture_history, f"{timestamp}   {stable}")
        self._last_stable_gesture = stable
        if action:
            self._prepend_bounded(self.action_log, f"{timestamp}   {action}")

    def _prepend_bounded(self, widget: QListWidget, text: str) -> None:
        widget.insertItem(0, text)
        while widget.count() > self.MAX_LOG_ITEMS:
            widget.takeItem(widget.count() - 1)

    @pyqtSlot()
    def toggle_recognition(self) -> None:
        self.stop_camera() if self.activation.is_active else self.start_camera()

    @pyqtSlot(str)
    def _clap_error(self, message: str) -> None:
        logger.warning("Clap detection unavailable: %s", message)

    @pyqtSlot(bool)
    def _set_startup_enabled(self, enabled: bool) -> None:
        try:
            self.settings_manager.set_startup_enabled(enabled)
        except OSError as exc:
            logger.exception("Unable to update Windows startup setting")
            self.startup_action.blockSignals(True)
            self.startup_action.setChecked(not enabled)
            self.startup_action.blockSignals(False)
            QMessageBox.warning(self, "Startup setting", str(exc))

    @pyqtSlot(QSystemTrayIcon.ActivationReason)
    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_from_tray()

    @pyqtSlot()
    def open_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _set_tray_active(self, active: bool) -> None:
        self.tray_icon.setIcon(self._active_icon if active else self._paused_icon)
        self.tray_icon.setToolTip(f"GestureOS — {'Active' if active else 'Paused'}")
        self.enable_action.setEnabled(not active)
        self.disable_action.setEnabled(active)

    def _set_status(self, text: str, color: str, animate: bool = False) -> None:
        self.status_text.setText(text)
        self.status_dot.setStyleSheet(f"color: {color};")
        self._status_pulse.stop()
        self._status_effect.setOpacity(1.0)
        if animate:
            self._status_pulse.start()

    @pyqtSlot()
    def start_camera(self) -> None:
        self._set_status("Starting recognition…", "#fbbf24", animate=True)
        self.start_button.setEnabled(False)
        self.camera.start_camera()

    @pyqtSlot()
    def stop_camera(self) -> None:
        self.stop_button.setEnabled(False)
        self._set_status("Pausing recognition…", "#fbbf24", animate=True)
        self.camera.stop_camera()

    @pyqtSlot()
    def _camera_started(self) -> None:
        self.activation.activate()
        self._set_status("Recognition Enabled", "#34d399", animate=True)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._set_tray_active(True)

    @pyqtSlot()
    def _camera_stopped(self) -> None:
        self.activation.deactivate()
        self.preview.clear()
        self.preview.setText("Camera preview is paused")
        self._set_status("Recognition Disabled", "#64748b")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._set_tray_active(False)

    @pyqtSlot(str)
    def _camera_error(self, message: str) -> None:
        logger.error("Camera error: %s", message)
        self.activation.deactivate()
        self._set_status("Camera unavailable", "#fb7185")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._set_tray_active(False)
        QMessageBox.warning(self, "Camera error", message)

    @pyqtSlot(object)
    def update_frame(self, frame: object) -> None:
        if frame is None:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        image = QImage(rgb.data, width, height, channels * width, QImage.Format.Format_RGB888).copy()
        self.preview.setPixmap(QPixmap.fromImage(image).scaled(
            self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        ))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._exit_requested:
            event.accept()
            return
        logger.info("Hiding GestureOS in the system tray")
        event.ignore()
        self.hide()

    @pyqtSlot()
    def exit_application(self) -> None:
        if self._exit_requested:
            return
        self._exit_requested = True
        logger.info("Exiting GestureOS")
        self.camera.stop_camera()
        self.clap_detector.stop()
        self.activation.deactivate()
        self.tray_icon.hide()
        self.hide()
        app = QApplication.instance()
        if app is not None:
            app.quit()
