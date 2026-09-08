from handwave.config.settings_manager import SettingsManager
from handwave.services.startup_manager import WindowsStartupManager


def test_enable_startup_creates_windows_launcher(tmp_path):
    startup_folder = tmp_path / "Startup"
    startup = WindowsStartupManager(
        startup_folder=startup_folder,
        executable=r"C:\Python311\pythonw.exe",
        project_root=r"C:\Apps\HandWave",
    )

    startup.enable()

    assert startup.is_enabled
    launcher = startup.launcher_path.read_text(encoding="utf-8")
    assert 'cd /d "C:\\Apps\\HandWave"' in launcher
    assert '"C:\\Python311\\pythonw.exe" -m handwave.main' in launcher


def test_setting_toggle_persists_and_removes_launcher(tmp_path):
    startup = WindowsStartupManager(startup_folder=tmp_path / "Startup")
    config = tmp_path / "config" / "settings.json"
    settings = SettingsManager(config, startup_manager=startup)

    settings.set_startup_enabled(True)
    assert startup.is_enabled
    assert SettingsManager(config).settings.startup_enabled

    settings.set_startup_enabled(False)
    assert not startup.is_enabled
    assert not SettingsManager(config).settings.startup_enabled


def test_reboot_simulation_restores_missing_startup_launcher(tmp_path):
    startup_folder = tmp_path / "Startup"
    config = tmp_path / "settings.json"
    first_boot = WindowsStartupManager(startup_folder=startup_folder)
    SettingsManager(config, startup_manager=first_boot).set_startup_enabled(True)
    first_boot.launcher_path.unlink()

    rebooted_startup = WindowsStartupManager(startup_folder=startup_folder)
    rebooted_app = SettingsManager(config, startup_manager=rebooted_startup)
    rebooted_app.synchronize_startup()

    assert rebooted_app.settings.startup_enabled
    assert rebooted_startup.is_enabled
    assert "-m handwave.main" in rebooted_startup.launcher_path.read_text(encoding="utf-8")
