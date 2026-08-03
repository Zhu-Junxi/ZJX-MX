from __future__ import annotations

from typing import Literal

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

GoogleFileKind = Literal["docs", "slides", "sheets"]

GOOGLE_CREATE_URLS: dict[GoogleFileKind, str] = {
    "docs": "https://docs.new",
    "slides": "https://slides.new",
    "sheets": "https://sheets.new",
}

GOOGLE_TITLES: dict[GoogleFileKind, str] = {
    "docs": "Google Docs",
    "slides": "Google Slides",
    "sheets": "Google Sheets",
}


def open_google_creator(kind: GoogleFileKind) -> str:
    """Open the Google new-file shortcut and return the URL used."""
    url = GOOGLE_CREATE_URLS[kind]
    QDesktopServices.openUrl(QUrl(url))
    return url
