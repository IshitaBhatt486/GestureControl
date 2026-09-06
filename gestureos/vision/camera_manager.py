"""Asynchronous capture, recognition, and action pipeline."""

from __future__ import annotations

import ctypes
import logging
import os
import threading
import time
from dataclasses import dataclass, replace

import cv2
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from gestureos.actions.action_mapper import ActionMapper
from gestureos.actions.action_queue import ActionQueue, ActionWorker
from gestureos.actions.pinch_controller import PinchController
from gestureos.config.settings_manager import AppSettings
from gestureos.gestures.gesture_engine import GestureEngine
from gestureos.gestures.gesture_filter import GestureFilter
from gestureos.gestures.swipe_recognizer import SwipeRecognizer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BufferedFrame:
    """A captured frame plus passive profiling metadata."""

    frame: object
    captured_at: float
    camera_fps: float


@dataclass(frozen=True)
class PipelineMetrics:
    """One snapshot of capture, recognition, latency, and process health."""

    camera_fps: float = 0.0
    recognition_fps: float = 0.0
    latency_ms: float = 0.0
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    dropped_frames: int = 0
    active_threads: int = 0


class LatestFrameBuffer:
    """Bounded thread-safe buffer that replaces stale, unprocessed frames."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._packet: BufferedFrame | None = None
        self._closed = False
        self.frames_dropped = 0

    def put(
        self,
        frame,
        captured_at: float | None = None,
        camera_fps: float = 0.0,
    ) -> None:
        with self._condition:
            if self._closed:
                return
            if self._packet is not None:
                self.frames_dropped += 1
            self._packet = BufferedFrame(
                frame=frame,
                captured_at=time.perf_counter() if captured_at is None else captured_at,
                camera_fps=camera_fps,
            )
            self._condition.notify()

    def get(self, timeout: float = 0.1):
        packet = self.get_packet(timeout)
        return None if packet is None else packet.frame

    def get_packet(self, timeout: float = 0.1) -> BufferedFrame | None:
        """Return the latest frame and its profiling metadata."""
        with self._condition:
            if self._packet is None and not self._closed:
                self._condition.wait(timeout)
            packet, self._packet = self._packet, None
            return packet

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._packet = None
            self._condition.notify_all()


class DiagnosticsMonitor:
    """Low-overhead process CPU and working-set sampler."""

    def __init__(self, clock=time.perf_counter, cpu_clock=time.process_time) -> None:
        self._clock = clock
        self._cpu_clock = cpu_clock
        self._last_wall = clock()
        self._last_cpu = cpu_clock()
        self.cpu_percent = 0.0
        self.memory_mb = 0.0

    def update(self) -> tuple[float, float]:
        now, cpu_now = self._clock(), self._cpu_clock()
        elapsed = now - self._last_wall
        if elapsed >= 1.0:
            cores = max(os.cpu_count() or 1, 1)
            self.cpu_percent = max(0.0, (cpu_now - self._last_cpu) / elapsed * 100.0 / cores)
            self.memory_mb = self._working_set_bytes() / (1024 * 1024)
            self._last_wall, self._last_cpu = now, cpu_now
        return self.cpu_percent, self.memory_mb

    @staticmethod
    def _working_set_bytes() -> int:
        if os.name != "nt":
            return 0
        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        process = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
            return int(counters.WorkingSetSize)
        return 0


class CameraWorker(QObject):
    """Capture-only worker; processing never blocks webcam reads."""

    opened = pyqtSignal()
    stopped = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, camera_index: int, stop_event: threading.Event, buffer: LatestFrameBuffer | None = None) -> None:
        super().__init__()
        self.camera_index = camera_index
        self.stop_event = stop_event
        self.buffer = buffer or LatestFrameBuffer()
        self.capture: cv2.VideoCapture | None = None
        self._last_capture_time: float | None = None
        self._camera_fps = 0.0

    @pyqtSlot()
    def run(self) -> None:
        try:
            self.capture = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not self.capture.isOpened():
                raise RuntimeError(
                    f"Could not open webcam {self.camera_index}. Check camera permissions and availability."
                )
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.capture.set(cv2.CAP_PROP_FPS, 30)
            self.opened.emit()
            while not self.stop_event.is_set():
                ok, frame = self.capture.read()
                if not ok:
                    raise RuntimeError("The webcam stopped returning frames.")
                captured_at = time.perf_counter()
                if self._last_capture_time is not None:
                    elapsed = captured_at - self._last_capture_time
                    if elapsed > 0:
                        current_fps = 1.0 / elapsed
                        self._camera_fps = (
                            current_fps
                            if self._camera_fps == 0
                            else 0.8 * self._camera_fps + 0.2 * current_fps
                        )
                self._last_capture_time = captured_at
                height, width = frame.shape[:2]
                if width > 640:
                    scale = 640 / width
                    frame = cv2.resize(
                        frame,
                        (640, max(1, int(height * scale))),
                        interpolation=cv2.INTER_AREA,
                    )
                self.buffer.put(frame, captured_at, self._camera_fps)
        except Exception as exc:
            logger.exception("Camera capture failed")
            self.error.emit(str(exc))
        finally:
            if self.capture is not None:
                self.capture.release()
                self.capture = None
            self.buffer.close()
            self.stopped.emit()


class GestureWorker(QObject):
    """Consumes only the latest frame and performs all landmark/action work."""

    frame_ready = pyqtSignal(object)
    stopped = pyqtSignal()
    error = pyqtSignal(str)
    activity = pyqtSignal(str, str, str)
    metrics_ready = pyqtSignal(object)
    confidence_ready = pyqtSignal(float)

    def __init__(
        self,
        buffer: LatestFrameBuffer,
        stop_event: threading.Event,
        settings: AppSettings,
        action_queue: ActionQueue | None = None,
    ) -> None:
        super().__init__()
        self.buffer = buffer
        self.stop_event = stop_event
        self.settings = settings
        self.engine: GestureEngine | None = None
        self.action_queue = action_queue
        dispatcher = action_queue.submit if action_queue is not None else None
        self.action_mapper = ActionMapper(
            cooldown=settings.gesture_cooldown,
            dispatcher=dispatcher,
            gesture_bindings=settings.gesture_bindings,
            enabled_gestures=settings.enabled_gestures,
        )
        self.pinch_controller = PinchController(dispatcher=dispatcher)
        self.gesture_filter = GestureFilter()
        self.swipe_recognizer = SwipeRecognizer()
        self.diagnostics_monitor = DiagnosticsMonitor()
        self._last_recognition_time: float | None = None
        self._recognition_fps = 0.0

    @pyqtSlot()
    def run(self) -> None:
        try:
            self.engine = GestureEngine(
                sensitivity=self.settings.gesture_sensitivity,
                overlay_enabled=self.settings.overlay_enabled,
            )
            while not self.stop_event.is_set():
                started = time.perf_counter()
                packet = self.buffer.get_packet()
                if packet is None:
                    continue
                annotated, gesture = self.engine.process(packet.frame)
                recognized_at = time.perf_counter()
                if self._last_recognition_time is not None:
                    elapsed = recognized_at - self._last_recognition_time
                    if elapsed > 0:
                        current_fps = 1.0 / elapsed
                        self._recognition_fps = (
                            current_fps
                            if self._recognition_fps == 0
                            else 0.8 * self._recognition_fps + 0.2 * current_fps
                        )
                self._last_recognition_time = recognized_at
                filtered = self.gesture_filter.update(gesture.name)
                pinch = self.pinch_controller.update(gesture.landmarks)
                swipe = self.swipe_recognizer.update(gesture.landmarks)
                cpu, memory = self.diagnostics_monitor.update()
                if self.settings.overlay_enabled:
                    cv2.putText(annotated, f"Stable: {filtered.stable_gesture}", (16, 128), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
                    cv2.putText(annotated, f"CPU: {cpu:.1f}%  Memory: {memory:.1f} MB", (16, 384), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
                action = "Unknown" if pinch.detected else swipe.name if swipe.name != "Unknown" else filtered.stable_gesture
                executed = self.action_mapper.execute(action)
                self.activity.emit(gesture.name, filtered.stable_gesture, action if executed else "")
                self.confidence_ready.emit(gesture.confidence)
                self.metrics_ready.emit(PipelineMetrics(
                    camera_fps=packet.camera_fps,
                    recognition_fps=self._recognition_fps,
                    latency_ms=(time.perf_counter() - packet.captured_at) * 1000.0,
                    cpu_percent=cpu,
                    memory_mb=memory,
                    dropped_frames=self.buffer.frames_dropped,
                ))
                self.frame_ready.emit(annotated)
                # Cap processing near 30 FPS; the latest-frame buffer performs adaptive skipping.
                self.stop_event.wait(max(0.0, (1.0 / 30.0) - (time.perf_counter() - started)))
        except Exception as exc:
            logger.exception("Gesture processing failed")
            self.error.emit(str(exc))
        finally:
            if self.engine is not None:
                self.engine.close()
                self.engine = None
            self.stopped.emit()


class CameraManager(QObject):
    """Own asynchronous capture, recognition, and action stages."""

    frame_ready = pyqtSignal(object)
    started = pyqtSignal()
    stopped = pyqtSignal()
    error = pyqtSignal(str)
    recognition_updated = pyqtSignal(str, str, str)
    diagnostics_updated = pyqtSignal(object)
    confidence_updated = pyqtSignal(float)

    def __init__(self, camera_index: int = 0, settings: AppSettings | None = None) -> None:
        super().__init__()
        self.settings = settings or AppSettings(camera_index=camera_index)
        self.camera_index = self.settings.camera_index
        self._capture_thread: QThread | None = None
        self._gesture_thread: QThread | None = None
        self._action_thread: QThread | None = None
        self._capture_worker: CameraWorker | None = None
        self._gesture_worker: GestureWorker | None = None
        self._action_worker: ActionWorker | None = None
        self._stop_event = threading.Event()
        self._buffer: LatestFrameBuffer | None = None
        self._action_queue: ActionQueue | None = None
        self._threads_finished = 0
        self._had_error = False

    @property
    def is_running(self) -> bool:
        return self._capture_thread is not None

    def start_camera(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._had_error = False
        self._threads_finished = 0
        self._buffer = LatestFrameBuffer()
        self._action_queue = ActionQueue()
        self._capture_thread = QThread(self)
        self._gesture_thread = QThread(self)
        self._action_thread = QThread(self)
        self._capture_worker = CameraWorker(self.camera_index, self._stop_event, self._buffer)
        self._gesture_worker = GestureWorker(
            self._buffer,
            self._stop_event,
            self.settings,
            self._action_queue,
        )
        self._action_worker = ActionWorker(self._action_queue)
        self._capture_worker.moveToThread(self._capture_thread)
        self._gesture_worker.moveToThread(self._gesture_thread)
        self._action_worker.moveToThread(self._action_thread)
        self._capture_thread.started.connect(self._capture_worker.run)
        self._gesture_thread.started.connect(self._gesture_worker.run)
        self._action_thread.started.connect(self._action_worker.run)
        self._capture_worker.opened.connect(self.started)
        self._gesture_worker.frame_ready.connect(self.frame_ready)
        self._gesture_worker.activity.connect(self.recognition_updated)
        self._gesture_worker.metrics_ready.connect(self._forward_metrics)
        self._gesture_worker.confidence_ready.connect(self.confidence_updated)
        for worker, thread in (
            (self._capture_worker, self._capture_thread),
            (self._gesture_worker, self._gesture_thread),
            (self._action_worker, self._action_thread),
        ):
            worker.error.connect(self._on_worker_error)
            worker.stopped.connect(worker.deleteLater)
            worker.stopped.connect(thread.quit)
            thread.finished.connect(self._on_thread_finished)
            thread.finished.connect(thread.deleteLater)
        self._gesture_worker.stopped.connect(self._close_action_queue)
        self._capture_thread.start()
        self._gesture_thread.start()
        self._action_thread.start()

    def stop_camera(self) -> None:
        """Request asynchronous shutdown and return immediately to the UI."""
        if not self.is_running:
            return
        self._stop_event.set()
        if self._buffer is not None:
            self._buffer.close()

    def update_settings(self, settings: AppSettings) -> None:
        """Use persisted settings the next time recognition starts."""
        self.settings = settings
        self.camera_index = settings.camera_index

    @pyqtSlot(object)
    def _forward_metrics(self, metrics: PipelineMetrics) -> None:
        threads = sum(
            1
            for thread in (
                self._capture_thread,
                self._gesture_thread,
                self._action_thread,
            )
            if thread is not None and thread.isRunning()
        )
        self.diagnostics_updated.emit(replace(metrics, active_threads=threads))

    @pyqtSlot()
    def _close_action_queue(self) -> None:
        if self._action_queue is not None:
            self._action_queue.close()

    @pyqtSlot()
    def _on_thread_finished(self) -> None:
        self._threads_finished += 1
        if self._threads_finished == 3:
            self._cleanup()
            self.stopped.emit()

    @pyqtSlot(str)
    def _on_worker_error(self, message: str) -> None:
        if not self._had_error:
            self._had_error = True
            self.error.emit(message)
        self._stop_event.set()
        if self._buffer is not None:
            self._buffer.close()

    def _cleanup(self) -> None:
        self._capture_worker = None
        self._gesture_worker = None
        self._action_worker = None
        self._capture_thread = None
        self._gesture_thread = None
        self._action_thread = None
        self._buffer = None
        self._action_queue = None
