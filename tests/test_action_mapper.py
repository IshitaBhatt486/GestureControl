from unittest.mock import MagicMock

import pytest

from handwave.actions.action_mapper import ActionMapper


def _mapper(times=(0.0,), cooldown=1.0):
    gui = MagicMock()
    keys = MagicMock()
    mapper = ActionMapper(
        cooldown=cooldown,
        clock=iter(times).__next__,
        pyautogui_module=gui,
        keyboard_module=keys,
    )
    return mapper, gui, keys


def test_all_gestures_fire_the_correct_media_keys():
    mapper, gui, keys = _mapper(times=(0.0, 1.0, 2.0, 3.0, 4.0))
    for gesture in ("Open Palm", "Thumbs Up", "Thumbs Down", "Peace Sign", "Pointing"):
        assert mapper.execute(gesture)

    assert [call.args[0] for call in gui.press.call_args_list] == [
        "playpause", "volumeup", "volumedown"
    ]
    assert [call.args[0] for call in keys.send.call_args_list] == ["next track", "previous track"]


def test_cooldown_blocks_different_gesture_until_one_second_passes():
    mapper, gui, _ = _mapper(times=(10.0, 10.5, 11.5))
    assert mapper.execute("Open Palm")
    assert not mapper.execute("Thumbs Up")
    assert mapper.execute("Peace Sign")
    assert gui.press.call_count == 1


def test_held_gesture_never_rapidly_repeats_and_neutral_pose_rearms_it():
    mapper, gui, _ = _mapper(times=(0.0, 5.0))
    assert mapper.execute("Thumbs Up")
    assert not mapper.execute("Thumbs Up")
    assert not mapper.execute("Thumbs Up")
    assert gui.press.call_count == 1
    assert not mapper.execute("Unknown")
    assert mapper.execute("Thumbs Up")
    assert gui.press.call_count == 2


def test_default_cooldown_and_invalid_value():
    mapper, _, _ = _mapper()
    assert mapper.cooldown == 1.0
    with pytest.raises(ValueError):
        ActionMapper(cooldown=-0.1)


def test_json_style_binding_reassigns_gesture_action():
    mapper, gui, _ = _mapper()
    mapper._gesture_bindings["Open Palm"] = "volume_down"

    assert mapper.execute("Open Palm")
    gui.press.assert_called_once_with("volumedown")


def test_apply_settings_swaps_bindings_in_place_without_recreating_mapper():
    mapper, gui, _ = _mapper(times=(0.0, 1.0))
    original_executor = mapper._executor
    mapper.apply_settings(
        cooldown=5.0,
        gesture_bindings={"Open Palm": "mute"},
        enabled_gestures={"Open Palm": True},
    )

    assert mapper.cooldown == 5.0
    assert mapper._executor is original_executor
    assert mapper.execute("Open Palm")
    gui.press.assert_called_once_with("volumemute")


def test_apply_settings_partial_update_only_changes_given_fields():
    mapper, _, _ = _mapper()
    mapper.apply_settings(cooldown=3.0)
    assert mapper.cooldown == 3.0
    assert mapper._enabled_gestures


def test_apply_settings_rejects_negative_cooldown():
    mapper, _, _ = _mapper()
    with pytest.raises(ValueError):
        mapper.apply_settings(cooldown=-1.0)


def test_disabled_gesture_never_executes():
    gui = MagicMock()
    mapper = ActionMapper(
        pyautogui_module=gui,
        keyboard_module=MagicMock(),
        enabled_gestures={"Open Palm": False},
    )

    assert not mapper.execute("Open Palm")
    gui.press.assert_not_called()
    assert mapper.last_outcome.blocked_reason == "gesture disabled"


def test_last_outcome_reports_cooldown_active():
    mapper, _, _ = _mapper(times=(10.0, 10.5))
    assert mapper.execute("Open Palm")
    assert not mapper.execute("Thumbs Up")
    assert mapper.last_outcome.gesture == "Thumbs Up"
    assert mapper.last_outcome.executed is False
    assert mapper.last_outcome.blocked_reason == "cooldown active"


def test_last_outcome_reports_not_re_armed():
    mapper, _, _ = _mapper(times=(0.0, 5.0))
    assert mapper.execute("Thumbs Up")
    assert not mapper.execute("Thumbs Up")
    assert mapper.last_outcome.blocked_reason == "gesture not re-armed"


def test_last_outcome_reports_no_action_bound():
    gui = MagicMock()
    mapper = ActionMapper(
        pyautogui_module=gui,
        keyboard_module=MagicMock(),
        gesture_bindings={"Fist": "none"},
        enabled_gestures={"Fist": True},
    )
    assert not mapper.execute("Fist")
    assert mapper.last_outcome.blocked_reason == "no action bound"


def test_last_outcome_reports_hold_duration_not_met():
    gui = MagicMock()
    mapper = ActionMapper(
        cooldown=0.0,
        clock=iter((0.0, 0.1)).__next__,
        pyautogui_module=gui,
        keyboard_module=MagicMock(),
        gesture_bindings={"Open Palm": {"type": "media", "value": "play_pause", "hold_duration": 1.0}},
    )
    assert not mapper.execute("Open Palm")
    assert mapper.last_outcome.blocked_reason == "hold duration not met"


def test_last_outcome_reports_action_failure():
    gui = MagicMock()
    gui.press.side_effect = RuntimeError("boom")
    mapper = ActionMapper(pyautogui_module=gui, keyboard_module=MagicMock())
    assert not mapper.execute("Open Palm")
    assert mapper.last_outcome.executed is False
    assert "boom" in mapper.last_outcome.blocked_reason


def test_last_outcome_reports_success():
    mapper, gui, _ = _mapper()
    assert mapper.execute("Open Palm")
    assert mapper.last_outcome.executed is True
    assert mapper.last_outcome.blocked_reason is None
    assert mapper.last_outcome.action_description == "Play / Pause"
