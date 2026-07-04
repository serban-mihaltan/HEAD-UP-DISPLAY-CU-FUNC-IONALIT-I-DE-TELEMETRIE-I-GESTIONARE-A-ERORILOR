from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class IconButton(QPushButton):
    """
    Render a custom icon-style navigation button.

    Implementation details:
        Groups related state and behavior behind a typed object used by the rest of the project.
    """
    def __init__(self, kind: str) -> None:
        """
        Handle init behavior for IconButton.

        Implementation details:
            Uses current settings, telemetry state, and Qt painting/layout APIs to update the visual
            output.
        """
        super().__init__()
        self.kind = kind
        self._background_color = QColor("#071421")
        self._foreground_color = QColor("#D8E1E8")
        self._border_color = QColor("#16324B")
        self.setFixedSize(48, 48)
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)

    def apply_palette(self, colors: dict[str, str]) -> None:
        """Apply the HUD palette to the custom-painted icon button."""
        self._background_color = QColor(colors.get("panel", "#071421"))
        self._foreground_color = QColor(colors.get("text", "#D8E1E8"))
        self._border_color = QColor(colors.get("panel_border", "#16324B"))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        """
        Render the widget whenever Qt requests a repaint.

        Implementation details:
            Creates a QPainter, derives current geometry from widget size, and calls specialized
            drawing helpers.
        """
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(self._border_color, 1.0))
        p.setBrush(self._background_color)
        p.drawEllipse(self.rect().adjusted(4, 4, -4, -4))
        p.setPen(QPen(self._foreground_color, 2.2))
        c = self.rect().center()
        if self.kind == "settings":
            p.drawEllipse(c, 8, 8)
            for dx, dy in [(0, -14), (10, -10), (14, 0), (10, 10), (0, 14), (-10, 10), (-14, 0), (-10, -10)]:
                p.drawLine(c.x() + dx * 0.65, c.y() + dy * 0.65, c.x() + dx, c.y() + dy)
        elif self.kind == "telemetry":
            p.drawLine(c.x() - 15, c.y() + 12, c.x() - 15, c.y() - 12)
            p.drawLine(c.x() - 15, c.y() + 12, c.x() + 15, c.y() + 12)
            path = QPainterPath()
            path.moveTo(c.x() - 13, c.y() + 8)
            path.lineTo(c.x() - 6, c.y() + 2)
            path.lineTo(c.x() + 1, c.y() + 6)
            path.lineTo(c.x() + 7, c.y() - 5)
            path.lineTo(c.x() + 14, c.y() - 9)
            p.drawPath(path)
        elif self.kind == "dtc":
            p.setFont(QFont("Arial", 10, QFont.Bold))
            p.drawText(self.rect().adjusted(5, 6, -5, -6), Qt.AlignCenter, "DTC")
        else:
            p.drawLine(c.x() - 11, c.y() - 6, c.x() + 2, c.y() - 6)
            p.drawLine(c.x() - 11, c.y() - 6, c.x() - 5, c.y() - 12)
            p.drawLine(c.x() - 11, c.y() - 6, c.x() - 5, c.y())
            p.drawLine(c.x() + 11, c.y() + 6, c.x() - 2, c.y() + 6)
            p.drawLine(c.x() + 11, c.y() + 6, c.x() + 5, c.y())
            p.drawLine(c.x() + 11, c.y() + 6, c.x() + 5, c.y() + 12)
        p.end()

    def sizeHint(self) -> QSize:  # noqa: N802
        """
        Return the preferred size for the custom icon button.

        Implementation details:
            Uses current settings, telemetry state, and Qt painting/layout APIs to update the visual
            output.
        """
        return QSize(48, 48)


class TopBar(QWidget):
    """
    Provide the main navigation and connection controls at the top of the app.

    Implementation details:
        Creates Qt buttons, exposes signals, and updates button state as navigation or connection
        status changes.
    """
    mirror_clicked = Signal()
    telemetry_clicked = Signal()
    dtc_clicked = Signal()
    settings_clicked = Signal()

    def __init__(self) -> None:
        """
        Handle init behavior for TopBar.

        Implementation details:
            Uses current settings, telemetry state, and Qt painting/layout APIs to update the visual
            output.
        """
        super().__init__()
        self.setFixedHeight(64)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        self.mirror_button = IconButton("mirror")
        self.telemetry_button = IconButton("telemetry")
        self.dtc_button = IconButton("dtc")
        self.settings_button = IconButton("settings")
        self.mirror_button.clicked.connect(self.mirror_clicked)
        self.telemetry_button.clicked.connect(self.telemetry_clicked)
        self.dtc_button.clicked.connect(self.dtc_clicked)
        self.settings_button.clicked.connect(self.settings_clicked)
        layout.addWidget(self.mirror_button)
        layout.addStretch(1)
        layout.addWidget(self.telemetry_button)
        layout.addWidget(self.dtc_button)
        layout.addWidget(self.settings_button)

    def apply_palette(self, colors: dict[str, str]) -> None:
        """Apply the HUD palette to the top navigation bar."""
        self.setStyleSheet(f"background:{colors.get('background', '#04070B')};")
        for button in (self.mirror_button, self.telemetry_button, self.dtc_button, self.settings_button):
            button.apply_palette(colors)
