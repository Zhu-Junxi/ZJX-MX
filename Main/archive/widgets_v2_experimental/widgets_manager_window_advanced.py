from __future__ import annotations

import copy

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.widget_manager import (
    GRID_COLUMNS,
    MAX_WIDGET_HEIGHT,
    MAX_WIDGET_WIDTH,
    default_block,
    default_shortcut_item,
    normalize_action_target,
)
from core.helpers import format_due_datetime
from ui.context_menus import AppContextMenu, add_menu_action
from ui.themed_forms import FormField, ThemedFormDialog


WEIGHT_OPTIONS = ("300", "400", "500", "600", "700", "800", "900")
ALIGNMENT_OPTIONS = ("left", "center", "right")
ROLE_OPTIONS = ("text", "muted", "accent")
BACKGROUND_OPTIONS = ("surface_alt", "surface", "accent_soft")


def theme_colours(theme, accent):
    if theme == "light":
        return {
            "surface": "#f8fbff",
            "surface_alt": "#eef5ff",
            "border": "#c9d7eb",
            "text": "#142033",
            "muted": "#5b6b82",
            "accent": accent,
            "pill": "#dce9ff",
            "accent_soft": "#f7edd0",
        }
    return {
        "surface": "#101827",
        "surface_alt": "#182335",
        "border": "#2a3a50",
        "text": "#e5eefc",
        "muted": "#9cb0c8",
        "accent": accent,
        "pill": "#17345f",
        "accent_soft": "#352f17",
    }


def qt_alignment(value):
    mapping = {
        "left": Qt.AlignmentFlag.AlignLeft,
        "center": Qt.AlignmentFlag.AlignHCenter,
        "right": Qt.AlignmentFlag.AlignRight,
    }
    return mapping.get(value, Qt.AlignmentFlag.AlignLeft)


def style_value(config, key, default):
    return dict(config.get("style") or {}).get(key, default)


def label_style(colours, *, size, weight, role):
    colour = colours.get(role, colours["text"])
    return f"color: {colour}; font-size: {int(size)}px; font-weight: {int(weight)};"


class ShortcutActionDialog(QDialog):
    def __init__(self, manager, action_item=None, parent=None):
        super().__init__(parent)
        self.manager = manager
        action_item = dict(action_item or {"label": "", "target": {"type": "section", "section": "Dashboard"}})
        target = normalize_action_target(action_item.get("target"))
        self._result = None

        self.setWindowTitle("Shortcut Action")
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Shortcut Action")
        title.setObjectName("DialogTitle")
        layout.addWidget(title)

        self.label_edit = QLineEdit(action_item.get("label", "Shortcut"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["section", "user", "course", "assignment", "file", "folder", "url"])
        self.type_combo.setCurrentText(target.get("type", "section"))

        self.section_combo = QComboBox()
        self.section_combo.addItems(["Dashboard", "Users", "Courses", "Assignments", "Files", "Resource Library", "Settings", "Help", "Widgets"])
        self.section_combo.setCurrentText(target.get("section", "Dashboard"))

        self.entity_combo = QComboBox()
        self.path_edit = QLineEdit(target.get("value", ""))

        self._entity_payloads = []
        self.populate_entities(target)

        for label_text, widget in [
            ("Button label", self.label_edit),
            ("Target type", self.type_combo),
            ("Section", self.section_combo),
            ("Entity target", self.entity_combo),
            ("Path / URL", self.path_edit),
        ]:
            row = QVBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            label = QLabel(label_text)
            label.setObjectName("FieldLabel")
            row.addWidget(label)
            row.addWidget(widget)
            layout.addLayout(row)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        save_btn = QPushButton("Save Action")
        cancel_btn.setObjectName("SecondaryButton")
        save_btn.setObjectName("PrimaryButton")
        button_row.addWidget(cancel_btn)
        button_row.addWidget(save_btn)
        layout.addLayout(button_row)

        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self.accept_if_valid)
        self.type_combo.currentTextChanged.connect(lambda: self.refresh_visibility())
        self.refresh_visibility(target)

    def populate_entities(self, target):
        target_type = target.get("type", "section")
        self._entity_payloads = []
        self.entity_combo.clear()
        if target_type == "user":
            for user in self.manager.vault.get_users():
                self.entity_combo.addItem(user.get("name", "User"))
                self._entity_payloads.append({"user_id": user["id"]})
        elif target_type == "course":
            for user in self.manager.vault.get_users():
                for course in self.manager.vault.get_courses(user["id"]):
                    self.entity_combo.addItem(f"{user.get('name', 'User')} / {course.get('code') or course.get('name') or 'Course'}")
                    self._entity_payloads.append({"user_id": user["id"], "course_id": course["id"]})
        elif target_type == "assignment":
            for binding in self.manager.all_assignment_bindings():
                self.entity_combo.addItem(f"{binding['label']}  |  {binding['due_display']}")
                self._entity_payloads.append(
                    {
                        "user_id": binding["user_id"],
                        "course_id": binding["course_id"],
                        "assignment_id": binding["assignment_id"],
                    }
                )

        selected_target = normalize_action_target(target)
        for index, payload in enumerate(self._entity_payloads):
            if selected_target.get("type") == "user" and payload.get("user_id") == selected_target.get("user_id"):
                self.entity_combo.setCurrentIndex(index)
                break
            if selected_target.get("type") == "course" and (
                payload.get("user_id"), payload.get("course_id")
            ) == (selected_target.get("user_id"), selected_target.get("course_id")):
                self.entity_combo.setCurrentIndex(index)
                break
            if selected_target.get("type") == "assignment" and (
                payload.get("user_id"), payload.get("course_id"), payload.get("assignment_id")
            ) == (
                selected_target.get("user_id"),
                selected_target.get("course_id"),
                selected_target.get("assignment_id"),
            ):
                self.entity_combo.setCurrentIndex(index)
                break

    def refresh_visibility(self, target=None):
        target = normalize_action_target(target or {"type": self.type_combo.currentText()})
        target_type = target.get("type", self.type_combo.currentText())
        self.populate_entities(target)
        self.section_combo.setVisible(target_type == "section")
        self.entity_combo.setVisible(target_type in {"user", "course", "assignment"})
        self.path_edit.setVisible(target_type in {"file", "folder", "url"})

    def accept_if_valid(self):
        target_type = self.type_combo.currentText()
        label = self.label_edit.text().strip() or "Shortcut"
        target = {"type": target_type}

        if target_type == "section":
            target["section"] = self.section_combo.currentText()
        elif target_type in {"user", "course", "assignment"}:
            if not self._entity_payloads:
                QMessageBox.information(self, "Shortcut Action", "There are no valid entities available for this target type yet.")
                return
            target.update(self._entity_payloads[self.entity_combo.currentIndex()])
        else:
            value = self.path_edit.text().strip()
            if not value:
                QMessageBox.information(self, "Shortcut Action", "Enter a file path, folder path, or URL.")
                return
            target["value"] = value

        self._result = {"label": label, "target": target}
        self.accept()

    def result_value(self):
        return self._result


