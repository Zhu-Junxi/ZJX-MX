from __future__ import annotations

import html
import shutil
import tempfile
from pathlib import Path
from typing import Iterable, List

from PySide6.QtCore import QMimeData, Qt, QTimer, QUrl, QRect
from PySide6.QtGui import QDrag, QPixmap, QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import QApplication


DRAG_GUARD_MS = 15000


def _unique_child_path(parent: Path, name: str) -> Path:
    candidate = parent / name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        candidate = parent / f"{stem} {index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _copy_path_to_stage(source: Path, stage_dir: Path) -> Path | None:
    source = Path(source)
    if not source.exists():
        return None

    destination = _unique_child_path(stage_dir, source.name)
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return destination


def stage_drag_paths(owner, paths: Iterable[Path]) -> List[Path]:
    """Copy paths to a temp export folder and retain it for the app lifetime."""
    unique_sources = []
    seen = set()
    for path in paths:
        path = Path(path)
        try:
            key = str(path.resolve())
        except Exception:
            key = str(path)
        if key in seen or not path.exists():
            continue
        seen.add(key)
        unique_sources.append(path)

    if not unique_sources:
        return []

    stage_dir = Path(tempfile.mkdtemp(prefix="zjx_lms_drag_export_"))
    staged_paths = []
    for source in unique_sources:
        try:
            staged = _copy_path_to_stage(source, stage_dir)
            if staged and staged.exists():
                staged_paths.append(staged)
        except Exception as error:
            print(f"Could not stage drag path {source}: {error}")

    if staged_paths:
        temp_dirs = getattr(owner, "_external_drag_temp_dirs", None)
        if temp_dirs is None:
            temp_dirs = []
            setattr(owner, "_external_drag_temp_dirs", temp_dirs)
        temp_dirs.append(stage_dir)
    else:
        shutil.rmtree(stage_dir, ignore_errors=True)

    return staged_paths



