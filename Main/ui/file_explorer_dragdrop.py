from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QRect, QMimeData, QUrl
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap

from ui.icons import load_icon


INTERNAL_MIME_TYPE = "application/x-zjx-resource-tree-items"
LINK_RESOURCE_TYPES = {"external_link", "youtube", "google_drive", "canvas"}


def payload_from_item(item):
    if item is None:
        return None
    data = item.data(0, Qt.ItemDataRole.UserRole) or {}
    if data.get("type") not in {"resource", "file_system_entry"}:
        return None
    return dict(data)


def drop_target_from_item(item, owner=None):
    """Copy the drop target into plain data before the tree can refresh."""
    cursor = item

    while cursor:
        data = cursor.data(0, Qt.ItemDataRole.UserRole) or {}
        item_type = data.get("type")

        if item_type == "resource":
            resource = dict(data.get("resource") or {})
            if resource.get("type") == "local_folder" and owner is not None and hasattr(owner, "vault"):
                path = owner.vault.resource_absolute_path(resource)
                if path and Path(path).exists() and Path(path).is_dir():
                    return {
                        "kind": "folder",
                        "folder_path": str(Path(path)),
                        "source": "resource",
                        "resource_id": resource.get("id"),
                        "is_background": False,
                    }

        if item_type == "file_system_entry":
            path = Path(data.get("path", ""))
            if path.exists() and path.is_dir():
                return {
                    "kind": "folder",
                    "folder_path": str(path),
                    "source": "file_system_entry",
                    "is_background": False,
                }

        cursor = cursor.parent()

    return {
        "kind": "background",
        "folder_path": None,
        "source": None,
        "is_background": item is None,
    }


def payload_resource(payload):
    if payload.get("type") != "resource":
        return {}
    return dict(payload.get("resource") or {})


def payload_is_link_resource(payload):
    return payload_resource(payload).get("type") in LINK_RESOURCE_TYPES


def resolve_payload_destination(payload, drop_target, owner):
    """Return the destination folder path, or None for top-level metadata links."""
    drop_target = drop_target or {}
    target_folder = drop_target.get("folder_path")
    if target_folder:
        return Path(target_folder)

    if payload.get("type") == "resource":
        resource = payload_resource(payload)
        resource_type = resource.get("type")
        if resource_type in LINK_RESOURCE_TYPES:
            return None
        if owner is None or not hasattr(owner, "vault"):
            return None
        source_path = owner.vault.resource_absolute_path(resource)
        if not source_path:
            return None
        return owner.top_level_destination_for_path(source_path, resource_type)

    if payload.get("type") == "file_system_entry":
        source_path = Path(payload.get("path", ""))
        return owner.top_level_destination_for_path(source_path)

    return None


def would_move_folder_into_itself(source_path, destination_parent):
    source_path = Path(source_path)
    destination_parent = Path(destination_parent)
    if not source_path.exists() or not source_path.is_dir():
        return False
    try:
        destination_parent.resolve().relative_to(source_path.resolve())
        return True
    except ValueError:
        return False


def selected_payloads(tree):
    items = tree.selectedItems() or ([tree.currentItem()] if tree.currentItem() else [])
    payloads = []
    for item in items:
        payload = payload_from_item(item)
        if payload:
            payloads.append(payload)
    return payloads


def encode_payloads(payloads):
    safe_payloads = []
    for payload in payloads or []:
        copied = dict(payload)
        if copied.get("type") == "resource":
            copied["resource"] = dict(copied.get("resource") or {})
        safe_payloads.append(copied)
    return json.dumps(safe_payloads, ensure_ascii=False).encode("utf-8")


def decode_payloads(mime_data):
    if not mime_data or not mime_data.hasFormat(INTERNAL_MIME_TYPE):
        return []
    try:
        data = bytes(mime_data.data(INTERNAL_MIME_TYPE)).decode("utf-8")
        payloads = json.loads(data)
    except Exception:
        return []
    if not isinstance(payloads, list):
        return []
    return [dict(payload) for payload in payloads if isinstance(payload, dict)]


def build_mime_data(payloads, owner=None, include_external=True):
    mime_data = QMimeData()
    mime_data.setData(INTERNAL_MIME_TYPE, encode_payloads(payloads))

    if include_external:
        paths, urls = external_payload(payloads, owner)
        qurls = [QUrl.fromLocalFile(str(path)) for path in paths]
        qurls.extend(QUrl(url) for url in urls)
        if qurls:
            mime_data.setUrls(qurls)
        if urls:
            mime_data.setText("\n".join(urls))

    return mime_data


