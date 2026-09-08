# Changelog

All notable changes are documented here. This project follows Semantic
Versioning; release-candidate suffixes identify pre-release builds.

## 1.0.0-rc.1 - 2026-09-06

### Added

- Responsive dark/light desktop dashboard, confidence display, and diagnostics page.
- JSON gesture rebinding, sensitivity controls, enable switches, and persistence.
- Camera, recognition, latency, CPU, RAM, dropped-frame, and thread metrics.
- Unit, integration, UI, benchmark, documentation, and packaging tests.
- PyInstaller executable, NSIS installer, shortcuts, uninstaller, and checksums.
- Complete user, developer, architecture, benchmark, and troubleshooting guides.
- Keyboard shortcuts and screen-reader names for primary application controls.

### Changed

- Capture, recognition, and actions now use separate workers with a capacity-one
  latest-frame buffer and stale-frame dropping.
- Camera retry is held until asynchronous worker teardown completes.

### Known limitations

- Windows 10/11 is the supported desktop platform.
- Public binaries are not code-signed; Windows SmartScreen may warn on first run.
- Real-world recognition quality depends on lighting, camera placement, and hardware.