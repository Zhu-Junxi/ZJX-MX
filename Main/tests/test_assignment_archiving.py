from pathlib import Path
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.vault_manager import VaultManager


class AssignmentArchivingTests(unittest.TestCase):
    def test_manual_past_due_assignment_stays_active(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = VaultManager(Path(temp_dir) / "vault")
            user = vault.add_user("Test User")
            course = vault.add_course(user["id"], "TEST1001", "Testing")
            assignment = vault.add_assignment(user["id"], course["id"], "Late Essay", "2000-01-01")

            self.assertFalse(assignment["completed"])
            self.assertEqual(assignment["status"], "Not started")
            self.assertEqual(assignment["completed_at"], "")

    def test_canvas_past_due_assignment_stays_active(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = VaultManager(Path(temp_dir) / "vault")
            user = vault.add_user("Test User")
            course = vault.add_course(user["id"], "TEST1001", "Testing")
            assignment, created = vault.add_or_update_canvas_assignment(
                user["id"],
                course["id"],
                {
                    "id": "123",
                    "name": "Canvas Essay",
                    "due_at": "2000-01-01T23:59:00Z",
                },
            )

            self.assertTrue(created)
            self.assertFalse(assignment["completed"])
            self.assertEqual(assignment["status"], "Not started")
            self.assertEqual(assignment["completed_at"], "")

    def test_canvas_sync_preserves_user_cleared_due_date(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = VaultManager(Path(temp_dir) / "vault")
            user = vault.add_user("Test User")
            course = vault.add_course(user["id"], "TEST1001", "Testing")
            assignment, _created = vault.add_or_update_canvas_assignment(
                user["id"],
                course["id"],
                {
                    "id": "123",
                    "name": "Canvas Essay",
                    "due_at": "2026-01-01T23:59:00Z",
                },
            )
            vault.update_assignment_fields(
                user["id"],
                course["id"],
                assignment["id"],
                due_date="",
                canvas_due_at="",
                due_date_overridden_by_user=True,
            )

            updated, created = vault.add_or_update_canvas_assignment(
                user["id"],
                course["id"],
                {
                    "id": "123",
                    "name": "Canvas Essay",
                    "due_at": "2026-02-01T23:59:00Z",
                },
            )

            self.assertFalse(created)
            self.assertEqual(updated["due_date"], "")
            self.assertEqual(updated["canvas_due_at"], "")

    def test_canvas_completed_course_is_archived(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = VaultManager(Path(temp_dir) / "vault")
            user = vault.add_user("Test User")

            course, created = vault.add_or_update_canvas_course(
                user["id"],
                {
                    "id": "123",
                    "course_code": "DONE1001",
                    "name": "Completed Canvas Course",
                    "workflow_state": "completed",
                },
            )

            self.assertTrue(created)
            self.assertTrue(course["canvas_finished"])
            self.assertTrue(course["archived"])
            self.assertEqual(course["archived_source"], "canvas")

    def test_canvas_past_end_course_is_archived(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = VaultManager(Path(temp_dir) / "vault")
            user = vault.add_user("Test User")

            course, _created = vault.add_or_update_canvas_course(
                user["id"],
                {
                    "id": "456",
                    "course_code": "PAST1001",
                    "name": "Past Canvas Course",
                    "workflow_state": "available",
                    "end_at": "2000-01-01T00:00:00Z",
                },
            )

            self.assertTrue(course["canvas_finished"])
            self.assertTrue(course["archived"])


if __name__ == "__main__":
    unittest.main()
