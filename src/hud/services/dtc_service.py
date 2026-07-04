"""DTC service layer for python-OBD with a raw ELM fallback.

The public API returns normalized DtcEntry objects for the UI while hiding
adapter-specific response formats and python-OBD version differences.
"""

from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from hud.models.dtc import DtcEntry
from hud.models.enums import DtcCategory
from hud.services.obd_service import get_obd_manager

try:
    import obd  # type: ignore
except Exception:  # pragma: no cover
    obd = None




_DTC_CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "dtc_catalog.csv"
_DTC_CODE_RE = re.compile(r"^[PBCU][0-3][0-9A-F]{3}$", re.IGNORECASE)


@lru_cache(maxsize=1)
def _load_dtc_catalog() -> dict[str, str]:
    """
    Load the HUD-local DTC description catalog as an uppercase code-to-description map.

    Implementation details:
        Reads the CSV once through lru_cache, normalizes the code column, preserves descriptions
        that contain commas, and returns an empty map if the catalog cannot be opened.
    """
    catalog: dict[str, str] = {}
    try:
        with _DTC_CATALOG_PATH.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.reader(handle):
                if len(row) < 2:
                    continue
                code = (row[0] or "").strip().upper()
                description = ",".join(row[1:]).strip()
                if code and description:
                    catalog[code] = description
    except Exception:
        return {}
    return catalog


def _dtc_category_for_code(code: str) -> str:
    """
    Return a human-readable DTC category label for a code prefix.

    Implementation details:
        Uses the first character of the normalized code to map P/B/C/U systems to powertrain, body,
        chassis, or network families.
    """
    system = (code or "")[:1].upper()
    return {
        "P": "P codes - Powertrain",
        "B": "B codes - Body",
        "C": "C codes - Chassis",
        "U": "U codes - Network",
    }.get(system, "Unknown")


def _generic_emulator_description_for(code: str) -> str:
    """
    Build a deterministic fallback description for valid codes missing from exact catalogs.

    Implementation details:
        Validates the P/B/C/U code shape, derives the OBD family from the first three characters,
        and labels the family as generic or manufacturer-specific from the second digit.
    """
    code = (code or "").strip().upper()
    if not _DTC_CODE_RE.match(code):
        return "Unknown DTC"
    family = code[:3]
    standard = "Generic OBD-II" if len(code) >= 2 and code[1] == "0" else "manufacturer-specific / enhanced"
    return f"{standard} {_dtc_category_for_code(code)} diagnostic trouble code ({family}xx family)"


