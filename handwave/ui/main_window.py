"""Polished HandWave desktop dashboard and tray controller."""

from __future__ import annotations

import logging

import cv2
from PyQt6.QtCore import QPropertyAnimation, QSettings, QTime, QTimer, Qt, pyqtSlot
from PyQt6.QtGui import QAction, QCloseEvent, QColor, QIcon, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from handwave.config.profile_manager import ProfileManager
from handwave.config.settings_manager import SettingsManager
from handwave.services.action_history import ActionHistory
from handwave.services.activation_service import ActivationService
from handwave.services.clap_detector import ClapDetector
from handwave.services.foreground_app import get_foreground_app
from handwave.services.profile_switcher import ProfileSwitchEvent, ProfileSwitcher
from handwave.ui.onboarding import OnboardingDialog
from handwave.ui.diagnostics_page import DiagnosticsPage
from handwave.ui.settings_dialog import SettingsDialog
from handwave.vision.camera_manager import CameraManager

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Application dashboard, activity timeline, onboarding, and tray lifecycle."""

    MAX_LOG_ITEMS = 50

    PROFILE_POLL_INTERVAL_MS = 1500

    def __init__(
        self,
        camera_manager: CameraManager | None = None,
        clap_detector: ClapDetector | None = None,
        settings_manager: SettingsManager | None = None,
        onboarding_settings: QSettings | None = None,
        profile_manager: ProfileManager | None = None,
        foreground_app_provider=None,
    ) -> None:
        super().__init__()
        self.settings_manager = settings_manager or SettingsManager()
        self.camera = camera_manager or CameraManager(settings=self.settings_manager.settings)
        self.activation = ActivationService()
        self.clap_detector = clap_detector or ClapDetector()
        self.onboarding_settings = onboarding_settings or QSettings("HandWave", "HandWave")
        self.onboarding_dialog: OnboardingDialog | None = None
        self.profile_manager = profile_manager or ProfileManager()
        self.profile_switcher = ProfileSwitcher(
            self.profile_manager,
            foreground_provider=foreground_app_provider or get_foreground_app,
            global_settings_provider=lambda: self.settings_manager.settings,
            on_change=self._on_profile_switch,
            enabled=self.settings_manager.settings.auto_switch_profiles,
        )
        self._profile_poll_timer = QTimer(self)
        self._profile_poll_timer.setInterval(self.PROFILE_POLL_INTERVAL_MS)
        self._profile_poll_timer.timeout.connect(self._poll_profile_switch)
        self._last_profile_event: ProfileSwitchEvent | None = None
        self.action_history = ActionHistory()
        self._last_confidence = 0.0
        self._exit_requested = False
        self._camera_error_pending = False
        self._last_stable_gesture = "Unknown"
        self._theme_mode = self.settings_manager.settings.theme
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
        self.setWindowTitle("HandWave")
        self.resize(1240, 820)
        self.setMinimumSize(760, 600)
        self.setStyleSheet(self._theme(self._theme_mode))

        brand = QLabel("HandWave")
        brand.setObjectName("brand")
        tagline = QLabel("Touchless media control for Windows")
        tagline.setObjectName("tagline")
        brand_layout = QVBoxLayout()
        brand_layout.setSpacing(0)
        brand_layout.addWidget(brand)
        brand_layout.addWidget(tagline)

        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        self.status_text = QLabel("Recognition Disabled")
        self.status_text.setObjectName("statusText")
        status_badge = QFrame()
        status_badge.setObjectName("statusBadge")
        status_layout = QHBoxLayout(status_badge)
        status_layout.setContentsMargins(12, 7, 12, 7)
        status_layout.setSpacing(7)
        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_text)

        self.theme_button = QPushButton()
        self.theme_button.setObjectName("themeButton")
        self.theme_button.setToolTip("Switch between dark and light appearance")
        self._sync_theme_button()

        header = QHBoxLayout()
        header.addLayout(brand_layout)
        header.addStretch()
        header.addWidget(status_badge)
        header.addWidget(self.theme_button)

        system_status = QFrame()
        system_status.setObjectName("statusStrip")
        system_status_layout = QHBoxLayout(system_status)
        system_status_layout.setContentsMargins(14, 8, 14, 8)
        system_status_layout.setSpacing(18)
        self.camera_status = QLabel("●  CAMERA IDLE")
        self.recognition_status = QLabel("●  RECOGNITION OFF")
        self.microphone_status = QLabel("●  MICROPHONE STANDBY")
        self.profile_status = QLabel("Active profile: Global")
        self.profile_status.setAccessibleName("Active application profile")
        for indicator in (self.camera_status, self.recognition_status, self.microphone_status, self.profile_status):
            indicator.setObjectName("systemIndicator")
            system_status_layout.addWidget(indicator)
        system_status_layout.addStretch()

        self.preview = QLabel("Camera preview is paused")
        self.preview.setObjectName("preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(360, 280)
        self.preview.setAccessibleName("Live camera preview")
        self.preview.setAccessibleDescription("Shows the camera image and detected hand landmarks while recognition is enabled.")

        camera_title = QLabel("Camera workspace")
        camera_title.setObjectName("cardTitle")
        camera_subtitle = QLabel("Live landmark tracking and gesture recognition")
        camera_subtitle.setObjectName("cardSubtitle")

        self.start_button = QPushButton("Enable Recognition")
        self.start_button.setObjectName("primaryButton")
        self.start_button.setAccessibleDescription("Start camera capture and gesture recognition")
        self.stop_button = QPushButton("Pause")
        self.stop_button.setEnabled(False)
        self.stop_button.setAccessibleDescription("Pause camera capture and gesture recognition")
        self.settings_button = QPushButton("Settings")
        self.settings_button.setAccessibleDescription("Open gesture bindings and sensitivity settings")
        controls = QHBoxLayout()
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.settings_button)
        controls.addStretch()

        camera_card = QFrame()
        camera_card.setObjectName("card")
        camera_layout = QVBoxLayout(camera_card)
        camera_layout.setContentsMargins(18, 16, 18, 18)
        camera_layout.setSpacing(12)
        camera_layout.addWidget(camera_title)
        camera_layout.addWidget(camera_subtitle)
        camera_layout.addWidget(self.preview, 1)
        camera_layout.addLayout(controls)

        self.live_gesture = QLabel("No gesture detected")
        self.live_gesture.setObjectName("liveGesture")
        self.confidence_label = QLabel("Confidence  0%")
        self.confidence_label.setObjectName("confidenceLabel")
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setObjectName("confidenceBar")
        self.confidence_bar.setRange(0, 100)
        self.confidence_bar.setValue(0)
        self.confidence_bar.setTextVisible(False)
        self.confidence_bar.setAccessibleName("Gesture confidence")
        self.confidence_bar.setAccessibleDescription("Recognition confidence from zero to one hundred percent")
        self.gesture_history = QListWidget()
        self.gesture_history.setObjectName("activityList")
        self.gesture_history.setAccessibleName("Gesture history")
        self.action_log = QListWidget()
        self.action_log.setObjectName("activityList")
        self.action_log.setAccessibleName("Action log")

        diagnostics_title = QLabel("DIAGNOSTICS")
        diagnostics_title.setObjectName("sectionLabel")
        self.diagnostics = QLabel(
            "Camera FPS       0.0\n"
            "Recognition FPS  0.0\n"
            "Latency           0.0 ms\n"
            "CPU               0.0%\n"
            "RAM               0.0 MB\n"
            "Dropped frames    0"
        )
        self.diagnostics.setObjectName("diagnostics")
        self.diagnostics.setAccessibleName("Pipeline diagnostics")

        sidebar = QFrame()
        sidebar.setObjectName("card")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(18, 18, 18, 18)
        side_layout.addWidget(QLabel("LIVE GESTURE", objectName="sectionLabel"))
        side_layout.addWidget(self.live_gesture)
        side_layout.addWidget(self.confidence_label)
        side_layout.addWidget(self.confidence_bar)
        side_layout.addSpacing(12)
        side_layout.addWidget(QLabel("GESTURE HISTORY", objectName="sectionLabel"))
        side_layout.addWidget(self.gesture_history, 1)
        side_layout.addWidget(QLabel("ACTION LOG", objectName="sectionLabel"))
        side_layout.addWidget(self.action_log, 1)
        side_layout.addWidget(diagnostics_title)
        side_layout.addWidget(self.diagnostics)

        sidebar.setMinimumWidth(300)
        self._content_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self._content_layout.setSpacing(18)
        self._content_layout.addWidget(camera_card, 3)
        self._content_layout.addWidget(sidebar, 2)

        layout = QVBoxLayout()
        layout.setContentsMargins(26, 22, 26, 24)
        layout.setSpacing(18)
        layout.addLayout(header)
        layout.addWidget(system_status)
        layout.addLayout(self._content_layout, 1)
        container = QWidget()
        container.setLayout(layout)
        scroll = QScrollArea()
        scroll.setObjectName("workspaceScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(container)
        self.diagnostics_page = DiagnosticsPage()
        self.pages = QTabWidget()
        self.pages.setObjectName("mainPages")
        self.pages.addTab(scroll, "Dashboard")
        self.pages.addTab(self.diagnostics_page, "Diagnostics")
        self.pages.setAccessibleName("HandWave pages")
        self.setCentralWidget(self.pages)
        self.statusBar().showMessage("Ready")

        self._status_effect = QGraphicsOpacityEffect(self.status_dot)
        self.status_dot.setGraphicsEffect(self._status_effect)
        self._status_pulse = QPropertyAnimation(self._status_effect, b"opacity", self)
        self._status_pulse.setDuration(900)
        self._status_pulse.setStartValue(1.0)
        self._status_pulse.setEndValue(0.35)
        self._status_pulse.setLoopCount(-1)
        self._set_status("Recognition Disabled", "#64748b")

    @staticmethod
    def _theme(mode: str = "dark") -> str:
        palette = {
            "dark": ("#0b0f17", "#111827", "#151e2e", "#e8edf5", "#8d9bb0", "#263247", "#080c13"),
            "light": ("#f3f5f8", "#ffffff", "#f7f9fc", "#172033", "#68758a", "#dbe1ea", "#e9edf3"),
        }[mode]
        bg, card, inset, text, muted, border, preview = palette
        return f"""
            QMainWindow, QWidget {{ background: {bg}; color: {text}; font-family: 'Segoe UI'; font-size: 12px; }}
            QScrollArea#workspaceScroll {{ background: {bg}; border: none; }}
            QLabel#brand {{ font-size: 28px; font-weight: 700; color: {text}; }}
            QLabel#tagline, QLabel#cardSubtitle, QLabel#confidenceLabel {{ color: {muted}; }}
            QLabel#cardTitle {{ font-size: 16px; font-weight: 650; color: {text}; }}
            QFrame#statusBadge, QFrame#statusStrip {{ background: {card}; border: 1px solid {border}; border-radius: 10px; }}
            QLabel#statusText {{ font-weight: 600; color: {text}; }}
            QLabel#statusDot {{ font-size: 16px; }}
            QLabel#systemIndicator {{ color: {muted}; font-size: 10px; font-weight: 700; }}
            QFrame#card {{ background: {card}; border: 1px solid {border}; border-radius: 14px; }}
            QLabel#preview {{ background: {preview}; border: 1px solid {border}; border-radius: 10px; color: {muted}; font-size: 15px; }}
            QLabel#sectionLabel {{ color: {muted}; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}
            QLabel#liveGesture {{ background: {inset}; border: 1px solid {border}; border-radius: 9px; color: #0ea978; padding: 13px; font-size: 15px; font-weight: 650; }}
            QLabel#diagnostics {{ background: {inset}; border: 1px solid {border}; border-radius: 9px; color: {muted}; padding: 11px; font-family: 'Consolas'; font-size: 11px; }}
            QProgressBar#confidenceBar {{ background: {inset}; border: 1px solid {border}; border-radius: 4px; height: 7px; }}
            QProgressBar#confidenceBar::chunk {{ background: #10b981; border-radius: 3px; }}
            QListWidget#activityList {{ background: {inset}; border: 1px solid {border}; border-radius: 9px; padding: 5px; outline: none; color: {text}; }}
            QListWidget#activityList::item {{ padding: 7px 6px; border-bottom: 1px solid {border}; }}
            QPushButton, QComboBox, QDoubleSpinBox {{ background: {inset}; color: {text}; border: 1px solid {border}; border-radius: 8px; padding: 8px 14px; font-weight: 600; }}
            QPushButton:hover, QComboBox:hover {{ border-color: #10b981; }}
            QPushButton:disabled {{ color: {muted}; background: {card}; }}
            QPushButton#primaryButton {{ background: #10b981; color: #06130f; border-color: #10b981; }}
            QPushButton#primaryButton:hover {{ background: #22c995; }}
            QPushButton#themeButton {{ min-width: 82px; }}
            QTabWidget#mainPages::pane {{ border: none; background: {bg}; }}
            QTabBar::tab {{ background: {card}; color: {muted}; border-bottom: 2px solid transparent;
                            padding: 10px 22px; min-width: 90px; font-weight: 600; }}
            QTabBar::tab:selected {{ color: {text}; border-bottom-color: #10b981; }}
            QLabel#pageTitle {{ color: {text}; font-size: 24px; font-weight: 700; }}
            QLabel#pageSubtitle {{ color: {muted}; font-size: 12px; }}
            QLabel#diagnosticsStatus {{ color: {muted}; font-size: 10px; font-weight: 700; }}
            QFrame#metricCard {{ background: {card}; border: 1px solid {border}; border-radius: 12px; }}
            QLabel#metricName {{ color: {muted}; font-size: 9px; font-weight: 700; letter-spacing: 1px; }}
            QLabel#metricValue {{ color: {text}; font-size: 24px; font-weight: 700; }}
            QLabel#metricCaption {{ color: {muted}; font-size: 10px; }}
            QLabel#currentGestureValue {{ color: #0ea978; font-size: 22px; font-weight: 700; }}
            QMenu {{ background: {card}; color: {text}; border: 1px solid {border}; padding: 6px; }}
            QMenu::item {{ padding: 7px 28px 7px 10px; border-radius: 5px; }}
            QMenu::item:selected {{ background: {inset}; color: #0ea978; }}
            QGroupBox {{ border: 1px solid {border}; border-radius: 10px; margin-top: 12px; padding-top: 10px; font-weight: 650; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; }}
            QDialog#onboarding {{ background: {card}; color: {text}; }}
            QLabel#eyebrow {{ color: #0ea978; font-size: 10px; font-weight: 700; }}
            QLabel#onboardingTitle {{ color: {text}; font-size: 25px; font-weight: 700; margin-top: 8px; }}
            QLabel#onboardingCopy {{ color: {muted}; font-size: 15px; }}
        """

    def _build_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self._paused_icon, self)
        self.tray_icon.setToolTip("HandWave — Paused")
        self.tray_menu = QMenu(self)
        self.open_action = QAction("Open HandWave", self)
        self.enable_action = QAction("Enable Recognition", self)
        self.disable_action = QAction("Disable Recognition", self)
        self.settings_action = QAction("Settings…", self)
        self.startup_action = QAction("Launch at Windows Startup", self, checkable=True)
        self.startup_action.setChecked(self.settings_manager.settings.startup_enabled)
        self.exit_action = QAction("Exit", self)
        self.enable_action.setShortcut("Alt+E")
        self.disable_action.setShortcut("Alt+P")
        self.settings_action.setShortcut("Ctrl+,")
        self.theme_action = QAction("Toggle theme", self)
        self.theme_action.setShortcut("Ctrl+T")
        self.diagnostics_action = QAction("Open diagnostics", self)
        self.diagnostics_action.setShortcut("Ctrl+D")
        self.addActions((self.enable_action, self.disable_action, self.settings_action, self.theme_action, self.diagnostics_action))
        self.disable_action.setEnabled(False)
        for action in (self.open_action, self.settings_action, None, self.enable_action, self.disable_action, None, self.startup_action, None, self.exit_action):
            self.tray_menu.addSeparator() if action is None else self.tray_menu.addAction(action)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self.start_camera)
        self.stop_button.clicked.connect(self.stop_camera)
        self.settings_button.clicked.connect(self.open_settings)
        self.theme_button.clicked.connect(self.toggle_theme)
        self.camera.frame_ready.connect(self.update_frame)
        self.camera.started.connect(self._camera_started)
        self.camera.stopped.connect(self._camera_stopped)
        self.camera.error.connect(self._camera_error)
        if hasattr(self.camera, "recognition_updated"):
            self.camera.recognition_updated.connect(self.update_activity)
        if hasattr(self.camera, "diagnostics_updated"):
            self.camera.diagnostics_updated.connect(self.update_diagnostics)
        if hasattr(self.camera, "confidence_updated"):
            self.camera.confidence_updated.connect(self.update_confidence)
        if hasattr(self.camera, "action_outcome_updated"):
            self.camera.action_outcome_updated.connect(self._record_action_outcome)
        self.open_action.triggered.connect(self.open_from_tray)
        self.enable_action.triggered.connect(self.start_camera)
        self.disable_action.triggered.connect(self.stop_camera)
        self.settings_action.triggered.connect(self.open_settings)
        self.theme_action.triggered.connect(self.toggle_theme)
        self.diagnostics_action.triggered.connect(lambda: self.pages.setCurrentIndex(1))
        self.startup_action.toggled.connect(self._set_startup_enabled)
        self.exit_action.triggered.connect(self.exit_application)
        self.tray_icon.activated.connect(self._tray_activated)
        self.clap_detector.double_clap.connect(self.toggle_recognition)
        self.clap_detector.error.connect(self._clap_error)
        if hasattr(self.clap_detector, "started"):
            self.clap_detector.started.connect(self._microphone_started)
        if hasattr(self.clap_detector, "stopped"):
            self.clap_detector.stopped.connect(self._microphone_stopped)

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
        self.diagnostics_page.update_gesture(raw, stable)
        timestamp = QTime.currentTime().toString("HH:mm:ss")
        if stable != "Unknown" and stable != self._last_stable_gesture:
            self._prepend_bounded(self.gesture_history, f"{timestamp}   {stable}")
        self._last_stable_gesture = stable
        if action:
            self._prepend_bounded(self.action_log, f"{timestamp}   {action}")

    @pyqtSlot(float)
    def update_confidence(self, confidence: float) -> None:
        self._last_confidence = confidence
        percent = max(0, min(100, round(confidence * 100)))
        self.confidence_bar.setValue(percent)
        self.confidence_label.setText(f"Confidence  {percent}%")

    @pyqtSlot(object)
    def _record_action_outcome(self, outcome: object) -> None:
        """Log a structured, bounded audit entry for every recognized gesture."""
        profile_name = None
        application = None
        if self._last_profile_event is not None:
            profile_name = (
                self._last_profile_event.match.profile.name
                if self._last_profile_event.match.profile
                else "Global"
            )
            application = self._last_profile_event.foreground.executable
        entry = self.action_history.record(
            gesture=outcome.gesture,
            confidence=self._last_confidence,
            action=outcome.action_description,
            executed=outcome.executed,
            blocked_reason=outcome.blocked_reason,
            application=application,
            profile=profile_name,
        )
        timestamp = QTime.currentTime().toString("HH:mm:ss")
        if not entry.executed:
            self._prepend_bounded(self.action_log, f"{timestamp}   Blocked: {entry.blocked_reason}")

    def _prepend_bounded(self, widget: QListWidget, text: str) -> None:
        widget.insertItem(0, text)
        while widget.count() > self.MAX_LOG_ITEMS:
            widget.takeItem(widget.count() - 1)

    @pyqtSlot(object)
    def update_diagnostics(self, metrics: object) -> None:
        """Display the latest passive pipeline profiling snapshot."""
        self.diagnostics_page.update_metrics(metrics)
        self.diagnostics.setText(
            f"Camera FPS       {metrics.camera_fps:5.1f}\n"
            f"Recognition FPS  {metrics.recognition_fps:5.1f}\n"
            f"Latency          {metrics.latency_ms:5.1f} ms\n"
            f"CPU              {metrics.cpu_percent:5.1f}%\n"
            f"RAM              {metrics.memory_mb:5.1f} MB\n"
            f"Dropped frames   {metrics.dropped_frames:5d}\n"
            f"Hands detected   {metrics.hands_detected:5d}\n"
            f"Left hand        {metrics.left_hand_pose or '-'}\n"
            f"Right hand       {metrics.right_hand_pose or '-'}\n"
            + self._profile_diagnostics_text()
        )

    def _profile_diagnostics_text(self) -> str:
        event = self._last_profile_event
        if event is None:
            return "Foreground app     unknown\nActive profile      Global\nMatch reason        n/a"
        name = event.match.profile.name if event.match.profile else "Global"
        app = event.foreground.executable or "unknown"
        return f"Foreground app     {app}\nActive profile      {name}\nMatch reason        {event.match.reason}"

    @pyqtSlot()
    def _poll_profile_switch(self) -> None:
        """Re-evaluate the foreground app; ``_on_profile_switch`` fires on change."""
        event = self.profile_switcher.poll()
        self._last_profile_event = event
        name = event.match.profile.name if event.match.profile else "Global"
        self.profile_status.setText(f"Active profile: {name}")

    def _on_profile_switch(self, event: ProfileSwitchEvent) -> None:
        """Fires only when the resolved profile actually changes (see ProfileSwitcher)."""
        if hasattr(self.camera, "apply_profile_settings"):
            self.camera.apply_profile_settings(event.effective_settings)

    @pyqtSlot()
    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings_manager.settings, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        settings = self.settings_manager.update(**dialog.values())
        if hasattr(self.camera, "update_settings"):
            self.camera.update_settings(settings)
        self.profile_switcher.set_enabled(settings.auto_switch_profiles)
        if settings.theme != self._theme_mode:
            self._theme_mode = settings.theme
            self.setStyleSheet(self._theme(self._theme_mode))
            self._sync_theme_button()
        self.statusBar().showMessage("Settings saved", 4000)

    @pyqtSlot()
    def toggle_theme(self) -> None:
        self._theme_mode = "light" if self._theme_mode == "dark" else "dark"
        self.settings_manager.update(theme=self._theme_mode)
        self.setStyleSheet(self._theme(self._theme_mode))
        self._sync_theme_button()

    def _sync_theme_button(self) -> None:
        self.theme_button.setText("Light mode" if self._theme_mode == "dark" else "Dark mode")

    @pyqtSlot()
    def toggle_recognition(self) -> None:
        self.stop_camera() if self.activation.is_active else self.start_camera()

    @pyqtSlot(str)
    def _clap_error(self, message: str) -> None:
        logger.warning("Clap detection unavailable: %s", message)
        self.microphone_status.setText("●  MICROPHONE UNAVAILABLE")
        self.microphone_status.setStyleSheet("color: #ef4444;")

    @pyqtSlot()
    def _microphone_started(self) -> None:
        self.microphone_status.setText("●  MICROPHONE READY")
        self.microphone_status.setStyleSheet("color: #10b981;")

    @pyqtSlot()
    def _microphone_stopped(self) -> None:
        self.microphone_status.setText("●  MICROPHONE OFF")
        self.microphone_status.setStyleSheet("")

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
        self.tray_icon.setToolTip(f"HandWave — {'Active' if active else 'Paused'}")
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
        if self._camera_error_pending:
            return
        self._set_status("Starting recognition…", "#fbbf24", animate=True)
        self.camera_status.setText("●  CAMERA STARTING")
        self.camera_status.setStyleSheet("color: #f59e0b;")
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
        self.camera_status.setText("●  CAMERA LIVE")
        self.camera_status.setStyleSheet("color: #10b981;")
        self.recognition_status.setText("●  RECOGNITION ACTIVE")
        self.recognition_status.setStyleSheet("color: #10b981;")
        self.diagnostics_page.set_pipeline_active(True)
        self._poll_profile_switch()
        self._profile_poll_timer.start()

    @pyqtSlot()
    def _camera_stopped(self) -> None:
        self._profile_poll_timer.stop()
        self.activation.deactivate()
        self.preview.clear()
        self.preview.setText("Camera preview is paused")
        camera_failed = self._camera_error_pending
        self._camera_error_pending = False
        self._set_status("Camera unavailable" if camera_failed else "Recognition Disabled", "#fb7185" if camera_failed else "#64748b")
        self.start_button.setEnabled(True)
        self.start_button.setText("Retry Camera" if camera_failed else "Enable Recognition")
        self.stop_button.setEnabled(False)
        self._set_tray_active(False)
        self.camera_status.setText("●  CAMERA ERROR" if camera_failed else "●  CAMERA IDLE")
        self.camera_status.setStyleSheet("color: #ef4444;" if camera_failed else "")
        self.recognition_status.setText("●  RECOGNITION OFF")
        self.recognition_status.setStyleSheet("")
        self.update_confidence(0.0)
        self.diagnostics_page.set_pipeline_active(False)
        self.diagnostics_page.update_gesture("Unknown", "Unknown")
        if self._exit_requested:
            self._complete_exit()

    @pyqtSlot(str)
    def _camera_error(self, message: str) -> None:
        logger.error("Camera error: %s", message)
        self._profile_poll_timer.stop()
        self._camera_error_pending = True
        self.activation.deactivate()
        self._set_status("Camera unavailable", "#fb7185")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self._set_tray_active(False)
        self.camera_status.setText("●  CAMERA ERROR")
        self.camera_status.setStyleSheet("color: #ef4444;")
        self.recognition_status.setText("●  RECOGNITION OFF")
        self.recognition_status.setStyleSheet("")
        self.diagnostics_page.set_pipeline_active(False)
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

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if not hasattr(self, "_content_layout"):
            return
        direction = (
            QBoxLayout.Direction.TopToBottom
            if event.size().width() < 980
            else QBoxLayout.Direction.LeftToRight
        )
        if self._content_layout.direction() != direction:
            self._content_layout.setDirection(direction)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._exit_requested:
            event.accept()
            return
        logger.info("Hiding HandWave in the system tray")
        event.ignore()
        self.hide()

    @pyqtSlot()
    def exit_application(self) -> None:
        if self._exit_requested:
            return
        self._exit_requested = True
        logger.info("Exiting HandWave")
        self._profile_poll_timer.stop()
        self.camera.stop_camera()
        self.clap_detector.stop()
        self.activation.deactivate()
        self.tray_icon.hide()
        self.hide()
        if not getattr(self.camera, "is_running", False):
            self._complete_exit()

    def _complete_exit(self) -> None:
        """Quit only after asynchronous camera workers have terminated."""
        app = QApplication.instance()
        if app is not None:
            app.quit()
