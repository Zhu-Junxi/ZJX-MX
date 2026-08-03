from __future__ import annotations

import copy
import ctypes
import os
import sys
import uuid
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from core.helpers import format_due_datetime, normalise_url, seconds_until_due


GRID_COLUMNS = 12
DEFAULT_WIDGET_SIZE = {"width": 420, "height": 180}
MAX_WIDGET_WIDTH = 1600
MAX_WIDGET_HEIGHT = 1200


def default_block_style():
    return {
        "alignment": "left",
        "padding": 14,
        "spacing": 8,
        "background_variant": "surface_alt",
        "title_size": 16,
        "title_weight": 800,
        "title_role": "text",
        "subtitle_size": 13,
        "subtitle_weight": 500,
        "subtitle_role": "muted",
        "text_size": 14,
        "text_weight": 500,
        "text_role": "muted",
        "hero_size": 40,
        "hero_weight": 800,
        "hero_role": "accent",
        "meta_size": 13,
        "meta_weight": 500,
        "meta_role": "muted",
    }


def make_widget_id():
    return f"wid_{uuid.uuid4().hex[:12]}"


def make_block_id():
    return f"blk_{uuid.uuid4().hex[:12]}"


def default_shortcut_item():
    return {
        "label": "Open Dashboard",
        "target": {
            "type": "section",
            "section": "Dashboard",
        },
    }


def default_block(block_type="title"):
    style = default_block_style()
    config = {
        "title": {
            "title": "Widget Title",
            "subtitle": "Optional subtitle",
            "style": dict(style),
        },
        "assignment_countdown": {
            "user_id": "",
            "course_id": "",
            "assignment_id": "",
            "show_assignment_title": True,
            "show_course_label": True,
            "show_due_label": True,
            "title": "Due",
            "style": dict(style),
        },
        "note": {
            "text": "Add a quick reminder or summary here.",
            "style": dict(style),
        },
        "shortcut": {
            "title": "Shortcuts",
            "items": [default_shortcut_item()],
            "style": dict(style),
        },
    }.get(block_type, {})
    return {
        "id": make_block_id(),
        "type": block_type,
        "grid_x": 0,
        "grid_y": 0,
        "grid_w": 12,
        "grid_h": 3,
        "config": config,
    }


def default_widget(name="New Widget"):
    return {
        "id": make_widget_id(),
        "name": name,
        "enabled": True,
        "position": {"x": 120, "y": 120},
        "size": dict(DEFAULT_WIDGET_SIZE),
        "opacity": 0.96,
        "theme_mode": "app",
        "locked": False,
        "display_mode": "desktop_only",
        "click_action_on_body": {"type": "none"},
        "blocks": [],
    }


def normalize_shortcut_item(item):
    item = dict(item or {})
    label = str(item.get("label") or "Shortcut").strip() or "Shortcut"
    target = normalize_action_target(item.get("target"))
    return {"label": label, "target": target}


def normalize_action_target(target):
    target = dict(target or {})
    target_type = str(target.get("type") or "none")
    if target_type not in {"none", "section", "user", "course", "assignment", "file", "folder", "url"}:
        target_type = "none"
    normalized = {"type": target_type}
    if target_type == "section":
        section = str(target.get("section") or "Dashboard")
        if section not in {"Dashboard", "Users", "Courses", "Assignments", "Files", "Resource Library", "Settings", "Help", "Widgets"}:
            section = "Dashboard"
        normalized["section"] = section
    elif target_type == "user":
        normalized["user_id"] = str(target.get("user_id") or "")
    elif target_type == "course":
        normalized["user_id"] = str(target.get("user_id") or "")
        normalized["course_id"] = str(target.get("course_id") or "")
    elif target_type == "assignment":
        normalized["user_id"] = str(target.get("user_id") or "")
        normalized["course_id"] = str(target.get("course_id") or "")
        normalized["assignment_id"] = str(target.get("assignment_id") or "")
    elif target_type in {"file", "folder", "url"}:
        normalized["value"] = str(target.get("value") or "").strip()
    return normalized


