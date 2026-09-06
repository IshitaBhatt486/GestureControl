# GestureOS Developer Guide

## Supported environment

- Windows 10/11
- CPython 3.11
- PyQt6 6.7+
- OpenCV 4.10+
- MediaPipe 0.10.14–0.10.21

Create the environment from the repository root:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r gestureos\requirements.txt
```

Run from source:

```powershell
python -m gestureos.main
```

## Repository layout

```text
gesture-control/
├── gestureos/
│   ├── actions/       Media actions, pinch control, asynchronous action queue
│   ├── assets/        Application icon and image assets
│   ├── config/        JSON settings schema, defaults, persistence
│   ├── gestures/      Landmark model, static poses, filter, swipe recognition
│   ├── services/      Clap detection, activation state, Windows startup
│   ├── ui/            Dashboard, diagnostics, settings, onboarding
│   ├── vision/        Capture/recognition workers and profiling
│   └── main.py        Application bootstrap
├── benchmarks/        Repeatable latency benchmarks
├── docs/              Product and engineering documentation
├── packaging/         NSIS and Windows version metadata
├── scripts/           Documentation utilities
├── tests/             Unit, integration, UI, and benchmark tests
├── GestureOS.spec     PyInstaller configuration
└── build_release.*    Release entry points
```

## Engineering model

The GUI thread owns every widget. Capture, recognition, and OS-side effects run on
three independent `QThread` workers. A condition-protected buffer holds at most one
camera frame. A FIFO action queue decouples media-key latency from inference.

See [Architecture](ARCHITECTURE.md) for component and sequence diagrams.

## Settings

`AppSettings` is an immutable validated snapshot. `SettingsManager.update()` uses
dataclass replacement and an atomic temporary-file rename. Gesture identifiers and
action identifiers live in `gestureos/config/gesture_config.py`.

When extending settings:

1. Add a typed field and validation to `AppSettings`.
2. Add its default to `gestureos/config/settings.json` when appropriate.
3. Add UI controls and return the value from `SettingsDialog.values()`.
4. Pass the immutable snapshot to the owning worker.
5. Add persistence, invalid-input, and UI tests.

Unknown JSON keys are ignored for forward/backward compatibility. Partial gesture
maps are merged with current defaults.

## Adding a static gesture

1. Add the display name to `GESTURES` and its default binding/enabled state.
2. Add a finger-state pattern to `GestureEngine.GESTURE_PATTERNS`.
3. Add orientation validation if the finger pattern is ambiguous.
4. Add geometry fixtures and recognition cases.
5. Add settings persistence and action-mapping coverage.

Static classification should remain deterministic and side-effect free. OS actions
belong in `ActionMapper`/`ActionWorker`, not in recognition code.

## Adding a motion gesture

Create a stateful recognizer that accepts `HandLandmarkData | None` and returns an
immutable result. Reset its history when no hand is present. Invoke it in
`GestureWorker`, then include it in action arbitration and tests. Use normalized,
time-based thresholds so behavior does not depend directly on processing FPS.

## Threading rules

- Never update Qt widgets from a worker.
- Never perform MediaPipe inference or OS key injection on the GUI thread.
- Do not replace `LatestFrameBuffer` with an unbounded image queue.
- Do not block `CameraManager.stop_camera()`; completion is signal-driven.
- Close the action queue only after recognition stops so accepted actions drain.
- Create and destroy MediaPipe resources inside the recognition worker.
- Use monotonic/performance clocks for durations.

## Tests and coverage

Run the complete framework:

```powershell
.\run_tests.cmd -q
```

Run one layer during development without applying the full-suite coverage gate:

```powershell
pytest -m unit --no-cov
pytest -m integration --no-cov
pytest -m ui --no-cov
pytest -m benchmark --no-cov
```

`tests/conftest.py` assigns exactly one marker by module. Full runs enforce 80%
branch coverage and generate JUnit, Cobertura XML, and HTML reports under
`test-results/`.

Test boundaries should inject clocks, camera devices, PyAutoGUI, keyboard, audio,
and settings paths. Hardware-independent tests must remain deterministic.

## Benchmarks

```powershell
python -m benchmarks.benchmark_frame_latency
```

The benchmark overloads producer/consumer boundaries intentionally. Do not treat
its absolute values as hardware certification; its regression assertions compare
strategies under the same scheduler and workload. See [Benchmark Report](BENCHMARK_REPORT.md).

## Documentation screenshots

Regenerate deterministic UI images without opening hardware:

```powershell
python scripts\capture_docs_screenshots.py
```

The script uses simulated Qt signals and labels the camera image
`DOCUMENTATION PREVIEW`. Review every generated image before committing it.

## Release build

```powershell
.\build_release.cmd
```

This runs the quality gate, builds the single-file application, compiles the NSIS
installer, and writes SHA-256 checksums. See [Release Guide](../RELEASE.md).