def _build_drag_preview_pixmap(paths: Iterable[Path]) -> QPixmap:
    """Create a small stable drag badge instead of grabbing the whole tree panel."""
    paths = [Path(path) for path in paths]
    count = len(paths)
    title = paths[0].name if count == 1 else f"{count} items"
    subtitle = "Drag to upload/copy" if count == 1 else "Drag selected items"

    width = 260
    height = 70
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    outer = QRect(2, 2, width - 4, height - 4)
    painter.setBrush(QColor(17, 24, 39, 238))
    painter.setPen(QPen(QColor(93, 140, 255, 210), 1))
    painter.drawRoundedRect(outer, 14, 14)

    icon_rect = QRect(14, 17, 36, 36)
    painter.setBrush(QColor(37, 99, 235, 230))
    painter.setPen(QPen(QColor(147, 197, 253, 220), 1))
    painter.drawRoundedRect(icon_rect, 10, 10)

    painter.setPen(QColor("#ffffff"))
    icon_font = QFont()
    icon_font.setPointSize(15)
    icon_font.setBold(True)
    painter.setFont(icon_font)
    painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, str(count) if count > 1 else "↗")

    title_font = QFont()
    title_font.setPointSize(10)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.setPen(QColor("#f8fafc"))
    painter.drawText(QRect(62, 14, width - 78, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)

    sub_font = QFont()
    sub_font.setPointSize(8)
    painter.setFont(sub_font)
    painter.setPen(QColor("#aab8ce"))
    painter.drawText(QRect(62, 38, width - 78, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, subtitle)

    painter.end()
    return pixmap



def _normalise_drag_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    lower = url.lower()
    if lower.startswith(("http://", "https://", "mailto:", "ftp://")):
        return url
    return "https://" + url


def _build_link_drag_preview_pixmap(urls: Iterable[str]) -> QPixmap:
    urls = [str(url).strip() for url in urls if str(url).strip()]
    count = len(urls)
    title = urls[0] if count == 1 else f"{count} links"
    if len(title) > 38:
        title = title[:35] + "..."
    subtitle = "Drop to paste link" if count == 1 else "Drop to paste selected links"

    width = 280
    height = 70
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    outer = QRect(2, 2, width - 4, height - 4)
    painter.setBrush(QColor(17, 24, 39, 238))
    painter.setPen(QPen(QColor(93, 140, 255, 210), 1))
    painter.drawRoundedRect(outer, 14, 14)

    icon_rect = QRect(14, 17, 36, 36)
    painter.setBrush(QColor(37, 99, 235, 230))
    painter.setPen(QPen(QColor(147, 197, 253, 220), 1))
    painter.drawRoundedRect(icon_rect, 10, 10)

    painter.setPen(QColor("#ffffff"))
    icon_font = QFont()
    icon_font.setPointSize(15)
    icon_font.setBold(True)
    painter.setFont(icon_font)
    painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, "🔗" if count == 1 else str(count))

    title_font = QFont()
    title_font.setPointSize(10)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.setPen(QColor("#f8fafc"))
    painter.drawText(QRect(62, 14, width - 78, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)

    sub_font = QFont()
    sub_font.setPointSize(8)
    painter.setFont(sub_font)
    painter.setPen(QColor("#aab8ce"))
    painter.drawText(QRect(62, 38, width - 78, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, subtitle)

    painter.end()
    return pixmap


def _set_drag_guard(owner, widget, active: bool, previous_quit_policy=None):
    """Set a guard visible to every closeEvent that may fire during native drag/drop.

    Windows/PySide6 can deliver delayed close/deactivation events after a native
    file drag. Keep the guard on the QApplication, owner window, and widget so
    none of them silently closes while the OS drag manager is still finishing.
    """
    app = QApplication.instance()
    targets = [obj for obj in (app, owner, widget) if obj is not None]
    for target in targets:
        try:
            setattr(target, "_external_drag_in_progress", active)
        except Exception:
            pass
    if app:
        try:
            if active:
                setattr(app, "_zjx_previous_quit_policy", previous_quit_policy)
                app.setQuitOnLastWindowClosed(False)
            else:
                old_policy = getattr(app, "_zjx_previous_quit_policy", True)
                app.setQuitOnLastWindowClosed(bool(old_policy))
        except Exception:
            pass


def _retain_drag_objects(owner, widget, drag, mime_data, urls, staged_paths):
    """Keep native drag objects alive past QDrag.exec().

    On Windows, PySide6 file drags can crash/exit if the Python wrappers for
    QDrag/QMimeData/URL data are garbage-collected while the native OLE drag
    manager still references them. Store them on both the owner and the widget
    until a delayed cleanup timer runs.
    """
    retained = {
        "drag": drag,
        "mime_data": mime_data,
        "urls": urls,
        "staged_paths": staged_paths,
        "pixmap": getattr(drag, "_zjx_preview_pixmap", None),
    }
    for target in (owner, widget):
        if target is None:
            continue
        try:
            setattr(target, "_last_external_drag_payload", retained)
        except Exception:
            pass


def _clear_retained_drag_objects(owner, widget):
    for target in (owner, widget):
        if target is None:
            continue
        try:
            setattr(target, "_last_external_drag_payload", None)
        except Exception:
            pass




def _build_link_mime_data(normalised_urls: Iterable[str]) -> tuple[QMimeData, list[QUrl]]:
    """Build broad cross-app link drag data.

    Different Windows/browser targets negotiate different MIME/clipboard formats.
    Use URL-list, plain text, HTML anchor markup, Mozilla URL formats, and
    Windows URL clipboard formats so link resources have the best chance of
    dropping as the actual address rather than being ignored.
    """
    normalised_urls = [str(url).strip() for url in normalised_urls if str(url).strip()]
    qurls = [QUrl.fromUserInput(value) for value in normalised_urls]
    plain_text = "\n".join(normalised_urls)
    uri_list = "\r\n".join(normalised_urls) + "\r\n"

    if len(normalised_urls) == 1:
        first = normalised_urls[0]
        html_text = f'<a href="{html.escape(first, quote=True)}">{html.escape(first)}</a>'
        moz_text = f"{first}\n{first}"
    else:
        html_text = "<br>".join(
            f'<a href="{html.escape(url, quote=True)}">{html.escape(url)}</a>'
            for url in normalised_urls
        )
        moz_text = "\n".join(f"{url}\n{url}" for url in normalised_urls)

    mime_data = QMimeData()
    mime_data.setUrls(qurls)
    mime_data.setText(plain_text)
    mime_data.setHtml(html_text)

    # Standard URL list. Many browsers/editors prefer this over plain text.
    mime_data.setData("text/uri-list", uri_list.encode("utf-8"))

    # Mozilla/browser-friendly link formats.
    mime_data.setData("text/x-moz-url", moz_text.encode("utf-16le"))
    mime_data.setData("text/x-moz-url-data", normalised_urls[0].encode("utf-8"))
    mime_data.setData("text/x-moz-url-desc", normalised_urls[0].encode("utf-8"))

    # Windows native URL clipboard/drag formats exposed through Qt. Some apps
    # request these instead of text/uri-list during OLE drag negotiation.
    first_url = normalised_urls[0]
    mime_data.setData(
        'application/x-qt-windows-mime;value="UniformResourceLocatorW"',
        (first_url + "\0").encode("utf-16le"),
    )
    try:
        ansi_url = (first_url + "\0").encode("mbcs", errors="ignore")
    except LookupError:
        ansi_url = (first_url + "\0").encode("utf-8")
    mime_data.setData(
        'application/x-qt-windows-mime;value="UniformResourceLocator"',
        ansi_url,
    )

    return mime_data, qurls

def run_safe_link_drag(widget, owner, urls: Iterable[str]) -> bool:
    """Run a copy-only external link drag as URL/text data.

    Link resources do not have local files to stage. Keep QDrag/QMimeData alive
    exactly like file drags because Windows/PySide6 can otherwise drop Python
    wrappers while native drag/drop is still negotiating with the target app.
    """
    normalised_urls = []
    seen = set()
    for url in urls:
        value = _normalise_drag_url(str(url))
        if not value or value in seen:
            continue
        seen.add(value)
        normalised_urls.append(value)

    if not normalised_urls:
        return False

    app = QApplication.instance()
    previous_quit_policy = app.quitOnLastWindowClosed() if app else True
    try:
        mime_data, qurls = _build_link_mime_data(normalised_urls)

        # Fallback for apps that refuse dragged URL/text data: the same link is
        # placed on the clipboard before the drag starts, so Ctrl+V still works.
        try:
            clipboard = app.clipboard() if app else None
            if clipboard:
                clipboard.setText("\n".join(normalised_urls))
        except Exception:
            pass

        drag = QDrag(widget)
        drag.setMimeData(mime_data)
        preview_pixmap = _build_link_drag_preview_pixmap(normalised_urls)
        drag._zjx_preview_pixmap = preview_pixmap
        drag.setPixmap(preview_pixmap)
        drag.setHotSpot(preview_pixmap.rect().center())

        _retain_drag_objects(owner, widget, drag, mime_data, qurls, normalised_urls)
        _set_drag_guard(owner, widget, True, previous_quit_policy)

        def cleanup_after_native_drag():
            _set_drag_guard(owner, widget, False)
            _clear_retained_drag_objects(owner, widget)

        drag.exec(Qt.DropAction.CopyAction, Qt.DropAction.CopyAction)
        QTimer.singleShot(DRAG_GUARD_MS, cleanup_after_native_drag)
        return True
    except BaseException as error:
        print(f"External link drag failed: {error}")
        try:
            _set_drag_guard(owner, widget, False, previous_quit_policy)
            _clear_retained_drag_objects(owner, widget)
        except Exception:
            pass
        return False


def run_safe_file_drag(widget, owner, source_paths: Iterable[Path]) -> bool:
    """Run a copy-only external file drag using staged temp copies.

    The drag data is intentionally retained after QDrag.exec() returns to avoid
    PySide6/Windows object-lifetime failures. Any Python-side exception is logged
    and swallowed so a failed export cannot terminate the app.
    """
    app = QApplication.instance()
    previous_quit_policy = app.quitOnLastWindowClosed() if app else True
    try:
        staged_paths = stage_drag_paths(owner, source_paths)
        if not staged_paths:
            return False

        urls = [QUrl.fromLocalFile(str(path)) for path in staged_paths if Path(path).exists()]
        if not urls:
            return False

        mime_data = QMimeData()
        mime_data.setUrls(urls)
        # Avoid adding setText(); some Windows drop targets negotiate text first
        # and can trigger unstable non-file drag paths in older PySide6 builds.

        drag = QDrag(widget)
        drag.setMimeData(mime_data)
        preview_pixmap = _build_drag_preview_pixmap(staged_paths)
        drag._zjx_preview_pixmap = preview_pixmap
        drag.setPixmap(preview_pixmap)
        drag.setHotSpot(preview_pixmap.rect().center())

        _retain_drag_objects(owner, widget, drag, mime_data, urls, staged_paths)
        _set_drag_guard(owner, widget, True, previous_quit_policy)

        def cleanup_after_native_drag():
            _set_drag_guard(owner, widget, False)
            _clear_retained_drag_objects(owner, widget)

        # Use the two-argument overload to force copy semantics. Do not offer
        # MoveAction to external apps because that can remove/lock staged files
        # and may cause Qt to emit unexpected close/drop cleanup events.
        drag.exec(Qt.DropAction.CopyAction, Qt.DropAction.CopyAction)
        QTimer.singleShot(DRAG_GUARD_MS, cleanup_after_native_drag)
        return True
    except BaseException as error:
        print(f"External drag failed: {error}")
        try:
            _set_drag_guard(owner, widget, False, previous_quit_policy)
            _clear_retained_drag_objects(owner, widget)
        except Exception:
            pass
        return False
