from __future__ import annotations

from copy import deepcopy

try:
    from serial.tools import list_ports
except Exception:  # pragma: no cover
    list_ports = None

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from hud.models.settings import AppSettings, DEFAULT_WIDGET_ORDER


class SettingsScreen(QWidget):
    """
    Build and manage the configuration interface for the HUD application.

    Implementation details:
        Composes tabbed Qt widgets, loads values from AppSettings, and emits structured settings
        changes back to the main window.
    """
    settings_changed = Signal(object)
    dtc_clicked = Signal()
    telemetry_clicked = Signal()
    connect_clicked = Signal()
    disconnect_clicked = Signal()

    WIDGET_LABELS = {
        "fuel_level": "Remaining fuel",
        "fuel_consumption": "Fuel consumption",
        "coolant_temp": "Coolant temperature",
        "oil_temp": "Oil temperature",
        "throttle_position": "Throttle position",
        "battery_voltage": "Battery voltage",
        "cel": "Check engine lamp",
    }

    COLOR_KEYS = [
        "background",
        "panel",
        "panel_border",
        "speed",
        "rpm_normal",
        "rpm_redline",
        "fuel",
        "coolant",
        "warning",
        "text",
        "ticks",
        "indicator",
        "muted",
    ]

    def __init__(self, settings: AppSettings, preset_provider) -> None:
        """
        Handle init behavior for SettingsScreen.

        Implementation details:
            Reads or updates Qt widgets and emits signals so the main window can keep application
            state synchronized.
        """
        super().__init__()
        self.settings = deepcopy(settings)
        self.preset_provider = preset_provider
        self._loading = False
        self._active_colors = dict(self.settings.colors)
        self._group_style = self._build_group_style(self._active_colors)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(24, 20, 24, 12)
        self.title = QLabel("Settings")
        title = self.title
        title.setStyleSheet("font-size:24px;font-weight:700;color:#D8E1E8;")
        self.apply_button = QPushButton("Apply")
        self.telemetry_button = QPushButton("Telemetry")
        self.dtc_button = QPushButton("DTC Screen")
        self.scale_minus_button = QPushButton("−")
        self.scale_minus_button.setToolTip("Decrease menu size")
        self.scale_plus_button = QPushButton("+")
        self.scale_plus_button.setToolTip("Increase menu size")
        self.scale_label = QLabel("100%")
        self.scale_label.setStyleSheet("color:#8AA0B2;")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(QLabel("Menu size"))
        header.addWidget(self.scale_minus_button)
        header.addWidget(self.scale_label)
        header.addWidget(self.scale_plus_button)
        header.addWidget(self.apply_button)
        header.addWidget(self.telemetry_button)
        header.addWidget(self.dtc_button)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self._apply_palette_styles()
        self.tabs.addTab(self._build_cluster_tab(), "Cluster")
        self.tabs.addTab(self._build_widgets_tab(), "Live widgets")
        self.tabs.addTab(self._build_telemetry_tab(), "Telemetry")
        self.tabs.addTab(self._build_connection_tab(), "Connection")
        self.tabs.addTab(self._build_colors_tab(), "Colors")
        self.tabs.addTab(self._build_presets_tab(), "Presets")
        root.addWidget(self.tabs, 1)

        self.apply_button.clicked.connect(self.emit_settings)
        self.scale_minus_button.clicked.connect(lambda: self.adjust_ui_scale(-10))
        self.scale_plus_button.clicked.connect(lambda: self.adjust_ui_scale(10))
        self.telemetry_button.clicked.connect(self.telemetry_clicked)
        self.dtc_button.clicked.connect(self.dtc_clicked)
        self.connect_button.clicked.connect(self.connect_clicked)
        self.disconnect_button.clicked.connect(self.disconnect_clicked)
        self.save_preset_button.clicked.connect(self.save_preset)
        self.load_preset_button.clicked.connect(self.load_preset)
        self.delete_preset_button.clicked.connect(self.delete_preset)
        self.browse_auto_export_dir.clicked.connect(self.pick_auto_export_dir)

        self._connect_change_signals()
        self.load_from_settings(settings)


    def _color(self, key: str, fallback: str) -> str:
        """Return a safe palette color value."""
        return str(self._active_colors.get(key) or fallback)

    def _build_group_style(self, colors: dict[str, str]) -> str:
        text = str(colors.get("text") or "#D8E1E8")
        border = str(colors.get("panel_border") or "#16324B")
        return (
            f"QGroupBox{{color:{text};border:1px solid {border};border-radius:12px;"
            "margin-top:8px;padding-top:16px;}"
            "QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 6px;}"
        )

    def apply_palette(self, colors: dict[str, str]) -> None:
        """Apply the current HUD palette to Settings-specific styled widgets."""
        self._active_colors = dict(colors)
        self._group_style = self._build_group_style(self._active_colors)
        for group in self.findChildren(QGroupBox):
            group.setStyleSheet(self._group_style)
        self._apply_palette_styles()

    def _apply_palette_styles(self) -> None:
        bg = self._color("background", "#04070B")
        panel = self._color("panel", "#071421")
        border = self._color("panel_border", "#16324B")
        text = self._color("text", "#D8E1E8")
        muted = self._color("muted", self._color("ticks", "#8AA0B2"))
        scale = max(0.70, min(1.80, float(getattr(self.settings, "ui_scale_percent", 100)) / 100.0))
        title_px = max(18, int(round(24 * scale)))
        tab_v = max(7, int(round(9 * scale)))
        tab_h = max(12, int(round(16 * scale)))
        self.title.setStyleSheet(f"font-size:{title_px}px;font-weight:700;color:{text};")
        self.scale_label.setStyleSheet(f"color:{muted};")
        self.tabs.setStyleSheet(
            f"QTabWidget::pane{{background:{bg};border:1px solid {border};}}"
            f"QTabBar::tab{{background:{panel};color:{text};padding:{tab_v}px {tab_h}px;"
            f"border:1px solid {border};border-bottom:none;border-top-left-radius:8px;border-top-right-radius:8px;}}"
            f"QTabBar::tab:selected{{background:{panel};color:{text};}}"
            f"QTabBar::tab:!selected{{background:{bg};color:{muted};}}"
            f"QTabBar::tab:hover{{background:{panel};color:{text};}}"
        )

    def _scroll_tab(self, layout: QVBoxLayout) -> QScrollArea:
        """
        Wrap a settings tab widget in a scrollable container.

        Implementation details:
            Reads or updates Qt widgets and emits signals so the main window can keep application
            state synchronized.
        """
        body = QWidget()
        body.setLayout(layout)
        layout.setContentsMargins(24, 18, 24, 24)
        layout.setSpacing(14)
        layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        return scroll

    def _build_cluster_tab(self) -> QScrollArea:
        """
        Build controls for cluster style, units, and gauge behavior.

        Implementation details:
            Creates Qt controls, places them into layouts, and returns the assembled widget tree.
        """
        layout = QVBoxLayout()
        cluster_box = QGroupBox("Speed / RPM")
        cluster_box.setStyleSheet(self._group_style)
        form = QFormLayout(cluster_box)
        self.speed_style = QComboBox(); self.speed_style.addItems(["digital", "analog"])
        self.rpm_style = QComboBox(); self.rpm_style.addItems(["digital", "analog"])
        self.analog_mode = QComboBox(); self.analog_mode.addItems(["needle", "arc"])
        self.analog_show_value = QCheckBox("Show numeric value inside analog gauges")
        self.max_speed = QSpinBox(); self.max_speed.setRange(60, 400); self.max_speed.setSuffix(" km/h")
        self.max_rpm = QSpinBox(); self.max_rpm.setRange(3000, 12000); self.max_rpm.setSingleStep(500)
        self.redline = QSpinBox(); self.redline.setRange(2000, 12000); self.redline.setSingleStep(100)
        form.addRow("Speed style", self.speed_style)
        form.addRow("RPM style", self.rpm_style)
        form.addRow("Analog rendering", self.analog_mode)
        form.addRow(self.analog_show_value)
        form.addRow("Speedometer max", self.max_speed)
        form.addRow("Tachometer max", self.max_rpm)
        form.addRow("Redline", self.redline)
        layout.addWidget(cluster_box)

        behavior_box = QGroupBox("HUD behavior")
        behavior_box.setStyleSheet(self._group_style)
        behavior_form = QFormLayout(behavior_box)
        self.mirror_check = QCheckBox("Mirror rendered cluster for windshield reflection")
        self.fullscreen_check = QCheckBox("Fullscreen")
        self.lock_widgets = QCheckBox("Lock widget positions and sizes")
        self.layout_grid_enabled = QCheckBox("Show/snap to layout grid while editing")
        self.layout_grid_size = QSpinBox()
        self.layout_grid_size.setRange(8, 160)
        self.layout_grid_size.setSingleStep(4)
        self.layout_grid_size.setSuffix(" px")
        behavior_form.addRow(self.mirror_check)
        behavior_form.addRow(self.fullscreen_check)
        behavior_form.addRow(self.lock_widgets)
        behavior_form.addRow(self.layout_grid_enabled)
        behavior_form.addRow("Grid size", self.layout_grid_size)
        layout.addWidget(behavior_box)
        return self._scroll_tab(layout)

    def _build_widgets_tab(self) -> QScrollArea:
        """
        Build controls for selecting visible dashboard widgets.

        Implementation details:
            Creates Qt controls, places them into layouts, and returns the assembled widget tree.
        """
        layout = QVBoxLayout()
        note = QLabel("Choose what appears on the HUD. The Telemetry screen still records supported parameters even when a widget is hidden here.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#8AA0B2;")
        layout.addWidget(note)

        self.widget_checks: dict[str, QCheckBox] = {}
        self.widget_bar_combos: dict[str, QComboBox] = {}
        self.widget_min_spins: dict[str, QDoubleSpinBox] = {}
        self.widget_max_spins: dict[str, QDoubleSpinBox] = {}

        for key, label in self.WIDGET_LABELS.items():
            row_box = QGroupBox(label)
            row_box.setStyleSheet(self._group_style)
            row_form = QFormLayout(row_box)
            check = QCheckBox("Show on main HUD")
            combo = QComboBox(); combo.addItems(["horizontal", "vertical"])
            min_spin = QDoubleSpinBox(); min_spin.setRange(-9999.0, 99999.0); min_spin.setDecimals(1)
            max_spin = QDoubleSpinBox(); max_spin.setRange(-9999.0, 99999.0); max_spin.setDecimals(1)
            row_form.addRow(check)
            row_form.addRow("Progress bar", combo)
            row_form.addRow("Expected / safe min", min_spin)
            row_form.addRow("Expected / safe max", max_spin)
            layout.addWidget(row_box)
            self.widget_checks[key] = check
            self.widget_bar_combos[key] = combo
            self.widget_min_spins[key] = min_spin
            self.widget_max_spins[key] = max_spin
        return self._scroll_tab(layout)


    def _build_telemetry_tab(self) -> QScrollArea:
        """
        Build controls for telemetry recording, graph limits, and export options.

        Implementation details:
            Creates Qt controls, places them into layouts, and returns the assembled widget tree.
        """
        layout = QVBoxLayout()

        sample_box = QGroupBox("Recording and graph view")
        sample_box.setStyleSheet(self._group_style)
        form = QFormLayout(sample_box)
        self.telemetry_sample_interval = QSpinBox()
        self.telemetry_sample_interval.setRange(100, 60000)
        self.telemetry_sample_interval.setSingleStep(100)
        self.telemetry_sample_interval.setSuffix(" ms")
        self.telemetry_history_seconds = QSpinBox()
        self.telemetry_history_seconds.setRange(30, 86400)
        self.telemetry_history_seconds.setSingleStep(30)
        self.telemetry_history_seconds.setSuffix(" s")
        self.telemetry_full_session = QCheckBox("Show the whole current session on telemetry graphs")
        form.addRow("Sample storage interval", self.telemetry_sample_interval)
        form.addRow("Graph time window", self.telemetry_history_seconds)
        form.addRow(self.telemetry_full_session)
        note = QLabel("The full session is always kept in memory until you clear it. The time-window option only controls what portion is drawn on the graphs.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#8AA0B2;")
        form.addRow(note)
        layout.addWidget(sample_box)

        export_box = QGroupBox("Telemetry export")
        export_box.setStyleSheet(self._group_style)
        export_form = QFormLayout(export_box)
        self.telemetry_auto_export = QCheckBox("Automatically export when the telemetry session ends")
        self.telemetry_export_format = QComboBox()
        self.telemetry_export_format.addItems(["xlsx", "csv"])
        export_dir_row = QHBoxLayout()
        self.telemetry_export_dir = QLineEdit()
        self.telemetry_export_dir.setPlaceholderText("Leave empty for the app telemetry_exports folder")
        self.browse_auto_export_dir = QPushButton("Browse")
        export_dir_row.addWidget(self.telemetry_export_dir, 1)
        export_dir_row.addWidget(self.browse_auto_export_dir)
        export_form.addRow(self.telemetry_auto_export)
        export_form.addRow("Export format", self.telemetry_export_format)
        export_form.addRow("Auto-export folder", export_dir_row)
        layout.addWidget(export_box)

        return self._scroll_tab(layout)

    def _build_connection_tab(self) -> QScrollArea:
        """
        Build controls for selecting and configuring the OBD adapter connection.

        Implementation details:
            Creates separate serial and TCP/IP controls so users can select detected COM ports or
            enter only a host and port for socket-based adapters.
        """
        layout = QVBoxLayout()
        conn_box = QGroupBox("OBD adapter")
        conn_box.setStyleSheet(self._group_style)
        form = QFormLayout(conn_box)

        self.connection_type = QComboBox()
        self.connection_type.addItem("Serial / COM / USB / Bluetooth", "serial")
        self.connection_type.addItem("TCP/IP socket / Wi-Fi", "tcp")

        self.autodetect = QCheckBox("Auto-detect serial adapter when no port is selected")

        self.serial_port_combo = QComboBox()
        self.serial_port_combo.setEditable(True)
        self.serial_port_combo.lineEdit().setPlaceholderText("Auto-detect, or choose COM/tty/rfcomm")
        self.refresh_ports_button = QPushButton("Refresh ports")
        serial_row = QHBoxLayout()
        serial_row.addWidget(self.serial_port_combo, 1)
        serial_row.addWidget(self.refresh_ports_button)

        self.tcp_host = QLineEdit()
        self.tcp_host.setPlaceholderText("127.0.0.1 or adapter IP")
        self.tcp_port = QSpinBox()
        self.tcp_port.setRange(1, 65535)
        self.tcp_port.setValue(3500)

        self.protocol = QComboBox()
        self.protocol.addItem("Autodetect", "auto")
        self.protocol.addItem("ISO 9141-2", "3")
        self.protocol.addItem("ISO 14230-4 KWP 5 baud", "4")
        self.protocol.addItem("ISO 14230-4 KWP fast", "5")
        self.protocol.addItem("ISO 15765-4 CAN 11/500", "6")
        self.protocol.addItem("ISO 15765-4 CAN 29/500", "7")
        self.protocol.addItem("ISO 15765-4 CAN 11/250", "8")
        self.protocol.addItem("ISO 15765-4 CAN 29/250", "9")

        self.baudrate = QSpinBox(); self.baudrate.setRange(9600, 500000); self.baudrate.setSingleStep(9600)
        self.fast_mode = QCheckBox("python-OBD fast mode")
        self.poll_interval = QSpinBox(); self.poll_interval.setRange(50, 2000); self.poll_interval.setSingleStep(10); self.poll_interval.setSuffix(" ms")
        self.speed_rpm_only = QCheckBox("Legacy mode: poll only Speed and RPM")
        self.speed_rpm_only.setToolTip("Use this for older or slow OBD/K-line vehicles that become unstable when many PIDs are queried.")
        self.auto_connect = QCheckBox("Auto-connect while disconnected")
        self.auto_connect_retry_interval = QSpinBox()
        self.auto_connect_retry_interval.setRange(250, 60000)
        self.auto_connect_retry_interval.setSingleStep(250)
        self.auto_connect_retry_interval.setSuffix(" ms")
        buttons = QHBoxLayout()
        self.connect_button = QPushButton("Connect")
        self.disconnect_button = QPushButton("Disconnect")
        buttons.addWidget(self.connect_button)
        buttons.addWidget(self.disconnect_button)

        form.addRow("Connection type", self.connection_type)
        form.addRow(self.autodetect)
        form.addRow("Detected serial port", serial_row)
        form.addRow("TCP/IP host", self.tcp_host)
        form.addRow("TCP/IP port", self.tcp_port)
        form.addRow("OBD protocol", self.protocol)
        form.addRow("Baudrate", self.baudrate)
        form.addRow("Poll interval", self.poll_interval)
        form.addRow(self.speed_rpm_only)
        form.addRow(self.fast_mode)
        form.addRow(self.auto_connect)
        form.addRow("Auto-connect retry interval", self.auto_connect_retry_interval)
        form.addRow(buttons)
        layout.addWidget(conn_box)
        self.refresh_ports_button.clicked.connect(self.refresh_serial_ports)
        self.connection_type.currentIndexChanged.connect(self.update_connection_fields)
        self.serial_port_combo.currentTextChanged.connect(lambda _text: self.update_connection_fields())
        self.tcp_host.textEdited.connect(lambda _text: self.update_connection_fields())
        self.tcp_port.valueChanged.connect(lambda _value: self.update_connection_fields())
        return self._scroll_tab(layout)

    def _build_colors_tab(self) -> QScrollArea:
        """
        Build controls for choosing the HUD color palette.

        Implementation details:
            Creates Qt controls, places them into layouts, and returns the assembled widget tree.
        """
        layout = QVBoxLayout()
        colors_box = QGroupBox("Palette")
        colors_box.setStyleSheet(self._group_style)
        grid = QGridLayout(colors_box)
        self.color_inputs: dict[str, QLineEdit] = {}
        for row, key in enumerate(self.COLOR_KEYS):
            line = QLineEdit()
            pick = QPushButton("Pick")
            pick.clicked.connect(lambda _=False, k=key: self.pick_color(k))
            grid.addWidget(QLabel(key.replace("_", " ").title()), row, 0)
            grid.addWidget(line, row, 1)
            grid.addWidget(pick, row, 2)
            self.color_inputs[key] = line
        layout.addWidget(colors_box)
        return self._scroll_tab(layout)

    def _build_presets_tab(self) -> QScrollArea:
        """
        Build controls for saving, loading, and deleting presets.

        Implementation details:
            Creates Qt controls, places them into layouts, and returns the assembled widget tree.
        """
        layout = QVBoxLayout()
        preset_box = QGroupBox("Layout presets")
        preset_box.setStyleSheet(self._group_style)
        row = QHBoxLayout(preset_box)
        self.save_preset_button = QPushButton("Save Preset")
        self.load_preset_button = QPushButton("Load Preset")
        self.delete_preset_button = QPushButton("Delete Preset")
        row.addWidget(self.save_preset_button)
        row.addWidget(self.load_preset_button)
        row.addWidget(self.delete_preset_button)
        row.addStretch(1)
        layout.addWidget(preset_box)
        return self._scroll_tab(layout)

    def _connect_change_signals(self) -> None:
        """
        Connect settings widgets to the signal that marks settings as changed.

        Implementation details:
            Registers callbacks/signals and updates service state for the active connection.
        """
        controls = [
            self.speed_style,
            self.rpm_style,
            self.analog_mode,
            self.analog_show_value,
            self.max_speed,
            self.max_rpm,
            self.redline,
            self.mirror_check,
            self.fullscreen_check,
            self.lock_widgets,
            self.layout_grid_enabled,
            self.layout_grid_size,
            self.connection_type,
            self.autodetect,
            self.serial_port_combo,
            self.tcp_host,
            self.tcp_port,
            self.protocol,
            self.baudrate,
            self.poll_interval,
            self.speed_rpm_only,
            self.fast_mode,
            self.auto_connect,
            self.auto_connect_retry_interval,
            self.telemetry_sample_interval,
            self.telemetry_history_seconds,
            self.telemetry_full_session,
            self.telemetry_auto_export,
            self.telemetry_export_format,
            self.telemetry_export_dir,
            *self.widget_checks.values(),
            *self.widget_bar_combos.values(),
            *self.widget_min_spins.values(),
            *self.widget_max_spins.values(),
            *self.color_inputs.values(),
        ]
        for control in controls:
            signal = (
                getattr(control, "currentTextChanged", None)
                or getattr(control, "valueChanged", None)
                or getattr(control, "toggled", None)
                or getattr(control, "textEdited", None)
            )
            if signal is not None:
                signal.connect(self.emit_settings)

    def load_from_settings(self, settings: AppSettings) -> None:
        """
        Populate the settings UI from an AppSettings object.

        Implementation details:
            Reads values from the source object or file and applies defaults when values are
            missing.
        """
        self._loading = True
        try:
            self.settings = deepcopy(settings)
            self.speed_style.setCurrentText(settings.speed_style if settings.speed_style in {"digital", "analog"} else "digital")
            self.rpm_style.setCurrentText(settings.rpm_style if settings.rpm_style in {"digital", "analog"} else "digital")
            self.analog_mode.setCurrentText(settings.analog_mode if settings.analog_mode in {"needle", "arc"} else "needle")
            self.analog_show_value.setChecked(settings.analog_show_value)
            self.max_speed.setValue(settings.max_speed_kph)
            self.max_rpm.setValue(settings.max_rpm)
            self.redline.setValue(min(settings.redline_rpm, settings.max_rpm))
            self.mirror_check.setChecked(settings.mirrored)
            self.fullscreen_check.setChecked(settings.fullscreen)
            self.lock_widgets.setChecked(settings.widget_locked)
            self.layout_grid_enabled.setChecked(settings.layout_grid_enabled)
            self.layout_grid_size.setValue(settings.layout_grid_size_px)
            self.scale_label.setText(f"{int(getattr(settings, 'ui_scale_percent', 100))}%")
            self.refresh_serial_ports()
            connection_type = getattr(settings.connection, "connection_type", "serial")
            if str(getattr(settings.connection, "port", "")).strip().startswith("socket://"):
                connection_type = "tcp"
            self.connection_type.setCurrentIndex(1 if connection_type == "tcp" else 0)
            self.autodetect.setChecked(settings.connection.autodetect)
            serial_port = settings.connection.port if connection_type != "tcp" else ""
            self._set_serial_port_text(serial_port)
            self.tcp_host.setText(str(getattr(settings.connection, "tcp_host", "127.0.0.1") or "127.0.0.1"))
            self.tcp_port.setValue(int(getattr(settings.connection, "tcp_port", 3500) or 3500))
            protocol = str(getattr(settings.connection, "protocol", "auto") or "auto")
            protocol_index = self.protocol.findData(protocol)
            self.protocol.setCurrentIndex(protocol_index if protocol_index >= 0 else 0)
            self.baudrate.setValue(settings.connection.baudrate)
            self.poll_interval.setValue(settings.connection.poll_interval_ms)
            self.speed_rpm_only.setChecked(bool(getattr(settings.connection, "speed_rpm_only", False)))
            self.fast_mode.setChecked(settings.connection.fast_mode)
            self.auto_connect.setChecked(settings.connection.auto_connect_enabled)
            self.auto_connect_retry_interval.setValue(settings.connection.auto_connect_retry_interval_ms)
            self.telemetry_sample_interval.setValue(settings.telemetry.sample_interval_ms)
            self.telemetry_history_seconds.setValue(settings.telemetry.graph_history_seconds)
            self.telemetry_full_session.setChecked(settings.telemetry.graph_full_session)
            self.telemetry_auto_export.setChecked(settings.telemetry.auto_export_enabled)
            self.telemetry_export_format.setCurrentText(settings.telemetry.export_format if settings.telemetry.export_format in {"xlsx", "csv"} else "xlsx")
            self.telemetry_export_dir.setText(settings.telemetry.auto_export_dir)
            for key, check in self.widget_checks.items():
                check.setChecked(settings.widget_visibility.get(key, True))
            for key, combo in self.widget_bar_combos.items():
                combo.setCurrentText(settings.widget_bar_orientation.get(key, "horizontal"))
                bounds = settings.widget_thresholds.get(key, {"min": 0.0, "max": 100.0})
                self.widget_min_spins[key].setValue(float(bounds.get("min", 0.0)))
                self.widget_max_spins[key].setValue(float(bounds.get("max", 100.0)))
            for key, line in self.color_inputs.items():
                line.setText(settings.colors.get(key, "#FFFFFF"))
            self.update_connection_fields()
            self.apply_ui_scale(getattr(settings, "ui_scale_percent", 100))
        finally:
            self._loading = False

    def gather_settings(self) -> AppSettings:
        """
        Collect the current settings UI state into an AppSettings object.

        Implementation details:
            Reads or updates Qt widgets and emits signals so the main window can keep application
            state synchronized.
        """
        s = deepcopy(self.settings)
        s.speed_style = self.speed_style.currentText()
        s.rpm_style = self.rpm_style.currentText()
        s.analog_mode = self.analog_mode.currentText()
        s.analog_show_value = self.analog_show_value.isChecked()
        s.max_speed_kph = self.max_speed.value()
        s.max_rpm = self.max_rpm.value()
        s.redline_rpm = min(self.redline.value(), s.max_rpm)
        s.mirrored = self.mirror_check.isChecked()
        s.fullscreen = self.fullscreen_check.isChecked()
        s.widget_locked = self.lock_widgets.isChecked()
        s.layout_grid_enabled = self.layout_grid_enabled.isChecked()
        s.layout_grid_size_px = self.layout_grid_size.value()
        s.ui_scale_percent = int(max(70, min(180, getattr(self.settings, "ui_scale_percent", 100))))
        mode = self.connection_type.currentData() or "serial"
        s.connection.connection_type = str(mode)
        if mode == "tcp":
            host = self.tcp_host.text().strip() or "127.0.0.1"
            port = self.tcp_port.value()
            s.connection.tcp_host = host
            s.connection.tcp_port = port
            s.connection.port = f"socket://{host}:{port}"
            s.connection.autodetect = False
        else:
            serial_port = self._selected_serial_port()
            s.connection.port = serial_port
            s.connection.autodetect = self.autodetect.isChecked() and not serial_port
        s.connection.protocol = str(self.protocol.currentData() or "auto")
        s.connection.baudrate = self.baudrate.value()
        s.connection.poll_interval_ms = self.poll_interval.value()
        s.connection.speed_rpm_only = self.speed_rpm_only.isChecked()
        s.connection.fast_mode = self.fast_mode.isChecked()
        s.connection.auto_connect_enabled = self.auto_connect.isChecked()
        s.connection.auto_connect_retry_interval_ms = self.auto_connect_retry_interval.value()
        s.telemetry.sample_interval_ms = self.telemetry_sample_interval.value()
        s.telemetry.graph_history_seconds = self.telemetry_history_seconds.value()
        s.telemetry.graph_full_session = self.telemetry_full_session.isChecked()
        s.telemetry.auto_export_enabled = self.telemetry_auto_export.isChecked()
        s.telemetry.export_format = self.telemetry_export_format.currentText()
        s.telemetry.auto_export_dir = self.telemetry_export_dir.text().strip()
        previous_visibility = dict(self.settings.widget_visibility)
        existing_order = [k for k in getattr(s, "widget_order", []) if k in DEFAULT_WIDGET_ORDER]
        for key, check in self.widget_checks.items():
            now_visible = check.isChecked()
            was_visible = bool(previous_visibility.get(key, False))
            s.widget_visibility[key] = now_visible
            if now_visible and not was_visible:
                # Re-added widgets go to the top/front of the z-order. The
                # DashboardCanvas paints in this order and hit-tests reversed.
                existing_order = [k for k in existing_order if k != key]
                existing_order.append(key)
            elif not now_visible:
                existing_order = [k for k in existing_order if k != key]
        for key in ("speed", "rpm"):
            if key not in existing_order:
                existing_order.insert(0 if key == "speed" else 1, key)
        for key in DEFAULT_WIDGET_ORDER:
            if key in {"speed", "rpm"}:
                continue
            if s.widget_visibility.get(key, False) and key not in existing_order:
                existing_order.append(key)
        s.widget_order = existing_order

        for key, combo in self.widget_bar_combos.items():
            s.widget_bar_orientation[key] = combo.currentText()
            min_v = self.widget_min_spins[key].value()
            max_v = self.widget_max_spins[key].value()
            if max_v < min_v:
                min_v, max_v = max_v, min_v
            s.widget_thresholds[key] = {"min": min_v, "max": max_v}
        for key, line in self.color_inputs.items():
            value = line.text().strip()
            if value:
                s.colors[key] = value
        return s

    def emit_settings(self, *args) -> None:
        """
        Emit the current settings to listeners after a user change.

        Implementation details:
            Collects current state and sends it through the matching Qt signal.
        """
        if self._loading:
            return
        self.settings_changed.emit(self.gather_settings())

    def adjust_ui_scale(self, delta: int) -> None:
        """Increase or decrease menu scale from the Settings screen."""
        current = int(max(70, min(180, getattr(self.settings, "ui_scale_percent", 100))))
        self.settings.ui_scale_percent = int(max(70, min(180, current + delta)))
        self.scale_label.setText(f"{self.settings.ui_scale_percent}%")
        self.apply_ui_scale(self.settings.ui_scale_percent)
        self.emit_settings()

    def apply_ui_scale(self, scale_percent: int) -> None:
        """Apply a readable size multiplier to the settings menu controls."""
        scale = max(0.70, min(1.80, float(scale_percent) / 100.0))
        title_px = max(18, int(round(24 * scale)))
        tab_v = max(7, int(round(9 * scale)))
        tab_h = max(12, int(round(16 * scale)))
        button_h = max(30, int(round(34 * scale)))
        self.scale_label.setText(f"{int(scale_percent)}%")
        self._apply_palette_styles()
        for button in self.findChildren(QPushButton):
            button.setMinimumHeight(button_h)
        for spin in self.findChildren(QSpinBox):
            spin.setMinimumHeight(button_h)
        for spin in self.findChildren(QDoubleSpinBox):
            spin.setMinimumHeight(button_h)
        for combo in self.findChildren(QComboBox):
            combo.setMinimumHeight(button_h)
        for line in self.findChildren(QLineEdit):
            line.setMinimumHeight(button_h)

    def refresh_serial_ports(self) -> None:
        """Refresh the serial port combo box from pyserial, preserving the current selection."""
        current = self._selected_serial_port()
        if not current:
            current = self.serial_port_combo.currentText().strip()
        self.serial_port_combo.blockSignals(True)
        try:
            self.serial_port_combo.clear()
            self.serial_port_combo.addItem("", "")
            if list_ports is not None:
                for port in sorted(list_ports.comports(), key=lambda p: p.device):
                    label = port.device
                    if port.description and port.description != port.device:
                        label = f"{port.device} — {port.description}"
                    self.serial_port_combo.addItem(label, port.device)
            if current:
                self._set_serial_port_text(current)
        finally:
            self.serial_port_combo.blockSignals(False)
        self.update_connection_fields()

    def _selected_serial_port(self) -> str:
        """Return the actual serial port value from the combo, without the display description."""
        text = self.serial_port_combo.currentText().strip()
        if not text:
            return ""
        for index in range(self.serial_port_combo.count()):
            data = self.serial_port_combo.itemData(index)
            item_text = self.serial_port_combo.itemText(index)
            if isinstance(data, str) and data.strip():
                if text == data.strip() or text == item_text or text.startswith(f"{data.strip()} —"):
                    return data.strip()
        if "—" in text:
            text = text.split("—", 1)[0].strip()
        return text

    def _set_serial_port_text(self, port: str) -> None:
        """Select an existing serial port or insert a previously saved/custom port."""
        port = (port or "").strip()
        if not port:
            self.serial_port_combo.setCurrentIndex(0)
            return
        for index in range(self.serial_port_combo.count()):
            if self.serial_port_combo.itemData(index) == port or self.serial_port_combo.itemText(index) == port:
                self.serial_port_combo.setCurrentIndex(index)
                return
        self.serial_port_combo.addItem(port, port)
        self.serial_port_combo.setCurrentIndex(self.serial_port_combo.count() - 1)

    def update_connection_fields(self) -> None:
        """Update connection field enabled states for the selected connection mode."""
        mode = self.connection_type.currentData() if hasattr(self, "connection_type") else "serial"
        serial_mode = mode != "tcp"
        self.autodetect.setEnabled(serial_mode)
        self.serial_port_combo.setEnabled(serial_mode)
        self.refresh_ports_button.setEnabled(serial_mode)
        self.baudrate.setEnabled(serial_mode)
        self.tcp_host.setEnabled(not serial_mode)
        self.tcp_port.setEnabled(not serial_mode)
        if not self._loading:
            self.emit_settings()

    def pick_color(self, key: str) -> None:
        """
        Open a color picker and store the chosen color in the target field.

        Implementation details:
            Opens the appropriate Qt dialog and stores the selected value when the user accepts.
        """
        color = QColorDialog.getColor(QColor(self.color_inputs[key].text()), self, f"Choose {key}")
        if color.isValid():
            self.color_inputs[key].setText(color.name())
            self.emit_settings()

    def pick_auto_export_dir(self) -> None:
        """
        Open a folder picker for telemetry auto-export output.

        Implementation details:
            Opens the appropriate Qt dialog and stores the selected value when the user accepts.
        """
        folder = QFileDialog.getExistingDirectory(self, "Choose telemetry auto-export folder", self.telemetry_export_dir.text().strip())
        if folder:
            self.telemetry_export_dir.setText(folder)
            self.emit_settings()

    def save_preset(self) -> None:
        """
        Save the current settings under a reusable preset name.

        Implementation details:
            Sanitizes the preset name and writes the current settings to the presets directory.
        """
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name")
        if ok and name.strip():
            current = self.gather_settings()
            self.settings_changed.emit(current)
            self.preset_provider("save", name.strip())

    def load_preset(self) -> None:
        """
        Load a named preset into an AppSettings instance.

        Implementation details:
            Reads the selected preset JSON and converts it into AppSettings.
        """
        presets = self.preset_provider("list", None)
        if not presets:
            return
        name, ok = QInputDialog.getItem(self, "Load Preset", "Preset", presets, 0, False)
        if ok and name:
            loaded = self.preset_provider("load", name)
            self.load_from_settings(loaded)
            self.settings_changed.emit(loaded)

    def delete_preset(self) -> None:
        """
        Remove a saved preset from disk.

        Implementation details:
            Deletes the preset file if it exists and leaves other presets untouched.
        """
        presets = self.preset_provider("list", None)
        if not presets:
            return
        name, ok = QInputDialog.getItem(self, "Delete Preset", "Preset", presets, 0, False)
        if not ok or not name:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Preset",
            f"Delete preset '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.preset_provider("delete", name)
