"""Shared helper for the atomic temp-file-then-replace persistence pattern.

On Windows, ``Path.replace`` can transiently fail with ``PermissionError``
when antivirus software or a cloud-sync client (e.g. OneDrive) briefly holds a
handle open on a just-written file. A short bounded retry rides out that
window without weakening the atomicity of the replace itself.
"""

from __future__ import annotations

import time
from pathlib import Path


def atomic_replace(temporary: Path, target: Path, attempts: int = 5, delay: float = 0.02) -> None:
    for attempt in range(attempts):
        try:
            temporary.replace(target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)
