from __future__ import annotations

import copy
import ctypes
import sys
import uuid
from pathlib import Path
from html import unescape
import re

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from core.helpers import format_due_datetime, normalise_url, seconds_until_due


TEMPLATE_ASSIGNMENT = "assignment_countdown"
TEMPLATE_SHORTCUTS = "shortcut_panel"
TEMPLATE_NOTE = "note_widget"
WIDGET_TEMPLATES = (TEMPLATE_ASSIGNMENT, TEMPLATE_SHORTCUTS, TEMPLATE_NOTE)
GRID_COLUMNS = 12
DEFAULT_WIDGET_SIZE = {"width": 420, "height": 180}
MAX_WIDGET_WIDTH = 1200
MAX_WIDGET_HEIGHT = 800


def make_widget_id():
    return f"wid_{uuid.uuid4().hex[:12]}"


def default_shortcut_item():
    return {
        "label": "Open Dashboard",
        "target": {
            "type": "section",
            "section": "Dashboard",
        },
    }


def default_template_config(template_type):
    template = str(template_type or TEMPLATE_ASSIGNMENT)
    if template == TEMPLATE_SHORTCUTS:
        return {
            "title": "Quick Links",
            "items": [
                {"label": "Dashboard", "target": {"type": "section", "section": "Dashboard"}},
                {"label": "Assignments", "target": {"type": "section", "section": "Assignments"}},
            ],
        }
    if template == TEMPLATE_NOTE:
        return {
            "title": "Pinned Note",
            "text": "Add a reminder, planning note, or study checklist here.",
            "allow_inline_edit": False,
        }
    return {
        "title": "Assignment details",
        "user_id": "",
        "course_id": "",
        "assignment_id": "",
        "show_assignment_title": True,
        "show_course_label": True,
        "show_due_label": True,
    }


def default_widget(template_type=TEMPLATE_ASSIGNMENT, name=None):
    template = template_type if template_type in WIDGET_TEMPLATES else TEMPLATE_ASSIGNMENT
    label_map = {
        TEMPLATE_ASSIGNMENT: "Assignment Countdown",
        TEMPLATE_SHORTCUTS: "Shortcut Panel",
        TEMPLATE_NOTE: "Note Widget",
    }
    size_map = {
        TEMPLATE_ASSIGNMENT: {"width": 460, "height": 210},
        TEMPLATE_SHORTCUTS: {"width": 360, "height": 220},
        TEMPLATE_NOTE: {"width": 360, "height": 200},
    }
    return {
        "id": make_widget_id(),
        "name": str(name or label_map[template]),
        "enabled": True,
        "position": {"x": 120, "y": 120},
        "size": dict(size_map[template]),
        "opacity": 0.96,
        "theme_mode": "app",
        "locked": False,
        "display_mode": "desktop_only",
        "click_action_on_body": {"type": "none"},
        "template_type": template,
        "template_config": default_template_config(template),
    }


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


def normalize_shortcut_item(item):
    item = dict(item or {})
    return {
        "label": str(item.get("label") or "Shortcut").strip() or "Shortcut",
        "target": normalize_action_target(item.get("target")),
    }


def legacy_widget_to_template(widget):
    blocks = list(widget.get("blocks") or [])
    for block in blocks:
        if block.get("type") == "assignment_countdown":
            config = dict(block.get("config") or {})
            return {
                **widget,
                "template_type": TEMPLATE_ASSIGNMENT,
                "template_config": {
                    "title": str(config.get("title") or "Assignment details"),
                    "user_id": str(config.get("user_id") or ""),
                    "course_id": str(config.get("course_id") or ""),
                    "assignment_id": str(config.get("assignment_id") or ""),
                    "show_assignment_title": bool(config.get("show_assignment_title", True)),
                    "show_course_label": bool(config.get("show_course_label", True)),
                    "show_due_label": bool(config.get("show_due_label", True)),
                },
            }
    for block in blocks:
        if block.get("type") == "shortcut":
            config = dict(block.get("config") or {})
            return {
                **widget,
                "template_type": TEMPLATE_SHORTCUTS,
                "template_config": {
                    "title": str(config.get("title") or "Shortcuts"),
                    "items": [normalize_shortcut_item(entry) for entry in config.get("items", [])] or [default_shortcut_item()],
                },
            }
    for block in blocks:
        if block.get("type") == "note":
            config = dict(block.get("config") or {})
            return {
                **widget,
                "template_type": TEMPLATE_NOTE,
                "template_config": {
                    "title": str(config.get("title") or widget.get("name") or "Pinned Note"),
                    "text": str(config.get("text") or ""),
                    "allow_inline_edit": bool(config.get("allow_inline_edit", False)),
                },
            }
    return {
        **widget,
        "template_type": TEMPLATE_NOTE,
        "template_config": {
            "title": str(widget.get("name") or "Pinned Note"),
            "text": "",
            "allow_inline_edit": False,
        },
    }


