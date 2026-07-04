from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from hud.models.settings import AppSettings
from hud.models.telemetry import TelemetrySnapshot
from hud.ui.widgets.dashboard_canvas import DashboardCanvas


class MainScreen(QWidget):
    """
    Host the live dashboard canvas used by the main HUD view.

    Implementation details:
        Groups related state and behavior behind a typed object used by the rest of the project.
    """
    layout_changed = Signal(dict)

    def __init__(self, settings: AppSettings) -> None:
        """
        Handle init behavior for MainScreen.

        Implementation details:
            Reads or updates Qt widgets and emits signals so the main window can keep application
            state synchronized.
        """
        super().__init__()
        self.settings = settings
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.dashboard = DashboardCanvas(settings)
        self.dashboard.widget_moved.connect(self.layout_changed)
        layout.addWidget(self.dashboard)

    def apply_settings(self, settings: AppSettings) -> None:
        """
        Apply the latest application settings to this screen or widget.

        Implementation details:
            Reads or updates Qt widgets and emits signals so the main window can keep application
            state synchronized.
        """
        self.settings = settings
        self.dashboard.set_settings(settings)

    def update_telemetry(self, snapshot: TelemetrySnapshot) -> None:
        """
        Update the screen with a new telemetry snapshot.

        Implementation details:
            Copies incoming state into the widget/service and refreshes dependent output.
        """
        self.dashboard.set_snapshot(snapshot)
