from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem

from app.app_info import APP_NAME, APP_VERSION, APP_ORGANIZATION, APP_DESCRIPTION
from app.ui_content import SETTINGS_SECTIONS
from ui.browser_widgets import BrowserItemDelegate


class SettingsViewsMixin:
    """Settings list/detail rendering boundary."""

    def add_settings_header(self, text, description=""):
        item = QListWidgetItem()
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        item.setData(Qt.ItemDataRole.UserRole, {"type": "setting_header"})
        item.setData(BrowserItemDelegate.TITLE_ROLE, text)
        item.setData(BrowserItemDelegate.SUBTITLE_ROLE, description)
        item.setToolTip("\n".join(part for part in [text, description] if part))
        item.setSizeHint(self.scaled_size(260, 86))
        self.item_list.addItem(item)

    def add_settings_action(self, label, action, icon_name="settings", subtitle="", meta="", badge_text=""):
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, {"type": "setting", "action": action})
        item.setData(BrowserItemDelegate.TITLE_ROLE, label)
        item.setData(BrowserItemDelegate.SUBTITLE_ROLE, subtitle)
        item.setData(BrowserItemDelegate.META_ROLE, meta)
        item.setData(BrowserItemDelegate.BADGE_ROLE, badge_text)
        item.setData(
            BrowserItemDelegate.ACTIVE_ROLE,
            badge_text in {"ON", "ENABLED", "SHOWN", "DARK", "LIGHT"} or str(badge_text).startswith("#"),
        )
        item.setData(BrowserItemDelegate.ICON_NAME_ROLE, icon_name)
        item.setToolTip("\n".join(part for part in [label, subtitle, meta, badge_text] if part))
        item.setSizeHint(self.scaled_size(260, 118))
        self.item_list.addItem(item)

    def setting_action_badge(self, action_data):
        action = action_data.get("action")
        if action == "scroll_speed":
            return f"{self.get_scroll_speed_percent()}%"
        if action == "ui_zoom":
            return f"{self.ui_zoom_percent}%"
        if action == "smooth_scroll":
            return "ON" if self.get_smooth_scrolling_enabled() else "OFF"
        if action == "theme_mode":
            return self.effective_theme_mode().upper()
        if action == "follow_system_theme":
            return "ON" if self.app_settings.get_follow_system_theme() else "OFF"
        if action == "accent_colour":
            return self.app_settings.get_accent_color().upper()
        if action == "reset_accent_colour":
            default_colour = getattr(self.app_settings, "default_accent_color", "#2563eb")
            return "DEFAULT" if self.app_settings.get_accent_color().lower() == default_colour.lower() else "RESET"
        if action == "toggle_history_panel":
            return "SHOWN" if self.history_panel_visible else "HIDDEN"
        if action == "course_announcements_panel":
            return "SHOWN" if self.app_settings.get_course_announcements_panel_visible() else "HIDDEN"
        if action == "due_countdown_precision":
            return "TUNED"
        if action == "canvas_auto_sync":
            return "ON" if self.app_settings.get_canvas_auto_sync_enabled() else "OFF"
        if action == "canvas_blacklist":
            user = self.get_current_user()
            return f"{len(user.get('canvas_blacklisted_course_ids', [])) if user else 0} SKIP"
        if action == "canvas_favourites":
            user = self.get_current_user()
            return f"{len(user.get('canvas_favourite_course_ids', [])) if user else 0} PIN"
        if action == "canvas_sync_details":
            user = self.get_current_user()
            return "SYNCED" if user and user.get("canvas_last_sync_at") else "NEVER"
        if action == "run_on_startup":
            startup = getattr(self, "startup_manager", None)
            if startup and not startup.is_supported():
                return "UNAVAILABLE"
            return "ON" if self.app_settings.get_run_on_startup_enabled() else "OFF"
        if action == "startup_launch_mode":
            return "TRAY" if self.app_settings.get_startup_launch_mode() == "background_to_tray" else "DASHBOARD"
        if action == "notifications_enabled":
            return "ON" if self.app_settings.get_notifications_enabled() else "OFF"
        if action == "tray_enabled":
            tray = getattr(self, "tray_controller", None)
            if tray and not tray.tray_available:
                return "UNAVAILABLE"
            return "ON" if self.app_settings.get_tray_enabled() else "OFF"
        if action == "close_action":
            return self.app_settings.get_close_action().replace("_", " ").upper()
        if action == "reminder_schedule":
            return f"{self.app_settings.get_reminder_poll_minutes()}M"
        if action == "snooze_reminders":
            return "SNOOZED" if self.app_settings.reminders_are_snoozed() else "READY"
        if action == "app_info":
            return f"v{APP_VERSION}"
        return ""

    def setting_action_meta(self, action_data):
        action = action_data.get("action")
        if action == "scroll_speed":
            return f"Current: {self.get_scroll_speed_percent()}%"
        if action == "ui_zoom":
            return f"Current zoom: {self.ui_zoom_percent}%"
        if action == "smooth_scroll":
            return "Enabled: inertia scrolling is active" if self.get_smooth_scrolling_enabled() else "Disabled: classic stopping scroll"
        if action == "theme_mode":
            return f"Current: {self.effective_theme_mode().title()} mode"
        if action == "follow_system_theme":
            return "Enabled: follows OS theme" if self.app_settings.get_follow_system_theme() else "Disabled: manual theme mode"
        if action == "accent_colour":
            return f"Current accent: {self.app_settings.get_accent_color()}"
        if action == "reset_accent_colour":
            return f"Restore: {getattr(self.app_settings, 'default_accent_color', '#2563eb')}"
        if action == "toggle_history_panel":
            return "Enabled: Recent Changes panel is visible" if self.history_panel_visible else "Disabled: Recent Changes panel is hidden"
        if action == "course_announcements_panel":
            return "Shown on course dashboards" if self.app_settings.get_course_announcements_panel_visible() else "Hidden: assignments move up to reclaim space"
        if action == "due_countdown_precision":
            return (
                f"Days->hours under {self.app_settings.get_due_countdown_hours_threshold()}h; "
                f"hours->minutes under {self.app_settings.get_due_countdown_minutes_threshold()}m; "
                f"minutes->seconds under {self.app_settings.get_due_countdown_seconds_threshold()}s"
            )
        if action == "canvas_auto_sync":
            return "Enabled: sync runs after launch" if self.app_settings.get_canvas_auto_sync_enabled() else "Disabled: manual sync only"
        if action == "canvas_blacklist":
            user = self.get_current_user()
            return f"{len(user.get('canvas_blacklisted_course_ids', [])) if user else 0} course(s) skipped"
        if action == "canvas_favourites":
            user = self.get_current_user()
            return f"{len(user.get('canvas_favourite_course_ids', [])) if user else 0} course(s) pinned"
        if action == "canvas_sync_details":
            user = self.get_current_user()
            return f"Last sync: {(user or {}).get('canvas_last_sync_at') or 'Never'}"
        if action == "run_on_startup":
            startup = getattr(self, "startup_manager", None)
            if startup and not startup.is_supported():
                return "Unsupported on this operating system"
            return "Enabled: Windows launches ZJX LMS after sign-in" if self.app_settings.get_run_on_startup_enabled() else "Disabled: app only launches manually"
        if action == "startup_launch_mode":
            if self.app_settings.get_startup_launch_mode() == "background_to_tray":
                return "Startup launch stays hidden in the tray until you restore it"
            return "Startup launch opens the main window on the Dashboard page"
        if action == "notifications_enabled":
            return "Enabled: due-soon and overdue reminders can be shown" if self.app_settings.get_notifications_enabled() else "Disabled: reminders are paused"
        if action == "tray_enabled":
            tray = getattr(self, "tray_controller", None)
            if tray and not tray.tray_available:
                return "System tray is unavailable in this session"
            return "Enabled: close-to-tray and reminder popups are available" if self.app_settings.get_tray_enabled() else "Disabled: close exits normally"
        if action == "close_action":
            return f"Current: {self.app_settings.get_close_action().replace('_', ' ')}"
        if action == "reminder_schedule":
            return f"Every {self.app_settings.get_reminder_poll_minutes()} minute(s); stages: {', '.join(self.app_settings.get_reminder_stages())}"
        if action == "snooze_reminders":
            return "Reminders are currently snoozed" if self.app_settings.reminders_are_snoozed() else "Reminders are not snoozed"
        if action == "app_info":
            return f"{APP_NAME} {APP_VERSION} - {APP_ORGANIZATION}"
        return action_data.get("meta", "")

    def show_settings_section(self):
        self.item_list.clear()

        for section in SETTINGS_SECTIONS:
            self.add_settings_header(section["header"], section.get("description", ""))
            for action_data in section["actions"]:
                self.add_settings_action(
                    action_data["label"],
                    action_data["action"],
                    action_data.get("icon", "settings"),
                    subtitle=action_data.get("subtitle", ""),
                    meta=self.setting_action_meta(action_data),
                    badge_text=self.setting_action_badge(action_data),
                )

        history_state = "shown" if self.history_panel_visible else "hidden"
        theme_state = self.effective_theme_mode()
        follow_system_state = "on" if self.app_settings.get_follow_system_theme() else "off"
        accent_color = self.app_settings.get_accent_color()
        scroll_speed = self.get_scroll_speed_percent()
        ui_zoom = self.ui_zoom_percent
        smooth_scroll_state = "on" if self.get_smooth_scrolling_enabled() else "off"
        auto_sync_state = "on" if self.app_settings.get_canvas_auto_sync_enabled() else "off"
        startup_state = "on" if self.app_settings.get_run_on_startup_enabled() else "off"
        startup_mode = self.app_settings.get_startup_launch_mode().replace("_", " ")
        notification_state = "on" if self.app_settings.get_notifications_enabled() else "off"
        tray_state = "on" if self.app_settings.get_tray_enabled() else "off"
        user = self.get_current_user()
        cards = [
            self.create_details_card(
                "Current Configuration",
                "\n".join([
                    f"Vault folder: {self.get_vault_path()}",
                    "Window layout: Adaptive and resizable",
                    f"Theme: {theme_state}",
                    f"Follow system theme: {follow_system_state}",
                    f"Accent colour: {accent_color}",
                    f"Scroll speed: {scroll_speed}%",
                    f"UI zoom: {ui_zoom}%",
                    f"Smooth scrolling inertia: {smooth_scroll_state}",
                    f"Course announcements panel: {'shown' if self.app_settings.get_course_announcements_panel_visible() else 'hidden'}",
                    f"Due countdown precision: {self.app_settings.get_due_countdown_hours_threshold()}h / {self.app_settings.get_due_countdown_minutes_threshold()}m / {self.app_settings.get_due_countdown_seconds_threshold()}s",
                    f"Canvas auto sync: {auto_sync_state}",
                    f"Run on startup: {startup_state}",
                    f"Startup launch mode: {startup_mode}",
                    f"Assignment notifications: {notification_state}",
                    f"System tray: {tray_state}",
                    f"Close behaviour: {self.app_settings.get_close_action().replace('_', ' ')}",
                    f"Reminder schedule: every {self.app_settings.get_reminder_poll_minutes()} minute(s), {', '.join(self.app_settings.get_reminder_stages())}",
                    f"Canvas blacklist: {len(user.get('canvas_blacklisted_course_ids', [])) if user else 0} course(s)",
                    f"Canvas favourites: {len(user.get('canvas_favourite_course_ids', [])) if user else 0} course(s)",
                    f"Recent Changes panel: {history_state}",
                ]),
            ),
            self.create_details_card(
                "Application",
                "\n".join([
                    f"Name: {APP_NAME}",
                    f"Version: {APP_VERSION}",
                    f"Organisation: {APP_ORGANIZATION}",
                    f"Description: {APP_DESCRIPTION}",
                    "Packaging assets: app icon and theme icons included",
                ]),
            ),
            self.create_tip_card(
                "Appearance and Interface",
                [
                    "Use the theme button beside Help to quickly switch between dark and light mode.",
                    "Use Accent Colour to change the highlight colour used by selected rows, buttons, and badges.",
                    "Enable Follow System Theme if you want the app to match the OS theme at launch.",
                    "Use Scroll Speed to reduce or increase mouse wheel and trackpad movement.",
                    "Use Smooth Scrolling to add or remove momentum after the wheel stops.",
                    "Use Course Announcements Panel to fully hide announcement cards when they take too much space.",
                    "Use Due Countdown Precision to control when countdowns switch to hours, minutes, or seconds.",
                    "The middle and dashboard panels can be resized with the draggable divider.",
                    "Collapse the sidebar with Ctrl+B when you need more horizontal space.",
                ],
            ),
            self.create_tip_card(
                "Canvas Sync Tuning",
                [
                    "Auto sync is off by default so the app starts quickly.",
                    "Use the Canvas Course Blacklist to skip old shells and irrelevant courses during sync.",
                    "Use Favourite Canvas Courses to pin important courses to the top of the Courses section.",
                ],
            ),
            self.create_tip_card(
                "Startup Behaviour",
                [
                    "Run on PC Startup registers the app in Windows so it launches after you sign in.",
                    "Choose Startup Launch Mode if you want startup launches to stay in the tray or open the Dashboard immediately.",
                    "Background startup works best when System Tray is enabled, because reminders can keep running without the main window being visible.",
                ],
            ),
            self.create_tip_card(
                "Vault and Tools",
                [
                    "The vault stores users, Canvas sync data, assignments, and imported resources locally.",
                    "The Resource Library gives a global view across users, courses, active assignments, and Archived Assignments.",
                ],
            ),
        ]
        self.show_card_page("Settings", "Select a setting on the left, or double-click to run it.", cards)
