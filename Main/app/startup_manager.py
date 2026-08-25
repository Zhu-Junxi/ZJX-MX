from __future__ import annotations

import os
import plistlib
import shlex
import sys
from pathlib import Path

from PySide6.QtCore import QSettings

from app.app_info import APP_DESCRIPTION, APP_INTERNAL_NAME, APP_NAME, APP_ORGANIZATION


class StartupManager:
    """Manage per-user startup registration for the current app install."""

    RUN_KEY_PATH = r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run"
    LINUX_DESKTOP_FILE = f"{APP_INTERNAL_NAME}.desktop"
    MACOS_LAUNCH_AGENT = "com.zjx.zjx-lms.plist"

    def __init__(self):
        self._last_error = ""
        self._settings = QSettings(self.RUN_KEY_PATH, QSettings.Format.NativeFormat) if self._is_windows() else None

    def platform_name(self):
        if self._is_windows():
            return "Windows"
        if self._is_macos():
            return "macOS"
        if self._is_linux_desktop():
            return "Linux"
        return "Unsupported"

    def registration_target(self):
        if self._is_windows():
            return self.RUN_KEY_PATH
        if self._is_macos():
            return str(self._macos_launch_agent_path())
        if self._is_linux_desktop():
            return str(self._linux_autostart_path())
        return "Unavailable"

    def capability_note(self):
        if self._is_windows():
            return "Windows Run-key registration"
        if self._is_macos():
            return "macOS LaunchAgent registration"
        if self._is_linux_desktop():
            return "freedesktop XDG Autostart registration"
        return "Startup registration is unavailable on this operating system"

    def startup_command(self):
        return self._command_string(self.startup_arguments())

    def startup_arguments(self):
        if getattr(sys, "frozen", False):
            return [str(Path(sys.executable).resolve()), "--startup"]

        script_path = Path(__file__).resolve().parents[1] / "main.py"
        executable = self._preferred_pythonw() if self._is_windows() else Path(sys.executable).resolve()
        return [str(executable), str(script_path), "--startup"]

    def is_supported(self):
        return self._is_windows() or self._is_macos() or self._is_linux_desktop()

    def is_enabled(self):
        if not self.is_supported():
            return False
        try:
            if self._is_windows():
                value = str(self._settings.value(APP_INTERNAL_NAME, "") or "").strip()
                return self._commands_match(value, self.startup_command())
            if self._is_macos():
                return self._macos_is_enabled()
            if self._is_linux_desktop():
                return self._linux_is_enabled()
        except Exception as exc:
            self._set_error(exc)
        return False

    def enable(self):
        if not self.is_supported():
            self._last_error = "Startup registration is not supported on this operating system."
            return False
        try:
            if self._is_windows():
                self._settings.setValue(APP_INTERNAL_NAME, self.startup_command())
            elif self._is_macos():
                self._write_macos_launch_agent()
            else:
                self._write_linux_desktop_file()
            self._last_error = ""
            return True
        except Exception as exc:
            self._set_error(exc)
            return False

    def disable(self):
        if not self.is_supported():
            self._last_error = "Startup registration is not supported on this operating system."
            return False
        try:
            if self._is_windows():
                self._settings.remove(APP_INTERNAL_NAME)
            elif self._is_macos():
                self._remove_file(self._macos_launch_agent_path())
            else:
                self._remove_file(self._linux_autostart_path())
            self._last_error = ""
            return True
        except Exception as exc:
            self._set_error(exc)
            return False

    def sync_enabled_state(self, enabled):
        return self.enable() if enabled else self.disable()

    def last_error(self):
        return self._last_error

    def display_name(self):
        return APP_NAME

    def _linux_is_enabled(self):
        path = self._linux_autostart_path()
        if not path.exists():
            return False
        content = path.read_text(encoding="utf-8")
        if self._desktop_value(content, "Hidden").lower() == "true":
            return False
        exec_value = self._desktop_value(content, "Exec")
        return self._commands_match(exec_value, self.startup_command())

    def _write_linux_desktop_file(self):
        path = self._linux_autostart_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._linux_desktop_file_content(), encoding="utf-8")

    def _linux_desktop_file_content(self):
        return "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                f"Name={APP_NAME}",
                f"Comment={APP_DESCRIPTION}",
                f"Exec={self.startup_command()}",
                "Terminal=false",
                "X-GNOME-Autostart-enabled=true",
                "",
            ]
        )

    def _desktop_value(self, content, key):
        prefix = f"{key}="
        for line in content.splitlines():
            if line.strip().startswith(prefix):
                return line.split("=", 1)[1].strip()
        return ""

    def _linux_autostart_path(self):
        config_home = os.environ.get("XDG_CONFIG_HOME")
        base = Path(config_home).expanduser() if config_home else Path.home() / ".config"
        return base / "autostart" / self.LINUX_DESKTOP_FILE

    def _macos_is_enabled(self):
        path = self._macos_launch_agent_path()
        if not path.exists():
            return False
        data = plistlib.loads(path.read_bytes())
        return data.get("ProgramArguments") == self.startup_arguments()

    def _write_macos_launch_agent(self):
        path = self._macos_launch_agent_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "Label": "com.zjx.zjx-lms",
            "ProgramArguments": self.startup_arguments(),
            "RunAtLoad": True,
            "KeepAlive": False,
            "StandardErrorPath": str(Path.home() / "Library" / "Logs" / "ZJX-LMS-startup.err.log"),
            "StandardOutPath": str(Path.home() / "Library" / "Logs" / "ZJX-LMS-startup.out.log"),
        }
        path.write_bytes(plistlib.dumps(data, sort_keys=False))

    def _macos_launch_agent_path(self):
        return Path.home() / "Library" / "LaunchAgents" / self.MACOS_LAUNCH_AGENT

    def _preferred_pythonw(self):
        executable = Path(sys.executable).resolve()
        if executable.name.lower() == "pythonw.exe":
            return executable
        pythonw_candidate = executable.with_name("pythonw.exe")
        if pythonw_candidate.exists():
            return pythonw_candidate
        return executable

    def _command_string(self, arguments):
        if self._is_windows():
            return " ".join(self._windows_quote(argument) for argument in arguments)
        if self._is_linux_desktop():
            return " ".join(self._desktop_exec_quote(argument) for argument in arguments)
        return " ".join(shlex.quote(str(argument)) for argument in arguments)

    def _commands_match(self, registered, expected):
        return str(registered or "").strip() == str(expected or "").strip()

    def _windows_quote(self, value):
        text = os.fspath(value)
        if text.startswith('"') and text.endswith('"'):
            return text
        return f'"{text}"'

    def _desktop_exec_quote(self, value):
        text = os.fspath(value)
        if text and all(char not in text for char in " \t\n\"'\\`$"):
            return text
        escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
        return f'"{escaped}"'

    def _remove_file(self, path):
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def _set_error(self, exc):
        self._last_error = str(exc) or exc.__class__.__name__

    def _is_windows(self):
        return sys.platform.startswith("win")

    def _is_macos(self):
        return sys.platform == "darwin"

    def _is_linux_desktop(self):
        return sys.platform.startswith("linux") or sys.platform.startswith(("freebsd", "openbsd", "netbsd"))
