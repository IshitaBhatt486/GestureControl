import pytest

from handwave.services.action_history import ActionHistory


def test_record_returns_entry_with_given_timestamp():
    history = ActionHistory()
    entry = history.record(
        gesture="Open Palm",
        confidence=0.9,
        action="Play / Pause",
        executed=True,
        timestamp=123.0,
    )
    assert entry.timestamp == 123.0
    assert entry.gesture == "Open Palm"
    assert entry.result_text == "Executed"


def test_blocked_entry_reports_reason_in_result_text():
    history = ActionHistory()
    entry = history.record(
        gesture="Thumbs Up",
        confidence=0.8,
        action="Volume Up",
        executed=False,
        blocked_reason="cooldown active",
        timestamp=1.0,
    )
    assert entry.result_text == "Blocked: cooldown active"


def test_recent_returns_most_recent_first():
    history = ActionHistory()
    history.record("A", 0.5, "a", True, timestamp=1.0)
    history.record("B", 0.5, "b", True, timestamp=2.0)
    history.record("C", 0.5, "c", True, timestamp=3.0)

    assert [entry.gesture for entry in history.recent()] == ["C", "B", "A"]


def test_recent_respects_limit():
    history = ActionHistory()
    for i in range(5):
        history.record(f"G{i}", 0.5, "a", True, timestamp=float(i))
    assert [entry.gesture for entry in history.recent(limit=2)] == ["G4", "G3"]


def test_history_is_bounded_and_never_grows_past_max_entries():
    history = ActionHistory(max_entries=3)
    for i in range(10):
        history.record(f"G{i}", 0.5, "a", True, timestamp=float(i))
    assert len(history) == 3
    assert [entry.gesture for entry in history.recent()] == ["G9", "G8", "G7"]


def test_clear_empties_history():
    history = ActionHistory()
    history.record("A", 0.5, "a", True, timestamp=1.0)
    history.clear()
    assert len(history) == 0
    assert history.recent() == []


def test_max_entries_must_be_positive():
    with pytest.raises(ValueError):
        ActionHistory(max_entries=0)


def test_entry_carries_application_and_profile_context():
    history = ActionHistory()
    entry = history.record(
        gesture="Swipe Left",
        confidence=0.7,
        action="Previous Track",
        executed=True,
        application="spotify.exe",
        profile="Spotify",
        timestamp=1.0,
    )
    assert entry.application == "spotify.exe"
    assert entry.profile == "Spotify"


def test_default_clock_used_when_timestamp_omitted():
    ticks = iter([42.0])
    history = ActionHistory(clock=lambda: next(ticks))
    entry = history.record("A", 0.5, "a", True)
    assert entry.timestamp == 42.0
