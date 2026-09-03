# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

mediapipe_data, mediapipe_binaries, mediapipe_hidden = collect_all("mediapipe")

a = Analysis(
    ["gestureos/main.py"],
    pathex=["."],
    binaries=mediapipe_binaries,
    datas=mediapipe_data
    + [
        ("gestureos/assets/gestureos.ico", "gestureos/assets"),
        ("gestureos/config/settings.json", "gestureos/config"),
    ],
    hiddenimports=mediapipe_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "pytestqt"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GestureOS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="gestureos/assets/gestureos.ico",
    version="packaging/version_info.txt",
)
