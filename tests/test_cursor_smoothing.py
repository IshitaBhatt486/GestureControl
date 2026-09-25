import pytest

from handwave.actions.cursor_smoothing import OneEuroFilter2D


def test_first_position_is_immediate_and_filter_can_reset():
    smoother = OneEuroFilter2D()
    assert smoother.update(.2, .3, 0.0) == (.2, .3)
    smoother.reset()
    assert smoother.update(.8, .7, 1.0) == (.8, .7)


def test_high_smoothing_moves_less_than_low_smoothing_for_same_step():
    low, high = OneEuroFilter2D("low"), OneEuroFilter2D("high")
    low.update(0, 0, 0); high.update(0, 0, 0)
    low_value = low.update(1, 0, 1/30)[0]
    high_value = high.update(1, 0, 1/30)[0]
    assert 0 < high_value < low_value < 1


def test_invalid_smoothing_level_is_rejected():
    with pytest.raises(ValueError):
        OneEuroFilter2D("maximum")
