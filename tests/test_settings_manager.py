import json

import pytest

from gestureos.config.settings_manager import AppSettings, SettingsManager
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
    }


def test_invalid_and_unknown_settings_are_rejected(tmp_path):
    manager = SettingsManager(tmp_path / "settings.json")
    with pytest.raises(ValueError):
        manager.update(gesture_sensitivity=1.5)
    with pytest.raises(KeyError):
        manager.update(not_a_setting=True)


def test_invalid_json_falls_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("not json", encoding="utf-8")
    assert SettingsManager(path).settings == AppSettings()
