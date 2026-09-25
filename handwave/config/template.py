"""Reusable HandWave behavior templates layered between globals and app profiles."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from typing import Any

from handwave.actions.action_definition import ActionDefinition
from handwave.config.gesture_config import GESTURES


def new_template_id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True)
class Template:
    """A sparse, independently persisted layer of reusable behavior overrides.

    Resolution is always ``global settings -> template -> application profile``.
    Gesture dictionaries are copied on every mutation, so no template can
    modify another template's bindings or enablement state.
    """

    template_id: str = field(default_factory=new_template_id)
    name: str = "New Template"
    gesture_sensitivity: float | None = None
    gesture_cooldown: float | None = None
    gesture_bindings: dict[str, ActionDefinition] = field(default_factory=dict)
    enabled_gestures: dict[str, bool] = field(default_factory=dict)
    # Persisted template-scoped feature settings. They remain local data until
    # their corresponding V2 controllers are enabled.
    mouse_settings: dict[str, Any] = field(default_factory=dict)
    pinch_settings: dict[str, Any] = field(default_factory=dict)
    clap_settings: dict[str, Any] = field(default_factory=dict)
    two_hand_settings: dict[str, Any] = field(default_factory=dict)
    custom_gesture_ids: tuple[str, ...] = ()
    application_mappings: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.template_id, str) or not self.template_id:
            raise ValueError("template_id must be a non-empty string")
        if not isinstance(self.name, str) or not self.name.strip() or len(self.name) > 200:
            raise ValueError("Template name must be between 1 and 200 characters")
        if self.gesture_sensitivity is not None and not 0.0 <= float(self.gesture_sensitivity) <= 1.0:
            raise ValueError("gesture_sensitivity must be between 0 and 1")
        if self.gesture_cooldown is not None and float(self.gesture_cooldown) < 0:
            raise ValueError("gesture_cooldown cannot be negative")
        unknown = set(self.gesture_bindings) - set(GESTURES)
        if unknown:
            raise ValueError(f"Unknown gestures in template: {', '.join(sorted(unknown))}")
        unknown = set(self.enabled_gestures) - set(GESTURES)
        if unknown:
            raise ValueError(f"Unknown enabled gestures in template: {', '.join(sorted(unknown))}")
        if any(not isinstance(value, bool) for value in self.enabled_gestures.values()):
            raise ValueError("enabled_gestures values must be booleans")
        for value in (self.mouse_settings, self.pinch_settings, self.clap_settings, self.two_hand_settings, self.application_mappings):
            if not isinstance(value, dict):
                raise ValueError("Template feature settings must be objects")
        if any(not isinstance(value, str) or not value for value in self.custom_gesture_ids):
            raise ValueError("custom_gesture_ids must contain non-empty strings")
        object.__setattr__(self, "gesture_bindings", {key: ActionDefinition.from_data(value) for key, value in self.gesture_bindings.items()})
        object.__setattr__(self, "enabled_gestures", dict(self.enabled_gestures))
        for field_name in ("mouse_settings", "pinch_settings", "clap_settings", "two_hand_settings", "application_mappings"):
            object.__setattr__(self, field_name, dict(getattr(self, field_name)))
        object.__setattr__(self, "custom_gesture_ids", tuple(self.custom_gesture_ids))

    def resolve(self, global_settings: Any) -> Any:
        bindings = dict(global_settings.gesture_bindings)
        bindings.update(self.gesture_bindings)
        enabled = dict(global_settings.enabled_gestures)
        enabled.update(self.enabled_gestures)
        return replace(
            global_settings,
            gesture_sensitivity=global_settings.gesture_sensitivity if self.gesture_sensitivity is None else self.gesture_sensitivity,
            gesture_cooldown=global_settings.gesture_cooldown if self.gesture_cooldown is None else self.gesture_cooldown,
            gesture_bindings=bindings,
            enabled_gestures=enabled,
        )

    def duplicate(self, name: str | None = None) -> "Template":
        return replace(
            self,
            template_id=new_template_id(),
            name=name or f"{self.name} (copy)",
            gesture_bindings=dict(self.gesture_bindings), enabled_gestures=dict(self.enabled_gestures),
            mouse_settings=dict(self.mouse_settings), pinch_settings=dict(self.pinch_settings),
            clap_settings=dict(self.clap_settings), two_hand_settings=dict(self.two_hand_settings),
            custom_gesture_ids=tuple(self.custom_gesture_ids), application_mappings=dict(self.application_mappings),
        )

    def to_dict(self) -> dict[str, Any]:
        result = {key: value for key, value in self.__dict__.items() if key != "gesture_bindings"}
        result["gesture_bindings"] = {key: value.to_dict() for key, value in self.gesture_bindings.items()}
        result["custom_gesture_ids"] = list(self.custom_gesture_ids)
        return result

    @classmethod
    def from_data(cls, data: object) -> "Template":
        if not isinstance(data, dict):
            raise ValueError("Template must be an object")
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"Unknown template fields: {', '.join(sorted(unknown))}")
        values = dict(data)
        values["gesture_bindings"] = {key: ActionDefinition.from_data(value) for key, value in (values.get("gesture_bindings") or {}).items()}
        return cls(**values)
