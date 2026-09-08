# Development

## Supported environment

- Windows 10/11
- CPython 3.11
- PyQt6 6.7+, OpenCV 4.10+, MediaPipe 0.10.14-0.10.21

```powershell
.\setup.cmd
```

creates `.venv` and installs `handwave\requirements.txt`. Run from source:

```powershell
.\run.cmd
```

## Repository layout

```text
gesture-control/
├── handwave/
│   ├── actions/       Action abstraction (ActionDefinition/Executor/Mapper), action queue
│   ├── config/        Settings, application profiles, atomic persistence
│   ├── gestures/      Landmark model, built-in/custom/two-hand recognition, record/replay
│   ├── services/      Clap detection, foreground-app + profile switching, action history, startup
│   ├── ui/            Dashboard, diagnostics, settings dialog, onboarding
│   ├── vision/         Capture/recognition worker threads and profiling
│   └── main.py         Application bootstrap
├── benchmarks/         Repeatable latency/startup benchmarks
├── tools/              Developer CLI tools (landmark replay)
├── docs/                This documentation
├── packaging/           NSIS and Windows version metadata
├── tests/               Unit, integration, UI, and benchmark tests
└── build_release.*      Release entry points
```

## Engineering model

The GUI thread owns every widget. Capture, recognition, and OS-side effects
run on three independent `QThread` workers; a capacity-one buffer holds only
the latest camera frame; a FIFO action queue decouples OS-call latency from
inference. See [architecture.md](architecture.md) for the full diagram,
[gesture-recognition.md](gesture-recognition.md) and
[actions.md](actions.md) for the two subsystems most likely to need
extending, and [profiles.md](profiles.md) for per-application overrides.

## Extending settings

1. Add a typed field + validation to `AppSettings` (`handwave/config/settings_manager.py`).
2. Add UI controls in the relevant `SettingsDialog` tab and return the value from `values()`.
3. Pass the immutable snapshot to the owning worker.
4. Add persistence, invalid-input, and UI tests (`tests/test_settings_manager.py`, `tests/test_settings_dialog.py`).

Unknown JSON keys are ignored for forward/backward compatibility; missing
keys fall back to defaults; a corrupted settings file falls back to its
`.bak` copy, then to defaults (see [architecture.md](architecture.md#persistence)).

## Adding a built-in static gesture

1. Add the display name to `GESTURES` (`handwave/config/gesture_config.py`) and its default binding/enabled state.
2. Add a finger-state pattern to `GestureEngine.GESTURE_PATTERNS`.
3. Add orientation validation if the finger pattern is ambiguous (see Thumbs Up/Down).
4. Add geometry fixtures and recognition cases (`tests/test_gesture_recognition.py`).
5. Add settings persistence and action-mapping coverage.

## Adding an action type

See [actions.md](actions.md#extending-the-action-abstraction).

## Startup performance discipline

Anything imported at module level of a file reachable from
`handwave.ui.main_window` is on the app-startup path. `mediapipe` (~0.7s
import cost) is deliberately deferred to `GestureWorker.run()` — see
`docs/development.md`'s sibling note in `tests/test_startup_performance.py`,
which asserts merely importing `main_window` never imports `mediapipe`. Run
`python -m benchmarks.benchmark_startup` before/after any change that touches
imports in `handwave/vision/camera_manager.py` or `handwave/ui/main_window.py`.

## Regenerating documentation screenshots

```powershell
python scripts\capture_docs_screenshots.py
```

Uses simulated Qt signals and labels the camera image `DOCUMENTATION
PREVIEW`. Review every generated image before committing it.
