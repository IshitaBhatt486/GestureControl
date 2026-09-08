import json
import subprocess
import sys

import pytest

_PROBE = (
    "import sys, json; "
    "from handwave.ui.main_window import MainWindow; "
    "print(json.dumps({'mediapipe_imported': 'mediapipe' in sys.modules, "
    "'cv2_imported': 'cv2' in sys.modules}))"
)


@pytest.mark.benchmark
def test_importing_main_window_does_not_import_mediapipe():
    """Regression guard: mediapipe (~0.7s import) must stay off the app-startup path.

    Runs in a fresh subprocess since mediapipe may already be cached in
    sys.modules from other tests in this same process.
    """
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["mediapipe_imported"] is False