class DtcService:
    """Read and clear diagnostic trouble codes through the shared OBD connection."""
    def __init__(self, connection_settings: Any) -> None:
        """
        Initialize the DTC service with the current connection settings.

        Implementation details:
            Stores the settings, obtains the shared OBD manager, and pushes the settings into that
            manager so DTC reads use the same adapter configuration as telemetry.
        """
        self.connection_settings = connection_settings
        self._manager = get_obd_manager()
        self._manager.update_settings(connection_settings)

    def read_all(self) -> list[DtcEntry]:
        """
        Read stored, pending, and permanent DTCs for display.

        Implementation details:
            Opens one exclusive OBD session to pause telemetry, queries Mode 03, 07, and 0A in
            order, then removes duplicate category/code pairs before returning entries to the UI.
        """
        if obd is None:
            return []
        entries: list[DtcEntry] = []
        with self._manager.exclusive_session() as connection:
            if connection is None:
                return []
            entries.extend(self._read_standard(connection, DtcCategory.STORED, "GET_DTC", "03"))
            entries.extend(self._read_standard(connection, DtcCategory.PENDING, "PENDING_DTC", "07"))
            entries.extend(self._read_standard(connection, DtcCategory.PERMANENT, "PERMANENT_DTC", "0A"))
        return self._dedupe(entries)

    def clear_all(self) -> tuple[bool, str]:
        """
        Clear all generic OBD-II diagnostic trouble codes.

        Implementation details:
            Uses python-OBD CLEAR_DTC when available, falls back to raw Mode 04, and reports whether
            the adapter acknowledged the request.
        """
        if obd is None:
            return False, "python-OBD not installed."
        with self._manager.exclusive_session() as connection:
            if connection is None:
                return False, "No active OBD connection available. Connect the adapter in Settings first."
            try:
                cmd = getattr(getattr(obd, "commands", object()), "CLEAR_DTC", None)
                if cmd is not None:
                    response = connection.query(cmd, force=True)
                    if response is None or not getattr(response, "is_null", lambda: True)():
                        return True, "DTC clear command sent."
                raw = self._send_raw(connection, "04")
                if raw is not None:
                    return True, "DTC clear command sent."
                return False, "Adapter did not acknowledge the clear command."
            except Exception as exc:
                return False, f"Failed to clear DTCs: {exc}"


    def _read_standard(
        self,
        connection: Any,
        category: DtcCategory,
        command_name: str,
        raw_mode: str,
    ) -> list[DtcEntry]:
        """
        Resolve one DTC category through the safest available path.

        Implementation details:
            Tries python-OBD first for structured values and descriptions, then sends the raw
            service number only if python-OBD does not provide usable data.
        """
        obd_rows = self._read_via_python_obd(connection, category, command_name, raw_mode)
        if obd_rows:
            return obd_rows

        raw_rows, raw_handled = self._read_via_raw_mode(connection, category, raw_mode)
        if raw_handled:
            return raw_rows
        return []

    def _read_via_python_obd(self, connection: Any, category: DtcCategory, command_name: str, raw_mode: str) -> list[DtcEntry]:
        """
        Read one DTC category through a python-OBD command object.

        Implementation details:
            Queries the requested command, converts structured response values when present, and
            inspects any embedded raw payload so a valid response is not queried twice.
        """
        cmd = getattr(getattr(obd, "commands", object()), command_name, None)
        if cmd is None:
            return []
        try:
            response = connection.query(cmd, force=True)

            if response is not None and not response.is_null() and getattr(response, "value", None):
                rows: list[DtcEntry] = []
                for item in response.value:
                    code, desc = self._coerce_python_obd_dtc(item)
                    if not code:
                        continue
                    rows.append(DtcEntry(category=category, code=code, description=self._describe_code(code, desc)))
                if rows:
                    return rows

            for raw_text in self._extract_raw_texts(response):
                codes = self._parse_dtc_response(raw_mode, raw_text)
                if codes:
                    return [
                        DtcEntry(
                            category=category,
                            code=code,
                            description=self._describe_code(code),
                            raw_payload=raw_text,
                        )
                        for code in codes
                    ]
                if self._is_related_empty_dtc_response(raw_mode, raw_text) or "NO DATA" in raw_text.upper():
                    return []
            return []
        except Exception:
            return []

    def _coerce_python_obd_dtc(self, item: Any) -> tuple[str, str]:
        """
        Normalize python-OBD DTC items to a code and optional description.

        Implementation details:
            Accepts tuple/list responses and object-like responses, extracting common code and
            description attributes while returning empty strings for unusable values.
        """
        if isinstance(item, (list, tuple)):
            if not item:
                return "", ""
            code = str(item[0] or "").strip().upper()
            desc = str(item[1] or "").strip() if len(item) > 1 else ""
            return code, desc
        code = str(getattr(item, "code", "") or getattr(item, "dtc", "") or item or "").strip().upper()
        desc = str(getattr(item, "description", "") or getattr(item, "desc", "") or "").strip()
        return code, desc

    def _describe_code(self, code: str, preferred: str | None = None) -> str:
        """
        Resolve the best available description for a DTC code.

        Implementation details:
            Prefers a non-empty python-OBD description, then tries python-OBD internal maps, the HUD
            CSV catalog, explicit fallback entries, and finally a generated family-level
            description.
        """
        code = (code or "").strip().upper()
        preferred = (preferred or "").strip()
        if preferred and preferred.lower() not in {"unknown", "unknown dtc", "n/a", "none"}:
            return preferred

        if obd is not None:
            for obj_path in (
                ("codes",),
                ("DTC",),
                ("dtc",),
                ("decoders", "dtc", "codes"),
                ("decoders", "dtc", "DTC"),
            ):
                try:
                    obj: Any = obd
                    for attr in obj_path:
                        obj = getattr(obj, attr)
                    if isinstance(obj, dict):
                        value = obj.get(code)
                        if value:
                            return str(value)
                    elif callable(obj):
                        value = obj(code)
                        if value:
                            return str(value)
                except Exception:
                    continue

        catalog_description = _load_dtc_catalog().get(code)
        if catalog_description:
            return catalog_description

        

        return _generic_emulator_description_for(code)

    def _read_via_raw_mode(self, connection: Any, category: DtcCategory, raw_mode: str) -> tuple[list[DtcEntry], bool]:
        """
        Read one DTC category by sending a raw OBD service number.

        Implementation details:
            Collects raw candidate responses, parses the first valid DTC payload, treats empty/NO
            DATA replies as handled, and reports whether any adapter response was seen.
        """
        saw_any_response = False
        for raw in self._send_raw_candidates(connection, raw_mode):
            normalized = (raw or '').strip()
            if not normalized:
                continue
            saw_any_response = True
            codes = self._parse_dtc_response(raw_mode, normalized)
            if codes:
                return ([DtcEntry(category=category, code=code, description=self._describe_code(code), raw_payload=normalized) for code in codes], True)
            if self._is_related_empty_dtc_response(raw_mode, normalized) or 'NO DATA' in normalized.upper():
                return ([], True)
        return ([], saw_any_response)

    def _read_via_raw_mode_(self, connection: Any, category: DtcCategory, raw_mode: str) -> tuple[list[DtcEntry], bool]:
        """Compatibility wrapper for archives that accidentally referenced a trailing-underscore method name."""
        return self._read_via_raw_mode(connection, category, raw_mode)

    def _send_raw(self, connection: Any, command: str) -> str | None:
        """
        Return the first raw response candidate for a command.

        Implementation details:
            Delegates to _send_raw_candidates and stops after the first text response, which is
            useful for single-response commands such as Mode 04 clear.
        """
        for text in self._send_raw_candidates(connection, command):
            return text
        return None

    def _send_raw_candidates(self, connection: Any, command: str) -> list[str]:
        """
        Send a raw command through whichever ELM/python-OBD interface is exposed.

        Implementation details:
            Builds a prioritized list of low-level send methods, tries compatible string/byte call
            signatures, extracts response text, de-duplicates it, and stops once the response
            satisfies the requested command.
        """
        command = (command or "").strip().upper()
        if not command:
            return []

        send_candidates: list[tuple[str, Any, str]] = []

        interface_objects: list[Any] = []
        for obj in [connection, getattr(connection, "interface", None), getattr(connection, "elm", None), getattr(connection, "_elm", None), getattr(connection, "_interface", None)]:
            if obj is not None and all(obj is not existing for existing in interface_objects):
                interface_objects.append(obj)

        for obj in interface_objects:
            func = getattr(obj, "_ELM327__send", None)
            if callable(func):
                send_candidates.append(("elm_private_send", func, "bytes"))

            func = getattr(obj, "send_and_parse", None)
            if callable(func):
                send_candidates.append(("send_and_parse", func, "bytes"))

        for obj in interface_objects:
            for attr in ("send", "_send"):
                func = getattr(obj, attr, None)
                if callable(func):
                    send_candidates.append((attr, func, "str"))

        for obj in interface_objects:
            func = getattr(obj, "query", None)
            if callable(func):
                send_candidates.append(("query", func, "query"))

        out: list[str] = []
        seen: set[str] = set()
        for name, func, mode in send_candidates:
            try:
                if mode == "bytes":
                    raw = func(command.encode("ascii"))
                elif mode == "query":
                    raw = func(command, force=True)
                else:
                    raw = func(command)
            except TypeError:
                try:
                    if mode == "bytes":
                        raw = func(command.encode("ascii"), True)
                    elif mode == "query":
                        raw = func(command, True)
                    else:
                        raw = func(command, True)
                except Exception:
                    continue
            except Exception:
                continue

            for text in self._extract_raw_texts(raw):
                cleaned_text = text.strip()
                if not cleaned_text or cleaned_text in seen:
                    continue
                seen.add(cleaned_text)
                out.append(cleaned_text)

                if command in {"03", "07", "0A"}:
                    if self._parse_dtc_response(command, cleaned_text) or self._is_related_empty_dtc_response(command, cleaned_text):
                        return out
                elif command == "04":
                    if self._is_clear_ack(cleaned_text):
                        return out
                elif self._looks_like_hex_response(cleaned_text):
                    return out
        return out

    def _extract_raw_texts(self, raw: Any) -> list[str]:
        """
        Extract readable response strings from python-OBD, ELM, or raw adapter objects.

        Implementation details:
            Recursively visits common attributes, message/frame containers, byte sequences, and
            string renderings while avoiding cycles and preserving both printable and hex forms.
        """
        texts: list[str] = []
        visited: set[int] = set()

        def append_text(value: str) -> None:
            """
            Append a non-empty raw response candidate to the local extraction list.

            Implementation details:
                Keeps the nested extractor small by centralizing the truthiness check before adding
                text to the shared list.
            """
            if value:
                texts.append(value)

        def visit(value: Any, depth: int = 0) -> None:
            """
            Recursively walk an unknown response object and collect response-like text.

            Implementation details:
                Handles strings, bytes, collections, common raw/data/value attributes, message
                containers, and hex-looking string representations with a depth and cycle guard.
            """
            if value is None or depth > 6:
                return
            if not isinstance(value, (str, bytes, bytearray, int, float, bool)):
                ident = id(value)
                if ident in visited:
                    return
                visited.add(ident)

            if isinstance(value, str):
                append_text(value)
                return
            if isinstance(value, (bytes, bytearray)):
                raw_bytes = bytes(value)
                decoded = ""
                try:
                    decoded = raw_bytes.decode("ascii", "ignore").strip()
                except Exception:
                    decoded = ""
                printable = bool(decoded) and sum(32 <= b <= 126 or b in (9, 10, 13) for b in raw_bytes) >= max(1, int(len(raw_bytes) * 0.85))
                if printable:
                    append_text(decoded)
                    if not self._looks_like_hex_response(decoded):
                        append_text(raw_bytes.hex(" ").upper())
                else:
                    append_text(raw_bytes.hex(" ").upper())
                return
            if isinstance(value, (list, tuple, set)):
                if value and all(isinstance(x, int) for x in value):
                    raw_bytes = bytes(int(x) & 0xFF for x in value)
                    decoded = ""
                    try:
                        decoded = raw_bytes.decode("ascii", "ignore").strip()
                    except Exception:
                        decoded = ""
                    printable = bool(decoded) and sum(32 <= b <= 126 or b in (9, 10, 13) for b in raw_bytes) >= max(1, int(len(raw_bytes) * 0.85))
                    if printable and self._looks_like_hex_response(decoded):
                        append_text(decoded)
                    else:
                        append_text(" ".join(f"{int(x) & 0xFF:02X}" for x in value))
                else:
                    for item in value:
                        visit(item, depth + 1)
                return

            for attr in ("raw", "data", "value", "bytes", "hex"):
                try:
                    attr_value = getattr(value, attr, None)
                except Exception:
                    continue
                if callable(attr_value) and attr in {"raw", "hex"}:
                    try:
                        attr_value = attr_value()
                    except Exception:
                        continue
                visit(attr_value, depth + 1)

            for attr in ("messages", "frames"):
                try:
                    visit(getattr(value, attr, None), depth + 1)
                except Exception:
                    pass

            dct = getattr(value, "__dict__", None)
            if isinstance(dct, dict):
                for key, item in dct.items():
                    if key.lower() in {"raw", "data", "value", "bytes", "messages", "frames", "response"}:
                        visit(item, depth + 1)

            try:
                rendered = str(value)
            except Exception:
                rendered = ""
            if self._looks_like_hex_response(rendered):
                append_text(rendered)

        visit(raw)

        deduped: list[str] = []
        seen: set[str] = set()
        for text in texts:
            cleaned = text.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                deduped.append(cleaned)
        return deduped

    def _parse_dtc_response(self, request_mode: str, raw: str) -> list[str]:
        """
        Parse a raw Mode 03, 07, or 0A response into DTC codes.

        Implementation details:
            First accepts already-textual codes, then cleans the payload, locates the matching
            response mode byte, and decodes the remaining data as two-byte DTC records.
        """
        textual_codes = self._extract_textual_dtc_codes(raw)
        if textual_codes:
            return textual_codes

        cleaned = self._clean_hex_payload(raw)
        if not cleaned:
            return []

        response_mode = {
            "03": "43",
            "07": "47",
            "0A": "4A",
        }.get(request_mode, "")
        if not response_mode:
            return []

        payloads: list[str] = []
        start = cleaned.find(response_mode)
        if start >= 0:
            payloads.append(cleaned[start + len(response_mode) :])

        if start < 0:
            payloads.append(cleaned)

        for payload in payloads:
            codes = self._decode_dtc_payload(payload)
            if codes:
                return codes
        return []

    def _clean_hex_payload(self, raw: str) -> str:
        """
        Normalize a raw adapter response into a continuous uppercase hex string.

        Implementation details:
            Removes separators and prompts, detects responses that were double-encoded as ASCII hex
            bytes, and returns the cleaned payload used by the DTC parser.
        """
        cleaned = re.sub(r"[^0-9A-Fa-f]", "", raw).upper()
        if not cleaned:
            return ""

        if len(cleaned) % 2 == 0:
            try:
                as_bytes = bytes.fromhex(cleaned)
                decoded = as_bytes.decode("ascii", "ignore").strip()
            except Exception:
                decoded = ""
            if decoded and sum(32 <= b <= 126 or b in (9, 10, 13) for b in as_bytes) >= max(1, int(len(as_bytes) * 0.85)):
                decoded_cleaned = re.sub(r"[^0-9A-Fa-f]", "", decoded).upper()
                if any(marker in decoded_cleaned for marker in ("43", "47", "4A")):
                    return decoded_cleaned
        return cleaned

    def _decode_dtc_payload(self, payload: str) -> list[str]:
        """
        Decode the data bytes after a DTC response mode marker.

        Implementation details:
            Reads the payload in two-byte records, skips zero padding, stops at trailing zero fill,
            and converts valid byte pairs into P/B/C/U code strings.
        """
        if len(payload) % 2:
            payload = payload[:-1]

        codes: list[str] = []
        for i in range(0, len(payload) - 3, 4):
            pair = payload[i : i + 4]
            if len(pair) < 4:
                break
            if pair == "0000":
                if set(payload[i + 4 :]) <= {"0"}:
                    break
                continue
            try:
                first = int(pair[:2], 16)
                second = int(pair[2:], 16)
            except ValueError:
                continue
            code = self._decode_dtc_bytes(first, second)
            if code is not None:
                codes.append(code)
        return codes

    @staticmethod
    def _extract_textual_dtc_codes(raw: str) -> list[str]:
        """
        Find explicit DTC code strings already present in a response.

        Implementation details:
            Uses a bounded regular expression for P/B/C/U codes and preserves first-seen order while
            removing duplicates.
        """
        codes: list[str] = []
        seen: set[str] = set()
        for match in re.finditer(r"(?<![A-Z0-9])([PCBU][0-3][0-9A-F]{3})(?![A-Z0-9])", raw.upper()):
            code = match.group(1)
            if code not in seen:
                seen.add(code)
                codes.append(code)
        return codes

    def _is_related_empty_dtc_response(self, request_mode: str, raw: str) -> bool:
        """
        Detect an empty response for the requested DTC service.

        Implementation details:
            Looks for the matching response mode byte and confirms the remaining payload is all zero
            padding, or accepts all-zero bare payloads as empty.
        """
        cleaned = self._clean_hex_payload(raw)
        response_mode = {"03": "43", "07": "47", "0A": "4A"}.get(request_mode, "")
        if not cleaned or not response_mode:
            return False
        if response_mode in cleaned:
            payload = cleaned[cleaned.find(response_mode) + 2 :]
            return bool(payload) and set(payload) <= {"0"}
        return len(cleaned) >= 4 and set(cleaned) <= {"0"}

    @staticmethod
    def _is_clear_ack(raw: str) -> bool:
        """
        Detect acknowledgement of a clear-DTC request.

        Implementation details:
            Cleans the response to hex and checks for the Mode 04 positive response byte, 44.
        """
        cleaned = re.sub(r"[^0-9A-Fa-f]", "", raw).upper()
        return "44" in cleaned

    @staticmethod
    def _looks_like_hex_response(text: str) -> bool:
        """
        Decide whether text resembles an OBD/ELM hex response.

        Implementation details:
            Strips non-hex characters and checks for known positive response markers used by DTC,
            clear-DTC, or supported-PID replies.
        """
        cleaned = re.sub(r"[^0-9A-Fa-f]", "", text).upper()
        return len(cleaned) >= 2 and any(marker in cleaned for marker in ("43", "44", "47", "4A", "4100"))

    @staticmethod
    def _decode_dtc_bytes(first: int, second: int) -> str | None:
        """
        Convert one two-byte DTC record into a five-character code.

        Implementation details:
            Uses the high bits of the first byte for the P/B/C/U system and the remaining nibbles
            for the four hexadecimal digits.
        """
        system = "PCBU"[(first >> 6) & 0x03]
        digit1 = (first >> 4) & 0x03
        digit2 = first & 0x0F
        digit3 = (second >> 4) & 0x0F
        digit4 = second & 0x0F
        return f"{system}{digit1:X}{digit2:X}{digit3:X}{digit4:X}"

    @staticmethod
    def _dedupe(entries: list[DtcEntry]) -> list[DtcEntry]:
        """
        Remove duplicate DTC rows while preserving display order.

        Implementation details:
            Tracks category/code keys and keeps the first occurrence so repeated reads from python-
            OBD and raw fallback do not duplicate UI rows.
        """
        seen: set[tuple[str, str]] = set()
        out: list[DtcEntry] = []
        for entry in entries:
            key = (entry.category.value, entry.code)
            if key in seen:
                continue
            seen.add(key)
            out.append(entry)
        return out