def normalize_template_config(template_type, config):
    template = template_type if template_type in WIDGET_TEMPLATES else TEMPLATE_ASSIGNMENT
    base = default_template_config(template)
    merged = dict(base)
    merged.update(dict(config or {}))
    if template == TEMPLATE_ASSIGNMENT:
        merged["title"] = str(merged.get("title") or "Assignment details")
        merged["user_id"] = str(merged.get("user_id") or "")
        merged["course_id"] = str(merged.get("course_id") or "")
        merged["assignment_id"] = str(merged.get("assignment_id") or "")
        merged["show_assignment_title"] = bool(merged.get("show_assignment_title", True))
        merged["show_course_label"] = bool(merged.get("show_course_label", True))
        merged["show_due_label"] = bool(merged.get("show_due_label", True))
    elif template == TEMPLATE_SHORTCUTS:
        merged["title"] = str(merged.get("title") or "Quick Links")
        merged["items"] = [normalize_shortcut_item(item) for item in merged.get("items", [])] or [default_shortcut_item()]
    elif template == TEMPLATE_NOTE:
        merged["title"] = str(merged.get("title") or "Pinned Note")
        merged["text"] = str(merged.get("text") or "")
        merged["text_format"] = "html" if str(merged.get("text_format") or "").lower() == "html" else "plain"
        merged["allow_inline_edit"] = bool(merged.get("allow_inline_edit", False))
    return merged


