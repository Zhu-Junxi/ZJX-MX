from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from core.validation import ValidationError
from services.app_logging import log_user_visible_error, log_warning
from services.canvas_client import CanvasAPIError, CanvasClient
from services.command_history import CanvasSyncAction
from ui.dialogs import CourseSyncPreferencesDialog
from ui.themed_forms import ThemedMessageDialog, ThemedProgressDialog


class CanvasActionsMixin:
    """Canvas sync and Canvas course preference commands."""

    def build_canvas_course_preference_options(self, user):
        """Return Canvas course rows for blacklist/favourite preference dialogs."""
        if not user:
            return []

        imported_by_canvas_id = {}
        for course in self.vault.get_courses(user["id"]):
            canvas_id = str(course.get("canvas_id") or "").strip()
            if canvas_id:
                imported_by_canvas_id[canvas_id] = {
                    "canvas_id": canvas_id,
                    "code": course.get("code", ""),
                    "name": course.get("name", ""),
                    "imported": True,
                }

        options = dict(imported_by_canvas_id)

        if user.get("canvas_access_token"):
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                client = CanvasClient(user.get("canvas_base_url"), user.get("canvas_access_token"))
                for canvas_course in client.fetch_current_courses():
                    canvas_id = str(canvas_course.get("id") or "").strip()
                    if not canvas_id:
                        continue
                    options[canvas_id] = {
                        "canvas_id": canvas_id,
                        "code": canvas_course.get("course_code") or canvas_course.get("sis_course_id") or canvas_course.get("name") or f"Canvas {canvas_id}",
                        "name": canvas_course.get("name") or canvas_course.get("course_code") or f"Canvas {canvas_id}",
                        "imported": canvas_id in imported_by_canvas_id,
                    }
            except CanvasAPIError as error:
                if not options:
                    self.show_user_warning(
                        "Canvas Course List Failed",
                        "Canvas courses could not be loaded. Check your Canvas settings and connection.",
                        error=error,
                        context={"user_id": user.get("id"), "canvas_base_url": user.get("canvas_base_url")},
                    )
                else:
                    self.show_user_warning(
                        "Canvas Course List Partially Available",
                        "Live Canvas courses could not be loaded. Imported courses will still be shown.",
                        error=error,
                        context={"user_id": user.get("id"), "canvas_base_url": user.get("canvas_base_url")},
                    )
            finally:
                QApplication.restoreOverrideCursor()

        return sorted(
            options.values(),
            key=lambda item: ((item.get("code") or item.get("name") or "").lower(), item.get("name", "").lower()),
        )

    def manage_canvas_course_preferences(self, mode, user=None):
        user = user or self.get_current_user()
        if not user:
            QMessageBox.warning(self, "No User", "Select a user before changing Canvas sync preferences.")
            return

        if mode not in {"blacklist", "favourites"}:
            return

        selected_key = "canvas_favourite_course_ids" if mode == "favourites" else "canvas_blacklisted_course_ids"
        options = self.build_canvas_course_preference_options(user)
        dialog = CourseSyncPreferencesDialog(
            self,
            mode=mode,
            courses=options,
            selected_ids=user.get(selected_key, []),
            user_name=user.get("name", ""),
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        chosen_ids = dialog.chosen_course_ids()
        if mode == "favourites":
            updated_user = self.vault.update_user_canvas_course_preferences(
                user["id"],
                favourite_course_ids=chosen_ids,
            )
            title = "Favourite Courses Updated"
            message = f"{len(chosen_ids)} Canvas course(s) will be pinned to the top of the Courses section."
        else:
            updated_user = self.vault.update_user_canvas_course_preferences(
                user["id"],
                blacklisted_course_ids=chosen_ids,
            )
            title = "Course Blacklist Updated"
            message = f"{len(chosen_ids)} Canvas course(s) will be skipped during future Canvas syncs."

        if updated_user:
            self.set_current_user(updated_user["id"])

        if self.current_section in {"Courses", "Settings", "Users"}:
            self.change_section(self.current_section)

        QMessageBox.information(self, title, message)
        self.trigger_reminder_check()

    def toggle_single_canvas_course_preference(self, course, mode):
        user = self.get_current_user()
        if not user or not course:
            return

        canvas_id = str(course.get("canvas_id") or "").strip()
        if not canvas_id:
            QMessageBox.information(self, "Manual Course", "Only Canvas-imported courses can be favourited or blacklisted for Canvas sync.")
            return

        if mode == "favourites":
            favourite_ids = set(user.get("canvas_favourite_course_ids", []))
            if canvas_id in favourite_ids:
                favourite_ids.remove(canvas_id)
                message = "removed from favourites"
            else:
                favourite_ids.add(canvas_id)
                message = "added to favourites"
            self.vault.update_user_canvas_course_preferences(user["id"], favourite_course_ids=favourite_ids)
        elif mode == "blacklist":
            blacklisted_ids = set(user.get("canvas_blacklisted_course_ids", []))
            if canvas_id in blacklisted_ids:
                blacklisted_ids.remove(canvas_id)
                message = "removed from the blacklist"
            else:
                blacklisted_ids.add(canvas_id)
                message = "added to the blacklist"
            self.vault.update_user_canvas_course_preferences(user["id"], blacklisted_course_ids=blacklisted_ids)
        else:
            return

        self.load_context_from_settings()
        self.change_section("Courses")
        QMessageBox.information(self, "Canvas Course Preference Updated", f"{course.get('code') or course.get('name')} was {message}.")
        self.trigger_reminder_check()

    def sync_canvas_data_for_user(self, user=None, automatic=False, show_intro=True):
        user = user or self.get_current_user()

        if not user:
            ThemedMessageDialog.show(
                self,
                title="No User Selected",
                subtitle="Canvas sync needs an active local user profile.",
                body="Select or create a user first, then run Sync Canvas again.",
                accept_text="Got It",
            )
            return

        if not user.get("canvas_access_token"):
            if automatic:
                return
            should_edit = ThemedMessageDialog.confirm(
                self,
                title="Canvas Token Missing",
                subtitle="This user cannot sync until a Canvas access token is saved.",
                body="Open the user settings now to add the Canvas URL and access token for this profile.",
                accept_text="Edit User Settings",
                cancel_text="Not Now",
            )
            if should_edit:
                self.edit_user_dialog(user)
            return

        if show_intro and not automatic:
            blacklisted_count = len(user.get("canvas_blacklisted_course_ids", []))
            should_sync = ThemedMessageDialog.confirm(
                self,
                title="Sync Canvas Data",
                subtitle="Import Canvas courses, assignments, and announcements into this user's local vault.",
                body=(
                    "This sync will fetch:\n"
                    "- Active and completed courses, except blacklisted courses\n"
                    "- Assignments for each imported course\n"
                    "- Announcements for each imported course\n"
                    "- Finished Canvas courses will be archived locally\n\n"
                    f"Current blacklist: {blacklisted_count} Canvas course(s).\n"
                    "Existing Canvas items are updated using stable Canvas IDs, so re-syncing will not duplicate them."
                ),
                accept_text="Start Sync",
                cancel_text="Cancel",
                minimum_width=620,
            )
            if not should_sync:
                return

        progress = ThemedProgressDialog(
            self,
            title="Syncing Canvas Data",
            subtitle=f"Fetching Canvas data for {user.get('name', 'this user')}.",
            initial_status="Preparing Canvas sync...\n\nZJX LMS is about to fetch courses, assignments, and announcements.",
            minimum_width=min(660, max(520, int(self.width() * 0.46))),
        )
        progress.set_status(
            "Preparing Canvas sync...\n\nZJX LMS is about to fetch courses, assignments, and announcements.",
            0,
        )
        progress.show()
        QApplication.processEvents()

        command = CanvasSyncAction(
            self.vault.user_dir(user["id"]),
            user.get("name", "user"),
        )
        command.capture_before()

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            progress.set_status("Connecting to Canvas...\n\nFetching your Canvas course list.", 5)
            QApplication.processEvents()

            user = self.vault.get_user(user["id"]) or user
            blacklisted_course_ids = {str(item) for item in user.get("canvas_blacklisted_course_ids", [])}

            client = CanvasClient(user.get("canvas_base_url"), user.get("canvas_access_token"))
            profile_warning = ""
            try:
                canvas_profile = client.fetch_user_profile()
                avatar_url = (
                    canvas_profile.get("avatar_url")
                    or canvas_profile.get("profile_pic_url")
                    or canvas_profile.get("picture")
                    or ""
                )
                avatar_bytes = None
                if avatar_url:
                    try:
                        avatar_bytes, _content_type = client.fetch_avatar_bytes(avatar_url)
                    except CanvasAPIError as error:
                        profile_warning = " Profile picture could not be cached."
                        log_warning("Canvas profile picture could not be cached: %r", error)
                updated_profile_user = self.vault.update_user_canvas_profile(
                    user["id"],
                    canvas_profile,
                    avatar_bytes=avatar_bytes,
                )
                if updated_profile_user:
                    user = updated_profile_user
            except CanvasAPIError as error:
                profile_warning = " Canvas profile could not be synced."
                log_warning("Canvas profile could not be synced: %r", error)

            all_canvas_courses = client.fetch_sync_courses()
            canvas_courses = [
                course for course in all_canvas_courses
                if str(course.get("id") or "") not in blacklisted_course_ids
            ]
            skipped_blacklisted_courses = len(all_canvas_courses) - len(canvas_courses)

            progress.set_status(
                f"Found {len(all_canvas_courses)} Canvas course(s).\n\n"
                f"Syncing {len(canvas_courses)} after blacklist filtering.",
                12,
            )
            QApplication.processEvents()

            courses_created = 0
            courses_updated = 0
            assignments_created = 0
            assignments_updated = 0
            announcements_synced = 0
            skipped_courses = 0
            courses_archived = 0
            archived_canvas_ids = set()
            assignment_failures = []
            announcement_failures = []
            first_course_id = None

            total_courses = max(1, len(canvas_courses))
            for index, canvas_course in enumerate(canvas_courses, start=1):
                imported_course, created = self.vault.add_or_update_canvas_course(user["id"], canvas_course)

                if not imported_course:
                    skipped_courses += 1
                    continue

                if created:
                    courses_created += 1
                else:
                    courses_updated += 1

                course_label = imported_course.get("code") or imported_course.get("name") or f"course {index}"
                base_progress = 12 + int((index - 1) / total_courses * 82)

                if imported_course.get("archived"):
                    courses_archived += 1
                    canvas_id = str(imported_course.get("canvas_id") or "").strip()
                    if canvas_id:
                        archived_canvas_ids.add(canvas_id)
                    progress.set_status(f"Archived finished Canvas course.\n\n{course_label}", min(94, base_progress + 4))
                    QApplication.processEvents()
                    continue

                first_course_id = first_course_id or imported_course["id"]

                progress.set_status(f"Syncing assignments...\n\n{course_label}", base_progress)
                QApplication.processEvents()

                try:
                    canvas_assignments = client.fetch_assignments(canvas_course.get("id"))
                except CanvasAPIError as error:
                    assignment_failures.append({"course": course_label, "error": repr(error)})
                    canvas_assignments = []

                for canvas_assignment in canvas_assignments:
                    imported_assignment, assignment_created = self.vault.add_or_update_canvas_assignment(
                        user["id"],
                        imported_course["id"],
                        canvas_assignment,
                    )
                    if not imported_assignment:
                        continue
                    if assignment_created:
                        assignments_created += 1
                    else:
                        assignments_updated += 1

                progress.set_status(f"Syncing announcements...\n\n{course_label}", min(94, base_progress + 4))
                QApplication.processEvents()

                try:
                    canvas_announcements = client.fetch_announcements(canvas_course.get("id"))
                    announcements_synced += self.vault.add_or_update_canvas_announcements(
                        user["id"],
                        imported_course["id"],
                        canvas_announcements,
                    )
                except CanvasAPIError as error:
                    announcement_failures.append({"course": course_label, "error": repr(error)})

                progress.set_status(f"Finished syncing course {index} of {total_courses}.\n\n{course_label}", 12 + int(index / total_courses * 82))
                QApplication.processEvents()

            summary = (
                f"Courses: {courses_created} created, {courses_updated} updated. "
                f"Assignments: {assignments_created} created, {assignments_updated} updated. "
                f"Announcements synced: {announcements_synced}."
            )
            if skipped_courses:
                summary += f" Skipped courses: {skipped_courses}."
            if courses_archived:
                summary += f" Archived courses: {courses_archived}."
            if skipped_blacklisted_courses:
                summary += f" Blacklisted courses skipped: {skipped_blacklisted_courses}."
            if assignment_failures:
                summary += f" Assignment sync failures: {len(assignment_failures)}."
            if announcement_failures:
                summary += f" Announcement sync failures: {len(announcement_failures)}."
            if profile_warning:
                summary += profile_warning

            newly_skipped_archived = sorted(archived_canvas_ids - blacklisted_course_ids)
            if newly_skipped_archived:
                updated_user = self.vault.update_user_canvas_course_preferences(
                    user["id"],
                    blacklisted_course_ids=blacklisted_course_ids | archived_canvas_ids,
                )
                if updated_user:
                    user = updated_user
                summary += f" Added archived courses to skipped list: {len(newly_skipped_archived)}."

            progress.set_status("Finalising sync...\n\nSaving the Canvas sync result locally.", 97)
            QApplication.processEvents()

            updated_user = self.vault.update_user_canvas_sync_status(user["id"], summary) or user
            self.commit_undo_snapshot(command)

            self.set_current_user(updated_user["id"])
            if first_course_id:
                self.set_current_course(first_course_id)
            self.change_section("Courses")

            detail = summary
            if assignment_failures:
                log_warning("Canvas assignment sync failures: %s", assignment_failures[:8])
            if announcement_failures:
                log_warning("Canvas announcement sync failures: %s", announcement_failures[:8])

            progress.set_status("Canvas sync complete.\n\nYour local vault is up to date.", 100)
            QApplication.processEvents()
            progress.close()

            if not automatic:
                ThemedMessageDialog.show(
                    self,
                    title="Canvas Sync Complete",
                    subtitle="Your local vault has been updated with the latest Canvas data.",
                    body=detail,
                    accept_text="Done",
                    minimum_width=640,
                )

            if self.library_window and hasattr(self.library_window, "refresh_tree"):
                self.library_window.refresh_tree()
            self.trigger_reminder_check()

        except (ValidationError, CanvasAPIError) as error:
            self.discard_undo_snapshot(command)
            progress.close()
            message = "Canvas sync could not finish. Check your connection and Canvas settings."
            log_user_visible_error(
                "Canvas Sync Failed",
                message,
                error=error,
                context={"user_id": user.get("id"), "canvas_base_url": user.get("canvas_base_url")},
            )
            ThemedMessageDialog.show(
                self,
                title="Canvas Sync Failed",
                subtitle="ZJX LMS could not complete the Canvas import.",
                body=message,
                accept_text="Close",
                minimum_width=620,
            )
        except Exception:
            self.discard_undo_snapshot(command)
            progress.close()
            raise
        finally:
            QApplication.restoreOverrideCursor()
