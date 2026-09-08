"""Microphone-backed double-clap detector.

Privacy: only scalar peak/RMS levels are ever computed from each audio block.
No audio samples are stored, buffered beyond the current block, or written to
disk at any point.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

try:
    import sounddevice as sd
except ImportError:  # Provides a clear runtime error before dependencies are installed.
    sd = None

logger = logging.getLogger(__name__)


class ClapState(Enum):
    """Explicit double-clap state machine (see ``ClapDetector.state``)."""

    IDLE = auto()
    WAITING_FOR_SECOND_CLAP = auto()


@dataclass(frozen=True)
class MicrophoneStatus:
    """A diagnostics snapshot suitable for a settings/calibration UI."""

    available: bool
    input_level: float
    noise_floor: float
    threshold: float
    error: str | None = None


@dataclass(frozen=True)
class CalibrationResult:
    ambient_rms: float
    threshold: float
    sample_count: int


class ClapDetector(QObject):
    """Detect two sharp audio peaks between 200 ms and 1000 ms apart.

    State machine: ``IDLE`` -> (sharp peak) -> ``WAITING_FOR_SECOND_CLAP`` ->
    either a second sharp peak inside the timing window confirms the double
    clap and returns to ``IDLE``, or the window expires and it returns to
    ``IDLE`` without firing.
    """

    double_clap = pyqtSignal()
    error = pyqtSignal(str)
    started = pyqtSignal()
    stopped = pyqtSignal()

    MIN_CLAP_SEPARATION = 0.2
    MAX_CLAP_SEPARATION = 1.0
    REFRACTORY_INTERVAL = 0.1

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        min_peak: float = 0.25,
        noise_multiplier: float = 6.0,
    ) -> None:
        super().__init__()
        self._clock = clock
        self.min_peak = min_peak
        self.noise_multiplier = noise_multiplier
        self._noise_floor = 0.02
        self._first_clap_time: float | None = None
        self._last_peak_time = float("-inf")
        self._stream = None
        self._last_input_level = 0.0
        self._last_error: str | None = None
        self._calibration_samples: list[float] = []
        self._calibrating = False

    @property
    def is_listening(self) -> bool:
        return self._stream is not None

    @property
    def state(self) -> ClapState:
        return ClapState.IDLE if self._first_clap_time is None else ClapState.WAITING_FOR_SECOND_CLAP

    @property
    def threshold(self) -> float:
        return max(self.min_peak, self._noise_floor * self.noise_multiplier)

    def status(self) -> MicrophoneStatus:
        """A point-in-time diagnostics snapshot for a "Test microphone" UI."""
        return MicrophoneStatus(
            available=self.is_listening,
            input_level=self._last_input_level,
            noise_floor=self._noise_floor,
            threshold=self.threshold,
            error=self._last_error,
        )

    def reset(self) -> None:
        """Return to ``IDLE`` without touching the microphone stream or calibration."""
        self._first_clap_time = None
        self._last_peak_time = float("-inf")

    @pyqtSlot()
    def start(self) -> None:
        """Start microphone capture; safe to call more than once."""
        if self._stream is not None:
            return
        if sd is None:
            message = "Microphone support requires the 'sounddevice' package"
            logger.error(message)
            self._last_error = message
            self.error.emit(message)
            return
        try:
            self._stream = sd.InputStream(
                channels=1,
                samplerate=44_100,
                blocksize=1024,
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()
            self._last_error = None
            logger.info("Clap detector started")
            self.started.emit()
        except Exception as exc:
            self._stream = None
            self._last_error = str(exc)
            logger.exception("Unable to start clap detector")
            self.error.emit(str(exc))

    def retry(self) -> None:
        """Re-attempt device initialization after a failure or disconnection."""
        self.stop()
        self.start()

    @pyqtSlot()
    def stop(self) -> None:
        """Stop and release microphone capture."""
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
                self.stopped.emit()
            except Exception:
                logger.exception("Unable to cleanly close microphone stream")

    # -- calibration ---------------------------------------------------------

    def begin_calibration(self) -> None:
        """Start collecting ambient-noise samples; call while the room is at rest."""
        self._calibrating = True
        self._calibration_samples = []

    def feed_calibration_sample(self, samples) -> None:
        """Record one ambient audio block. Never triggers a clap while calibrating."""
        audio = np.asarray(samples, dtype=np.float32).reshape(-1)
        if audio.size == 0:
            return
        rms = float(np.sqrt(np.mean(audio * audio)))
        self._calibration_samples.append(rms)

    def finish_calibration(self, margin: float = 6.0) -> CalibrationResult:
        """Derive a baseline noise floor and threshold from the recorded samples."""
        self._calibrating = False
        if not self._calibration_samples:
            raise ValueError("No calibration samples were recorded")
        ambient = sum(self._calibration_samples) / len(self._calibration_samples)
        self._noise_floor = ambient
        threshold = max(self.min_peak, ambient * margin)
        return CalibrationResult(ambient, threshold, len(self._calibration_samples))

    # -- detection -------------------------------------------------------

    def _audio_callback(self, samples, frames, timing, status) -> None:
        if status:
            logger.debug("Microphone status: %s", status)
        self.process_audio(samples)

    def process_audio(self, samples, timestamp: float | None = None) -> bool:
        """Process one normalized float audio block; returns true on a double clap."""
        audio = np.asarray(samples, dtype=np.float32).reshape(-1)
        if audio.size == 0:
            return False
        now = self._clock() if timestamp is None else timestamp
        absolute = np.abs(audio)
        peak = float(np.max(absolute))
        rms = float(np.sqrt(np.mean(audio * audio)))
        self._last_input_level = peak

        if self._calibrating:
            self._calibration_samples.append(rms)
            return False

        # Speech and steady noise have a much lower peak-to-RMS ratio than a clap.
        crest_factor = peak / max(rms, 1e-6)
        sharp_peak = peak >= self.threshold and crest_factor >= 2.5
        if not sharp_peak:
            self._noise_floor = 0.98 * self._noise_floor + 0.02 * rms
            if self._first_clap_time is not None and now - self._first_clap_time > self.MAX_CLAP_SEPARATION:
                self._first_clap_time = None
            return False

        if now - self._last_peak_time < self.REFRACTORY_INTERVAL:
            return False
        self._last_peak_time = now

        if self._first_clap_time is None or now - self._first_clap_time > self.MAX_CLAP_SEPARATION:
            self._first_clap_time = now
            return False

        interval = now - self._first_clap_time
        if interval < self.MIN_CLAP_SEPARATION:
            return False

        self._first_clap_time = None
        logger.info("Double clap detected (%.0f ms apart)", interval * 1000)
        self.double_clap.emit()
        return True
