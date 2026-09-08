from PyQt6.QtWidgets import QTabWidget

from handwave.config.settings_manager import AppSettings
from handwave.ui.settings_dialog import SettingsDialog


def test_dialog_edits_sensitivity_binding_and_enabled_state(qtbot):
    dialog = SettingsDialog(AppSettings())
    qtbot.addWidget(dialog)

    dialog.sensitivity.setValue(0.8)
    row = dialog._gesture_rows["Fist"]
    row.type_combo.setCurrentIndex(row.type_combo.findData("media"))
    row.media_combo.setCurrentIndex(row.media_combo.findData("play_pause"))
    row.enabled_checkbox.setChecked(True)
    dialog._gesture_rows["Peace Sign"].enabled_checkbox.setChecked(False)

    values = dialog.values()

    assert values["gesture_sensitivity"] == 0.8
    assert values["gesture_bindings"]["Fist"]["type"] == "media"
    assert values["gesture_bindings"]["Fist"]["value"] == "play_pause"
    assert values["enabled_gestures"]["Fist"] is True
    assert values["enabled_gestures"]["Peace Sign"] is False
    assert values["auto_switch_profiles"] is True


def test_dialog_toggles_auto_switch_profiles(qtbot):
    dialog = SettingsDialog(AppSettings())
    qtbot.addWidget(dialog)

    dialog.auto_switch_profiles.setChecked(False)

    assert dialog.values()["auto_switch_profiles"] is False


def test_dialog_is_organized_into_sections(qtbot):
    dialog = SettingsDialog(AppSettings())
    qtbot.addWidget(dialog)

    tabs = dialog.findChild(QTabWidget)
    labels = [tabs.tabText(index) for index in range(tabs.count())]
    assert labels == ["General", "Camera", "Gestures && Actions", "Appearance"]


def test_dialog_edits_camera_index_and_theme(qtbot):
    dialog = SettingsDialog(AppSettings())
    qtbot.addWidget(dialog)

    dialog.camera_index.setValue(2)
    dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData("light"))

    values = dialog.values()
    assert values["camera_index"] == 2
    assert values["theme"] == "light"


def test_dialog_edits_global_cooldown(qtbot):
    dialog = SettingsDialog(AppSettings())
    qtbot.addWidget(dialog)

    dialog.cooldown.setValue(2.5)

    assert dialog.values()["gesture_cooldown"] == 2.5


def test_dialog_supports_keyboard_hotkey_action(qtbot):
    dialog = SettingsDialog(AppSettings())
    qtbot.addWidget(dialog)

    row = dialog._gesture_rows["Swipe Right"]
    row.enabled_checkbox.setChecked(True)
    row.type_combo.setCurrentIndex(row.type_combo.findData("hotkey"))
    row.text_value.setText("ctrl+pagedown")

    binding = dialog.values()["gesture_bindings"]["Swipe Right"]
    assert binding["type"] == "hotkey"
    assert binding["value"] == "ctrl+pagedown"


def test_dialog_forces_confirmation_for_command_actions(qtbot):
    dialog = SettingsDialog(AppSettings())
    qtbot.addWidget(dialog)

    row = dialog._gesture_rows["Pointing"]
    row.enabled_checkbox.setChecked(True)
    row.type_combo.setCurrentIndex(row.type_combo.findData("command"))

    assert row.confirmation_checkbox.isChecked()
    assert not row.confirmation_checkbox.isEnabled()
