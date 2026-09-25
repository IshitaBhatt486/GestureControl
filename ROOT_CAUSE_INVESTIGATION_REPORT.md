# HandWave root-cause investigation

## Architecture verified from source

`handwave/main.py` constructs `MainWindow`, starts `ClapDetector`, and enters
the Qt event loop. `MainWindow` connects `ClapDetector.double_clap` to the
recognition toggle. `ClapDetector` opens a `sounddevice.InputStream`, computes
peak/RMS in its callback, applies its two-clap state machine, then queues the
Qt signal onto the GUI thread. `MicrophoneDialog` reads the same scalar status
and persists calibration values through `SettingsManager`.

The release path is `build_release.cmd` -> `build_release.ps1` ->
`run_tests.cmd` -> PyInstaller (`HandWave.spec`) -> NSIS (`HandWave.nsi`).

## Evidence and root causes

### Double-clap capture

The live device test found default input device 1 and reproduced PortAudio
`-9999` / MME error 11 when opening it. The detector then tried other inputs.
Before this investigation it could bind `Stereo Mix`; the test observed 69
callbacks from that endpoint in 1.5 seconds. Stereo Mix is playback loopback,
not a physical microphone, so it is not valid clap capture.

The detector now tries the selected/default input and then only input names
containing `microphone`; loopback/speaker endpoints are not silently used.
If no physical microphone opens, automatic recovery reports a microphone
error instead of listening to the wrong source.

### Build

The first build-gate failure was the full test suite, not PyInstaller:
`Pointing Up`, `Pointing Down`, `Pointing Left`, and `Pointing Right` existed
in `GESTURES` but not in `GESTURE_GLYPHS`. The settings-tab test also had an
obsolete expected tab list after the Microphone tab was introduced.

The clean PyInstaller work directory is isolated in `.build-release` to avoid
the reproduced stale-work-dir `WinError 5`. NSIS remains unavailable on this
machine: `makensis.exe` was absent from PATH and both standard install paths.
Installer generation therefore requires NSIS installation or `NSIS_MAKENSIS`.

### Retry button and calibration UX

`MicrophoneDialog` no longer contains a Retry button or a retry signal-slot.
It requests automatic detector startup and relies on the detector recovery
timer/watchdog. The dialog includes background-noise sampling, five-clap
sampling, calculated peak/RMS thresholds, saved timing values, confidence,
and reset/recalibrate actions.

## Modified files and minimal diffs

| File | Change |
|---|---|
| `handwave/services/clap_detector.py` | Restrict fallback capture inputs to physical microphone names. |
| `tests/test_clap_detector.py` | Add regression test excluding Stereo Mix/speaker loopback. |
| `handwave/ui/gesture_icons.py` | Add local glyphs for all configured pointing gestures. |
| `tests/test_settings_dialog.py` | Update the expected settings tabs to include Microphone. |
| `handwave/ui/microphone_dialog.py` | Current wizard/retry removal implementation. |
| `handwave/config/settings_manager.py` | Current persisted RMS calibration threshold. |
| `build_release.ps1`, `HandWave.spec` | Current release diagnostics/work-directory hardening. |

## Validation

- Full test/coverage gate: **343 passed** after the final fallback regression
  test; minimum coverage remains above the configured 80% threshold.
- Live capture: default MME microphone failure was reproduced; loopback
  fallback was reproduced and is now prevented.
- `makensis.exe` availability: **not installed**.

## Risks and recommendations

- Some hardware drivers use names that do not contain `microphone`. Users can
  select a configured device index; consider exposing friendly device names in
  the selector rather than relying on names for automatic fallback.
- The final NSIS installer cannot be verified until NSIS is installed.
- Run the packaged executable on a clean Windows account after NSIS is
  available, including a physical-microphone double-clap test.
