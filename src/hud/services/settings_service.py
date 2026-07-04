from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from hud.models.settings import AppSettings


class SettingsService:
    """
    Load, save, and manage application settings and presets.

    Implementation details:
        Resolves config paths, serializes AppSettings to JSON, and stores presets in a dedicated
        presets folder.
    """
    def __init__(self, base_dir: Path, presets_dir: Path | None = None) -> None:
        """
        Handle init behavior for SettingsService.

        Implementation details:
            Coordinates file, settings, or adapter state through a small service-layer API.
        """
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.base_dir / "settings.json"

        # Presets are intentionally stored next to the app/current working
        # folder instead of being hidden in the user profile. This makes them
        # easy to back up, copy, or ship with a portable HUD folder.
        legacy_presets_dir = self.base_dir / "presets"
        self.presets_dir = presets_dir or legacy_presets_dir
        self.presets_dir.mkdir(parents=True, exist_ok=True)
        if self.presets_dir != legacy_presets_dir and legacy_presets_dir.exists() and not any(self.presets_dir.glob("*.json")):
            for source in legacy_presets_dir.glob("*.json"):
                try:
                    shutil.copy2(source, self.presets_dir / source.name)
                except Exception:
                    pass
        self._settings = self.load()

    @property
    def settings(self) -> AppSettings:
        """
        Return the currently loaded application settings object.

        Implementation details:
            Returns the cached settings object owned by the service.
        """
        return self._settings

    def load(self) -> AppSettings:
        """
        Load application settings from persistent storage.

        Implementation details:
            Reads JSON when present, falls back to defaults on missing or invalid files, and caches
            the result.
        """
        if not self.settings_path.exists():
            return AppSettings()
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return AppSettings.from_dict(data)
        except Exception:
            return AppSettings()

    def save(self) -> None:
        """
        Persist the current application settings to disk.

        Implementation details:
            Creates the config directory when needed and writes the serialized settings JSON.
        """
        self.base_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._settings.to_dict(), indent=2, ensure_ascii=False)
        tmp_name = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.base_dir, prefix="settings_", suffix=".json", delete=False) as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
                tmp_name = fh.name
            os.replace(tmp_name, self.settings_path)
            return
        except Exception:
            pass
        try:
            with open(self.settings_path, "w", encoding="utf-8") as fh:
                fh.write(payload)
        except Exception:
            pass
        finally:
            if tmp_name:
                try:
                    Path(tmp_name).unlink(missing_ok=True)
                except Exception:
                    pass

    def update(self, new_settings: AppSettings) -> None:
        """
        Replace the in-memory application settings with a new value.

        Implementation details:
            Stores the provided settings object and immediately persists it.
        """
        self._settings = new_settings
        self.save()

    def save_preset(self, name: str, settings: AppSettings | None = None) -> None:
        """
        Save the current settings under a reusable preset name.

        Implementation details:
            Sanitizes the preset name and writes the current settings to the presets directory.
        """
        safe_name = ''.join(ch for ch in name if ch not in '<>:"/|?*').strip() or 'preset'
        target = self.presets_dir / f"{safe_name}.json"
        payload = (settings or self._settings).to_dict()
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        if safe_name not in self._settings.preset_names:
            self._settings.preset_names.append(safe_name)
            self.save()

    def load_preset(self, name: str) -> AppSettings:
        """
        Load a named preset into an AppSettings instance.

        Implementation details:
            Reads the selected preset JSON and converts it into AppSettings.
        """
        safe_name = ''.join(ch for ch in name if ch not in '<>:"/|?*').strip() or 'preset'
        target = self.presets_dir / f"{safe_name}.json"
        data = json.loads(target.read_text(encoding="utf-8"))
        settings = AppSettings.from_dict(data)
        self.update(settings)
        return settings

    def delete_preset(self, name: str) -> bool:
        """
        Remove a saved preset from disk.

        Implementation details:
            Deletes the preset file if it exists and leaves other presets untouched.
        """
        safe_name = ''.join(ch for ch in name if ch not in '<>:"/|?*').strip() or 'preset'
        target = self.presets_dir / f"{safe_name}.json"
        try:
            target.unlink(missing_ok=True)
        except Exception:
            return False
        self._settings.preset_names = [n for n in self._settings.preset_names if n != safe_name]
        self.save()
        return True

    def list_presets(self) -> list[str]:
        """
        List the available saved presets.

        Implementation details:
            Scans the presets directory and returns preset file stems in sorted order.
        """
        names = sorted(p.stem for p in self.presets_dir.glob("*.json"))
        self._settings.preset_names = names
        return names
