from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.dashboard_views import DashboardViewsMixin


class TodoDashboardHelper(DashboardViewsMixin):
    pass


class TodoVault:
    def __init__(self, assignment):
        self.assignment = assignment

    def get_assignment(self, user_id, course_id, assignment_id):
        if (user_id, course_id, assignment_id) == ("user", "course", self.assignment["id"]):
            return dict(self.assignment)
        return None


class TodoDashboardTests(unittest.TestCase):
    def setUp(self):
        self.dashboard = TodoDashboardHelper()

    def test_open_todos_are_rendered_before_completed_todos(self):
        todos = [
            {"id": "done", "title": "Submit", "done": True},
            {"id": "open", "title": "Draft", "done": False},
            {"id": "open_2", "title": "Review", "done": False},
        ]

        sorted_ids = [todo["id"] for todo in self.dashboard.sorted_assignment_todos(todos)]

        self.assertEqual(sorted_ids, ["open", "open_2", "done"])

    def test_todo_meta_prefers_completed_timestamp(self):
        todo = {
            "title": "Submit",
            "done": True,
            "updated_at": "2026-06-07T09:30:00",
            "completed_at": "2026-06-08T10:15:00",
        }

        self.assertEqual(self.dashboard.todo_meta_text(todo), "Completed 08 Jun 10:15")

    def test_dashboard_render_uses_fresh_assignment_from_vault(self):
        stale_assignment = {"id": "assignment", "title": "Essay", "todos": []}
        fresh_assignment = {
            "id": "assignment",
            "title": "Essay",
            "todos": [{"id": "todo", "title": "Draft", "done": False}],
        }
        self.dashboard.current_user_id = "user"
        self.dashboard.vault = TodoVault(fresh_assignment)

        result = self.dashboard.assignment_for_dashboard_render(
            stale_assignment,
            {"id": "course"},
        )

        self.assertEqual(result["todos"], fresh_assignment["todos"])


if __name__ == "__main__":
    unittest.main()
