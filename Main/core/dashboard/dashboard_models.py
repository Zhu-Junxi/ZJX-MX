from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


TIMEFRAME_OPTIONS = {
    "today": 0,
    "next_3_days": 3,
    "next_7_days": 7,
    "next_14_days": 14,
    "next_30_days": 30,
    "all_upcoming": None,
}

SORT_OPTIONS = {
    "due_soonest",
    "least_ready",
    "course",
    "assignment_name",
    "recently_updated",
    "overdue_first",
}

VIEW_MODES = {"grid", "list"}

GROUP_ORDER = ["overdue", "today", "tomorrow", "this_week", "later", "no_due_date"]

SUMMARY_METRIC_KEYS = {
    "overdue",
    "due_today",
    "due_tomorrow",
    "due_this_week",
    "no_due_date",
    "later",
    "open_total",
    "open_todos",
    "resources_total",
    "with_todos",
    "low_readiness",
}

DEFAULT_SUMMARY_METRIC_KEYS = ("overdue", "due_today", "due_this_week", "no_due_date")

GROUP_TITLES = {
    "overdue": "Overdue",
    "today": "Today",
    "tomorrow": "Tomorrow",
    "this_week": "This Week",
    "later": "Later",
    "no_due_date": "No Due Date",
}


@dataclass(frozen=True)
class CountdownDisplay:
    main_text: str
    sub_text: str
    category: str
    severity: str
    total_seconds_remaining: int | None
    is_overdue: bool = False
    is_due_now: bool = False
    is_no_due_date: bool = False
    is_completed: bool = False


@dataclass(frozen=True)
class TodoCounts:
    completed: int = 0
    total: int = 0

    @property
    def open(self) -> int:
        return max(0, self.total - self.completed)


@dataclass(frozen=True)
class DashboardSettings:
    timeframe: str = "next_7_days"
    sort: str = "due_soonest"
    view_mode: str = "grid"
    summary_metric_keys: tuple[str, str, str, str] = DEFAULT_SUMMARY_METRIC_KEYS
    show_completed: bool = False
    show_no_due_date: bool = True
    show_todos: bool = True
    show_readiness: bool = True
    show_summary_metrics: bool = True
    show_next_due: bool = True
    show_timeline: bool = True
    compact_cards: bool = False


@dataclass(frozen=True)
class DashboardAssignmentItem:
    user_id: str
    course_id: str
    course_code: str
    course_name: str
    assignment_id: str
    title: str
    assignment: dict[str, Any]
    course: dict[str, Any]
    due_at: datetime | None
    due_text: str
    countdown: CountdownDisplay
    group: str
    readiness: int
    todos: TodoCounts
    completed: bool
    updated_at: str = ""
    canvas_url: str = ""


@dataclass(frozen=True)
class DashboardGroup:
    key: str
    title: str
    items: tuple[DashboardAssignmentItem, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SummaryMetrics:
    overdue: int = 0
    due_today: int = 0
    due_this_week: int = 0
    completed_this_week: int = 0


@dataclass(frozen=True)
class DashboardData:
    settings: DashboardSettings
    items: tuple[DashboardAssignmentItem, ...]
    groups: tuple[DashboardGroup, ...]
    next_due: DashboardAssignmentItem | None
    timeline_items: tuple[DashboardAssignmentItem, ...]
    summary: SummaryMetrics