def normalize_block(block):
    block = dict(block or {})
    block_type = str(block.get("type") or "title")
    if block_type not in {"title", "assignment_countdown", "note", "shortcut"}:
        block_type = "title"
    base = default_block(block_type)
    base["id"] = str(block.get("id") or base["id"])
    for key in ("grid_x", "grid_y", "grid_w", "grid_h"):
        try:
            base[key] = int(block.get(key, base[key]))
        except (TypeError, ValueError):
            pass
    base["grid_x"] = max(0, min(GRID_COLUMNS - 1, base["grid_x"]))
    base["grid_y"] = max(0, min(24, base["grid_y"]))
    base["grid_w"] = max(1, min(GRID_COLUMNS, base["grid_w"]))
    base["grid_h"] = max(1, min(12, base["grid_h"]))
    if base["grid_x"] + base["grid_w"] > GRID_COLUMNS:
        base["grid_x"] = max(0, GRID_COLUMNS - base["grid_w"])

    config = dict(base.get("config", {}))
    config.update(dict(block.get("config") or {}))
    style = dict(default_block_style())
    style.update(dict(config.get("style") or {}))
    style["alignment"] = str(style.get("alignment") or "left")
    if style["alignment"] not in {"left", "center", "right"}:
        style["alignment"] = "left"
    style["background_variant"] = str(style.get("background_variant") or "surface_alt")
    if style["background_variant"] not in {"surface_alt", "surface", "accent_soft"}:
        style["background_variant"] = "surface_alt"
    for key, minimum, maximum in (
        ("padding", 6, 40),
        ("spacing", 2, 24),
        ("title_size", 10, 42),
        ("subtitle_size", 10, 32),
        ("text_size", 10, 32),
        ("hero_size", 18, 96),
        ("meta_size", 10, 28),
    ):
        try:
            style[key] = max(minimum, min(maximum, int(style.get(key, default_block_style()[key]))))
        except (TypeError, ValueError):
            style[key] = default_block_style()[key]
    for key, default_value in (
        ("title_weight", 800),
        ("subtitle_weight", 500),
        ("text_weight", 500),
        ("hero_weight", 800),
        ("meta_weight", 500),
    ):
        try:
            style[key] = max(300, min(900, int(style.get(key, default_value))))
        except (TypeError, ValueError):
            style[key] = default_value
    for key, default_value in (
        ("title_role", "text"),
        ("subtitle_role", "muted"),
        ("text_role", "muted"),
        ("hero_role", "accent"),
        ("meta_role", "muted"),
    ):
        value = str(style.get(key) or default_value)
        if value not in {"text", "muted", "accent"}:
            value = default_value
        style[key] = value

    if block_type == "shortcut":
        config["items"] = [normalize_shortcut_item(item) for item in config.get("items", [])] or [default_shortcut_item()]
        config["title"] = str(config.get("title") or "Shortcuts")
    elif block_type == "assignment_countdown":
        config["user_id"] = str(config.get("user_id") or "")
        config["course_id"] = str(config.get("course_id") or "")
        config["assignment_id"] = str(config.get("assignment_id") or "")
        config["show_assignment_title"] = bool(config.get("show_assignment_title", True))
        config["show_course_label"] = bool(config.get("show_course_label", True))
        config["show_due_label"] = bool(config.get("show_due_label", True))
        config["title"] = str(config.get("title") or "Due")
    elif block_type == "note":
        config["text"] = str(config.get("text") or "")
    elif block_type == "title":
        config["title"] = str(config.get("title") or "Widget Title")
        config["subtitle"] = str(config.get("subtitle") or "")

    config["style"] = style
    base["config"] = config
    return base


