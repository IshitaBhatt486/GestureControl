from handwave.gestures.arbitration import select_action_candidate


def test_two_hand_gesture_has_highest_priority():
    assert select_action_candidate(
        two_hand_gesture="Both Palms Open",
        pinch_detected=True,
        swipe_gesture="Swipe Left",
        stable_gesture="Open Palm",
    ) == "Both Palms Open"


def test_pinch_consumes_the_frame_before_swipe_or_static_gesture():
    assert select_action_candidate(
        pinch_detected=True,
        swipe_gesture="Swipe Left",
        stable_gesture="Open Palm",
    ) == "Unknown"


def test_swipe_has_priority_over_static_gesture():
    assert select_action_candidate(
        swipe_gesture="Swipe Left", stable_gesture="Open Palm"
    ) == "Swipe Left"


def test_static_gesture_is_used_when_no_motion_gesture_applies():
    assert select_action_candidate(stable_gesture="Open Palm") == "Open Palm"
