from benchmarks.benchmark_frame_latency import (
    benchmark_fifo,
    benchmark_latest_frame,
    benchmark_queued_actions,
    benchmark_synchronous_actions,
)


def test_latest_frame_pipeline_reduces_overload_latency():
    fifo = benchmark_fifo(frame_count=80, producer_interval=0.001, processing_time=0.006)
    latest = benchmark_latest_frame(
        frame_count=80,
        producer_interval=0.001,
        processing_time=0.006,
    )

    assert latest.frames_dropped > 0
    assert latest.p95_latency_ms < fifo.p95_latency_ms * 0.5
    assert latest.elapsed_ms < fifo.elapsed_ms * 0.7


def test_action_queue_removes_os_call_latency_from_recognition():
    synchronous = benchmark_synchronous_actions(action_count=20, action_time=0.003)
    queued = benchmark_queued_actions(action_count=20, action_time=0.003)

    assert queued.actions_executed == synchronous.actions_executed == 20
    assert queued.recognition_blocked_ms < synchronous.recognition_blocked_ms * 0.2
