from unittest.mock import MagicMock

import pytest

from handwave.actions.action_definition import ActionDefinition
from handwave.actions.action_executor import ActionExecutor


def _executor():
    gui = MagicMock()
    keys = MagicMock()
    launcher = MagicMock()
    executor = ActionExecutor(pyautogui_module=gui, keyboard_module=keys, program_launcher=launcher)
    return executor, gui, keys, launcher


def test_none_action_does_nothing():
    executor, gui, keys, launcher = _executor()
    executor.execute(ActionDefinition())
    gui.press.assert_not_called()
    launcher.assert_not_called()


def test_key_action_presses_single_key():
    executor, gui, _, _ = _executor()
    executor.execute(ActionDefinition(type="key", value="F5"))
    gui.press.assert_called_once_with("f5")


def test_hotkey_action_sends_combination_in_order():
    executor, gui, _, _ = _executor()
    executor.execute(ActionDefinition(type="hotkey", value="Ctrl+Shift+S"))
    gui.hotkey.assert_called_once_with("ctrl", "shift", "s")


@pytest.mark.parametrize(
    "value,method,args",
    [
        ("left_click", "click", {"button": "left"}),
        ("right_click", "click", {"button": "right"}),
        ("middle_click", "click", {"button": "middle"}),
    ],
)
def test_mouse_click_actions(value, method, args):
    executor, gui, _, _ = _executor()
    executor.execute(ActionDefinition(type="mouse", value=value))
    getattr(gui, method).assert_called_once_with(**args)


def test_mouse_scroll_actions():
    executor, gui, _, _ = _executor()
    executor.execute(ActionDefinition(type="mouse", value="scroll_up"))
    gui.scroll.assert_called_once_with(1)
    executor.execute(ActionDefinition(type="mouse", value="scroll_down"))
    gui.scroll.assert_called_with(-1)


def test_text_action_types_the_configured_string():
    executor, gui, _, _ = _executor()
    executor.execute(ActionDefinition(type="text", value="hello world"))
    gui.write.assert_called_once_with("hello world")


def test_command_action_launches_without_a_shell():
    executor, _, _, launcher = _executor()
    action = ActionDefinition(type="command", value="notepad.exe file.txt", requires_confirmation=True)
    executor.execute(action)
    launcher.assert_called_once_with(["notepad.exe", "file.txt"], shell=False)


def test_media_actions_use_pyautogui_for_transport_keys():
    executor, gui, keys, _ = _executor()
    executor.execute(ActionDefinition(type="media", value="play_pause"))
    gui.press.assert_called_with("playpause")
    executor.execute(ActionDefinition(type="media", value="next_track"))
    keys.send.assert_called_with("next track")


def test_media_next_track_falls_back_when_keyboard_module_missing():
    gui = MagicMock()
    executor = ActionExecutor(pyautogui_module=gui, keyboard_module=None, program_launcher=MagicMock())
    executor.execute(ActionDefinition(type="media", value="next_track"))
    gui.press.assert_called_with("nexttrack")


def test_callback_for_defers_execution_until_invoked():
    executor, gui, _, _ = _executor()
    callback = executor.callback_for(ActionDefinition(type="key", value="Enter"))
    gui.press.assert_not_called()
    callback()
    gui.press.assert_called_once_with("enter")


def test_keyboard_input_failure_uses_low_level_fallback():
    executor, gui, keys, _ = _executor()
    gui.hotkey.side_effect = OSError("desktop unavailable")

    executor.execute(ActionDefinition(type="hotkey", value="Win+Tab"))

    keys.send.assert_called_once_with("win+tab")
