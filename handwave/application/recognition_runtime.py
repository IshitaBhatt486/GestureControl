"""Bridge domain recognition results to asynchronous local actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from handwave.actions.action_mapper import ActionMapper
from handwave.actions.pinch_controller import PinchControlResult, PinchController
from handwave.config.settings_manager import AppSettings
from handwave.gestures.arbitration import select_action_candidate
from handwave.gestures.gesture_filter import FilteredGesture, GestureFilter
from handwave.gestures.swipe_recognizer import SwipeRecognizer, SwipeResult

if TYPE_CHECKING:
    from handwave.gestures.gesture_engine import GestureResult


@dataclass(frozen=True)
class RecognitionDispatch:
    """The action decision derived from one recognition result."""

    filtered: FilteredGesture
    pinch: PinchControlResult
    swipe: SwipeResult
    action: str
    executed: bool


class RecognitionActionRuntime:
    """Own stateful action-policy components for one recognition session.

    The vision layer provides a ``GestureResult`` and receives a domain-level
    decision. ActionMapper and PinchController submit work through the injected
    dispatcher, so OS input remains on the independent action-worker thread.
    """

    def __init__(
        self,
        settings: AppSettings,
        dispatcher: Callable[[str, Callable[[], None]], None] | None = None,
    ) -> None:
        self.action_mapper = ActionMapper(
            cooldown=settings.gesture_cooldown,
            dispatcher=dispatcher,
            gesture_bindings=settings.gesture_bindings,
            enabled_gestures=settings.enabled_gestures,
        )
        self.pinch_controller = PinchController(dispatcher=dispatcher)
        self.gesture_filter = GestureFilter()
        self.swipe_recognizer = SwipeRecognizer()

    def evaluate(self, result: "GestureResult") -> RecognitionDispatch:
        """Filter, arbitrate, and submit at most one non-pinch action request."""
        filtered = self.gesture_filter.update(result.name)
        pinch = self.pinch_controller.update(result.landmarks)
        swipe = self.swipe_recognizer.update(result.landmarks)
        action = select_action_candidate(
            two_hand_gesture=result.two_hand.name,
            pinch_detected=pinch.detected,
            swipe_gesture=swipe.name,
            stable_gesture=filtered.stable_gesture,
        )
        return RecognitionDispatch(
            filtered=filtered,
            pinch=pinch,
            swipe=swipe,
            action=action,
            executed=self.action_mapper.execute(action),
        )

    def apply_settings(self, settings: AppSettings) -> None:
        """Replace action configuration without touching recognition state."""
        self.action_mapper.apply_settings(
            cooldown=settings.gesture_cooldown,
            gesture_bindings=settings.gesture_bindings,
            enabled_gestures=settings.enabled_gestures,
        )
