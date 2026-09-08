"""Reproducible cold/warm startup benchmark.

Run with: python -m benchmarks.benchmark_startup

Measures, in a fresh subprocess so imports are never warm from a previous
run in the same process:
  - import cost up to and including `handwave.ui.main_window`
  - QApplication + SettingsManager + MainWindow construction
  - UI-visible time (window.show())

Reports whether mediapipe was imported merely to reach a visible window, since
that import (~0.7s) is the dominant startup cost this benchmark guards
against regressing (see docs/development.md "Startup performance discipline").
"""

from __future__ import annotations

import json
import subprocess
import sys

_PROBE = r"""
import json, sys, time
t0 = time.perf_counter()
marks = {}
def mark(name):
    marks[name] = time.perf_counter() - t0

from PyQt6.QtWidgets import QApplication
mark("pyqt6_import")
from handwave.config.settings_manager import SettingsManager
from handwave.ui.main_window import MainWindow
mark("main_window_import")

app = QApplication(sys.argv)
mark("qapplication_created")
settings = SettingsManager()
window = MainWindow(settings_manager=settings)
mark("main_window_constructed")
window.show()
mark("ui_visible")

marks["mediapipe_imported_before_ui_visible"] = "mediapipe" in sys.modules
print(json.dumps(marks))
"""


def run_once() -> dict:
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def main() -> None:
    cold = run_once()
    print("Cold start (fresh interpreter):")
    print(json.dumps(cold, indent=2))
    if cold["mediapipe_imported_before_ui_visible"]:
        print("\nREGRESSION: mediapipe was imported before the UI became visible.")
    else:
        print("\nOK: mediapipe is not imported until recognition actually starts.")


if __name__ == "__main__":
    main()
