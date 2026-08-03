import json
import os
import re
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def slugify(text):
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return text or "untitled"


def normalise_url(url):
    url = url.strip()

    if not url:
        return url

    parsed = urlparse(url)

    if not parsed.scheme:
        return "https://" + url

    return url


def safe_read_json(path, default):
    path = Path(path)

    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        return default


def safe_write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    temp_path = Path(temp_name)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            temp_path.unlink()
        except OSError:
            pass
        raise


def unique_path(directory, filename):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    original = Path(filename)
    stem = original.stem
    suffix = original.suffix

    candidate = directory / original.name
    counter = 2

    while candidate.exists():
        candidate = directory / f"{stem}_{counter}{suffix}"
        counter += 1

    return candidate


def unique_folder_path(directory, folder_name):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    base_name = slugify(folder_name)
    candidate = directory / base_name
    counter = 2

    while candidate.exists():
        candidate = directory / f"{base_name}_{counter}"
        counter += 1

    return candidate


def format_size(size_bytes):
    size = float(size_bytes)

    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024

    return f"{size:.2f} TB"


def parse_due_date(date_text):
    """Parse manual and Canvas due-date values.

    Supported values:
    - YYYY-MM-DD
    - YYYY-MM-DD HH:MM
    - YYYY-MM-DD HH:MM:SS
    - ISO datetimes such as 2026-07-12T13:59:59Z
    """
    if not date_text:
        return None

    text = str(date_text).strip()

    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def due_date_has_explicit_time(date_text):
    """Return True when the user/Canvas supplied an actual time component."""
    if not date_text:
        return False

    text = str(date_text).strip()
    if "T" in text:
        return True

    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(:\d{2})?", text))


def local_due_datetime(date_text):
    """Return a due datetime normalised for local display/comparison."""
    due_date = parse_due_date(date_text)

    if not due_date:
        return None

    if due_date.tzinfo is not None:
        return due_date.astimezone()

    return due_date


def format_due_datetime(date_text):
    """Return a user-facing due-date string without hiding HH:MM:SS when available."""
    due_date = local_due_datetime(date_text)

    if not due_date:
        return "No due date"

    if due_date_has_explicit_time(date_text):
        return due_date.strftime("%Y-%m-%d %H:%M:%S")

    return due_date.strftime("%Y-%m-%d")


def seconds_until_due(date_text):
    """Return signed seconds until the due time, or None for missing/invalid dates."""
    due_date = local_due_datetime(date_text)

    if not due_date:
        return None

    if due_date_has_explicit_time(date_text):
        now = datetime.now(due_date.tzinfo) if due_date.tzinfo else datetime.now()
        return int((due_date - now).total_seconds())

    today = datetime.now().date()
    return (due_date.date() - today).days * 86400


def is_past_date(date_string: str) -> bool:
    """
    Returns True if the current UTC time is past the given ISO datetime string.
    
    Example input:
    "2026-07-12T13:59:59Z"
    """
    try:
        # Convert "Z" into "+00:00" so Python understands it as UTC
        target_date = datetime.fromisoformat(date_string.replace("Z", "+00:00"))

        # Get current UTC time
        current_date = datetime.now(timezone.utc)

        return current_date > target_date

    except ValueError:
        raise ValueError("Invalid date format. Expected format like: 2026-07-12T13:59:59Z")

def is_due_date_past(date_text) -> bool:
    """Return True when a due-date value is genuinely past.

    Timed values are compared to the exact hour/minute/second. Date-only values
    stay active until the following local day so a simple YYYY-MM-DD due date
    does not disappear during the due day.
    """
    remaining_seconds = seconds_until_due(date_text)

    if remaining_seconds is None:
        return False

    return remaining_seconds < 0
