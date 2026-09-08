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
    "Swipe Left",
    "Swipe Right",
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
    "Swipe Left": "previous_track",
    "Swipe Right": "next_track",
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
