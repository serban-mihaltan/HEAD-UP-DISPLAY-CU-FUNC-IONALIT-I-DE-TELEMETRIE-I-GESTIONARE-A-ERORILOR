from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


DEFAULT_COLORS = {
    "background": "#04070B",
    "panel": "#071421",
    "panel_border": "#16324B",
    "speed": "#F7FBFF",
    "rpm_normal": "#E7EEF7",
    "rpm_redline": "#FF5151",
    "fuel": "#F4C95D",
    "coolant": "#53C6FF",
    "warning": "#FF7B72",
    "text": "#D8E1E8",
    "ticks": "#8AA0B2",
    "indicator": "#00E5FF",
    "muted": "#7C91A5",
}

DEFAULT_WIDGET_VISIBILITY = {
    "fuel_level": True,
    "fuel_consumption": True,
    "coolant_temp": True,
    "oil_temp": False,
    "throttle_position": True,
    "battery_voltage": True,
    "cel": True,
}

DEFAULT_WIDGET_ORDER = [
    "speed",
    "rpm",
    "fuel_level",
    "fuel_consumption",
    "coolant_temp",
    "oil_temp",
    "throttle_position",
    "battery_voltage",
    "cel",
]

DEFAULT_WIDGET_POSITIONS = {
    "speed": {"x": 0.25, "y": 0.18, "w": 0.50, "h": 0.34},
    "rpm": {"x": 0.08, "y": 0.60, "w": 0.84, "h": 0.16},
    "fuel_level": {"x": 0.06, "y": 0.78, "w": 0.16, "h": 0.16},
    "fuel_consumption": {"x": 0.24, "y": 0.78, "w": 0.18, "h": 0.16},
    "coolant_temp": {"x": 0.44, "y": 0.78, "w": 0.16, "h": 0.16},
    "oil_temp": {"x": 0.62, "y": 0.78, "w": 0.16, "h": 0.16},
    "throttle_position": {"x": 0.80, "y": 0.78, "w": 0.16, "h": 0.16},
    "battery_voltage": {"x": 0.74, "y": 0.12, "w": 0.18, "h": 0.14},
    "cel": {"x": 0.08, "y": 0.12, "w": 0.16, "h": 0.12},
}



DEFAULT_WIDGET_BAR_ORIENTATION = {
    "fuel_level": "horizontal",
    "fuel_consumption": "horizontal",
    "coolant_temp": "horizontal",
    "oil_temp": "horizontal",
    "throttle_position": "horizontal",
    "battery_voltage": "horizontal",
    "cel": "horizontal",
}

DEFAULT_WIDGET_THRESHOLDS = {
    "fuel_level": {"min": 15.0, "max": 100.0},
    "fuel_consumption": {"min": 0.0, "max": 20.0},
    "coolant_temp": {"min": 70.0, "max": 105.0},
    "oil_temp": {"min": 70.0, "max": 125.0},
    "throttle_position": {"min": 0.0, "max": 100.0},
    "battery_voltage": {"min": 11.8, "max": 14.8},
    "cel": {"min": 0.0, "max": 0.0},
}

@dataclass(slots=True)
class ConnectionSettings:
    """
    Store adapter connection options for serial, TCP, and auto-connect modes.

    Implementation details:
        Groups related state and behavior behind a typed object used by the rest of the project.
    """
    autodetect: bool = True
    port: str = ""
    baudrate: int = 38400
    protocol: str = "auto"
    fast_mode: bool = False
    poll_interval_ms: int = 120
    auto_connect_enabled: bool = False
    auto_connect_retry_interval_ms: int = 1000
    connection_type: str = "serial"
    tcp_host: str = "127.0.0.1"
    tcp_port: int = 3500
    speed_rpm_only: bool = False

    def resolved_port(self) -> str:
        """Return the port string expected by python-OBD / pyserial."""
        if self.connection_type == "tcp":
            host = (self.tcp_host or "127.0.0.1").strip() or "127.0.0.1"
            port = int(self.tcp_port or 3500)
            return f"socket://{host}:{port}"
        return (self.port or "").strip()


@dataclass(slots=True)
class TelemetrySettings:
    # How often a received OBD snapshot is committed to the telemetry history.
    # This is intentionally separate from connection.poll_interval_ms, which
    # controls how often the adapter is queried.
    """
    Store telemetry graphing, recording, and auto-export preferences.

    Implementation details:
        Groups related state and behavior behind a typed object used by the rest of the project.
    """
    sample_interval_ms: int = 500
    graph_history_seconds: int = 300
    graph_full_session: bool = False
    auto_export_enabled: bool = False
    auto_export_dir: str = ""
    export_format: str = "xlsx"


