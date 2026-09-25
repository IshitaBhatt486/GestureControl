# Double-clap reliability report

## Root cause

The microphone stream was opened at a hard-coded 44,100 Hz on an unvalidated
Windows default device. On this machine, opening that MME endpoint fails with
PortAudio `-9999` (MME error 11), so no audio callback can run. The old code
also had no device identity in diagnostics, no fallback/recovery, and could
emit a GUI-affecting Qt signal from PortAudio's native callback thread.

## Targeted changes

- `handwave/services/clap_detector.py`
  - Validates the configured/default microphone and logs its index, name, and
    native sample rate before opening a stream.
  - Uses each device's default sample rate; tries other input devices when the
    Windows default cannot open.
  - Logs stream start, first callback, sampled peak/RMS telemetry, clap,
    double-clap, and outgoing Qt toggle.
  - Queues callback-originated double-clap delivery to the detector's Qt
    thread before UI receivers run.
  - Adds scalar status fields, callback watchdog, exponential retry, and
    recovery after callback/status/device faults. Permission/access failures
    include the Windows microphone privacy setting guidance.
  - Makes peak threshold, noise multiplier, device index, and double-clap
    window configurable.
- `handwave/config/settings_manager.py`
  - Persists and validates the microphone and clap controls.
- `handwave/ui/settings_dialog.py`
  - Adds a Microphone settings tab for those controls.
- `handwave/ui/diagnostics_page.py` and `handwave/ui/main_window.py`
  - Show selected device, stream health, RMS, peak, and last-clap timestamp;
    log receipt of the UI-thread activation toggle.
- `tests/test_clap_detector.py`, `tests/test_settings_manager.py`
  - Cover selected-device status and persisted configurable thresholds/window.

## Verification

- Device enumeration found Windows default input index `1` (Intel microphone
  array) with input channels.
- Direct stream creation at the old fixed 44,100 Hz failed with PortAudio
  `-9999` / MME error 11, reproducing the observed no-callback failure.
- Focused test run: `53 passed` using a workspace-local pytest temp directory.
- The standard user Temp directory is permission-denied in this execution
  environment, so the focused run used `--basetemp .test-tmp/...` and
  `--no-cov`; this is unrelated to application behavior.
