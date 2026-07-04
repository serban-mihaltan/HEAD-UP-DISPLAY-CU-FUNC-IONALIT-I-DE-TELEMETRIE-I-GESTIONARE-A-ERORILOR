from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from hud.models.settings import AppSettings
from hud.models.telemetry import TelemetrySnapshot
from hud.services.telemetry_export import default_export_path, export_telemetry


@dataclass(frozen=True)
class TelemetryMetric:
    """
    Describe one telemetry series that can be graphed or exported.

    Implementation details:
        Groups related state and behavior behind a typed object used by the rest of the project.
    """
    key: str
    title: str
    unit: str
    value: Callable[[TelemetrySnapshot], float | None]
    color_key: str
    minimum: Callable[[AppSettings], float]
    maximum: Callable[[AppSettings], float]


METRICS: list[TelemetryMetric] = [
    TelemetryMetric("speed", "Speed", "km/h", lambda s: s.speed_kph, "speed", lambda _: 0.0, lambda st: float(st.max_speed_kph)),
    TelemetryMetric("rpm", "RPM", "rpm", lambda s: s.rpm, "rpm_normal", lambda _: 0.0, lambda st: float(st.max_rpm)),
    TelemetryMetric("throttle_position", "Throttle", "%", lambda s: s.throttle_position, "indicator", lambda _: 0.0, lambda _: 100.0),
    TelemetryMetric("fuel_consumption", "Fuel consumption", "L/100km", lambda s: s.fuel_consumption_l_100km, "fuel", lambda _: 0.0, lambda st: float(st.widget_thresholds.get("fuel_consumption", {}).get("max", 20.0))),
    TelemetryMetric("fuel_level", "Remaining fuel", "%", lambda s: s.fuel_level, "fuel", lambda _: 0.0, lambda _: 100.0),
    TelemetryMetric("coolant_temp", "Coolant", "°C", lambda s: s.coolant_temp_c, "coolant", lambda _: 0.0, lambda _: 130.0),
    TelemetryMetric("oil_temp", "Oil temp", "°C", lambda s: s.oil_temp_c, "text", lambda _: 0.0, lambda _: 150.0),
    TelemetryMetric("battery_voltage", "Battery voltage", "V", lambda s: s.battery_voltage, "indicator", lambda _: 8.0, lambda _: 16.0),
]


