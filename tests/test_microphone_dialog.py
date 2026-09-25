from types import SimpleNamespace
from unittest.mock import MagicMock

from handwave.services.clap_detector import ClapState
from handwave.ui.microphone_dialog import MicrophoneDialog


class FakeDetector:
    def __init__(self, *, listening: bool, error: str | None = None) -> None:
        self.is_listening = listening
        self.start = MagicMock()
        self.state = ClapState.IDLE
        self._status = SimpleNamespace(
            available=listening,
            stream_status="running" if listening else "stopped",
            error=error,
            noise_floor=0.01,
            input_level=0.02,
            threshold=0.03,
            device="Test microphone",
            rms=0.01,
            callback_count=0,
        )

    def status(self):
        return self._status


def test_dialog_starts_microphone_automatically_and_has_no_retry_button(qtbot):
    detector = FakeDetector(listening=False)
    dialog = MicrophoneDialog(detector)
    qtbot.addWidget(dialog)

    detector.start.assert_called_once()
    assert [button.text() for button in dialog.findChildren(type(dialog.recalibrate))] == [
        "Recalibrate", "Reset Calibration"
    ]
    assert dialog.health.text() == "No microphone detected"


def test_dialog_reports_listening_and_error_states(qtbot):
    detector = FakeDetector(listening=True)
    dialog = MicrophoneDialog(detector)
    qtbot.addWidget(dialog)
    assert dialog.health.text() == "Connected • Listening"

    detector._status.available = False
    detector._status.stream_status = "error"
    detector._status.error = "access denied"
    dialog._refresh()
    assert dialog.health.text() == "Microphone error"
