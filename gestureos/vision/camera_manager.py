"""Two-thread webcam capture and gesture-processing pipeline."""

from __future__ import annotations

import ctypes
import logging
import os
import threading
import time

import cv2
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from gestureos.actions.action_mapper import ActionMapper
from gestureos.actions.pinch_controller import PinchController
from gestureos.config.settings_manager import AppSettings
from gestureos.gestures.gesture_engine import GestureEngine
from gestureos.gestures.gesture_filter import GestureFilter
from gestureos.gestures.swipe_recognizer import SwipeRecognizer

logger = logging.getLogger(__name__)


class LatestFrameBuffer:
    """Bounded thread-safe buffer that replaces stale, unprocessed frames."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._frame = None
        self._closed = False
        self.frames_dropped = 0

    def put(self, frame) -> None:
        with self._condition:
            if self._closed:
                return
            if self._frame is not None:
                self.frames_dropped += 1
            self._frame = frame
            self._condition.notify()

    def get(self, timeout: float = 0.1):
        with self._condition:
            if self._frame is None and not self._closed:
                self._condition.wait(timeout)
            frame, self._frame = self._frame, None
            return frame

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._frame = None
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
                height, width = frame.shape[:2]
                if width > 640:
                    scale = 640 / width
                    frame = cv2.resize(
                        frame,
                        (640, max(1, int(height * scale))),
                        interpolation=cv2.INTER_AREA,
                    )
                self.buffer.put(frame)
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

    def __init__(self, buffer: LatestFrameBuffer, stop_event: threading.Event, settings: AppSettings) -> None:
        super().__init__()
        self.buffer = buffer
        self.stop_event = stop_event
        self.settings = settings
        self.engine: GestureEngine | None = None
        self.action_mapper = ActionMapper(cooldown=settings.gesture_cooldown)
        self.pinch_controller = PinchController()
        self.gesture_filter = GestureFilter()
        self.swipe_recognizer = SwipeRecognizer()
        self.diagnostics = DiagnosticsMonitor()

    @pyqtSlot()
    def run(self) -> None:
        try:
            self.engine = GestureEngine(
                sensitivity=self.settings.gesture_sensitivity,
                overlay_enabled=self.settings.overlay_enabled,
            )
            while not self.stop_event.is_set():
                started = time.perf_counter()
                frame = self.buffer.get()
                if frame is None:
                    continue
                annotated, gesture = self.engine.process(frame)
                filtered = self.gesture_filter.update(gesture.name)
                pinch = self.pinch_controller.update(gesture.landmarks)
                swipe = self.swipe_recognizer.update(gesture.landmarks)
                if self.settings.overlay_enabled:
                    cpu, memory = self.diagnostics.update()
                    cv2.putText(annotated, f"Stable: {filtered.stable_gesture}", (16, 128), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
                    cv2.putText(annotated, f"CPU: {cpu:.1f}%  Memory: {memory:.1f} MB", (16, 384), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
                action = "Unknown" if pinch.detected else swipe.name if swipe.name != "Unknown" else filtered.stable_gesture
                executed = self.action_mapper.execute(action)
                self.activity.emit(gesture.name, filtered.stable_gesture, action if executed else "")
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
    """Own separate capture and gesture threads with a bounded handoff."""

    frame_ready = pyqtSignal(object)
    started = pyqtSignal()
    stopped = pyqtSignal()
    error = pyqtSignal(str)
    recognition_updated = pyqtSignal(str, str, str)

    def __init__(self, camera_index: int = 0, settings: AppSettings | None = None) -> None:
        super().__init__()
        self.settings = settings or AppSettings(camera_index=camera_index)
        self.camera_index = self.settings.camera_index
        self._capture_thread: QThread | None = None
        self._gesture_thread: QThread | None = None
        self._capture_worker: CameraWorker | None = None
        self._gesture_worker: GestureWorker | None = None
        self._stop_event = threading.Event()
        self._buffer: LatestFrameBuffer | None = None
        self._workers_stopped = 0
        self._had_error = False

    @property
    def is_running(self) -> bool:
        return self._capture_thread is not None and self._capture_thread.isRunning()

    def start_camera(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._had_error = False
        self._workers_stopped = 0
        self._buffer = LatestFrameBuffer()
        self._capture_thread, self._gesture_thread = QThread(self), QThread(self)
        self._capture_worker = CameraWorker(self.camera_index, self._stop_event, self._buffer)
        self._gesture_worker = GestureWorker(self._buffer, self._stop_event, self.settings)
        self._capture_worker.moveToThread(self._capture_thread)
        self._gesture_worker.moveToThread(self._gesture_thread)
        self._capture_thread.started.connect(self._capture_worker.run)
        self._gesture_thread.started.connect(self._gesture_worker.run)
        self._capture_worker.opened.connect(self.started)
        self._gesture_worker.frame_ready.connect(self.frame_ready)
        self._gesture_worker.activity.connect(self.recognition_updated)
        for worker, thread in ((self._capture_worker, self._capture_thread), (self._gesture_worker, self._gesture_thread)):
            worker.error.connect(self._on_worker_error)
            worker.stopped.connect(self._on_worker_stopped)
            worker.stopped.connect(thread.quit)
        self._capture_thread.start()
        self._gesture_thread.start()

    def stop_camera(self) -> None:
        self._stop_event.set()
        if self._buffer is not None:
            self._buffer.close()
        for thread in (self._capture_thread, self._gesture_thread):
            if thread is not None and thread.isRunning():
                thread.quit()
                if not thread.wait(3000):
                    logger.warning("Worker thread did not stop within 3 seconds")
        self._cleanup()

    @pyqtSlot()
    def _on_worker_stopped(self) -> None:
        self._workers_stopped += 1
        if self._workers_stopped == 2 and not self._had_error:
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
        self._capture_thread = None
        self._gesture_thread = None
        self._buffer = None