class TelemetryGraph(QWidget):
    """
    Render one telemetry metric as a scrolling graph.

    Implementation details:
        Uses QPainter to draw axes, grid lines, thresholds, and the metric polyline from recent
        samples.
    """
    def __init__(self, metric: TelemetryMetric, settings: AppSettings) -> None:
        """
        Handle init behavior for TelemetryGraph.

        Implementation details:
            Reads or updates Qt widgets and emits signals so the main window can keep application
            state synchronized.
        """
        super().__init__()
        self.telemetry_metric = metric
        self.settings = settings
        self.samples: list[TelemetrySnapshot] = []
        self.setMinimumHeight(180)
        self.setMinimumWidth(360)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_settings(self, settings: AppSettings) -> None:
        """
        Update the settings used by this widget or graph.

        Implementation details:
            Stores the new value on the object and triggers repaint or downstream updates when
            required.
        """
        self.settings = settings
        self.update()

    def set_samples(self, samples: list[TelemetrySnapshot]) -> None:
        """
        Replace the graph sample buffer with the provided telemetry history.

        Implementation details:
            Stores the new value on the object and triggers repaint or downstream updates when
            required.
        """
        self.samples = list(samples)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        """
        Render the widget whenever Qt requests a repaint.

        Implementation details:
            Creates a QPainter, derives current geometry from widget size, and calls specialized
            drawing helpers.
        """
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.fillRect(self.rect(), QColor(self.settings.colors["panel"]))
            outer = QRectF(self.rect()).adjusted(8, 8, -8, -8)
            border = QColor(self.settings.colors["panel_border"])
            painter.setPen(QPen(border, 1.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(outer, 12, 12)

            title_rect = QRectF(outer.x() + 12, outer.y() + 8, outer.width() * 0.58, 28)
            latest = self._latest_value()
            latest_text = "--" if latest is None else f"{latest:.1f} {self.telemetry_metric.unit}"
            painter.setPen(QColor(self.settings.colors["text"]))
            painter.setFont(QFont("Arial", 11, QFont.Bold))
            painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter, self.telemetry_metric.title)
            painter.setPen(QColor(self.settings.colors.get(self.telemetry_metric.color_key, self.settings.colors["text"])))
            painter.drawText(QRectF(outer.x() + outer.width() * 0.56, outer.y() + 8, outer.width() * 0.38, 28), Qt.AlignRight | Qt.AlignVCenter, latest_text)

            plot = QRectF(outer.x() + 58, outer.y() + 46, outer.width() - 74, outer.height() - 72)
            self._draw_grid(painter, plot)
            self._draw_series(painter, plot)
        finally:
            painter.end()

    def _latest_value(self) -> float | None:
        """
        Return the latest numeric value for this graph metric.

        Implementation details:
            Reads or updates Qt widgets and emits signals so the main window can keep application
            state synchronized.
        """
        for sample in reversed(self.samples):
            value = self.telemetry_metric.value(sample)
            if value is not None:
                return float(value)
        return None

    def _draw_grid(self, painter: QPainter, plot: QRectF) -> None:
        """
        Draw graph grid lines, axis labels, and optional threshold markers.

        Implementation details:
            Uses QPainter primitives and calculated geometry to render the requested overlay or
            shape.
        """
        values = self._series_values()
        min_v, max_v, ticks = self._value_axis(values)

        grid = QColor(self.settings.colors["panel_border"])
        grid.setAlpha(95)
        painter.setPen(QPen(grid, 0.8))
        span_v = max(0.0001, max_v - min_v)
        for tick in ticks:
            y = plot.bottom() - plot.height() * ((tick - min_v) / span_v)
            painter.drawLine(plot.left(), y, plot.right(), y)
        for i in range(5):
            x = plot.x() + plot.width() * i / 4
            painter.drawLine(x, plot.top(), x, plot.bottom())

        painter.setPen(QColor(self.settings.colors["muted"]))
        painter.setFont(QFont("Arial", 8))
        label_width = max(46, min(70, int(plot.left() - 8)))
        for tick in ticks:
            y = plot.bottom() - plot.height() * ((tick - min_v) / span_v)
            painter.drawText(
                QRectF(plot.left() - label_width - 8, y - 8, label_width, 16),
                Qt.AlignRight | Qt.AlignVCenter,
                self._format_axis_label(tick),
            )

    def _draw_series(self, painter: QPainter, plot: QRectF) -> None:
        """
        Draw the telemetry series polyline inside the graph plot area.

        Implementation details:
            Uses QPainter primitives and calculated geometry to render the requested overlay or
            shape.
        """
        values = self._series_values()
        if len(values) < 2:
            painter.setPen(QColor(self.settings.colors["muted"]))
            painter.setFont(QFont("Arial", 9))
            message = "Waiting for data" if not self.samples else "Waiting for another sample"
            painter.drawText(plot, Qt.AlignCenter, message)
            return

        first_t = values[0][0]
        last_t = max(values[-1][0], first_t + 1.0)
        min_v, max_v, _ticks = self._value_axis(values)
        span_t = max(1.0, last_t - first_t)
        span_v = max(0.0001, max_v - min_v)

        def point(ts: float, val: float) -> tuple[float, float]:
            """
            Handle point behavior for TelemetryGraph.

            Implementation details:
                Reads or updates Qt widgets and emits signals so the main window can keep
                application state synchronized.
            """
            x = plot.x() + plot.width() * ((ts - first_t) / span_t)
            y = plot.bottom() - plot.height() * ((val - min_v) / span_v)
            return x, y

        path = QPainterPath()
        x0, y0 = point(*values[0])
        path.moveTo(x0, y0)
        for ts, val in values[1:]:
            x, y = point(ts, val)
            path.lineTo(x, y)
        pen = QPen(QColor(self.settings.colors.get(self.telemetry_metric.color_key, self.settings.colors["text"])), 2.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)

    def _series_values(self) -> list[tuple[float, float]]:
        """
        Extract numeric series values from telemetry snapshots for one metric.

        Implementation details:
            Reads or updates Qt widgets and emits signals so the main window can keep application
            state synchronized.
        """
        values: list[tuple[float, float]] = []
        for sample in self.samples:
            value = self.telemetry_metric.value(sample)
            if value is None:
                continue
            try:
                numeric = float(value)
            except Exception:
                continue
            if math.isfinite(numeric):
                values.append((sample.timestamp, numeric))
        return values

    def _value_axis(self, values: list[tuple[float, float]]) -> tuple[float, float, list[float]]:
        """
        Calculate graph minimum and maximum values for the current data range.

        Implementation details:
            Reads or updates Qt widgets and emits signals so the main window can keep application
            state synchronized.
        """
        configured_min = float(self.telemetry_metric.minimum(self.settings))
        configured_max = float(self.telemetry_metric.maximum(self.settings))
        if configured_max < configured_min:
            configured_min, configured_max = configured_max, configured_min

        if values:
            data_values = [value for _timestamp, value in values]
            raw_min = min(data_values)
            raw_max = max(data_values)
            if raw_max <= raw_min:
                spread = max(abs(raw_max) * 0.10, 1.0)
                raw_min -= spread
                raw_max += spread
            else:
                spread = raw_max - raw_min
                raw_min -= spread * 0.05
                raw_max += spread * 0.05

            # Percent / fixed-range gauges are easier to compare when they keep
            # their natural bounds as long as the data fits. Open-ended values,
            # especially fuel consumption, use a data-driven axis so small
            # changes remain visible and labels stay meaningful.
            fixed_range_metric = self.telemetry_metric.key in {"throttle_position", "fuel_level", "battery_voltage"}
            if fixed_range_metric and configured_min <= min(data_values) and max(data_values) <= configured_max:
                raw_min, raw_max = configured_min, configured_max

            # Most HUD telemetry channels are physically non-negative. The
            # padding/rounding step can otherwise create a misleading negative
            # lower axis, e.g. fuel consumption showing -20 even though all
            # samples are >= 0. Only clamp when the data itself is non-negative;
            # this still allows a metric to show real negative values if a PID
            # or future metric can actually produce them.
            if self._clamp_axis_to_zero(data_values, configured_min):
                raw_min = max(0.0, raw_min)
        else:
            raw_min, raw_max = configured_min, configured_max
            if configured_min >= 0.0:
                raw_min = max(0.0, raw_min)

        nice_min, nice_max, ticks = self._nice_ticks(raw_min, raw_max, tick_count=5)
        if self._metric_is_non_negative() and nice_min < 0.0:
            nice_min = 0.0
            ticks = [tick for tick in ticks if tick >= 0.0]
            if not ticks or ticks[0] > 0.0:
                ticks.insert(0, 0.0)
            if ticks[-1] < nice_max:
                ticks.append(nice_max)
        return nice_min, nice_max, ticks

    def _metric_is_non_negative(self) -> bool:
        """
        Check whether the metric should be clamped to non-negative values.

        Implementation details:
            Reads or updates Qt widgets and emits signals so the main window can keep application
            state synchronized.
        """
        return self.telemetry_metric.key in {
            "speed",
            "rpm",
            "throttle_position",
            "fuel_consumption",
            "fuel_level",
            "battery_voltage",
        }

    def _clamp_axis_to_zero(self, data_values: list[float], configured_min: float) -> bool:
        """
        Clamp a graph axis at zero when the represented metric cannot be negative.

        Implementation details:
            Compares the input against both bounds and returns the nearest valid value.
        """
        if not self._metric_is_non_negative():
            return False
        return configured_min >= 0.0 and all(value >= 0.0 for value in data_values)

    @staticmethod
    def _nice_ticks(raw_min: float, raw_max: float, tick_count: int = 5) -> tuple[float, float, list[float]]:
        """
        Generate readable tick values for the graph axis.

        Implementation details:
            Rounds raw ranges to conventional chart intervals so graph labels are easier to read.
        """
        if not math.isfinite(raw_min) or not math.isfinite(raw_max):
            raw_min, raw_max = 0.0, 1.0
        if raw_max < raw_min:
            raw_min, raw_max = raw_max, raw_min
        if raw_max <= raw_min:
            raw_max = raw_min + 1.0

        intervals = max(1, tick_count - 1)
        raw_step = (raw_max - raw_min) / intervals
        step = TelemetryGraph._nice_number(raw_step, round_to_nearest=True)
        if step <= 0 or not math.isfinite(step):
            step = 1.0
        nice_min = math.floor(raw_min / step) * step
        nice_max = math.ceil(raw_max / step) * step
        # Make sure floating point rounding does not reduce the number of labels.
        ticks = [nice_min + step * i for i in range(intervals + 1)]
        if ticks[-1] < nice_max - step * 0.001:
            ticks.append(nice_max)
        else:
            nice_max = ticks[-1]
        return nice_min, nice_max, ticks

    @staticmethod
    def _nice_number(value: float, round_to_nearest: bool) -> float:
        """
        Round an axis interval to a human-friendly number.

        Implementation details:
            Rounds raw ranges to conventional chart intervals so graph labels are easier to read.
        """
        if value <= 0 or not math.isfinite(value):
            return 1.0
        exponent = math.floor(math.log10(value))
        fraction = value / (10 ** exponent)
        if round_to_nearest:
            if fraction < 1.5:
                nice_fraction = 1.0
            elif fraction < 3.0:
                nice_fraction = 2.0
            elif fraction < 7.0:
                nice_fraction = 5.0
            else:
                nice_fraction = 10.0
        else:
            if fraction <= 1.0:
                nice_fraction = 1.0
            elif fraction <= 2.0:
                nice_fraction = 2.0
            elif fraction <= 5.0:
                nice_fraction = 5.0
            else:
                nice_fraction = 10.0
        return nice_fraction * (10 ** exponent)

    @staticmethod
    def _format_axis_label(value: float) -> str:
        """
        Format a numeric axis value for display on the graph.

        Implementation details:
            Chooses precision and suffixes based on the value range so labels remain readable.
        """
        if abs(value) >= 100:
            return f"{value:.0f}"
        if abs(value) >= 10:
            return f"{value:.1f}".rstrip("0").rstrip(".")
        if abs(value) >= 1:
            return f"{value:.2f}".rstrip("0").rstrip(".")
        return f"{value:.3f}".rstrip("0").rstrip(".")


class TelemetryScreen(QWidget):
    """
    Collect, display, and export telemetry history samples.

    Implementation details:
        Buffers TelemetrySnapshot values, filters them by the selected time window, refreshes
        graphs, and delegates export work.
    """
    settings_changed = Signal(object)

    def __init__(self, settings: AppSettings) -> None:
        """
        Handle init behavior for TelemetryScreen.

        Implementation details:
            Reads or updates Qt widgets and emits signals so the main window can keep application
            state synchronized.
        """
        super().__init__()
        self.settings = settings
        self.samples: list[TelemetrySnapshot] = []
        self._last_recorded_timestamp: float | None = None
        self._last_auto_export_signature: tuple[int, float] | None = None
        self._loading_controls = False
        self._active_colors = dict(settings.colors)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        header = QHBoxLayout()
        self.title = QLabel("Telemetry")
        self.status = QLabel("Connect to the vehicle to begin recording.")
        self.export_button = QPushButton("Export")
        self.clear_button = QPushButton("Clear graphs")
        header.addWidget(self.title)
        header.addWidget(self.status, 1)
        header.addWidget(self.export_button)
        header.addWidget(self.clear_button)
        root.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        body = QWidget()
        body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.grid = QGridLayout(body)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(12)
        self.graphs: list[TelemetryGraph] = []
        for idx, metric in enumerate(METRICS):
            graph = TelemetryGraph(metric, settings)
            self.graphs.append(graph)
            self.grid.addWidget(graph, idx // 2, idx % 2)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        self.export_button.clicked.connect(self.export_dialog)
        self.clear_button.clicked.connect(self.clear)
        self.apply_settings(settings)


    def apply_palette(self, colors: dict[str, str]) -> None:
        """Apply the current HUD palette to Telemetry-specific styled widgets."""
        self._active_colors = dict(colors)
        text = self._active_colors.get("text", "#D8E1E8")
        muted = self._active_colors.get("muted", self._active_colors.get("ticks", "#8AA0B2"))
        self.title.setStyleSheet(f"font-size:24px;font-weight:700;color:{text};")
        self.status.setStyleSheet(f"color:{muted};")

    def apply_settings(self, settings: AppSettings) -> None:
        """
        Apply the latest application settings to this screen or widget.

        Implementation details:
            Reads or updates Qt widgets and emits signals so the main window can keep application
            state synchronized.
        """
        self.settings = settings
        self.apply_palette(settings.colors)
        for graph in self.graphs:
            graph.set_settings(settings)
        self._refresh_graphs()

    def update_telemetry(self, snapshot: TelemetrySnapshot) -> None:
        """
        Update the screen with a new telemetry snapshot.

        Implementation details:
            Copies incoming state into the widget/service and refreshes dependent output.
        """
        if snapshot.connected:
            if self._should_record(snapshot):
                self.samples.append(snapshot)
                self._last_recorded_timestamp = snapshot.timestamp
            self._set_recording_status(snapshot)
        else:
            self.status.setText("Disconnected. Graphs keep the last recorded values.")
        self._refresh_graphs()

    def clear(self) -> None:
        """
        Remove telemetry history and reset the visual state.

        Implementation details:
            Resets the stored state and refreshes the visible UI to match.
        """
        self.samples.clear()
        self._last_recorded_timestamp = None
        self._last_auto_export_signature = None
        self.status.setText("Telemetry history cleared.")
        self._refresh_graphs()

    def has_samples(self) -> bool:
        """
        Report whether telemetry history is available for export.

        Implementation details:
            Reads or updates Qt widgets and emits signals so the main window can keep application
            state synchronized.
        """
        return bool(self.samples)

    def export_dialog(self) -> Path | None:
        """
        Ask the user for an export destination and write telemetry data.

        Implementation details:
            Builds a destination path, normalizes samples, and delegates writing to the export
            helpers.
        """
        if not self.samples:
            QMessageBox.information(self, "Export telemetry", "No telemetry samples to export yet.")
            return None
        fmt = self.settings.telemetry.export_format.lower()
        default = default_export_path(Path.home(), fmt)
        if fmt == "csv":
            filter_text = "CSV file (*.csv);;Excel workbook (*.xlsx)"
        else:
            filter_text = "Excel workbook (*.xlsx);;CSV file (*.csv)"
        filename, _ = QFileDialog.getSaveFileName(self, "Export telemetry", str(default), filter_text)
        if not filename:
            return None
        try:
            path = export_telemetry(self.samples, Path(filename))
        except Exception as exc:
            QMessageBox.warning(self, "Export telemetry", f"Export failed: {exc}")
            return None
        self.status.setText(f"Exported {len(self.samples)} samples to {path}.")
        QMessageBox.information(self, "Export telemetry", f"Exported telemetry to:\n{path}")
        return path

    def auto_export(self, fallback_base_dir: Path) -> Path | None:
        """
        Export telemetry automatically to the configured directory.

        Implementation details:
            Reads or updates Qt widgets and emits signals so the main window can keep application
            state synchronized.
        """
        if not self.settings.telemetry.auto_export_enabled or not self.samples:
            return None
        signature = (len(self.samples), self.samples[-1].timestamp)
        if signature == self._last_auto_export_signature:
            return None
        fmt = self.settings.telemetry.export_format.lower()
        configured_dir = self.settings.telemetry.auto_export_dir.strip()
        base_dir = Path(configured_dir).expanduser() if configured_dir else fallback_base_dir / "telemetry_exports"
        try:
            path = export_telemetry(self.samples, default_export_path(base_dir, fmt))
        except Exception as exc:
            self.status.setText(f"Automatic telemetry export failed: {exc}")
            return None
        self._last_auto_export_signature = signature
        self.status.setText(f"Automatically exported {len(self.samples)} samples to {path}.")
        return path

    def _should_record(self, snapshot: TelemetrySnapshot) -> bool:
        """
        Decide whether a telemetry sample should be kept in history.

        Implementation details:
            Reads or updates Qt widgets and emits signals so the main window can keep application
            state synchronized.
        """
        if self._last_recorded_timestamp is None:
            return True
        if snapshot.timestamp <= self._last_recorded_timestamp:
            return False
        interval_s = max(0.1, self.settings.telemetry.sample_interval_ms / 1000.0)
        return (snapshot.timestamp - self._last_recorded_timestamp) >= interval_s

    def _set_recording_status(self, snapshot: TelemetrySnapshot) -> None:
        """
        Update the telemetry recording status label.

        Implementation details:
            Stores the new value on the object and triggers repaint or downstream updates when
            required.
        """
        shown = len(self._visible_samples())
        if self.settings.telemetry.graph_full_session:
            view_text = "full session"
        else:
            view_text = f"last {self.settings.telemetry.graph_history_seconds}s"
        self.status.setText(f"Recording {len(self.samples)} samples from {snapshot.source}; showing {shown} ({view_text}).")

    def _visible_samples(self) -> list[TelemetrySnapshot]:
        """
        Return only the samples within the configured graph time window.

        Implementation details:
            Reads or updates Qt widgets and emits signals so the main window can keep application
            state synchronized.
        """
        if not self.samples:
            return []
        if self.settings.telemetry.graph_full_session:
            return list(self.samples)
        anchor = self.samples[-1].timestamp
        cutoff = anchor - float(self.settings.telemetry.graph_history_seconds)
        return [sample for sample in self.samples if sample.timestamp >= cutoff]

    def _refresh_graphs(self) -> None:
        """
        Refresh all telemetry graphs from the current visible sample buffer.

        Implementation details:
            Reads or updates Qt widgets and emits signals so the main window can keep application
            state synchronized.
        """
        visible = self._visible_samples()
        for graph in self.graphs:
            graph.set_samples(visible)

