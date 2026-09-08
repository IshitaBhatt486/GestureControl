"""User-facing gesture binding and recognition settings editor."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from handwave.actions.action_definition import (
    ACTION_TYPES,
    MEDIA_ACTIONS,
    MOUSE_ACTIONS,
    ActionDefinition,
)
from handwave.config.gesture_config import GESTURES
from handwave.config.settings_manager import AppSettings

_TEXT_VALUE_TYPES = {"key", "hotkey", "text", "command"}


class ActionEditorRow(QWidget):
    """One gesture's enabled state plus its full action definition editor."""

    def __init__(self, gesture: str, binding: ActionDefinition, enabled: bool) -> None:
        super().__init__()
        self.gesture = gesture

        self.enabled_checkbox = QCheckBox(gesture)
        self.enabled_checkbox.setChecked(enabled)

        self.type_combo = QComboBox()
        for action_type, label in ACTION_TYPES.items():
            self.type_combo.addItem(label, action_type)

        self.media_combo = QComboBox()
        for value, label in MEDIA_ACTIONS.items():
            self.media_combo.addItem(label, value)

        self.mouse_combo = QComboBox()
        for value, label in MOUSE_ACTIONS.items():
            self.mouse_combo.addItem(label, value)

        self.text_value = QLineEdit()
        self.text_value.setPlaceholderText("e.g. ctrl+shift+s, Space, hello world, notepad.exe")

        self.value_stack = QStackedWidget()
        self.value_stack.addWidget(QLabel(""))  # none
        self.value_stack.addWidget(self.media_combo)
        self.value_stack.addWidget(self.text_value)  # key
        self.value_stack.addWidget(self.text_value)  # hotkey (shared widget, index unused directly)
        self.value_stack.addWidget(self.mouse_combo)
        self.value_stack.addWidget(self.text_value)  # text
        self.value_stack.addWidget(self.text_value)  # command

        self.confirmation_checkbox = QCheckBox("Confirm")
        self.confirmation_checkbox.setToolTip(
            "Require a hold before this action fires (recommended for destructive actions)"
        )

        self.hold_spin = QDoubleSpinBox()
        self.hold_spin.setRange(0.0, 10.0)
        self.hold_spin.setSingleStep(0.1)
        self.hold_spin.setSuffix(" s")
        self.hold_spin.setToolTip("Hold duration before this gesture's action fires")

        self.cooldown_spin = QDoubleSpinBox()
        self.cooldown_spin.setRange(0.0, 60.0)
        self.cooldown_spin.setSingleStep(0.1)
        self.cooldown_spin.setSuffix(" s")
        self.cooldown_spin.setSpecialValueText("Default")
        self.cooldown_spin.setToolTip("Per-gesture cooldown override; 0 uses the global cooldown")

        self._load(binding)
        self.enabled_checkbox.toggled.connect(self._set_row_enabled)
        self.type_combo.currentIndexChanged.connect(self._sync_value_widget)
        self._set_row_enabled(enabled)
        self._sync_value_widget()

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.enabled_checkbox, 2)
        row.addWidget(self.type_combo, 2)
        row.addWidget(self.value_stack, 3)
        row.addWidget(self.confirmation_checkbox, 1)
        row.addWidget(self.hold_spin, 1)
        row.addWidget(self.cooldown_spin, 1)

    def _load(self, binding: ActionDefinition) -> None:
        self.type_combo.setCurrentIndex(self.type_combo.findData(binding.type))
        if binding.type == "media":
            self.media_combo.setCurrentIndex(self.media_combo.findData(binding.value))
        elif binding.type == "mouse":
            self.mouse_combo.setCurrentIndex(self.mouse_combo.findData(binding.value))
        elif binding.type in _TEXT_VALUE_TYPES:
            value = binding.value
            self.text_value.setText(" ".join(value) if isinstance(value, tuple) else str(value))
        self.confirmation_checkbox.setChecked(binding.requires_confirmation)
        self.hold_spin.setValue(binding.hold_duration)
        self.cooldown_spin.setValue(binding.cooldown if binding.cooldown is not None else 0.0)

    def _current_type(self) -> str:
        return str(self.type_combo.currentData())

    def _sync_value_widget(self) -> None:
        action_type = self._current_type()
        widget = {
            "none": self.value_stack.widget(0),
            "media": self.media_combo,
            "key": self.text_value,
            "hotkey": self.text_value,
            "mouse": self.mouse_combo,
            "text": self.text_value,
            "command": self.text_value,
        }[action_type]
        self.value_stack.setCurrentWidget(widget)
        dangerous = action_type == "command"
        if dangerous:
            self.confirmation_checkbox.setChecked(True)
        self.confirmation_checkbox.setEnabled(not dangerous)

    def _set_row_enabled(self, enabled: bool) -> None:
        for widget in (
            self.type_combo,
            self.value_stack,
            self.confirmation_checkbox,
            self.hold_spin,
            self.cooldown_spin,
        ):
            widget.setEnabled(enabled)
        if enabled:
            self._sync_value_widget()

    def action_dict(self) -> dict[str, object]:
        action_type = self._current_type()
        if action_type == "media":
            value: object = self.media_combo.currentData()
        elif action_type == "mouse":
            value = self.mouse_combo.currentData()
        elif action_type in _TEXT_VALUE_TYPES:
            value = self.text_value.text()
        else:
            value = ""
        cooldown = self.cooldown_spin.value()
        return {
            "type": action_type,
            "value": value,
            "requires_confirmation": self.confirmation_checkbox.isChecked(),
            "hold_duration": self.hold_spin.value(),
            "cooldown": cooldown if cooldown > 0.0 else None,
        }


