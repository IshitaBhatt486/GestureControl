"""Gesture and action identifiers shared by settings, UI, and execution."""

from __future__ import annotations

GESTURES = (
    "Open Palm",
    "Fist",
    "Thumbs Up",
    "Thumbs Down",
    "Peace Sign",
    "Pointing",
    "Swipe Left",
    "Swipe Right",
)

ACTIONS = {
    "none": "No action",
    "play_pause": "Play / Pause",
    "volume_up": "Volume Up",
    "volume_down": "Volume Down",
    "next_track": "Next Track",
    "previous_track": "Previous Track",
}

DEFAULT_GESTURE_BINDINGS = {
    "Open Palm": "play_pause",
    "Fist": "none",
    "Thumbs Up": "volume_up",
    "Thumbs Down": "volume_down",
    "Peace Sign": "next_track",
    "Pointing": "previous_track",
    "Swipe Left": "previous_track",
    "Swipe Right": "next_track",
}

DEFAULT_ENABLED_GESTURES = {
    gesture: action != "none"
    for gesture, action in DEFAULT_GESTURE_BINDINGS.items()
}


def complete_bindings(values: dict[str, str] | None = None) -> dict[str, str]:
    result = DEFAULT_GESTURE_BINDINGS.copy()
    if values:
        result.update(values)
    return result


def complete_enabled(values: dict[str, bool] | None = None) -> dict[str, bool]:
    result = DEFAULT_ENABLED_GESTURES.copy()
    if values:
        result.update(values)
    return result
