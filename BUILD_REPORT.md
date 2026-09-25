# Release build report

## Root causes reproduced

1. The release gate first failed in
   `tests/test_fingerprint_indicator.py::test_disappearance_fades_and_reappearance_restores_contact`.
   It assumed five 16 ms Qt timer ticks would always occur during an 80 ms
   wait. Under load, fewer ticks occur, so the release test gate was flaky.
2. The subsequent clean PyInstaller invocation failed removing the stale,
   locked `build\\HandWave\\localpycs` directory with `PermissionError:
   [WinError 5] Access is denied`. The old script retried without `--clean`,
   concealing that failure and risking a stale executable.
3. NSIS is not installed or discoverable on this machine (`makensis.exe` is
   absent from PATH and the standard NSIS installation paths). Installer
   creation cannot run until it is installed or `NSIS_MAKENSIS` points to it.

## Changes

- `tests/test_fingerprint_indicator.py`: replaces the timing assumption with
  a bounded `waitUntil` for the observable fade-completion condition.
- `build_release.ps1`:
  - logs named release stages;
  - validates Python 3.11, required imports/versions, release inputs, icon,
    settings asset, and packaging files before building;
  - uses `.build-release` as a dedicated PyInstaller work path;
  - retains `--clean` and fails immediately instead of silently retrying a
    non-clean build;
  - labels the NSIS packaging stage clearly.
- `build_release.cmd`: adds a visible release-build banner.
- `HandWave.spec`: excludes unused MediaPipe GenAI/test hidden imports.

## Verification

- Python: `3.11.9`.
- Imports verified: PyInstaller 6.22.2, MediaPipe 0.10.14, PyQt6 6.11.0,
  NumPy 2.4.6, OpenCV 4.14.0.94, sounddevice 0.5.6.
- Assets and spec inputs exist; `HandWave.spec` collects MediaPipe binaries,
  data, and hidden imports and includes the application icon/settings asset.
- The isolated clean PyInstaller stage begins successfully and no longer
  fails on the old locked work directory. A superseded long-running analysis
  was stopped after the spec was narrowed; rerun `build_release.cmd` to build
  the final executable with the updated spec.
- NSIS installer generation remains blocked until NSIS is installed. Use
  `winget install --id NSIS.NSIS -e`, or set `NSIS_MAKENSIS` to an existing
  `makensis.exe`, then run `build_release.cmd`.
