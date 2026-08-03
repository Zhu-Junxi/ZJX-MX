from __future__ import annotations

from datetime import datetime, timedelta

from core.helpers import due_date_has_explicit_time, local_due_datetime

from .dashboard_models import CountdownDisplay


def normalise_due_datetime(due_value) -> datetime | None:
    """Return a local, timezone-naive datetime for stable dashboard comparisons."""
    due_at = local_due_datetime(due_value)
    if not due_at:
        return None

    if due_at.tzinfo is not None:
        due_at = due_at.astimezone().replace(tzinfo=None)

    return due_at


def normalise_now(now: datetime | None = None) -> datetime:
    now = now or datetime.now()
    if now.tzinfo is not None:
        return now.astimezone().replace(tzinfo=None)
    return now


def format_time_left(now: datetime | None, due_at, is_completed=False) -> CountdownDisplay:
    """Format exact remaining time without vague deadline labels."""
    if is_completed:
        return CountdownDisplay(
            main_text="Done",
            sub_text="Completed",
            category="completed",
            severity="completed",
            total_seconds_remaining=None,
            is_completed=True,
        )

    due_dt = normalise_due_datetime(due_at)
    if not due_dt:
        return CountdownDisplay(
            main_text="-",
            sub_text="No due date",
            category="no_due_date",
            severity="none",
            total_seconds_remaining=None,
            is_no_due_date=True,
        )

    current = normalise_now(now)
    remaining = int((due_dt - current).total_seconds())
    is_due_now = abs(remaining) < 60
    is_overdue = remaining < 0 and not is_due_now
    absolute = abs(remaining)
    main = _format_seconds_exact(absolute if is_overdue else max(0, remaining))

    if is_due_now:
        return CountdownDisplay(
            main_text="Now",
            sub_text="Due now",
            category="due_now",
            severity="danger",
            total_seconds_remaining=remaining,
            is_due_now=True,
        )

    if is_overdue:
        return CountdownDisplay(
            main_text=main,
            sub_text="overdue",
            category="overdue",
            severity="danger",
            total_seconds_remaining=remaining,
            is_overdue=True,
        )

    severity = "safe"
    category = "later"
    if remaining <= 24 * 3600:
        severity = "danger"
        category = "today"
    elif remaining <= 3 * 24 * 3600:
        severity = "warning"
        category = "soon"

    return CountdownDisplay(
        main_text=main,
        sub_text="until due",
        category=category,
        severity=severity,
        total_seconds_remaining=remaining,
    )


def deadline_group(now: datetime | None, due_at, is_completed=False) -> str:
    if is_completed:
        due_dt = normalise_due_datetime(due_at)
    else:
        due_dt = normalise_due_datetime(due_at)

    if not due_dt:
        return "no_due_date"

    current = normalise_now(now)
    today = current.date()
    due_date = due_dt.date()

    if due_dt < current:
        return "overdue"
    if due_date == today:
        return "today"
    if due_date == today + timedelta(days=1):
        return "tomorrow"
    if due_date <= today + timedelta(days=7):
        return "this_week"
    return "later"


def is_inside_timeframe(now: datetime | None, due_at, timeframe: str) -> bool:
    due_dt = normalise_due_datetime(due_at)
    if not due_dt:
        return True

    current = normalise_now(now)
    if due_dt < current:
        return True

    if timeframe == "today":
        return due_dt.date() == current.date()

    days = {
        "next_3_days": 3,
        "next_7_days": 7,
        "next_14_days": 14,
        "next_30_days": 30,
    }.get(timeframe)

    if days is None:
        return True

    return due_dt <= current + timedelta(days=days)


def display_due_text(due_value) -> str:
    due_dt = normalise_due_datetime(due_value)
    if not due_dt:
        return "No due date"
    if due_date_has_explicit_time(due_value):
        return due_dt.strftime("%d %b %Y %H:%M")
    return due_dt.strftime("%d %b %Y")


def _format_seconds_exact(seconds: int) -> str:
    seconds = max(0, int(seconds))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"
