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
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from gestureos.config.gesture_config import ACTIONS, GESTURES
from gestureos.config.settings_manager import AppSettings


class SettingsDialog(QDialog):
    """Edit persisted recognition sensitivity and per-gesture behavior."""

    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GestureOS Settings")
        self.setMinimumWidth(540)
        self._gesture_enabled: dict[str, QCheckBox] = {}
        self._gesture_actions: dict[str, QComboBox] = {}

        self.sensitivity = QDoubleSpinBox()
        self.sensitivity.setRange(0.0, 1.0)
        self.sensitivity.setSingleStep(0.05)
        self.sensitivity.setDecimals(2)
        self.sensitivity.setValue(settings.gesture_sensitivity)
        self.sensitivity.setToolTip("MediaPipe hand detection and tracking confidence threshold")

        general = QGroupBox("Recognition")
        general_form = QFormLayout(general)
        general_form.addRow("Sensitivity", self.sensitivity)

        gestures = QGroupBox("Gesture bindings")
        gesture_layout = QVBoxLayout(gestures)
        for gesture in GESTURES:
            enabled = QCheckBox(gesture)
            enabled.setChecked(settings.enabled_gestures[gesture])
            action = QComboBox()
            for action_id, label in ACTIONS.items():
                action.addItem(label, action_id)
            action.setCurrentIndex(action.findData(settings.gesture_bindings[gesture]))
            action.setEnabled(enabled.isChecked())
            enabled.toggled.connect(action.setEnabled)

            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(enabled, 1)
            row_layout.addWidget(action, 1)
            gesture_layout.addWidget(row)
            self._gesture_enabled[gesture] = enabled
            self._gesture_actions[gesture] = action

        note = QLabel("Changes apply the next time recognition is enabled.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #94a3b8;")
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(general)
        layout.addWidget(gestures)
        layout.addWidget(note)
        layout.addWidget(buttons)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

    def values(self) -> dict[str, object]:
        return {
            "gesture_sensitivity": self.sensitivity.value(),
            "gesture_bindings": {
                gesture: str(combo.currentData())
                for gesture, combo in self._gesture_actions.items()
            },
            "enabled_gestures": {
                gesture: checkbox.isChecked()
                for gesture, checkbox in self._gesture_enabled.items()
            },
        }
