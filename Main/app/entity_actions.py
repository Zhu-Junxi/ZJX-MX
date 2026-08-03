from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QDialog, QMessageBox

from core.validation import ValidationError, validate_assignment_payload, validate_course_payload
from services.command_history import (
    AssignmentCreateAction,
    AssignmentUpdateAction,
    CompositeAction,
    CourseCreateAction,
    CourseUpdateAction,
    FileDeleteAction,
    UserDeleteAction,
    UserUpdateAction,
)
from ui.dialogs import CreateUserDialog
from ui.themed_forms import FormField, ThemedFormDialog


class EntityActionsMixin:
    """User, course, and assignment CRUD commands."""

    def ensure_course_context(self):
        if not self.current_user_id or not self.current_course_id:
            QMessageBox.warning(self, "Missing Context", "Select a user and course first.")
            return False
        return True

    def add_user_dialog(self):
        self.show_create_user_dialog(required=False)

    def edit_user_dialog(self, user=None):
        user = user or self.get_current_user()
        if not user:
            QMessageBox.warning(self, "No User", "Select a user first.")
            return

        dialog = CreateUserDialog(self, required=False, user=user)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            action = UserUpdateAction(
                self.vault,
                user,
                dialog.user_payload(),
                description=f"Edited user: {user.get('name', 'profile')}",
            )
            self.command_history.perform(action)
            self.update_history_panel()
            updated_user = action.after_user
            self.set_current_user(updated_user["id"])
            self.change_section("Users")
            self.show_user_detail(updated_user)

        except ValidationError as error:
            QMessageBox.warning(self, "Invalid User Details", str(error))
        except Exception:
            raise


    def select_user_and_open_courses(self, user):
        if not user:
            return

        self.set_current_user(user["id"])
        self.change_section("Dashboard")

    def delete_user_dialog(self, user=None):
        user = user or self.get_current_user()

        if not user:
            return

        user_name = user.get("name", "Unnamed User")
        course_count = len(self.vault.get_courses(user["id"]))

        reply = QMessageBox.question(
            self,
            "Delete User",
            f"Delete user '{user_name}'?\n\n"
            f"This removes the user profile, {course_count} course(s), assignments, resources, and local vault files for this user.\n"
            "You can undo this immediately with Ctrl+Z.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if hasattr(self, "release_file_explorer_handles"):
                self.release_file_explorer_handles()
            action = UserDeleteAction(
                self.vault,
                user,
                description=f"Deleted user: {user_name}",
            )
            self.command_history.perform(action)
            self.update_history_panel()

            remaining_users = self.vault.get_users()

            if remaining_users:
                self.set_current_user(remaining_users[0]["id"])
            else:
                self.current_user_id = None
                self.current_course_id = None
                self.current_assignment_id = None
                self.app_settings.set_current_user_id(None)
                self.app_settings.set_current_course_id(None)
                self.app_settings.set_current_assignment_id(None)
                self.update_sidebar_user_label()

            self.change_section("Users")

            if self.library_window and hasattr(self.library_window, "refresh_tree"):
                self.library_window.refresh_tree()
            self.trigger_reminder_check()

        except Exception:
            raise

    def add_course_dialog(self):
        if not self.current_user_id:
            QMessageBox.warning(self, "No User", "Select a user first.")
            return

        values = ThemedFormDialog.ask(
            self,
            title="Add Course",
            subtitle="Create a local course workspace with the details below.",
            fields=[
                FormField(
                    "code",
                    "Course code",
                    placeholder="e.g. COMP1010",
                    required=True,
                ),
                FormField(
                    "name",
                    "Course name",
                    placeholder="e.g. Programming Fundamentals",
                    required=True,
                ),
            ],
            accept_text="Create Course",
        )
        if not values:
            return

        code = values["code"].strip()
        name = values["name"].strip()
        try:
            payload = validate_course_payload(code, name)
            action = CourseCreateAction(
                self.vault,
                self.current_user_id,
                payload["code"],
                payload["name"],
                description=f"Created course: {payload['code']}",
            )
            self.command_history.perform(action)
            self.update_history_panel()
            course = action.course
        except ValidationError as error:
            QMessageBox.warning(self, "Invalid Course", str(error))
            return

        self.set_current_course(course["id"])
        self.change_section("Courses")

    def set_course_archived(self, course=None, archived=True, source="manual", user_id=None):
        user_id = user_id or self.current_user_id
        if not user_id:
            return

        course = course or self.get_current_course()
        if not course:
            return

        archived = bool(archived)
        fields = {
            "archived": archived,
            "archived_at": datetime.now().isoformat(timespec="seconds") if archived else "",
            "archived_source": source if archived else "",
        }

        course_action = CourseUpdateAction(
            self.vault,
            user_id,
            course,
            fields,
            description=f"{'Archived' if archived else 'Unarchived'} course: {course.get('code', course.get('name', 'course'))}",
        )
        actions = [course_action]

        user = self.vault.get_user(user_id)
        canvas_id = str(course.get("canvas_id") or "").strip()
        if user and canvas_id:
            skipped_ids = {str(item) for item in user.get("canvas_blacklisted_course_ids", [])}
            favourite_ids = {str(item) for item in user.get("canvas_favourite_course_ids", [])}

            if archived:
                skipped_ids.add(canvas_id)
                favourite_ids.discard(canvas_id)
            else:
                skipped_ids.discard(canvas_id)

            if (
                skipped_ids != set(user.get("canvas_blacklisted_course_ids", []))
                or favourite_ids != set(user.get("canvas_favourite_course_ids", []))
            ):
                actions.append(
                    UserUpdateAction(
                        self.vault,
                        user,
                        {
                            "canvas_blacklisted_course_ids": sorted(skipped_ids),
                            "canvas_favourite_course_ids": sorted(favourite_ids),
                        },
                        description=f"Updated Canvas skipped courses for {user.get('name', 'user')}",
                    )
                )

        action = course_action if len(actions) == 1 else CompositeAction(
            f"{'Archived' if archived else 'Unarchived'} course: {course.get('code', course.get('name', 'course'))}",
            actions,
            action_type="archive_course" if archived else "unarchive_course",
            affected_item=str(course.get("id", "")),
        )
        self.command_history.perform(action)
        self.update_history_panel()

        if archived and self.current_user_id == user_id and self.current_course_id == course.get("id"):
            visible_courses = self.get_visible_courses(user_id)
            if visible_courses:
                self.set_current_course(visible_courses[0]["id"])
            else:
                self.current_course_id = None
                self.current_assignment_id = None
                self.app_settings.set_current_course_id(None)
                self.app_settings.set_current_assignment_id(None)

        if self.current_section in {"Courses", "Assignments", "Files", "Dashboard"}:
            self.change_section("Courses" if archived else self.current_section)

        if self.library_window and hasattr(self.library_window, "refresh_tree"):
            self.library_window.refresh_tree()
        self.trigger_reminder_check()

    def archive_course_dialog(self, course=None, user_id=None):
        user_id = user_id or self.current_user_id
        if not user_id:
            return

        course = course or self.get_current_course()
        if not course:
            return

        reply = QMessageBox.question(
            self,
            "Archive Course",
            f"Archive course '{course.get('code')} - {course.get('name')}'?\n\n"
            "The course will be hidden from the Courses section, but its assignments and resources will remain available in the Resource Library.\n"
            "You can undo this immediately with Ctrl+Z.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.set_course_archived(course, True, source="manual", user_id=user_id)

    def delete_course_dialog(self, course=None):
        if not self.current_user_id:
            return

        course = course or self.get_current_course()
        if not course:
            return

        reply = QMessageBox.question(
            self,
            "Remove Course",
            f"Remove course '{course.get('code')} - {course.get('name')}'?\n\n"
            "This deletes the course, assignments, resources, and local vault files for this course.\n"
            "You can undo this immediately with Ctrl+Z.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if hasattr(self, "release_file_explorer_handles"):
                self.release_file_explorer_handles()
            action = FileDeleteAction(
                self.vault.course_dir(self.current_user_id, course["id"]),
                description=f"Removed course: {course.get('code', course.get('name', 'course'))}",
            )
            self.command_history.perform(action)
            self.update_history_panel()

            remaining_courses = self.vault.get_courses(self.current_user_id)
            if remaining_courses:
                self.set_current_course(remaining_courses[0]["id"])
            else:
                self.current_course_id = None
                self.current_assignment_id = None
                self.app_settings.set_current_course_id(None)
                self.app_settings.set_current_assignment_id(None)

            self.change_section("Courses")

            if self.library_window and hasattr(self.library_window, "refresh_tree"):
                self.library_window.refresh_tree()

        except Exception:
            raise

    def delete_assignment_dialog(self, assignment=None):
        if not self.ensure_course_context():
            return

        assignment = assignment or self.get_current_assignment()
        if not assignment:
            return

        reply = QMessageBox.question(
            self,
            "Remove Assignment / Assessment",
            f"Remove assignment '{assignment.get('title')}'?\n\n"
            "This deletes the assignment and all resources attached to it.\n"
            "You can undo this immediately with Ctrl+Z.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if hasattr(self, "release_file_explorer_handles"):
                self.release_file_explorer_handles()
            action = FileDeleteAction(
                self.vault.assignment_dir(self.current_user_id, self.current_course_id, assignment["id"]),
                description=f"Removed assignment: {assignment.get('title', 'assignment')}",
            )
            self.command_history.perform(action)
            self.update_history_panel()

            if self.current_assignment_id == assignment["id"]:
                self.set_current_assignment(None)

            self.change_section("Assignments")

            if self.library_window and hasattr(self.library_window, "refresh_tree"):
                self.library_window.refresh_tree()

        except Exception:
            raise

    def add_assignment_dialog(self):
        if not self.ensure_course_context():
            return

        values = ThemedFormDialog.ask(
            self,
            title="Add Assignment / Assessment",
            subtitle="Add the assessment details on one page. The due date can include hour, minute, and second precision.",
            fields=[
                FormField(
                    "title",
                    "Assignment or assessment title",
                    placeholder="e.g. Week 6 Lab Report",
                    required=True,
                ),
                FormField(
                    "due_date",
                    "Due date",
                    placeholder="e.g. 2026-05-10 23:59:59",
                    hint="Accepted formats include YYYY-MM-DD, YYYY-MM-DD HH:MM, or YYYY-MM-DD HH:MM:SS. Leave blank if there is no due date.",
                ),
            ],
            accept_text="Create Assignment",
        )
        if not values:
            return

        title = values["title"].strip()
        due_date = values["due_date"].strip()
        try:
            payload = validate_assignment_payload(title, due_date, "Not started")
            action = AssignmentCreateAction(
                self.vault,
                self.current_user_id,
                self.current_course_id,
                payload["title"],
                payload["due_date"],
                payload["status"],
                description=f"Created assignment: {payload['title']}",
            )
            self.command_history.perform(action)
            self.update_history_panel()
            assignment = action.assignment
        except ValidationError as error:
            QMessageBox.warning(self, "Invalid Assignment", str(error))
            return

        self.set_current_assignment(assignment["id"])
        self.change_section("Assignments")
        self.trigger_reminder_check()

    def edit_assignment_dialog(self, assignment=None):
        if not self.ensure_course_context():
            return

        assignment = assignment or self.get_current_assignment()
        if not assignment:
            return

        values = ThemedFormDialog.ask(
            self,
            title="Edit Assignment / Assessment",
            subtitle="Update the title or due date. Leave the due date blank if it should stay open without a deadline.",
            fields=[
                FormField(
                    "title",
                    "Assignment or assessment title",
                    default=assignment.get("title", ""),
                    required=True,
                ),
                FormField(
                    "due_date",
                    "Due date",
                    default=assignment.get("due_date", ""),
                    placeholder="e.g. 2026-05-10 23:59:59",
                    hint="Accepted formats include YYYY-MM-DD, YYYY-MM-DD HH:MM, or YYYY-MM-DD HH:MM:SS. Leave blank if there is no due date.",
                ),
            ],
            accept_text="Save Assignment",
        )
        if not values:
            return

        title = values["title"].strip()
        due_date = values["due_date"].strip()
        try:
            payload = validate_assignment_payload(title, due_date, assignment.get("status") or "Not started")
        except ValidationError as error:
            QMessageBox.warning(self, "Invalid Assignment", str(error))
            return

        try:
            action = AssignmentUpdateAction(
                self.vault,
                self.current_user_id,
                self.current_course_id,
                assignment,
                {
                    "title": payload["title"],
                    "due_date": payload["due_date"],
                    "canvas_due_at": "",
                    "due_date_overridden_by_user": True,
                    "archive_prompted_due_text": "",
                    "archive_prompted_at": "",
                },
                description=f"Edited assignment: {assignment.get('title', 'assignment')}",
            )
            self.command_history.perform(action)
            self.update_history_panel()
            self.change_section("Assignments")

            if self.library_window and hasattr(self.library_window, "refresh_tree"):
                self.library_window.refresh_tree()
            self.trigger_reminder_check()
        except Exception:
            raise
