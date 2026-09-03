"""GestureOS application entry point."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

from gestureos.ui.main_window import MainWindow
from gestureos.config.settings_manager import SettingsManager
from gestureos.services.startup_manager import WindowsStartupManager


def resource_path(relative: str) -> Path:
    """Resolve bundled PyInstaller resources and source-tree assets."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return root / relative


def configure_logging() -> None:
    """Configure console and file logging for the application."""
    log_dir = Path.home() / ".gestureos"
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_dir / "gestureos.log", encoding="utf-8"))
    except OSError:
        # Console logging still works if the user's home directory is read-only.
        pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=handlers,
        force=True,
    )


def main() -> int:
    configure_logging()
    logger = logging.getLogger(__name__)
    try:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        app.setApplicationName("GestureOS")
        app.setOrganizationName("GestureOS")
        app.setApplicationVersion("1.0.0")
        from PyQt6.QtGui import QIcon

        app.setWindowIcon(QIcon(str(resource_path("gestureos/assets/gestureos.ico"))))
        settings = SettingsManager(startup_manager=WindowsStartupManager())
        settings.synchronize_startup()
        window = MainWindow(settings_manager=settings)
        window.clap_detector.start()
        window.show()
        QTimer.singleShot(0, window.show_onboarding_if_needed)
        logger.info("GestureOS started")
        return app.exec()
    except Exception as exc:  # Last-resort GUI startup guard.
        logger.exception("GestureOS failed to start")
        if QApplication.instance() is not None:
            QMessageBox.critical(None, "GestureOS", f"Unable to start GestureOS:\n{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
