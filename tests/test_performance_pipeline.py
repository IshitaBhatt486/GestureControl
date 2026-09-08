import tracemalloc

import numpy as np

from handwave.vision.camera_manager import DiagnosticsMonitor, LatestFrameBuffer


def test_latest_frame_buffer_skips_stale_frames_and_stays_bounded():
    buffer = LatestFrameBuffer()
    frames = [np.full((8, 8, 3), value, dtype=np.uint8) for value in range(10)]
    for frame in frames:
        buffer.put(frame)

    latest = buffer.get()
    assert np.array_equal(latest, frames[-1])
    assert buffer.frames_dropped == 9
    assert buffer.get(timeout=0) is None


def test_accelerated_30_minute_buffer_soak_has_no_growth():
    """Simulate 30 FPS for 30 minutes without wall-clock waiting."""
    buffer = LatestFrameBuffer()
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    tracemalloc.start()
    before = tracemalloc.take_snapshot()
    for index in range(30 * 60 * 30):
        buffer.put(frame)
        if index % 3 == 0:
            buffer.get(timeout=0)
    buffer.get(timeout=0)
    after = tracemalloc.take_snapshot()
    growth = sum(stat.size_diff for stat in after.compare_to(before, "filename"))
    tracemalloc.stop()

    assert growth < 1_000_000
    assert buffer._packet is None


def test_buffer_preserves_capture_profiling_metadata():
    buffer = LatestFrameBuffer()
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    buffer.put(frame, captured_at=12.5, camera_fps=29.7)

    packet = buffer.get_packet(timeout=0)

    assert packet is not None
    assert packet.frame is frame
    assert packet.captured_at == 12.5
    assert packet.camera_fps == 29.7


def test_diagnostics_reports_cpu_and_memory_estimates():
    wall = iter((0.0, 2.0))
    cpu = iter((0.0, 0.2))
    monitor = DiagnosticsMonitor(clock=wall.__next__, cpu_clock=cpu.__next__)
    cpu_percent, memory_mb = monitor.update()
    assert cpu_percent >= 0
    assert memory_mb >= 0
