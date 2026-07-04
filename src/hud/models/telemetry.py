from __future__ import annotations

from dataclasses import dataclass, field
from time import time


@dataclass(slots=True)
class TelemetrySnapshot:
    """
    Store one sampled set of live vehicle telemetry values.

    Implementation details:
        Groups related state and behavior behind a typed object used by the rest of the project.
    """
    speed_kph: float = 0.0
    rpm: float = 0.0
    fuel_level: float | None = None
    coolant_temp_c: float | None = None
    oil_temp_c: float | None = None
    throttle_position: float | None = None
    fuel_rate_lph: float | None = None
    fuel_consumption_l_100km: float | None = None
    battery_voltage: float | None = None
    cel_active: bool = False
    connected: bool = False
    source: str = "none"
    timestamp: float = field(default_factory=time)
