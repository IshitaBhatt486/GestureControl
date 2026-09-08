# Gesture recognition

## Built-in static gestures

`GestureEngine.GESTURE_PATTERNS` (`handwave/gestures/gesture_engine.py`) maps a
per-finger extended/folded pattern (`HandLandmarkData.get_finger_states()`,
derived from joint angles, rotation-independent) to a name: Open Palm, Fist,
Thumbs Up, Thumbs Down, Peace Sign, Pointing. Thumbs Up/Down also check the
thumb's direction vector, since both share the same finger-state pattern.
Swipe Left/Right (`SwipeRecognizer`) and pinch (`PinchController`) use
centroid motion instead of a static pattern.

## Multi-hand tracking

MediaPipe is configured for up to 2 hands (`GestureEngine.MAX_HANDS`). Each
detected hand becomes an immutable `HandState`
(`handwave/gestures/hand_state.py`): landmarks, timestamp, handedness (or
`None` when MediaPipe's handedness confidence is below
`HANDEDNESS_CONFIDENCE_THRESHOLD` — treated explicitly as "uncertain," never
guessed), and a coarse `pose` property (Open Palm / Fist / Other) used only
for two-hand pose agreement. The first detected hand is always the "primary"
hand for single-hand fields, which is exactly what happened before multi-hand
support existed (max_num_hands was 1), so single-hand behavior is unchanged.

## Two-hand gestures

`TwoHandRecognizer` (`handwave/gestures/two_hand_recognizer.py`) treats a
two-hand gesture as a *relationship* between two `HandState`s — centroid
distance and its change across frames, plus pose agreement — rather than
running the single-hand classifier twice and guessing:

| Gesture | Condition |
|---|---|
| Both Palms Open | both hands' pose is Open Palm, distance stable |
| Both Fists | both hands' pose is Fist, distance stable |
| Hands Moving Apart | both Open Palm, centroid distance increasing past a threshold |
| Hands Moving Together | both Open Palm, centroid distance decreasing past a threshold |

Requiring pose agreement before motion is considered is what keeps incidental
repositioning (e.g., while doing an unrelated single-hand gesture) from being
misread as a two-hand gesture — see the false-activation tests in
`tests/test_two_hand_recognizer.py`.

## Arbitration priority

One action name is chosen per frame, in this order (implemented in
`GestureWorker.run()`, `handwave/vision/camera_manager.py`):

**two-hand gesture > pinch > swipe > static gesture**

This is a plain `if/elif` chain, not a configurable priority table — changing
it means editing that one method, with a comment there explaining the
rationale (two-hand and pinch are intentional, low-ambiguity motions;
swipe and static poses are more prone to accidental triggering while doing
something else with the hand).

## Custom gestures (static, first cut)

`handwave/gestures/custom_gesture.py` builds a custom gesture from the same
5-value finger-extension vector the built-in patterns use
(`extension_vector()`), so built-in and custom gestures share one
representation. Recording quality control (`evaluate_sample`) rejects a
sample for: no hand detected, too much tracking loss, too short/long a
duration, inconsistent trajectory (centroid moved too much for a *static*
pose), or excessive per-finger variance. `compute_representative_gesture()`
averages accepted samples into a centroid and derives a distance tolerance;
`CustomGestureMatcher` is a nearest-centroid classifier against that
tolerance. `detect_conflicts()` compares a candidate against both built-in
prototypes and existing custom gestures. `combine_detections()` gives
built-in gestures priority — a custom gesture only fills in poses the
built-in patterns leave as "Unknown."

**Limitations, explicitly**: only static single-hand custom gestures are
implemented end to end. The frame/sample data model
(`GestureFrame`/`GestureSample`) already records per-frame timestamp and
centroid, so motion gestures and two-hand custom gestures can reuse the same
storage format later, but their matching logic does not exist yet. There is
no recording/test UI yet — `CustomGestureStore` persists definitions, but
creating one currently requires calling the Python API directly.

## Record and replay

`GestureEngine.recognize_hands(hand_states)` is the single method that runs
recognition (built-in + custom + two-hand) after hand states are known —
`process()` calls it after MediaPipe extraction; `LandmarkReplayer`
(`handwave/gestures/landmark_replay.py`) calls it directly with hand states
reconstructed from a recorded `LandmarkSequence`
(`handwave/gestures/landmark_sequence.py`). Replaying a sequence therefore
exercises the *exact* recognition code path used live — there is no second,
parallel implementation. See:

```powershell
python -m tools.replay_gesture path\to\sequence.json --speed 2
```

Recordings store normalized landmark data only (never camera frames), with a
`schema_version` and metadata field labeling the content as landmark data.
