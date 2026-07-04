from __future__ import annotations

from enum import Enum


class DashboardStyle(str, Enum):
    """
    Enumerate the available dashboard cluster rendering styles.

    Implementation details:
        Groups related state and behavior behind a typed object used by the rest of the project.
    """
    DIGITAL = "digital"
    SEMI_ANALOG = "semi_analog"
    ANALOG = "analog"
    RACING = "racing"


class ScreenName(str, Enum):
    """
    Enumerate the application screens used by the main window router.

    Implementation details:
        Groups related state and behavior behind a typed object used by the rest of the project.
    """
    MAIN = "main"
    TELEMETRY = "telemetry"
    SETTINGS = "settings"
    DTC = "dtc"


class DtcCategory(str, Enum):
    """
    Enumerate the supported DTC groups read from OBD-II service modes.

    Implementation details:
        Groups related state and behavior behind a typed object used by the rest of the project.
    """
    STORED = "stored"
    PENDING = "pending"
    PERMANENT = "permanent"
    ACTIVE = "active"
    UNKNOWN = "unknown"
