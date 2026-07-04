"""Shared OBD connection manager and telemetry worker."""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import replace
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from hud.models.telemetry import TelemetrySnapshot

try:
    import obd  # type: ignore
except Exception:  # pragma: no cover
    obd = None


class SharedOBDManager:
    """Own the process-wide adapter connection and serialize OBD traffic."""

    def __init__(self) -> None:
        """
        Create the shared connection state used by telemetry and diagnostic services.

        Implementation details:
            Initializes the adapter lock, connection cache, telemetry pause flag, service-active
            flag, and the default set of HUD widgets that may request PIDs.
        """
        self._lock = threading.RLock()
        self._connection = None
        self._settings = None
        self._telemetry_paused = threading.Event()
        self._service_active = threading.Event()
        self._hud_active = True
        self._visible_widgets: set[str] = {"speed", "rpm", "fuel_level", "fuel_consumption", "coolant_temp", "oil_temp", "throttle_position", "battery_voltage", "cel"}

    def update_settings(self, connection_settings: Any) -> None:
        """
        Store the latest OBD connection settings.

        Implementation details:
            Keeps a reference to the settings object so subsequent connection reuse checks and
            workers operate against the same configuration.
        """
        self._settings = connection_settings

    def _same_settings(self, connection_settings: Any) -> bool:
        """
        Check whether a new connection request can reuse the current adapter.

        Implementation details:
            Compares the connection-critical settings fields and ignores unrelated UI settings that
            do not require reconnecting.
        """
        old = self._settings
        if old is None:
            return False
        attrs = ("autodetect", "port", "baudrate", "protocol", "fast_mode", "connection_type", "tcp_host", "tcp_port")
        return all(getattr(old, a, None) == getattr(connection_settings, a, None) for a in attrs)

    def connect(self, connection_settings: Any) -> tuple[bool, str]:
        """
        Open or reuse the python-OBD adapter connection.

        Implementation details:
            Serializes connection work with the shared lock, reuses a compatible live connection,
            creates an autodetected or explicit-port connection, and validates the resulting status.
        """
        if obd is None:
            return False, "python-OBD not installed"
        with self._lock:
            if self._connection is not None and self._same_settings(connection_settings):
                if self.is_connected():
                    self._settings = connection_settings
                    return True, "Connected to ELM327"
                self._close_locked()
            self._settings = connection_settings
            try:
                # Keep the serial/TCP path identical from python-OBD's point of view: both
                # ultimately receive a port string.  Serial ports are COMx/tty/rfcomm values,
                # while TCP/IP adapters use pyserial's socket://host:port URL handler.
                kwargs = {"fast": connection_settings.fast_mode}

                # Older ISO/K-line vehicles and inexpensive ELM327 clones often need a longer
                # response window than modern CAN adapters.  In Speed/RPM-only mode, stability is
                # preferred over maximum refresh rate.
                kwargs["timeout"] = 2.0 if bool(getattr(connection_settings, "speed_rpm_only", False)) else 1.0

                protocol = str(getattr(connection_settings, "protocol", "auto") or "auto").strip()
                if protocol and protocol.lower() != "auto":
                    kwargs["protocol"] = protocol

                port = self._resolved_port(connection_settings)
                if getattr(connection_settings, "connection_type", "serial") == "tcp":
                    conn = obd.OBD(portstr=port, **kwargs)
                elif connection_settings.autodetect and not port:
                    conn = obd.OBD(**kwargs)
                else:
                    conn = obd.OBD(portstr=(port or None), baudrate=connection_settings.baudrate, **kwargs)
                if conn is None:
                    self._connection = None
                    return False, "Disconnected"
                self._connection = conn
                if not self.is_connected():
                    self._close_locked()
                    return False, "Disconnected"
                return True, "Connected to ELM327"
            except Exception as exc:
                self._connection = None
                return False, f"Connect error: {exc}"

    @staticmethod
    def _resolved_port(connection_settings: Any) -> str:
        """Return the connection target to pass into python-OBD."""
        resolver = getattr(connection_settings, "resolved_port", None)
        if callable(resolver):
            return str(resolver() or "").strip()
        if getattr(connection_settings, "connection_type", "serial") == "tcp":
            host = str(getattr(connection_settings, "tcp_host", "127.0.0.1") or "127.0.0.1").strip()
            port = int(getattr(connection_settings, "tcp_port", 3500) or 3500)
            return f"socket://{host}:{port}"
        return str(getattr(connection_settings, "port", "") or "").strip()

    def disconnect(self) -> None:
        """
        Close the current adapter connection from public callers.

        Implementation details:
            Acquires the shared lock before delegating to the locked close helper so no telemetry
            query can run while the connection is being torn down.
        """
        with self._lock:
            self._close_locked()

    def _close_locked(self) -> None:
        """
        Close the cached adapter connection while the caller owns the lock.

        Implementation details:
            Attempts a best-effort close and always clears the cached connection reference even if
            the adapter close call raises.
        """
        if self._connection is not None:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None

    def is_connected(self) -> bool:
        """
        Report whether the cached python-OBD connection is ready for queries.

        Implementation details:
            Rejects missing connections, missing python-OBD, disconnected statuses, and exception-
            throwing status checks.
        """
        conn = self._connection
        if conn is None or obd is None:
            return False
        try:
            status = conn.status()
            # Do not treat ELM_CONNECTED as a hard failure. Some cheap USB/CH340
            # adapters and older ISO/K-line vehicles can temporarily report that
            # state even though the serial adapter is still usable. Individual PID
            # queries are still allowed to return None/NO DATA.
            if hasattr(obd, "OBDStatus") and status == obd.OBDStatus.NOT_CONNECTED:
                return False
        except Exception:
            return False
        return True

    def set_telemetry_paused(self, paused: bool) -> None:
        """
        Pause or resume background telemetry polling.

        Implementation details:
            Sets or clears the telemetry pause event that the worker checks before sending regular
            PID requests.
        """
        if paused:
            self._telemetry_paused.set()
        else:
            self._telemetry_paused.clear()

    def telemetry_paused(self) -> bool:
        """
        Return whether background telemetry polling is currently paused.

        Implementation details:
            Reads the pause event state without modifying any connection or worker state.
        """
        return self._telemetry_paused.is_set()

    def set_hud_context(self, hud_active: bool, visible_widgets: set[str] | None = None) -> None:
        """
        Update which HUD widgets are allowed to drive live PID polling.

        Implementation details:
            Stores the HUD-active flag and visible widget keys under the shared lock so the
            telemetry worker sees a consistent polling context.
        """
        with self._lock:
            self._hud_active = bool(hud_active)
            self._visible_widgets = set(visible_widgets or set())

    def hud_active(self) -> bool:
        """
        Return whether the main HUD is currently requesting live telemetry.

        Implementation details:
            Reads the HUD-active flag under the shared lock to avoid races with screen/context
            changes.
        """
        with self._lock:
            return self._hud_active

    def should_query_widget(self, key: str) -> bool:
        """
        Decide whether a telemetry PID should be queried for a widget.

        Implementation details:
            Checks both that the HUD is active and that the widget key is in the visible widget set,
            reducing unnecessary OBD traffic.
        """
        with self._lock:
            return self._hud_active and key in self._visible_widgets

    def query(self, command: Any, force: bool = True):
        """
        Execute a normal telemetry query when diagnostics are not using the adapter.

        Implementation details:
            Rejects queries during service sessions, validates connection state under the shared
            lock, and suppresses adapter exceptions by returning None.
        """
        if command is None or self._service_active.is_set():
            return None
        with self._lock:
            if self._service_active.is_set() or not self.is_connected() or self._connection is None:
                return None
            try:
                return self._connection.query(command, force=force)
            except Exception:
                return None

    @contextmanager
    def exclusive_session(self):
        """
        Reserve the adapter for a diagnostic/service operation.

        Implementation details:
            Marks service traffic active, pauses telemetry, waits briefly for the polling loop to
            observe the pause, holds the shared lock for the caller, then restores normal polling in
            a finally block.
        """
        self._service_active.set()
        self.set_telemetry_paused(True)
        time.sleep(0.05)
        self._lock.acquire()
        try:
            yield self._connection if self.is_connected() else None
        finally:
            self._lock.release()
            self._service_active.clear()
            self.set_telemetry_paused(False)


