from PyQt6.QtCore import Qt
import pytest

from handwave.ui.cursor_assist_overlay import CursorAssistOverlay, CursorAssistState


def test_glass_overlay_is_frameless_topmost_tool_and_click_through(qtbot):
    overlay = CursorAssistOverlay()
    qtbot.addWidget(overlay)
    flags = overlay.windowFlags()

    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert flags & Qt.WindowType.Tool
    assert flags & Qt.WindowType.WindowTransparentForInput
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert overlay.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert overlay.width() == overlay.height() == 22


def test_overlay_coalesces_positions_at_frame_rate_and_hides_cleanly(qtbot):
    overlay = CursorAssistOverlay(size=18, opacity=.5)
    qtbot.addWidget(overlay)
    overlay.update_position(120, 240)
    overlay.update_position(140, 260)
    qtbot.wait(25)

    assert overlay.isVisible()
    assert overlay.pos().x() == 131  # 140 minus half the 18px diameter
    assert overlay.pos().y() == 251
    assert overlay.windowOpacity() == pytest.approx(.5, abs=.01)
    overlay.hide_overlay()
    assert not overlay.isVisible()
    assert not overlay._frame_timer.isActive()


def test_overlay_exposes_all_visual_states_and_only_animates_gesture_feedback(qtbot):
    overlay = CursorAssistOverlay()
    qtbot.addWidget(overlay)
    overlay.update_position(100, 100)

    for state in (
        CursorAssistState.IDLE,
        CursorAssistState.TRACKING,
        CursorAssistState.CLICK_READY,
        CursorAssistState.CALIBRATION,
    ):
        overlay.set_state(state)
        assert overlay.state is state

    overlay.set_state(CursorAssistState.GESTURE_DETECTED)
    initial_phase = overlay._pulse_phase
    qtbot.wait(25)
    assert overlay._pulse_phase != initial_phase


def test_overlay_reports_lightweight_local_performance_metrics(qtbot):
    overlay = CursorAssistOverlay(size=24)
    qtbot.addWidget(overlay)
    overlay.update_position(100, 100)
    overlay.update_position(101, 101)

    metrics = overlay.metrics()
    assert metrics.framebuffer_kb == pytest.approx(2.25)
    assert metrics.paint_cpu_percent >= 0.0
    assert metrics.render_fps >= 0.0