def external_payload(payloads, owner=None):
    paths = []
    urls = []
    for payload in payloads or []:
        path = None
        if payload.get("type") == "file_system_entry":
            path = Path(payload.get("path", ""))
        elif payload.get("type") == "resource":
            resource = payload.get("resource", {}) or {}
            if resource.get("path") and owner is not None and hasattr(owner, "vault"):
                path = owner.vault.resource_absolute_path(resource)
            elif resource.get("url"):
                url = str(resource.get("url") or "").strip()
                if url and url not in urls:
                    urls.append(url)
        if path and Path(path).exists():
            resolved = Path(path).resolve()
            if resolved not in paths:
                paths.append(resolved)
    return paths, urls


def classify_payloads(payloads):
    counts = {
        "files": 0,
        "folders": 0,
        "notes": 0,
        "links": 0,
        "mixed": 0,
    }
    first_name = ""
    for payload in payloads or []:
        label, kind = payload_label_and_kind(payload)
        if not first_name:
            first_name = label
        if kind == "file":
            counts["files"] += 1
        elif kind == "folder":
            counts["folders"] += 1
        elif kind == "note":
            counts["notes"] += 1
        elif kind == "link":
            counts["links"] += 1
    active_kinds = sum(1 for key in ("files", "folders", "notes", "links") if counts[key])
    counts["mixed"] = active_kinds > 1
    return counts, first_name


def payload_label_and_kind(payload):
    if payload.get("type") == "resource":
        resource = payload.get("resource", {}) or {}
        label = str(resource.get("title") or "Resource")
        resource_type = resource.get("type")
        if resource_type == "local_folder":
            return label, "folder"
        if resource_type == "note":
            return label, "note"
        if resource_type in {"external_link", "youtube", "google_drive", "canvas"}:
            return label, "link"
        return label, "file"

    path = Path(payload.get("path", ""))
    label = path.name or "Item"
    if path.exists() and path.is_dir():
        return label, "folder"
    return label, "file"


def preview_text(payloads, action="Move"):
    payloads = list(payloads or [])
    count = len(payloads)
    counts, first_name = classify_payloads(payloads)
    if count <= 0:
        return action, "No items"

    if count == 1:
        _label, kind = payload_label_and_kind(payloads[0])
        kind_label = {"file": "file", "folder": "folder", "note": "note", "link": "link"}.get(kind, "item")
        return f"{action} {kind_label}", first_name

    if counts["mixed"]:
        summary = f"{count} mixed items"
    elif counts["folders"]:
        summary = f"{count} folders"
    elif counts["links"]:
        summary = f"{count} links"
    elif counts["notes"]:
        summary = f"{count} notes"
    else:
        summary = f"{count} files"
    return f"{action} items", summary


def build_drag_preview_pixmap(payloads, action="Move"):
    title, subtitle = preview_text(payloads, action=action)
    if len(subtitle) > 38:
        subtitle = subtitle[:35] + "..."

    width, height = 286, 74
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    outer = QRect(2, 2, width - 4, height - 4)
    painter.setBrush(QColor(17, 24, 39, 242))
    painter.setPen(QPen(QColor(93, 140, 255, 220), 1))
    painter.drawRoundedRect(outer, 14, 14)

    icon_rect = QRect(14, 18, 38, 38)
    painter.setBrush(QColor(37, 99, 235, 235))
    painter.setPen(QPen(QColor(147, 197, 253, 230), 1))
    painter.drawRoundedRect(icon_rect, 10, 10)
    load_icon("share").paint(painter, icon_rect.adjusted(8, 8, -8, -8), Qt.AlignmentFlag.AlignCenter)

    title_font = QFont()
    title_font.setPointSize(10)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.setPen(QColor("#f8fafc"))
    painter.drawText(QRect(64, 15, width - 82, 24), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)

    sub_font = QFont()
    sub_font.setPointSize(8)
    painter.setFont(sub_font)
    painter.setPen(QColor("#aab8ce"))
    painter.drawText(QRect(64, 41, width - 82, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, subtitle)

    painter.end()
    return pixmap


def local_paths_from_mime(mime_data):
    if not mime_data or not mime_data.hasUrls():
        return []
    return [Path(url.toLocalFile()) for url in mime_data.urls() if url.isLocalFile()]
