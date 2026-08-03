from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QSettings

from app.app_info import APP_INTERNAL_NAME, APP_NAME


class StartupManager:
    """Manage Windows startup registration for the current app install."""

    RUN_KEY_PATH = r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run"

    def __init__(self):
        self._settings = QSettings(self.RUN_KEY_PATH, QSettings.Format.NativeFormat)

    def is_supported(self):
        return sys.platform.startswith("win")

    def startup_command(self):
        if getattr(sys, "frozen", False):
            executable = Path(sys.executable).resolve()
            return self._quote(executable) + " --startup"

        script_path = Path(__file__).resolve().parents[1] / "main.py"
        python_executable = self._preferred_pythonw()
        return f"{self._quote(python_executable)} {self._quote(script_path)} --startup"

    def is_enabled(self):
        if not self.is_supported():
            return False
        value = str(self._settings.value(APP_INTERNAL_NAME, "") or "").strip()
        return bool(value)

    def enable(self):
        if not self.is_supported():
            return False
        self._settings.setValue(APP_INTERNAL_NAME, self.startup_command())
        return True

    def disable(self):
        if not self.is_supported():
            return False
        self._settings.remove(APP_INTERNAL_NAME)
        return True

    def sync_enabled_state(self, enabled):
        return self.enable() if enabled else self.disable()

    def display_name(self):
        return APP_NAME

    def _preferred_pythonw(self):
        executable = Path(sys.executable).resolve()
        if executable.name.lower() == "pythonw.exe":
            return executable
        pythonw_candidate = executable.with_name("pythonw.exe")
        if pythonw_candidate.exists():
            return pythonw_candidate
        return executable

    def _quote(self, value):
        text = os.fspath(value)
        if text.startswith('"') and text.endswith('"'):
            return text
        return f'"{text}"'
