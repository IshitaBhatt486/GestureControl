"""Current-user Windows Startup folder integration."""

from __future__ import annotations

import os
import sys
from pathlib import Path


class WindowsStartupManager:
    """Create or remove GestureOS's launcher in the Windows Startup folder."""

    LAUNCHER_NAME = "GestureOS.cmd"

    def __init__(
        self,
        startup_folder: str | Path | None = None,
        executable: str | Path | None = None,
        project_root: str | Path | None = None,
    ) -> None:
        self.startup_folder = (
            Path(startup_folder) if startup_folder is not None else self.default_startup_folder()
        )
        self.executable = Path(executable) if executable is not None else self._default_executable()
        self.project_root = (
            Path(project_root) if project_root is not None else Path(__file__).resolve().parents[2]
        )

    @staticmethod
    def default_startup_folder() -> Path:
        roaming = os.environ.get("APPDATA")
        base = Path(roaming) if roaming else Path.home() / "AppData" / "Roaming"
        return base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

    @staticmethod
    def _default_executable() -> Path:
        executable = Path(sys.executable)
        if executable.name.lower() == "python.exe":
            pythonw = executable.with_name("pythonw.exe")
            if pythonw.exists():
                return pythonw
        return executable

    @property
    def launcher_path(self) -> Path:
        return self.startup_folder / self.LAUNCHER_NAME

    @property
    def is_enabled(self) -> bool:
        return self.launcher_path.is_file()

    def enable(self) -> None:
        self.startup_folder.mkdir(parents=True, exist_ok=True)
        if getattr(sys, "frozen", False):
            contents = "@echo off\n" f'start "" "{self.executable}"\n'
        else:
            contents = (
                "@echo off\n"
                f'cd /d "{self.project_root}"\n'
                f'start "" "{self.executable}" -m gestureos.main\n'
            )
        temporary = self.launcher_path.with_suffix(".cmd.tmp")
        temporary.write_text(contents, encoding="utf-8")
        temporary.replace(self.launcher_path)

    def disable(self) -> None:
        self.launcher_path.unlink(missing_ok=True)

    def set_enabled(self, enabled: bool) -> None:
        self.enable() if enabled else self.disable()
