from pathlib import Path


def test_release_spec_has_single_executable_icon_and_version():
    root = Path(__file__).resolve().parents[1]
    spec = (root / "GestureOS.spec").read_text(encoding="utf-8")
    assert 'name="GestureOS"' in spec
    assert 'icon="gestureos/assets/gestureos.ico"' in spec
    assert 'version="packaging/version_info.txt"' in spec
    assert "COLLECT(" not in spec
    assert (root / "gestureos" / "assets" / "gestureos.ico").is_file()


def test_nsis_installer_defines_shortcuts_registration_and_uninstaller():
    root = Path(__file__).resolve().parents[1]
    installer = (root / "packaging" / "GestureOS.nsi").read_text(encoding="utf-8")

    assert 'OutFile "..\\dist\\GestureOS-${PRODUCT_VERSION}-Setup.exe"' in installer
    assert 'InstallDir "$LOCALAPPDATA\\Programs\\GestureOS"' in installer
    assert 'CreateShortcut "$DESKTOP\\GestureOS.lnk"' in installer
    assert 'CreateShortcut "$SMPROGRAMS\\GestureOS\\GestureOS.lnk"' in installer
    assert 'WriteUninstaller "$INSTDIR\\Uninstall.exe"' in installer
    assert 'WriteRegStr HKCU "${UNINSTALL_REGKEY}" "UninstallString"' in installer
    assert 'Section "Uninstall"' in installer
    assert 'Delete "$DESKTOP\\GestureOS.lnk"' in installer


def test_release_pipeline_builds_installer_and_checksums():
    root = Path(__file__).resolve().parents[1]
    script = (root / "build_release.ps1").read_text(encoding="utf-8")

    assert "PyInstaller" in script
    assert "GestureOS.nsi" in script
    assert "makensis" in script
    assert "Get-FileHash -Algorithm SHA256" in script
