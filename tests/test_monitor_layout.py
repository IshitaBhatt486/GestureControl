from handwave.services.monitor_layout import MonitorGeometry, MonitorLayout


def test_primary_target_uses_selected_primary_monitor():
    layout = MonitorLayout((
        MonitorGeometry("DISPLAY1", 0, 0, 1920, 1080, True),
        MonitorGeometry("DISPLAY2", 1920, 0, 2560, 1440),
    ))

    assert layout.target("primary") == MonitorGeometry("DISPLAY1", 0, 0, 1920, 1080, True)


def test_all_monitor_target_preserves_negative_desktop_coordinates():
    layout = MonitorLayout((
        MonitorGeometry("LEFT", -1280, 0, 1280, 1024),
        MonitorGeometry("MAIN", 0, 0, 1920, 1080, True),
    ))

    assert layout.target("all") == MonitorGeometry("all-monitors", -1280, 0, 3200, 1080)
    assert layout.fingerprint == "LEFT:-1280,0,1280,1024;MAIN:0,0,1920,1080"


def test_ultrawide_is_a_normal_primary_target():
    layout = MonitorLayout((MonitorGeometry("ULTRAWIDE", 0, 0, 3440, 1440, True),))

    assert layout.target("primary").width == 3440
    assert layout.target("primary").height == 1440
