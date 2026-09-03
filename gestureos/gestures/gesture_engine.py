"""MediaPipe-backed hand landmark processing."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable

import cv2
import mediapipe as mp

from gestureos.gestures.hand_landmark_data import HandLandmarkData

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GestureResult:
    hands_detected: int = 0
    name: str | None = None
    fps: float = 0.0
    landmarks: HandLandmarkData | None = None
    confidence: float = 0.0


@dataclass(frozen=True)
class GestureDetection:
    name: str = "Unknown"
    confidence: float = 0.0


class GestureEngine:
    """Detects and draws hand landmarks; gesture classification can be extended here."""

    LANDMARK_STYLE = mp.solutions.drawing_utils.DrawingSpec(
        color=(0, 255, 0), thickness=2, circle_radius=3
    )
    CONNECTION_STYLE = mp.solutions.drawing_utils.DrawingSpec(
        color=(0, 255, 0), thickness=2, circle_radius=2
    )
    GESTURE_PATTERNS = {
        "Open Palm": {finger: "extended" for finger in ("thumb", "index", "middle", "ring", "pinky")},
        "Fist": {finger: "folded" for finger in ("thumb", "index", "middle", "ring", "pinky")},
        "Thumbs Up": {
            "thumb": "extended", "index": "folded", "middle": "folded", "ring": "folded", "pinky": "folded"
        },
        "Thumbs Down": {
            "thumb": "extended", "index": "folded", "middle": "folded", "ring": "folded", "pinky": "folded"
        },
        "Peace Sign": {
            "thumb": "folded", "index": "extended", "middle": "extended", "ring": "folded", "pinky": "folded"
        },
        "Pointing": {
            "thumb": "folded", "index": "extended", "middle": "folded", "ring": "folded", "pinky": "folded"
        },
    }

    def __init__(
        self,
        clock: Callable[[], float] = time.perf_counter,
        sensitivity: float = 0.6,
        overlay_enabled: bool = True,
    ) -> None:
        self._hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=sensitivity,
            min_tracking_confidence=sensitivity,
        )
        self._drawing = mp.solutions.drawing_utils
        self._connections = mp.solutions.hands.HAND_CONNECTIONS
        self._clock = clock
        self._last_frame_time: float | None = None
        self._fps = 0.0
        self.overlay_enabled = overlay_enabled

    def process(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        result = self._hands.process(rgb)
        rgb.flags.writeable = True

        detected_hands = result.multi_hand_landmarks or []
        count = len(detected_hands)
        landmark_data = None
        for landmarks in detected_hands:
            landmark_data = HandLandmarkData.from_mediapipe(landmarks)
            if self.overlay_enabled:
                self._drawing.draw_landmarks(
                    frame,
                    landmarks,
                    self._connections,
                    self.LANDMARK_STYLE,
                    self.CONNECTION_STYLE,
                )

        now = self._clock()
        if self._last_frame_time is not None:
            elapsed = now - self._last_frame_time
            if elapsed > 0:
                current_fps = 1.0 / elapsed
                # Smooth the display while keeping it responsive to performance drops.
                self._fps = current_fps if self._fps == 0 else (0.8 * self._fps + 0.2 * current_fps)
        self._last_frame_time = now

        status = "Hand detected" if count else "No hand detected"
        gesture = self.detect_gesture(landmark_data)
        if self.overlay_enabled:
            self._draw_overlay(frame, status, gesture, landmark_data)
        return frame, GestureResult(
            hands_detected=count,
            name=gesture.name,
            fps=self._fps,
            landmarks=landmark_data,
            confidence=gesture.confidence,
        )

    def _draw_overlay(self, frame, status, gesture, landmark_data) -> None:
        cv2.putText(
            frame,
            status,
            (16, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            f"FPS: {self._fps:.1f}",
            (16, 64),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            f"Raw: {gesture.name} ({gesture.confidence:.0%})",
            (16, 96),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        if landmark_data is not None:
            for row, (finger, state) in enumerate(landmark_data.get_finger_states().items(), start=5):
                cv2.putText(
                    frame,
                    f"{finger.title()}: {state}",
                    (16, 32 * row),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )
            pinch_distance = landmark_data.get_pinch_distance()
            pinch_detected = pinch_distance <= 0.08
            cv2.putText(
                frame,
                "Pinch detected" if pinch_detected else "Pinch not detected",
                (16, 320),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                f"Pinch distance: {pinch_distance:.3f}",
                (16, 352),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

    def detect_gesture(self, landmarks: HandLandmarkData | None) -> GestureDetection:
        """Recognize a gesture from a single normalized landmark snapshot."""
        if landmarks is None:
            return GestureDetection()

        states = landmarks.get_finger_states()
        scores = landmarks.get_finger_extension_scores()
        for name, pattern in self.GESTURE_PATTERNS.items():
            if states != pattern:
                continue
            if name == "Thumbs Up" and not self._thumb_points_up(landmarks):
                continue
            if name == "Thumbs Down" and not self._thumb_points_down(landmarks):
                continue
            matches = [score if pattern[finger] == "extended" else 1.0 - score for finger, score in scores.items()]
            return GestureDetection(name, sum(matches) / len(matches))
        return GestureDetection()

    @staticmethod
    def _thumb_points_up(landmarks: HandLandmarkData) -> bool:
        points = landmarks.get_landmarks()
        wrist, thumb_mcp, thumb_tip = points[0], points[2], points[4]
        vertical = thumb_mcp.y - thumb_tip.y
        horizontal = abs(thumb_tip.x - thumb_mcp.x)
        return thumb_tip.y < wrist.y and vertical > horizontal

    @staticmethod
    def _thumb_points_down(landmarks: HandLandmarkData) -> bool:
        points = landmarks.get_landmarks()
        thumb_mcp, thumb_tip = points[2], points[4]
        vertical = thumb_tip.y - thumb_mcp.y
        horizontal = abs(thumb_tip.x - thumb_mcp.x)
        return vertical > horizontal

    def close(self) -> None:
        self._hands.close()
