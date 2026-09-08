from unittest.mock import patch

import pytest

from handwave.config.atomic_write import atomic_replace


def test_atomic_replace_succeeds_immediately(tmp_path):
    temporary = tmp_path / "file.tmp"
    target = tmp_path / "file.json"
    temporary.write_text("data", encoding="utf-8")

    atomic_replace(temporary, target)

    assert target.read_text(encoding="utf-8") == "data"
    assert not temporary.exists()


def test_atomic_replace_retries_past_a_transient_lock(tmp_path):
    temporary = tmp_path / "file.tmp"
    target = tmp_path / "file.json"
    temporary.write_text("data", encoding="utf-8")

    real_replace = type(temporary).replace
    call_count = {"n": 0}

    def flaky_replace(self, target_path):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise PermissionError("transient lock")
        return real_replace(self, target_path)

    with patch("handwave.config.atomic_write.time.sleep"):
        with patch.object(type(temporary), "replace", flaky_replace):
            atomic_replace(temporary, target, attempts=5, delay=0.0)

    assert call_count["n"] == 3
    assert target.read_text(encoding="utf-8") == "data"


def test_atomic_replace_raises_after_exhausting_attempts(tmp_path):
    temporary = tmp_path / "file.tmp"
    target = tmp_path / "file.json"
    temporary.write_text("data", encoding="utf-8")

    with patch("handwave.config.atomic_write.time.sleep"):
        with patch.object(type(temporary), "replace", side_effect=PermissionError("locked")):
            with pytest.raises(PermissionError):
                atomic_replace(temporary, target, attempts=3, delay=0.0)
