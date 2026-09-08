from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from handwave.actions.action_mapper import ActionMapper
from handwave.gestures.hand_landmark_data import HandLandmarkData
from handwave.gestures.swipe_recognizer import SwipeRecognizer


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def _hand(x, y=0.5):
    return HandLandmarkData([SimpleNamespace(x=x, y=y, z=0.0) for _ in range(21)])


@pytest.mark.parametrize(
    ("positions", "expected", "key"),
    [
        ((0.80, 0.72, 0.61, 0.48), "Swipe Left", "previous track"),
        ((0.20, 0.28, 0.39, 0.53), "Swipe Right", "next track"),
    ],
)
def test_intentional_swipes_recognize_direction_and_fire_track_key(positions, expected, key):
    clock = Clock()
    recognizer = SwipeRecognizer(clock=clock)
    keyboard = MagicMock()
    mapper = ActionMapper(clock=clock, pyautogui_module=MagicMock(), keyboard_module=keyboard)

    detected = []
    for index, x in enumerate(positions):
        clock.now = index * 0.1
        result = recognizer.update(_hand(x))
        if result.name != "Unknown":
            detected.append(result)
            mapper.execute(result.name)

    assert len(detected) == 1
    assert detected[0].name == expected
    assert detected[0].velocity >= 0.5
    keyboard.send.assert_called_once_with(key)


def test_random_and_diagonal_movements_do_not_trigger():
    clock = Clock()
    recognizer = SwipeRecognizer(clock=clock)
    movements = [
        (0.50, 0.50),
        (0.57, 0.48),
        (0.49, 0.54),
        (0.61, 0.45),
        (0.52, 0.51),
        (0.70, 0.72),
    ]

    results = []
    for index, (x, y) in enumerate(movements):
        clock.now = index * 0.1
        results.append(recognizer.update(_hand(x, y)).name)

    assert set(results) == {"Unknown"}


def test_slow_horizontal_drift_does_not_trigger():
    clock = Clock()
    recognizer = SwipeRecognizer(clock=clock)
    results = []
    for index, x in enumerate((0.30, 0.34, 0.38, 0.42, 0.46, 0.48)):
        clock.now = index * 0.2
        results.append(recognizer.update(_hand(x)).name)
    assert set(results) == {"Unknown"}
