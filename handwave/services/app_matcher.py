"""Deterministic, recognition-independent matching from a foreground app to a profile."""

from __future__ import annotations

from dataclasses import dataclass

from handwave.config.profile import Profile, normalize_executable


@dataclass(frozen=True)
class AppMatch:
    """The outcome of matching the foreground application against known profiles."""

    profile: Profile | None
    reason: str


def select_profile(
    profiles: list[Profile],
    executable: str | None,
    window_title: str | None = None,
) -> AppMatch:
    """Pick the profile that should be active for the given foreground application.

    Priority, most to least specific:
      1. profiles explicitly disabled are never selected
      2. an executable match with a matching window-title pattern (most specific)
      3. an executable-only match
      4. no match -> the global profile (``None``)
    """
    candidates = [profile for profile in profiles if profile.enabled and profile.app_executable]
    if not candidates or not executable:
        return AppMatch(None, "global_fallback")

    target = normalize_executable(executable)
    exact = [profile for profile in candidates if profile.app_executable == target]
    if not exact:
        return AppMatch(None, "global_fallback")

    title = (window_title or "").lower()
    specific = [
        profile
        for profile in exact
        if profile.app_window_title_pattern and profile.app_window_title_pattern.lower() in title
    ]
    if specific:
        return AppMatch(_choose_deterministic(specific), "window_title_match")
    return AppMatch(_choose_deterministic(exact), "executable_match")


def _choose_deterministic(profiles: list[Profile]) -> Profile:
    """Break ties between equally-specific matches by the lowest profile id."""
    return min(profiles, key=lambda profile: profile.profile_id)
