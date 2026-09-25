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

    SAFE_NAVIGATION_INPUTS = {
        ("key", "esc"),
        ("hotkey", "alt+tab"),
        ("hotkey", "win+tab"),
        ("hotkey", "win+ctrl+left"),
        ("hotkey", "win+ctrl+right"),
    }

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
            self._safe_input(action, lambda: self._execute_media(str(action.value)))
        elif action.type == "key":
            self._safe_input(action, lambda: self._execute_key(str(action.value)))
        elif action.type == "hotkey":
            self._safe_input(action, lambda: self._execute_hotkey(str(action.value)))
        elif action.type == "mouse":
            self._safe_input(action, lambda: self._execute_mouse(str(action.value)))
        elif action.type == "text":
            self._pyautogui.write(str(action.value))
        elif action.type == "command":
            # A validated argv sequence and shell=False avoid shell-string execution.
            self._program_launcher(list(action.value), shell=False)
        else:  # Defensive guard if an object bypassed ActionDefinition validation.
            raise ValueError(f"Unsupported action type: {action.type}")

    @staticmethod
    def _safe_input(action: ActionDefinition, callback: Callable[[], None]) -> None:
        """Fail closed when Windows input injection is unavailable.

        Navigation bindings are ordinary, configurable key/hotkey actions. If
        the OS rejects input (for example on a locked desktop), logging and a
        no-op are safer than interrupting the recognition worker or launching
        an application-specific fallback.
        """
        try:
            callback()
        except Exception as exc:
            if (action.type, str(action.value)) not in ActionExecutor.SAFE_NAVIGATION_INPUTS:
                raise
            logger.warning("Local input action unavailable (%s): %s", action.describe(), exc)

    def _execute_key(self, value: str) -> None:
        try:
            self._pyautogui.press(value)
        except Exception:
            if self._keyboard is None:
                raise
            logger.info("PyAutoGUI key injection failed; using keyboard fallback")
            self._keyboard.send(value)

    def _execute_hotkey(self, value: str) -> None:
        keys = parse_hotkey(value)
        try:
            self._pyautogui.hotkey(*keys)
        except Exception:
            if self._keyboard is None:
                raise
            logger.info("PyAutoGUI hotkey injection failed; using keyboard fallback")
            self._keyboard.send("+".join(keys))

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
