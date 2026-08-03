from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from core.helpers import parse_due_date

from .dashboard_models import (
    GROUP_ORDER,
    GROUP_TITLES,
    DashboardAssignmentItem,
    DashboardData,
    DashboardGroup,
    DashboardSettings,
    SummaryMetrics,
)
from .dashboard_readiness import calculate_readiness, todo_counts
from .dashboard_time import deadline_group, format_time_left, is_inside_timeframe, normalise_due_datetime


def build_dashboard_data(vault, user_id: str | None, settings: DashboardSettings, now: datetime | None = None) -> DashboardData:
    current = now or datetime.now()
    settings = settings or DashboardSettings()
    items = tuple(_sorted_items(_collect_items(vault, user_id, settings, current), settings.sort))
    grouped = _group_items(items)
    next_due = next((item for item in items if item.due_at and not item.completed), None)
    timeline_items = tuple(item for item in items if item.due_at and not item.completed)[:12]

    return DashboardData(
        settings=settings,
        items=items,
        groups=grouped,
        next_due=next_due,
        timeline_items=timeline_items,
        summary=_summary_metrics(items, current),
    )


def visible_courses(vault, user_id: str | None) -> list[dict]:
    if not user_id:
        return []

    user = vault.get_user(user_id) if hasattr(vault, "get_user") else {}
    blacklisted = {str(item) for item in (user or {}).get("canvas_blacklisted_course_ids", [])}
    favourites = {str(item) for item in (user or {}).get("canvas_favourite_course_ids", [])}
    courses = []

    for course in vault.get_courses(user_id):
        if bool((course or {}).get("archived")):
            continue
        canvas_id = str((course or {}).get("canvas_id") or "").strip()
        if canvas_id and canvas_id in blacklisted:
            continue
        courses.append(course)

    return sorted(
        courses,
        key=lambda course: (
            0 if str((course or {}).get("canvas_id") or "").strip() in favourites else 1,
            0 if (course or {}).get("source") == "canvas" else 1,
            ((course or {}).get("code") or (course or {}).get("name") or "").lower(),
            ((course or {}).get("name") or "").lower(),
        ),
    )


def _collect_items(vault, user_id: str | None, settings: DashboardSettings, now: datetime) -> list[DashboardAssignmentItem]:
    if not user_id:
        return []

    items: list[DashboardAssignmentItem] = []
    for course in visible_courses(vault, user_id):
        course_id = course.get("id")
        if not course_id:
            continue

        for assignment in vault.get_assignments(user_id, course_id):
            completed = _assignment_is_finished(assignment)
            if completed:
                continue

            due_text = assignment.get("canvas_due_at") or assignment.get("due_date") or ""
            due_at = normalise_due_datetime(due_text)
            if not due_at and not settings.show_no_due_date:
                continue
            if not is_inside_timeframe(now, due_text, settings.timeframe):
                continue

            countdown = format_time_left(now, due_text, is_completed=completed)
            todos = todo_counts(assignment)
            items.append(
                DashboardAssignmentItem(
                    user_id=user_id,
                    course_id=course_id,
                    course_code=course.get("code") or course.get("name") or "Course",
                    course_name=course.get("name") or "",
                    assignment_id=assignment.get("id") or "",
                    title=assignment.get("title") or "Untitled assignment",
                    assignment=assignment,
                    course=course,
                    due_at=due_at,
                    due_text=due_text,
                    countdown=countdown,
                    group=deadline_group(now, due_text, is_completed=completed),
                    readiness=calculate_readiness(assignment),
                    todos=todos,
                    completed=completed,
                    updated_at=assignment.get("updated_at") or assignment.get("created_at") or "",
                    canvas_url=assignment.get("canvas_html_url") or "",
                )
            )

    return items


def _assignment_is_finished(assignment: dict) -> bool:
    if bool(assignment.get("completed")):
        return True

    status = str(assignment.get("status") or "").strip().lower()
    return status in {"completed", "complete", "finished", "done"}


def _sorted_items(items: list[DashboardAssignmentItem], sort_mode: str) -> list[DashboardAssignmentItem]:
    if sort_mode == "least_ready":
        return sorted(items, key=lambda item: (item.readiness, _due_sort_value(item), item.course_code.lower(), item.title.lower()))
    if sort_mode == "course":
        return sorted(items, key=lambda item: (item.course_code.lower(), _due_sort_value(item), item.title.lower()))
    if sort_mode == "assignment_name":
        return sorted(items, key=lambda item: (item.title.lower(), _due_sort_value(item), item.course_code.lower()))
    if sort_mode == "recently_updated":
        return sorted(items, key=lambda item: (item.updated_at or "",), reverse=True)
    if sort_mode == "overdue_first":
        return sorted(items, key=lambda item: (0 if item.group == "overdue" else 1, _due_sort_value(item), item.title.lower()))
    return sorted(items, key=lambda item: (_due_sort_value(item), item.course_code.lower(), item.title.lower()))


def _due_sort_value(item: DashboardAssignmentItem) -> datetime:
    return item.due_at or datetime.max


def _group_items(items: tuple[DashboardAssignmentItem, ...]) -> tuple[DashboardGroup, ...]:
    by_group = defaultdict(list)
    for item in items:
        by_group[item.group].append(item)

    groups = []
    for key in GROUP_ORDER:
        groups.append(DashboardGroup(key=key, title=GROUP_TITLES[key], items=tuple(by_group.get(key, []))))
    return tuple(groups)


def _summary_metrics(items: tuple[DashboardAssignmentItem, ...], now: datetime) -> SummaryMetrics:
    today = now.date()
    week_end = today + timedelta(days=7)
    overdue = 0
    due_today = 0
    due_this_week = 0
    completed_this_week = 0

    for item in items:
        if item.completed:
            completed_at = parse_due_date(item.assignment.get("completed_at") or "")
            if completed_at and today <= completed_at.date() <= week_end:
                completed_this_week += 1
            continue

        if not item.due_at:
            continue
        if item.due_at < now:
            overdue += 1
        if item.due_at.date() == today:
            due_today += 1
        if today <= item.due_at.date() <= week_end:
            due_this_week += 1

    return SummaryMetrics(
        overdue=overdue,
        due_today=due_today,
        due_this_week=due_this_week,
        completed_this_week=completed_this_week,
    )
