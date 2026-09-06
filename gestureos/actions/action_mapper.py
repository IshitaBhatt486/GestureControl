"""Cooldown-protected Windows media actions for recognized gestures."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import pyautogui

from gestureos.config.gesture_config import (
    DEFAULT_ENABLED_GESTURES,
    DEFAULT_GESTURE_BINDINGS,
)

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
        dispatcher: Callable[[str, Callable[[], None]], None] | None = None,
        gesture_bindings: dict[str, str] | None = None,
        enabled_gestures: dict[str, bool] | None = None,
    ) -> None:
        if cooldown < 0:
            raise ValueError("Cooldown cannot be negative")
        self.cooldown = cooldown
        self._clock = clock
        self._pyautogui = pyautogui_module
        self._keyboard = keyboard_module
        self._dispatcher = dispatcher
        self._gesture_bindings = (
            DEFAULT_GESTURE_BINDINGS.copy()
            if gesture_bindings is None
            else gesture_bindings.copy()
        )
        self._enabled_gestures = (
            DEFAULT_ENABLED_GESTURES.copy()
            if enabled_gestures is None
            else enabled_gestures.copy()
        )
        self._pyautogui.FAILSAFE = True
        self._last_trigger_time = float("-inf")
        self._active_gesture: str | None = None
        self._action_callbacks: dict[str, Callable[[], None]] = {
            "play_pause": lambda: self._pyautogui.press("playpause"),
            "volume_up": lambda: self._pyautogui.press("volumeup"),
            "volume_down": lambda: self._pyautogui.press("volumedown"),
            "next_track": lambda: self._send_keyboard("next track"),
            "previous_track": lambda: self._send_keyboard("previous track"),
        }
        self._registered_actions: dict[str, Callable[[], None]] = {}

    def register(self, gesture: str, action: Callable[[], None]) -> None:
        """Register or replace an action while retaining cooldown protection."""
        self._registered_actions[gesture] = action
        self._enabled_gestures[gesture] = True

    def _send_keyboard(self, key: str) -> None:
        if self._keyboard is None:
            fallback = {"next track": "nexttrack", "previous track": "prevtrack"}
            logger.warning("The 'keyboard' package is unavailable; using PyAutoGUI fallback")
            self._pyautogui.press(fallback[key])
            return
        self._keyboard.send(key)

    def execute(self, gesture: str | None) -> bool:
        """Execute once per gesture pose, subject to the global cooldown."""
        action_id = self._gesture_bindings.get(gesture or "", "none")
        action = self._registered_actions.get(gesture or "")
        if (
            not self._enabled_gestures.get(gesture or "", False)
            or (action is None and action_id == "none")
        ):
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
            action = action or self._action_callbacks[action_id]
            if self._dispatcher is None:
                action()
            else:
                self._dispatcher(gesture, action)
            self._last_trigger_time = now
            logger.info("Accepted action for gesture %s", gesture)
            return True
        except Exception:
            logger.exception("Action failed for gesture %s", gesture)
            return False
