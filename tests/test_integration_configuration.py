from unittest.mock import MagicMock

from handwave.actions.action_mapper import ActionMapper
from handwave.config.settings_manager import SettingsManager


def test_persisted_binding_drives_action_execution_after_restart(tmp_path):
    path = tmp_path / "settings.json"
    manager = SettingsManager(path)
    bindings = manager.settings.gesture_bindings.copy()
    bindings["Open Palm"] = "next_track"
    manager.update(gesture_bindings=bindings)

    restored = SettingsManager(path).settings
    keyboard = MagicMock()
    mapper = ActionMapper(
        gesture_bindings=restored.gesture_bindings,
        enabled_gestures=restored.enabled_gestures,
        pyautogui_module=MagicMock(),
        keyboard_module=keyboard,
    )

    assert mapper.execute("Open Palm")
    keyboard.send.assert_called_once_with("next track")
