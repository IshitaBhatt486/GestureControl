import pytest

from handwave.actions.action_definition import ActionDefinition


def test_media_action_round_trips_through_dict():
    action = ActionDefinition(type="media", value="play_pause")
    data = action.to_dict()
    assert ActionDefinition.from_data(data) == action


def test_legacy_string_binding_still_loads_as_media_action():
    assert ActionDefinition.from_data("volume_up") == ActionDefinition(type="media", value="volume_up")
    assert ActionDefinition.from_data("none") == ActionDefinition()


@pytest.mark.parametrize(
    "type_,value",
    [
        ("key", "Space"),
        ("key", "F5"),
        ("hotkey", "Ctrl+C"),
        ("hotkey", "Ctrl+Shift+S"),
        ("mouse", "left_click"),
        ("mouse", "scroll_up"),
        ("text", "hello world"),
    ],
)
def test_supported_action_types_normalize_and_round_trip(type_, value):
    action = ActionDefinition(type=type_, value=value)
    assert ActionDefinition.from_data(action.to_dict()) == action


def test_command_action_requires_confirmation_or_hold():
    with pytest.raises(ValueError):
        ActionDefinition(type="command", value="notepad.exe")
    action = ActionDefinition(type="command", value="notepad.exe", requires_confirmation=True)
    assert action.value == ("notepad.exe",)
    assert action.effective_hold_duration == ActionDefinition.CONFIRMATION_HOLD


def test_dangerous_hotkey_requires_confirmation_or_hold():
    with pytest.raises(ValueError):
        ActionDefinition(type="hotkey", value="alt+f4")
    action = ActionDefinition(type="hotkey", value="alt+f4", hold_duration=2.0)
    assert action.hold_duration == 2.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"type": "bogus"},
        {"type": "media", "value": "not_a_media_action"},
        {"type": "mouse", "value": "not_a_mouse_action"},
        {"type": "key", "value": ""},
        {"type": "key", "value": "a+b"},
        {"type": "hotkey", "value": "ctrl"},
        {"type": "hotkey", "value": "a+b"},
        {"type": "hotkey", "value": "ctrl+ctrl"},
        {"type": "text", "value": ""},
        {"type": "text", "value": "x" * 1001},
        {"type": "command", "value": "", "requires_confirmation": True},
        {"type": "command", "value": "  ", "requires_confirmation": True},
        {"hold_duration": -1},
        {"hold_duration": 11},
        {"cooldown": -1},
        {"cooldown": 61},
        {"requires_confirmation": "yes"},
    ],
)
def test_invalid_configurations_are_rejected(kwargs):
    with pytest.raises(ValueError):
        ActionDefinition(**kwargs)


def test_from_data_rejects_unknown_fields_and_bad_shapes():
    with pytest.raises(ValueError):
        ActionDefinition.from_data({"type": "media", "value": "play_pause", "bogus": True})
    with pytest.raises(ValueError):
        ActionDefinition.from_data(42)


def test_command_value_parses_argv_safely():
    action = ActionDefinition(
        type="command", value='notepad.exe "C:\\My Docs\\a.txt"', requires_confirmation=True
    )
    assert action.value == ("notepad.exe", "C:\\My Docs\\a.txt")


def test_describe_is_human_readable_for_every_type():
    assert ActionDefinition().describe() == "No action"
    assert ActionDefinition(type="media", value="mute").describe() == "Mute"
    assert ActionDefinition(type="mouse", value="left_click").describe() == "Left click"
    assert ActionDefinition(type="key", value="F5").describe() == "f5"
    assert ActionDefinition(type="hotkey", value="Ctrl+C").describe() == "ctrl+c"
    assert (
        ActionDefinition(type="command", value="notepad.exe", requires_confirmation=True).describe()
        == "Launch notepad.exe"
    )
