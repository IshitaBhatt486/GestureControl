"""Central local icon registry for textual HandWave gesture labels."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

GESTURE_GLYPHS = {
    "Open Palm": "✋", "Fist": "✊", "Thumbs Up": "👍", "Thumbs Down": "👎",
    "Peace Sign": "✌", "Pointing": "👉", "Swipe Left": "←", "Swipe Right": "→",
    "Finger Swipe Up": "↑", "Hand Swipe Up": "⇧", "Finger Swipe Down": "↓", "Hand Swipe Down": "⇩",
    "Pinch": "↕", "Mouse": "🖱", "Custom": "✦", "Unknown": "•",
    "Pointing Up": "☝",
    "Pointing Down": "👇",
    "Pointing Left": "👈",
    "Pointing Right": "👉",
}


def gesture_text(name: str) -> str:
    """Return an icon-prefixed visual label while retaining the full text name."""
    return f"{GESTURE_GLYPHS.get(name, GESTURE_GLYPHS['Custom'])} {name}"


def gesture_icon(name: str, theme: str = "dark") -> QIcon:
    """Build a local theme-aware icon; unknown names receive a safe fallback."""
    pixmap = QPixmap(24, 24); pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor("#0f766e" if theme == "light" else "#5eead4")
    painter.setPen(QPen(color, 2)); painter.setBrush(Qt.BrushStyle.NoBrush)
    if "Swipe" in name:
        painter.drawLine(5, 12, 19, 12)
        if "Left" in name: painter.drawLine(5, 12, 10, 7); painter.drawLine(5, 12, 10, 17)
        elif "Right" in name: painter.drawLine(19, 12, 14, 7); painter.drawLine(19, 12, 14, 17)
        elif "Up" in name: painter.drawLine(12, 5, 12, 19); painter.drawLine(12, 5, 7, 10); painter.drawLine(12, 5, 17, 10)
        else: painter.drawLine(12, 5, 12, 19); painter.drawLine(12, 19, 7, 14); painter.drawLine(12, 19, 17, 14)
    else:
        painter.drawEllipse(5, 5, 14, 14)
    painter.end()
    return QIcon(pixmap)
