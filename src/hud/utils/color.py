from __future__ import annotations

from PySide6.QtGui import QColor


def qcolor(value: str) -> QColor:
    """
    Create a QColor from a hex string with a safe fallback.

    Implementation details:
        Attempts to parse the requested color and returns the fallback color when parsing fails.
    """
    color = QColor(value)
    if not color.isValid():
        return QColor("#FFFFFF")
    return color
