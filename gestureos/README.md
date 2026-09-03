# GestureOS

A modular Windows desktop foundation for webcam-based hand gesture controls.

## Setup

Use Python 3.11, then run from the repository root:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r gestureos\requirements.txt
python -m gestureos.main
```

Allow desktop apps to access the camera in Windows Settings if prompted. Logs are
written to `%USERPROFILE%\.gestureos\gestureos.log` when that location is writable.

## Tests

```powershell
pytest -q
```

The automated tests cover startup UI construction, Start/Stop wiring, camera-open
errors, resource release, single-hand MediaPipe configuration, drawing styles,
detection loss/recovery, and FPS calculation. Confirm live behavior with a physical
webcam by moving one hand into and out of frame and checking that all 21 green
landmarks and their green connections track the hand. The on-screen FPS should
remain above 20 on the target machine.
