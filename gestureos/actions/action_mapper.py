"""Cooldown-protected Windows media actions for recognized gestures."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import pyautogui

try:
    import keyboard
except ImportError:  # Allows diagnostics/tests before requirements are installed.
    keyboard = None

logger = logging.getLogger(__name__)


class ActionMapper:
    """Map gesture transitions to Windows media keys without rapid repeats."""

    def __init__(
        self,
        cooldown: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        pyautogui_module: Any = pyautogui,
        keyboard_module: Any = keyboard,
    ) -> None:
        if cooldown < 0:
            raise ValueError("Cooldown cannot be negative")
        self.cooldown = cooldown
        self._clock = clock
        self._pyautogui = pyautogui_module
        self._keyboard = keyboard_module
        self._pyautogui.FAILSAFE = True
        self._last_trigger_time = float("-inf")
        self._active_gesture: str | None = None
        self._actions: dict[str, Callable[[], None]] = {
            "Open Palm": lambda: self._pyautogui.press("playpause"),
            "Thumbs Up": lambda: self._pyautogui.press("volumeup"),
            "Thumbs Down": lambda: self._pyautogui.press("volumedown"),
            "Peace Sign": lambda: self._send_keyboard("next track"),
            "Pointing": lambda: self._send_keyboard("previous track"),
            "Swipe Left": lambda: self._send_keyboard("previous track"),
            "Swipe Right": lambda: self._send_keyboard("next track"),
        }

    def register(self, gesture: str, action: Callable[[], None]) -> None:
        """Register or replace an action while retaining cooldown protection."""
        self._actions[gesture] = action

    def _send_keyboard(self, key: str) -> None:
        if self._keyboard is None:
            fallback = {"next track": "nexttrack", "previous track": "prevtrack"}
            logger.warning("The 'keyboard' package is unavailable; using PyAutoGUI fallback")
            self._pyautogui.press(fallback[key])
            return
        self._keyboard.send(key)

    def execute(self, gesture: str | None) -> bool:
        """Execute once per gesture pose, subject to the global cooldown."""
        if gesture not in self._actions:
            self._active_gesture = None
            return False
        if gesture == self._active_gesture:
            return False

        self._active_gesture = gesture
        now = self._clock()
        if now - self._last_trigger_time < self.cooldown:
            logger.debug("Action for %s suppressed by cooldown", gesture)
            return False

        try:
            self._actions[gesture]()
            self._last_trigger_time = now
            logger.info("Executed action for gesture %s", gesture)
            return True
        except Exception:
            logger.exception("Action failed for gesture %s", gesture)
            return False
