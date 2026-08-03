from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from services.assignment_reminders import collect_reminder_candidates, snooze_until
from ui.icons import load_app_icon, load_icon
from ui.signal_helpers import connect_owned_slot


class TrayController:
    """Owns system tray actions, native notifications, and reminder polling."""

    def __init__(self, main_window):
        self.main_window = main_window
        self.settings = main_window.app_settings
        self.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray_icon = None
        self.menu = None
        self._actions = []
        self._quitting = False

        self.timer = QTimer(main_window)
        connect_owned_slot(self.timer, "timeout", self.check_reminders)

        if self.tray_available and self.settings.get_tray_enabled():
            self.setup_tray()

        self.restart_timer()
        QTimer.singleShot(1500, self.check_reminders)

    def setup_tray(self):
        if self.tray_icon is not None:
            return

        icon = load_app_icon()
        if icon.isNull():
            icon = load_icon("assignment")
        self.tray_icon = QSystemTrayIcon(icon, self.main_window)
        self.tray_icon.setToolTip("ZJX")
        self.menu = QMenu(self.main_window)
        self.menu.setObjectName("ContextMenu")

        self.add_action("Show ZJX LMS", self.restore_window)
        self.add_action("Open Dashboard", lambda: self.restore_window("Dashboard"))
        self.add_action("Sync Canvas", lambda: self.main_window.sync_canvas_data_for_user(self.main_window.get_current_user()))
        self.add_action("Open Resource Library", self.main_window.open_resource_library)
        self.add_action("Open Widgets Manager", self.main_window.open_widgets_manager)
        self.menu.addSeparator()
        self.add_action("Snooze Reminders 1h", lambda: self.snooze_reminders(60))
        self.add_action("Pause Reminders", self.toggle_notifications)
        self.menu.addSeparator()
        self.add_action("Quit", self.quit_app)

        self.tray_icon.setContextMenu(self.menu)
        connect_owned_slot(self.tray_icon, "activated", self.handle_activation, argument=True)
        connect_owned_slot(self.tray_icon, "messageClicked", lambda: self.restore_window("Dashboard"))
        self.tray_icon.show()

    def add_action(self, label, callback):
        action = QAction(label, self.menu)
        connect_owned_slot(action, "triggered", callback, checked=True)
        self.menu.addAction(action)
        self._actions.append(action)
        return action

    def restart_timer(self):
        minutes = self.settings.get_reminder_poll_minutes()
        self.timer.start(max(1, minutes) * 60 * 1000)

    def handle_activation(self, reason):
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self.restore_window()

    def restore_window(self, section=None):
        window = self.main_window
        if section:
            window.change_section(section)
        window.show()
        window.raise_()
        window.activateWindow()

    def tray_can_run(self):
        return (
            self.tray_available
            and self.settings.get_tray_enabled()
            and self.tray_icon is not None
            and self.tray_icon.isVisible()
        )

    def check_reminders(self):
        candidates = self.collect_due_reminder_candidates(respect_settings=True, respect_sent=True)
        if not candidates:
            return []

        if self.tray_can_run():
            sent = self.show_candidates(candidates)
            self.settings.add_sent_reminder_keys(sent)
        return candidates

    def show_candidates(self, candidates):
        sent = []
        for candidate in candidates[:3]:
            if self.show_assignment_notification(candidate):
                sent.append(candidate.notification_key)
        return sent

    def collect_due_reminder_candidates(self, *, respect_settings=True, respect_sent=True):
        if respect_settings:
            if not self.settings.get_notifications_enabled():
                return []
            if self.settings.reminders_are_snoozed():
                return []

        sent_keys = self.settings.get_sent_reminder_keys() if respect_sent else []
        return collect_reminder_candidates(
            self.main_window.vault,
            enabled_stages=self.settings.get_reminder_stages(),
            sent_keys=sent_keys,
        )

    def run_developer_reminder_check(self):
        return self.check_reminders()

    def replay_next_developer_reminder(self):
        if self.tray_icon is None and self.tray_available:
            self.setup_tray()
        candidates = self.collect_due_reminder_candidates(respect_settings=False, respect_sent=False)
        if not candidates:
            return 0
        return len(self.show_candidates(candidates[:1]))

    def notification_parts_for_candidate(self, candidate):
        due_text = getattr(candidate, "due_text", "") or candidate.assignment.get("canvas_due_at") or candidate.assignment.get("due_date") or ""
        time_left = self.main_window.due_countdown_text(due_text)
        return self.notification_parts(
            title=time_left,
            assignment_title=getattr(candidate, "assignment_title", "") or candidate.assignment.get("title") or "Untitled assignment",
            course_details=getattr(candidate, "course_label", "") or candidate.course.get("code") or candidate.course.get("name") or "Course",
        )

    def notification_parts(self, *, title, assignment_title, course_details):
        return str(title or "Due date unavailable").upper(), "\n".join(
            [
                str(assignment_title or "Untitled assignment"),
                str(course_details or "Course"),
            ]
        )

    def show_assignment_notification(self, candidate, timeout_ms=10000):
        title, body = self.notification_parts_for_candidate(candidate)
        return self.show_assignment_notification_body(
            title,
            body,
            timeout_ms=timeout_ms,
        )

    def show_assignment_notification_body(self, title, body, timeout_ms=10000):
        if not self.tray_can_run():
            return False
        self.tray_icon.showMessage(
            title,
            body,
            QSystemTrayIcon.MessageIcon.Warning,
            timeout_ms,
        )
        return True

    def snooze_reminders(self, minutes):
        self.settings.set_reminder_snoozed_until(snooze_until(minutes))

    def toggle_notifications(self):
        self.settings.set_notifications_enabled(not self.settings.get_notifications_enabled())
        if self.main_window.current_section == "Settings":
            self.main_window.show_settings_section()
            self.main_window.show_setting_detail("notifications_enabled")

    def refresh(self):
        if self.tray_icon is None and self.tray_available and self.settings.get_tray_enabled():
            self.setup_tray()
        elif self.tray_icon is not None and not self.settings.get_tray_enabled():
            if not self.main_window.isVisible():
                self.restore_window()
            self.tray_icon.hide()
            self.tray_icon = None
        self.restart_timer()

    def quit_app(self):
        self._quitting = True
        self.main_window.force_quit_requested = True
        self.timer.stop()
        if self.tray_icon is not None:
            self.tray_icon.hide()
        self.main_window.close()
        app = QApplication.instance()
        if app is not None:
            QTimer.singleShot(0, app.quit)
