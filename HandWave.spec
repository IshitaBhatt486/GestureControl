# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

mediapipe_data, mediapipe_binaries, mediapipe_hidden = collect_all("mediapipe")
# HandWave uses MediaPipe's hand-landmarker APIs, not its optional GenAI
# converter or upstream test suite. Their discovery pulls in optional torch
# imports and unnecessarily makes release analysis noisy and slow.
mediapipe_hidden = [
    module for module in mediapipe_hidden
    if ".genai" not in module and ".test" not in module
]

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
