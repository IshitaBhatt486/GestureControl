from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QLabel

from handwave.ui.fingerprint_indicator import FingerprintIndicator


def _indicator(qtbot, width=400, height=300):
    preview = QLabel()
    preview.resize(width, height)
    preview.show()
    qtbot.addWidget(preview)
    indicator = FingerprintIndicator(preview, fade_duration_ms=50)
    indicator.sync_geometry()
    return preview, indicator


def test_fingertip_movement_is_smoothed_in_preview_coordinates(qtbot):
    _, indicator = _indicator(qtbot)
    indicator.update_fingertips([(0.25, 0.50)])
    assert indicator.contact_positions == (QPointF(100.0, 150.0),)

    indicator.update_fingertips([(0.75, 0.50)])
    assert indicator.contact_positions[0].x() == 170.0  # 35% smoothing, not a jump to 300.


def test_disappearance_fades_and_reappearance_restores_contact(qtbot):
    _, indicator = _indicator(qtbot)
    indicator.update_fingertips([(0.5, 0.5)])
    indicator.update_fingertips([])
    # QTimer ticks are not guaranteed to land exactly every 16 ms under CI
    # load. Wait for the observable fade completion instead of assuming five
    # ticks have occurred within an 80 ms wall-clock window.
    qtbot.waitUntil(lambda: indicator.contact_positions == (), timeout=250)
    assert indicator.contact_positions == ()

    indicator.update_fingertips([(0.5, 0.5)])
    assert indicator.contact_opacities == (0.9,)


def test_jitter_and_high_frequency_updates_stay_bounded(qtbot):
    _, indicator = _indicator(qtbot)
    for index in range(120):
        indicator.update_fingertips([(0.5 + (0.003 if index % 2 else -0.003), 0.5)])
    assert len(indicator.contact_positions) == 1
    assert abs(indicator.contact_positions[0].x() - 200.0) < 4.0


def test_normalized_mapping_handles_camera_resolution_and_high_dpi_logical_scaling(qtbot):
    _, indicator = _indicator(qtbot, width=640, height=480)
    assert indicator.map_normalized_point(0.5, 0.25) == QPointF(320.0, 120.0)

    indicator.resize(320, 240)  # Qt maps in logical pixels; device scale does not alter this contract.
    assert indicator.map_normalized_point(0.5, 0.25) == QPointF(160.0, 60.0)


def test_multiple_hands_and_ui_resizing_update_each_contact(qtbot):
    preview, indicator = _indicator(qtbot)
    indicator.update_fingertips([(0.2, 0.3), (0.8, 0.7)])
    assert indicator.contact_positions == (QPointF(80.0, 90.0), QPointF(320.0, 210.0))

    preview.resize(600, 200)
    indicator.sync_geometry()
    indicator.update_fingertips([(0.2, 0.3), (0.8, 0.7)])
    assert indicator.width() == 600
    assert indicator.height() == 200
