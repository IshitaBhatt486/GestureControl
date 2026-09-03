from types import SimpleNamespace
from unittest.mock import MagicMock

from gestureos.actions.pinch_controller import PinchController
from gestureos.gestures.hand_landmark_data import HandLandmarkData


def _hand(y, pinched=True):
    points = [SimpleNamespace(x=0.5, y=0.7, z=0.0) for _ in range(21)]
    points[4] = SimpleNamespace(x=0.48, y=y, z=0.0)
    points[8] = SimpleNamespace(x=0.52 if pinched else 0.75, y=y, z=0.0)
    return HandLandmarkData(points)


def test_pinch_movement_changes_volume_smoothly_one_step_at_a_time():
    gui = MagicMock()
    times = iter((0.0, 0.2, 0.4, 0.6))
    controller = PinchController(smoothing=0.5, clock=times.__next__, pyautogui_module=gui)

    assert controller.update(_hand(0.60)).detected
    first = controller.update(_hand(0.52))
    second = controller.update(_hand(0.44))
    controller.update(_hand(0.52))
    down = controller.update(_hand(0.62))

    assert first.action == "volumeup"
    assert second.action == "volumeup"
    assert down.action == "volumedown"
    assert [call.args[0] for call in gui.press.call_args_list] == [
        "volumeup", "volumeup", "volumeup", "volumedown"
    ]


def test_small_jitter_and_non_pinch_movement_are_ignored():
    gui = MagicMock()
    controller = PinchController(smoothing=0.35, clock=lambda: 1.0, pyautogui_module=gui)

    for y in (0.50, 0.49, 0.505, 0.495, 0.51):
        result = controller.update(_hand(y))
        assert result.detected
        assert result.action is None

    for y in (0.5, 0.3, 0.7):
        result = controller.update(_hand(y, pinched=False))
        assert not result.detected
    gui.press.assert_not_called()


def test_pinch_distance_is_normalized_and_reported():
    controller = PinchController(pyautogui_module=MagicMock())
    result = controller.update(_hand(0.5))
    assert result.distance is not None
    assert abs(result.distance - 0.04) < 1e-6
