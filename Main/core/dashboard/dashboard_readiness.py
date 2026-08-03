from __future__ import annotations

from .dashboard_models import TodoCounts


def todo_counts(assignment: dict | None) -> TodoCounts:
    todos = (assignment or {}).get("todos") or []
    total = len(todos)
    completed = sum(1 for todo in todos if bool(todo.get("done")))
    return TodoCounts(completed=completed, total=total)


def calculate_readiness(assignment: dict | None) -> int:
    assignment = assignment or {}
    if bool(assignment.get("completed")):
        return 100

    counts = todo_counts(assignment)
    if counts.total <= 0:
        return 0

    todo_ratio = counts.completed / counts.total
    complete_ratio = 1 if bool(assignment.get("completed")) else 0
    readiness = (todo_ratio * 0.8 + complete_ratio * 0.2) * 100
    return max(0, min(100, int(round(readiness))))