def note_text_summary(text):
    text = str(text or "")
    text = re.sub(r"<img\b[^>]*>", "[image] ", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_widget(widget):
    widget = dict(widget or {})
    if "template_type" not in widget:
        widget = legacy_widget_to_template(widget)

    template_type = str(widget.get("template_type") or TEMPLATE_ASSIGNMENT)
    if template_type not in WIDGET_TEMPLATES:
        template_type = TEMPLATE_ASSIGNMENT
    base = default_widget(template_type, widget.get("name"))
    base["id"] = str(widget.get("id") or base["id"])
    base["name"] = str(widget.get("name") or base["name"]).strip() or base["name"]
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
        base["size"]["height"] = max(140, min(MAX_WIDGET_HEIGHT, int(size.get("height", base["size"]["height"]))))
    except (TypeError, ValueError):
        pass
    try:
        base["opacity"] = max(0.55, min(1.0, float(widget.get("opacity", base["opacity"]))))
    except (TypeError, ValueError):
        pass
    theme_mode = str(widget.get("theme_mode") or "app")
    base["theme_mode"] = theme_mode if theme_mode in {"app", "dark", "light"} else "app"
    display_mode = str(widget.get("display_mode") or "desktop_only")
    base["display_mode"] = display_mode if display_mode in {"desktop_only", "always_visible"} else "desktop_only"
    base["locked"] = bool(widget.get("locked", False))
    base["click_action_on_body"] = normalize_action_target(widget.get("click_action_on_body"))
    base["template_type"] = template_type
    base["template_config"] = normalize_template_config(template_type, widget.get("template_config"))
    return base


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

    def foreground_window_handle(self):
        if not sys.platform.startswith("win"):
            return 0
        try:
            user32 = ctypes.windll.user32
            return int(user32.GetForegroundWindow() or 0)
        except Exception:
            return 0

    def foreground_window_class_name(self, hwnd):
        if not sys.platform.startswith("win") or not hwnd:
            return ""
        try:
            user32 = ctypes.windll.user32
            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(int(hwnd), class_name, 255)
            return class_name.value
        except Exception:
            return ""

    def is_widget_window_handle(self, hwnd):
        try:
            target = int(hwnd)
        except Exception:
            return False
        if not target:
            return False
        for window in self.widget_windows.values():
            try:
                if hasattr(window, "window_handle_int"):
                    handle = window.window_handle_int()
                else:
                    handle = int(window.winId())
                if int(handle) == target:
                    return True
            except Exception:
                continue
        return False

    def is_own_app_window_handle(self, hwnd):
        try:
            target = int(hwnd)
        except Exception:
            return False
        if not target:
            return False
        for window in (self.main_window, self.manager_window):
            if window is None:
                continue
            try:
                if int(window.winId()) == target:
                    return True
            except Exception:
                continue
        return False

    def foreground_window_kind(self):
        if not sys.platform.startswith("win"):
            return "desktop"
        hwnd = self.foreground_window_handle()
        if not hwnd:
            return "desktop"
        try:
            shell = int(ctypes.windll.user32.GetShellWindow() or 0)
            if shell and int(hwnd) == shell:
                return "desktop"
        except Exception:
            pass

        class_name = self.foreground_window_class_name(hwnd)
        if class_name in {"Progman", "WorkerW"}:
            return "desktop"
        if self.is_widget_window_handle(hwnd):
            return "own_widget"
        if self.is_own_app_window_handle(hwnd):
            return "own_app"
        return "other_app"

    def desktop_widgets_should_be_visible(self):
        try:
            return self.foreground_window_kind() in {"desktop", "own_widget"}
        except Exception:
            return True

    def widget_needs_second_refresh(self, widget):
        if widget.get("template_type") != TEMPLATE_ASSIGNMENT:
            return False
        threshold = self.main_window.app_settings.get_due_countdown_seconds_threshold()
        if threshold <= 0:
            return False
        assignment = self.resolve_assignment_reference(widget.get("template_config", {}))
        if not assignment:
            return False
        due_text = assignment["assignment"].get("canvas_due_at") or assignment["assignment"].get("due_date") or ""
        remaining = seconds_until_due(due_text)
        if remaining is None:
            return False
        return abs(int(remaining)) < threshold

    def get_widget(self, widget_id):
        for widget in self.widgets:
            if widget.get("id") == widget_id:
                return widget
        return None

    def add_widget_from_preset(self, preset_name):
        mapping = {
            "Assignment Countdown": TEMPLATE_ASSIGNMENT,
            "Shortcut Panel": TEMPLATE_SHORTCUTS,
            "Note Widget": TEMPLATE_NOTE,
        }
        template_type = mapping.get(preset_name, preset_name)
        widget = default_widget(template_type if template_type in WIDGET_TEMPLATES else TEMPLATE_ASSIGNMENT)
        if template_type == TEMPLATE_ASSIGNMENT:
            assignments = self.all_assignment_bindings()
            if assignments:
                widget["template_config"].update(
                    {
                        "user_id": assignments[0]["user_id"],
                        "course_id": assignments[0]["course_id"],
                        "assignment_id": assignments[0]["assignment_id"],
                    }
                )
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

    def set_widget_position(self, widget_id, x, y):
        widget = self.get_widget(widget_id)
        if not widget:
            return
        widget["position"]["x"] = int(x)
        widget["position"]["y"] = int(y)
        self.save_definitions()
        if self.manager_window is not None:
            self.manager_window.reload_from_manager(keep_selection=True)

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

    def template_summary(self, widget):
        template = widget.get("template_type", TEMPLATE_ASSIGNMENT)
        config = widget.get("template_config", {})
        if template == TEMPLATE_ASSIGNMENT:
            assignment = self.resolve_assignment_reference(config)
            if assignment:
                return assignment["assignment"].get("title", "Assignment")
            return "Pick an assignment"
        if template == TEMPLATE_SHORTCUTS:
            return f"{len(config.get('items', []))} shortcut(s)"
        return note_text_summary(config.get("text") or "Note")[:36] or "Note"

    def cache_note_image(self, widget_id, image):
        if not widget_id or image is None or image.isNull():
            return ""

        assets_dir = self.vault.root_path / "widget_assets" / str(widget_id)
        assets_dir.mkdir(parents=True, exist_ok=True)
        path = assets_dir / f"note_image_{uuid.uuid4().hex[:12]}.png"
        if image.width() > 1400 or image.height() > 1400:
            image = image.scaled(1400, 1400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        if not image.save(str(path), "PNG"):
            return ""
        return str(path)

    def update_note_text_from_widget(self, widget_id, text, text_format="plain"):
        widget = self.get_widget(widget_id)
        if not widget or widget.get("template_type") != TEMPLATE_NOTE:
            return
        config = widget.setdefault("template_config", {})
        new_text = str(text or "")
        new_format = "html" if str(text_format).lower() == "html" else "plain"
        if config.get("text", "") == new_text and config.get("text_format", "plain") == new_format:
            return
        config["text"] = new_text
        config["text_format"] = new_format
        self.save_definitions()
        if self.manager_window is not None:
            current = self.manager_window.current_widget()
            if current is not None and current.get("id") == widget_id:
                current_text = self.manager_window.note_text.toHtml() if new_format == "html" else self.manager_window.note_text.toPlainText()
                if current_text != new_text:
                    blocked = self.manager_window.note_text.blockSignals(True)
                    if new_format == "html":
                        self.manager_window.note_text.setHtml(new_text)
                    else:
                        self.manager_window.note_text.setPlainText(new_text)
                    self.manager_window.note_text.blockSignals(blocked)
                self.manager_window.preview_canvas.set_definition(widget)

    def _show_missing_target(self, message):
        QMessageBox.information(self.manager_window or self.main_window, "Widget Action", message)

    def apply_theme_refresh(self):
        for window in self.widget_windows.values():
            window.refresh_theme()
        if self.manager_window is not None:
            self.manager_window.apply_theme_styling()
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
