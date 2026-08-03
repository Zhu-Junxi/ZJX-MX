from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse


class ValidationError(ValueError):
    """Raised when user-entered data is unsafe or invalid for the app model."""


DEFAULT_CANVAS_BASE_URL = "https://canvas.sydney.edu.au"


def clean_string(value, *, field_name="Value", required=False, max_length=255):
    text = "" if value is None else str(value).strip()

    if required and not text:
        raise ValidationError(f"{field_name} is required.")

    if len(text) > max_length:
        raise ValidationError(f"{field_name} must be {max_length} characters or fewer.")

    return text


def validate_canvas_base_url(value):
    url = clean_string(
        value or DEFAULT_CANVAS_BASE_URL,
        field_name="Canvas URL",
        required=True,
        max_length=300,
    ).rstrip("/")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("Canvas URL must look like https://canvas.your-uni.edu.au")

    return url


def validate_canvas_token(value, *, required=False):
    token = clean_string(value, field_name="Canvas access token", required=required, max_length=2048)

    if not token:
        return ""

    if any(character.isspace() for character in token):
        raise ValidationError("Canvas access token must not contain spaces or new lines.")

    if len(token) < 10:
        raise ValidationError("Canvas access token looks too short.")

    return token


def validate_user_payload(payload, *, token_required=False):
    return {
        "name": clean_string(payload.get("name"), field_name="Name", required=True, max_length=80),
        "university": clean_string(payload.get("university"), field_name="University", max_length=120),
        "canvas_base_url": validate_canvas_base_url(payload.get("canvas_base_url")),
        "canvas_access_token": validate_canvas_token(
            payload.get("canvas_access_token"),
            required=token_required,
        ),
    }


def validate_course_payload(code, name):
    return {
        "code": clean_string(code, field_name="Course code", required=True, max_length=60),
        "name": clean_string(name, field_name="Course name", required=True, max_length=160),
    }


def validate_assignment_payload(title, due_date="", status="Not started"):
    clean_due_date = clean_string(due_date, field_name="Due date", max_length=60)

    if clean_due_date:
        parse_user_due_date(clean_due_date)

    return {
        "title": clean_string(title, field_name="Assignment title", required=True, max_length=180),
        "due_date": clean_due_date,
        "status": clean_string(status or "Not started", field_name="Status", max_length=80) or "Not started",
    }


def parse_user_due_date(value):
    """Validate date strings typed by the user.

    Manual entries stay simple: YYYY-MM-DD, YYYY-MM-DD HH:MM, YYYY-MM-DD HH:MM:SS, or Canvas-style ISO.
    """
    text = clean_string(value, field_name="Due date", required=True, max_length=60)

    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValidationError(
            "Due date must be blank, YYYY-MM-DD, YYYY-MM-DD HH:MM, YYYY-MM-DD HH:MM:SS, or Canvas ISO datetime."
        ) from error
