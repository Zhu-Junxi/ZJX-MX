from pathlib import Path
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.entity_actions import EntityActionsMixin
from core.vault_manager import VaultManager
from services.command_history import CommandHistory


class FakeSettings:
    def set_current_course_id(self, value):
        self.current_course_id = value

    def set_current_assignment_id(self, value):
        self.current_assignment_id = value


class FakeMainWindow(EntityActionsMixin):
    def __init__(self, vault, user_id, course_id):
        self.vault = vault
        self.command_history = CommandHistory()
        self.app_settings = FakeSettings()
        self.current_user_id = user_id
        self.current_course_id = course_id
        self.current_assignment_id = None
        self.current_section = "Help"
        self.library_window = None
        self.history_updated = False
        self.reminder_checked = False

    def get_current_course(self):
        return self.vault.get_course(self.current_user_id, self.current_course_id)

    def get_visible_courses(self, user_id=None):
        return [
            course for course in self.vault.get_courses(user_id or self.current_user_id)
            if not course.get("archived")
        ]

    def update_history_panel(self):
        self.history_updated = True

    def change_section(self, section):
        self.current_section = section

    def trigger_reminder_check(self):
        self.reminder_checked = True


class CourseArchivingTests(unittest.TestCase):
    def test_archiving_canvas_course_adds_to_skipped_list_and_undo_restores(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = VaultManager(Path(temp_dir) / "vault")
            user = vault.add_user("Test User")
            course, _created = vault.add_or_update_canvas_course(
                user["id"],
                {
                    "id": "123",
                    "course_code": "TEST1001",
                    "name": "Testing",
                    "workflow_state": "available",
                },
            )
            app = FakeMainWindow(vault, user["id"], course["id"])

            app.set_course_archived(course, True)

            archived = vault.get_course(user["id"], course["id"])
            updated_user = vault.get_user(user["id"])
            self.assertTrue(archived["archived"])
            self.assertIn("123", updated_user["canvas_blacklisted_course_ids"])

            app.command_history.undo()

            restored = vault.get_course(user["id"], course["id"])
            restored_user = vault.get_user(user["id"])
            self.assertFalse(restored.get("archived", False))
            self.assertNotIn("123", restored_user["canvas_blacklisted_course_ids"])

    def test_unarchiving_canvas_course_removes_from_skipped_list(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = VaultManager(Path(temp_dir) / "vault")
            user = vault.add_user("Test User")
            course, _created = vault.add_or_update_canvas_course(
                user["id"],
                {
                    "id": "123",
                    "course_code": "TEST1001",
                    "name": "Testing",
                    "workflow_state": "completed",
                },
            )
            vault.update_user_canvas_course_preferences(user["id"], blacklisted_course_ids=["123"])
            app = FakeMainWindow(vault, user["id"], course["id"])

            app.set_course_archived(course, False)

            unarchived = vault.get_course(user["id"], course["id"])
            updated_user = vault.get_user(user["id"])
            self.assertFalse(unarchived["archived"])
            self.assertNotIn("123", updated_user["canvas_blacklisted_course_ids"])


if __name__ == "__main__":
    unittest.main()
