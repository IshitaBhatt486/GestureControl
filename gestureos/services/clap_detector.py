"""Microphone-backed double-clap detector."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

try:
    import sounddevice as sd
except ImportError:  # Provides a clear runtime error before dependencies are installed.
    sd = None

logger = logging.getLogger(__name__)


class ClapDetector(QObject):
    """Detect two sharp audio peaks between 200 ms and 1000 ms apart."""

    double_clap = pyqtSignal()
    error = pyqtSignal(str)

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

    @property
    def is_listening(self) -> bool:
        return self._stream is not None

    @pyqtSlot()
    def start(self) -> None:
        """Start microphone capture; safe to call more than once."""
        if self._stream is not None:
            return
        if sd is None:
            message = "Microphone support requires the 'sounddevice' package"
            logger.error(message)
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
            logger.info("Clap detector started")
        except Exception as exc:
            self._stream = None
            logger.exception("Unable to start clap detector")
            self.error.emit(str(exc))

    @pyqtSlot()
    def stop(self) -> None:
        """Stop and release microphone capture."""
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                logger.exception("Unable to cleanly close microphone stream")

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
        threshold = max(self.min_peak, self._noise_floor * self.noise_multiplier)

        # Speech and steady noise have a much lower peak-to-RMS ratio than a clap.
        crest_factor = peak / max(rms, 1e-6)
        sharp_peak = peak >= threshold and crest_factor >= 2.5
        if not sharp_peak:
            self._noise_floor = 0.98 * self._noise_floor + 0.02 * rms
            if self._first_clap_time is not None and now - self._first_clap_time > 1.0:
                self._first_clap_time = None
            return False

        if now - self._last_peak_time < 0.1:
            return False
        self._last_peak_time = now

        if self._first_clap_time is None or now - self._first_clap_time > 1.0:
            self._first_clap_time = now
            return False

        interval = now - self._first_clap_time
        if interval < 0.2:
            return False

        self._first_clap_time = None
        logger.info("Double clap detected (%.0f ms apart)", interval * 1000)
        self.double_clap.emit()
        return True
