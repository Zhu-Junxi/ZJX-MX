from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from core.helpers import normalise_url


LINK_RESOURCE_TYPES = {"external_link", "youtube", "google_drive", "canvas"}
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def safe_shortcut_name(value: str, fallback: str = "Untitled") -> str:
    cleaned = "".join("_" if char in '<>:"/\\|?*' or ord(char) < 32 else char for char in str(value or ""))
    cleaned = " ".join(cleaned.split()).strip(" .")
    cleaned = cleaned or fallback
    if cleaned.upper() in WINDOWS_RESERVED_NAMES:
        cleaned = f"{cleaned}_"
    return cleaned[:140].rstrip(" .") or fallback


def shortcut_filename(title: str) -> str:
    return f"{safe_shortcut_name(title, fallback='Link')}.url"


def is_url_shortcut(path) -> bool:
    return Path(path).suffix.lower() == ".url"


def classify_link_resource_type(url: str) -> str:
    parsed = urlparse(normalise_url(url or ""))
    host = parsed.netloc.lower()
    combined = f"{host}{parsed.path.lower()}"

    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "drive.google.com" in host or "docs.google.com" in host:
        return "google_drive"
    if "canvas" in combined:
        return "canvas"
    return "external_link"


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def read_url_shortcut(path) -> dict | None:
    path = Path(path)
    if not is_url_shortcut(path) or not path.is_file():
        return None

    values = {}
    for line in _read_text(path).splitlines():
        line = line.strip()
        if not line or line.startswith("["):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
        elif ":" in line:
            key, value = line.split(":", 1)
        else:
            continue
        values[key.strip().lower()] = value.strip()

    url = values.get("url", "").strip()
    if not url:
        return None

    resource_type = values.get("type", "").strip()
    if resource_type not in LINK_RESOURCE_TYPES:
        resource_type = classify_link_resource_type(url)

    tags = [tag.strip() for tag in values.get("tags", "").split(",") if tag.strip()]
    return {
        "url": normalise_url(url),
        "title": values.get("title", "").strip() or path.stem,
        "type": resource_type,
        "tags": tags,
    }


def url_shortcut_body(url: str, *, title: str = "", resource_type: str = "external_link", tags=None, fallback_title: str = "Link"):
    url = normalise_url(url or "")
    tags = list(tags or [])
    return (
        f"[InternetShortcut]\n"
        f"URL={url}\n"
        f"\n"
        f"[ZJX LMS Resource]\n"
        f"Title: {title or fallback_title}\n"
        f"Type: {resource_type if resource_type in LINK_RESOURCE_TYPES else 'external_link'}\n"
        f"Tags: {', '.join(tags)}\n"
    )


def write_url_shortcut(path, url: str, *, title: str = "", resource_type: str = "external_link", tags=None):
    path = Path(path)
    body = url_shortcut_body(
        url,
        title=title,
        resource_type=resource_type,
        tags=tags,
        fallback_title=path.stem,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path
