# HandWave

A modular Windows desktop foundation for webcam-based hand gesture controls.

## Setup

Use Python 3.11, then run from the repository root:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r handwave\requirements.txt
python -m handwave.main
```

Allow desktop apps to access the camera in Windows Settings if prompted. Logs are
written to `%USERPROFILE%\.handwave\handwave.log` when that location is writable.

## Gesture settings

Open **Settings** from the main window or system-tray menu to:

- Rebind any static or swipe gesture to play/pause, volume, or track controls.
- Enable or disable individual gestures.
- Adjust MediaPipe detection and tracking sensitivity.

Use the theme control in the title area to switch between the persisted dark and
light desktop themes. The workspace automatically stacks its camera and activity
panels on compact window sizes.

The **Diagnostics** tab updates from the live processing stream and reports camera
and recognition FPS, capture-to-recognition latency, process CPU and memory use,
active pipeline threads, and the current raw and stable gesture.

Settings are saved as JSON and loaded on the next launch. Recognition-related
changes take effect the next time recognition is enabled. Development runs use
`handwave/config/settings.json`; packaged builds store settings under
`%APPDATA%\HandWave\config\settings.json`.

## Tests

```powershell
.\run_tests.cmd -q
```

The complete suite is divided into four selectable layers:

```powershell
pytest -m unit --no-cov
pytest -m integration --no-cov
pytest -m ui --no-cov
pytest -m benchmark --no-cov
```

Every complete run enforces at least 80% branch coverage and automatically writes:

- `test-results/junit.xml` for test results and CI ingestion.
- `test-results/coverage.xml` for machine-readable coverage.
- `test-results/coverage-html/index.html` for an interactive coverage report.

Marker assignment is centralized in `tests/conftest.py`, so every collected test
belongs to exactly one framework layer. The release build runs the same test and
coverage gate before packaging.

## Pipeline benchmark

Run the repeatable overloaded-consumer benchmark from the repository root:

```powershell
python -m benchmarks.benchmark_frame_latency
```

It compares an unbounded FIFO baseline with the production latest-frame buffer
using the same producer rate and processing cost. It also compares synchronous
OS actions with the dedicated action queue. The benchmark reports median and p95
capture-to-processing latency, elapsed time, dropped frames, and recognition time
blocked by actions. The test suite enforces both latency improvements.

The automated tests cover startup UI construction, Start/Stop wiring, camera-open
errors, resource release, single-hand MediaPipe configuration, drawing styles,
detection loss/recovery, and FPS calculation. Confirm live behavior with a physical
webcam by moving one hand into and out of frame and checking that all 21 green
landmarks and their green connections track the hand. The on-screen FPS should
remain above 20 on the target machine.