class SettingsDialog(QDialog):
    """Edit persisted settings, organized into sections by concern.

    Sections reflect what is actually implemented today: gestures and their
    actions share one editor row per gesture (the model is 1:1, not two
    independent lists), so they live in a single "Gestures & Actions" tab
    rather than being split artificially. Startup behavior stays on the tray
    menu (its own toggle already round-trips through
    ``SettingsManager.set_startup_enabled``, which also updates the Windows
    Startup launcher — duplicating it here risked the two falling out of
    sync). Microphone calibration and Application Profile/Custom Gesture
    editors are follow-on work: their backends exist
    (``ClapDetector.status()``/calibration, ``ProfileManager``,
    ``CustomGestureStore``) but have no dedicated editor UI yet.
    """

    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("HandWave Settings")
        self.setMinimumWidth(760)
        self.setMinimumHeight(560)
        self._gesture_rows: dict[str, ActionEditorRow] = {}

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(settings), "General")
        tabs.addTab(self._build_camera_tab(settings), "Camera")
        tabs.addTab(self._build_gestures_tab(settings), "Gestures && Actions")
        tabs.addTab(self._build_appearance_tab(settings), "Appearance")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

    def _build_general_tab(self, settings: AppSettings) -> QWidget:
        self.sensitivity = QDoubleSpinBox()
        self.sensitivity.setRange(0.0, 1.0)
        self.sensitivity.setSingleStep(0.05)
        self.sensitivity.setDecimals(2)
        self.sensitivity.setValue(settings.gesture_sensitivity)
        self.sensitivity.setToolTip("MediaPipe hand detection and tracking confidence threshold")

        self.cooldown = QDoubleSpinBox()
        self.cooldown.setRange(0.0, 60.0)
        self.cooldown.setSingleStep(0.1)
        self.cooldown.setSuffix(" s")
        self.cooldown.setValue(settings.gesture_cooldown)
        self.cooldown.setToolTip("Global minimum time between actions; a gesture can override this")

        self.auto_switch_profiles = QCheckBox("Automatically switch application profiles")
        self.auto_switch_profiles.setChecked(settings.auto_switch_profiles)
        self.auto_switch_profiles.setToolTip(
            "Apply a matching application profile's overrides when that application is focused"
        )

        widget = QWidget()
        form = QFormLayout(widget)
        form.addRow("Sensitivity", self.sensitivity)
        form.addRow("Cooldown", self.cooldown)
        form.addRow(self.auto_switch_profiles)
        return widget

    def _build_camera_tab(self, settings: AppSettings) -> QWidget:
        self.camera_index = QSpinBox()
        self.camera_index.setRange(0, 8)
        self.camera_index.setValue(settings.camera_index)
        self.camera_index.setToolTip("Index of the capture device to use, in OS enumeration order")

        widget = QWidget()
        form = QFormLayout(widget)
        form.addRow("Camera index", self.camera_index)
        note = QLabel("Applies the next time recognition is enabled.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #94a3b8;")
        form.addRow(note)
        return widget

    def _build_gestures_tab(self, settings: AppSettings) -> QWidget:
        gestures = QWidget()
        gesture_layout = QVBoxLayout(gestures)
        header = QHBoxLayout()
        for text in ("Gesture", "Action type", "Value", "", "Hold", "Cooldown"):
            header.addWidget(QLabel(text))
        gesture_layout.addLayout(header)
        for gesture in GESTURES:
            row = ActionEditorRow(
                gesture,
                settings.gesture_bindings[gesture],
                settings.enabled_gestures[gesture],
            )
            gesture_layout.addWidget(row)
            self._gesture_rows[gesture] = row
        gesture_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(gestures)

        note = QLabel(
            "Program launches and potentially destructive combinations (e.g. Alt+F4) "
            "always require a hold."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #94a3b8;")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(scroll, 1)
        layout.addWidget(note)
        return container

    def _build_appearance_tab(self, settings: AppSettings) -> QWidget:
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.setCurrentIndex(self.theme_combo.findData(settings.theme))

        widget = QWidget()
        form = QFormLayout(widget)
        form.addRow("Theme", self.theme_combo)
        return widget

    def values(self) -> dict[str, object]:
        return {
            "gesture_sensitivity": self.sensitivity.value(),
            "gesture_cooldown": self.cooldown.value(),
            "auto_switch_profiles": self.auto_switch_profiles.isChecked(),
            "camera_index": self.camera_index.value(),
            "theme": self.theme_combo.currentData(),
            "gesture_bindings": {
                gesture: row.action_dict() for gesture, row in self._gesture_rows.items()
            },
            "enabled_gestures": {
                gesture: row.enabled_checkbox.isChecked()
                for gesture, row in self._gesture_rows.items()
            },
        }
