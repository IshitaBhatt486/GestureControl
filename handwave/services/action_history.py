"""Bounded audit trail of recognized gestures and their action outcomes."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class HistoryEntry:
    """One row of the action-history/diagnostics view."""

    timestamp: float
    gesture: str | None
    confidence: float
    action: str
    executed: bool
    blocked_reason: str | None = None
    application: str | None = None
    profile: str | None = None

    @property
    def result_text(self) -> str:
        return "Executed" if self.executed else f"Blocked: {self.blocked_reason or 'unknown reason'}"


class ActionHistory:
    """Fixed-capacity ring buffer so the UI can never grow this without limit."""

    def __init__(self, max_entries: int = 200, clock: Callable[[], float] = time.time) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._clock = clock
        self._entries: deque[HistoryEntry] = deque(maxlen=max_entries)

    @property
    def max_entries(self) -> int:
        return self._entries.maxlen  # type: ignore[return-value]

    def record(
        self,
        gesture: str | None,
        confidence: float,
        action: str,
        executed: bool,
        blocked_reason: str | None = None,
        application: str | None = None,
        profile: str | None = None,
        timestamp: float | None = None,
    ) -> HistoryEntry:
        entry = HistoryEntry(
            timestamp=self._clock() if timestamp is None else timestamp,
            gesture=gesture,
            confidence=confidence,
            action=action,
            executed=executed,
            blocked_reason=blocked_reason,
            application=application,
            profile=profile,
        )
        self._entries.append(entry)
        return entry

    def recent(self, limit: int | None = None) -> list[HistoryEntry]:
        """Most-recent-first entries, optionally capped at ``limit``."""
        entries = list(reversed(self._entries))
        return entries if limit is None else entries[:limit]

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
