from unittest.mock import MagicMock

from handwave.actions.action_mapper import ActionMapper
from handwave.gestures.gesture_filter import GestureFilter


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_rapid_hand_movement_never_becomes_stable_or_triggers_actions():
    clock = Clock()
    gesture_filter = GestureFilter(clock=clock)
    gui = MagicMock()
    keys = MagicMock()
    mapper = ActionMapper(clock=clock, pyautogui_module=gui, keyboard_module=keys)

    for index in range(20):
        clock.now = index * 0.05
        raw = "Open Palm" if index % 2 == 0 else "Peace Sign"
        filtered = gesture_filter.update(raw)
        mapper.execute(filtered.stable_gesture)

    assert filtered.stable_gesture == "Unknown"
    gui.press.assert_not_called()
    keys.send.assert_not_called()


def test_stable_gesture_requires_500ms_then_triggers_only_once():
    clock = Clock()
    gesture_filter = GestureFilter(clock=clock)
    gui = MagicMock()
    mapper = ActionMapper(clock=clock, pyautogui_module=gui, keyboard_module=MagicMock())
    outputs = []

    for index in range(16):
        clock.now = index * 0.05
        filtered = gesture_filter.update("Thumbs Up")
        outputs.append(filtered)
        mapper.execute(filtered.stable_gesture)

    assert all(output.raw_gesture == "Thumbs Up" for output in outputs)
    assert outputs[9].stable_gesture == "Unknown"
    assert outputs[10].stable_gesture == "Thumbs Up"
    gui.press.assert_called_once_with("volumeup")


def test_majority_vote_ignores_occasional_bad_frames():
    clock = Clock()
    gesture_filter = GestureFilter(clock=clock)
    sequence = ["Pointing", "Pointing", "Unknown", "Pointing"] * 4

    for index, raw in enumerate(sequence):
        clock.now = index * 0.05
        result = gesture_filter.update(raw)

    assert result.raw_gesture == "Pointing"
    assert result.stable_gesture == "Pointing"


def test_reset_clears_stable_gesture_and_history():
    clock = Clock()
    gesture_filter = GestureFilter(persistence_seconds=0, clock=clock)
    assert gesture_filter.update("Fist").stable_gesture == "Fist"
    gesture_filter.reset()
    assert gesture_filter.update(None).stable_gesture == "Unknown"
