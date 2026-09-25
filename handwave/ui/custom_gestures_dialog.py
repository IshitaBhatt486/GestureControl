"""Local, privacy-safe custom static-gesture recording workflow."""

from __future__ import annotations

import time

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget, QMessageBox, QProgressBar, QPushButton, QVBoxLayout

from handwave.gestures.custom_gesture import CustomGestureDefinition, CustomGestureMatcher, GestureFrame, GestureSample, compute_representative_gesture, detect_conflicts, evaluate_sample
from handwave.gestures.custom_gesture_store import CustomGestureStore
from handwave.ui.gesture_icons import gesture_icon


class CustomGesturesDialog(QDialog):
    """Create/manage static gestures with one timed sample-recording control."""

    RECORDING_DURATION_MS = 2_500

    def __init__(self, store: CustomGestureStore, parent=None) -> None:
        super().__init__(parent)
        self.store, self.pending_name, self.samples, self.frames = store, "", [], None
        self.setWindowTitle("HandWave Custom Gestures")
        self.list, self.status = QListWidget(), QLabel("Add a gesture, then record at least two repetitions.")
        self.add, self.record, self.test, self.save = QPushButton("Add Custom Gesture"), QPushButton("Record 2.5-second sample"), QPushButton("Test Recognition"), QPushButton("Save")
        self.rename, self.enable, self.duplicate, self.delete = QPushButton("Rename"), QPushButton("Enable / Disable"), QPushButton("Duplicate"), QPushButton("Delete")
        self.progress = QProgressBar(); self.progress.setRange(0, self.RECORDING_DURATION_MS)
        self.add.clicked.connect(self._add); self.record.clicked.connect(self._record); self.test.clicked.connect(self._test); self.save.clicked.connect(self._save)
        self.rename.clicked.connect(self._rename); self.enable.clicked.connect(self._toggle); self.duplicate.clicked.connect(self._duplicate); self.delete.clicked.connect(self._delete)
        self._elapsed = 0; self._recording_timer = QTimer(self); self._recording_timer.setInterval(50); self._recording_timer.timeout.connect(self._advance_recording)
        layout = QVBoxLayout(self); layout.addWidget(self.status); layout.addWidget(self.list); layout.addWidget(self.progress)
        for buttons in ((self.add, self.record), (self.test, self.save), (self.rename, self.enable, self.duplicate, self.delete)):
            row = QHBoxLayout()
            for button in buttons: row.addWidget(button)
            layout.addLayout(row)
        self._refresh()

    def feed_hands(self, hands: tuple) -> None:
        if self.frames is None: return
        hand = hands[0] if hands else None
        self.frames.append(GestureFrame.from_landmarks(time.monotonic(), hand.landmarks if hand else None, len(hands)))

    def _add(self) -> None:
        name, ok = QInputDialog.getText(self, "Add Custom Gesture", "Gesture name")
        if ok and name.strip(): self.pending_name, self.samples = name.strip(), []; self.status.setText(f"{self.pending_name}: hold a static pose, then select Record sample.")

    def _record(self) -> None:
        if not self.pending_name: self.status.setText("Name the gesture first."); return
        self.frames, self._elapsed = [], 0; self.progress.setValue(0); self.record.setEnabled(False)
        self.status.setText("Recording landmark data only — hold still. No video is saved."); self._recording_timer.start()

    def _advance_recording(self) -> None:
        self._elapsed += self._recording_timer.interval(); self.progress.setValue(min(self._elapsed, self.RECORDING_DURATION_MS))
        if self._elapsed >= self.RECORDING_DURATION_MS:
            self._recording_timer.stop(); self.record.setEnabled(True); self._finish_recording()

    def _finish_recording(self) -> None:
        if self.frames is None: return
        sample, self.frames = GestureSample(tuple(self.frames)), None; quality = evaluate_sample(sample)
        if quality.accepted: self.samples.append(sample); self.status.setText(f"Accepted sample {len(self.samples)}. Record another repetition.")
        else: self.status.setText(f"Sample rejected: {quality.reason}. Keep the hand visible and still, then try again.")

    def _test(self) -> None:
        if not self.samples: return
        scores, tolerance = compute_representative_gesture(self.samples); detection = CustomGestureMatcher([CustomGestureDefinition(name=self.pending_name or "Test", representative_scores=scores, tolerance=tolerance)]).match(scores)
        self.status.setText(f"Test recognition: {detection.name} ({detection.confidence:.0%})")

    def _save(self) -> None:
        if len(self.samples) < 2: self.status.setText("Record at least two accepted repetitions before saving."); return
        scores, tolerance = compute_representative_gesture(self.samples); warnings = detect_conflicts(scores, self.store.list_gestures())
        if warnings and QMessageBox.question(self, "Similar gesture", f"This gesture is very similar to {warnings[0].name}. Save anyway?") != QMessageBox.StandardButton.Yes: return
        stored = tuple({"lighting": sample.lighting, "frames": [{"timestamp": f.timestamp, "hand_count": f.hand_count, "extension_scores": list(f.extension_scores), "centroid": list(f.centroid) if f.centroid else None, "handedness": f.handedness} for f in sample.frames]} for sample in self.samples)
        self.store.add_gesture(CustomGestureDefinition(name=self.pending_name, representative_scores=scores, tolerance=tolerance, sample_count=len(self.samples), samples=stored)); self.pending_name, self.samples = "", []; self._refresh(); self.status.setText("Saved locally. No video was stored.")

    def _selected(self): return self.store.get_gesture(str(self.list.currentItem().data(32))) if self.list.currentItem() else None
    def _rename(self) -> None:
        if gesture := self._selected():
            name, ok = QInputDialog.getText(self, "Rename Custom Gesture", "Name", text=gesture.name)
            if ok and name.strip(): self.store.update_gesture(gesture.gesture_id, name=name.strip()); self._refresh()
    def _toggle(self) -> None:
        if gesture := self._selected(): self.store.set_enabled(gesture.gesture_id, not gesture.enabled); self._refresh()
    def _duplicate(self) -> None:
        if gesture := self._selected(): self.store.duplicate_gesture(gesture.gesture_id); self._refresh()
    def _delete(self) -> None:
        if gesture := self._selected(): self.store.delete_gesture(gesture.gesture_id); self._refresh()
    def _refresh(self) -> None:
        self.list.clear()
        for gesture in self.store.list_gestures():
            from PyQt6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(gesture_icon("Custom"), f"{'Enabled' if gesture.enabled else 'Disabled'}  {gesture.name} ({gesture.sample_count} samples)")
            item.setData(32, gesture.gesture_id); item.setToolTip(gesture.name); self.list.addItem(item)