_SHARED_MANAGER = SharedOBDManager()


def get_obd_manager() -> SharedOBDManager:
    """
    Return the process-wide shared OBD manager.

    Implementation details:
        Exposes the singleton manager so telemetry, DTC, and UI code coordinate through the same
        connection and lock.
    """
    return _SHARED_MANAGER


class TelemetryWorker(QObject):
    """Background worker that connects to the adapter and publishes telemetry."""

    telemetry_ready = Signal(object)
    status_changed = Signal(str)
    finished = Signal()

    def __init__(self, connection_settings: Any) -> None:
        """
        Create a telemetry worker for one set of connection settings.

        Implementation details:
            Stores the settings, initializes worker state, and updates the shared manager before the
            worker thread starts connecting.
        """
        super().__init__()
        self.connection_settings = connection_settings
        self._running = False
        self._manager = get_obd_manager()
        self._manager.update_settings(connection_settings)

    @Slot()
    def run(self) -> None:
        """
        Connect to the adapter and run the polling loop.

        Implementation details:
            Attempts connection, emits status and disconnected snapshots, runs telemetry polling
            while connected, and optionally retries according to the auto-connect settings.
        """
        self._running = True
        auto_connect = bool(getattr(self.connection_settings, "auto_connect_enabled", False))
        retry_s = max(0.25, float(getattr(self.connection_settings, "auto_connect_retry_interval_ms", 1000)) / 1000.0)

        while self._running:
            ok, message = self._manager.connect(self.connection_settings)
            if ok:
                self.status_changed.emit(message)
                self._poll_real()
                if not auto_connect or not self._running:
                    break
                self._manager.disconnect()
                self.status_changed.emit(f"OBD disconnected; retrying in {retry_s:g}s")
            else:
                self.status_changed.emit(message)
                self.telemetry_ready.emit(TelemetrySnapshot(connected=False, source="none"))
                if not auto_connect:
                    break
                self.status_changed.emit(f"Auto-connect: {message}; retrying in {retry_s:g}s")

            deadline = time.monotonic() + retry_s
            while self._running and time.monotonic() < deadline:
                time.sleep(min(0.10, max(0.0, deadline - time.monotonic())))

        self.finished.emit()

    def stop(self) -> None:
        """
        Request the telemetry worker to stop.

        Implementation details:
            Clears the running flag and unpauses telemetry so a stopped worker cannot leave the
            shared manager in a paused state.
        """
        self._running = False
        self._manager.set_telemetry_paused(False)

    def _poll_real(self) -> None:
        """
        Poll active telemetry PIDs and publish snapshots.

        Implementation details:
            Builds command objects, skips polling while paused or disconnected, queries only visible
            widgets, refreshes slow-changing values on a slower cadence, and emits immutable
            snapshot copies.
        """
        cmds = self._build_commands()
        sleep_s = max(0.10, self.connection_settings.poll_interval_ms / 1000.0)
        slow_interval_s = 1.0
        last_slow_poll = 0.0
        latest_snapshot = TelemetrySnapshot(connected=True, source="obd")
        speed_rpm_only = bool(getattr(self.connection_settings, "speed_rpm_only", False))

        while self._running:
            if self._manager.telemetry_paused():
                time.sleep(0.05)
                continue
            if not self._manager.is_connected():
                self.status_changed.emit("OBD disconnected")
                self.telemetry_ready.emit(TelemetrySnapshot(connected=False, source="none"))
                break
            if not self._manager.hud_active():
                time.sleep(0.10)
                continue
            try:
                latest_snapshot.connected = True
                latest_snapshot.source = "obd"

                speed = latest_snapshot.speed_kph
                if self._manager.should_query_widget("speed") or speed_rpm_only:
                    speed = float(self._safe_query(cmds.get("SPEED"), "km/h") or 0.0)
                    latest_snapshot.speed_kph = speed
                else:
                    latest_snapshot.speed_kph = 0.0
                    speed = 0.0

                if self._manager.should_query_widget("rpm") or speed_rpm_only:
                    latest_snapshot.rpm = float(self._safe_query(cmds.get("RPM")) or 0.0)
                else:
                    latest_snapshot.rpm = 0.0

                if not speed_rpm_only and self._manager.should_query_widget("throttle_position"):
                    latest_snapshot.throttle_position = self._maybe_float(self._safe_query(cmds.get("THROTTLE_POS")))
                else:
                    latest_snapshot.throttle_position = None

                if not speed_rpm_only and self._manager.should_query_widget("fuel_consumption"):
                    fuel_lph = self._maybe_float(self._safe_query(cmds.get("FUEL_RATE"), "liter/hour"))
                    if fuel_lph is None:
                        maf_gps = self._maybe_float(self._safe_query(cmds.get("MAF"), "gram/second"))
                        fuel_lph = self._estimate_fuel_rate_lph_from_maf(maf_gps)
                    latest_snapshot.fuel_rate_lph = fuel_lph
                    latest_snapshot.fuel_consumption_l_100km = self._fuel_l_100km(fuel_lph, speed)
                else:
                    latest_snapshot.fuel_rate_lph = None
                    latest_snapshot.fuel_consumption_l_100km = None

                now = time.monotonic()
                if speed_rpm_only:
                    latest_snapshot.fuel_level = None
                    latest_snapshot.coolant_temp_c = None
                    latest_snapshot.oil_temp_c = None
                    latest_snapshot.battery_voltage = None
                    latest_snapshot.cel_active = False
                    last_slow_poll = now
                elif now - last_slow_poll >= slow_interval_s:
                    if self._manager.should_query_widget("fuel_level"):
                        latest_snapshot.fuel_level = self._maybe_float(self._safe_query(cmds.get("FUEL_LEVEL")))
                    else:
                        latest_snapshot.fuel_level = None

                    if self._manager.should_query_widget("coolant_temp"):
                        latest_snapshot.coolant_temp_c = self._maybe_float(self._safe_query(cmds.get("COOLANT_TEMP"), "degC"))
                    else:
                        latest_snapshot.coolant_temp_c = None

                    if self._manager.should_query_widget("oil_temp"):
                        oil_temp = self._safe_query(cmds.get("OIL_TEMP"), "degC")
                        if oil_temp is None:
                            oil_temp = self._safe_query(cmds.get("ENGINE_OIL_TEMP"), "degC")
                        latest_snapshot.oil_temp_c = self._maybe_float(oil_temp)
                    else:
                        latest_snapshot.oil_temp_c = None

                    if self._manager.should_query_widget("battery_voltage"):
                        voltage = self._safe_query(cmds.get("CONTROL_MODULE_VOLTAGE"))
                        if voltage is None:
                            voltage = self._safe_query(cmds.get("ELM_VOLTAGE"))
                        latest_snapshot.battery_voltage = self._maybe_float(voltage)
                    else:
                        latest_snapshot.battery_voltage = None

                    if self._manager.should_query_widget("cel"):
                        status_value = self._safe_query(cmds.get("STATUS"))
                        if isinstance(status_value, str):
                            latest_snapshot.cel_active = "MIL" in status_value.upper() or "ON" in status_value.upper()
                        elif status_value is None:
                            latest_snapshot.cel_active = False
                    else:
                        latest_snapshot.cel_active = False

                    last_slow_poll = now

                self.telemetry_ready.emit(replace(latest_snapshot, timestamp=time.time()))
                self.status_changed.emit("OBD connected")
            except Exception as exc:
                self.status_changed.emit(f"Polling stopped: {exc}")
                self.telemetry_ready.emit(TelemetrySnapshot(connected=False, source="none"))
                break
            time.sleep(sleep_s)

    def _build_commands(self) -> dict[str, Any]:
        """
        Build the python-OBD command lookup used by the polling loop.

        Implementation details:
            Reads named command objects from obd.commands and returns None for commands unavailable
            in the installed python-OBD version.
        """
        command_table = getattr(obd, "commands", object()) if obd is not None else object()
        names = [
            "SPEED",
            "RPM",
            "FUEL_LEVEL",
            "FUEL_RATE",
            "MAF",
            "THROTTLE_POS",
            "COOLANT_TEMP",
            "OIL_TEMP",
            "ENGINE_OIL_TEMP",
            "CONTROL_MODULE_VOLTAGE",
            "ELM_VOLTAGE",
            "STATUS",
        ]
        return {name: getattr(command_table, name, None) for name in names}

    def _safe_query(self, command: Any, unit: str | None = None) -> float | str | None:
        """
        Query one PID and normalize the response value.

        Implementation details:
            Delegates to the shared manager, handles null responses, optionally converts units, and
            returns a float when possible or a string fallback otherwise.
        """
        response = self._manager.query(command, force=True)
        if response is None or response.is_null():
            return None
        value = response.value
        if unit and hasattr(value, "to"):
            try:
                value = value.to(unit)
            except Exception:
                pass
        if hasattr(value, "magnitude"):
            return float(value.magnitude)
        try:
            return float(value)
        except Exception:
            return str(value)

    @staticmethod
    def _estimate_fuel_rate_lph_from_maf(maf_gps: float | None) -> float | None:
        """
        Estimate fuel consumption rate when the direct fuel-rate PID is unavailable.

        Implementation details:
            Converts MAF from grams per second to litres per hour using a petrol stoichiometric AFR
            and density approximation, returning None for invalid inputs.
        """
        if maf_gps is None or maf_gps < 0:
            return None
        return maf_gps * 3600.0 / (14.7 * 745.0)

    @staticmethod
    def _fuel_l_100km(fuel_lph: float | None, speed_kph: float) -> float | None:
        """
        Convert fuel rate and speed into litres per 100 km.

        Implementation details:
            Rejects invalid fuel rates and near-stationary speeds, then applies the standard l/h to
            l/100km calculation.
        """
        if fuel_lph is None or fuel_lph < 0:
            return None
        if speed_kph <= 2.0:
            return None
        return fuel_lph * 100.0 / speed_kph

    @staticmethod
    def _maybe_float(value: float | str | None) -> float | None:
        """
        Convert optional values to floats for telemetry fields.

        Implementation details:
            Returns None for missing or unparseable values and otherwise uses Python float
            conversion.
        """
        try:
            return None if value is None else float(value)
        except Exception:
            return None
