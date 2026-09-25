"""Resolve competing gesture recognizers into one action candidate."""

from __future__ import annotations


UNKNOWN_GESTURE = "Unknown"


def select_action_candidate(
    *,
    two_hand_gesture: str = UNKNOWN_GESTURE,
    pinch_detected: bool = False,
    swipe_gesture: str = UNKNOWN_GESTURE,
    stable_gesture: str = UNKNOWN_GESTURE,
) -> str:
    """Return the one gesture eligible for action dispatch in this frame.

    Recognition layers deliberately remain independent. This small, pure policy
    is their single arbitration point: two-hand motions take precedence over a
    pinch, then swipe, then a filtered static pose. A held pinch consumes the
    frame because pinch control dispatches its own volume request.
    """
    if two_hand_gesture != UNKNOWN_GESTURE:
        return two_hand_gesture
    if pinch_detected:
        return UNKNOWN_GESTURE
    if swipe_gesture != UNKNOWN_GESTURE:
        return swipe_gesture
    return stable_gesture
