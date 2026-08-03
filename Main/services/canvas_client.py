from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import Message
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from core.validation import validate_canvas_base_url, validate_canvas_token


class CanvasAPIError(RuntimeError):
    """Raised for Canvas connection, authentication, and API response errors."""


@dataclass(frozen=True)
class CanvasSyncResult:
    courses_created: int = 0
    courses_updated: int = 0
    assignments_created: int = 0
    assignments_updated: int = 0
    skipped_courses: int = 0
    assignment_failures: tuple[str, ...] = ()

    @property
    def imported_courses(self):
        return self.courses_created + self.courses_updated

    @property
    def imported_assignments(self):
        return self.assignments_created + self.assignments_updated


class CanvasClient:
    """Minimal Canvas LMS REST client used by ZJX LMS.

    The client deliberately uses the Python standard library so the desktop app
    does not require an extra ``requests`` dependency to perform the first API
    sync.
    """

    def __init__(self, base_url, access_token, timeout=30):
        self.base_url = validate_canvas_base_url(base_url)
        self.access_token = validate_canvas_token(access_token, required=True)
        self.timeout = timeout

    def api_url(self, path, params=None):
        clean_path = path.lstrip("/")
        if not clean_path.startswith("api/v1/"):
            clean_path = f"api/v1/{clean_path}"

        url = urljoin(f"{self.base_url}/", clean_path)

        if params:
            query = urlencode({key: value for key, value in params.items() if value is not None}, doseq=True)
            if query:
                url = f"{url}?{query}"

        return url

    def get_json(self, path_or_url, params=None):
        url = path_or_url if str(path_or_url).startswith(("http://", "https://")) else self.api_url(path_or_url, params)
        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
                "User-Agent": "ZJX-LMS/0.1",
            },
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                payload = json.loads(raw) if raw else None
                return payload, response.headers
        except HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            if error.code in {401, 403}:
                raise CanvasAPIError("Canvas rejected the token. Check the user's Canvas access token.") from error
            raise CanvasAPIError(f"Canvas API returned HTTP {error.code}: {body[:400]}") from error
        except URLError as error:
            raise CanvasAPIError(f"Could not connect to Canvas: {error.reason}") from error
        except json.JSONDecodeError as error:
            raise CanvasAPIError("Canvas returned a response that was not valid JSON.") from error

    def get_paginated(self, path, params=None):
        next_url = self.api_url(path, params or {})

        while next_url:
            payload, headers = self.get_json(next_url)
            if isinstance(payload, list):
                for item in payload:
                    yield item
            elif payload is not None:
                yield payload

            next_url = self.next_link(headers)

    @staticmethod
    def next_link(headers: Message):
        link_header = headers.get("Link") if headers else None
        if not link_header:
            return None

        for part in link_header.split(","):
            section = part.strip()
            if 'rel="next"' not in section:
                continue

            start = section.find("<")
            end = section.find(">")
            if start != -1 and end != -1 and end > start:
                return section[start + 1:end]

        return None

    def fetch_courses(self, enrollment_state="active"):
        return list(
            self.get_paginated(
                "courses",
                {
                    "per_page": 100,
                    "enrollment_state": enrollment_state,
                    "include[]": "term",
                },
            )
        )

    def fetch_current_courses(self):
        return [course for course in self.fetch_courses() if self.course_is_current(course)]

    def fetch_sync_courses(self):
        courses_by_id = {}
        for enrollment_state in ("active", "completed"):
            for course in self.fetch_courses(enrollment_state=enrollment_state):
                canvas_id = str(course.get("id") or "").strip()
                if canvas_id:
                    courses_by_id[canvas_id] = course
        return list(courses_by_id.values())

    def fetch_user_profile(self):
        payload, _headers = self.get_json("users/self/profile")
        return payload if isinstance(payload, dict) else {}

    def fetch_avatar_bytes(self, avatar_url, *, max_bytes=5 * 1024 * 1024):
        if not avatar_url:
            return b"", ""

        request = Request(
            str(avatar_url),
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "image/*,*/*;q=0.8",
                "User-Agent": "ZJX-LMS/0.1",
            },
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                data = response.read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise CanvasAPIError("Canvas profile picture was too large to cache.")
                return data, content_type
        except HTTPError as error:
            if error.code in {401, 403}:
                raise CanvasAPIError("Canvas rejected the token while fetching the profile picture.") from error
            raise CanvasAPIError(f"Canvas profile picture returned HTTP {error.code}.") from error
        except URLError as error:
            raise CanvasAPIError(f"Could not fetch Canvas profile picture: {error.reason}") from error

    def fetch_assignments(self, canvas_course_id):
        return list(
            self.get_paginated(
                f"courses/{canvas_course_id}/assignments",
                {
                    "per_page": 100,
                    "order_by": "due_at",
                },
            )
        )

    def fetch_announcements(self, canvas_course_id):
        return [
            self.normalise_announcement(item, canvas_course_id)
            for item in self.get_paginated(
                "announcements",
                {
                    "per_page": 100,
                    "context_codes[]": f"course_{canvas_course_id}",
                    "active_only": False,
                },
            )
        ]

    @staticmethod
    def strip_html(value):
        if not value:
            return ""
        text = re.sub(r"<br\s*/?>", "\n", str(value), flags=re.IGNORECASE)
        text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    def normalise_announcement(self, announcement, canvas_course_id):
        title = announcement.get("title") or announcement.get("message") or "Untitled announcement"
        posted_at = announcement.get("posted_at") or announcement.get("created_at") or announcement.get("delayed_post_at") or ""
        return {
            "id": str(announcement.get("id") or announcement.get("url") or title),
            "title": str(title).strip(),
            "date": posted_at,
            "source": "Canvas",
            "body": self.strip_html(announcement.get("message") or announcement.get("description") or ""),
            "canvas_id": str(announcement.get("id", "")),
            "canvas_course_id": str(canvas_course_id),
            "canvas_html_url": announcement.get("html_url") or announcement.get("url") or "",
            "canvas_read_state": announcement.get("read_state", ""),
        }

    @staticmethod
    def course_is_current(course):
        end_at = course.get("end_at")
        workflow_state = str(course.get("workflow_state", "")).lower()

        if workflow_state in {"deleted", "unpublished", "completed"}:
            return False

        if not end_at:
            return True

        try:
            end_date = datetime.fromisoformat(end_at.replace("Z", "+00:00"))
        except ValueError:
            return True

        return datetime.now(timezone.utc) <= end_date
