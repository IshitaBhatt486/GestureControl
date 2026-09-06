"""Validated JSON settings storage."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from gestureos.services.startup_manager import WindowsStartupManager
from gestureos.config.gesture_config import (
    ACTIONS,
    GESTURES,
    complete_bindings,
    complete_enabled,
)


@dataclass(frozen=True)
class AppSettings:
    camera_index: int = 0
    gesture_sensitivity: float = 0.6
    gesture_cooldown: float = 1.0
    startup_enabled: bool = False
    overlay_enabled: bool = True
    gesture_bindings: dict[str, str] = field(default_factory=complete_bindings)
    enabled_gestures: dict[str, bool] = field(default_factory=complete_enabled)
    theme: str = "dark"

    def __post_init__(self) -> None:
        if not isinstance(self.camera_index, int) or isinstance(self.camera_index, bool) or self.camera_index < 0:
            raise ValueError("camera_index must be a non-negative integer")
        if (
            not isinstance(self.gesture_sensitivity, (int, float))
            or isinstance(self.gesture_sensitivity, bool)
            or not 0.0 <= self.gesture_sensitivity <= 1.0
        ):
            raise ValueError("gesture_sensitivity must be between 0 and 1")
        if (
            not isinstance(self.gesture_cooldown, (int, float))
            or isinstance(self.gesture_cooldown, bool)
            or self.gesture_cooldown < 0
        ):
            raise ValueError("gesture_cooldown cannot be negative")
        if not isinstance(self.startup_enabled, bool) or not isinstance(self.overlay_enabled, bool):
            raise ValueError("startup_enabled and overlay_enabled must be booleans")
        if set(self.gesture_bindings) != set(GESTURES):
            raise ValueError("gesture_bindings must contain every supported gesture")
        if any(action not in ACTIONS for action in self.gesture_bindings.values()):
            raise ValueError("gesture_bindings contains an unsupported action")
        if set(self.enabled_gestures) != set(GESTURES):
            raise ValueError("enabled_gestures must contain every supported gesture")
        if any(not isinstance(enabled, bool) for enabled in self.enabled_gestures.values()):
            raise ValueError("enabled_gestures values must be booleans")
        if self.theme not in {"dark", "light"}:
            raise ValueError("theme must be 'dark' or 'light'")


class SettingsManager:
    """Load and atomically save application settings across restarts."""

    DEFAULT_PATH = (
        Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        / "GestureOS"
        / "config"
        / "settings.json"
        if getattr(sys, "frozen", False)
        else Path(__file__).with_name("settings.json")
    )
    FIELDS = set(AppSettings.__dataclass_fields__)

    def __init__(
        self,
        path: str | Path | None = None,
        startup_manager: WindowsStartupManager | None = None,
    ) -> None:
        self.path = Path(path) if path is not None else self.DEFAULT_PATH
        self.startup_manager = startup_manager
        self.settings = self.load()

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            values = {key: value for key, value in raw.items() if key in self.FIELDS}
            values["gesture_bindings"] = complete_bindings(values.get("gesture_bindings"))
            values["enabled_gestures"] = complete_enabled(values.get("enabled_gestures"))
            return AppSettings(**values)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return AppSettings()

    def update(self, **changes: Any) -> AppSettings:
        unknown = set(changes) - self.FIELDS
        if unknown:
            raise KeyError(f"Unknown settings: {', '.join(sorted(unknown))}")
        updated = replace(self.settings, **changes)
        self.settings = updated
        self.save()
        return updated

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(asdict(self.settings), indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    def set_startup_enabled(self, enabled: bool) -> AppSettings:
        """Toggle both the persisted setting and Windows Startup launcher."""
        if not isinstance(enabled, bool):
            raise ValueError("startup_enabled must be a boolean")
        if self.startup_manager is not None:
            self.startup_manager.set_enabled(enabled)
        return self.update(startup_enabled=enabled)

    def synchronize_startup(self) -> None:
        """Repair the Startup launcher to match the persisted setting on launch."""
        if self.startup_manager is not None:
            self.startup_manager.set_enabled(self.settings.startup_enabled)
