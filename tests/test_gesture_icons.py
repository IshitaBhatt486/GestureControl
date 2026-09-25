from handwave.ui.gesture_icons import GESTURE_GLYPHS, gesture_icon, gesture_text


def test_every_configured_gesture_has_a_local_icon_and_textual_label(qtbot):
    from handwave.config.gesture_config import GESTURES
    for gesture in GESTURES:
        assert gesture in GESTURE_GLYPHS
        assert gesture in gesture_text(gesture)
        assert not gesture_icon(gesture, "dark").isNull()
        assert not gesture_icon(gesture, "light").isNull()


def test_missing_gesture_uses_accessible_text_and_safe_local_fallback(qtbot):
    assert "My custom gesture" in gesture_text("My custom gesture")
    assert not gesture_icon("My custom gesture").isNull()
