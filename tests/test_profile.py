import pytest

from handwave.actions.action_definition import ActionDefinition
from handwave.config.profile import Profile, normalize_executable
from handwave.config.settings_manager import AppSettings


def test_normalize_executable_strips_path_and_case():
    assert normalize_executable("C:\\Program Files\\Spotify\\Spotify.EXE") == "spotify.exe"
    assert normalize_executable("chrome.exe") == "chrome.exe"


def test_default_profile_has_no_overrides():
    profile = Profile(name="Spotify")
    assert profile.enabled is True
    assert profile.gesture_bindings == {}
    assert profile.enabled_gestures == {}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": ""},
        {"name": "  "},
        {"app_executable": "   "},
        {"app_window_title_pattern": ""},
        {"gesture_sensitivity": 1.5},
        {"gesture_cooldown": -1},
        {"gesture_bindings": {"Not A Gesture": "play_pause"}},
        {"enabled_gestures": {"Not A Gesture": True}},
        {"enabled": "yes"},
    ],
)
def test_invalid_profile_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        Profile(name=kwargs.get("name", "Valid"), **{k: v for k, v in kwargs.items() if k != "name"})


def test_resolve_only_applies_explicit_overrides():
    profile = Profile(
        name="Spotify",
        app_executable="Spotify.exe",
        gesture_bindings={"Open Palm": "play_pause", "Swipe Left": "previous_track"},
    )
    global_settings = AppSettings(gesture_sensitivity=0.6, gesture_cooldown=1.0)

    resolved = profile.resolve(global_settings)

    assert resolved.gesture_sensitivity == 0.6  # inherited, not overridden
    assert resolved.gesture_bindings["Open Palm"] == ActionDefinition(type="media", value="play_pause")
    # Untouched gestures still come from the global configuration.
    assert resolved.gesture_bindings["Thumbs Up"] == global_settings.gesture_bindings["Thumbs Up"]


def test_resolve_overrides_sensitivity_and_cooldown_when_set():
    profile = Profile(name="Chrome", gesture_sensitivity=0.9, gesture_cooldown=2.5)
    global_settings = AppSettings(gesture_sensitivity=0.6, gesture_cooldown=1.0)

    resolved = profile.resolve(global_settings)

    assert resolved.gesture_sensitivity == 0.9
    assert resolved.gesture_cooldown == 2.5


def test_reset_overrides_clears_everything_but_identity():
    profile = Profile(
        name="Chrome",
        app_executable="chrome.exe",
        gesture_sensitivity=0.9,
        gesture_bindings={"Open Palm": "mute"},
    )
    reset = profile.reset_overrides()

    assert reset.profile_id == profile.profile_id
    assert reset.app_executable == "chrome.exe"
    assert reset.gesture_sensitivity is None
    assert reset.gesture_bindings == {}


def test_duplicate_creates_independent_copy_with_new_id():
    original = Profile(name="Spotify", gesture_bindings={"Open Palm": "play_pause"})
    copy = original.duplicate()

    assert copy.profile_id != original.profile_id
    assert copy.name == "Spotify (copy)"
    assert copy.gesture_bindings == original.gesture_bindings

    # Mutating one profile's dict must never affect the other (no shared references).
    copy.gesture_bindings["Fist"] = ActionDefinition(type="media", value="mute")
    assert "Fist" not in original.gesture_bindings


def test_copy_overrides_from_keeps_target_identity_but_adopts_source_overrides():
    target = Profile(name="Chrome", app_executable="chrome.exe")
    source = Profile(name="Spotify", app_executable="spotify.exe", gesture_sensitivity=0.8)

    merged = target.copy_overrides_from(source)

    assert merged.profile_id == target.profile_id
    assert merged.app_executable == "chrome.exe"  # target's own identity preserved
    assert merged.gesture_sensitivity == 0.8  # source's overrides adopted

    merged.gesture_bindings.get("Open Palm")  # no KeyError; just confirms dict shape
    source_copy = merged.gesture_bindings
    assert source_copy is not source.gesture_bindings


def test_to_dict_and_from_data_round_trip():
    profile = Profile(
        name="PowerPoint",
        app_executable="POWERPNT.EXE",
        app_window_title_pattern="PowerPoint",
        gesture_bindings={"Swipe Left": "previous_track"},
        enabled_gestures={"Swipe Left": True},
    )
    restored = Profile.from_data(profile.to_dict())
    assert restored == profile


def test_from_data_rejects_unknown_fields_and_bad_shape():
    with pytest.raises(ValueError):
        Profile.from_data({"name": "X", "bogus": True})
    with pytest.raises(ValueError):
        Profile.from_data("not a dict")
    with pytest.raises(ValueError):
        Profile.from_data({"name": "X", "gesture_bindings": "not a dict"})
