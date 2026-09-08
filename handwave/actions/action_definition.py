"""Validated, serializable descriptions of local gesture actions."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Any, ClassVar


ACTION_TYPES = {
    "none": "No action",
    "media": "Media action",
    "key": "Keyboard key",
    "hotkey": "Keyboard combination",
    "mouse": "Mouse action",
    "text": "Type text",
    "command": "Launch program",
}

MEDIA_ACTIONS = {
    "play_pause": "Play / Pause",
    "next_track": "Next Track",
    "previous_track": "Previous Track",
    "volume_up": "Volume Up",
    "volume_down": "Volume Down",
    "mute": "Mute",
}

MOUSE_ACTIONS = {
    "left_click": "Left click",
    "right_click": "Right click",
    "middle_click": "Middle click",
    "scroll_up": "Scroll up",
    "scroll_down": "Scroll down",
}

_KEY_ALIASES = {
    "escape": "esc",
    "control": "ctrl",
    "return": "enter",
    "pageup": "pageup",
    "pagedown": "pagedown",
    "spacebar": "space",
}
_MODIFIERS = {"ctrl", "alt", "shift", "win", "command"}


def normalize_key(value: str) -> str:
    key = value.strip().lower().replace(" ", "")
    key = _KEY_ALIASES.get(key, key)
    if not key or len(key) > 32 or any(character in key for character in "+\n\r\0"):
        raise ValueError("Keyboard key must be one non-empty key name")
    return key


def parse_hotkey(value: str) -> tuple[str, ...]:
    parts = tuple(normalize_key(part) for part in value.split("+"))
    if len(parts) < 2 or len(parts) > 5:
        raise ValueError("Keyboard combinations require between two and five keys")
    if len(set(parts)) != len(parts):
        raise ValueError("Keyboard combinations cannot repeat a key")
    if not any(part in _MODIFIERS for part in parts[:-1]):
        raise ValueError("Keyboard combinations must begin with a modifier key")
    return parts


def parse_command(value: str | list[str] | tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(value, str):
        try:
            parts = tuple(part.strip('"') for part in shlex.split(value, posix=False))
        except ValueError as exc:
            raise ValueError("Program command contains invalid quoting") from exc
    elif isinstance(value, (list, tuple)):
        parts = tuple(value)
    else:
        raise ValueError("Program command must be a command line or argument list")
    if not 1 <= len(parts) <= 64 or any(not isinstance(part, str) for part in parts):
        raise ValueError("Program command must contain 1 to 64 string arguments")
    if any(not part or len(part) > 2048 or any(char in part for char in "\n\r\0") for part in parts):
        raise ValueError("Program command contains an empty or invalid argument")
    return parts


@dataclass(frozen=True)
class ActionDefinition:
    """A side-effect-free action request created from trusted configuration."""

    type: str = "none"
    value: str | tuple[str, ...] = ""
    requires_confirmation: bool = False
    hold_duration: float = 0.0
    cooldown: float | None = None

    CONFIRMATION_HOLD: ClassVar[float] = 1.5

    def __post_init__(self) -> None:
        if self.type not in ACTION_TYPES:
            raise ValueError(f"Unsupported action type: {self.type}")
        if not isinstance(self.requires_confirmation, bool):
            raise ValueError("requires_confirmation must be a boolean")
        if (
            not isinstance(self.hold_duration, (int, float))
            or isinstance(self.hold_duration, bool)
            or not 0.0 <= self.hold_duration <= 10.0
        ):
            raise ValueError("hold_duration must be between 0 and 10 seconds")
        if (
            self.cooldown is not None
            and (
                not isinstance(self.cooldown, (int, float))
                or isinstance(self.cooldown, bool)
                or not 0.0 <= self.cooldown <= 60.0
            )
        ):
            raise ValueError("cooldown must be between 0 and 60 seconds")

        normalized: str | tuple[str, ...]
        if self.type == "none":
            normalized = ""
        elif self.type == "media":
            if self.value not in MEDIA_ACTIONS:
                raise ValueError("Unsupported media action")
            normalized = str(self.value)
        elif self.type == "key":
            normalized = normalize_key(str(self.value))
        elif self.type == "hotkey":
            keys = parse_hotkey(str(self.value))
            normalized = "+".join(keys)
        elif self.type == "mouse":
            if self.value not in MOUSE_ACTIONS:
                raise ValueError("Unsupported mouse action")
            normalized = str(self.value)
        elif self.type == "text":
            normalized = str(self.value)
            if not normalized or len(normalized) > 1000 or "\0" in normalized:
                raise ValueError("Text must contain between 1 and 1000 characters")
        else:
            normalized = parse_command(self.value)

        effective_hold = max(float(self.hold_duration), self.CONFIRMATION_HOLD) if self.requires_confirmation else float(self.hold_duration)
        dangerous_hotkey = self.type == "hotkey" and str(normalized) in {"alt+f4", "ctrl+alt+delete"}
        if (self.type == "command" or dangerous_hotkey) and effective_hold < self.CONFIRMATION_HOLD:
            raise ValueError("Program and potentially destructive actions require confirmation or a 1.5 second hold")
        object.__setattr__(self, "value", normalized)
        object.__setattr__(self, "hold_duration", float(self.hold_duration))
        if self.cooldown is not None:
            object.__setattr__(self, "cooldown", float(self.cooldown))

    @property
    def effective_hold_duration(self) -> float:
        return max(self.hold_duration, self.CONFIRMATION_HOLD) if self.requires_confirmation else self.hold_duration

    def to_dict(self) -> dict[str, Any]:
        value: str | list[str] = list(self.value) if isinstance(self.value, tuple) else self.value
        return {
            "type": self.type,
            "value": value,
            "requires_confirmation": self.requires_confirmation,
            "hold_duration": self.hold_duration,
            "cooldown": self.cooldown,
        }

    @classmethod
    def from_data(cls, data: object) -> "ActionDefinition":
        """Load structured data or a legacy media-action identifier."""
        if isinstance(data, cls):
            return data
        if isinstance(data, str):
            return cls("none") if data == "none" else cls("media", data)
        if not isinstance(data, dict):
            raise ValueError("Action configuration must be an object or legacy media identifier")
        allowed = {"type", "value", "requires_confirmation", "hold_duration", "cooldown"}
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"Unknown action fields: {', '.join(sorted(unknown))}")
        return cls(
            type=data.get("type", "none"),
            value=data.get("value", ""),
            requires_confirmation=data.get("requires_confirmation", False),
            hold_duration=data.get("hold_duration", 0.0),
            cooldown=data.get("cooldown"),
        )

    def describe(self) -> str:
        if self.type == "none":
            return "No action"
        if self.type == "media":
            return MEDIA_ACTIONS[str(self.value)]
        if self.type == "mouse":
            return MOUSE_ACTIONS[str(self.value)]
        if self.type == "command":
            return f"Launch {self.value[0]}"
        return str(self.value)
