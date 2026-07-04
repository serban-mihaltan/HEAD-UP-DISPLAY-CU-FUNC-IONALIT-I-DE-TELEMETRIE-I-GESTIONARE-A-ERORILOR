"""Diagnostic Trouble Code screen widget."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from hud.models.dtc import DtcEntry


class DtcScreen(QWidget):
    """Render DTC rows and expose user actions through Qt signals."""

    refresh_requested = Signal()
    clear_all_requested = Signal()

    def __init__(self) -> None:
        """
        Build the DTC screen UI and wire user actions to signals.

        Implementation details:
            Creates labels, the read-only table, action buttons, styling, layout, and Qt signal
            connections for refresh and clear requests.
        """
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)
        self._scale_percent = 100
        self._active_colors = {
            "background": "#04070B",
            "panel": "#071421",
            "panel_border": "#16324B",
            "text": "#D8E1E8",
            "muted": "#8AA0B2",
        }
        self.title = QLabel("Diagnostic Trouble Codes")
        self.status_label = QLabel("Press Refresh to query the vehicle.")
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Category", "Code", "Description"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.apply_palette(self._active_colors)
        buttons = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.clear_all_button = QPushButton("Clear All")
        for btn in [self.refresh_button, self.clear_all_button]:
            btn.setMinimumHeight(36)
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.clear_all_button)
        buttons.addStretch(1)
        root.addWidget(self.title)
        root.addWidget(self.status_label)
        root.addWidget(self.table, 1)
        root.addLayout(buttons)
        self.refresh_button.clicked.connect(self.refresh_requested)
        self.clear_all_button.clicked.connect(self.clear_all_requested)


    def apply_palette(self, colors: dict[str, str]) -> None:
        """Apply the current HUD palette to the DTC screen."""
        self._active_colors.update(colors)
        bg = self._active_colors.get("background", "#04070B")
        panel = self._active_colors.get("panel", "#071421")
        border = self._active_colors.get("panel_border", "#16324B")
        text = self._active_colors.get("text", "#D8E1E8")
        muted = self._active_colors.get("muted", self._active_colors.get("ticks", "#8AA0B2"))
        scale = max(0.70, min(1.80, float(getattr(self, "_scale_percent", 100)) / 100.0))
        self.title.setStyleSheet(f"font-size:{max(18, int(round(24 * scale)))}px;font-weight:700;color:{text};")
        self.status_label.setStyleSheet(f"font-size:{max(10, int(round(12 * scale)))}px;color:{muted};")
        self.table.setStyleSheet(
            f"QTableWidget{{background:{panel};alternate-background-color:{bg};color:{text};"
            f"gridline-color:{border};selection-background-color:{border};selection-color:{text};"
            f"border:1px solid {border};border-radius:12px;}}"
            "QTableWidget::item{padding:6px;border:none;background:transparent;}"
            f"QTableWidget::item:selected{{background:{border};color:{text};}}"
            f"QHeaderView::section{{background:{panel};color:{text};border:none;padding:8px;}}"
        )

    def set_entries(self, entries: list[DtcEntry]) -> None:
        """
        Replace the visible DTC table with a new result set.

        Implementation details:
            Resizes the table, creates non-editable category/code/description cells for each
            DtcEntry, and updates the status label with the loaded count.
        """
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            items = [
                QTableWidgetItem(entry.category.value),
                QTableWidgetItem(entry.code),
                QTableWidgetItem(entry.description),
            ]
            for item in items:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, items[0])
            self.table.setItem(row, 1, items[1])
            self.table.setItem(row, 2, items[2])
        self.status_label.setText(f"{len(entries)} code(s) loaded")


    def clear_view(self) -> None:
        """
        Clear all visible DTC results.

        Implementation details:
            Sets the table row count to zero and updates the status label to show that no codes are
            loaded.
        """
        self.table.setRowCount(0)
        self.status_label.setText("0 code(s) loaded")

    def set_status(self, text: str) -> None:
        """
        Display a status message above the DTC table.

        Implementation details:
            Writes the provided text directly to the status label so controller code can report
            progress or errors.
        """
        self.status_label.setText(text)

    def apply_ui_scale(self, scale_percent: int) -> None:
        """Resize DTC screen text and action controls for small displays."""
        self._scale_percent = int(scale_percent)
        scale = max(0.70, min(1.80, float(scale_percent) / 100.0))
        self.apply_palette(self._active_colors)
        row_height = max(28, int(round(30 * scale)))
        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, row_height)
        self.refresh_button.setMinimumHeight(max(32, int(round(36 * scale))))
        self.clear_all_button.setMinimumHeight(max(32, int(round(36 * scale))))

