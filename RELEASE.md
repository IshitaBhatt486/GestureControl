# GestureOS release guide

## Prerequisites

- Windows 10 or 11.
- Python 3.11 and the project `.venv` with `gestureos/requirements.txt` installed.
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
2. Builds the windowed, single-file `GestureOS.exe` using PyInstaller.
3. Builds the per-user NSIS installer.
4. Generates SHA-256 checksums for both executable artifacts.

## Outputs

- `dist/GestureOS.exe` — portable Windows executable.
- `dist/GestureOS-1.0.0-rc.1-Setup.exe` — interactive and silent installer.
- `dist/SHA256SUMS.txt` — release checksums.

## Installer behavior

The installer does not require administrator rights. It installs into
`%LOCALAPPDATA%\Programs\GestureOS`, creates a desktop shortcut and a GestureOS
Start Menu folder, and registers GestureOS in Windows **Installed apps**.

Silent installation:

```powershell
.\GestureOS-1.0.0-rc.1-Setup.exe /S
```

## Uninstall

Use **Settings > Apps > Installed apps > GestureOS**, the **Uninstall GestureOS**
Start Menu entry, or run:

```powershell
"$env:LOCALAPPDATA\Programs\GestureOS\Uninstall.exe"
```

Silent uninstall:

```powershell
& "$env:LOCALAPPDATA\Programs\GestureOS\Uninstall.exe" /S
```

Uninstall removes the application, desktop shortcut, Start Menu entries, and
uninstall registration. User settings under `%APPDATA%\GestureOS` are retained so
an upgrade or reinstall preserves preferences.

## Release checklist

1. Update `gestureos/version.py` and `packaging/version_info.txt` together.
2. Run `.\build_release.cmd` on a clean Windows checkout.
3. Verify `SHA256SUMS.txt` against both artifacts.
4. Test interactive install, application launch, upgrade, and uninstall in a clean VM.
5. Code-sign both `.exe` files before public distribution when a signing certificate is available.
