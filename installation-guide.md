# HandWave release guide

## Prerequisites

- Windows 10 or 11.
- Python 3.11 and the project `.venv` with `handwave/requirements.txt` installed.
- NSIS 3.x. Install it with `winget install --id NSIS.NSIS -e` if needed.

For a portable NSIS installation, set `NSIS_MAKENSIS` to the absolute path of
`makensis.exe` before running the build.

## Build

From the repository root, run:

```powershell
.\build_release.cmd
```

The release pipeline:

1. Runs all tests, enforces the 80% coverage gate, and generates test reports.
2. Builds the windowed, single-file `HandWave.exe` using PyInstaller.
3. Builds the per-user NSIS installer.
4. Generates SHA-256 checksums for both executable artifacts.

## Outputs

- `dist/HandWave.exe` — portable Windows executable.
- `dist/HandWave-1.0.0-rc.1-Setup.exe` — interactive installer.
- `dist/SHA256SUMS.txt` — release checksums.

## Installer behavior

The installer does not require administrator rights. It installs into
`%LOCALAPPDATA%\Programs\HandWave`, creates a desktop shortcut and a HandWave
Start Menu folder, and registers HandWave in Windows **Installed apps**.

Silent installation:

```powershell
.\HandWave-1.0.0-rc.1-Setup.exe /S
```

## Uninstall

Use **Settings > Apps > Installed apps > HandWave**, the **Uninstall HandWave**
Start Menu entry, or run:

```powershell
"$env:LOCALAPPDATA\Programs\HandWave\Uninstall.exe"
```

Silent uninstall:

```powershell
& "$env:LOCALAPPDATA\Programs\HandWave\Uninstall.exe" /S
```

Uninstall removes the application, desktop shortcut, Start Menu entries, and
uninstall registration. User settings under `%APPDATA%\HandWave` are retained so
an upgrade or reinstall preserves preferences.