def normalize_widget(widget):
    widget = dict(widget or {})
    base = default_widget(str(widget.get("name") or "Widget"))
    base["id"] = str(widget.get("id") or base["id"])
    base["name"] = str(widget.get("name") or base["name"]).strip() or "Widget"
    base["enabled"] = bool(widget.get("enabled", True))
    position = dict(widget.get("position") or {})
    size = dict(widget.get("size") or {})
    try:
        base["position"]["x"] = int(position.get("x", base["position"]["x"]))
        base["position"]["y"] = int(position.get("y", base["position"]["y"]))
    except (TypeError, ValueError):
        pass
    try:
        base["size"]["width"] = max(240, min(MAX_WIDGET_WIDTH, int(size.get("width", base["size"]["width"]))))
        base["size"]["height"] = max(120, min(MAX_WIDGET_HEIGHT, int(size.get("height", base["size"]["height"]))))
    except (TypeError, ValueError):
        pass
    try:
        base["opacity"] = max(0.55, min(1.0, float(widget.get("opacity", base["opacity"]))))
    except (TypeError, ValueError):
        pass
    theme_mode = str(widget.get("theme_mode") or "app")
    base["theme_mode"] = theme_mode if theme_mode in {"app", "dark", "light"} else "app"
    base["locked"] = bool(widget.get("locked", False))
    display_mode = str(widget.get("display_mode") or "desktop_only")
    base["display_mode"] = display_mode if display_mode in {"desktop_only", "always_visible"} else "desktop_only"
    base["click_action_on_body"] = normalize_action_target(widget.get("click_action_on_body"))
    base["blocks"] = [normalize_block(block) for block in widget.get("blocks", [])]
    return base


def widget_preset_definition(preset_name, assignments):
    preset = str(preset_name or "Blank Widget")
    selected_assignment = assignments[0] if assignments else None

    if preset == "Assignment Countdown":
        widget = default_widget("Assignment Countdown")
        widget["size"] = {"width": 460, "height": 210}
        widget["blocks"] = [
            {
                "id": make_block_id(),
                "type": "assignment_countdown",
                "grid_x": 0,
                "grid_y": 0,
                "grid_w": 12,
                "grid_h": 6,
                "config": {
                    "user_id": selected_assignment["user_id"] if selected_assignment else "",
                    "course_id": selected_assignment["course_id"] if selected_assignment else "",
                    "assignment_id": selected_assignment["assignment_id"] if selected_assignment else "",
                    "show_assignment_title": True,
                    "show_course_label": True,
                    "show_due_label": True,
                    "title": "Assignment details",
                    "style": {
                        **default_block_style(),
                        "hero_size": 52,
                        "title_size": 15,
                        "meta_size": 12,
                        "padding": 18,
                        "spacing": 10,
                    },
                },
            }
        ]
        return widget

    if preset == "Shortcut Panel":
        widget = default_widget("Shortcut Panel")
        widget["size"] = {"width": 360, "height": 220}
        widget["blocks"] = [
            {
                "id": make_block_id(),
                "type": "title",
                "grid_x": 0,
                "grid_y": 0,
                "grid_w": 12,
                "grid_h": 2,
                "config": {
                    "title": "Quick Links",
                    "subtitle": "Open common destinations",
                    "style": {**default_block_style(), "title_size": 18},
                },
            },
            {
                "id": make_block_id(),
                "type": "shortcut",
                "grid_x": 0,
                "grid_y": 2,
                "grid_w": 12,
                "grid_h": 4,
                "config": {
                    "title": "Launch",
                    "items": [
                        {"label": "Dashboard", "target": {"type": "section", "section": "Dashboard"}},
                        {"label": "Assignments", "target": {"type": "section", "section": "Assignments"}},
                        {"label": "Library", "target": {"type": "section", "section": "Resource Library"}},
                    ],
                    "style": {**default_block_style(), "padding": 16},
                },
            },
        ]
        return widget

    if preset == "Note Widget":
        widget = default_widget("Note Widget")
        widget["size"] = {"width": 340, "height": 190}
        widget["blocks"] = [
            {
                "id": make_block_id(),
                "type": "title",
                "grid_x": 0,
                "grid_y": 0,
                "grid_w": 12,
                "grid_h": 2,
                "config": {
                    "title": "Pinned Note",
                    "subtitle": "Quick reminder",
                    "style": {**default_block_style(), "title_size": 18},
                },
            },
            {
                "id": make_block_id(),
                "type": "note",
                "grid_x": 0,
                "grid_y": 2,
                "grid_w": 12,
                "grid_h": 4,
                "config": {
                    "text": "Add a reminder, planning note, or study checklist here.",
                    "style": {**default_block_style(), "text_size": 15},
                },
            },
        ]
        return widget

    widget = default_widget("Blank Widget")
    widget["blocks"] = []
    return widget


class WidgetManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.vault = main_window.vault
        self.widgets = []
        self.widget_windows = {}
        self.manager_window = None

        self.refresh_timer = QTimer(main_window)
        self.refresh_timer.timeout.connect(self.refresh_visible_widgets)
        self.visibility_timer = QTimer(main_window)
        self.visibility_timer.timeout.connect(self.refresh_widget_visibility_state)

        self.load_definitions()
        self.sync_live_widgets()

    def load_definitions(self):
        self.widgets = [normalize_widget(item) for item in self.vault.load_desktop_widgets()]
        return list(self.widgets)

    def save_definitions(self):
        self.vault.save_desktop_widgets(self.widgets)

    def update_vault(self, vault):
        self.vault = vault
        self.load_definitions()
        self.sync_live_widgets()
        if self.manager_window is not None:
            self.manager_window.reload_from_manager()

    def all_assignment_bindings(self):
        bindings = []
        for user in self.vault.get_users():
            for course in self.vault.get_courses(user["id"]):
                for assignment in self.vault.get_assignments(user["id"], course["id"]):
                    due_text = assignment.get("canvas_due_at") or assignment.get("due_date") or ""
                    bindings.append(
                        {
                            "user_id": user["id"],
                            "course_id": course["id"],
                            "assignment_id": assignment.get("id", ""),
                            "label": (
                                f"{user.get('name', 'User')} / "
                                f"{course.get('code') or course.get('name') or 'Course'} / "
                                f"{assignment.get('title', 'Assignment')}"
                            ),
                            "due_display": format_due_datetime(due_text),
                        }
                    )
        return bindings

    def current_theme_mode_for_widget(self, widget):
        mode = widget.get("theme_mode", "app")
        return self.main_window.effective_theme_mode() if mode == "app" else mode

    def visible_widgets(self):
        return [widget for widget in self.widgets if widget.get("enabled")]

    def show_manager_window(self):
        from ui.widgets_manager_window import WidgetsManagerWindow

        if self.manager_window is None:
            self.manager_window = WidgetsManagerWindow(self)
        self.manager_window.reload_from_manager()
        self.manager_window.show()
        self.manager_window.raise_()
        self.manager_window.activateWindow()

    def close_manager_window(self):
        if self.manager_window is not None:
            self.manager_window.close()
            self.manager_window = None

    def sync_live_widgets(self):
        from ui.widgets_manager_window import DesktopWidgetWindow

        active_ids = set()
        for widget in self.widgets:
            widget_id = widget["id"]
            if not widget.get("enabled"):
                continue
            active_ids.add(widget_id)
            window = self.widget_windows.get(widget_id)
            if window is None:
                window = DesktopWidgetWindow(self, widget)
                self.widget_windows[widget_id] = window
            window.set_definition(widget)

        for widget_id in list(self.widget_windows.keys()):
            if widget_id not in active_ids:
                self.widget_windows[widget_id].close()
                del self.widget_windows[widget_id]

        self.refresh_widget_visibility_state()
        self.update_refresh_interval()

    def refresh_visible_widgets(self):
        for widget in self.visible_widgets():
            window = self.widget_windows.get(widget["id"])
            if window is not None:
                window.refresh_content()
        if self.manager_window is not None and hasattr(self.manager_window, "current_widget"):
            current = self.manager_window.current_widget()
            if current is not None:
                self.manager_window.preview_canvas.set_definition(current)
        self.update_refresh_interval()

    def refresh_widget_visibility_state(self):
        desktop_visible = self.desktop_widgets_should_be_visible()
        for widget in self.visible_widgets():
            window = self.widget_windows.get(widget["id"])
            if window is None:
                continue
            display_mode = widget.get("display_mode", "desktop_only")
            should_show = display_mode == "always_visible" or desktop_visible
            window.apply_visibility(should_show)
        if self.visible_widgets():
            self.visibility_timer.start(1200)
        else:
            self.visibility_timer.stop()

    def update_refresh_interval(self):
        if not self.visible_widgets():
            self.refresh_timer.stop()
            return
        interval = 60_000
        if any(self.widget_needs_second_refresh(widget) for widget in self.visible_widgets()):
            interval = 1_000
        self.refresh_timer.start(interval)

    def desktop_widgets_should_be_visible(self):
        if not sys.platform.startswith("win"):
            return True
        try:
            user32 = ctypes.windll.user32
            foreground = user32.GetForegroundWindow()
            if not foreground:
                return True
            shell = user32.GetShellWindow()
            if foreground == shell:
                return True

            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(foreground, class_name, 255)
            if class_name.value in {"Progman", "WorkerW"}:
                return True

            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(foreground, ctypes.byref(pid))
            return int(pid.value) == os.getpid()
        except Exception:
            return True

    def widget_needs_second_refresh(self, widget):
        threshold = self.main_window.app_settings.get_due_countdown_seconds_threshold()
        if threshold <= 0:
            return False
        for block in widget.get("blocks", []):
            if block.get("type") != "assignment_countdown":
                continue
            assignment = self.resolve_assignment_reference(block.get("config", {}))
            if not assignment:
                continue
            due_text = assignment.get("canvas_due_at") or assignment.get("due_date") or ""
            remaining = seconds_until_due(due_text)
            if remaining is None:
                continue
            if abs(int(remaining)) < threshold:
                return True
        return False

    def get_widget(self, widget_id):
        for widget in self.widgets:
            if widget.get("id") == widget_id:
                return widget
        return None

    def add_widget_from_preset(self, preset_name):
        widget = widget_preset_definition(preset_name, self.all_assignment_bindings())
        self.widgets.append(normalize_widget(widget))
        self.save_definitions()
        self.sync_live_widgets()
        return self.widgets[-1]

    def duplicate_widget(self, widget_id):
        widget = self.get_widget(widget_id)
        if not widget:
            return None
        duplicate = normalize_widget(copy.deepcopy(widget))
        duplicate["id"] = make_widget_id()
        duplicate["name"] = f"{duplicate['name']} Copy"
        duplicate["position"]["x"] += 28
        duplicate["position"]["y"] += 28
        for block in duplicate.get("blocks", []):
            block["id"] = make_block_id()
        self.widgets.append(duplicate)
        self.save_definitions()
        self.sync_live_widgets()
        return duplicate

    def delete_widget(self, widget_id):
        self.widgets = [widget for widget in self.widgets if widget.get("id") != widget_id]
        window = self.widget_windows.pop(widget_id, None)
        if window is not None:
            window.close()
        self.save_definitions()
        self.sync_live_widgets()

    def replace_widget(self, widget_id, widget_data):
        updated = normalize_widget(widget_data)
        for index, widget in enumerate(self.widgets):
            if widget.get("id") == widget_id:
                self.widgets[index] = updated
                break
        self.save_definitions()
        self.sync_live_widgets()

    def set_widget_position(self, widget_id, x, y):
        widget = self.get_widget(widget_id)
        if not widget:
            return
        widget["position"]["x"] = int(x)
        widget["position"]["y"] = int(y)
        self.save_definitions()
        if self.manager_window is not None:
            self.manager_window.reload_from_manager(keep_selection=True)

    def update_widget(self, widget_id, mutate_callback):
        widget = self.get_widget(widget_id)
        if not widget:
            return None
        mutate_callback(widget)
        normalized = normalize_widget(widget)
        for index, existing in enumerate(self.widgets):
            if existing.get("id") == widget_id:
                self.widgets[index] = normalized
                break
        self.save_definitions()
        self.sync_live_widgets()
        if self.manager_window is not None:
            self.manager_window.reload_from_manager(keep_selection=True)
        return normalized

    def apply_widget_changes(self, widget_id, *, refresh_manager=False):
        widget = self.get_widget(widget_id)
        if not widget:
            return None

        normalized = normalize_widget(widget)
        for index, existing in enumerate(self.widgets):
            if existing.get("id") == widget_id:
                self.widgets[index] = normalized
                break

        self.save_definitions()
        self.sync_live_widgets()
        if refresh_manager and self.manager_window is not None:
            self.manager_window.reload_from_manager(keep_selection=True)
        return normalized

    def resolve_assignment_reference(self, binding):
        user_id = str(binding.get("user_id") or "")
        course_id = str(binding.get("course_id") or "")
        assignment_id = str(binding.get("assignment_id") or "")
        if not user_id or not course_id or not assignment_id:
            return None
        assignment = self.vault.get_assignment(user_id, course_id, assignment_id)
        if not assignment:
            return None
        return {
            "user_id": user_id,
            "course_id": course_id,
            "assignment_id": assignment_id,
            "user": self.vault.get_user(user_id),
            "course": self.vault.get_course(user_id, course_id),
            "assignment": assignment,
        }

    def describe_action_target(self, target):
        target = normalize_action_target(target)
        target_type = target.get("type")
        if target_type == "none":
            return "No action"
        if target_type == "section":
            return f"Open {target.get('section', 'Dashboard')}"
        if target_type == "user":
            user = self.vault.get_user(target.get("user_id"))
            return f"User: {user.get('name', 'Missing user')}" if user else "Missing user"
        if target_type == "course":
            course = self.vault.get_course(target.get("user_id"), target.get("course_id"))
            return f"Course: {(course or {}).get('code') or (course or {}).get('name') or 'Missing course'}"
        if target_type == "assignment":
            assignment = self.vault.get_assignment(target.get("user_id"), target.get("course_id"), target.get("assignment_id"))
            return f"Assignment: {(assignment or {}).get('title') or 'Missing assignment'}"
        if target_type in {"file", "folder", "url"}:
            return str(target.get("value") or "Missing target")
        return "Unknown action"

    def open_action(self, target_spec):
        target = normalize_action_target(target_spec)
        target_type = target.get("type")

        if target_type == "none":
            return

        if target_type == "section":
            section = target.get("section", "Dashboard")
            if section == "Resource Library":
                self.main_window.tray_controller.restore_window()
                self.main_window.open_resource_library()
                return
            if section == "Widgets":
                self.main_window.tray_controller.restore_window()
                self.show_manager_window()
                return
            self.main_window.tray_controller.restore_window(section if section in {"Dashboard", "Users", "Courses", "Assignments", "Files", "Settings", "Help"} else None)
            return

        if target_type == "user":
            user = self.vault.get_user(target.get("user_id"))
            if not user:
                self._show_missing_target("This widget points to a user that no longer exists.")
                return
            self.main_window.set_current_user(user["id"])
            self.main_window.tray_controller.restore_window("Users")
            return

        if target_type == "course":
            course = self.vault.get_course(target.get("user_id"), target.get("course_id"))
            if not course:
                self._show_missing_target("This widget points to a course that no longer exists.")
                return
            self.main_window.set_current_user(target.get("user_id"))
            self.main_window.set_current_course(course["id"])
            self.main_window.tray_controller.restore_window("Courses")
            return

        if target_type == "assignment":
            assignment = self.vault.get_assignment(target.get("user_id"), target.get("course_id"), target.get("assignment_id"))
            if not assignment:
                self._show_missing_target("This widget points to an assignment that no longer exists.")
                return
            self.main_window.set_current_user(target.get("user_id"))
            self.main_window.set_current_course(target.get("course_id"))
            self.main_window.set_current_assignment(assignment["id"])
            self.main_window.tray_controller.restore_window("Assignments")
            return

        if target_type == "url":
            value = str(target.get("value") or "").strip()
            if not value:
                self._show_missing_target("This widget URL is empty.")
                return
            QDesktopServices.openUrl(QUrl(normalise_url(value)))
            return

        if target_type in {"file", "folder"}:
            value = str(target.get("value") or "").strip()
            if not value:
                self._show_missing_target("This widget target path is empty.")
                return
            path = Path(value)
            if not path.exists():
                self._show_missing_target("This widget points to a file or folder that no longer exists.")
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            return

    def _show_missing_target(self, message):
        QMessageBox.information(self.manager_window or self.main_window, "Widget Action", message)

    def apply_theme_refresh(self):
        for window in self.widget_windows.values():
            window.refresh_theme()
        if self.manager_window is not None:
            self.manager_window.reload_from_manager(keep_selection=True)

    def shutdown(self):
        self.refresh_timer.stop()
        self.visibility_timer.stop()
        for window in list(self.widget_windows.values()):
            window.close()
        self.widget_windows.clear()
        if self.manager_window is not None:
            self.manager_window.close()
            self.manager_window = None
