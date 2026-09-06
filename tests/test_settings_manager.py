import json

import pytest

from gestureos.config.settings_manager import AppSettings, SettingsManager
from gestureos.config.gesture_config import (
    DEFAULT_ENABLED_GESTURES,
    DEFAULT_GESTURE_BINDINGS,
)
from gestureos.vision.camera_manager import CameraManager


def test_changed_settings_persist_after_restart(tmp_path):
    path = tmp_path / "config" / "settings.json"
    first_app = SettingsManager(path)
    first_app.update(
        camera_index=2,
        gesture_sensitivity=0.8,
        gesture_cooldown=1.5,
        startup_enabled=True,
        overlay_enabled=False,
    )

    restarted_app = SettingsManager(path)
    assert restarted_app.settings == AppSettings(
        camera_index=2,
        gesture_sensitivity=0.8,
        gesture_cooldown=1.5,
        startup_enabled=True,
        overlay_enabled=False,
    )
    assert CameraManager(settings=restarted_app.settings).camera_index == 2


def test_file_contains_only_supported_settings(tmp_path):
    path = tmp_path / "settings.json"
    manager = SettingsManager(path)
    manager.update(gesture_cooldown=2.0)
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "camera_index": 0,
        "gesture_sensitivity": 0.6,
        "gesture_cooldown": 2.0,
        "startup_enabled": False,
        "overlay_enabled": True,
        "gesture_bindings": DEFAULT_GESTURE_BINDINGS,
        "enabled_gestures": DEFAULT_ENABLED_GESTURES,
        "theme": "dark",
    }


def test_invalid_and_unknown_settings_are_rejected(tmp_path):
    manager = SettingsManager(tmp_path / "settings.json")
    with pytest.raises(ValueError):
        manager.update(gesture_sensitivity=1.5)
    with pytest.raises(KeyError):
        manager.update(not_a_setting=True)
    with pytest.raises(ValueError):
        manager.update(theme="system")


def test_invalid_json_falls_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("not json", encoding="utf-8")
    assert SettingsManager(path).settings == AppSettings()


def test_partial_legacy_gesture_configuration_is_migrated(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({
        "gesture_sensitivity": 0.75,
        "gesture_bindings": {"Fist": "play_pause"},
        "enabled_gestures": {"Fist": True},
    }), encoding="utf-8")

    settings = SettingsManager(path).settings

    assert settings.gesture_sensitivity == 0.75
    assert settings.gesture_bindings["Fist"] == "play_pause"
    assert settings.enabled_gestures["Fist"] is True
    assert settings.gesture_bindings["Open Palm"] == "play_pause"


def test_gesture_rebinding_and_enabled_state_persist(tmp_path):
    path = tmp_path / "settings.json"
    manager = SettingsManager(path)
    bindings = manager.settings.gesture_bindings.copy()
    enabled = manager.settings.enabled_gestures.copy()
    bindings["Fist"] = "play_pause"
    enabled["Fist"] = True
    enabled["Thumbs Down"] = False

    manager.update(gesture_bindings=bindings, enabled_gestures=enabled)
    restored = SettingsManager(path).settings

    assert restored.gesture_bindings["Fist"] == "play_pause"
    assert restored.enabled_gestures["Fist"] is True
    assert restored.enabled_gestures["Thumbs Down"] is False
