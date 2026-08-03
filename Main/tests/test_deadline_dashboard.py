from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.dashboard.dashboard_models import DashboardSettings
from core.dashboard.dashboard_readiness import calculate_readiness, todo_counts
from core.dashboard.dashboard_service import build_dashboard_data
from core.dashboard.dashboard_settings import (
    dashboard_settings_from_mapping,
    load_dashboard_settings,
    save_dashboard_settings,
)
from core.dashboard.dashboard_time import deadline_group, format_time_left


class FakeSettingsBackend:
    def __init__(self):
        self.values = {}

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value


class FakeVault:
    def __init__(self):
        self.user = {
            "id": "user",
            "canvas_blacklisted_course_ids": ["skip_canvas"],
            "canvas_favourite_course_ids": ["fav_canvas"],
        }
        self.courses = [
            {"id": "skip", "code": "SKIP101", "name": "Skipped", "canvas_id": "skip_canvas", "source": "canvas"},
            {"id": "fav", "code": "FAV101", "name": "Favourite", "canvas_id": "fav_canvas", "source": "canvas"},
            {"id": "manual", "code": "MAN101", "name": "Manual", "source": "manual"},
            {"id": "archived", "code": "OLD101", "name": "Archived", "source": "manual", "archived": True},
        ]
        self.assignments = {
            "skip": [
                {"id": "hidden", "title": "Hidden", "canvas_due_at": "2026-06-08T09:00:00+10:00"},
            ],
            "fav": [
                {
                    "id": "lab",
                    "title": "Lab Report",
                    "canvas_due_at": "2026-06-08T12:00:00+10:00",
                    "completed": False,
                    "todos": [{"id": "a", "done": True}, {"id": "b", "done": False}],
                },
                {
                    "id": "done",
                    "title": "Done Task",
                    "canvas_due_at": "2026-06-09T12:00:00+10:00",
                    "completed": True,
                    "completed_at": "2026-06-08T08:00:00",
                },
                {
                    "id": "finished",
                    "title": "Finished By Status",
                    "canvas_due_at": "2026-06-09T13:00:00+10:00",
                    "completed": False,
                    "status": "Finished",
                },
            ],
            "manual": [
                {"id": "later", "title": "Later Task", "due_date": "2026-06-20", "completed": False},
                {"id": "nodue", "title": "No Due Task", "due_date": "", "completed": False},
            ],
            "archived": [
                {"id": "archived_assignment", "title": "Archived Course Task", "due_date": "2026-06-08", "completed": False},
            ],
        }

    def get_user(self, user_id):
        return self.user if user_id == "user" else None

    def get_courses(self, user_id):
        return list(self.courses) if user_id == "user" else []

    def get_assignments(self, user_id, course_id):
        return list(self.assignments.get(course_id, []))


class DeadlineDashboardTests(unittest.TestCase):
    def test_format_time_left_uses_exact_units(self):
        now = datetime(2026, 6, 8, 10, 0, 0)

        display = format_time_left(now, "2026-06-10 12:30")

        self.assertEqual(display.main_text, "2d 2h")
        self.assertEqual(display.sub_text, "until due")
        self.assertFalse(display.is_overdue)

    def test_format_time_left_handles_overdue_due_now_and_no_due(self):
        now = datetime(2026, 6, 8, 10, 0, 0)

        overdue = format_time_left(now, "2026-06-08 08:30")
        due_now = format_time_left(now, "2026-06-08 10:00")
        no_due = format_time_left(now, "")

        self.assertTrue(overdue.is_overdue)
        self.assertEqual(overdue.main_text, "1h 30m")
        self.assertTrue(due_now.is_due_now)
        self.assertTrue(no_due.is_no_due_date)

    def test_deadline_grouping(self):
        now = datetime(2026, 6, 8, 10, 0, 0)

        self.assertEqual(deadline_group(now, "2026-06-08 09:59"), "overdue")
        self.assertEqual(deadline_group(now, "2026-06-08 23:59"), "today")
        self.assertEqual(deadline_group(now, "2026-06-09 09:00"), "tomorrow")
        self.assertEqual(deadline_group(now, "2026-06-12"), "this_week")
        self.assertEqual(deadline_group(now, ""), "no_due_date")

    def test_readiness_uses_todo_ratio_and_completion(self):
        assignment = {"todos": [{"done": True}, {"done": False}, {"done": False}]}

        self.assertEqual(todo_counts(assignment).completed, 1)
        self.assertEqual(calculate_readiness(assignment), 27)
        self.assertEqual(calculate_readiness({"completed": True, "todos": []}), 100)
        self.assertEqual(calculate_readiness({"todos": []}), 0)

    def test_settings_sanitize_and_persist(self):
        backend = FakeSettingsBackend()
        dirty = dashboard_settings_from_mapping({
            "timeframe": "bad",
            "sort": "bad",
            "view_mode": "bad",
            "show_completed": "yes",
            "show_next_due": "off",
            "summary_metric_keys": ["bad", "due_today", "due_today", "open_total"],
        })

        self.assertEqual(dirty.timeframe, "next_7_days")
        self.assertEqual(dirty.sort, "due_soonest")
        self.assertEqual(dirty.view_mode, "grid")
        self.assertTrue(dirty.show_completed)
        self.assertFalse(dirty.show_next_due)
        self.assertEqual(dirty.summary_metric_keys, ("due_today", "open_total", "overdue", "due_this_week"))

        saved = save_dashboard_settings(
            backend,
            "user",
            DashboardSettings(
                sort="least_ready",
                show_next_due=False,
                show_timeline=False,
                summary_metric_keys=("open_total", "open_todos", "with_todos", "low_readiness"),
            ),
        )
        loaded = load_dashboard_settings(backend, "user")

        self.assertEqual(saved.sort, "least_ready")
        self.assertEqual(loaded.sort, "least_ready")
        self.assertFalse(loaded.show_next_due)
        self.assertFalse(loaded.show_timeline)
        self.assertEqual(loaded.summary_metric_keys, ("open_total", "open_todos", "with_todos", "low_readiness"))

    def test_service_filters_groups_and_sorts_deadline_data(self):
        vault = FakeVault()
        now = datetime(2026, 6, 8, 10, 0, 0)
        settings = DashboardSettings(timeframe="next_30_days", show_completed=True)

        data = build_dashboard_data(vault, "user", settings, now=now)
        ids = [item.assignment_id for item in data.items]

        self.assertNotIn("hidden", ids)
        self.assertNotIn("archived_assignment", ids)
        self.assertNotIn("done", ids)
        self.assertNotIn("finished", ids)
        self.assertEqual(data.next_due.assignment_id, "lab")
        self.assertEqual(data.summary.due_today, 1)
        self.assertEqual(data.summary.completed_this_week, 0)
        self.assertEqual([group.key for group in data.groups], ["overdue", "today", "tomorrow", "this_week", "later", "no_due_date"])
        self.assertIn("nodue", [item.assignment_id for item in data.groups[-1].items])

    def test_service_hides_completed_and_no_due_when_configured(self):
        vault = FakeVault()
        now = datetime(2026, 6, 8, 10, 0, 0)
        settings = DashboardSettings(timeframe="next_30_days", show_completed=False, show_no_due_date=False)

        data = build_dashboard_data(vault, "user", settings, now=now)
        ids = [item.assignment_id for item in data.items]

        self.assertNotIn("done", ids)
        self.assertNotIn("finished", ids)
        self.assertNotIn("nodue", ids)


if __name__ == "__main__":
    unittest.main()
