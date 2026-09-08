"""Validated JSON settings storage."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from handwave.actions.action_definition import ActionDefinition
from handwave.services.startup_manager import WindowsStartupManager
from handwave.config.atomic_write import atomic_replace
from handwave.config.gesture_config import (
    ACTIONS,
    GESTURES,
    complete_bindings,
    complete_enabled,
)

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class AppSettings:
    camera_index: int = 0
    gesture_sensitivity: float = 0.6
    gesture_cooldown: float = 1.0
    startup_enabled: bool = False
    overlay_enabled: bool = True
    gesture_bindings: dict[str, ActionDefinition] = field(default_factory=complete_bindings)
    enabled_gestures: dict[str, bool] = field(default_factory=complete_enabled)
    theme: str = "dark"
    auto_switch_profiles: bool = True

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
        if not isinstance(self.auto_switch_profiles, bool):
            raise ValueError("auto_switch_profiles must be a boolean")
        normalized_bindings = complete_bindings(self.gesture_bindings)
        object.__setattr__(self, "gesture_bindings", normalized_bindings)
        if set(normalized_bindings) != set(GESTURES):
            raise ValueError("gesture_bindings must contain every supported gesture")
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
        / "HandWave"
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
        self._backup_path = self.path.with_suffix(self.path.suffix + ".bak")
        self.startup_manager = startup_manager
        self.settings = self.load()

    def load(self) -> AppSettings:
        for candidate in (self.path, self._backup_path):
            if not candidate.exists():
                continue
            try:
                raw = json.loads(candidate.read_text(encoding="utf-8"))
                # schema_version is informational for now: the field set has not
                # changed shape since version 1, so no migration is required yet.
                values = {key: value for key, value in raw.items() if key in self.FIELDS}
                values["gesture_bindings"] = complete_bindings(values.get("gesture_bindings"))
                values["enabled_gestures"] = complete_enabled(values.get("enabled_gestures"))
                return AppSettings(**values)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue
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
        if self.path.exists():
            try:
                self._backup_path.write_bytes(self.path.read_bytes())
            except OSError:
                pass
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        payload: dict[str, Any] = {"schema_version": SCHEMA_VERSION, **asdict(self.settings)}
        payload["gesture_bindings"] = {
            gesture: action.to_dict()
            for gesture, action in self.settings.gesture_bindings.items()
        }
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        atomic_replace(temporary, self.path)

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
