from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.helpers import format_due_datetime, local_due_datetime, seconds_until_due


REMINDER_STAGES = (
    ("7d", 7 * 86400),
    ("3d", 3 * 86400),
    ("1d", 86400),
    ("6h", 6 * 3600),
    ("1h", 3600),
    ("overdue", -1),
)


@dataclass(frozen=True)
class ReminderCandidate:
    user: dict
    course: dict
    assignment: dict
    due_text: str
    due_display: str
    remaining_seconds: int
    stage: str
    notification_key: str

    @property
    def overdue(self):
        return self.stage == "overdue"

    @property
    def course_label(self):
        return self.course.get("code") or self.course.get("name") or "Course"

    @property
    def assignment_title(self):
        return self.assignment.get("title") or "Untitled assignment"


def collect_reminder_candidates(vault, enabled_stages=None, sent_keys=None, now=None):
    """Return due reminder candidates without touching UI state."""
    enabled_stages = set(enabled_stages or [stage for stage, _seconds in REMINDER_STAGES])
    sent_keys = set(sent_keys or [])
    candidates = []

    for user in vault.get_users():
        blacklisted = {str(item) for item in user.get("canvas_blacklisted_course_ids", [])}
        for course in vault.get_courses(user.get("id")):
            if course.get("archived"):
                continue
            canvas_id = str(course.get("canvas_id") or "")
            if canvas_id and canvas_id in blacklisted:
                continue

            for assignment in vault.get_assignments(user.get("id"), course.get("id")):
                candidate = reminder_candidate_for_assignment(user, course, assignment, enabled_stages, sent_keys)
                if candidate:
                    candidates.append(candidate)

    return sorted(candidates, key=lambda item: (item.remaining_seconds, item.course_label.lower(), item.assignment_title.lower()))


def reminder_candidate_for_assignment(user, course, assignment, enabled_stages, sent_keys):
    if not assignment or assignment.get("completed"):
        return None

    due_text = assignment.get("canvas_due_at") or assignment.get("due_date") or ""
    due_dt = local_due_datetime(due_text)
    remaining = seconds_until_due(due_text)
    if due_dt is None or remaining is None:
        return None

    stage = stage_for_remaining_seconds(remaining)
    if stage not in enabled_stages:
        return None

    key = reminder_key(user, course, assignment, due_text, stage)
    if key in sent_keys:
        return None

    return ReminderCandidate(
        user=user,
        course=course,
        assignment=assignment,
        due_text=due_text,
        due_display=format_due_datetime(due_text),
        remaining_seconds=remaining,
        stage=stage,
        notification_key=key,
    )


def stage_for_remaining_seconds(remaining):
    if remaining < 0:
        return "overdue"
    for stage, threshold in sorted(
        ((stage, threshold) for stage, threshold in REMINDER_STAGES if stage != "overdue"),
        key=lambda item: item[1],
    ):
        if remaining <= threshold:
            return stage
    return ""


def reminder_key(user, course, assignment, due_text, stage):
    return "|".join(
        [
            str(user.get("id") or ""),
            str(course.get("id") or ""),
            str(assignment.get("id") or ""),
            str(due_text or ""),
            str(stage or ""),
        ]
    )


def snooze_until(minutes):
    return datetime.now().timestamp() + max(1, int(minutes)) * 60
