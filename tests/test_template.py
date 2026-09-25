import pytest

from handwave.actions.action_definition import ActionDefinition
from handwave.config.settings_manager import AppSettings
from handwave.config.template import Template


def test_template_inherits_globals_and_overrides_only_its_gestures():
    base = AppSettings()
    template = Template(name="Presentation", gesture_bindings={"Peace Sign": {"type": "key", "value": "right"}}, enabled_gestures={"Peace Sign": True}, gesture_cooldown=0.2)
    effective = template.resolve(base)
    assert effective.gesture_bindings["Peace Sign"] == ActionDefinition(type="key", value="right")
    assert effective.gesture_bindings["Open Palm"] == base.gesture_bindings["Open Palm"]
    assert effective.gesture_cooldown == 0.2


def test_duplicate_is_independent_and_invalid_templates_are_rejected():
    original = Template(name="Gaming", gesture_bindings={"Peace Sign": "play_pause"})
    duplicate = original.duplicate("Gaming copy")
    assert duplicate.template_id != original.template_id
    assert duplicate.gesture_bindings is not original.gesture_bindings
    with pytest.raises(ValueError): Template(name="", gesture_bindings={})
    with pytest.raises(ValueError): Template(name="Bad", gesture_bindings={"Not a gesture": "none"})
