from pathlib import Path


def test_release_spec_has_single_executable_icon_and_version():
    root = Path(__file__).resolve().parents[1]
    spec = (root / "GestureOS.spec").read_text(encoding="utf-8")
    assert 'name="GestureOS"' in spec
    assert 'icon="gestureos/assets/gestureos.ico"' in spec
    assert 'version="packaging/version_info.txt"' in spec
    assert "COLLECT(" not in spec
    assert (root / "gestureos" / "assets" / "gestureos.ico").is_file()
