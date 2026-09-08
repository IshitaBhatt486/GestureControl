"""Local execution backend for validated action definitions."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from typing import Any

import pyautogui

from handwave.actions.action_definition import ActionDefinition, parse_hotkey

try:
    import keyboard
except ImportError:
    keyboard = None

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Execute one validated action locally without invoking a command shell."""

    def __init__(
        self,
        pyautogui_module: Any = pyautogui,
        keyboard_module: Any = keyboard,
        program_launcher: Callable[..., Any] = subprocess.Popen,
    ) -> None:
        self._pyautogui = pyautogui_module
        self._keyboard = keyboard_module
        self._program_launcher = program_launcher
        self._pyautogui.FAILSAFE = True

    def callback_for(self, action: ActionDefinition) -> Callable[[], None]:
        """Create the callback placed on the existing action queue."""
        return lambda: self.execute(action)

    def execute(self, action: ActionDefinition) -> None:
        if action.type == "none":
            return
        if action.type == "media":
            self._execute_media(str(action.value))
        elif action.type == "key":
            self._pyautogui.press(str(action.value))
        elif action.type == "hotkey":
            self._pyautogui.hotkey(*parse_hotkey(str(action.value)))
        elif action.type == "mouse":
            self._execute_mouse(str(action.value))
        elif action.type == "text":
            self._pyautogui.write(str(action.value))
        elif action.type == "command":
            # A validated argv sequence and shell=False avoid shell-string execution.
            self._program_launcher(list(action.value), shell=False)
        else:  # Defensive guard if an object bypassed ActionDefinition validation.
            raise ValueError(f"Unsupported action type: {action.type}")

    def _execute_media(self, value: str) -> None:
        pyautogui_keys = {
            "play_pause": "playpause",
            "volume_up": "volumeup",
            "volume_down": "volumedown",
            "mute": "volumemute",
        }
        if value in pyautogui_keys:
            self._pyautogui.press(pyautogui_keys[value])
            return
        keyboard_keys = {"next_track": "next track", "previous_track": "previous track"}
        if self._keyboard is not None:
            self._keyboard.send(keyboard_keys[value])
        else:
            fallback = {"next_track": "nexttrack", "previous_track": "prevtrack"}
            logger.warning("The 'keyboard' package is unavailable; using PyAutoGUI fallback")
            self._pyautogui.press(fallback[value])

    def _execute_mouse(self, value: str) -> None:
        if value.endswith("_click"):
            self._pyautogui.click(button=value.removesuffix("_click"))
        else:
            self._pyautogui.scroll(1 if value == "scroll_up" else -1)
