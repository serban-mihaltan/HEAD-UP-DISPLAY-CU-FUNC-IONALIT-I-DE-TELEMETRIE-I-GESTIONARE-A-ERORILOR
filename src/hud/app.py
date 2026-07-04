from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from hud.services.settings_service import SettingsService
from hud.ui.main_window import MainWindow


def main() -> int:
    """
    Start the HUD application process.

    Implementation details:
        Creates QApplication and MainWindow, shows the window, and starts the Qt event loop.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Automotive HUD")
    

    app_folder = Path(sys.argv[0]).resolve().parent
    if not (app_folder / "src").exists() and (Path.cwd() / "src").exists():
        app_folder = Path.cwd()
    settings = SettingsService(Path.home() / ".automotive_hud", app_folder / "presets")
    window = MainWindow(settings)
    window.show()
    return app.exec()
