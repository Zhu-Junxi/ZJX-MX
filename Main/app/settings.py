from pathlib import Path
import json
import time

from PySide6.QtCore import QSettings

from core.dashboard.dashboard_settings import (
    load_dashboard_settings,
    save_dashboard_settings,
)


class AppSettings:
    """Small wrapper around QSettings for persistent app state."""

    def __init__(self):
        # Keep the original QSettings namespace so existing local installs keep
        # their saved vault path and selected user/course context after upgrades.
        self.settings = QSettings("ManagementHub", "LearningFileManager")
        self.default_vault_path = Path.home() / "ZJX-LMS"
        self.legacy_default_vault_path = Path.home() / "LearningVault"
        self.default_accent_color = "#2563eb"

    def get_vault_path(self):
        saved_path = self.settings.value("vault_path")

        if saved_path:
            vault_path = Path(saved_path)

            # Migrate the old bundled default name to the new default without
            # touching genuinely custom vault locations.
            if vault_path == self.legacy_default_vault_path:
                vault_path = self.default_vault_path
                self.settings.setValue("vault_path", str(vault_path))
        else:
            vault_path = self.default_vault_path
            self.settings.setValue("vault_path", str(vault_path))

        vault_path.mkdir(parents=True, exist_ok=True)
        return vault_path

    def set_vault_path(self, path):
        vault_path = Path(path)
        vault_path.mkdir(parents=True, exist_ok=True)
        self.settings.setValue("vault_path", str(vault_path))
        return vault_path

    def get_current_user_id(self):
        return self.settings.value("current_user_id")

    def set_current_user_id(self, user_id):
        if user_id:
            self.settings.setValue("current_user_id", user_id)
        else:
            self.settings.remove("current_user_id")

    def get_current_course_id(self):
        return self.settings.value("current_course_id")

    def set_current_course_id(self, course_id):
        if course_id:
            self.settings.setValue("current_course_id", course_id)
        else:
            self.settings.remove("current_course_id")

    def get_current_assignment_id(self):
        return self.settings.value("current_assignment_id")

    def set_current_assignment_id(self, assignment_id):
        if assignment_id:
            self.settings.setValue("current_assignment_id", assignment_id)
        else:
            self.settings.remove("current_assignment_id")

    def get_history_panel_visible(self):
        value = self.settings.value("history_panel_visible", True)

        if isinstance(value, bool):
            return value

        if value is None:
            return True

        return str(value).lower() not in {"false", "0", "no", "off"}

    def set_history_panel_visible(self, visible):
        self.settings.setValue("history_panel_visible", bool(visible))

    def get_onboarding_completed(self):
        value = self.settings.value("onboarding_completed", False)

        if isinstance(value, bool):
            return value

        return str(value).lower() in {"true", "1", "yes", "on"}

    def set_onboarding_completed(self, completed):
        self.settings.setValue("onboarding_completed", bool(completed))

    def get_main_splitter_state(self):
        return self.settings.value("main_splitter_state")

    def set_main_splitter_state(self, state):
        if state is not None:
            self.settings.setValue("main_splitter_state", state)

    def get_sidebar_width(self, default=300):
        return self._bounded_int_value("sidebar_width", default, 240, 520)

    def set_sidebar_width(self, width):
        self.settings.setValue("sidebar_width", max(240, min(520, int(width))))

    def get_window_size(self):
        width = self._bounded_int_value("window_width", 0, 0, 10000)
        height = self._bounded_int_value("window_height", 0, 0, 10000)
        return (width, height) if width and height else None

    def set_window_size(self, width, height):
        self.settings.setValue("window_width", max(640, int(width)))
        self.settings.setValue("window_height", max(480, int(height)))

    def get_ui_zoom_percent(self):
        return self._bounded_int_value("ui_zoom_percent", 100, 60, 200)

    def set_ui_zoom_percent(self, percent):
        try:
            percent = int(percent)
        except (TypeError, ValueError):
            percent = 100
        percent = max(60, min(200, percent))
        self.settings.setValue("ui_zoom_percent", percent)
        return percent

    def get_font_style(self):
        value = str(self.settings.value("font_style", "default") or "default").lower()
        return value if value in {"default", "monospace"} else "default"

    def set_font_style(self, style):
        value = str(style or "default").lower()
        if value not in {"default", "monospace"}:
            value = "default"
        self.settings.setValue("font_style", value)
        return value


    def get_scroll_speed_percent(self):
        value = self.settings.value("scroll_speed_percent", 45)

        try:
            value = int(value)
        except (TypeError, ValueError):
            value = 45

        return max(10, min(300, value))

    def set_scroll_speed_percent(self, percent):
        try:
            percent = int(percent)
        except (TypeError, ValueError):
            percent = 45

        percent = max(10, min(300, percent))
        self.settings.setValue("scroll_speed_percent", percent)
        return percent

    def get_smooth_scrolling_enabled(self):
        value = self.settings.value("smooth_scrolling_enabled", True)

        if isinstance(value, bool):
            return value

        return str(value).lower() not in {"false", "0", "no", "off"}

    def set_smooth_scrolling_enabled(self, enabled):
        self.settings.setValue("smooth_scrolling_enabled", bool(enabled))
        return bool(enabled)

    def get_canvas_auto_sync_enabled(self):
        value = self.settings.value("canvas_auto_sync_enabled", False)

        if isinstance(value, bool):
            return value

        return str(value).lower() in {"true", "1", "yes", "on"}

    def set_canvas_auto_sync_enabled(self, enabled):
        self.settings.setValue("canvas_auto_sync_enabled", bool(enabled))
        return bool(enabled)

    def get_notifications_enabled(self):
        return self._bool_value("notifications_enabled", True)

    def set_notifications_enabled(self, enabled):
        self.settings.setValue("notifications_enabled", bool(enabled))
        return bool(enabled)

    def get_run_on_startup_enabled(self):
        return self._bool_value("run_on_startup_enabled", False)

    def set_run_on_startup_enabled(self, enabled):
        self.settings.setValue("run_on_startup_enabled", bool(enabled))
        return bool(enabled)

    def get_startup_launch_mode(self):
        value = str(self.settings.value("startup_launch_mode", "background_to_tray") or "background_to_tray")
        return value if value in {"background_to_tray", "open_dashboard"} else "background_to_tray"

    def set_startup_launch_mode(self, mode):
        mode = str(mode or "background_to_tray")
        if mode not in {"background_to_tray", "open_dashboard"}:
            mode = "background_to_tray"
        self.settings.setValue("startup_launch_mode", mode)
        return mode

    def get_tray_enabled(self):
        return self._bool_value("tray_enabled", True)

    def set_tray_enabled(self, enabled):
        self.settings.setValue("tray_enabled", bool(enabled))
        return bool(enabled)

    def get_close_action(self):
        value = str(self.settings.value("close_action", "ask") or "ask")
        return value if value in {"ask", "minimize_to_tray", "quit"} else "ask"

    def set_close_action(self, action):
        action = str(action or "ask")
        if action not in {"ask", "minimize_to_tray", "quit"}:
            action = "ask"
        self.settings.setValue("close_action", action)
        return action

    def get_reminder_poll_minutes(self):
        return self._bounded_int_value("reminder_poll_minutes", 5, 1, 120)

    def set_reminder_poll_minutes(self, minutes):
        try:
            minutes = int(minutes)
        except (TypeError, ValueError):
            minutes = 5
        minutes = max(1, min(120, minutes))
        self.settings.setValue("reminder_poll_minutes", minutes)
        return minutes

    def get_reminder_stages(self):
        raw = self.settings.value("reminder_stages")
        default = ["7d", "3d", "1d", "6h", "1h", "overdue"]
        if not raw:
            return default
        try:
            stages = json.loads(raw) if isinstance(raw, str) else list(raw)
        except Exception:
            return default
        allowed = {"7d", "3d", "1d", "6h", "1h", "overdue"}
        stages = [stage for stage in stages if stage in allowed]
        return stages or default

    def set_reminder_stages(self, stages):
        allowed = {"7d", "3d", "1d", "6h", "1h", "overdue"}
        stages = [stage for stage in stages if stage in allowed] or ["7d", "3d", "1d", "6h", "1h", "overdue"]
        self.settings.setValue("reminder_stages", json.dumps(stages))
        return stages

    def get_reminder_snoozed_until(self):
        try:
            return float(self.settings.value("reminder_snoozed_until", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def set_reminder_snoozed_until(self, timestamp):
        try:
            timestamp = float(timestamp)
        except (TypeError, ValueError):
            timestamp = 0
        self.settings.setValue("reminder_snoozed_until", max(0, timestamp))
        return max(0, timestamp)

    def reminders_are_snoozed(self):
        return self.get_reminder_snoozed_until() > time.time()

    def get_sent_reminder_keys(self):
        raw = self.settings.value("sent_reminder_keys", "[]")
        try:
            keys = json.loads(raw) if isinstance(raw, str) else list(raw)
        except Exception:
            keys = []
        return {str(key) for key in keys}

    def set_sent_reminder_keys(self, keys):
        keys = sorted({str(key) for key in keys})
        self.settings.setValue("sent_reminder_keys", json.dumps(keys[-1000:]))
        return set(keys[-1000:])

    def add_sent_reminder_keys(self, keys):
        current = self.get_sent_reminder_keys()
        current.update(str(key) for key in keys)
        return self.set_sent_reminder_keys(current)

    def clear_sent_reminder_keys(self):
        self.settings.setValue("sent_reminder_keys", "[]")

    def _bool_value(self, key, default=False):
        value = self.settings.value(key, default)

        if isinstance(value, bool):
            return value

        return str(value).lower() in {"true", "1", "yes", "on"}

    def _bounded_int_value(self, key, default, minimum, maximum):
        value = self.settings.value(key, default)

        try:
            value = int(value)
        except (TypeError, ValueError):
            value = default

        return max(minimum, min(maximum, value))

    def _context_key(self, prefix, *parts):
        safe_parts = [
            str(part or "none").replace("/", "_").replace("\\", "_")
            for part in parts
        ]
        return "/".join([prefix] + safe_parts)

    def get_course_announcements_collapsed(self, user_id, course_id):
        return self._bool_value(
            self._context_key("course_announcements_collapsed", user_id, course_id),
            False,
        )

    def set_course_announcements_collapsed(self, user_id, course_id, collapsed):
        self.settings.setValue(
            self._context_key("course_announcements_collapsed", user_id, course_id),
            bool(collapsed),
        )
        return bool(collapsed)

    def get_course_announcements_panel_visible(self):
        return self._bool_value("course_announcements_panel_visible", True)

    def set_course_announcements_panel_visible(self, visible):
        self.settings.setValue("course_announcements_panel_visible", bool(visible))
        return bool(visible)

    def get_due_countdown_hours_threshold(self):
        return self._bounded_int_value("due_countdown_hours_threshold", 24, 1, 168)

    def get_due_countdown_minutes_threshold(self):
        return self._bounded_int_value("due_countdown_minutes_threshold", 60, 1, 240)

    def get_due_countdown_seconds_threshold(self):
        return self._bounded_int_value("due_countdown_seconds_threshold", 60, 0, 300)

    def set_due_countdown_thresholds(self, hours, minutes, seconds):
        hours = max(1, min(168, int(hours)))
        minutes = max(1, min(240, int(minutes)))
        seconds = max(0, min(300, int(seconds)))

        self.settings.setValue("due_countdown_hours_threshold", hours)
        self.settings.setValue("due_countdown_minutes_threshold", minutes)
        self.settings.setValue("due_countdown_seconds_threshold", seconds)
        return hours, minutes, seconds

    def get_deadline_dashboard_settings(self, user_id):
        return load_dashboard_settings(self.settings, user_id)

    def set_deadline_dashboard_settings(self, user_id, settings):
        return save_dashboard_settings(self.settings, user_id, settings)

    def get_theme_mode(self):
        mode = str(self.settings.value("theme_mode", "dark") or "dark").lower()
        return mode if mode in {"dark", "light"} else "dark"

    def set_theme_mode(self, mode):
        mode = str(mode or "dark").lower()
        if mode not in {"dark", "light"}:
            mode = "dark"
        self.settings.setValue("theme_mode", mode)
        return mode

    def get_follow_system_theme(self):
        value = self.settings.value("follow_system_theme", False)
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"true", "1", "yes", "on"}

    def set_follow_system_theme(self, enabled):
        self.settings.setValue("follow_system_theme", bool(enabled))
        return bool(enabled)

    def get_accent_color(self):
        value = str(self.settings.value("accent_color", self.default_accent_color) or self.default_accent_color)
        return value if value.startswith("#") and len(value) in {4, 7, 9} else self.default_accent_color

    def set_accent_color(self, color):
        color = str(color or self.default_accent_color)
        if not color.startswith("#"):
            color = self.default_accent_color
        self.settings.setValue("accent_color", color)
        return color

    def reset_accent_color(self):
        self.settings.setValue("accent_color", self.default_accent_color)
        return self.default_accent_color
