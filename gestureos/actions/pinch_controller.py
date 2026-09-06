"""Smoothed pinch-motion volume control."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pyautogui

from gestureos.gestures.hand_landmark_data import HandLandmarkData


@dataclass(frozen=True)
class PinchControlResult:
    detected: bool
    distance: float | None
    action: str | None = None


class PinchController:
    """Convert deliberate vertical movement during a pinch into volume steps."""

    def __init__(
        self,
        pinch_threshold: float = 0.08,
        movement_threshold: float = 0.025,
        smoothing: float = 0.35,
        action_cooldown: float = 0.1,
        clock: Callable[[], float] = time.monotonic,
        pyautogui_module: Any = pyautogui,
        dispatcher: Callable[[str, Callable[[], None]], None] | None = None,
    ) -> None:
        if not 0 < smoothing <= 1:
            raise ValueError("Smoothing must be between 0 and 1")
        self.pinch_threshold = pinch_threshold
        self.movement_threshold = movement_threshold
        self.smoothing = smoothing
        self.action_cooldown = action_cooldown
        self._clock = clock
        self._pyautogui = pyautogui_module
        self._dispatcher = dispatcher
        self._smoothed_y: float | None = None
        self._action_anchor_y: float | None = None
        self._last_action_time = float("-inf")

    def update(self, landmarks: HandLandmarkData | None) -> PinchControlResult:
        if landmarks is None:
            self.reset()
            return PinchControlResult(False, None)

        distance = landmarks.get_pinch_distance()
        if distance > self.pinch_threshold:
            self.reset()
            return PinchControlResult(False, distance)

        midpoint_y = landmarks.get_pinch_midpoint_y()
        if self._smoothed_y is None:
            self._smoothed_y = midpoint_y
            self._action_anchor_y = midpoint_y
            return PinchControlResult(True, distance)

        self._smoothed_y += self.smoothing * (midpoint_y - self._smoothed_y)
        assert self._action_anchor_y is not None
        movement = self._action_anchor_y - self._smoothed_y
        now = self._clock()
        if abs(movement) < self.movement_threshold or now - self._last_action_time < self.action_cooldown:
            return PinchControlResult(True, distance)

        action = "volumeup" if movement > 0 else "volumedown"
        callback = lambda: self._pyautogui.press(action)
        if self._dispatcher is None:
            callback()
        else:
            self._dispatcher(action, callback)
        # One step per threshold crossing prevents large, noisy frame jumps from bursting.
        direction = 1.0 if movement > 0 else -1.0
        self._action_anchor_y -= direction * self.movement_threshold
        self._last_action_time = now
        return PinchControlResult(True, distance, action)

    def reset(self) -> None:
        self._smoothed_y = None
        self._action_anchor_y = None
