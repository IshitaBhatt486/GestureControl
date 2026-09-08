import json

import pytest

from handwave.gestures.custom_gesture import CustomGestureDefinition
from handwave.gestures.custom_gesture_store import CustomGestureStore, SCHEMA_VERSION


def _definition(name="Salute", scores=(1.0, 0.0, 0.0, 0.0, 0.0)):
    return CustomGestureDefinition(name=name, representative_scores=scores, tolerance=0.2)


def test_first_run_has_no_gestures(tmp_path):
    store = CustomGestureStore(tmp_path / "custom_gestures.json")
    assert store.list_gestures() == []


def test_add_gesture_persists_after_restart(tmp_path):
    path = tmp_path / "custom_gestures.json"
    store = CustomGestureStore(path)
    definition = store.add_gesture(_definition())

    restarted = CustomGestureStore(path)
    assert restarted.get_gesture(definition.gesture_id) == definition


def test_add_gesture_rejects_duplicate_name(tmp_path):
    store = CustomGestureStore(tmp_path / "custom_gestures.json")
    store.add_gesture(_definition("Salute"))
    with pytest.raises(ValueError):
        store.add_gesture(_definition("salute"))  # case-insensitive collision


def test_update_and_delete_gesture(tmp_path):
    store = CustomGestureStore(tmp_path / "custom_gestures.json")
    definition = store.add_gesture(_definition())

    updated = store.update_gesture(definition.gesture_id, tolerance=0.3)
    assert updated.tolerance == 0.3

    store.delete_gesture(definition.gesture_id)
    assert store.list_gestures() == []
    with pytest.raises(KeyError):
        store.update_gesture(definition.gesture_id, tolerance=0.1)


def test_duplicate_gesture_is_independent(tmp_path):
    store = CustomGestureStore(tmp_path / "custom_gestures.json")
    original = store.add_gesture(_definition())
    copy = store.duplicate_gesture(original.gesture_id)

    assert copy.gesture_id != original.gesture_id
    store.update_gesture(copy.gesture_id, tolerance=0.4)

    assert store.get_gesture(original.gesture_id).tolerance == 0.2
    assert store.get_gesture(copy.gesture_id).tolerance == 0.4


def test_enable_disable_gesture(tmp_path):
    store = CustomGestureStore(tmp_path / "custom_gestures.json")
    definition = store.add_gesture(_definition())
    disabled = store.set_enabled(definition.gesture_id, False)
    assert disabled.enabled is False


def test_corrupted_primary_file_recovers_from_backup(tmp_path):
    path = tmp_path / "custom_gestures.json"
    store = CustomGestureStore(path)
    store.add_gesture(_definition("First"))
    store.add_gesture(_definition("Second"))  # writes a .bak of the "First only" state

    path.write_text("not json", encoding="utf-8")

    recovered = CustomGestureStore(path)
    assert len(recovered.list_gestures()) == 1


def test_fully_corrupted_state_with_no_backup_starts_empty(tmp_path):
    path = tmp_path / "custom_gestures.json"
    path.write_text("not json", encoding="utf-8")
    assert CustomGestureStore(path).list_gestures() == []


def test_legacy_payload_without_schema_version_is_migrated(tmp_path):
    path = tmp_path / "custom_gestures.json"
    path.write_text(json.dumps({"gestures": [_definition().to_dict()]}), encoding="utf-8")
    store = CustomGestureStore(path)
    assert len(store.list_gestures()) == 1

    store.update_gesture(store.list_gestures()[0].gesture_id, tolerance=0.25)
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == SCHEMA_VERSION