class WidgetCanvas(QWidget):
    def __init__(self, manager, definition=None, *, preview=False, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.definition = definition or {}
        self.preview = preview
        self.block_select_callback = None
        self.block_context_menu_callback = None
        self.background_context_menu_callback = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.outer = QFrame()
        self.outer.setObjectName("DesktopWidgetOuter")
        self.outer_layout = QVBoxLayout(self.outer)
        self.outer_layout.setContentsMargins(14, 14, 14, 14)
        self.outer_layout.setSpacing(0)

        self.grid_host = QFrame()
        self.grid_layout = QGridLayout(self.grid_host)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setHorizontalSpacing(10)
        self.grid_layout.setVerticalSpacing(10)
        self.outer_layout.addWidget(self.grid_host)
        if self.preview:
            self.grid_host.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.grid_host.customContextMenuRequested.connect(self._open_background_context_menu)
        layout.addWidget(self.outer)

        self.set_definition(self.definition)

    def set_definition(self, definition):
        self.definition = definition or {}
        if self.preview:
            width = int(self.definition.get("size", {}).get("width", 420))
            height = int(self.definition.get("size", {}).get("height", 180))
            max_width = 560
            max_height = 380
            scale = min(max_width / max(1, width), max_height / max(1, height), 1.0)
            self.setFixedSize(max(220, int(width * scale)), max(120, int(height * scale)))
        self.refresh()

    def refresh(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        accent = self.manager.main_window.app_settings.get_accent_color()
        colours = theme_colours(self.manager.current_theme_mode_for_widget(self.definition), accent)
        opacity = self.definition.get("opacity", 0.96)
        rgba = QColor(colours["surface"])
        rgba.setAlphaF(opacity)
        self.outer.setStyleSheet(
            f"""
            QFrame#DesktopWidgetOuter {{
                background-color: rgba({rgba.red()}, {rgba.green()}, {rgba.blue()}, {rgba.alpha()});
                border: 1px solid {colours['border']};
                border-radius: 24px;
            }}
            """
        )

        for column in range(GRID_COLUMNS):
            self.grid_layout.setColumnStretch(column, 1)

        blocks = self.definition.get("blocks", [])
        if not blocks:
            empty = QLabel("No blocks yet")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color: {colours['muted']};")
            self.grid_layout.addWidget(empty, 0, 0, 1, GRID_COLUMNS)
            return

        for block in blocks:
            frame = self.build_block_frame(block, colours)
            self.grid_layout.addWidget(
                frame,
                int(block.get("grid_y", 0)),
                int(block.get("grid_x", 0)),
                max(1, int(block.get("grid_h", 1))),
                max(1, int(block.get("grid_w", 1))),
            )

    def build_block_frame(self, block, colours):
        config = block.get("config", {})
        style = dict(config.get("style") or {})
        padding = int(style.get("padding", 14))
        spacing = int(style.get("spacing", 8))
        variant = style.get("background_variant", "surface_alt")
        background = colours["surface_alt"]
        if variant == "surface":
            background = colours["surface"]
        elif variant == "accent_soft":
            background = colours["accent_soft"]

        frame = QFrame()
        frame.setObjectName("DesktopWidgetBlock")
        frame.setStyleSheet(
            f"""
            QFrame#DesktopWidgetBlock {{
                background-color: {background};
                border: 1px solid {colours['border']};
                border-radius: 18px;
            }}
            QPushButton {{
                background-color: {colours['pill']};
                border: 1px solid {colours['border']};
                border-radius: 12px;
                padding: 8px 10px;
                color: {colours['text']};
                font-weight: 700;
                text-align: left;
            }}
            QPushButton:hover {{
                border-color: {colours['accent']};
            }}
            """
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(padding, padding, padding, padding)
        layout.setSpacing(spacing)
        alignment = qt_alignment(style.get("alignment", "left"))

        def add_text(text, *, size, weight, role):
            label = QLabel(text)
            label.setWordWrap(True)
            label.setAlignment(alignment)
            label.setStyleSheet(label_style(colours, size=size, weight=weight, role=role))
            layout.addWidget(label)
            return label

        block_type = block.get("type")

        if block_type == "title":
            add_text(
                config.get("title", "Widget Title"),
                size=style.get("title_size", 16),
                weight=style.get("title_weight", 800),
                role=style.get("title_role", "text"),
            )
            subtitle = str(config.get("subtitle", "")).strip()
            if subtitle:
                add_text(
                    subtitle,
                    size=style.get("subtitle_size", 13),
                    weight=style.get("subtitle_weight", 500),
                    role=style.get("subtitle_role", "muted"),
                )
        elif block_type == "assignment_countdown":
            add_text(
                config.get("title", "Assignment details"),
                size=style.get("title_size", 16),
                weight=style.get("title_weight", 800),
                role=style.get("title_role", "text"),
            )
            resolved = self.manager.resolve_assignment_reference(config)
            if not resolved:
                add_text(
                    "Assignment unavailable",
                    size=style.get("hero_size", 40),
                    weight=style.get("hero_weight", 800),
                    role="muted",
                )
            else:
                assignment = resolved["assignment"]
                course = resolved["course"] or {}
                due_text = assignment.get("canvas_due_at") or assignment.get("due_date") or ""
                add_text(
                    self.manager.main_window.due_countdown_text(due_text),
                    size=style.get("hero_size", 40),
                    weight=style.get("hero_weight", 800),
                    role=style.get("hero_role", "accent"),
                )
                if config.get("show_assignment_title", True):
                    add_text(
                        assignment.get("title", "Untitled assignment"),
                        size=style.get("title_size", 16),
                        weight=style.get("title_weight", 800),
                        role=style.get("title_role", "text"),
                    )
                if config.get("show_course_label", True):
                    add_text(
                        course.get("code") or course.get("name") or "Course",
                        size=style.get("meta_size", 13),
                        weight=style.get("meta_weight", 500),
                        role=style.get("meta_role", "muted"),
                    )
                if config.get("show_due_label", True):
                    add_text(
                        f"Due: {format_due_datetime(due_text)}",
                        size=style.get("meta_size", 13),
                        weight=style.get("meta_weight", 500),
                        role=style.get("meta_role", "muted"),
                    )
        elif block_type == "note":
            add_text(
                config.get("text", ""),
                size=style.get("text_size", 14),
                weight=style.get("text_weight", 500),
                role=style.get("text_role", "muted"),
            )
        elif block_type == "shortcut":
            add_text(
                config.get("title", "Shortcuts"),
                size=style.get("title_size", 16),
                weight=style.get("title_weight", 800),
                role=style.get("title_role", "text"),
            )
            for item in config.get("items", []):
                button = QPushButton(item.get("label", "Shortcut"))
                button.clicked.connect(lambda checked=False, target=item.get("target"): self.manager.open_action(target))
                layout.addWidget(button)

        layout.addStretch()
        if self.preview:
            frame.setCursor(Qt.CursorShape.PointingHandCursor)
            frame.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            frame.mousePressEvent = lambda event, block_id=block.get("id"): self._handle_preview_block_press(event, block_id)
            frame.customContextMenuRequested.connect(
                lambda pos, block_id=block.get("id"), source=frame: self._open_block_context_menu(source, block_id, pos)
            )
        return frame

    def _handle_preview_block_press(self, event, block_id):
        if callable(self.block_select_callback):
            self.block_select_callback(block_id)

    def _open_block_context_menu(self, source, block_id, pos):
        if callable(self.block_context_menu_callback):
            self.block_context_menu_callback(block_id, source, pos)

    def _open_background_context_menu(self, pos):
        if callable(self.background_context_menu_callback):
            self.background_context_menu_callback(pos)


class DesktopWidgetWindow(QWidget):
    def __init__(self, manager, definition):
        super().__init__(None)
        self.manager = manager
        self.definition = definition
        self.drag_origin = None
        self.drag_start_position = None
        self.drag_moved = False

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.canvas = WidgetCanvas(manager, definition, preview=False, parent=self)
        layout.addWidget(self.canvas)

        self.set_definition(definition)

    def install_drag_filters(self):
        for widget in [self, self.canvas, self.canvas.outer, self.canvas.grid_host, *self.canvas.findChildren(QWidget)]:
            if isinstance(widget, QPushButton):
                continue
            widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self.drag_origin = event.globalPosition().toPoint()
            self.drag_start_position = self.pos()
            self.drag_moved = False
        elif event.type() == QEvent.Type.MouseMove and self.drag_origin is not None and not self.definition.get("locked"):
            offset = event.globalPosition().toPoint() - self.drag_origin
            if offset.manhattanLength() > 3:
                self.drag_moved = True
            self.move(self.drag_start_position + offset)
        elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            if self.drag_moved:
                self.manager.set_widget_position(self.definition["id"], self.x(), self.y())
            elif not self.drag_moved:
                target = self.definition.get("click_action_on_body", {"type": "none"})
                if target.get("type") != "none":
                    self.manager.open_action(target)
            self.drag_origin = None
            self.drag_start_position = None
            self.drag_moved = False
        return super().eventFilter(watched, event)

    def set_definition(self, definition):
        self.definition = definition
        width = int(definition.get("size", {}).get("width", 420))
        height = int(definition.get("size", {}).get("height", 180))
        self.resize(width, height)
        self.move(
            int(definition.get("position", {}).get("x", 120)),
            int(definition.get("position", {}).get("y", 120)),
        )
        self.canvas.set_definition(definition)
        self.install_drag_filters()
        self.setWindowOpacity(float(definition.get("opacity", 0.96)))
        self.setToolTip(definition.get("name", "Widget"))

    def refresh_content(self):
        self.canvas.refresh()

    def refresh_theme(self):
        self.canvas.refresh()

    def apply_visibility(self, visible):
        if visible:
            self.show()
        else:
            self.hide()


class BlockEditorCard(QFrame):
    def __init__(self, editor, block_id, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.block_id = block_id
        self.collapsed = False
        self._loading = False
        self.setObjectName("ContentPanel")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.open_context_menu)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.header_button = QPushButton()
        self.header_button.setObjectName("SmallButton")
        self.header_button.clicked.connect(self.select_card)
        self.collapse_btn = QPushButton("Collapse")
        self.collapse_btn.setObjectName("SmallButton")
        self.duplicate_btn = QPushButton("Duplicate")
        self.duplicate_btn.setObjectName("SmallButton")
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("SmallButton")
        header.addWidget(self.header_button, 1)
        header.addWidget(self.collapse_btn)
        header.addWidget(self.duplicate_btn)
        header.addWidget(self.delete_btn)
        outer.addLayout(header)

        self.content_widget = QWidget()
        content = QVBoxLayout(self.content_widget)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(10)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["title", "assignment_countdown", "note", "shortcut"])
        self.grid_x = QSpinBox()
        self.grid_x.setRange(0, GRID_COLUMNS - 1)
        self.grid_y = QSpinBox()
        self.grid_y.setRange(0, 24)
        self.grid_w = QSpinBox()
        self.grid_w.setRange(1, GRID_COLUMNS)
        self.grid_h = QSpinBox()
        self.grid_h.setRange(1, 12)

        self.title_edit = QLineEdit()
        self.subtitle_edit = QLineEdit()
        self.note_edit = QTextEdit()
        self.assignment_combo = QComboBox()
        self.show_assignment_title = QCheckBox("Show assignment title")
        self.show_course_label = QCheckBox("Show course label")
        self.show_due_label = QCheckBox("Show due label")

        self.alignment_combo = QComboBox()
        self.alignment_combo.addItems(ALIGNMENT_OPTIONS)
        self.background_combo = QComboBox()
        self.background_combo.addItems(BACKGROUND_OPTIONS)
        self.padding_spin = QSpinBox()
        self.padding_spin.setRange(6, 40)
        self.spacing_spin = QSpinBox()
        self.spacing_spin.setRange(2, 24)
        self.title_size_spin = QSpinBox()
        self.title_size_spin.setRange(10, 42)
        self.subtitle_size_spin = QSpinBox()
        self.subtitle_size_spin.setRange(10, 32)
        self.text_size_spin = QSpinBox()
        self.text_size_spin.setRange(10, 32)
        self.hero_size_spin = QSpinBox()
        self.hero_size_spin.setRange(18, 96)
        self.meta_size_spin = QSpinBox()
        self.meta_size_spin.setRange(10, 28)

        self.title_weight_combo = QComboBox()
        self.title_weight_combo.addItems(WEIGHT_OPTIONS)
        self.subtitle_weight_combo = QComboBox()
        self.subtitle_weight_combo.addItems(WEIGHT_OPTIONS)
        self.text_weight_combo = QComboBox()
        self.text_weight_combo.addItems(WEIGHT_OPTIONS)
        self.hero_weight_combo = QComboBox()
        self.hero_weight_combo.addItems(WEIGHT_OPTIONS)
        self.meta_weight_combo = QComboBox()
        self.meta_weight_combo.addItems(WEIGHT_OPTIONS)

        self.title_role_combo = QComboBox()
        self.title_role_combo.addItems(ROLE_OPTIONS)
        self.subtitle_role_combo = QComboBox()
        self.subtitle_role_combo.addItems(ROLE_OPTIONS)
        self.text_role_combo = QComboBox()
        self.text_role_combo.addItems(ROLE_OPTIONS)
        self.hero_role_combo = QComboBox()
        self.hero_role_combo.addItems(ROLE_OPTIONS)
        self.meta_role_combo = QComboBox()
        self.meta_role_combo.addItems(ROLE_OPTIONS)

        self.shortcuts_list = QListWidget()
        self.shortcuts_list.setMaximumHeight(120)
        self.shortcut_add_btn = QPushButton("Add Action")
        self.shortcut_add_btn.setObjectName("SmallButton")
        self.shortcut_edit_btn = QPushButton("Edit Action")
        self.shortcut_edit_btn.setObjectName("SmallButton")
        self.shortcut_delete_btn = QPushButton("Delete Action")
        self.shortcut_delete_btn.setObjectName("SmallButton")

        content.addWidget(self.section_label("Layout"))
        content.addWidget(self.single_row("Block type", self.type_combo))
        content.addWidget(self.dual_row("Grid X", self.grid_x, "Grid Y", self.grid_y))
        content.addWidget(self.dual_row("Grid Width", self.grid_w, "Grid Height", self.grid_h))

        content.addWidget(self.section_label("Content"))
        self.title_row = self.single_row("Title", self.title_edit)
        self.subtitle_row = self.single_row("Subtitle", self.subtitle_edit)
        self.note_row = self.single_row("Note", self.note_edit)
        self.assignment_row = self.single_row("Assignment", self.assignment_combo)
        content.addWidget(self.title_row)
        content.addWidget(self.subtitle_row)
        content.addWidget(self.note_row)
        content.addWidget(self.assignment_row)
        content.addWidget(self.show_assignment_title)
        content.addWidget(self.show_course_label)
        content.addWidget(self.show_due_label)

        content.addWidget(self.section_label("Style"))
        content.addWidget(self.dual_row("Alignment", self.alignment_combo, "Background", self.background_combo))
        content.addWidget(self.dual_row("Padding", self.padding_spin, "Spacing", self.spacing_spin))
        self.title_style_row = self.quad_row(
            ("Title size", self.title_size_spin),
            ("Weight", self.title_weight_combo),
            ("Color", self.title_role_combo),
            ("Subtitle size", self.subtitle_size_spin),
        )
        self.subtitle_style_row = self.dual_row("Subtitle weight", self.subtitle_weight_combo, "Subtitle color", self.subtitle_role_combo)
        self.text_style_row = self.triple_row(
            ("Text size", self.text_size_spin),
            ("Weight", self.text_weight_combo),
            ("Color", self.text_role_combo),
        )
        self.hero_style_row = self.triple_row(
            ("Hero size", self.hero_size_spin),
            ("Weight", self.hero_weight_combo),
            ("Color", self.hero_role_combo),
        )
        self.meta_style_row = self.triple_row(
            ("Meta size", self.meta_size_spin),
            ("Weight", self.meta_weight_combo),
            ("Color", self.meta_role_combo),
        )
        content.addWidget(self.title_style_row)
        content.addWidget(self.subtitle_style_row)
        content.addWidget(self.text_style_row)
        content.addWidget(self.hero_style_row)
        content.addWidget(self.meta_style_row)

        self.shortcut_section_label = self.section_label("Actions")
        content.addWidget(self.shortcut_section_label)
        content.addWidget(self.shortcuts_list)
        shortcut_buttons = QHBoxLayout()
        shortcut_buttons.addWidget(self.shortcut_add_btn)
        shortcut_buttons.addWidget(self.shortcut_edit_btn)
        shortcut_buttons.addWidget(self.shortcut_delete_btn)
        content.addLayout(shortcut_buttons)

        outer.addWidget(self.content_widget)

        self.header_button.clicked.connect(self.select_card)
        self.collapse_btn.clicked.connect(self.toggle_collapsed)
        self.duplicate_btn.clicked.connect(lambda: self.editor.duplicate_block(self.block_id))
        self.delete_btn.clicked.connect(lambda: self.editor.delete_block(self.block_id))
        self.shortcut_add_btn.clicked.connect(self.add_shortcut_action)
        self.shortcut_edit_btn.clicked.connect(self.edit_shortcut_action)
        self.shortcut_delete_btn.clicked.connect(self.delete_shortcut_action)

        for widget in [self.title_edit, self.subtitle_edit]:
            widget.textChanged.connect(self.queue_live_update)
        self.note_edit.textChanged.connect(self.queue_live_update)
        for widget in [
            self.type_combo,
            self.grid_x,
            self.grid_y,
            self.grid_w,
            self.grid_h,
            self.assignment_combo,
            self.show_assignment_title,
            self.show_course_label,
            self.show_due_label,
            self.alignment_combo,
            self.background_combo,
            self.padding_spin,
            self.spacing_spin,
            self.title_size_spin,
            self.subtitle_size_spin,
            self.text_size_spin,
            self.hero_size_spin,
            self.meta_size_spin,
            self.title_weight_combo,
            self.subtitle_weight_combo,
            self.text_weight_combo,
            self.hero_weight_combo,
            self.meta_weight_combo,
            self.title_role_combo,
            self.subtitle_role_combo,
            self.text_role_combo,
            self.hero_role_combo,
            self.meta_role_combo,
        ]:
            if isinstance(widget, QCheckBox):
                widget.toggled.connect(self.apply_live_change)
            elif isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self.apply_live_change)
            elif isinstance(widget, QSpinBox):
                widget.valueChanged.connect(self.apply_live_change)

        self.refresh_from_block()

    def section_label(self, text):
        label = QLabel(text)
        label.setObjectName("CardTitle")
        return label

    def single_row(self, label_text, widget):
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(label_text)
        label.setObjectName("FieldLabel")
        layout.addWidget(label)
        layout.addWidget(widget)
        return wrapper

    def dual_row(self, left_label, left_widget, right_label, right_widget):
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.single_row(left_label, left_widget))
        layout.addWidget(self.single_row(right_label, right_widget))
        return wrapper

    def triple_row(self, first, second, third):
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        for label_text, widget in (first, second, third):
            layout.addWidget(self.single_row(label_text, widget))
        return wrapper

    def quad_row(self, first, second, third, fourth):
        wrapper = QWidget()
        layout = QGridLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)
        for index, entry in enumerate((first, second, third, fourth)):
            layout.addWidget(self.single_row(entry[0], entry[1]), index // 2, index % 2)
        return wrapper

    def current_block(self):
        widget = self.editor.current_widget()
        if not widget:
            return None
        for block in widget.get("blocks", []):
            if block.get("id") == self.block_id:
                return block
        return None

    def select_card(self):
        self.editor.select_block(self.block_id, focus=True)

    def set_selected(self, selected):
        self.setStyleSheet(
            "QFrame#ContentPanel { border: 2px solid %s; border-radius: 16px; }" % (
                self.editor.manager.main_window.app_settings.get_accent_color() if selected else "transparent"
            )
        )

    def toggle_collapsed(self):
        self.collapsed = not self.collapsed
        self.content_widget.setVisible(not self.collapsed)
        self.collapse_btn.setText("Expand" if self.collapsed else "Collapse")

    def queue_live_update(self, *_args):
        if self._loading:
            return
        self.editor.queue_live_update()

    def apply_live_change(self, *_args):
        if self._loading:
            return
        self.editor.apply_live_changes()

    def refresh_from_block(self):
        block = self.current_block()
        if not block:
            return
        self._loading = True
        config = block.get("config", {})
        style = dict(config.get("style") or {})

        self.header_button.setText(self.editor.block_display_name(block))
        self.type_combo.setCurrentText(block.get("type", "title"))
        self.grid_x.setValue(int(block.get("grid_x", 0)))
        self.grid_y.setValue(int(block.get("grid_y", 0)))
        self.grid_w.setValue(int(block.get("grid_w", 1)))
        self.grid_h.setValue(int(block.get("grid_h", 1)))
        self.title_edit.setText(config.get("title", ""))
        self.subtitle_edit.setText(config.get("subtitle", ""))
        self.note_edit.setPlainText(config.get("text", ""))
        self.populate_assignment_combo(config)
        self.show_assignment_title.setChecked(bool(config.get("show_assignment_title", True)))
        self.show_course_label.setChecked(bool(config.get("show_course_label", True)))
        self.show_due_label.setChecked(bool(config.get("show_due_label", True)))

        self.alignment_combo.setCurrentText(style.get("alignment", "left"))
        self.background_combo.setCurrentText(style.get("background_variant", "surface_alt"))
        self.padding_spin.setValue(int(style.get("padding", 14)))
        self.spacing_spin.setValue(int(style.get("spacing", 8)))
        self.title_size_spin.setValue(int(style.get("title_size", 16)))
        self.subtitle_size_spin.setValue(int(style.get("subtitle_size", 13)))
        self.text_size_spin.setValue(int(style.get("text_size", 14)))
        self.hero_size_spin.setValue(int(style.get("hero_size", 40)))
        self.meta_size_spin.setValue(int(style.get("meta_size", 13)))

        self.title_weight_combo.setCurrentText(str(style.get("title_weight", 800)))
        self.subtitle_weight_combo.setCurrentText(str(style.get("subtitle_weight", 500)))
        self.text_weight_combo.setCurrentText(str(style.get("text_weight", 500)))
        self.hero_weight_combo.setCurrentText(str(style.get("hero_weight", 800)))
        self.meta_weight_combo.setCurrentText(str(style.get("meta_weight", 500)))
        self.title_role_combo.setCurrentText(style.get("title_role", "text"))
        self.subtitle_role_combo.setCurrentText(style.get("subtitle_role", "muted"))
        self.text_role_combo.setCurrentText(style.get("text_role", "muted"))
        self.hero_role_combo.setCurrentText(style.get("hero_role", "accent"))
        self.meta_role_combo.setCurrentText(style.get("meta_role", "muted"))

        self.populate_shortcuts_list(config.get("items", []))
        self.refresh_visibility()
        self._loading = False

    def refresh_visibility(self):
        block = self.current_block()
        block_type = block.get("type", "title") if block else "title"
        self.title_row.setVisible(block_type in {"title", "assignment_countdown", "shortcut"})
        self.subtitle_row.setVisible(block_type == "title")
        self.note_row.setVisible(block_type == "note")
        self.assignment_row.setVisible(block_type == "assignment_countdown")
        self.show_assignment_title.setVisible(block_type == "assignment_countdown")
        self.show_course_label.setVisible(block_type == "assignment_countdown")
        self.show_due_label.setVisible(block_type == "assignment_countdown")

        self.title_style_row.setVisible(block_type in {"title", "assignment_countdown", "shortcut"})
        self.subtitle_style_row.setVisible(block_type == "title")
        self.text_style_row.setVisible(block_type == "note")
        self.hero_style_row.setVisible(block_type == "assignment_countdown")
        self.meta_style_row.setVisible(block_type == "assignment_countdown")
        self.shortcut_section_label.setVisible(block_type == "shortcut")
        self.shortcuts_list.setVisible(block_type == "shortcut")
        self.shortcut_add_btn.setVisible(block_type == "shortcut")
        self.shortcut_edit_btn.setVisible(block_type == "shortcut")
        self.shortcut_delete_btn.setVisible(block_type == "shortcut")

    def populate_assignment_combo(self, config):
        self.assignment_combo.clear()
        bindings = self.editor.manager.all_assignment_bindings()
        if not bindings:
            self.assignment_combo.addItem("No assignments available")
            return
        selected = (
            str(config.get("user_id") or ""),
            str(config.get("course_id") or ""),
            str(config.get("assignment_id") or ""),
        )
        current_index = 0
        for index, binding in enumerate(bindings):
            self.assignment_combo.addItem(f"{binding['label']}  |  {binding['due_display']}")
            self.assignment_combo.setItemData(index, (binding["user_id"], binding["course_id"], binding["assignment_id"]), Qt.ItemDataRole.UserRole)
            if (binding["user_id"], binding["course_id"], binding["assignment_id"]) == selected:
                current_index = index
        self.assignment_combo.setCurrentIndex(current_index)

    def populate_shortcuts_list(self, items):
        self.shortcuts_list.clear()
        for item in items:
            self.shortcuts_list.addItem(f"{item.get('label', 'Shortcut')} -> {self.editor.manager.describe_action_target(item.get('target'))}")
        self.shortcut_edit_btn.setEnabled(bool(items))
        self.shortcut_delete_btn.setEnabled(bool(items))

    def write_to_block(self, block):
        block_type = self.type_combo.currentText()
        base = default_block(block_type)
        existing_config = dict(block.get("config") or {})
        config = dict(base.get("config", {}))
        style = dict(config.get("style") or {})
        style.update(
            {
                "alignment": self.alignment_combo.currentText(),
                "background_variant": self.background_combo.currentText(),
                "padding": self.padding_spin.value(),
                "spacing": self.spacing_spin.value(),
                "title_size": self.title_size_spin.value(),
                "subtitle_size": self.subtitle_size_spin.value(),
                "text_size": self.text_size_spin.value(),
                "hero_size": self.hero_size_spin.value(),
                "meta_size": self.meta_size_spin.value(),
                "title_weight": int(self.title_weight_combo.currentText()),
                "subtitle_weight": int(self.subtitle_weight_combo.currentText()),
                "text_weight": int(self.text_weight_combo.currentText()),
                "hero_weight": int(self.hero_weight_combo.currentText()),
                "meta_weight": int(self.meta_weight_combo.currentText()),
                "title_role": self.title_role_combo.currentText(),
                "subtitle_role": self.subtitle_role_combo.currentText(),
                "text_role": self.text_role_combo.currentText(),
                "hero_role": self.hero_role_combo.currentText(),
                "meta_role": self.meta_role_combo.currentText(),
            }
        )
        config["style"] = style

        block["type"] = block_type
        block["grid_x"] = self.grid_x.value()
        block["grid_y"] = self.grid_y.value()
        block["grid_w"] = self.grid_w.value()
        block["grid_h"] = self.grid_h.value()

        if block_type == "title":
            config["title"] = self.title_edit.text().strip() or "Widget Title"
            config["subtitle"] = self.subtitle_edit.text().strip()
        elif block_type == "assignment_countdown":
            payload = self.assignment_combo.currentData(Qt.ItemDataRole.UserRole)
            if payload:
                config["user_id"], config["course_id"], config["assignment_id"] = payload
            config["title"] = self.title_edit.text().strip() or "Assignment details"
            config["show_assignment_title"] = self.show_assignment_title.isChecked()
            config["show_course_label"] = self.show_course_label.isChecked()
            config["show_due_label"] = self.show_due_label.isChecked()
        elif block_type == "note":
            config["text"] = self.note_edit.toPlainText().strip()
        elif block_type == "shortcut":
            config["title"] = self.title_edit.text().strip() or "Shortcuts"
            config["items"] = copy.deepcopy(existing_config.get("items") or [default_shortcut_item()])

        block["config"] = config

    def selected_shortcut_index(self):
        item = self.shortcuts_list.currentItem()
        return self.shortcuts_list.row(item) if item else -1

    def add_shortcut_action(self):
        block = self.current_block()
        if not block:
            return
        dialog = ShortcutActionDialog(self.editor.manager, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.result_value():
            return
        block.setdefault("config", {}).setdefault("items", []).append(dialog.result_value())
        self.editor.apply_live_changes()
        self.refresh_from_block()

    def edit_shortcut_action(self):
        block = self.current_block()
        index = self.selected_shortcut_index()
        items = list(block.get("config", {}).get("items", [])) if block else []
        if not block or index < 0 or index >= len(items):
            return
        dialog = ShortcutActionDialog(self.editor.manager, action_item=items[index], parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.result_value():
            return
        block.setdefault("config", {}).setdefault("items", [])[index] = dialog.result_value()
        self.editor.apply_live_changes()
        self.refresh_from_block()

    def delete_shortcut_action(self):
        block = self.current_block()
        index = self.selected_shortcut_index()
        items = block.get("config", {}).get("items", []) if block else []
        if not block or index < 0 or index >= len(items):
            return
        items.pop(index)
        if not items:
            items.append(default_shortcut_item())
        self.editor.apply_live_changes()
        self.refresh_from_block()

    def open_context_menu(self, pos):
        self.editor.select_block(self.block_id)
        menu = AppContextMenu(self)
        add_menu_action(menu, "Duplicate Block", "copy", lambda: self.editor.duplicate_block(self.block_id), shortcut="Ctrl+D")
        add_menu_action(menu, "Delete Block", "delete", lambda: self.editor.delete_block(self.block_id), shortcut="Delete")
        if self.current_block() and self.current_block().get("type") == "shortcut":
            add_menu_action(menu, "Edit Shortcut Actions", "edit", self.edit_shortcut_action)
        menu.exec(self.mapToGlobal(pos))


class WidgetsManagerWindow(QMainWindow):
    def __init__(self, manager):
        super().__init__(manager.main_window)
        self.manager = manager
        self.selected_widget_id = None
        self.selected_block_id = None
        self.block_cards = {}
        self._loading = False
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self.apply_live_changes)
        self._live_status_text = "Live updates on"

        self.setWindowTitle("Desktop Widgets")
        available = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
        if available:
            self.resize(
                min(available.width() - 40, max(1180, int(available.width() * 0.92))),
                min(available.height() - 40, max(760, int(available.height() * 0.9))),
            )
        else:
            self.resize(1340, 860)
        self.setMinimumSize(1100, 720)

        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        title = QLabel("Desktop Widgets")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Create floating utility widgets that stay active while the app is running.")
        subtitle.setObjectName("PageSubtitle")
        outer.addWidget(title)
        outer.addWidget(subtitle)
        outer.addWidget(self.build_top_bar())

        splitter = QSplitter()
        outer.addWidget(splitter, 1)

        splitter.addWidget(self.build_left_panel())
        splitter.addWidget(self.build_preview_panel())
        splitter.addWidget(self.build_right_panel())
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([260, 600, 420])

        self.setCentralWidget(container)
        self.refresh_action_states()

    def closeEvent(self, event):
        self.manager.manager_window = None
        super().closeEvent(event)

    def build_top_bar(self):
        bar = QFrame()
        bar.setObjectName("ContentPanel")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        self.top_add_widget_btn = QPushButton("Add Widget")
        self.top_duplicate_widget_btn = QPushButton("Duplicate")
        self.top_rename_widget_btn = QPushButton("Rename")
        self.top_delete_widget_btn = QPushButton("Delete")
        self.top_add_block_btn = QPushButton("Add Block")
        self.top_delete_block_btn = QPushButton("Delete Block")
        self.top_save_now_btn = QPushButton("Save Now")
        for button in (
            self.top_add_widget_btn,
            self.top_duplicate_widget_btn,
            self.top_rename_widget_btn,
            self.top_delete_widget_btn,
            self.top_add_block_btn,
            self.top_delete_block_btn,
            self.top_save_now_btn,
        ):
            button.setObjectName("SmallButton")

        self.live_status_label = QLabel(self._live_status_text)
        self.live_status_label.setObjectName("CardBody")

        layout.addWidget(self.top_add_widget_btn)
        layout.addWidget(self.top_duplicate_widget_btn)
        layout.addWidget(self.top_rename_widget_btn)
        layout.addWidget(self.top_delete_widget_btn)
        layout.addSpacing(10)
        layout.addWidget(self.top_add_block_btn)
        layout.addWidget(self.top_delete_block_btn)
        layout.addStretch()
        layout.addWidget(self.live_status_label)
        layout.addWidget(self.top_save_now_btn)

        self.top_add_widget_btn.clicked.connect(self.create_widget)
        self.top_duplicate_widget_btn.clicked.connect(self.duplicate_widget)
        self.top_rename_widget_btn.clicked.connect(self.rename_widget)
        self.top_delete_widget_btn.clicked.connect(self.delete_widget)
        self.top_add_block_btn.clicked.connect(self.add_block)
        self.top_delete_block_btn.clicked.connect(lambda: self.delete_block())
        self.top_save_now_btn.clicked.connect(self.force_save_now)
        return bar

    def build_left_panel(self):
        panel = QFrame()
        panel.setObjectName("ContentPanel")
        panel.setMinimumWidth(220)
        panel.setMaximumWidth(320)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        label = QLabel("Widgets")
        label.setObjectName("CardTitle")
        layout.addWidget(label)

        self.widget_list = QListWidget()
        self.widget_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.widget_list, 1)

        helper = QLabel("Use the top action bar for widget-level actions.")
        helper.setObjectName("CardBody")
        helper.setWordWrap(True)
        layout.addWidget(helper)

        self.widget_list.currentItemChanged.connect(self.on_widget_selected)
        self.widget_list.itemDoubleClicked.connect(lambda item: self.focus_selected_widget())
        self.widget_list.customContextMenuRequested.connect(self.open_widget_list_context_menu)
        return panel

    def build_preview_panel(self):
        panel = QFrame()
        panel.setObjectName("ContentPanel")
        panel.setMinimumWidth(340)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        label = QLabel("Live Preview")
        label.setObjectName("CardTitle")
        layout.addWidget(label)

        preview_hint = QLabel("Changes update the preview and the live desktop widget automatically.")
        preview_hint.setObjectName("CardBody")
        preview_hint.setWordWrap(True)
        layout.addWidget(preview_hint)

        preview_scroll = QScrollArea()
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setFrameShape(QFrame.Shape.NoFrame)

        preview_host = QWidget()
        preview_layout = QVBoxLayout(preview_host)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.addStretch()

        self.preview_canvas = WidgetCanvas(self.manager, preview=True, parent=preview_host)
        self.preview_canvas.block_select_callback = self.select_block
        self.preview_canvas.block_context_menu_callback = self.open_preview_block_context_menu
        self.preview_canvas.background_context_menu_callback = self.open_preview_background_context_menu
        preview_layout.insertWidget(0, self.preview_canvas, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        preview_scroll.setWidget(preview_host)
        layout.addWidget(preview_scroll, 1)
        return panel

    def build_right_panel(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumWidth(360)

        host = QWidget()
        self.inspector_layout = QVBoxLayout(host)
        self.inspector_layout.setContentsMargins(0, 0, 0, 0)
        self.inspector_layout.setSpacing(12)

        self.widget_settings_card = self.build_widget_settings_card()
        self.inspector_layout.addWidget(self.widget_settings_card)

        blocks_card = QFrame()
        blocks_card.setObjectName("ContentPanel")
        blocks_layout = QVBoxLayout(blocks_card)
        blocks_layout.setContentsMargins(14, 14, 14, 14)
        blocks_layout.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("Blocks")
        title.setObjectName("CardTitle")
        self.blocks_add_btn = QPushButton("Add Block")
        self.blocks_add_btn.setObjectName("SmallButton")
        self.blocks_add_btn.clicked.connect(self.add_block)
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.blocks_add_btn)
        blocks_layout.addLayout(title_row)

        self.empty_blocks_label = QLabel("This widget is blank. Add a block to start building it.")
        self.empty_blocks_label.setObjectName("CardBody")
        self.empty_blocks_label.setWordWrap(True)
        blocks_layout.addWidget(self.empty_blocks_label)

        self.empty_add_block_btn = QPushButton("Add Block")
        self.empty_add_block_btn.setObjectName("PrimaryButton")
        self.empty_add_block_btn.clicked.connect(self.add_block)
        blocks_layout.addWidget(self.empty_add_block_btn, 0, Qt.AlignmentFlag.AlignLeft)

        self.blocks_container = QWidget()
        self.blocks_container_layout = QVBoxLayout(self.blocks_container)
        self.blocks_container_layout.setContentsMargins(0, 0, 0, 0)
        self.blocks_container_layout.setSpacing(12)
        blocks_layout.addWidget(self.blocks_container)

        self.inspector_layout.addWidget(blocks_card)
        self.inspector_layout.addStretch()
        scroll.setWidget(host)
        return scroll

    def build_widget_settings_card(self):
        card = QFrame()
        card.setObjectName("ContentPanel")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Widget Settings")
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        self.widget_name = QLineEdit()
        self.widget_x = QSpinBox()
        self.widget_x.setRange(-5000, 5000)
        self.widget_y = QSpinBox()
        self.widget_y.setRange(-5000, 5000)
        self.widget_width = QSpinBox()
        self.widget_width.setRange(240, MAX_WIDGET_WIDTH)
        self.widget_height = QSpinBox()
        self.widget_height.setRange(120, MAX_WIDGET_HEIGHT)
        self.widget_theme = QComboBox()
        self.widget_theme.addItems(["app", "dark", "light"])
        self.widget_display_mode = QComboBox()
        self.widget_display_mode.addItems(["desktop_only", "always_visible"])
        self.widget_opacity = QSlider(Qt.Orientation.Horizontal)
        self.widget_opacity.setRange(55, 100)
        self.widget_enabled = QCheckBox("Widget enabled")
        self.widget_locked = QCheckBox("Lock desktop position")
        self.widget_body_action = QComboBox()
        self.widget_body_action.addItems(["none", "section", "user", "course", "assignment", "file", "folder", "url"])
        self.widget_body_target_label = QLabel("No action")
        self.widget_body_target_label.setObjectName("CardBody")
        self.edit_body_action_btn = QPushButton("Edit Body Action")
        self.edit_body_action_btn.setObjectName("SmallButton")

        layout.addWidget(self.single_row("Name", self.widget_name))
        layout.addWidget(self.dual_row("Position X", self.widget_x, "Position Y", self.widget_y))
        layout.addWidget(self.dual_row("Width", self.widget_width, "Height", self.widget_height))
        layout.addWidget(self.section_text("Appearance"))
        layout.addWidget(self.dual_row("Theme", self.widget_theme, "Display mode", self.widget_display_mode))
        layout.addWidget(self.single_row("Opacity", self.widget_opacity))
        layout.addWidget(self.widget_enabled)
        layout.addWidget(self.widget_locked)
        layout.addWidget(self.section_text("Behavior"))
        layout.addWidget(self.single_row("Body action type", self.widget_body_action))
        layout.addWidget(self.single_row("Body action target", self.widget_body_target_label))
        layout.addWidget(self.edit_body_action_btn, 0, Qt.AlignmentFlag.AlignLeft)

        self.widget_name.textChanged.connect(self.queue_live_update)
        for widget in [
            self.widget_x,
            self.widget_y,
            self.widget_width,
            self.widget_height,
            self.widget_theme,
            self.widget_display_mode,
            self.widget_opacity,
            self.widget_enabled,
            self.widget_locked,
            self.widget_body_action,
        ]:
            if isinstance(widget, QCheckBox):
                widget.toggled.connect(self.apply_live_changes)
            elif isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self.apply_live_changes)
            elif isinstance(widget, (QSpinBox, QSlider)):
                widget.valueChanged.connect(self.apply_live_changes)
        self.edit_body_action_btn.clicked.connect(self.edit_body_action)
        return card

    def section_text(self, text):
        label = QLabel(text)
        label.setObjectName("CardTitle")
        return label

    def single_row(self, label_text, widget):
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(label_text)
        label.setObjectName("FieldLabel")
        layout.addWidget(label)
        layout.addWidget(widget)
        return wrapper

    def dual_row(self, left_label, left_widget, right_label, right_widget):
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.single_row(left_label, left_widget))
        layout.addWidget(self.single_row(right_label, right_widget))
        return wrapper

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self.clear_layout(child_layout)

    def queue_live_update(self, *_args):
        if self._loading:
            return
        self.live_status_label.setText("Saving...")
        self._debounce_timer.start(220)

    def force_save_now(self):
        self._debounce_timer.stop()
        self.apply_live_changes()

    def current_widget(self):
        if not self.selected_widget_id:
            return None
        return self.manager.get_widget(self.selected_widget_id)

    def current_block(self):
        widget = self.current_widget()
        if not widget or not self.selected_block_id:
            return None
        for block in widget.get("blocks", []):
            if block.get("id") == self.selected_block_id:
                return block
        return None

    def block_display_name(self, block):
        config = block.get("config", {})
        block_type = block.get("type", "title")
        title = config.get("title") or config.get("text") or block_type.replace("_", " ").title()
        return f"{block_type.replace('_', ' ').title()} · {title[:36]}"

    def refresh_widget_list_labels(self):
        for row in range(self.widget_list.count()):
            item = self.widget_list.item(row)
            widget = self.manager.get_widget(item.data(Qt.ItemDataRole.UserRole))
            if widget:
                status = "ON" if widget.get("enabled") else "OFF"
                item.setText(f"{widget['name']} [{status}]")

    def rebuild_block_cards(self):
        self.clear_layout(self.blocks_container_layout)
        self.block_cards = {}
        widget = self.current_widget()
        blocks = widget.get("blocks", []) if widget else []

        has_blocks = bool(blocks)
        self.empty_blocks_label.setVisible(not has_blocks)
        self.empty_add_block_btn.setVisible(not has_blocks)
        self.blocks_container.setVisible(has_blocks)

        for block in blocks:
            card = BlockEditorCard(self, block["id"], parent=self.blocks_container)
            self.block_cards[block["id"]] = card
            self.blocks_container_layout.addWidget(card)

        self.blocks_container_layout.addStretch()
        if blocks and not self.selected_block_id:
            self.selected_block_id = blocks[0]["id"]
        if self.selected_block_id and self.selected_block_id not in self.block_cards:
            self.selected_block_id = blocks[0]["id"] if blocks else None
        self.refresh_selected_block_state()

    def refresh_selected_block_state(self):
        for block_id, card in self.block_cards.items():
            card.set_selected(block_id == self.selected_block_id)
        self.refresh_action_states()

    def reload_from_manager(self, keep_selection=False):
        selected_widget_id = self.selected_widget_id if keep_selection else None
        selected_block_id = self.selected_block_id if keep_selection else None

        self._loading = True
        self.widget_list.clear()
        for widget in self.manager.widgets:
            status = "ON" if widget.get("enabled") else "OFF"
            item = QListWidgetItem(f"{widget['name']} [{status}]")
            item.setData(Qt.ItemDataRole.UserRole, widget["id"])
            self.widget_list.addItem(item)
            if widget["id"] == selected_widget_id:
                self.widget_list.setCurrentItem(item)
        if self.widget_list.currentItem() is None and self.widget_list.count():
            self.widget_list.setCurrentRow(0)
        self._loading = False

        if self.widget_list.currentItem() is not None:
            self.on_widget_selected(self.widget_list.currentItem(), None)
            if selected_block_id:
                self.select_block(selected_block_id)
        else:
            self.selected_widget_id = None
            self.selected_block_id = None
            self.preview_canvas.set_definition({})
            self.rebuild_block_cards()
            self.refresh_action_states()

    def on_widget_selected(self, current, previous):
        if self._loading:
            return
        self.selected_widget_id = current.data(Qt.ItemDataRole.UserRole) if current else None
        widget = self.current_widget()
        self._loading = True
        if not widget:
            self.preview_canvas.set_definition({})
            self._loading = False
            self.rebuild_block_cards()
            self.refresh_action_states()
            return

        self.widget_name.setText(widget.get("name", ""))
        self.widget_x.setValue(int(widget.get("position", {}).get("x", 120)))
        self.widget_y.setValue(int(widget.get("position", {}).get("y", 120)))
        self.widget_width.setValue(int(widget.get("size", {}).get("width", 420)))
        self.widget_height.setValue(int(widget.get("size", {}).get("height", 180)))
        self.widget_theme.setCurrentText(widget.get("theme_mode", "app"))
        self.widget_display_mode.setCurrentText(widget.get("display_mode", "desktop_only"))
        self.widget_opacity.setValue(int(round(float(widget.get("opacity", 0.96)) * 100)))
        self.widget_enabled.setChecked(bool(widget.get("enabled")))
        self.widget_locked.setChecked(bool(widget.get("locked")))
        body_action = normalize_action_target(widget.get("click_action_on_body"))
        self.widget_body_action.setCurrentText(body_action.get("type", "none"))
        self.widget_body_target_label.setText(self.manager.describe_action_target(body_action))
        self.preview_canvas.set_definition(widget)
        self.selected_block_id = widget.get("blocks", [{}])[0].get("id") if widget.get("blocks") else None
        self._loading = False
        self.rebuild_block_cards()
        self.live_status_label.setText("Live updates on")

    def select_block(self, block_id, focus=False):
        if not block_id:
            return
        self.selected_block_id = block_id
        self.refresh_selected_block_state()
        card = self.block_cards.get(block_id)
        if card is not None:
            if card.collapsed:
                card.toggle_collapsed()
            if focus:
                card.header_button.setFocus()

    def write_widget_state(self, widget):
        widget["name"] = self.widget_name.text().strip() or "Widget"
        widget["position"] = {"x": self.widget_x.value(), "y": self.widget_y.value()}
        widget["size"] = {"width": self.widget_width.value(), "height": self.widget_height.value()}
        widget["theme_mode"] = self.widget_theme.currentText()
        widget["display_mode"] = self.widget_display_mode.currentText()
        widget["opacity"] = self.widget_opacity.value() / 100.0
        widget["enabled"] = self.widget_enabled.isChecked()
        widget["locked"] = self.widget_locked.isChecked()
        target = normalize_action_target(widget.get("click_action_on_body"))
        target["type"] = self.widget_body_action.currentText()
        if target["type"] == "none":
            target = {"type": "none"}
        widget["click_action_on_body"] = target
        self.widget_body_target_label.setText(self.manager.describe_action_target(target))

    def write_block_state(self, widget):
        for block in widget.get("blocks", []):
            card = self.block_cards.get(block.get("id"))
            if card is not None:
                card.write_to_block(block)

    def apply_live_changes(self, *_args):
        if self._loading:
            return
        widget = self.current_widget()
        if not widget:
            return
        self.write_widget_state(widget)
        self.write_block_state(widget)
        normalized = self.manager.apply_widget_changes(widget["id"], refresh_manager=False)
        if normalized is None:
            return
        self.refresh_widget_list_labels()
        self.preview_canvas.set_definition(normalized)
        for block_id, card in self.block_cards.items():
            if card.current_block():
                card.header_button.setText(self.block_display_name(card.current_block()))
        self.refresh_selected_block_state()
        self.live_status_label.setText("Saved live")

    def refresh_action_states(self):
        has_widget = self.current_widget() is not None
        has_block = self.current_block() is not None
        for control in (
            self.top_duplicate_widget_btn,
            self.top_rename_widget_btn,
            self.top_delete_widget_btn,
            self.top_add_block_btn,
            self.top_save_now_btn,
            self.widget_name,
            self.widget_x,
            self.widget_y,
            self.widget_width,
            self.widget_height,
            self.widget_theme,
            self.widget_display_mode,
            self.widget_opacity,
            self.widget_enabled,
            self.widget_locked,
            self.widget_body_action,
            self.edit_body_action_btn,
            self.blocks_add_btn,
            self.empty_add_block_btn,
        ):
            control.setEnabled(has_widget)
        self.top_delete_block_btn.setEnabled(has_block)

    def create_widget(self):
        values = ThemedFormDialog.ask(
            self,
            title="Create Widget",
            subtitle="Choose a starting point for the new desktop widget.",
            fields=[
                FormField(
                    "preset",
                    "Widget preset",
                    kind="combo",
                    default="Blank Widget",
                    options=("Blank Widget", "Assignment Countdown", "Shortcut Panel", "Note Widget"),
                )
            ],
            accept_text="Create Widget",
        )
        if not values:
            return
        widget = self.manager.add_widget_from_preset(values["preset"])
        self.reload_from_manager()
        self.live_status_label.setText("Saved live")
        for row in range(self.widget_list.count()):
            item = self.widget_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == widget["id"]:
                self.widget_list.setCurrentItem(item)
                break

    def duplicate_widget(self):
        widget = self.current_widget()
        if not widget:
            return
        duplicated = self.manager.duplicate_widget(widget["id"])
        self.reload_from_manager()
        self.live_status_label.setText("Saved live")
        for row in range(self.widget_list.count()):
            item = self.widget_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == duplicated["id"]:
                self.widget_list.setCurrentItem(item)
                break

    def rename_widget(self):
        widget = self.current_widget()
        if not widget:
            return
        values = ThemedFormDialog.ask(
            self,
            title="Rename Widget",
            subtitle="Choose a clearer display name for this widget.",
            fields=[FormField("name", "Widget name", default=widget.get("name", "Widget"), required=True)],
            accept_text="Rename",
        )
        if not values:
            return
        widget["name"] = values["name"].strip() or "Widget"
        self.manager.apply_widget_changes(widget["id"], refresh_manager=False)
        self.refresh_widget_list_labels()
        self.widget_name.setText(widget["name"])
        self.live_status_label.setText("Saved live")

    def delete_widget(self):
        widget = self.current_widget()
        if not widget:
            return
        if QMessageBox.question(self, "Delete Widget", f"Delete '{widget['name']}'?") != QMessageBox.StandardButton.Yes:
            return
        self.manager.delete_widget(widget["id"])
        self.reload_from_manager()
        self.live_status_label.setText("Saved live")

    def add_block(self):
        widget = self.current_widget()
        if not widget:
            return
        values = ThemedFormDialog.ask(
            self,
            title="Add Block",
            subtitle="Choose the content block type to place in this widget.",
            fields=[
                FormField(
                    "block_type",
                    "Block type",
                    kind="combo",
                    default="title",
                    options=("title", "assignment_countdown", "note", "shortcut"),
                )
            ],
            accept_text="Add Block",
        )
        if not values:
            return
        block = default_block(values["block_type"])
        block["grid_y"] = len(widget.get("blocks", [])) * 2
        widget.setdefault("blocks", []).append(block)
        self.manager.apply_widget_changes(widget["id"], refresh_manager=False)
        self.rebuild_block_cards()
        self.select_block(block["id"], focus=True)
        self.preview_canvas.set_definition(widget)
        self.live_status_label.setText("Saved live")

    def delete_block(self, block_id=None):
        widget = self.current_widget()
        target_id = block_id or self.selected_block_id
        if not widget or not target_id:
            return
        widget["blocks"] = [item for item in widget.get("blocks", []) if item.get("id") != target_id]
        self.manager.apply_widget_changes(widget["id"], refresh_manager=False)
        self.selected_block_id = widget.get("blocks", [{}])[0].get("id") if widget.get("blocks") else None
        self.rebuild_block_cards()
        self.preview_canvas.set_definition(widget)
        self.live_status_label.setText("Saved live")

    def duplicate_block(self, block_id=None):
        widget = self.current_widget()
        target_id = block_id or self.selected_block_id
        if not widget or not target_id:
            return
        source = None
        for block in widget.get("blocks", []):
            if block.get("id") == target_id:
                source = block
                break
        if not source:
            return
        new_block = {
            "id": default_block(source.get("type", "title"))["id"],
            "type": source.get("type", "title"),
            "grid_x": source.get("grid_x", 0),
            "grid_y": min(24, source.get("grid_y", 0) + 1),
            "grid_w": source.get("grid_w", 12),
            "grid_h": source.get("grid_h", 3),
            "config": copy.deepcopy(source.get("config", {})),
        }
        widget.setdefault("blocks", []).append(new_block)
        self.manager.apply_widget_changes(widget["id"], refresh_manager=False)
        self.rebuild_block_cards()
        self.select_block(new_block["id"], focus=True)
        self.preview_canvas.set_definition(widget)
        self.live_status_label.setText("Saved live")

    def edit_body_action(self):
        widget = self.current_widget()
        if not widget:
            return
        current = {"label": widget.get("name", "Widget"), "target": widget.get("click_action_on_body", {"type": "none"})}
        dialog = ShortcutActionDialog(self.manager, action_item=current, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.result_value():
            return
        widget["click_action_on_body"] = dialog.result_value().get("target", {"type": "none"})
        self.manager.apply_widget_changes(widget["id"], refresh_manager=False)
        body_action = normalize_action_target(widget.get("click_action_on_body"))
        self.widget_body_action.setCurrentText(body_action.get("type", "none"))
        self.widget_body_target_label.setText(self.manager.describe_action_target(body_action))
        self.live_status_label.setText("Saved live")

    def focus_selected_widget(self):
        widget = self.current_widget()
        if widget:
            self.preview_canvas.set_definition(widget)

    def open_widget_list_context_menu(self, pos):
        item = self.widget_list.itemAt(pos)
        if item:
            self.widget_list.setCurrentItem(item)
        menu = AppContextMenu(self)
        add_menu_action(menu, "Add Widget", "plus", self.create_widget, shortcut="Ctrl+N")
        if self.current_widget():
            add_menu_action(menu, "Duplicate Widget", "copy", self.duplicate_widget, shortcut="Ctrl+D")
            add_menu_action(menu, "Rename Widget", "edit", self.rename_widget, shortcut="F2")
            add_menu_action(menu, "Delete Widget", "delete", self.delete_widget, shortcut="Delete")
        menu.exec(self.widget_list.mapToGlobal(pos))

    def open_preview_background_context_menu(self, pos):
        menu = AppContextMenu(self)
        add_menu_action(menu, "Add Block", "plus", self.add_block, shortcut="Ctrl+Shift+N")
        add_menu_action(menu, "Refresh Preview", "refresh", lambda: self.preview_canvas.set_definition(self.current_widget() or {}))
        if self.current_widget():
            add_menu_action(menu, "Rename Widget", "edit", self.rename_widget, shortcut="F2")
        menu.exec(self.preview_canvas.grid_host.mapToGlobal(pos))

    def open_preview_block_context_menu(self, block_id, source, pos):
        self.select_block(block_id)
        menu = AppContextMenu(self)
        add_menu_action(menu, "Duplicate Block", "copy", lambda: self.duplicate_block(block_id), shortcut="Ctrl+D")
        add_menu_action(menu, "Delete Block", "delete", lambda: self.delete_block(block_id), shortcut="Delete")
        target = source or self.preview_canvas.grid_host
        menu.exec(target.mapToGlobal(pos or target.rect().center()))

    def keyPressEvent(self, event):
        focus = QApplication.focusWidget()
        editing_focus = isinstance(focus, (QLineEdit, QTextEdit))
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key.Key_Escape:
            self.close()
            return
        if modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_W:
            self.close()
            return
        if modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_N:
            self.create_widget()
            return
        if modifiers == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier) and key == Qt.Key.Key_N:
            self.add_block()
            return
        if modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_D:
            if self.selected_block_id and not self.widget_list.hasFocus():
                self.duplicate_block()
            else:
                self.duplicate_widget()
            return
        if key == Qt.Key.Key_F2 and not editing_focus:
            self.rename_widget()
            return
        if key == Qt.Key.Key_Delete and not editing_focus:
            if self.selected_block_id and not self.widget_list.hasFocus():
                self.delete_block()
            else:
                self.delete_widget()
            return
        super().keyPressEvent(event)
