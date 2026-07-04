from __future__ import annotations

import csv
import html
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

from hud.models.telemetry import TelemetrySnapshot


COLUMNS: list[tuple[str, str]] = [
    ("timestamp", "Timestamp"),
    ("elapsed_s", "Elapsed (s)"),
    ("source", "Source"),
    ("connected", "Connected"),
    ("speed_kph", "Speed (km/h)"),
    ("rpm", "RPM"),
    ("throttle_position", "Throttle (%)"),
    ("fuel_consumption_l_100km", "Fuel consumption (L/100km)"),
    ("fuel_rate_lph", "Fuel rate (L/h)"),
    ("fuel_level", "Fuel level (%)"),
    ("coolant_temp_c", "Coolant temp (°C)"),
    ("oil_temp_c", "Oil temp (°C)"),
    ("battery_voltage", "Battery voltage (V)"),
    ("cel_active", "CEL active"),
]


def export_telemetry(samples: Iterable[TelemetrySnapshot], path: Path) -> Path:
    """Export telemetry samples to CSV or a dependency-free XLSX workbook."""
    sample_list = list(samples)
    if not sample_list:
        raise ValueError("No telemetry samples to export")
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".csv":
        _write_csv(sample_list, path)
    else:
        if path.suffix.lower() != ".xlsx":
            path = path.with_suffix(".xlsx")
        _write_xlsx(sample_list, path)
    return path


def default_export_path(base_dir: Path, fmt: str = "xlsx") -> Path:
    """
    Build a timestamped default telemetry export path.

    Implementation details:
        Coordinates file, settings, or adapter state through a small service-layer API.
    """
    suffix = ".csv" if fmt.lower() == "csv" else ".xlsx"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return base_dir / f"telemetry_{stamp}{suffix}"


def _rows(samples: list[TelemetrySnapshot]) -> list[list[object | None]]:
    """
    Convert telemetry snapshots into tabular export rows.

    Implementation details:
        Coordinates file, settings, or adapter state through a small service-layer API.
    """
    start = samples[0].timestamp
    rows: list[list[object | None]] = []
    for s in samples:
        rows.append([
            datetime.fromtimestamp(s.timestamp).isoformat(timespec="milliseconds"),
            round(s.timestamp - start, 3),
            s.source,
            int(bool(s.connected)),
            _round(s.speed_kph),
            _round(s.rpm),
            _round(s.throttle_position),
            _round(s.fuel_consumption_l_100km),
            _round(s.fuel_rate_lph),
            _round(s.fuel_level),
            _round(s.coolant_temp_c),
            _round(s.oil_temp_c),
            _round(s.battery_voltage),
            int(bool(s.cel_active)),
        ])
    return rows


def _round(value: float | None) -> float | None:
    """
    Round numeric export values while preserving missing values.

    Implementation details:
        Coordinates file, settings, or adapter state through a small service-layer API.
    """
    if value is None:
        return None
    try:
        return round(float(value), 3)
    except Exception:
        return None


def _write_csv(samples: list[TelemetrySnapshot], path: Path) -> None:
    """
    Write telemetry rows as a CSV file.

    Implementation details:
        Coordinates file, settings, or adapter state through a small service-layer API.
    """
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow([label for _, label in COLUMNS])
        writer.writerows(_rows(samples))


def _write_xlsx(samples: list[TelemetrySnapshot], path: Path) -> None:
    """
    Write telemetry rows as a minimal XLSX workbook.

    Implementation details:
        Creates the required XML parts and writes them into a ZIP container with XLSX paths.
    """
    data = [[label for _, label in COLUMNS], *_rows(samples)]
    sheet_xml = _worksheet_xml(data)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _content_types_xml())
        zf.writestr("_rels/.rels", _rels_xml())
        zf.writestr("xl/workbook.xml", _workbook_xml())
        zf.writestr("xl/_rels/workbook.xml.rels", _workbook_rels_xml())
        zf.writestr("xl/styles.xml", _styles_xml())
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def _col_name(index: int) -> str:
    """
    Convert a one-based column index to an Excel column name.

    Implementation details:
        Coordinates file, settings, or adapter state through a small service-layer API.
    """
    name = ""
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def _worksheet_xml(rows: list[list[object | None]]) -> str:
    """
    Build the worksheet XML used inside the generated XLSX file.

    Implementation details:
        Coordinates file, settings, or adapter state through a small service-layer API.
    """
    row_xml: list[str] = []
    for r_idx, row in enumerate(rows, start=1):
        cells: list[str] = []
        for c_idx, value in enumerate(row, start=1):
            ref = f"{_col_name(c_idx)}{r_idx}"
            if value is None or value == "":
                cells.append(f'<c r="{ref}"/>')
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                text = html.escape(str(value), quote=False)
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>')
        row_xml.append(f'<row r="{r_idx}">' + "".join(cells) + "</row>")
    max_col = _col_name(len(COLUMNS))
    max_row = max(1, len(rows))
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <dimension ref="A1:{max_col}{max_row}"/>
  <sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
  <sheetFormatPr defaultRowHeight="15"/>
  <cols>
    <col min="1" max="1" width="25" customWidth="1"/>
    <col min="2" max="14" width="16" customWidth="1"/>
  </cols>
  <sheetData>{''.join(row_xml)}</sheetData>
  <autoFilter ref="A1:{max_col}{max_row}"/>
</worksheet>'''


def _content_types_xml() -> str:
    """
    Build the XLSX content-types manifest.

    Implementation details:
        Coordinates file, settings, or adapter state through a small service-layer API.
    """
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>'''


def _rels_xml() -> str:
    """
    Build the root relationship XML for the XLSX package.

    Implementation details:
        Coordinates file, settings, or adapter state through a small service-layer API.
    """
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''


def _workbook_xml() -> str:
    """
    Build the workbook XML for the XLSX package.

    Implementation details:
        Coordinates file, settings, or adapter state through a small service-layer API.
    """
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Telemetry" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''


def _workbook_rels_xml() -> str:
    """
    Build the workbook relationship XML for the XLSX package.

    Implementation details:
        Coordinates file, settings, or adapter state through a small service-layer API.
    """
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''


def _styles_xml() -> str:
    """
    Build the minimal style sheet XML for the XLSX package.

    Implementation details:
        Coordinates file, settings, or adapter state through a small service-layer API.
    """
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''
