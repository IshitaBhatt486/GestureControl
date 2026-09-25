from types import SimpleNamespace
from unittest.mock import MagicMock

from handwave.actions.action_mapper import ActionMapper
from handwave.gestures.swipe_recognizer import SwipeRecognizer


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class MotionHand:
    """Deterministic landmark protocol fixture with a selected motion source."""

    def __init__(self, x, y, source):
        self.x, self.y, self.source = x, y, source

    def get_finger_states(self):
        if self.source == "finger":
            return {"thumb": "folded", "index": "extended", "middle": "folded", "ring": "folded", "pinky": "folded"}
        if self.source == "hand":
            return {finger: "extended" for finger in ("thumb", "index", "middle", "ring", "pinky")}
        return {finger: "folded" for finger in ("thumb", "index", "middle", "ring", "pinky")}

    def get_landmarks(self):
        points = [SimpleNamespace(x=self.x, y=self.y, z=0.0) for _ in range(21)]
        points[8] = SimpleNamespace(x=self.x, y=self.y, z=0.0)
        return points

    def get_centroid(self):
        return self.x, self.y


def _recognize(source, positions, clock=None):
    clock = clock or Clock()
    recognizer = SwipeRecognizer(clock=clock)
    results = []
    for index, (x, y) in enumerate(positions):
        clock.now = index * 0.1
        results.append(recognizer.update(MotionHand(x, y, source)))
    return results, recognizer, clock


def _detected(results):
    return next(result for result in results if result.name != "Unknown")


def test_upward_finger_swipe_tracks_index_tip_and_is_explicitly_classified():
    results, _, _ = _recognize("finger", [(0.5, 0.78), (0.5, 0.62), (0.5, 0.45), (0.5, 0.28)])
    detected = _detected(results)
    assert (detected.name, detected.source, detected.axis) == ("Finger Swipe Up", "finger", "vertical")
    assert "index-tip" in detected.diagnostic


def test_upward_hand_swipe_tracks_open_palm_centroid():
    results, _, _ = _recognize("hand", [(0.5, 0.78), (0.5, 0.62), (0.5, 0.45), (0.5, 0.28)])
    detected = _detected(results)
    assert (detected.name, detected.source, detected.axis) == ("Hand Swipe Up", "hand", "vertical")
    assert "centroid" in detected.diagnostic


def test_downward_finger_and_hand_swipes_are_distinct():
    positions = [(0.5, 0.20), (0.5, 0.36), (0.5, 0.54), (0.5, 0.72)]
    finger, _, _ = _recognize("finger", positions)
    hand, _, _ = _recognize("hand", positions)
    assert _detected(finger).name == "Finger Swipe Down"
    assert _detected(hand).name == "Hand Swipe Down"


def test_open_hand_horizontal_swipes_recognize_virtual_desktop_directions():
    left, _, _ = _recognize("hand", [(0.80, 0.5), (0.65, 0.5), (0.47, 0.5), (0.28, 0.5)])
    right, _, _ = _recognize("hand", [(0.20, 0.5), (0.36, 0.5), (0.55, 0.5), (0.74, 0.5)])
    assert _detected(left).name == "Swipe Left"
    assert _detected(right).name == "Swipe Right"
    assert _detected(left).source == _detected(right).source == "hand"


def test_horizontal_pointing_swipes_work_and_diagonal_motion_is_rejected():
    finger_horizontal, _, _ = _recognize("finger", [(0.2, 0.5), (0.36, 0.5), (0.55, 0.5), (0.74, 0.5)])
    diagonal, _, _ = _recognize("hand", [(0.2, 0.2), (0.36, 0.36), (0.55, 0.55), (0.74, 0.74)])
    closed_hand, _, _ = _recognize("other", [(0.5, 0.8), (0.5, 0.6), (0.5, 0.4), (0.5, 0.2)])
    assert _detected(finger_horizontal).name == "Swipe Right"
    assert all(result.name == "Unknown" for result in diagonal + closed_hand)


def test_slow_motion_is_rejected():
    clock = Clock()
    recognizer = SwipeRecognizer(clock=clock)
    results = []
    for index, y in enumerate((0.80, 0.74, 0.68, 0.62, 0.56)):
        clock.now = index * 0.2
        results.append(recognizer.update(MotionHand(0.5, y, "hand")).name)
    assert set(results) == {"Unknown"}


def test_recognizer_cooldown_and_action_mapper_rearm_are_enforced():
    clock = Clock()
    recognizer = SwipeRecognizer(clock=clock)
    first = []
    for index, y in enumerate((0.80, 0.62, 0.44, 0.26)):
        clock.now = index * 0.1
        first.append(recognizer.update(MotionHand(0.5, y, "hand")).name)
    assert "Hand Swipe Up" in first

    for index, y in enumerate((0.80, 0.62, 0.44, 0.26), start=4):
        clock.now = index * 0.1
        assert recognizer.update(MotionHand(0.5, y, "hand")).name == "Unknown"

    gui = MagicMock()
    mapper = ActionMapper(clock=clock, pyautogui_module=gui)
    clock.now = 2.0
    assert mapper.execute("Hand Swipe Up") is True
    assert mapper.execute("Hand Swipe Up") is False
    assert mapper.last_outcome.blocked_reason == "gesture not re-armed"
    mapper.execute(None)
    clock.now = 3.1
    assert mapper.execute("Hand Swipe Up") is True
    assert gui.hotkey.call_count == 2


def test_default_navigation_bindings_and_existing_media_gesture_use_action_abstraction():
    clock = Clock()
    gui = MagicMock()
    mapper = ActionMapper(clock=clock, pyautogui_module=gui)
    clock.now = 2.0
    assert mapper.execute("Swipe Left") is True
    gui.hotkey.assert_called_once_with("win", "ctrl", "left")

    mapper.execute(None)  # re-arm before using another configured gesture.
    clock.now = 3.1
    assert mapper.execute("Open Palm") is True
    gui.press.assert_called_once_with("playpause")
