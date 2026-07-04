from __future__ import annotations

from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QLabel, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from hud.models.enums import ScreenName
from hud.models.settings import AppSettings
from hud.models.telemetry import TelemetrySnapshot
from hud.services.dtc_service import DtcService
from hud.services.obd_service import TelemetryWorker, get_obd_manager
from hud.services.settings_service import SettingsService
from hud.ui.screens.dtc_screen import DtcScreen
from hud.ui.screens.main_screen import MainScreen
from hud.ui.screens.settings_screen import SettingsScreen
from hud.ui.screens.telemetry_screen import TelemetryScreen
from hud.ui.widgets.top_bar import TopBar


class MainWindow(QMainWindow):
    """
    Coordinate the HUD screens, shared services, connection lifecycle, and telemetry flow.

    Implementation details:
        Creates screens and workers, wires Qt signals, applies settings, and routes OBD operations
        through shared services.
    """
    def __init__(self, settings_service: SettingsService) -> None:
        """
        Handle init behavior for MainWindow.

        Implementation details:
            Uses the object state and supplied arguments to compute and return the required result.
        """
        super().__init__()
        self.settings_service = settings_service
        self.settings = settings_service.settings
        self.telemetry_thread: QThread | None = None
        self.telemetry_worker: TelemetryWorker | None = None
        self._last_snapshot = TelemetrySnapshot(connected=False, source="none")
        self._startup_complete = False
        self.obd_manager = get_obd_manager()
        self.setWindowTitle("Automotive HUD")
        self.resize(1280, 720)

        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.top_bar = TopBar()
        self.stack = QStackedWidget()
        self.main_screen = MainScreen(self.settings)
        self.telemetry_screen = TelemetryScreen(self.settings)
        self.settings_screen = SettingsScreen(self.settings, self._handle_preset_action)
        self.dtc_screen = DtcScreen()
        self.status_label = QLabel("HUD ready - disconnected")
        self.status_label.setStyleSheet("padding:8px 16px;color:#8AA0B2;background:#04070B;")

        self.stack.addWidget(self.main_screen)
        self.stack.addWidget(self.telemetry_screen)
        self.stack.addWidget(self.settings_screen)
        self.stack.addWidget(self.dtc_screen)
        outer.addWidget(self.top_bar)
        outer.addWidget(self.stack, 1)
        outer.addWidget(self.status_label)
        self.setCentralWidget(root)
        self._apply_palette()
        self._wire_events()
        self._apply_settings(self.settings, restart_connection=False)
        self.navigate(ScreenName.MAIN)
        self._handle_telemetry(TelemetrySnapshot(connected=False, source="none"))
        self._startup_complete = True
        if self.settings.connection.auto_connect_enabled:
            QTimer.singleShot(0, self.connect_vehicle)

    def _wire_events(self) -> None:
        """
        Connect UI signals to the handlers that control navigation, settings, and OBD actions.

        Implementation details:
            Uses the object state and supplied arguments to compute and return the required result.
        """
        self.top_bar.mirror_clicked.connect(self.toggle_mirror)
        self.top_bar.telemetry_clicked.connect(self._telemetry_button_route)
        self.top_bar.dtc_clicked.connect(self._dtc_button_route)
        self.top_bar.settings_clicked.connect(self._settings_button_route)
        self.settings_screen.settings_changed.connect(self._apply_settings)
        self.telemetry_screen.settings_changed.connect(self._apply_settings)
        self.settings_screen.telemetry_clicked.connect(lambda: self.navigate(ScreenName.TELEMETRY))
        self.settings_screen.dtc_clicked.connect(lambda: self.navigate(ScreenName.DTC))
        self.settings_screen.connect_clicked.connect(self.connect_vehicle)
        self.settings_screen.disconnect_clicked.connect(self.disconnect_vehicle)
        self.main_screen.layout_changed.connect(self._widget_positions_changed)
        self.dtc_screen.refresh_requested.connect(self.refresh_dtcs)
        self.dtc_screen.clear_all_requested.connect(self.clear_all_dtcs)

    def _widget_positions_changed(self, positions: dict) -> None:
        # Keep every in-memory settings copy synchronized so toggling unrelated
        # controls (for example Lock widgets) does not resurrect stale default
        # widget geometry from an older SettingsScreen snapshot.
        """
        Persist dashboard widget layout changes made on the canvas.

        Implementation details:
            Uses the object state and supplied arguments to compute and return the required result.
        """
        self.settings.widget_positions = {k: dict(v) for k, v in positions.items()}
        self.main_screen.settings.widget_positions = {k: dict(v) for k, v in positions.items()}
        self.settings_screen.settings.widget_positions = {k: dict(v) for k, v in positions.items()}
        self.settings_service.update(self.settings)

    def connect_vehicle(self) -> None:
        """
        Open the configured OBD connection and start live telemetry polling.

        Implementation details:
            Applies settings to the OBD manager, connects, creates a TelemetryWorker, and starts the
            thread.
        """
        self.disconnect_vehicle()
        self.telemetry_thread = QThread(self)
        self.obd_manager.update_settings(self.settings.connection)
        self.telemetry_worker = TelemetryWorker(self.settings.connection)
        self.telemetry_worker.moveToThread(self.telemetry_thread)
        self.telemetry_thread.started.connect(self.telemetry_worker.run)
        self.telemetry_worker.telemetry_ready.connect(self._handle_telemetry)
        self.telemetry_worker.status_changed.connect(self._set_status)
        self.telemetry_worker.finished.connect(self.telemetry_thread.quit)
        self.telemetry_thread.start()

    def disconnect_vehicle(self) -> None:
        """
        Stop telemetry polling and close the current OBD connection.

        Implementation details:
            Stops the worker, waits for it to finish, disconnects the OBD manager, and updates
            status.
        """
        if self.telemetry_worker is not None:
            self.telemetry_worker.stop()
        if self.telemetry_thread is not None:
            self.telemetry_thread.quit()
            self.telemetry_thread.wait(1000)
        self.telemetry_thread = None
        self.telemetry_worker = None
        self.obd_manager.disconnect()
        disconnected = TelemetrySnapshot(connected=False, source="none")
        self._handle_telemetry(disconnected)
        exported_path = self._auto_export_telemetry()
        if exported_path is not None:
            self._set_status(f"HUD ready - disconnected; telemetry exported to {exported_path}")
        else:
            self._set_status("HUD ready - disconnected")

    def navigate(self, screen: ScreenName) -> None:
        """
        Switch the stacked UI to the requested screen.

        Implementation details:
            Maps ScreenName values to stacked-widget pages and updates top-bar selection state.
        """
        self.stack.setCurrentIndex({ScreenName.MAIN: 0, ScreenName.TELEMETRY: 1, ScreenName.SETTINGS: 2, ScreenName.DTC: 3}[screen])
        if screen is ScreenName.TELEMETRY:
            # Force a repaint with the latest background samples when the user
            # opens telemetry after spending time on another screen.
            self.telemetry_screen.update_telemetry(self._last_snapshot)
        self._update_hud_query_context(screen)

    def _handle_telemetry(self, snapshot: TelemetrySnapshot) -> None:
        """
        Process one telemetry sample received from the worker thread.

        Implementation details:
            Stores the sample, updates visible screens, and lets recording/export logic consume it.
        """
        self._last_snapshot = snapshot
        self.main_screen.update_telemetry(snapshot)
        self.telemetry_screen.update_telemetry(snapshot)

    def _telemetry_button_route(self) -> None:
        """
        Route the telemetry navigation button based on the current screen.

        Implementation details:
            Uses the object state and supplied arguments to compute and return the required result.
        """
        if self.stack.currentWidget() is self.telemetry_screen:
            self.navigate(ScreenName.MAIN)
        else:
            self.navigate(ScreenName.TELEMETRY)

    def _dtc_button_route(self) -> None:
        """
        Route the DTC navigation button based on the current screen.

        Implementation details:
            Uses the object state and supplied arguments to compute and return the required result.
        """
        if self.stack.currentWidget() is self.dtc_screen:
            self.navigate(ScreenName.MAIN)
        else:
            self.navigate(ScreenName.DTC)

    def _settings_button_route(self) -> None:
        """
        Route the settings navigation button based on the current screen.

        Implementation details:
            Stores the new value on the object and triggers repaint or downstream updates when
            required.
        """
        current = self.stack.currentWidget()
        if current is self.main_screen:
            self.navigate(ScreenName.SETTINGS)
        elif current is self.settings_screen:
            self.navigate(ScreenName.MAIN)
        else:
            self.navigate(ScreenName.SETTINGS)

    def _apply_settings(self, settings: AppSettings, restart_connection: bool = False) -> None:
        """
        Apply newly edited settings to the UI and runtime services.

        Implementation details:
            Copies the settings into each screen, updates service configuration, and restarts the
            connection when needed.
        """
        old_connection = self._connection_runtime_signature(self.settings)
        self.settings = settings
        self.settings_service.update(settings)
        self.main_screen.apply_settings(settings)
        self.telemetry_screen.apply_settings(settings)
        self.settings_screen.load_from_settings(settings)
        self._apply_ui_scale()
        self._apply_palette()
        self._update_hud_query_context()
        if settings.fullscreen and not self.isFullScreen():
            self.showFullScreen()
        elif not settings.fullscreen and self.isFullScreen():
            self.showNormal()

        connection_changed = old_connection != self._connection_runtime_signature(settings)
        if self._startup_complete:
            if restart_connection:
                self.connect_vehicle()
            elif connection_changed and self.telemetry_worker is not None:
                self._set_status("Connection settings changed; reconnect to apply them")
            elif settings.connection.auto_connect_enabled and self.telemetry_worker is None:
                self.connect_vehicle()

    @staticmethod
    def _connection_runtime_signature(settings: AppSettings) -> tuple:
        """
        Build a comparable signature for connection-affecting settings.

        Implementation details:
            Registers callbacks/signals and updates service state for the active connection.
        """
        conn = settings.connection
        return (
            conn.autodetect,
            conn.port,
            conn.baudrate,
            conn.protocol,
            conn.fast_mode,
            conn.poll_interval_ms,
            conn.auto_connect_enabled,
            conn.auto_connect_retry_interval_ms,
            getattr(conn, "connection_type", "serial"),
            getattr(conn, "tcp_host", "127.0.0.1"),
            getattr(conn, "tcp_port", 3500),
        )

    def _update_hud_query_context(self, screen: ScreenName | None = None) -> None:
        """
        Tell the OBD manager which telemetry fields are currently visible on the HUD.

        Implementation details:
            Copies incoming state into the widget/service and refreshes dependent output.
        """
        if screen is None:
            current = self.stack.currentWidget()
            if current is self.dtc_screen:
                screen = ScreenName.DTC
            elif current is self.settings_screen:
                screen = ScreenName.SETTINGS
            elif current is self.telemetry_screen:
                screen = ScreenName.TELEMETRY
            else:
                screen = ScreenName.MAIN

        # Do not keep the live PID loop running while the DTC/service screen is
        # visible. DTC commands are still serialized with exclusive_session(), but
        # stopping telemetry here avoids immediate 010D/010C/etc. traffic before
        # and after Mode 03/07/0A reads and makes the emulator log unambiguous.
        if screen is ScreenName.DTC:
            self.obd_manager.set_hud_context(False, set())
            return

        # Telemetry history should be built continuously while the main HUD or
        # telemetry page is visible.
        keys = self._all_live_query_keys()
        if bool(getattr(self.settings.connection, "speed_rpm_only", False)):
            keys = {"speed", "rpm"}
        self.obd_manager.set_hud_context(True, keys)

    @staticmethod
    def _all_live_query_keys() -> set[str]:
        """
        Return every telemetry query key used by the live dashboard widgets.

        Implementation details:
            Uses the object state and supplied arguments to compute and return the required result.
        """
        return {
            "speed",
            "rpm",
            "fuel_level",
            "fuel_consumption",
            "coolant_temp",
            "oil_temp",
            "throttle_position",
            "battery_voltage",
            "cel",
        }

    def _apply_ui_scale(self) -> None:
        """Apply the menu scale setting to non-HUD controls."""
        scale_percent = int(max(70, min(180, getattr(self.settings, "ui_scale_percent", 100))))
        self.settings_screen.apply_ui_scale(scale_percent)
        self.dtc_screen.apply_ui_scale(scale_percent)
        colors = self.settings.colors
        self.status_label.setStyleSheet(
            f"padding:{max(6, int(round(8 * scale_percent / 100)))}px {max(12, int(round(16 * scale_percent / 100)))}px;"
            f"font-size:{max(10, int(round(12 * scale_percent / 100)))}px;"
            f"color:{colors.get('muted', colors.get('ticks', '#8AA0B2'))};background:{colors.get('background', '#04070B')};"
        )

    def _apply_palette(self) -> None:
        """
        Apply the selected theme colors to top-level widgets.

        Implementation details:
            Uses the object state and supplied arguments to compute and return the required result.
        """
        bg = self.settings.colors["background"]
        panel = self.settings.colors["panel"]
        text = self.settings.colors["text"]
        border = self.settings.colors["panel_border"]
        muted = self.settings.colors.get("muted", self.settings.colors.get("ticks", text))
        scale = max(0.70, min(1.80, float(getattr(self.settings, "ui_scale_percent", 100)) / 100.0))
        font_px = max(10, int(round(12 * scale)))
        pad_v = max(6, int(round(8 * scale)))
        pad_h = max(10, int(round(12 * scale)))
        radius = max(8, int(round(10 * scale)))
        self.setStyleSheet(
            f"QMainWindow, QWidget{{background:{bg};color:{text};font-size:{font_px}px;}}"
            f"QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget, QScrollArea, QGroupBox{{background:{panel};color:{text};border:1px solid {border};font-size:{font_px}px;}}"
            f"QPushButton{{background:{panel};color:{text};border:1px solid {border};padding:{pad_v}px {pad_h}px;border-radius:{radius}px;font-size:{font_px}px;}}"
            f"QPushButton:hover{{background:{panel};}}"
            f"QCheckBox{{spacing:8px;color:{text};}}"
            f"QTabWidget::pane{{background:{bg};border:1px solid {border};}}"
            f"QTabBar::tab{{background:{panel};color:{text};padding:9px 16px;border:1px solid {border};border-bottom:none;border-top-left-radius:8px;border-top-right-radius:8px;}}"
            f"QTabBar::tab:selected{{background:{panel};color:{text};}}"
            f"QTabBar::tab:!selected{{background:{bg};color:{muted};}}"
            f"QTabBar::tab:hover{{background:{panel};color:{text};}}"
        )
        self.status_label.setStyleSheet(
            f"padding:{max(6, int(round(8 * scale * 100 / 100)))}px {max(12, int(round(16 * scale * 100 / 100)))}px;"
            f"font-size:{font_px}px;color:{muted};background:{bg};"
        )
        if hasattr(self.top_bar, "apply_palette"):
            self.top_bar.apply_palette(self.settings.colors)
        if hasattr(self.settings_screen, "apply_palette"):
            self.settings_screen.apply_palette(self.settings.colors)
        if hasattr(self.telemetry_screen, "apply_palette"):
            self.telemetry_screen.apply_palette(self.settings.colors)
        if hasattr(self.dtc_screen, "apply_palette"):
            self.dtc_screen.apply_palette(self.settings.colors)

    def toggle_mirror(self) -> None:
        """
        Toggle mirrored rendering for HUD windscreen reflection use.

        Implementation details:
            Inverts the current state and reapplies the affected view settings.
        """
        self.settings.mirrored = not self.settings.mirrored
        self._apply_settings(self.settings)

    def refresh_dtcs(self) -> None:
        """
        Read DTCs from the active vehicle connection and update the DTC screen.

        Implementation details:
            Pauses telemetry through the DTC service, reads all categories, and populates the DTC
            table.
        """
        self.dtc_screen.set_status("Reading DTCs…")
        try:
            service = DtcService(self.settings.connection)
            entries = service.read_all()
        except Exception as exc:
            self.dtc_screen.set_entries([])
            self.dtc_screen.set_status(f"DTC read failed: {exc}")
            return

        self.dtc_screen.set_entries(entries)
        if entries:
            self.dtc_screen.set_status(f"Loaded {len(entries)} DTC(s).")
        elif self.obd_manager.is_connected():
            self.dtc_screen.set_status("No DTCs found.")
        else:
            self.dtc_screen.set_status("No active OBD connection. Connect the adapter first.")

    def clear_all_dtcs(self) -> None:
        """
        Clear all DTCs through the DTC service and refresh the DTC display.

        Implementation details:
            Uses the shared DTC service, handles success/failure status, and refreshes the visible
            list.
        """
        self.dtc_screen.set_status("Clearing DTCs…")
        try:
            service = DtcService(self.settings.connection)
            ok, message = service.clear_all()
        except Exception as exc:
            self.dtc_screen.set_status(f"DTC clear failed: {exc}")
            return

        if not ok:
            self.dtc_screen.set_status(message)
            return

        # Keep the Mode 04 acknowledgement visible instead of immediately
        # overwriting it with the refresh result.
        try:
            entries = service.read_all()
        except Exception as exc:
            self.dtc_screen.set_status(f"{message} Follow-up read failed: {exc}")
            return

        self.dtc_screen.set_entries(entries)
        if entries:
            self.dtc_screen.set_status(f"{message} {len(entries)} DTC(s) still present.")
        else:
            self.dtc_screen.set_status(f"{message} No DTCs found.")


    def _handle_preset_action(self, action: str, value: str | None):
        """
        Run the requested preset save, load, or delete operation.

        Implementation details:
            Uses the object state and supplied arguments to compute and return the required result.
        """
        if action == "save" and value:
            self.settings_service.save_preset(value, self.settings)
            return None
        if action == "load" and value:
            loaded = self.settings_service.load_preset(value)
            self.settings = loaded
            self.main_screen.apply_settings(loaded)
            return loaded
        if action == "delete" and value:
            self.settings_service.delete_preset(value)
            return None
        if action == "list":
            return self.settings_service.list_presets()
        return None

    def _set_status(self, text: str) -> None:
        """
        Display connection or action status in the top bar.

        Implementation details:
            Stores the new value on the object and triggers repaint or downstream updates when
            required.
        """
        self.status_label.setText(text)

    def _auto_export_telemetry(self):
        """
        Write telemetry history automatically when auto-export is enabled.

        Implementation details:
            Uses the object state and supplied arguments to compute and return the required result.
        """
        path = self.telemetry_screen.auto_export(self.settings_service.base_dir)
        if path is not None:
            self._set_status(f"Telemetry exported to {path}")
        return path

    def closeEvent(self, event) -> None:  # noqa: N802
        """
        Cleanly shut down services before the main window closes.

        Implementation details:
            Runs auto-export if required, stops telemetry, disconnects OBD, and then accepts the Qt
            close event.
        """
        self.disconnect_vehicle()
        super().closeEvent(event)
