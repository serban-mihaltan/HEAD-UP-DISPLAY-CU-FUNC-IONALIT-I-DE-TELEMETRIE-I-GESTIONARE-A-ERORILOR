from __future__ import annotations

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel


class TelemetryCards(QFrame):
    """
    Display compact cards for the latest telemetry values.

    Implementation details:
        Groups related state and behavior behind a typed object used by the rest of the project.
    """
    KEYS = [
        "fuel_level",
        "fuel_consumption",
        "coolant_temp",
        "oil_temp",
        "throttle_position",
        "battery_voltage",
        "cel",
    ]

    def __init__(self) -> None:
        """
        Handle init behavior for TelemetryCards.

        Implementation details:
            Uses current settings, telemetry state, and Qt painting/layout APIs to update the visual
            output.
        """
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.layout = QGridLayout(self)
        self.labels: dict[str, QLabel] = {}
        for row, key in enumerate(self.KEYS):
            title = QLabel(key.replace("_", " ").title())
            value = QLabel("--")
            self.layout.addWidget(title, row, 0)
            self.layout.addWidget(value, row, 1)
            self.labels[key] = value

    def update_values(self, values: dict[str, str], visible_map: dict[str, bool]) -> None:
        """
        Refresh telemetry cards from the latest snapshot.

        Implementation details:
            Copies incoming state into the widget/service and refreshes dependent output.
        """
        for i, (key, value_label) in enumerate(self.labels.items()):
            title_item = self.layout.itemAtPosition(i, 0)
            value_item = self.layout.itemAtPosition(i, 1)
            visible = visible_map.get(key, True)
            if title_item and title_item.widget():
                title_item.widget().setVisible(visible)
            if value_item and value_item.widget():
                value_item.widget().setVisible(visible)
            value_label.setText(values.get(key, "--"))
