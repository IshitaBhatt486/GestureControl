from unittest.mock import MagicMock

import pytest

from gestureos.actions.action_mapper import ActionMapper


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
