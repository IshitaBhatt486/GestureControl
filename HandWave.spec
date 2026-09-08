# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

mediapipe_data, mediapipe_binaries, mediapipe_hidden = collect_all("mediapipe")

a = Analysis(
    ["handwave/main.py"],
    pathex=["."],
    binaries=mediapipe_binaries,
    datas=mediapipe_data
    + [
        ("handwave/assets/handwave.ico", "handwave/assets"),
        ("handwave/config/settings.json", "handwave/config"),
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
    name="HandWave",
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
    icon="handwave/assets/handwave.ico",
    version="packaging/version_info.txt",
)
