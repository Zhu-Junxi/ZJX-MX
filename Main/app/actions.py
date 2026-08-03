from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QLineEdit, QMessageBox, QTextEdit, QPlainTextEdit

from services.command_history import SnapshotCommand, SnapshotRestoreError
from services.app_logging import log_user_visible_error
from app.canvas_actions import CanvasActionsMixin
from app.entity_actions import EntityActionsMixin
from app.resource_actions import ResourceActionsMixin
from app.settings_actions import SettingsActionsMixin
from ui.keyboard_shortcuts import shortcut_text_from_key_event


class AppActionsMixin(ResourceActionsMixin, EntityActionsMixin, SettingsActionsMixin, CanvasActionsMixin):
    """Command, preview, editing, CRUD, and file-operation handlers.

    The methods in this mixin intentionally operate through ``self`` so the
    main window stays the single owner of UI state while this module carries the
    heavy interaction logic.
    """

    def show_user_warning(self, title, message, *, error=None, context=None):
        if error is not None or context:
            log_user_visible_error(title, message, error=error, context=context)
        QMessageBox.warning(self, title, message)

    def show_user_error(self, title, message, *, error=None, context=None, fatal=False):
        if error is not None or context:
            log_user_visible_error(title, message, error=error, context=context)
        if fatal:
            QMessageBox.critical(self, title, message)
        else:
            QMessageBox.warning(self, title, message)

    # =========================================================
    # Keyboard Shortcuts
    # =========================================================
    def setup_resource_shortcuts(self):
        self._file_shortcuts = {
            "Ctrl+A": self.select_all_resources,
            "Ctrl+C": self.copy_selected_resources,
            "Ctrl+X": self.cut_selected_resources,
            "Ctrl+V": self.paste_resources,
            "Delete": self.delete_selected_resources,
            "F2": self.rename_selected_resource,
            "F5": self.manual_refresh_file_explorer,
            "Return": self.open_selected_resource,
            "Enter": self.open_selected_resource,
        }

        self._global_shortcuts = {
            "Ctrl+Z": self.undo_last_change,
            "Ctrl+Shift+Z": self.redo_last_change,
            "Ctrl+Y": self.redo_last_change,
            "Meta+Z": self.undo_last_change,
            "Meta+Shift+Z": self.redo_last_change,
            "Meta+Y": self.redo_last_change,
            "Ctrl+B": self.toggle_sidebar,
            "Ctrl++": lambda: self.adjust_ui_zoom(5),
            "Ctrl+=": lambda: self.adjust_ui_zoom(5),
            "Ctrl+-": lambda: self.adjust_ui_zoom(-5),
        }
        app = QApplication.instance()
        if app is not None and not getattr(self, "_shortcut_filter_installed", False):
            app.installEventFilter(self)
            self._shortcut_filter_installed = True

    def handle_app_shortcut_event(self, watched, event):
        if event.type() != QEvent.Type.KeyPress:
            return False

        key_sequence = shortcut_text_from_key_event(event)
        if not key_sequence:
            return False

        callback = getattr(self, "_global_shortcuts", {}).get(key_sequence)
        if callback:
            callback()
            return True

        callback = getattr(self, "_file_shortcuts", {}).get(key_sequence)
        if callback:
            return self.run_file_shortcut(callback)

        return False

    def run_file_shortcut(self, callback):
        """Run a file-browser shortcut only when it is safe to do so."""
        if getattr(self, "current_section", None) != "Files":
            return False

        focus = QApplication.focusWidget()
        if isinstance(focus, (QLineEdit, QTextEdit, QPlainTextEdit)):
            return False

        callback()
        return True

    # =========================================================
    # UNDO / REDO HISTORY
    # =========================================================

    def begin_undo_snapshot(self, description):
        if not self.current_user_id or not self.current_course_id:
            return None

        command = SnapshotCommand(description, self.current_context_dir())
        command.capture_before()
        return command

    def commit_undo_snapshot(self, command):
        if not command:
            return

        command.capture_after()

        if command.has_changes():
            self.command_history.push_done(command)
            self.update_history_panel()
        else:
            command.cleanup()

    def discard_undo_snapshot(self, command):
        if command:
            command.cleanup()

    def begin_undo_snapshot_for_context(self, description, user_id, course_id, assignment_id=None):
        command = SnapshotCommand(
            description,
            self.vault.context_dir(user_id, course_id, assignment_id),
        )
        command.capture_before()
        return command

    def begin_undo_snapshot_for_resource(self, description, resource):
        return self.begin_undo_snapshot_for_context(
            description,
            resource.get("user_id"),
            resource.get("course_id"),
            resource.get("assignment_id"),
        )

    def resource_is_current_context(self, resource):
        return (
            resource.get("user_id") == self.current_user_id
            and resource.get("course_id") == self.current_course_id
            and resource.get("assignment_id") == self.current_assignment_id
        )

    def refresh_after_resource_change(self, resource=None):
        if resource is None or self.resource_is_current_context(resource):
            if self.current_section == "Files":
                self.refresh_resource_tree_preserving_state()
            elif self.current_section in ["Courses", "Assignments"]:
                self.change_section(self.current_section)

        if self.library_window and hasattr(self.library_window, "refresh_tree"):
            self.library_window.refresh_tree()

    def undo_last_change(self):
        try:
            if hasattr(self, "release_file_explorer_handles"):
                self.release_file_explorer_handles()
            command = self.command_history.undo()
        except SnapshotRestoreError as error:
            self.show_user_warning(
                "Undo Blocked",
                str(error),
            )
            self.update_history_panel()
            return
        except Exception as error:
            self.show_user_warning(
                "Undo Failed",
                "Undo could not complete. The history entry was kept so you can retry after checking the vault.",
                error=error,
            )
            self.update_history_panel()
            return

        if not command:
            self.show_text_page("Undo", self.current_context_label(), "There is nothing to undo.")
            return

        self.refresh_after_history_restore(f"Undid: {command.description}")

    def redo_last_change(self):
        try:
            if hasattr(self, "release_file_explorer_handles"):
                self.release_file_explorer_handles()
            command = self.command_history.redo()
        except SnapshotRestoreError as error:
            self.show_user_warning(
                "Redo Blocked",
                str(error),
            )
            self.update_history_panel()
            return
        except Exception as error:
            self.show_user_warning(
                "Redo Failed",
                "Redo could not complete. The history entry was kept so you can retry after checking the vault.",
                error=error,
            )
            self.update_history_panel()
            return

        if not command:
            self.show_text_page("Redo", self.current_context_label(), "There is nothing to redo.")
            return

        self.refresh_after_history_restore(f"Redid: {command.description}")

    def refresh_after_history_restore(self, message):
        self.load_context_from_settings()
        self.update_sidebar_user_label()

        if self.current_section == "Files":
            self.refresh_resource_tree_preserving_state()
        else:
            self.change_section(self.current_section)

        if self.library_window and hasattr(self.library_window, "refresh_tree"):
            self.library_window.refresh_tree()

        self.update_history_panel()
        self.show_text_page("History", self.current_context_label(), message)
        self.trigger_reminder_check()

    def update_history_panel(self):
        if not hasattr(self, "history_list"):
            return

        self.history_list.clear()
        descriptions = self.command_history.recent_descriptions(limit=8)

        if descriptions:
            for description in descriptions:
                self.history_list.addItem(description)
        else:
            self.history_list.addItem("No changes yet")

        if hasattr(self, "zpx"):
            row_count = self.history_list.count()
            row_height = self.zpx(28)
            target_height = self.zpx(34) if row_count <= 1 else min(self.zpx(116), self.zpx(8) + (row_count * row_height))
            self.history_list.setFixedHeight(target_height)
            if hasattr(self, "history_panel"):
                self.history_panel.setMaximumHeight(self.zpx(210))

        self.undo_btn.setEnabled(self.command_history.can_undo())
        self.redo_btn.setEnabled(self.command_history.can_redo())

    def set_history_panel_visible(self, visible):
        self.history_panel_visible = bool(visible)
        self.app_settings.set_history_panel_visible(self.history_panel_visible)

        if hasattr(self, "history_panel"):
            self.history_panel.setVisible(self.history_panel_visible and not getattr(self, "sidebar_is_collapsed", False))
            self.history_toggle.setChecked(self.history_panel_visible)

        if self.current_section == "Settings":
            self.show_settings_section()
