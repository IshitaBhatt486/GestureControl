from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from handwave.services.clap_detector import ClapDetector, ClapState


def _clap(amplitude=1.0, size=256, at=20):
    block = np.zeros(size, dtype=np.float32)
    block[at] = amplitude
    return block


def _quiet_noise(rng, level=0.02, size=256):
    return rng.normal(0, level, size).astype(np.float32)


def test_double_clap_enables_then_disables_system(qtbot):
    detector = ClapDetector()
    enabled = [False]
    detector.double_clap.connect(lambda: enabled.__setitem__(0, not enabled[0]))

    assert not detector.process_audio(_clap(), timestamp=1.0)
    assert detector.process_audio(_clap(), timestamp=1.5)
    assert enabled[0]

    assert not detector.process_audio(_clap(), timestamp=2.0)
    assert detector.process_audio(_clap(), timestamp=2.5)
    assert not enabled[0]


def test_uneven_but_valid_claps_still_trigger():
    detector = ClapDetector()
    assert not detector.process_audio(_clap(), timestamp=0.0)
    assert detector.process_audio(_clap(), timestamp=0.25)  # close to the minimum separation

    detector.reset()
    assert not detector.process_audio(_clap(), timestamp=10.0)
    assert detector.process_audio(_clap(), timestamp=10.95)  # close to the maximum separation


def test_too_fast_claps_do_not_trigger():
    detector = ClapDetector()
    detections = []
    detector.double_clap.connect(lambda: detections.append(True))
    detector.process_audio(_clap(), timestamp=0.0)
    detector.process_audio(_clap(), timestamp=0.15)  # inside the refractory/min-separation window
    assert detections == []


def test_too_slow_claps_do_not_trigger():
    detector = ClapDetector()
    detections = []
    detector.double_clap.connect(lambda: detections.append(True))
    detector.process_audio(_clap(), timestamp=0.0)
    detector.process_audio(_clap(), timestamp=1.2)
    assert detections == []


def test_single_clap_alone_never_triggers():
    detector = ClapDetector()
    detections = []
    detector.double_clap.connect(lambda: detections.append(True))
    detector.process_audio(_clap(), timestamp=0.0)
    assert detections == []
    assert detector.state == ClapState.WAITING_FOR_SECOND_CLAP


def test_peaks_outside_timing_window_do_not_trigger():
    detector = ClapDetector()
    detections = []
    detector.double_clap.connect(lambda: detections.append(True))

    detector.process_audio(_clap(), timestamp=0.0)
    detector.process_audio(_clap(), timestamp=0.15)
    detector.process_audio(_clap(), timestamp=1.2)
    assert detections == []


def test_normal_speech_and_background_noise_do_not_trigger():
    detector = ClapDetector()
    detections = []
    detector.double_clap.connect(lambda: detections.append(True))
    time_axis = np.linspace(0, 1, 256, endpoint=False)

    for index in range(30):
        speech = 0.45 * np.sin(2 * np.pi * (3 + index % 4) * time_axis)
        detector.process_audio(speech, timestamp=index * 0.05)
    rng = np.random.default_rng(4)
    for index in range(30, 60):
        noise = rng.normal(0, 0.03, 256)
        detector.process_audio(noise, timestamp=index * 0.05)

    assert detections == []


def test_repeated_double_claps_keep_working():
    detector = ClapDetector()
    count = [0]
    detector.double_clap.connect(lambda: count.__setitem__(0, count[0] + 1))
    for round_start in (0.0, 5.0, 10.0):
        detector.process_audio(_clap(), timestamp=round_start)
        assert detector.process_audio(_clap(), timestamp=round_start + 0.4)
    assert count[0] == 3


def test_state_machine_transitions_and_reset():
    detector = ClapDetector()
    assert detector.state == ClapState.IDLE
    detector.process_audio(_clap(), timestamp=0.0)
    assert detector.state == ClapState.WAITING_FOR_SECOND_CLAP
    detector.process_audio(_clap(), timestamp=0.4)
    assert detector.state == ClapState.IDLE

    detector.process_audio(_clap(), timestamp=10.0)
    assert detector.state == ClapState.WAITING_FOR_SECOND_CLAP
    detector.reset()
    assert detector.state == ClapState.IDLE


def test_calibration_derives_baseline_and_threshold():
    detector = ClapDetector()
    rng = np.random.default_rng(1)
    detector.begin_calibration()
    for _ in range(20):
        detector.feed_calibration_sample(_quiet_noise(rng, level=0.01))
    result = detector.finish_calibration(margin=6.0)

    assert result.sample_count == 20
    assert result.ambient_rms == pytest.approx(detector._noise_floor)
    assert result.threshold >= detector.min_peak


def test_calibration_samples_never_trigger_a_clap():
    detector = ClapDetector()
    detections = []
    detector.double_clap.connect(lambda: detections.append(True))
    detector.begin_calibration()
    detector.feed_calibration_sample(_clap())  # even a loud sample must not fire during calibration
    detector.finish_calibration()
    assert detections == []


def test_finish_calibration_without_samples_raises():
    detector = ClapDetector()
    detector.begin_calibration()
    with pytest.raises(ValueError):
        detector.finish_calibration()


def test_status_reports_input_level_and_availability():
    detector = ClapDetector()
    status_before = detector.status()
    assert status_before.available is False
    assert status_before.input_level == 0.0

    detector.process_audio(_clap(amplitude=0.6), timestamp=0.0)
    status_after = detector.status()
    assert status_after.input_level == pytest.approx(0.6)


def test_start_without_sounddevice_reports_a_clear_error(qtbot):
    detector = ClapDetector()
    errors = []
    detector.error.connect(errors.append)

    with patch("handwave.services.clap_detector.sd", None):
        detector.start()

    assert not detector.is_listening
    assert "sounddevice" in errors[0]
    assert detector.status().error is not None


def test_device_failure_is_recovered_from_without_crashing(qtbot):
    detector = ClapDetector()
    errors = []
    detector.error.connect(errors.append)
    failing_module = MagicMock()
    failing_module.InputStream.side_effect = OSError("device unavailable")

    with patch("handwave.services.clap_detector.sd", failing_module):
        detector.start()
    assert not detector.is_listening
    assert errors  # a clear, non-fatal error was reported

    working_stream = MagicMock()
    working_module = MagicMock()
    working_module.InputStream.return_value = working_stream
    with patch("handwave.services.clap_detector.sd", working_module):
        detector.retry()

    assert detector.is_listening
    assert detector.status().error is None


def test_stop_keeps_camera_independent_no_exception_on_double_stop(qtbot):
    detector = ClapDetector()
    detector.stop()  # never started; must not raise
    working_module = MagicMock()
    with patch("handwave.services.clap_detector.sd", working_module):
        detector.start()
    detector.stop()
    detector.stop()  # idempotent
    assert not detector.is_listening


def test_process_audio_never_stores_raw_samples():
    """Privacy: only scalar levels are retained, never the sample array itself."""
    detector = ClapDetector()
    detector.process_audio(_clap(), timestamp=0.0)
    for value in vars(detector).values():
        assert not isinstance(value, np.ndarray)
