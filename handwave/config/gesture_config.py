"""Gesture and action identifiers shared by settings, UI, and execution."""

from __future__ import annotations

from handwave.actions.action_definition import ActionDefinition, MEDIA_ACTIONS

GESTURES = (
    "Open Palm",
    "Fist",
    "Thumbs Up",
    "Thumbs Down",
    "Peace Sign",
    "Pointing",
    "Pointing Up",
    "Pointing Down",
    "Pointing Left",
    "Pointing Right",
    "Swipe Left",
    "Swipe Right",
    "Finger Swipe Up",
    "Hand Swipe Up",
    "Finger Swipe Down",
    "Hand Swipe Down",
)

ACTIONS = {
    "none": "No action",
    **MEDIA_ACTIONS,
}

DEFAULT_GESTURE_BINDINGS = {
    "Open Palm": "play_pause",
    "Fist": "none",
    "Thumbs Up": "volume_up",
    "Thumbs Down": "volume_down",
    "Peace Sign": "next_track",
    "Pointing": "previous_track",
    "Pointing Up": "volume_up",
    "Pointing Down": "volume_down",
    "Pointing Left": "previous_track",
    "Pointing Right": "next_track",
    "Swipe Left": {"type": "hotkey", "value": "win+ctrl+left"},
    "Swipe Right": {"type": "hotkey", "value": "win+ctrl+right"},
    "Finger Swipe Up": {"type": "hotkey", "value": "alt+tab"},
    "Hand Swipe Up": {"type": "hotkey", "value": "win+tab"},
    "Finger Swipe Down": {"type": "key", "value": "esc"},
    "Hand Swipe Down": {"type": "key", "value": "esc"},
}

DEFAULT_ENABLED_GESTURES = {
    gesture: action != "none"
    for gesture, action in DEFAULT_GESTURE_BINDINGS.items()
}


def complete_bindings(values: dict[str, object] | None = None) -> dict[str, ActionDefinition]:
    result = {
        gesture: ActionDefinition.from_data(action)
        for gesture, action in DEFAULT_GESTURE_BINDINGS.items()
    }
    if values:
        result.update({gesture: ActionDefinition.from_data(action) for gesture, action in values.items()})
    return result


def complete_enabled(values: dict[str, bool] | None = None) -> dict[str, bool]:
    result = DEFAULT_ENABLED_GESTURES.copy()
    if values:
        result.update(values)
    return result