@dataclass(slots=True)
class AppSettings:
    """
    Store the full HUD configuration used by the UI and service layer.

    Implementation details:
        Groups related state and behavior behind a typed object used by the rest of the project.
    """
    mirrored: bool = False
    fullscreen: bool = False
    ui_scale_percent: int = 100
    max_rpm: int = 8000
    max_speed_kph: int = 280
    redline_rpm: int = 6500
    speed_style: str = "digital"
    rpm_style: str = "digital"
    analog_mode: str = "needle"
    analog_show_value: bool = True
    layout_grid_enabled: bool = True
    layout_grid_size_px: int = 32
    colors: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_COLORS))
    widget_visibility: dict[str, bool] = field(default_factory=lambda: dict(DEFAULT_WIDGET_VISIBILITY))
    widget_order: list[str] = field(default_factory=lambda: list(DEFAULT_WIDGET_ORDER))
    widget_positions: dict[str, dict[str, float]] = field(default_factory=lambda: {k: dict(v) for k, v in DEFAULT_WIDGET_POSITIONS.items()})
    widget_bar_orientation: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_WIDGET_BAR_ORIENTATION))
    widget_thresholds: dict[str, dict[str, float]] = field(default_factory=lambda: {k: dict(v) for k, v in DEFAULT_WIDGET_THRESHOLDS.items()})
    widget_locked: bool = False
    connection: ConnectionSettings = field(default_factory=ConnectionSettings)
    telemetry: TelemetrySettings = field(default_factory=TelemetrySettings)
    preset_names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the settings model into a JSON-serializable dictionary.

        Implementation details:
            Uses dataclass serialization and normalizes enum values for JSON storage.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        """
        Create settings from a dictionary loaded from disk.

        Implementation details:
            Merges stored values with defaults and converts serialized enum strings back to enums.
        """
        connection_data = dict(data.get("connection", {}))
        allowed_connection = {
            "autodetect",
            "port",
            "baudrate",
            "protocol",
            "fast_mode",
            "poll_interval_ms",
            "auto_connect_enabled",
            "auto_connect_retry_interval_ms",
            "connection_type",
            "tcp_host",
            "tcp_port",
            "speed_rpm_only",
        }
        connection_payload = {k: v for k, v in connection_data.items() if k in allowed_connection}
        connection = ConnectionSettings(**connection_payload)
        if str(getattr(connection, "connection_type", "serial")) not in {"serial", "tcp"}:
            connection.connection_type = "serial"
        if str(getattr(connection, "port", "")).strip().startswith("socket://") and not connection_payload.get("connection_type"):
            connection.connection_type = "tcp"
            try:
                target = str(connection.port).strip().removeprefix("socket://")
                host, port_text = target.rsplit(":", 1)
                connection.tcp_host = host or "127.0.0.1"
                connection.tcp_port = int(port_text)
            except Exception:
                connection.tcp_host = "127.0.0.1"
                connection.tcp_port = 3500
        connection.tcp_host = str(getattr(connection, "tcp_host", "127.0.0.1") or "127.0.0.1").strip() or "127.0.0.1"
        try:
            connection.tcp_port = int(max(1, min(65535, int(connection.tcp_port))))
        except Exception:
            connection.tcp_port = 3500
        if connection.connection_type == "tcp":
            connection.autodetect = False
            connection.port = connection.resolved_port()
        try:
            connection.poll_interval_ms = int(max(50, min(5000, int(connection.poll_interval_ms))))
        except Exception:
            connection.poll_interval_ms = 120
        try:
            connection.auto_connect_retry_interval_ms = int(max(250, min(60000, int(connection.auto_connect_retry_interval_ms))))
        except Exception:
            connection.auto_connect_retry_interval_ms = 1000
        connection.auto_connect_enabled = bool(connection.auto_connect_enabled)
        connection.speed_rpm_only = bool(getattr(connection, "speed_rpm_only", False))

        telemetry_data = dict(data.get("telemetry", {}))
        telemetry = TelemetrySettings()
        try:
            telemetry.sample_interval_ms = int(max(100, min(60000, int(telemetry_data.get("sample_interval_ms", telemetry.sample_interval_ms)))))
        except Exception:
            pass
        try:
            telemetry.graph_history_seconds = int(max(30, min(86400, int(telemetry_data.get("graph_history_seconds", telemetry.graph_history_seconds)))))
        except Exception:
            pass
        telemetry.graph_full_session = bool(telemetry_data.get("graph_full_session", telemetry.graph_full_session))
        telemetry.auto_export_enabled = bool(telemetry_data.get("auto_export_enabled", telemetry.auto_export_enabled))
        telemetry.auto_export_dir = str(telemetry_data.get("auto_export_dir", telemetry.auto_export_dir) or "")
        telemetry.export_format = str(telemetry_data.get("export_format", telemetry.export_format) or "xlsx").lower()
        if telemetry.export_format not in {"xlsx", "csv"}:
            telemetry.export_format = "xlsx"

        style = str(data.get("style", "digital"))
        speed_style = str(data.get("speed_style", style if style in {"digital", "analog", "racing"} else "digital"))
        rpm_style = str(data.get("rpm_style", "digital" if style == "semi_analog" else style if style in {"digital", "analog", "racing"} else "digital"))
        if speed_style not in {"digital", "analog"}:
            speed_style = "digital"
        if rpm_style not in {"digital", "analog"}:
            rpm_style = "digital"

        positions = {k: dict(v) for k, v in DEFAULT_WIDGET_POSITIONS.items()}
        for key, raw in dict(data.get("widget_positions", {})).items():
            if key in positions and isinstance(raw, dict):
                for sub in ("x", "y", "w", "h"):
                    if sub in raw:
                        try:
                            positions[key][sub] = float(raw[sub])
                        except Exception:
                            pass

        bar_orientation = dict(DEFAULT_WIDGET_BAR_ORIENTATION)
        for key, value in dict(data.get("widget_bar_orientation", {})).items():
            if key in bar_orientation and str(value) in {"horizontal", "vertical"}:
                bar_orientation[key] = str(value)

        thresholds = {k: dict(v) for k, v in DEFAULT_WIDGET_THRESHOLDS.items()}
        for key, raw in dict(data.get("widget_thresholds", {})).items():
            if key in thresholds and isinstance(raw, dict):
                for sub in ("min", "max"):
                    if sub in raw:
                        try:
                            thresholds[key][sub] = float(raw[sub])
                        except Exception:
                            pass

        widget_order: list[str] = []
        for raw_key in data.get("widget_order", DEFAULT_WIDGET_ORDER):
            key = str(raw_key)
            if key in DEFAULT_WIDGET_ORDER and key not in widget_order:
                widget_order.append(key)
        for key in DEFAULT_WIDGET_ORDER:
            if key not in widget_order:
                widget_order.append(key)

        try:
            layout_grid_size_px = int(max(8, min(160, int(data.get("layout_grid_size_px", 32)))))
        except Exception:
            layout_grid_size_px = 32
        try:
            ui_scale_percent = int(max(70, min(180, int(data.get("ui_scale_percent", 100)))))
        except Exception:
            ui_scale_percent = 100

        return cls(
            mirrored=bool(data.get("mirrored", False)),
            fullscreen=bool(data.get("fullscreen", False)),
            ui_scale_percent=ui_scale_percent,
            max_rpm=int(data.get("max_rpm", 8000)),
            max_speed_kph=int(data.get("max_speed_kph", 280)),
            redline_rpm=int(data.get("redline_rpm", 6500)),
            speed_style=speed_style,
            rpm_style=rpm_style,
            analog_mode=str(data.get("analog_mode", "needle" if str(data.get("analog_mode", "needle")) in {"needle", "arc"} else "needle")),
            analog_show_value=bool(data.get("analog_show_value", True)),
            layout_grid_enabled=bool(data.get("layout_grid_enabled", True)),
            layout_grid_size_px=layout_grid_size_px,
            colors={**DEFAULT_COLORS, **dict(data.get("colors", {}))},
            widget_visibility={**DEFAULT_WIDGET_VISIBILITY, **dict(data.get("widget_visibility", {}))},
            widget_order=widget_order,
            widget_positions=positions,
            widget_bar_orientation=bar_orientation,
            widget_thresholds=thresholds,
            widget_locked=bool(data.get("widget_locked", False)),
            connection=connection,
            telemetry=telemetry,
            preset_names=list(data.get("preset_names", [])),
        )
