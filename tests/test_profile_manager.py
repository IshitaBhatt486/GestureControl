import json

import pytest

from handwave.config.profile import Profile
from handwave.config.profile_manager import ProfileManager, SCHEMA_VERSION


def test_first_run_has_no_profiles(tmp_path):
    manager = ProfileManager(tmp_path / "profiles.json")
    assert manager.list_profiles() == []
    assert manager.get_active_profile() is None


def test_create_profile_persists_after_restart(tmp_path):
    path = tmp_path / "profiles.json"
    manager = ProfileManager(path)
    profile = manager.create_profile("Spotify", app_executable="spotify.exe")

    restarted = ProfileManager(path)
    assert restarted.get_profile(profile.profile_id) == profile
    assert len(restarted.list_profiles()) == 1


def test_update_edit_and_delete_profile(tmp_path):
    manager = ProfileManager(tmp_path / "profiles.json")
    profile = manager.create_profile("Chrome", app_executable="chrome.exe")

    updated = manager.update_profile(profile.profile_id, gesture_sensitivity=0.9)
    assert updated.gesture_sensitivity == 0.9

    manager.delete_profile(profile.profile_id)
    assert manager.list_profiles() == []
    with pytest.raises(KeyError):
        manager.update_profile(profile.profile_id, gesture_sensitivity=0.1)


def test_duplicate_profile_is_independent(tmp_path):
    manager = ProfileManager(tmp_path / "profiles.json")
    original = manager.create_profile(
        "Spotify", app_executable="spotify.exe", gesture_bindings={"Open Palm": "play_pause"}
    )
    copy = manager.duplicate_profile(original.profile_id)

    assert copy.profile_id != original.profile_id
    manager.update_profile(copy.profile_id, gesture_bindings={"Open Palm": "mute"})

    assert manager.get_profile(original.profile_id).gesture_bindings["Open Palm"].value == "play_pause"
    assert manager.get_profile(copy.profile_id).gesture_bindings["Open Palm"].value == "mute"


def test_copy_settings_from_another_profile_creates_independent_copy(tmp_path):
    manager = ProfileManager(tmp_path / "profiles.json")
    source = manager.create_profile("Spotify", app_executable="spotify.exe", gesture_sensitivity=0.9)
    target = manager.create_profile("New Profile", app_executable="notepad.exe")

    merged = manager.copy_settings_from(target.profile_id, source.profile_id)

    assert merged.app_executable == "notepad.exe"
    assert merged.gesture_sensitivity == 0.9

    manager.update_profile(source.profile_id, gesture_sensitivity=0.1)
    assert manager.get_profile(target.profile_id).gesture_sensitivity == 0.9


def test_enable_disable_and_reset_overrides(tmp_path):
    manager = ProfileManager(tmp_path / "profiles.json")
    profile = manager.create_profile("Chrome", gesture_sensitivity=0.9)

    disabled = manager.set_enabled(profile.profile_id, False)
    assert disabled.enabled is False

    reset = manager.reset_overrides(profile.profile_id)
    assert reset.gesture_sensitivity is None


def test_active_profile_selection(tmp_path):
    manager = ProfileManager(tmp_path / "profiles.json")
    profile = manager.create_profile("Spotify")

    manager.set_active_profile(profile.profile_id)
    assert manager.get_active_profile() == profile

    manager.set_active_profile(None)
    assert manager.get_active_profile() is None

    with pytest.raises(KeyError):
        manager.set_active_profile("does-not-exist")


def test_import_export_round_trip(tmp_path):
    manager = ProfileManager(tmp_path / "profiles.json")
    original = manager.create_profile("Spotify", app_executable="spotify.exe")
    export_path = tmp_path / "spotify.json"
    manager.export_profile(original.profile_id, export_path)

    other_manager = ProfileManager(tmp_path / "other_profiles.json")
    imported = other_manager.import_profile(export_path)

    assert imported.profile_id != original.profile_id  # always assigned a fresh id
    assert imported.name == original.name
    assert imported.app_executable == original.app_executable


def test_corrupted_primary_file_recovers_from_backup(tmp_path):
    path = tmp_path / "profiles.json"
    manager = ProfileManager(path)
    manager.create_profile("Spotify")
    manager.create_profile("Chrome")  # second save creates a .bak of the first save

    path.write_text("not json", encoding="utf-8")

    recovered = ProfileManager(path)
    assert len(recovered.list_profiles()) == 1  # backup holds the state before the last save


def test_fully_corrupted_state_with_no_backup_starts_empty(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text("not json", encoding="utf-8")
    manager = ProfileManager(path)
    assert manager.list_profiles() == []


def test_legacy_payload_without_schema_version_is_migrated(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text(
        json.dumps({"profiles": [Profile(name="Spotify").to_dict()], "active_profile_id": None}),
        encoding="utf-8",
    )
    manager = ProfileManager(path)
    assert len(manager.list_profiles()) == 1

    # Re-saving upgrades the on-disk schema version.
    manager.update_profile(manager.list_profiles()[0].profile_id, gesture_sensitivity=0.5)
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == SCHEMA_VERSION
