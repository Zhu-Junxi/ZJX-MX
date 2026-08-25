from __future__ import annotations

import os
import sys

from PySide6.QtWidgets import QSystemTrayIcon


class PlatformCapabilities:
    """Runtime OS and desktop-session capabilities used for graceful fallbacks."""

    def __init__(self, *, environ=None, tray_available=None, tray_messages_supported=None):
        self.environ = dict(os.environ if environ is None else environ)
        self.os_name = self._detect_os_name()
        self.desktop = self._normalise_desktop(self.environ.get("XDG_CURRENT_DESKTOP") or self.environ.get("DESKTOP_SESSION") or "")
        self.desktop_session = str(self.environ.get("DESKTOP_SESSION") or "")
        self.session_type = str(self.environ.get("XDG_SESSION_TYPE") or "").lower()
        self.wayland = bool(self.environ.get("WAYLAND_DISPLAY")) or self.session_type == "wayland"
        self.x11 = bool(self.environ.get("DISPLAY")) or self.session_type == "x11"
        self.tray_available = QSystemTrayIcon.isSystemTrayAvailable() if tray_available is None else bool(tray_available)
        self.tray_messages_supported = QSystemTrayIcon.supportsMessages() if tray_messages_supported is None else bool(tray_messages_supported)

    def platform_label(self):
        if self.os_name != "Linux":
            return self.os_name
        parts = ["Linux"]
        if self.desktop:
            parts.append(self.desktop)
        if self.session_type:
            parts.append(self.session_type.upper())
        return " / ".join(parts)

    def tray_status_text(self):
        if self.tray_available and self.tray_messages_supported:
            return "available with native notification messages"
        if self.tray_available:
            return "available, but native notification messages are not reported as supported"
        if self.os_name == "Linux":
            return self._linux_tray_unavailable_text()
        return "unavailable in this session"

    def startup_support_note(self):
        if self.os_name == "Windows":
            return "Windows Run-key registration"
        if self.os_name == "macOS":
            return "macOS LaunchAgent registration"
        if self.os_name == "Linux":
            return "freedesktop XDG Autostart registration"
        return "Startup registration is unavailable on this operating system"

    def close_to_tray_supported(self):
        return self.tray_available

    def native_reminders_supported(self):
        return self.tray_available and self.tray_messages_supported

    def _linux_tray_unavailable_text(self):
        desktop = self.desktop.lower()
        if "gnome" in desktop:
            return "unavailable; GNOME sessions often need an AppIndicator or tray shell extension"
        if self.wayland:
            return "unavailable in this Wayland session"
        if self.x11:
            return "unavailable in this X11 session"
        return "unavailable in this desktop session"

    def _detect_os_name(self):
        if sys.platform.startswith("win"):
            return "Windows"
        if sys.platform == "darwin":
            return "macOS"
        if sys.platform.startswith("linux"):
            return "Linux"
        return "Unsupported"

    def _normalise_desktop(self, value):
        tokens = [part.strip() for part in str(value or "").replace(":", ";").split(";") if part.strip()]
        if not tokens:
            return ""
        names = {
            "kde": "KDE Plasma",
            "plasma": "KDE Plasma",
            "gnome": "GNOME",
            "xfce": "Xfce",
            "lxqt": "LXQt",
            "cinnamon": "Cinnamon",
            "mate": "MATE",
            "deepin": "DDE",
            "dde": "DDE",
        }
        normalised = [names.get(token.lower(), token) for token in tokens]
        return ", ".join(dict.fromkeys(normalised))
