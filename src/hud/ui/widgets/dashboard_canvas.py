from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from hud.models.settings import AppSettings, DEFAULT_WIDGET_ORDER
from hud.models.telemetry import TelemetrySnapshot


@dataclass
class DragState:
    """
    Track the active dashboard widget drag or resize operation.

    Implementation details:
        Groups related state and behavior behind a typed object used by the rest of the project.
    """
    key: str | None = None
    mode: str = "none"  # none | move | resize
    edge: str = ""
    offset_x: float = 0.0
    offset_y: float = 0.0
    start_rect: tuple[float, float, float, float] | None = None


class DashboardCanvas(QWidget):
    """
    Render and edit the configurable dashboard widget layout.

    Implementation details:
        Uses normalized widget rectangles, mouse hit testing, grid snapping, and QPainter drawing
        helpers.
    """
    widget_moved = Signal(dict)

    def __init__(self, settings: AppSettings) -> None:
        """
        Handle init behavior for DashboardCanvas.

        Implementation details:
            Uses current settings, telemetry state, and Qt painting/layout APIs to update the visual
            output.
        """
        super().__init__()
        self.settings = settings
        self.snapshot = TelemetrySnapshot(connected=False, source="none")
        self.drag = DragState()
        self.setMinimumSize(900, 500)
        self.setMouseTracking(True)

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

    def _widget_keys(self) -> list[str]:
        """
        Return widget keys in the same order they were added to the layout.

        Implementation details:
            Uses current settings, telemetry state, and Qt painting/layout APIs to update the visual
            output.
        """
        order: list[str] = []
        for key in getattr(self.settings, "widget_order", DEFAULT_WIDGET_ORDER):
            if key in DEFAULT_WIDGET_ORDER and key not in order:
                order.append(key)
        for key in DEFAULT_WIDGET_ORDER:
            if key not in order:
                order.append(key)
        return order

    def _fit_font(self, family: str, text: str, rect: QRectF, weight: int = QFont.Bold, max_ratio: float = 0.55, min_px: int = 8) -> QFont:
        """
        Create a font size that fits text inside a target rectangle.

        Implementation details:
            Uses current settings, telemetry state, and Qt painting/layout APIs to update the visual
            output.
        """
        safe_w = max(1.0, rect.width() * 0.88)
        safe_h = max(1.0, rect.height() * 0.82)
        size = max(min_px, int(min(rect.height() * max_ratio, rect.width() * 0.28)))
        while size > min_px:
            font = QFont(family)
            font.setBold(weight >= QFont.Bold)
            font.setPixelSize(size)
            metrics = QFontMetrics(font)
            tight = metrics.tightBoundingRect(text)
            if tight.width() <= safe_w and metrics.height() <= safe_h:
                return font
            size -= 1
        font = QFont(family)
        font.setBold(weight >= QFont.Bold)
        font.setPixelSize(min_px)
        return font

    def _actual_rect(self, key: str) -> QRectF:
        """
        Convert a normalized widget rectangle into a pixel rectangle.

        Implementation details:
            Uses current settings, telemetry state, and Qt painting/layout APIs to update the visual
            output.
        """
        p = self.settings.widget_positions.get(key, {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.1})
        return QRectF(p["x"] * self.width(), p["y"] * self.height(), p["w"] * self.width(), p["h"] * self.height())

    def _safe_dim(self, value: float, fallback: float) -> float:
        """
        Return a non-zero safe dimension for layout calculations.

        Implementation details:
            Validates inputs and substitutes fallback values before returning the result.
        """
        try:
            if math.isfinite(value) and value > 0:
                return value
        except Exception:
            pass
        return fallback

    def _set_rect(self, key: str, rect: QRectF, snap_mode: str | None = None) -> None:
        """
        Store a normalized widget rectangle back into settings.

        Implementation details:
            Stores the new value on the object and triggers repaint or downstream updates when
            required.
        """
        if self.settings.layout_grid_enabled and not self.settings.widget_locked:
            rect = self._snap_rect(rect, snap_mode or "move")
        w = self._safe_dim(self.width(), 1.0)
        h = self._safe_dim(self.height(), 1.0)
        min_w = 80.0 / w
        min_h = 52.0 / h
        rw = max(min_w, min(0.98, rect.width() / w))
        rh = max(min_h, min(0.98, rect.height() / h))
        rx = max(0.0, min(1.0 - rw, rect.x() / w))
        ry = max(0.0, min(1.0 - rh, rect.y() / h))
        self.settings.widget_positions[key] = {"x": rx, "y": ry, "w": rw, "h": rh}
        self.widget_moved.emit(self.settings.widget_positions)
        self.update()

    def _grid_size(self) -> float:
        """
        Return the active dashboard snap-grid size.

        Implementation details:
            Uses current settings, telemetry state, and Qt painting/layout APIs to update the visual
            output.
        """
        try:
            return float(max(8, min(160, int(self.settings.layout_grid_size_px))))
        except Exception:
            return 32.0

    def _snap_value(self, value: float) -> float:
        """
        Snap one coordinate value to the grid.

        Implementation details:
            Uses current settings, telemetry state, and Qt painting/layout APIs to update the visual
            output.
        """
        grid = self._grid_size()
        return round(value / grid) * grid

    def _snap_rect(self, rect: QRectF, mode: str) -> QRectF:
        """
        Snap a widget rectangle to the dashboard grid.

        Implementation details:
            Uses current settings, telemetry state, and Qt painting/layout APIs to update the visual
            output.
        """
        if self.width() <= 0 or self.height() <= 0:
            return rect
        min_w = 80.0
        min_h = 52.0
        if mode == "resize":
            left = self._snap_value(rect.left())
            top = self._snap_value(rect.top())
            right = self._snap_value(rect.right())
            bottom = self._snap_value(rect.bottom())
            if right - left < min_w:
                right = left + min_w
            if bottom - top < min_h:
                bottom = top + min_h
            snapped = QRectF(QPointF(left, top), QPointF(right, bottom)).normalized()
        else:
            snapped = QRectF(rect)
            snapped.moveLeft(self._snap_value(rect.left()))
            snapped.moveTop(self._snap_value(rect.top()))
        snapped.moveLeft(max(0.0, min(self.width() - snapped.width(), snapped.left())))
        snapped.moveTop(max(0.0, min(self.height() - snapped.height(), snapped.top())))
        return snapped

    def _edge_mode(self, rect: QRectF, pos: QPointF) -> str:
        """
        Identify which resize edge or corner is under the pointer.

        Implementation details:
            Uses current settings, telemetry state, and Qt painting/layout APIs to update the visual
            output.
        """
        margin = max(8.0, min(rect.width(), rect.height()) * 0.06)
        left = abs(pos.x() - rect.left()) <= margin
        right = abs(pos.x() - rect.right()) <= margin
        top = abs(pos.y() - rect.top()) <= margin
        bottom = abs(pos.y() - rect.bottom()) <= margin
        parts = []
        if left:
            parts.append("left")
        elif right:
            parts.append("right")
        if top:
            parts.append("top")
        elif bottom:
            parts.append("bottom")
        return "-".join(parts)

    def _hit_test(self, pos: QPointF) -> tuple[str | None, str, str]:
        """
        Find the dashboard widget under a mouse position.

        Implementation details:
            Uses current settings, telemetry state, and Qt painting/layout APIs to update the visual
            output.
        """
        for key in reversed(self._widget_keys()):
            if key not in self.settings.widget_positions:
                continue
            if key not in ("speed", "rpm") and not self.settings.widget_visibility.get(key, False):
                continue
            rect = self._actual_rect(key)
            if rect.contains(pos):
                edge = self._edge_mode(rect, pos)
                if edge:
                    return key, "resize", edge
                return key, "move", ""
        return None, "none", ""

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """
        Start dragging or resizing a dashboard widget from a mouse press.

        Implementation details:
            Uses hit testing to choose the top-most editable widget and records the initial drag
            state.
        """
        if event.button() != Qt.LeftButton or self.settings.widget_locked:
            return super().mousePressEvent(event)
        pos = self._to_content_pos(event.position())
        key, mode, edge = self._hit_test(pos)
        if key is not None:
            rect = self._actual_rect(key)
            self.drag = DragState(
                key=key,
                mode=mode,
                edge=edge,
                offset_x=pos.x() - rect.x(),
                offset_y=pos.y() - rect.y(),
                start_rect=(rect.x(), rect.y(), rect.width(), rect.height()),
            )
            self.setCursor(self._cursor_for_edge(edge) if mode == "resize" else Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        """
        Update a dashboard drag or resize operation while the mouse moves.

        Implementation details:
            Calculates deltas from the saved drag state, applies snapping and constraints, then
            repaints.
        """
        pos = self._to_content_pos(event.position())
        if self.drag.key:
            key = self.drag.key
            x0, y0, w0, h0 = self.drag.start_rect or (0.0, 0.0, 100.0, 80.0)
            rect = QRectF(x0, y0, w0, h0)
            if self.drag.mode == "move":
                rect.moveTo(pos.x() - self.drag.offset_x, pos.y() - self.drag.offset_y)
            else:
                min_w = 80.0
                min_h = 52.0
                left = rect.left()
                right = rect.right()
                top = rect.top()
                bottom = rect.bottom()
                if "left" in self.drag.edge:
                    left = min(pos.x(), right - min_w)
                if "right" in self.drag.edge:
                    right = max(pos.x(), left + min_w)
                if "top" in self.drag.edge:
                    top = min(pos.y(), bottom - min_h)
                if "bottom" in self.drag.edge:
                    bottom = max(pos.y(), top + min_h)
                rect = QRectF(QPointF(left, top), QPointF(right, bottom)).normalized()
            rect.moveLeft(max(0.0, min(self.width() - rect.width(), rect.x())))
            rect.moveTop(max(0.0, min(self.height() - rect.height(), rect.y())))
            rect.setWidth(min(rect.width(), self.width() - rect.x()))
            rect.setHeight(min(rect.height(), self.height() - rect.y()))
            self._set_rect(key, rect, self.drag.mode)
            event.accept()
            return
        hover, mode, edge = self._hit_test(pos)
        if hover and not self.settings.widget_locked:
            self.setCursor(self._cursor_for_edge(edge) if mode == "resize" else Qt.OpenHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """
        Finish the active dashboard drag or resize operation.

        Implementation details:
            Clears drag state and emits the position-changed signal after an edit completes.
        """
        self.drag = DragState()
        self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def _cursor_for_edge(self, edge: str):
        """
        Choose the cursor shape for a resize edge or corner.

        Implementation details:
            Uses current settings, telemetry state, and Qt painting/layout APIs to update the visual
            output.
        """
        if edge in {"left", "right"}:
            return Qt.SizeHorCursor
        if edge in {"top", "bottom"}:
            return Qt.SizeVerCursor
        if edge in {"left-top", "right-bottom"}:
            return Qt.SizeFDiagCursor
        if edge in {"right-top", "left-bottom"}:
            return Qt.SizeBDiagCursor
        return Qt.SizeAllCursor

    def _to_content_pos(self, pointf) -> QPointF:
        """
        Convert a widget mouse position into dashboard content coordinates.

        Implementation details:
            Uses current settings, telemetry state, and Qt painting/layout APIs to update the visual
            output.
        """
        if not self.settings.mirrored:
            return QPointF(pointf.x(), pointf.y())
        return QPointF(self.width() - pointf.x(), pointf.y())

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
            painter.fillRect(self.rect(), QColor(self.settings.colors["background"]))
            if self.settings.mirrored:
                painter.translate(self.width(), 0)
                painter.scale(-1, 1)
            self._paint_cluster_surface(painter)
            if self.settings.layout_grid_enabled and not self.settings.widget_locked:
                self._paint_layout_grid(painter)
            for key in self._widget_keys():
                if key in ("speed", "rpm") or self.settings.widget_visibility.get(key, False):
                    self._paint_widget(painter, key)
        finally:
            if painter.isActive():
                painter.end()

    def _paint_cluster_surface(self, painter: QPainter) -> None:
        """
        Draw the background surface behind dashboard widgets.

        Implementation details:
            Uses QPainter primitives and current settings/snapshot state to draw the requested
            visual element.
        """
        rect = self.rect().adjusted(2, 2, -2, -2)
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 22, 22)
        panel = QColor(self.settings.colors["panel"])
        panel.setAlpha(10)
        painter.fillPath(path, panel)

    def _paint_layout_grid(self, painter: QPainter) -> None:
        """
        Draw the editable layout grid overlay.

        Implementation details:
            Uses QPainter primitives and current settings/snapshot state to draw the requested
            visual element.
        """
        grid = self._grid_size()
        if grid <= 0:
            return
        minor = QColor(self.settings.colors["muted"])
        minor.setAlpha(34)
        major = QColor(self.settings.colors["muted"])
        major.setAlpha(72)
        x = 0.0
        column = 0
        while x <= self.width():
            painter.setPen(QPen(major if column % 4 == 0 else minor, 0.8))
            painter.drawLine(QPointF(x, 0), QPointF(x, self.height()))
            x += grid
            column += 1
        y = 0.0
        row = 0
        while y <= self.height():
            painter.setPen(QPen(major if row % 4 == 0 else minor, 0.8))
            painter.drawLine(QPointF(0, y), QPointF(self.width(), y))
            y += grid
            row += 1

    def _paint_widget(self, painter: QPainter, key: str) -> None:
        """
        Dispatch one dashboard widget to the correct painter.

        Implementation details:
            Uses QPainter primitives and current settings/snapshot state to draw the requested
            visual element.
        """
        rect = self._actual_rect(key)
        if key == "speed":
            self._paint_speed_widget(painter, rect)
        elif key == "rpm":
            self._paint_rpm_widget(painter, rect)
        else:
            self._paint_card_widget(painter, rect, key)
        if not self.settings.widget_locked:
            self._paint_resize_guides(painter, rect)

    def _paint_speed_widget(self, painter: QPainter, rect: QRectF) -> None:
        """
        Draw the configured speed display widget.

        Implementation details:
            Uses QPainter primitives and current settings/snapshot state to draw the requested
            visual element.
        """
        self._panel(painter, rect, 18)
        if self.settings.speed_style == "analog":
            self._paint_analog(painter, rect, self.snapshot.speed_kph, self.settings.max_speed_kph, "km/h", False)
        else:
            self._draw_speed_digits(painter, rect)

    def _paint_rpm_widget(self, painter: QPainter, rect: QRectF) -> None:
        """
        Draw the configured RPM display widget.

        Implementation details:
            Uses QPainter primitives and current settings/snapshot state to draw the requested
            visual element.
        """
        self._panel(painter, rect, 18)
        if self.settings.rpm_style == "analog":
            self._paint_analog(painter, rect, self.snapshot.rpm, self.settings.max_rpm, "RPM", True)
        else:
            self._paint_digital_rpm(painter, rect)

    def _draw_speed_digits(self, painter: QPainter, rect: QRectF) -> None:
        """
        Draw the large central digital speed value.

        Implementation details:
            Uses QPainter primitives and calculated geometry to render the requested overlay or
            shape.
        """
        digits_rect = QRectF(rect.x() + rect.width() * 0.03, rect.y() + rect.height() * 0.04, rect.width() * 0.94, rect.height() * 0.76)
        value_text = str(max(0, int(round(self.snapshot.speed_kph))))
        painter.setPen(QColor(self.settings.colors["speed"]))
        painter.setFont(self._fit_font("Arial", value_text, digits_rect, max_ratio=0.82, min_px=18))
        painter.drawText(digits_rect.adjusted(0, -1, 0, -1), Qt.AlignHCenter | Qt.AlignVCenter, value_text)

    def _paint_digital_rpm(self, painter: QPainter, rect: QRectF) -> None:
        # Number labels live above the bars. This reads more naturally at HUD
        # sizes and avoids the labels looking like a separate bottom axis.
        """
        Draw the digital RPM bar widget.

        Implementation details:
            Uses QPainter primitives and current settings/snapshot state to draw the requested
            visual element.
        """
        scale_rect = QRectF(rect.x() + rect.width() * 0.06, rect.y() + rect.height() * 0.06, rect.width() * 0.88, rect.height() * 0.20)
        bar_rect = QRectF(rect.x() + rect.width() * 0.06, rect.y() + rect.height() * 0.30, rect.width() * 0.88, rect.height() * 0.48)
        unit_rect = QRectF(rect.x() + rect.width() * 0.06, rect.y() + rect.height() * 0.80, rect.width() * 0.88, rect.height() * 0.14)

        painter.setFont(self._fit_font("Arial", str(max(1, self.settings.max_rpm // 1000)), QRectF(0, 0, 42, scale_rect.height()), max_ratio=0.80, min_px=9))
        max_label = max(1, math.ceil(self.settings.max_rpm / 1000))
        for label in range(1, max_label + 1):
            label_rpm = label * 1000
            if label_rpm > self.settings.max_rpm + 250:
                continue
            x = scale_rect.x() + scale_rect.width() * (min(label_rpm, self.settings.max_rpm) / max(1, self.settings.max_rpm))
            label_red = label_rpm >= self.settings.redline_rpm
            painter.setPen(QColor(self.settings.colors["rpm_redline"] if label_red else self.settings.colors["text"]))
            painter.drawText(QRectF(x - 21, scale_rect.y(), 42, scale_rect.height()), Qt.AlignCenter, str(label))

        segment_step = 100  # ten segments per 1,000 RPM
        band_count = max(10, math.ceil(self.settings.max_rpm / segment_step))
        gap = max(0.5, min(1.4, rect.width() * 0.0022))
        band_width = max(0.8, (bar_rect.width() - gap * (band_count - 1)) / band_count)
        active_count = math.ceil(min(max(self.snapshot.rpm, 0.0), self.settings.max_rpm) / float(segment_step))
        inactive = QColor("#12202C")
        inactive.setAlpha(150)

        for i in range(band_count):
            x = bar_rect.x() + i * (band_width + gap)
            band_start = i * segment_step
            band = QRectF(x, bar_rect.y(), band_width, bar_rect.height())
            is_active = i < active_count
            is_red = band_start >= self.settings.redline_rpm
            fill = self.settings.colors["rpm_redline"] if is_red else self.settings.colors["rpm_normal"]
            color = QColor(fill) if is_active else QColor(inactive)
            if is_active:
                color.setAlpha(245)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            if band_width < 2.2:
                painter.drawRect(band)
            else:
                painter.drawRoundedRect(band, 2.0, 2.0)

        painter.setPen(QColor(self.settings.colors["muted"]))
        painter.setFont(self._fit_font("Arial", "RPM x1000", unit_rect, weight=QFont.DemiBold, max_ratio=0.72, min_px=8))
        painter.drawText(unit_rect, Qt.AlignCenter, "RPM x1000")

    def _paint_analog(self, painter: QPainter, rect: QRectF, value: float, maximum: int, unit: str, has_redline: bool) -> None:
        """
        Draw an analog circular gauge widget.

        Implementation details:
            Uses QPainter primitives and current settings/snapshot state to draw the requested
            visual element.
        """
        center = QPointF(rect.center().x(), rect.y() + rect.height() * 0.56)
        radius = min(rect.width() * 0.40, rect.height() * 0.44)
        start_deg = 225.0
        span_deg = 270.0
        arc_rect = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
        maximum = max(1, int(maximum))
        frac = max(0.0, min(1.0, value / maximum))
        accent = self.settings.colors["rpm_normal"] if has_redline else self.settings.colors["speed"]
        if has_redline and value >= self.settings.redline_rpm:
            accent = self.settings.colors["rpm_redline"]

        painter.setBrush(Qt.NoBrush)
        base_pen = QPen(QColor(18, 32, 44, 150), max(2.0, radius * 0.035))
        base_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(base_pen)
        painter.drawArc(arc_rect, int((90.0 - start_deg) * 16), int(-span_deg * 16))

        # Do not draw a permanent red circular accent on the tach face. The
        # redline remains visible through red tick labels, and the active arc
        # turns red only when RPM actually reaches the configured redline.

        active_pen = QPen(QColor(accent), max(2.4, radius * 0.030))
        active_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(active_pen)
        painter.drawArc(arc_rect, int((90.0 - start_deg) * 16), int(-span_deg * frac * 16))

        if unit == "km/h":
            self._draw_speed_gauge_ticks(painter, center, radius, start_deg, span_deg, maximum)
        else:
            self._draw_rpm_gauge_ticks(painter, center, radius, start_deg, span_deg, maximum, has_redline)

        if self.settings.analog_mode == "needle":
            ang = math.radians(start_deg - span_deg * frac)
            tip = QPointF(center.x() + math.cos(ang) * radius * 0.72, center.y() - math.sin(ang) * radius * 0.72)
            needle_pen = QPen(QColor(accent), max(2.0, radius * 0.025))
            needle_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(needle_pen)
            painter.drawLine(center, tip)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(self.settings.colors["text"]))
            painter.drawEllipse(center, max(3.0, radius * 0.035), max(3.0, radius * 0.035))

        unit_rect = QRectF(rect.x() + rect.width() * 0.16, rect.y() + rect.height() * 0.75, rect.width() * 0.68, rect.height() * 0.14)
        if self.settings.analog_show_value:
            value_text = str(max(0, int(round(value))))
            value_rect = QRectF(rect.x() + rect.width() * 0.16, rect.y() + rect.height() * 0.56, rect.width() * 0.68, rect.height() * 0.22)
            painter.setPen(QColor(accent))
            painter.setFont(self._fit_font("Arial", value_text, value_rect, max_ratio=0.90, min_px=12))
            painter.drawText(value_rect, Qt.AlignCenter, value_text)
        else:
            unit_rect = QRectF(rect.x() + rect.width() * 0.16, rect.y() + rect.height() * 0.64, rect.width() * 0.68, rect.height() * 0.16)
        painter.setPen(QColor(self.settings.colors.get("text", self.settings.colors.get("muted", "#D8E1E8"))))
        painter.setFont(self._fit_font("Arial", unit, unit_rect, weight=QFont.DemiBold, max_ratio=0.75, min_px=8))
        painter.drawText(unit_rect, Qt.AlignCenter, unit)

    def _draw_speed_gauge_ticks(self, painter: QPainter, center: QPointF, radius: float, start_deg: float, span_deg: float, maximum: int) -> None:
        # Minor tick every 10 km/h, labels every 20 km/h.
        """
        Draw speed gauge tick marks and labels.

        Implementation details:
            Uses QPainter primitives and calculated geometry to render the requested overlay or
            shape.
        """
        tick_step = 10
        label_step = 20
        values = list(range(0, maximum + 1, tick_step))
        if values[-1] != maximum:
            values.append(maximum)
        for tick_value in values:
            t = max(0.0, min(1.0, tick_value / max(1, maximum)))
            ang = math.radians(start_deg - span_deg * t)
            labelled = (tick_value % label_step == 0) or tick_value == maximum
            inner_scale = 0.76 if labelled else 0.84
            p1 = QPointF(center.x() + math.cos(ang) * radius * inner_scale, center.y() - math.sin(ang) * radius * inner_scale)
            p2 = QPointF(center.x() + math.cos(ang) * radius * 0.95, center.y() - math.sin(ang) * radius * 0.95)
            painter.setPen(QPen(QColor(self.settings.colors["ticks"]), max(1.0, radius * (0.016 if labelled else 0.009))))
            painter.drawLine(p1, p2)
            if labelled:
                label_radius = radius * 0.61
                lp = QPointF(center.x() + math.cos(ang) * label_radius, center.y() - math.sin(ang) * label_radius)
                painter.setPen(QColor(self.settings.colors.get("text", self.settings.colors.get("muted", "#D8E1E8"))))
                painter.setFont(QFont("Arial", max(7, int(radius * 0.095)), QFont.Bold))
                painter.drawText(QRectF(lp.x() - 22, lp.y() - 10, 44, 20), Qt.AlignCenter, str(int(round(tick_value))))

    def _draw_rpm_gauge_ticks(self, painter: QPainter, center: QPointF, radius: float, start_deg: float, span_deg: float, maximum: int, has_redline: bool) -> None:
        """
        Draw RPM gauge tick marks and labels.

        Implementation details:
            Uses QPainter primitives and calculated geometry to render the requested overlay or
            shape.
        """
        max_label = max(1, math.ceil(maximum / 1000))
        # Half-thousand minor ticks make the analog tach easier to read without
        # crowding the numbered 1k labels.
        tick_values = list(range(0, maximum + 1, 500))
        if tick_values[-1] != maximum:
            tick_values.append(maximum)
        for tick_value in tick_values:
            t = max(0.0, min(1.0, tick_value / max(1, maximum)))
            ang = math.radians(start_deg - span_deg * t)
            major = tick_value % 1000 == 0 or tick_value == maximum
            inner_scale = 0.78 if major else 0.85
            p1 = QPointF(center.x() + math.cos(ang) * radius * inner_scale, center.y() - math.sin(ang) * radius * inner_scale)
            p2 = QPointF(center.x() + math.cos(ang) * radius * 0.95, center.y() - math.sin(ang) * radius * 0.95)
            label_red = has_redline and tick_value >= self.settings.redline_rpm
            tick_color = self.settings.colors["rpm_redline"] if label_red else self.settings.colors["ticks"]
            painter.setPen(QPen(QColor(tick_color), max(1.0, radius * (0.016 if major else 0.010))))
            painter.drawLine(p1, p2)
            if major:
                label_radius = radius * 0.62
                lp = QPointF(center.x() + math.cos(ang) * label_radius, center.y() - math.sin(ang) * label_radius)
                label = str(int(round(tick_value / 1000)))
                normal_label_color = self.settings.colors.get("text", self.settings.colors.get("muted", "#D8E1E8"))
                painter.setPen(QColor(self.settings.colors["rpm_redline"] if label_red else normal_label_color))
                painter.setFont(QFont("Arial", max(8, int(radius * 0.12)), QFont.Bold))
                painter.drawText(QRectF(lp.x() - 22, lp.y() - 11, 44, 22), Qt.AlignCenter, label)
    def _paint_card_widget(self, painter: QPainter, rect: QRectF, key: str) -> None:
        """
        Draw a compact metric card widget.

        Implementation details:
            Uses QPainter primitives and current settings/snapshot state to draw the requested
            visual element.
        """
        self._panel(painter, rect, 14)
        labels = {
            "fuel_level": "Fuel",
            "fuel_consumption": "Cons.",
            "coolant_temp": "Coolant",
            "oil_temp": "Oil temp",
            "throttle_position": "Throttle",
            "battery_voltage": "Voltage",
            "cel": "CEL",
        }
        fuel_consumption_text = "--"
        if self.snapshot.fuel_consumption_l_100km is not None:
            fuel_consumption_text = f"{self.snapshot.fuel_consumption_l_100km:.1f} L/100"
        elif self.snapshot.fuel_rate_lph is not None:
            fuel_consumption_text = f"{self.snapshot.fuel_rate_lph:.1f} L/h"
        values = {
            "fuel_level": "--" if self.snapshot.fuel_level is None else f"{self.snapshot.fuel_level:.0f}%",
            "fuel_consumption": fuel_consumption_text,
            "coolant_temp": "--" if self.snapshot.coolant_temp_c is None else f"{self.snapshot.coolant_temp_c:.0f}°C",
            "oil_temp": "--" if self.snapshot.oil_temp_c is None else f"{self.snapshot.oil_temp_c:.0f}°C",
            "throttle_position": "--" if self.snapshot.throttle_position is None else f"{self.snapshot.throttle_position:.0f}%",
            "battery_voltage": "--" if self.snapshot.battery_voltage is None else f"{self.snapshot.battery_voltage:.1f} V",
            "cel": "ON" if self.snapshot.cel_active else "OFF",
        }
        orientation = self.settings.widget_bar_orientation.get(key, "horizontal")
        numeric, safe_min, safe_max, accent = self._widget_value_info(key)
        if orientation == "vertical":
            bar_rect = QRectF(rect.right() - rect.width() * 0.18, rect.y() + rect.height() * 0.12, rect.width() * 0.08, rect.height() * 0.72)
            label_rect = QRectF(rect.x() + rect.width() * 0.08, rect.y() + rect.height() * 0.14, rect.width() * 0.60, rect.height() * 0.18)
            value_rect = QRectF(rect.x() + rect.width() * 0.08, rect.y() + rect.height() * 0.40, rect.width() * 0.60, rect.height() * 0.22)
        else:
            label_rect = QRectF(rect.x() + rect.width() * 0.08, rect.y() + rect.height() * 0.12, rect.width() * 0.84, rect.height() * 0.18)
            value_rect = QRectF(rect.x() + rect.width() * 0.08, rect.y() + rect.height() * 0.34, rect.width() * 0.84, rect.height() * 0.22)
            bar_rect = QRectF(rect.x() + rect.width() * 0.08, rect.bottom() - rect.height() * 0.18, rect.width() * 0.84, rect.height() * 0.08)
        painter.setPen(QColor(self.settings.colors["muted"]))
        painter.setFont(self._fit_font("Arial", labels[key], label_rect, weight=QFont.DemiBold, max_ratio=0.30, min_px=8))
        painter.drawText(label_rect, Qt.AlignLeft | Qt.AlignVCenter, labels[key])
        value_text = values[key]
        painter.setPen(accent)
        painter.setFont(self._fit_font("Arial", value_text, value_rect, max_ratio=0.40, min_px=9))
        painter.drawText(value_rect.adjusted(0, -1, 0, -1), Qt.AlignLeft | Qt.AlignVCenter, value_text)
        if key != "cel":
            frac = 0.0
            if numeric is not None:
                span = max(0.0001, safe_max - safe_min)
                frac = (numeric - safe_min) / span
            self._draw_progress_by_orientation(painter, bar_rect, frac, accent, orientation)


    def _widget_value_info(self, key: str) -> tuple[float | None, float, float, QColor]:
        """
        Resolve a widget key into its current value, label, unit, and range.

        Implementation details:
            Looks up the metric in the current telemetry snapshot and returns display metadata from
            settings.
        """
        bounds = self.settings.widget_thresholds.get(key, {"min": 0.0, "max": 100.0})
        safe_min = float(bounds.get("min", 0.0))
        safe_max = float(bounds.get("max", 100.0))
        palette = {
            "fuel_level": self.settings.colors["fuel"],
            "fuel_consumption": self.settings.colors["fuel"],
            "coolant_temp": self.settings.colors["coolant"],
            "oil_temp": self.settings.colors["text"],
            "throttle_position": self.settings.colors["indicator"],
            "battery_voltage": self.settings.colors["indicator"],
            "cel": self.settings.colors["warning"],
        }
        numeric = {
            "fuel_level": self.snapshot.fuel_level,
            "fuel_consumption": self.snapshot.fuel_consumption_l_100km if self.snapshot.fuel_consumption_l_100km is not None else self.snapshot.fuel_rate_lph,
            "coolant_temp": self.snapshot.coolant_temp_c,
            "oil_temp": self.snapshot.oil_temp_c,
            "throttle_position": self.snapshot.throttle_position,
            "battery_voltage": self.snapshot.battery_voltage,
            "cel": 1.0 if self.snapshot.cel_active else 0.0,
        }.get(key)
        color_key = palette.get(key, self.settings.colors["text"])
        color = QColor(self.settings.colors["warning"] if (numeric is not None and (numeric < safe_min or numeric > safe_max)) else color_key)
        return numeric, safe_min, safe_max, color

    def _draw_progress_by_orientation(self, painter: QPainter, rect: QRectF, frac: float, color: QColor, orientation: str) -> None:
        """
        Draw a progress indicator in the configured orientation.

        Implementation details:
            Uses QPainter primitives and calculated geometry to render the requested overlay or
            shape.
        """
        frac = max(0.0, min(1.0, frac))
        bg = QColor("#102132")
        bg.setAlpha(90)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 4, 4)
        color = QColor(color)
        color.setAlpha(220)
        painter.setBrush(color)
        if orientation == "vertical":
            fill_h = rect.height() * frac
            fill = QRectF(rect.x(), rect.bottom() - fill_h, rect.width(), fill_h)
        else:
            fill = QRectF(rect.x(), rect.y(), rect.width() * frac, rect.height())
        painter.drawRoundedRect(fill, 4, 4)

    def _draw_linear_progress(self, painter: QPainter, rect: QRectF, frac: float, color: QColor) -> None:
        """
        Draw a linear progress bar inside a card widget.

        Implementation details:
            Uses QPainter primitives and calculated geometry to render the requested overlay or
            shape.
        """
        frac = max(0.0, min(1.0, frac))
        bg = QColor("#102132")
        bg.setAlpha(90)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 4, 4)
        fill = QRectF(rect.x(), rect.y(), rect.width() * frac, rect.height())
        color.setAlpha(220)
        painter.setBrush(color)
        painter.drawRoundedRect(fill, 4, 4)

    def _panel(self, painter: QPainter, rect: QRectF, radius: float) -> None:
        """
        Draw a rounded panel background.

        Implementation details:
            Uses current settings, telemetry state, and Qt painting/layout APIs to update the visual
            output.
        """
        if self.settings.widget_locked:
            return
        border = QColor(self.settings.colors["panel_border"])
        border.setAlpha(55)
        painter.setPen(QPen(border, 0.7))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.8, 0.8, -0.8, -0.8), radius, radius)

    def _paint_resize_guides(self, painter: QPainter, rect: QRectF) -> None:
        """
        Draw resize handles for the selected editable widget.

        Implementation details:
            Uses QPainter primitives and current settings/snapshot state to draw the requested
            visual element.
        """
        c = QColor(self.settings.colors["muted"])
        c.setAlpha(150)
        painter.setPen(QPen(c, 1.0))
        d = min(12.0, rect.width() * 0.08, rect.height() * 0.08)
        # corners
        painter.drawLine(rect.left(), rect.top() + d, rect.left(), rect.top())
        painter.drawLine(rect.left(), rect.top(), rect.left() + d, rect.top())
        painter.drawLine(rect.right() - d, rect.top(), rect.right(), rect.top())
        painter.drawLine(rect.right(), rect.top(), rect.right(), rect.top() + d)
        painter.drawLine(rect.left(), rect.bottom() - d, rect.left(), rect.bottom())
        painter.drawLine(rect.left(), rect.bottom(), rect.left() + d, rect.bottom())
        painter.drawLine(rect.right() - d, rect.bottom(), rect.right(), rect.bottom())
        painter.drawLine(rect.right(), rect.bottom() - d, rect.right(), rect.bottom())
        # side midpoints
        mid = 8.0
        painter.drawLine(rect.center().x() - mid, rect.top(), rect.center().x() + mid, rect.top())
        painter.drawLine(rect.center().x() - mid, rect.bottom(), rect.center().x() + mid, rect.bottom())
        painter.drawLine(rect.left(), rect.center().y() - mid, rect.left(), rect.center().y() + mid)
        painter.drawLine(rect.right(), rect.center().y() - mid, rect.right(), rect.center().y() + mid)
