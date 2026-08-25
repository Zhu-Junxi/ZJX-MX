from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QColorDialog,
    QFileDialog,
    QMessageBox,
)

from app.app_info import APP_NAME, APP_VERSION, APP_ORGANIZATION, APP_DESCRIPTION
from services.assignment_reminders import snooze_until
from services.app_logging import log_user_visible_error
from services.vault_exporter import VaultExporter
from ui.dialogs import ExportVaultDialog
from ui.themed_forms import FormField, ThemedFormDialog, ThemedProgressDialog


class SettingsActionsMixin:
    """Settings, theme, zoom, and preference action boundary."""

    def show_setting_detail(self, action):
        vault_path = self.get_vault_path()

        if action == "current_vault":
            self.show_text_page("Current Vault", "Active local storage location", f"\nCurrent vault folder:\n\n{vault_path}\n")
        elif action == "change_vault":
            self.show_text_page("Change Vault Folder", "Vault folder selection", "\nChoose where all application data should be stored.\n")
        elif action == "open_vault":
            self.show_text_page("Open Vault Folder", "Vault folder location", f"\nVault folder:\n\n{vault_path}\n\nUse this when you want to inspect files manually or copy the vault yourself.\n")
        elif action == "backup_vault":
            self.show_text_page(
                "Backup Vault Folder",
                "Copy local app data before beta testing",
                "\n"
                f"Current vault folder:\n\n{vault_path}\n\n"
                "Double-click this setting to choose a destination folder. ZJX LMS will copy the current vault into a timestamped backup folder there.\n\n"
                "The backup includes local users, Canvas sync metadata, cached Canvas profile pictures, imported resources, widgets, and pasted note images.\n",
            )
        elif action == "reset_vault":
            self.show_text_page("Reset Vault Folder", "Default vault location", f"\nDefault vault folder:\n\n{self.default_vault_path}\n")
        elif action == "open_library":
            self.show_text_page("Resource Library", "Universal resource browser", "\nThe Resource Library shows all resources across all users, courses, and assignments. Assignments you mark complete are grouped under Archived Assignments.\n")
        elif action == "open_widgets_manager":
            self.show_text_page(
                "Desktop Widgets",
                "Template-based floating widgets",
                "\nDesktop Widgets lets you choose from a few focused widget templates such as assignment countdowns, notes, and shortcut panels. "
                "These widgets stay active while the app process is running, including when the main window is hidden in the system tray.\n",
            )
        elif action == "export_vault_archive":
            self.show_text_page(
                "Export Vault Archive",
                "Portable human-readable vault export",
                "\nCreate a zip archive of the current vault using readable user, course, assignment, and resource names.\n\n"
                "The export includes local files, imported folders, notes, and shortcut files for Canvas, Google Drive, YouTube, and external link resources. "
                "The source vault is not modified.\n",
            )
        elif action == "window_layout":
            self.show_text_page(
                "Adaptive Window Layout",
                "Screen-aware sizing",
                "\nThe app starts at a size based on your laptop screen and remains resizable with the cursor.\n\nThe left sidebar keeps a stable width, while the middle browser and right dashboard resize with the window. Drag the divider between the middle panel and dashboard to choose your preferred layout. Collapse the sidebar with Ctrl+B if you need more horizontal space.\n",
            )
        elif action == "scroll_speed":
            self.show_text_page(
                "Scroll Speed",
                "Mouse wheel and trackpad tuning",
                f"\nCurrent scroll speed: {self.get_scroll_speed_percent()}%\n\nDouble-click this setting to choose a value from 10% to 300%. Lower values slow down scrolling for touchpads and high-resolution mouse wheels; higher values move quickly through long dashboards, resource lists, and card pages. The setting applies to nested cards and labels inside scroll areas, not just the outer panel.\n",
            )
        elif action == "ui_zoom":
            self.show_text_page(
                "UI Zoom",
                "Scale text and controls",
                f"\nCurrent zoom: {self.ui_zoom_percent}%\n\nUse Ctrl + + and Ctrl + - to adjust quickly, or double-click this setting to choose a precise value from 60% to 200%. The zoom value is saved and restored when the app opens.\n",
            )
        elif action == "smooth_scroll":
            state = "enabled" if self.get_smooth_scrolling_enabled() else "disabled"
            self.show_text_page(
                "Smooth Scrolling",
                "Momentum after wheel input",
                f"\nSmooth scrolling is currently {state}.\n\nWhen enabled, wheel movement decays gradually instead of stopping abruptly. Turn it off if you prefer the exact classic scroll behaviour.\n",
            )
        elif action == "theme_mode":
            self.show_text_page(
                "Theme Mode",
                "Dark and light appearance",
                f"\nCurrent theme: {self.effective_theme_mode().title()}\nFollow system theme: {'On' if self.app_settings.get_follow_system_theme() else 'Off'}\n\nDouble-click to toggle between dark and light mode. The quick theme button beside Help does the same thing and disables Follow System Theme for manual control.\n",
            )
        elif action == "font_style":
            current = "Mono-spaced Font" if self.app_settings.get_font_style() == "monospace" else "Default Font"
            self.show_text_page(
                "Font Style",
                "Application typography",
                f"\nCurrent font style: {current}\n\nDefault Font uses the app's current readable UI font stack. Mono-spaced Font uses JetBrains Mono first, with platform monospace fallbacks if JetBrains Mono is not installed.\n",
            )
        elif action == "follow_system_theme":
            self.show_text_page(
                "Follow System Theme",
                "OS theme matching",
                f"\nFollow system theme is currently {'enabled' if self.app_settings.get_follow_system_theme() else 'disabled'}.\n\nWhen enabled, the app chooses dark or light mode from the operating system palette at launch. Turn it off if you prefer a fixed theme.\n",
            )
        elif action == "accent_colour":
            self.show_text_page(
                "Accent Colour",
                "App highlight colour",
                f"\nCurrent accent colour: {self.app_settings.get_accent_color()}\nDefault accent colour: {getattr(self.app_settings, 'default_accent_color', '#2563eb')}\n\nDouble-click to choose a new accent colour. It is applied to selected rows, active navigation, toolbar buttons, badges, and context menu highlights. Use Reset Accent to return to the default blue.\n",
            )
        elif action == "reset_accent_colour":
            self.show_text_page(
                "Reset Accent",
                "Restore the default highlight colour",
                f"\nCurrent accent colour: {self.app_settings.get_accent_color()}\nDefault accent colour: {getattr(self.app_settings, 'default_accent_color', '#2563eb')}\n\nDouble-click this setting to reset the app accent back to the default colour.\n",
            )
        elif action == "course_announcements_panel":
            state = "shown" if self.app_settings.get_course_announcements_panel_visible() else "hidden"
            self.show_text_page(
                "Course Announcements Panel",
                "Dashboard visibility",
                f"\nThe course announcements panel is currently {state}.\n\nDouble-click this setting to toggle it. When hidden, the entire announcements block is removed from the course dashboard so urgent assignments can use the reclaimed space.\n",
            )
        elif action == "due_countdown_precision":
            hours = self.app_settings.get_due_countdown_hours_threshold()
            minutes = self.app_settings.get_due_countdown_minutes_threshold()
            seconds = self.app_settings.get_due_countdown_seconds_threshold()
            self.show_text_page(
                "Due Countdown Precision",
                "Days, hours, minutes, and seconds thresholds",
                "\n"
                f"Current thresholds: {hours}h / {minutes}m / {seconds}s\n\n"
                "The countdown displays days until the remaining time drops below the hour threshold, "
                "hours until it drops below the minute threshold, minutes until it drops below the second threshold, "
                "and seconds only when the remaining time is genuinely short.\n",
            )
        elif action == "canvas_auto_sync":
            state = "enabled" if self.app_settings.get_canvas_auto_sync_enabled() else "disabled"
            self.show_text_page(
                "Canvas Auto Sync",
                "Startup sync behaviour",
                f"\nCanvas auto sync is currently {state}.\n\nWhen enabled, ZJX LMS automatically syncs the selected user after the app opens. The default is off so launch stays fast and predictable. Blacklisted Canvas courses are still skipped during auto sync.\n",
            )
        elif action == "canvas_blacklist":
            user = self.get_current_user()
            count = len(user.get("canvas_blacklisted_course_ids", [])) if user else 0
            self.show_text_page(
                "Canvas Course Blacklist",
                "Skip unwanted Canvas courses",
                f"\nCurrent blacklisted Canvas courses: {count}.\n\nDouble-click this setting to choose Canvas courses that should be skipped during future syncs and hidden from the active Courses list. This keeps old shells, sandboxes, and irrelevant courses from flooding the app.\n",
            )
        elif action == "canvas_favourites":
            user = self.get_current_user()
            count = len(user.get("canvas_favourite_course_ids", [])) if user else 0
            self.show_text_page(
                "Favourite Canvas Courses",
                "Pin important courses",
                f"\nCurrent favourite Canvas courses: {count}.\n\nDouble-click this setting to choose Canvas courses that should always appear at the top of the Courses section. Blacklisted courses cannot also be favourites.\n",
            )
        elif action == "canvas_sync_details":
            user = self.get_current_user()
            if user:
                blacklist_count = len(user.get("canvas_blacklisted_course_ids", []))
                favourite_count = len(user.get("canvas_favourite_course_ids", []))
                last_sync = user.get("canvas_last_sync_at") or "Never"
                last_result = user.get("canvas_last_sync_result") or "Never synced"
            else:
                blacklist_count = favourite_count = 0
                last_sync = "No user selected"
                last_result = "No user selected"
            self.show_text_page(
                "Canvas Sync Details",
                "Fine tune sync behaviour",
                "\n"
                f"Auto sync on startup: {'On' if self.app_settings.get_canvas_auto_sync_enabled() else 'Off'}\n"
                f"Blacklisted Canvas courses: {blacklist_count}\n"
                f"Favourite Canvas courses: {favourite_count}\n"
                f"Last sync: {last_sync}\n"
                f"Last result: {last_result}\n\n"
                "Use the blacklist when Canvas has too many old course shells. Use favourites for current core courses that should stay at the top. Manual courses are never affected by Canvas sync filters.\n",
            )
        elif action == "run_on_startup":
            startup = getattr(self, "startup_manager", None)
            if startup and not startup.is_supported():
                self.show_text_page(
                    "Run on PC Startup",
                    "Startup registration",
                    "\nThis option is currently unavailable on this operating system.\n",
                )
            else:
                state = "enabled" if self.app_settings.get_run_on_startup_enabled() else "disabled"
                command = startup.startup_command() if startup else "Unavailable"
                platform = startup.platform_name() if startup else "this operating system"
                target = startup.registration_target() if startup else "Unavailable"
                support = startup.capability_note() if hasattr(startup, "capability_note") else ""
                self.show_text_page(
                    "Run on PC Startup",
                    f"Launch automatically after sign-in on {platform}",
                    "\n"
                    f"Run on startup is currently {state}.\n\n"
                    "Double-click this setting to add or remove ZJX LMS from the current user's startup apps.\n\n"
                    f"Registration method: {support or platform}\n"
                    f"Registration target:\n{target}\n\n"
                    f"Registered command:\n{command}\n",
                )
        elif action == "startup_launch_mode":
            mode = self.app_settings.get_startup_launch_mode()
            launch_text = "Background to tray" if mode == "background_to_tray" else "Open Dashboard window"
            self.show_text_page(
                "Startup Launch Mode",
                "Choose how automatic startup launches behave",
                "\n"
                f"Current startup launch mode: {launch_text}\n\n"
                "Background to tray keeps the app hidden when your operating system starts it, so reminders can run quietly in the system tray when this desktop session supports tray icons. "
                "Open Dashboard window shows the main window immediately and switches it to the Dashboard page.\n",
            )
        elif action == "notifications_enabled":
            state = "enabled" if self.app_settings.get_notifications_enabled() else "disabled"
            self.show_text_page(
                "Assignment Notifications",
                "Native reminder popups",
                f"\nNotifications are currently {state}.\n\n"
                "When enabled, ZJX LMS checks upcoming assignments and shows native tray notifications for smart due-date stages: "
                "7 days, 3 days, 1 day, 6 hours, 1 hour, and overdue.\n",
            )
        elif action == "tray_enabled":
            tray = getattr(self, "tray_controller", None)
            availability = tray.capabilities.tray_status_text() if tray else "unknown"
            platform = tray.capabilities.platform_label() if tray else "this session"
            state = "enabled" if self.app_settings.get_tray_enabled() else "disabled"
            self.show_text_page(
                "Minimize to Tray",
                "Background reminder support",
                f"\nPlatform/session: {platform}\nSystem tray is {availability}.\nTray mode is currently {state}.\n\n"
                "When tray mode is enabled, closing the window can hide it instead of quitting so reminders continue to run.",
            )
        elif action == "close_action":
            self.show_text_page(
                "Close Button Behaviour",
                "Choose what the X button does",
                f"\nCurrent close behaviour: {self.app_settings.get_close_action().replace('_', ' ')}.\n\n"
                "Ask means the first close asks whether to minimize to tray or quit, then remembers your choice.",
            )
        elif action == "reminder_schedule":
            self.show_text_page(
                "Reminder Schedule",
                "Polling interval and due stages",
                "\n"
                f"Poll interval: {self.app_settings.get_reminder_poll_minutes()} minute(s)\n"
                f"Stages: {', '.join(self.app_settings.get_reminder_stages())}\n\n"
                "A reminder is sent once per assignment/stage/due-date combination.",
            )
        elif action == "snooze_reminders":
            self.show_text_page(
                "Snooze Reminders",
                "Temporarily silence notifications",
                "\nReminders are currently snoozed.\n" if self.app_settings.reminders_are_snoozed() else "\nReminders are not currently snoozed.\n"
            )
        elif action == "app_info":
            self.show_text_page(
                "About ZJX LMS",
                "Application release information",
                "\n"
                f"App name: {APP_NAME}\n"
                f"Version: {APP_VERSION}\n"
                f"Organisation: {APP_ORGANIZATION}\n"
                f"Description: {APP_DESCRIPTION}\n\n"
                "Private beta packaging uses PyInstaller with the included app icon, SVG icon sets, and packaged assets.\n",
            )
        elif action == "toggle_history_panel":
            state = "shown" if self.history_panel_visible else "hidden"
            self.show_text_page(
                "Change History Panel",
                "Sidebar history visibility",
                f"\nThe Recent Changes panel is currently {state}.\n\nIt shows recent undoable file/resource edits and quick Undo/Redo buttons. This setting is saved and is on by default.\n",
            )

    def run_setting_action(self, action):
        if action == "change_vault":
            self.choose_vault_folder()
        elif action == "open_vault":
            self.open_vault_folder()
        elif action == "backup_vault":
            self.backup_vault_folder()
        elif action == "reset_vault":
            self.reset_vault_folder()
        elif action == "open_library":
            self.open_resource_library()
        elif action == "open_widgets_manager":
            self.open_widgets_manager()
        elif action == "export_vault_archive":
            self.export_vault_archive()
        elif action == "scroll_speed":
            self.change_scroll_speed()
        elif action == "ui_zoom":
            self.change_ui_zoom()
        elif action == "smooth_scroll":
            self.toggle_smooth_scrolling()
        elif action == "theme_mode":
            self.toggle_theme_mode()
        elif action == "font_style":
            self.change_font_style()
        elif action == "follow_system_theme":
            self.toggle_follow_system_theme()
        elif action == "accent_colour":
            self.choose_accent_colour()
        elif action == "reset_accent_colour":
            self.reset_accent_colour()
        elif action == "course_announcements_panel":
            self.toggle_course_announcements_panel_visibility()
        elif action == "due_countdown_precision":
            self.change_due_countdown_precision()
        elif action == "canvas_auto_sync":
            self.toggle_canvas_auto_sync()
        elif action == "canvas_blacklist":
            self.manage_canvas_course_preferences("blacklist")
        elif action == "canvas_favourites":
            self.manage_canvas_course_preferences("favourites")
        elif action == "canvas_sync_details":
            self.show_setting_detail("canvas_sync_details")
        elif action == "run_on_startup":
            self.toggle_run_on_startup()
        elif action == "startup_launch_mode":
            self.change_startup_launch_mode()
        elif action == "notifications_enabled":
            self.toggle_notifications_enabled()
        elif action == "tray_enabled":
            self.toggle_tray_enabled()
        elif action == "close_action":
            self.change_close_action()
        elif action == "reminder_schedule":
            self.change_reminder_schedule()
        elif action == "snooze_reminders":
            self.snooze_assignment_reminders()
        elif action == "app_info":
            self.open_developer_tools_panel()
        elif action == "toggle_history_panel":
            self.set_history_panel_visible(not self.history_panel_visible)

    def open_developer_tools_panel(self):
        from ui.developer_console import DeveloperConsole

        existing = getattr(self, "developer_tools_dialog", None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return

        dialog = DeveloperConsole(self)
        self.developer_tools_dialog = dialog
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda *_args: setattr(self, "developer_tools_dialog", None))
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def refresh_notification_settings_ui(self, action):
        tray = getattr(self, "tray_controller", None)
        if tray:
            tray.refresh()
        if self.current_section == "Settings":
            self.show_settings_section()
            self.show_setting_detail(action)

    def toggle_run_on_startup(self):
        startup = getattr(self, "startup_manager", None)
        if not startup or not startup.is_supported():
            QMessageBox.information(self, "Startup Unavailable", "Run on PC Startup is not available on this operating system.")
            self.refresh_notification_settings_ui("run_on_startup")
            return

        enabled = not self.app_settings.get_run_on_startup_enabled()
        changed = startup.sync_enabled_state(enabled)
        enabled = startup.is_enabled()
        self.app_settings.set_run_on_startup_enabled(enabled)
        state = "enabled" if enabled else "disabled"
        if not changed:
            detail = startup.last_error() or "The startup registration could not be updated."
            QMessageBox.warning(self, "Startup Update Failed", detail)
        else:
            QMessageBox.information(self, "Startup Updated", f"Run on PC Startup is now {state}.")
        self.refresh_notification_settings_ui("run_on_startup")

    def change_startup_launch_mode(self):
        labels = {
            "Background to Tray": "background_to_tray",
            "Open Dashboard Window": "open_dashboard",
        }
        current = {
            "background_to_tray": "Background to Tray",
            "open_dashboard": "Open Dashboard Window",
        }.get(self.app_settings.get_startup_launch_mode(), "Background to Tray")
        values = ThemedFormDialog.ask(
            self,
            title="Startup Launch Mode",
            subtitle="Choose how ZJX LMS should appear when your operating system starts it automatically.",
            fields=[
                FormField(
                    "mode",
                    "When launched on startup",
                    kind="combo",
                    default=current,
                    options=tuple(labels.keys()),
                ),
            ],
            accept_text="Save Launch Mode",
        )
        if not values:
            return

        mode = self.app_settings.set_startup_launch_mode(labels.get(values["mode"], "background_to_tray"))
        summary = "stay in the tray background" if mode == "background_to_tray" else "open the Dashboard window"
        QMessageBox.information(self, "Startup Launch Mode Updated", f"Automatic startup launches will now {summary}.")
        self.refresh_notification_settings_ui("startup_launch_mode")

    def toggle_notifications_enabled(self):
        enabled = self.app_settings.set_notifications_enabled(not self.app_settings.get_notifications_enabled())
        state = "enabled" if enabled else "disabled"
        QMessageBox.information(self, "Notifications Updated", f"Assignment notifications are now {state}.")
        self.refresh_notification_settings_ui("notifications_enabled")

    def toggle_tray_enabled(self):
        enabled = self.app_settings.set_tray_enabled(not self.app_settings.get_tray_enabled())
        state = "enabled" if enabled else "disabled"
        QMessageBox.information(self, "Tray Updated", f"System tray support is now {state}.")
        self.refresh_notification_settings_ui("tray_enabled")

    def change_close_action(self):
        labels = {
            "Ask First Time": "ask",
            "Minimize to Tray": "minimize_to_tray",
            "Quit": "quit",
        }
        current = {
            "ask": "Ask First Time",
            "minimize_to_tray": "Minimize to Tray",
            "quit": "Quit",
        }.get(self.app_settings.get_close_action(), "Ask First Time")
        values = ThemedFormDialog.ask(
            self,
            title="Close Button Behaviour",
            subtitle="Choose what the window close button should do.",
            fields=[
                FormField("action", "Close button action", kind="combo", default=current, options=tuple(labels.keys())),
            ],
            accept_text="Save Behaviour",
        )
        if not values:
            return
        self.app_settings.set_close_action(labels.get(values["action"], "ask"))
        self.refresh_notification_settings_ui("close_action")

    def change_reminder_schedule(self):
        values = ThemedFormDialog.ask(
            self,
            title="Reminder Schedule",
            subtitle="Tune how often reminders are checked and which stages are enabled.",
            fields=[
                FormField(
                    "poll",
                    "Check reminders every",
                    kind="slider",
                    default=self.app_settings.get_reminder_poll_minutes(),
                    minimum=1,
                    maximum=300,
                    step=1,
                    suffix="m",
                ),
                FormField(
                    "stages",
                    "Enabled stages",
                    default=", ".join(self.app_settings.get_reminder_stages()),
                    hint="Allowed: 7d, 3d, 1d, 6h, 1h, overdue",
                ),
            ],
            accept_text="Save Schedule",
        )
        if not values:
            return

        stages = [part.strip() for part in str(values.get("stages", "")).split(",") if part.strip()]
        self.app_settings.set_reminder_poll_minutes(values["poll"])
        self.app_settings.set_reminder_stages(stages)
        self.refresh_notification_settings_ui("reminder_schedule")

    def snooze_assignment_reminders(self):
        self.app_settings.set_reminder_snoozed_until(snooze_until(60))
        QMessageBox.information(self, "Reminders Snoozed", "Assignment reminders are snoozed for one hour.")
        self.refresh_notification_settings_ui("snooze_reminders")


    def refresh_visible_course_dashboard(self):
        course = None
        user_id = getattr(self, "course_dashboard_user_id", None) or self.current_user_id
        course_id = getattr(self, "course_dashboard_course_id", None) or self.current_course_id

        if user_id and course_id:
            course = self.vault.get_course(user_id, course_id)

        if course:
            self.show_course_dashboard_page(course, preview_mode=False)

    def toggle_course_announcements_panel_visibility(self):
        visible = self.app_settings.set_course_announcements_panel_visible(
            not self.app_settings.get_course_announcements_panel_visible()
        )
        state = "shown" if visible else "hidden"

        if self.current_section == "Settings":
            self.show_settings_section()
            self.show_setting_detail("course_announcements_panel")
        elif getattr(self, "detail_stack", None) and self.detail_stack.currentWidget() == getattr(self, "course_dashboard_page", None):
            self.refresh_visible_course_dashboard()

        QMessageBox.information(self, "Announcements Panel Updated", f"Course announcements are now {state}.")

    def change_due_countdown_precision(self):
        current_hours = self.app_settings.get_due_countdown_hours_threshold()
        current_minutes = self.app_settings.get_due_countdown_minutes_threshold()
        current_seconds = self.app_settings.get_due_countdown_seconds_threshold()

        values = ThemedFormDialog.ask(
            self,
            title="Due Countdown Precision",
            subtitle="Adjust when the assignment countdown switches between days, hours, minutes, and seconds.",
            fields=[
                FormField(
                    "hours",
                    "Show hours when under",
                    kind="slider",
                    default=current_hours,
                    minimum=1,
                    maximum=168,
                    step=1,
                    suffix="h",
                    hint="Default: 24h. Above this value, the UI uses days.",
                ),
                FormField(
                    "minutes",
                    "Show minutes when under",
                    kind="slider",
                    default=current_minutes,
                    minimum=1,
                    maximum=240,
                    step=1,
                    suffix="m",
                    hint="Default: 60m. Above this value, the UI uses hours.",
                ),
                FormField(
                    "seconds",
                    "Show seconds when under",
                    kind="slider",
                    default=current_seconds,
                    minimum=0,
                    maximum=300,
                    step=1,
                    suffix="s",
                    hint="Set to 0 to disable second-level countdowns.",
                ),
            ],
            accept_text="Save Precision",
        )
        if not values:
            return

        hours, minutes, seconds = self.app_settings.set_due_countdown_thresholds(
            values["hours"],
            values["minutes"],
            values["seconds"],
        )

        if self.current_section == "Settings":
            self.show_settings_section()
            self.show_setting_detail("due_countdown_precision")
        elif getattr(self, "detail_stack", None) and self.detail_stack.currentWidget() == getattr(self, "course_dashboard_page", None):
            self.refresh_visible_course_dashboard()
        elif getattr(self, "detail_stack", None) and self.detail_stack.currentWidget() == getattr(self, "assignment_dashboard_page", None):
            assignment = self.get_current_assignment() if hasattr(self, "get_current_assignment") else None
            if assignment:
                self.show_assignment_dashboard_page(assignment, preview_mode=False)

        QMessageBox.information(
            self,
            "Countdown Precision Updated",
            f"Due countdown thresholds set to {hours}h / {minutes}m / {seconds}s.",
        )

    def change_scroll_speed(self):
        current = self.get_scroll_speed_percent()
        values = ThemedFormDialog.ask(
            self,
            title="Scroll Speed",
            subtitle="Tune how responsive scrolling feels across the app.",
            fields=[
                FormField(
                    "speed",
                    "Scroll speed",
                    kind="slider",
                    default=current,
                    minimum=10,
                    maximum=300,
                    step=5,
                    suffix="%",
                    hint="10% is very controlled, 45% is balanced, 100% is close to normal, and 300% is fast.",
                )
            ],
            accept_text="Save Speed",
        )

        if not values:
            return

        value = self.set_scroll_speed_percent(values["speed"])
        if hasattr(self, "scroll_tuner"):
            self.scroll_tuner.refresh()
        QMessageBox.information(self, "Scroll Speed Updated", f"Scroll speed set to {value}%.")
        self.show_setting_detail("scroll_speed")

    def change_ui_zoom(self):
        values = ThemedFormDialog.ask(
            self,
            title="UI Zoom",
            subtitle="Scale text, rows, and controls across the app.",
            fields=[
                FormField(
                    "zoom",
                    "Zoom ratio",
                    kind="slider",
                    default=self.ui_zoom_percent,
                    minimum=60,
                    maximum=200,
                    step=5,
                    suffix="%",
                    hint="Ctrl + + increases zoom. Ctrl + - decreases zoom.",
                )
            ],
            accept_text="Apply Zoom",
        )

        if not values:
            return

        self.set_ui_zoom_percent(values["zoom"])
        self.show_setting_detail("ui_zoom")

    def change_font_style(self):
        labels = {
            "Default Font": "default",
            "Mono-spaced Font": "monospace",
        }
        current = "Mono-spaced Font" if self.app_settings.get_font_style() == "monospace" else "Default Font"
        values = ThemedFormDialog.ask(
            self,
            title="Font Style",
            subtitle="Choose the typography used across the app.",
            fields=[
                FormField(
                    "font_style",
                    "Application font",
                    kind="combo",
                    default=current,
                    options=tuple(labels.keys()),
                )
            ],
            accept_text="Save Font",
        )
        if not values:
            return

        style = self.app_settings.set_font_style(labels.get(values["font_style"], "default"))
        self.apply_zoom_font()
        self.apply_current_theme()
        self.refresh_list_item_size_hints()
        self.refresh_middle_panel_scaling()
        if self.current_section == "Settings":
            self.show_settings_section()
        selected = "Mono-spaced Font" if style == "monospace" else "Default Font"
        QMessageBox.information(self, "Font Updated", f"Font style set to {selected}.")
        self.show_setting_detail("font_style")

    def toggle_smooth_scrolling(self):
        enabled = self.set_smooth_scrolling_enabled(not self.get_smooth_scrolling_enabled())
        state = "enabled" if enabled else "disabled"
        QMessageBox.information(self, "Smooth Scrolling Updated", f"Smooth scrolling is now {state}.")
        self.show_setting_detail("smooth_scroll")

    def toggle_follow_system_theme(self):
        enabled = self.app_settings.set_follow_system_theme(not self.app_settings.get_follow_system_theme())
        self.apply_current_theme()
        state = "enabled" if enabled else "disabled"
        QMessageBox.information(self, "System Theme Updated", f"Follow system theme is now {state}.")
        if self.current_section == "Settings":
            self.show_settings_section()
        self.show_setting_detail("follow_system_theme")

    def choose_accent_colour(self):
        current = QColorDialog.getColor(QColor(self.app_settings.get_accent_color()), self, "Choose Accent Colour")
        if not current.isValid():
            return
        self.app_settings.set_accent_color(current.name())
        self.apply_current_theme()
        if self.current_section == "Settings":
            self.show_settings_section()
        self.show_setting_detail("accent_colour")


    def reset_accent_colour(self):
        self.app_settings.reset_accent_color()
        self.apply_current_theme()
        if self.current_section == "Settings":
            self.show_settings_section()
        self.show_setting_detail("accent_colour")

    def choose_vault_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose Vault Folder", str(self.get_vault_path()))
        if not folder:
            return

        self.set_vault_path(folder)
        QMessageBox.information(self, "Vault Updated", f"Vault folder updated to:\n\n{folder}")
        self.change_section("Settings")

    def open_vault_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.get_vault_path())))

    def backup_vault_folder(self):
        source = self.get_vault_path()
        if not source.exists():
            QMessageBox.warning(self, "Backup Vault", "The current vault folder does not exist yet.")
            return

        destination_root = QFileDialog.getExistingDirectory(self, "Choose Backup Destination", str(source.parent))
        if not destination_root:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = self._unique_backup_path(destination_root, f"{source.name}_backup_{timestamp}")

        try:
            shutil.copytree(source, destination)
        except Exception as error:
            message = "The vault could not be backed up."
            if hasattr(self, "show_user_warning"):
                self.show_user_warning(
                    "Backup Failed",
                    message,
                    error=error,
                    context={"source": source, "destination": destination},
                )
            else:
                log_user_visible_error("Backup Failed", message, error=error)
                QMessageBox.warning(self, "Backup Failed", message)
            return

        QMessageBox.information(self, "Backup Complete", f"Vault backup created at:\n\n{destination}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(destination)))

    def _unique_backup_path(self, destination_root, folder_name):
        base = Path(destination_root) / folder_name
        candidate = base
        counter = 2
        while candidate.exists():
            candidate = base.with_name(f"{base.name}_{counter}")
            counter += 1
        return candidate

    def export_vault_archive(self):
        source = self.get_vault_path()
        if not source.exists():
            QMessageBox.warning(self, "Export Vault Archive", "The current vault folder does not exist yet.")
            return

        dialog = ExportVaultDialog(self, vault=self.vault)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        options = dialog.export_options()
        progress = ThemedProgressDialog(
            self,
            title="Exporting Vault Archive",
            subtitle="Creating a portable, human-readable zip copy of the selected vault content.",
            initial_status="Preparing vault export...",
            minimum_width=min(660, max(520, int(self.width() * 0.46))),
        )
        progress.set_status("Preparing vault export...\n\nReading selected vault sections.", 0)
        progress.show()
        QApplication.processEvents()

        def update_progress(message, value):
            progress.set_status(message, value)
            QApplication.processEvents()

        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            result = VaultExporter(self.vault).export_to_zip(options, progress_callback=update_progress)
        except Exception as error:
            QApplication.restoreOverrideCursor()
            progress.close()
            message = "The vault could not be exported."
            if hasattr(self, "show_user_warning"):
                self.show_user_warning("Export Failed", message, error=error, context={"options": options})
            else:
                log_user_visible_error("Export Failed", message, error=error)
                QMessageBox.warning(self, "Export Failed", message)
            return
        finally:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

        progress.set_status("Export complete.\n\nYour portable archive is ready.", 100)
        QApplication.processEvents()
        progress.close()

        warning_text = ""
        if result.warnings:
            warning_text = f"\n\nWarnings: {len(result.warnings)} issue(s) were recorded in the export manifest."

        QMessageBox.information(
            self,
            "Export Complete",
            "Vault archive created at:\n\n"
            f"{result.zip_path}\n\n"
            f"Files copied: {result.file_count}\n"
            f"Folders copied: {result.folder_count}\n"
            f"Links exported: {result.link_count}\n"
            f"Missing resources: {result.missing_count}"
            f"{warning_text}",
        )
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(result.zip_path.parent)))

    def reset_vault_folder(self):
        self.set_vault_path(self.default_vault_path)
        QMessageBox.information(self, "Vault Reset", f"Vault folder reset to:\n\n{self.default_vault_path}")
        self.change_section("Settings")

    def toggle_canvas_auto_sync(self):
        enabled = self.app_settings.set_canvas_auto_sync_enabled(
            not self.app_settings.get_canvas_auto_sync_enabled()
        )
        state = "enabled" if enabled else "disabled"
        QMessageBox.information(
            self,
            "Canvas Auto Sync Updated",
            f"Canvas auto sync on app startup is now {state}.\n\n"
            "Default is off to keep app startup snappy.",
        )
        if self.current_section == "Settings":
            self.change_section("Settings")
