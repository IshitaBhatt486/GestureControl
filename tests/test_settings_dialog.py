from gestureos.config.settings_manager import AppSettings
from gestureos.ui.settings_dialog import SettingsDialog


def test_dialog_edits_sensitivity_binding_and_enabled_state(qtbot):
    dialog = SettingsDialog(AppSettings())
    qtbot.addWidget(dialog)

    dialog.sensitivity.setValue(0.8)
    dialog._gesture_actions["Fist"].setCurrentIndex(
        dialog._gesture_actions["Fist"].findData("play_pause")
    )
    dialog._gesture_enabled["Fist"].setChecked(True)
    dialog._gesture_enabled["Peace Sign"].setChecked(False)

    values = dialog.values()

    assert values["gesture_sensitivity"] == 0.8
    assert values["gesture_bindings"]["Fist"] == "play_pause"
    assert values["enabled_gestures"]["Fist"] is True
    assert values["enabled_gestures"]["Peace Sign"] is False
