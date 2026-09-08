"""Application profiles that override a sparse subset of global settings."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from typing import Any

from handwave.actions.action_definition import ActionDefinition
from handwave.config.gesture_config import GESTURES


def new_profile_id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True)
class Profile:
    """A named, independently editable override layer on top of global settings.

    Only fields explicitly set here diverge from the global configuration;
    everything else is inherited at resolution time via :meth:`resolve`.
    """

    profile_id: str = field(default_factory=new_profile_id)
    name: str = "New Profile"
    app_executable: str | None = None
    app_window_title_pattern: str | None = None
    enabled: bool = True
    gesture_sensitivity: float | None = None
    gesture_cooldown: float | None = None
    gesture_bindings: dict[str, ActionDefinition] = field(default_factory=dict)
    enabled_gestures: dict[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id:
            raise ValueError("profile_id must be a non-empty string")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Profile name must be a non-empty string")
        if len(self.name) > 200:
            raise ValueError("Profile name is too long")
        if self.app_executable is not None:
            executable = normalize_executable(self.app_executable)
            if not executable:
                raise ValueError("app_executable cannot be blank")
            object.__setattr__(self, "app_executable", executable)
        if self.app_window_title_pattern is not None and not self.app_window_title_pattern.strip():
            raise ValueError("app_window_title_pattern cannot be blank")
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")
        if self.gesture_sensitivity is not None and not 0.0 <= float(self.gesture_sensitivity) <= 1.0:
            raise ValueError("gesture_sensitivity must be between 0 and 1")
        if self.gesture_cooldown is not None and float(self.gesture_cooldown) < 0:
            raise ValueError("gesture_cooldown cannot be negative")
        unknown_gestures = set(self.gesture_bindings) - set(GESTURES)
        if unknown_gestures:
            raise ValueError(f"Unknown gestures in overrides: {', '.join(sorted(unknown_gestures))}")
        unknown_enabled = set(self.enabled_gestures) - set(GESTURES)
        if unknown_enabled:
            raise ValueError(f"Unknown gestures in enabled overrides: {', '.join(sorted(unknown_enabled))}")
        normalized_bindings = {
            gesture: ActionDefinition.from_data(action)
            for gesture, action in self.gesture_bindings.items()
        }
        object.__setattr__(self, "gesture_bindings", normalized_bindings)
        if any(not isinstance(value, bool) for value in self.enabled_gestures.values()):
            raise ValueError("enabled_gestures override values must be booleans")
        object.__setattr__(self, "enabled_gestures", dict(self.enabled_gestures))

    def resolve(self, global_settings: Any) -> Any:
        """Return an ``AppSettings``-shaped object with this profile's overrides applied."""
        merged_bindings = dict(global_settings.gesture_bindings)
        merged_bindings.update(self.gesture_bindings)
        merged_enabled = dict(global_settings.enabled_gestures)
        merged_enabled.update(self.enabled_gestures)
        return replace(
            global_settings,
            gesture_sensitivity=(
                global_settings.gesture_sensitivity
                if self.gesture_sensitivity is None
                else self.gesture_sensitivity
            ),
            gesture_cooldown=(
                global_settings.gesture_cooldown
                if self.gesture_cooldown is None
                else self.gesture_cooldown
            ),
            gesture_bindings=merged_bindings,
            enabled_gestures=merged_enabled,
        )

    def reset_overrides(self) -> "Profile":
        """Return a copy with every override cleared, keeping identity and app matching."""
        return replace(
            self,
            gesture_sensitivity=None,
            gesture_cooldown=None,
            gesture_bindings={},
            enabled_gestures={},
        )

    def duplicate(self, name: str | None = None) -> "Profile":
        """Return an independent copy with a new id and no shared mutable state."""
        return replace(
            self,
            profile_id=new_profile_id(),
            name=name or f"{self.name} (copy)",
            gesture_bindings=dict(self.gesture_bindings),
            enabled_gestures=dict(self.enabled_gestures),
        )

    def copy_overrides_from(self, source: "Profile") -> "Profile":
        """Adopt another profile's overrides while keeping this profile's identity."""
        return replace(
            self,
            gesture_sensitivity=source.gesture_sensitivity,
            gesture_cooldown=source.gesture_cooldown,
            gesture_bindings=dict(source.gesture_bindings),
            enabled_gestures=dict(source.enabled_gestures),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "app_executable": self.app_executable,
            "app_window_title_pattern": self.app_window_title_pattern,
            "enabled": self.enabled,
            "gesture_sensitivity": self.gesture_sensitivity,
            "gesture_cooldown": self.gesture_cooldown,
            "gesture_bindings": {
                gesture: action.to_dict() for gesture, action in self.gesture_bindings.items()
            },
            "enabled_gestures": dict(self.enabled_gestures),
        }

    @classmethod
    def from_data(cls, data: object) -> "Profile":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValueError("Profile configuration must be an object")
        allowed = set(cls.__dataclass_fields__)
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"Unknown profile fields: {', '.join(sorted(unknown))}")
        kwargs: dict[str, Any] = {key: value for key, value in data.items() if key != "gesture_bindings"}
        raw_bindings = data.get("gesture_bindings") or {}
        if not isinstance(raw_bindings, dict):
            raise ValueError("gesture_bindings must be an object")
        kwargs["gesture_bindings"] = {
            gesture: ActionDefinition.from_data(action) for gesture, action in raw_bindings.items()
        }
        return cls(**kwargs)


def normalize_executable(value: str) -> str:
    """Normalize a process image name for stable, case-insensitive comparison."""
    name = value.strip().lower().replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    return name
