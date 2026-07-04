from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from hud.models.enums import DashboardStyle
from hud.models.settings import AppSettings
from hud.models.telemetry import TelemetrySnapshot
from hud.utils.color import qcolor
from hud.utils.gauge_math import digital_rpm_bands, label_color_is_red, ratio


class DashboardWidget(QWidget):
    """
    Render the legacy single-cluster dashboard visualization.

    Implementation details:
        Selects a dashboard style from settings and delegates the actual drawing to style-specific
        painter helpers.
    """
    def __init__(self, settings: AppSettings) -> None:
        """
        Handle init behavior for DashboardWidget.

        Implementation details:
            Uses current settings, telemetry state, and Qt painting/layout APIs to update the visual
            output.
        """
        super().__init__()
        self.settings = settings
        self.snapshot = TelemetrySnapshot()
        self.setMinimumHeight(360)

    def set_settings(self, settings: AppSettings) -> None:
        """
        Update the settings used by this widget or graph.

        Implementation details:
            Stores the new value on the object and triggers repaint or downstream updates when
            required.
        """
        self.settings = settings
        self.update()

    def set_snapshot(self, snapshot: TelemetrySnapshot) -> None:
        """
        Update the telemetry snapshot used for rendering.

        Implementation details:
            Stores the new value on the object and triggers repaint or downstream updates when
            required.
        """
        self.snapshot = snapshot
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        """
        Render the widget whenever Qt requests a repaint.

        Implementation details:
            Creates a QPainter, derives current geometry from widget size, and calls specialized
            drawing helpers.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), qcolor(self.settings.colors["background"]))
        style = self.settings.style
        if style == DashboardStyle.DIGITAL:
            self._paint_digital(painter)
        elif style == DashboardStyle.SEMI_ANALOG:
            self._paint_semi_analog(painter)
        elif style == DashboardStyle.ANALOG:
            self._paint_analog(painter)
        else:
            self._paint_racing(painter)
        painter.end()

    def _paint_speed_center(self, painter: QPainter, rect: QRectF) -> None:
        """
        Draw the central speed text for the legacy dashboard.

        Implementation details:
            Uses QPainter primitives and current settings/snapshot state to draw the requested
            visual element.
        """
        painter.setPen(qcolor(self.settings.colors["speed"]))
        big = QFont("Arial", max(26, int(rect.height() * 0.22)), QFont.Bold)
        painter.setFont(big)
        painter.drawText(rect, Qt.AlignCenter, f"{int(self.snapshot.speed_kph):03d}")
        small_rect = rect.adjusted(0, rect.height() * 0.28, 0, 0)
        painter.setFont(QFont("Arial", max(11, int(rect.height() * 0.07))))
        painter.drawText(small_rect, Qt.AlignHCenter | Qt.AlignTop, "km/h")

    def _paint_digital(self, painter: QPainter) -> None:
        """
        Draw the legacy digital dashboard style.

        Implementation details:
            Uses QPainter primitives and current settings/snapshot state to draw the requested
            visual element.
        """
        center_rect = QRectF(self.width() * 0.28, self.height() * 0.18, self.width() * 0.44, self.height() * 0.46)
        self._paint_speed_center(painter, center_rect)
        self._paint_digital_rpm_bar(painter, QRectF(self.width() * 0.08, self.height() * 0.72, self.width() * 0.84, self.height() * 0.12), mirrored=False)

    def _paint_semi_analog(self, painter: QPainter) -> None:
        """
        Draw the legacy semi-analog dashboard style.

        Implementation details:
            Uses QPainter primitives and current settings/snapshot state to draw the requested
            visual element.
        """
        self._paint_analog_gauge(painter, QRectF(self.width() * 0.07, self.height() * 0.16, self.width() * 0.38, self.width() * 0.38), self.snapshot.rpm, self.settings.max_rpm, "RPM", self.settings.redline_rpm)
        self._paint_speed_center(painter, QRectF(self.width() * 0.35, self.height() * 0.24, self.width() * 0.30, self.height() * 0.28))

    def _paint_analog(self, painter: QPainter) -> None:
        """
        Draw an analog circular gauge widget.

        Implementation details:
            Uses QPainter primitives and current settings/snapshot state to draw the requested
            visual element.
        """
        self._paint_analog_gauge(painter, QRectF(self.width() * 0.06, self.height() * 0.18, self.width() * 0.34, self.width() * 0.34), self.snapshot.speed_kph, self.settings.max_speed_kph, "km/h", None)
        self._paint_analog_gauge(painter, QRectF(self.width() * 0.60, self.height() * 0.18, self.width() * 0.34, self.width() * 0.34), self.snapshot.rpm, self.settings.max_rpm, "RPM", self.settings.redline_rpm)

    def _paint_racing(self, painter: QPainter) -> None:
        """
        Draw the legacy racing dashboard style.

        Implementation details:
            Uses QPainter primitives and current settings/snapshot state to draw the requested
            visual element.
        """
        self._paint_speed_center(painter, QRectF(self.width() * 0.34, self.height() * 0.20, self.width() * 0.32, self.height() * 0.28))
        self._paint_digital_rpm_bar(painter, QRectF(self.width() * 0.08, self.height() * 0.60, self.width() * 0.84, self.height() * 0.14), mirrored=True)

    def _paint_digital_rpm_bar(self, painter: QPainter, rect: QRectF, mirrored: bool) -> None:
        """
        Draw the legacy RPM bar.

        Implementation details:
            Uses QPainter primitives and current settings/snapshot state to draw the requested
            visual element.
        """
        bands = digital_rpm_bands(self.settings.max_rpm, self.settings.redline_rpm)
        count = max(1, len(bands))
        gap = 4
        if mirrored:
            half = count // 2
            left_rect = QRectF(rect.x(), rect.y(), rect.width() / 2 - gap, rect.height())
            right_rect = QRectF(rect.center().x() + gap, rect.y(), rect.width() / 2 - gap, rect.height())
            self._paint_segment_side(painter, left_rect, half, reverse=True)
            self._paint_segment_side(painter, right_rect, count - half, reverse=False)
        else:
            seg_w = rect.width() / count
            active_ratio = ratio(self.snapshot.rpm, self.settings.max_rpm)
            active_count = int(math.ceil(active_ratio * count))
            for idx, band in enumerate(bands):
                segment = QRectF(rect.x() + idx * seg_w + gap / 2, rect.y(), seg_w - gap, rect.height())
                is_active = idx < active_count
                band_red = band.start_rpm >= self.settings.redline_rpm or band.end_rpm > self.settings.redline_rpm
                color = self.settings.colors["rpm_redline"] if band_red else self.settings.colors["rpm_normal"]
                painter.fillRect(segment, qcolor(color if is_active else "#1A222A"))
            self._paint_rpm_labels(painter, rect)

    def _paint_segment_side(self, painter: QPainter, rect: QRectF, count: int, reverse: bool) -> None:
        """
        Draw one side of segmented legacy gauge indicators.

        Implementation details:
            Uses QPainter primitives and current settings/snapshot state to draw the requested
            visual element.
        """
        total_bands = digital_rpm_bands(self.settings.max_rpm, self.settings.redline_rpm)
        seg_w = rect.width() / max(1, count)
        active_ratio = ratio(self.snapshot.rpm, self.settings.max_rpm)
        active_total = int(math.ceil(active_ratio * len(total_bands)))
        for idx in range(count):
            logical_index = idx if not reverse else count - 1 - idx
            global_index = logical_index if not reverse else logical_index
            band = total_bands[min(global_index, len(total_bands) - 1)]
            x = rect.x() + idx * seg_w + 2
            segment = QRectF(x, rect.y(), seg_w - 4, rect.height())
            is_active = global_index < active_total
            band_red = band.start_rpm >= self.settings.redline_rpm or band.end_rpm > self.settings.redline_rpm
            color = self.settings.colors["rpm_redline"] if band_red else self.settings.colors["rpm_normal"]
            painter.fillRect(segment, qcolor(color if is_active else "#1A222A"))
        self._paint_rpm_labels(painter, QRectF(rect.x() - rect.width(), rect.y(), rect.width() * 2 + 8, rect.height()))

    def _paint_rpm_labels(self, painter: QPainter, rect: QRectF) -> None:
        """
        Draw RPM labels for the legacy bar display.

        Implementation details:
            Uses QPainter primitives and current settings/snapshot state to draw the requested
            visual element.
        """
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        for value in range(1000, self.settings.max_rpm + 1, 1000):
            red = label_color_is_red(value, self.settings.redline_rpm)
            painter.setPen(qcolor(self.settings.colors["rpm_redline" if red else "text"]))
            x = rect.x() + rect.width() * (value / self.settings.max_rpm)
            painter.drawText(QRectF(x - 12, rect.y() - 18, 24, 16), Qt.AlignCenter, str(value // 1000))

    def _paint_analog_gauge(self, painter: QPainter, rect: QRectF, value: float, maximum: int, unit: str, redline: int | None) -> None:
        """
        Draw a generic analog gauge for the legacy dashboard.

        Implementation details:
            Uses QPainter primitives and current settings/snapshot state to draw the requested
            visual element.
        """
        center = rect.center()
        radius = min(rect.width(), rect.height()) / 2
        painter.setPen(QPen(qcolor(self.settings.colors["ticks"]), 2))
        painter.drawEllipse(rect)
        start_angle = 220
        span = 260
        steps = 10
        for i in range(steps + 1):
            frac = i / steps
            ang = math.radians(start_angle - span * frac)
            inner = QPointF(center.x() + math.cos(ang) * radius * 0.76, center.y() - math.sin(ang) * radius * 0.76)
            outer = QPointF(center.x() + math.cos(ang) * radius * 0.92, center.y() - math.sin(ang) * radius * 0.92)
            tick_value = maximum * frac
            tick_red = redline is not None and tick_value >= redline
            painter.setPen(QPen(qcolor(self.settings.colors["rpm_redline" if tick_red else "ticks"]), 2))
            painter.drawLine(inner, outer)
            label_pos = QPointF(center.x() + math.cos(ang) * radius * 0.62, center.y() - math.sin(ang) * radius * 0.62)
            painter.setPen(qcolor(self.settings.colors["text"]))
            label = str(int(tick_value / (1000 if unit == "RPM" else 1)))
            painter.drawText(QRectF(label_pos.x() - 16, label_pos.y() - 10, 32, 20), Qt.AlignCenter, label)
        needle_frac = ratio(value, maximum)
        ang = math.radians(start_angle - span * needle_frac)
        tip = QPointF(center.x() + math.cos(ang) * radius * 0.72, center.y() - math.sin(ang) * radius * 0.72)
        painter.setPen(QPen(qcolor(self.settings.colors["speed" if unit == "km/h" else "rpm_normal"]), 4))
        painter.drawLine(center, tip)
        painter.setPen(qcolor(self.settings.colors["text"]))
        painter.setFont(QFont("Arial", 12, QFont.Bold))
        painter.drawText(QRectF(rect.x(), rect.y() + rect.height() * 0.62, rect.width(), 22), Qt.AlignCenter, f"{int(value)}")
        painter.setFont(QFont("Arial", 10))
        painter.drawText(QRectF(rect.x(), rect.y() + rect.height() * 0.75, rect.width(), 20), Qt.AlignCenter, unit)
