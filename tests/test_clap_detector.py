import numpy as np

from gestureos.services.clap_detector import ClapDetector


def _clap():
    block = np.zeros(256, dtype=np.float32)
    block[20] = 1.0
    return block


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


def test_peaks_outside_timing_window_do_not_trigger(qtbot):
    detector = ClapDetector()
    detections = []
    detector.double_clap.connect(lambda: detections.append(True))

    detector.process_audio(_clap(), timestamp=0.0)
    detector.process_audio(_clap(), timestamp=0.15)
    detector.process_audio(_clap(), timestamp=1.2)
    assert detections == []


def test_normal_speech_and_background_noise_do_not_trigger(qtbot):
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
