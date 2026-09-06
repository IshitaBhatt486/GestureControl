"""Compare overloaded FIFO buffering with GestureOS's latest-frame handoff."""

from __future__ import annotations

import json
import queue
import statistics
import threading
import time
from dataclasses import asdict, dataclass

from gestureos.actions.action_queue import ActionQueue, ActionWorker
from gestureos.vision.camera_manager import LatestFrameBuffer


@dataclass(frozen=True)
class BenchmarkResult:
    strategy: str
    frames_produced: int
    frames_processed: int
    frames_dropped: int
    median_latency_ms: float
    p95_latency_ms: float
    elapsed_ms: float


@dataclass(frozen=True)
class ActionBenchmarkResult:
    strategy: str
    actions_executed: int
    recognition_blocked_ms: float
    total_elapsed_ms: float


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def _result(
    strategy: str,
    frame_count: int,
    processed: int,
    dropped: int,
    latencies: list[float],
    elapsed: float,
) -> BenchmarkResult:
    return BenchmarkResult(
        strategy=strategy,
        frames_produced=frame_count,
        frames_processed=processed,
        frames_dropped=dropped,
        median_latency_ms=statistics.median(latencies) * 1000.0,
        p95_latency_ms=_percentile(latencies, 0.95) * 1000.0,
        elapsed_ms=elapsed * 1000.0,
    )


def benchmark_fifo(
    frame_count: int = 120,
    producer_interval: float = 0.002,
    processing_time: float = 0.01,
) -> BenchmarkResult:
    """Measure the latency of retaining every frame under overload."""
    frames: queue.Queue[tuple[int, float] | None] = queue.Queue()
    latencies: list[float] = []

    def produce() -> None:
        for index in range(frame_count):
            frames.put((index, time.perf_counter()))
            time.sleep(producer_interval)
        frames.put(None)

    def consume() -> None:
        while True:
            item = frames.get()
            if item is None:
                return
            _, captured_at = item
            time.sleep(processing_time)
            latencies.append(time.perf_counter() - captured_at)

    started = time.perf_counter()
    producer = threading.Thread(target=produce)
    consumer = threading.Thread(target=consume)
    producer.start()
    consumer.start()
    producer.join()
    consumer.join()
    return _result(
        "fifo",
        frame_count,
        len(latencies),
        0,
        latencies,
        time.perf_counter() - started,
    )


def benchmark_latest_frame(
    frame_count: int = 120,
    producer_interval: float = 0.002,
    processing_time: float = 0.01,
) -> BenchmarkResult:
    """Measure latency when stale frames are replaced instead of queued."""
    frames = LatestFrameBuffer()
    producer_done = threading.Event()
    latencies: list[float] = []

    def produce() -> None:
        for index in range(frame_count):
            frames.put(index, captured_at=time.perf_counter())
            time.sleep(producer_interval)
        producer_done.set()

    def consume() -> None:
        while True:
            packet = frames.get_packet(timeout=0.002)
            if packet is None:
                if producer_done.is_set():
                    return
                continue
            time.sleep(processing_time)
            latencies.append(time.perf_counter() - packet.captured_at)

    started = time.perf_counter()
    producer = threading.Thread(target=produce)
    consumer = threading.Thread(target=consume)
    producer.start()
    consumer.start()
    producer.join()
    consumer.join()
    return _result(
        "latest-frame",
        frame_count,
        len(latencies),
        frames.frames_dropped,
        latencies,
        time.perf_counter() - started,
    )


def benchmark_synchronous_actions(
    action_count: int = 40,
    action_time: float = 0.005,
) -> ActionBenchmarkResult:
    """Baseline where recognition performs each simulated OS call itself."""
    executed = 0
    started = time.perf_counter()
    for _ in range(action_count):
        time.sleep(action_time)
        executed += 1
    elapsed = time.perf_counter() - started
    return ActionBenchmarkResult("synchronous", executed, elapsed * 1000.0, elapsed * 1000.0)


def benchmark_queued_actions(
    action_count: int = 40,
    action_time: float = 0.005,
) -> ActionBenchmarkResult:
    """Measure recognition handoff time while a dedicated worker executes actions."""
    actions = ActionQueue()
    worker = ActionWorker(actions)
    executed = 0
    executed_lock = threading.Lock()

    def perform() -> None:
        nonlocal executed
        time.sleep(action_time)
        with executed_lock:
            executed += 1

    total_started = time.perf_counter()
    action_thread = threading.Thread(target=worker.run)
    action_thread.start()
    recognition_started = time.perf_counter()
    for index in range(action_count):
        actions.submit(f"action-{index}", perform)
    recognition_elapsed = time.perf_counter() - recognition_started
    actions.close()
    action_thread.join()
    total_elapsed = time.perf_counter() - total_started
    return ActionBenchmarkResult(
        "queued",
        executed,
        recognition_elapsed * 1000.0,
        total_elapsed * 1000.0,
    )


def run_benchmark() -> dict[str, BenchmarkResult | ActionBenchmarkResult]:
    return {
        "fifo": benchmark_fifo(),
        "latest_frame": benchmark_latest_frame(),
        "synchronous_actions": benchmark_synchronous_actions(),
        "queued_actions": benchmark_queued_actions(),
    }


if __name__ == "__main__":
    print(json.dumps({name: asdict(result) for name, result in run_benchmark().items()}, indent=2))
