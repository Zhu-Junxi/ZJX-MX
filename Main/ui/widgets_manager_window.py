from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QSize, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QImageReader
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
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.widget_manager import (
    MAX_WIDGET_HEIGHT,
    MAX_WIDGET_WIDTH,
    TEMPLATE_ASSIGNMENT,
    TEMPLATE_NOTE,
    TEMPLATE_SHORTCUTS,
    default_shortcut_item,
    normalize_action_target,
)
from app.styles import APP_FONT_STACK, build_context_menu_styles, scaled_font_px
from core.helpers import format_due_datetime
from ui.context_menus import AppContextMenu, add_menu_action
from ui.icons import load_icon
from ui.themed_forms import FormField, ThemedFormDialog


def note_content_is_html(config):
    return str((config or {}).get("text_format") or "").lower() == "html"


def set_note_editor_content(editor, config):
    text = str((config or {}).get("text") or "")
    if note_content_is_html(config):
        editor.setHtml(text)
    else:
        editor.setPlainText(text)


def note_editor_content(editor, prefer_html=False):
    document_html = editor.toHtml()
    has_image = "<img" in document_html.lower()
    if prefer_html or has_image:
        return document_html, "html"
    return editor.toPlainText(), "plain"


class ImagePasteNoteEdit(QTextEdit):
    def __init__(self, image_cache_callback=None, parent=None):
        super().__init__(parent)
        self.image_cache_callback = image_cache_callback
        self.setAcceptRichText(True)

    def insertFromMimeData(self, source):
        image = None
        if source.hasImage():
            image = source.imageData()
        elif source.hasUrls():
            for url in source.urls():
                if not url.isLocalFile():
                    continue
                reader = QImageReader(url.toLocalFile())
                reader.setAutoTransform(True)
                loaded = reader.read()
                if not loaded.isNull():
                    image = loaded
                    break

        if image is None or image.isNull():
            super().insertFromMimeData(source)
            return

        image_path = self.image_cache_callback(image) if self.image_cache_callback else ""
        if not image_path:
            super().insertFromMimeData(source)
            return

        display_width = min(image.width(), max(140, self.viewport().width() - 36))
        image_url = QUrl.fromLocalFile(str(Path(image_path))).toString()
        self.textCursor().insertHtml(
            f'<p><img src="{image_url}" width="{int(display_width)}"></p>'
        )


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
        }
    return {
        "surface": "#101827",
        "surface_alt": "#182335",
        "border": "#2a3a50",
        "text": "#e5eefc",
        "muted": "#9cb0c8",
        "accent": accent,
        "pill": "#17345f",
    }


def manager_editor_colours(theme, accent):
    if theme == "light":
        return {
            "window_bg": "#eef4fb",
            "text": "#16304f",
            "title": "#10253c",
            "muted": "#5c718b",
            "label": "#6a7d95",
            "card_bg": "rgba(255, 255, 255, 0.96)",
            "card_border": "#d8e2ef",
            "input_bg": "#f8fbff",
            "input_border": "#d6e0ec",
            "item_hover": "#edf4ff",
            "item_bg": "#ffffff",
            "item_selected": "#e7f0ff",
            "item_disabled": "#f3f7fc",
            "pill_on_bg": accent,
            "pill_off_bg": "#dbe5f2",
            "pill_off_text": "#58708d",
            "menu_bg": "#ffffff",
            "menu_border": "#cbd8ea",
            "menu_hover": "#eaf2ff",
            "button_bg": "#f5f9ff",
            "button_hover": "#eaf2ff",
            "button_pressed": "#dde9fb",
            "checkbox_bg": "#ffffff",
            "checkbox_border": "#bdd0e8",
            "slider_groove": "#dce7f4",
            "slider_handle": "#ffffff",
            "slider_handle_border": "#b9cde6",
        }
    return {
        "window_bg": "#0d1522",
        "text": "#dbe8fb",
        "title": "#f3f8ff",
        "muted": "#9eb2cb",
        "label": "#8da3c0",
        "card_bg": "rgba(19, 30, 48, 0.96)",
        "card_border": "#273954",
        "input_bg": "#121d2f",
        "input_border": "#2a3d5b",
        "item_hover": "#1a2b43",
        "item_bg": "#121d2f",
        "item_selected": "#17345f",
        "item_disabled": "#111927",
        "pill_on_bg": accent,
        "pill_off_bg": "#26364d",
        "pill_off_text": "#a6b8cf",
        "menu_bg": "#101827",
        "menu_border": "#2a3d5b",
        "menu_hover": "#1b2d47",
        "button_bg": "#142236",
        "button_hover": "#1b2d47",
        "button_pressed": "#203657",
        "checkbox_bg": "#121d2f",
        "checkbox_border": "#3a5070",
        "slider_groove": "#25364d",
        "slider_handle": "#f8fbff",
        "slider_handle_border": "#90a9cb",
    }


def widget_editor_popup_stylesheet(manager):
    accent = manager.main_window.app_settings.get_accent_color()
    theme = manager.main_window.effective_theme_mode()
    zoom_percent = getattr(manager.main_window, "ui_zoom_percent", 100)
    colours = manager_editor_colours(theme, accent)
    base = scaled_font_px(15, zoom_percent)
    small = scaled_font_px(13, zoom_percent)
    title = scaled_font_px(23, zoom_percent)
    return f"""
    {build_context_menu_styles(theme, accent)}

    QDialog,
    QDialog#ThemedFormDialog {{
        background-color: {colours['window_bg']};
        color: {colours['text']};
        font-family: {APP_FONT_STACK};
        font-size: {base}px;
    }}
    QDialog QWidget {{
        background-color: transparent;
        color: {colours['text']};
        font-family: {APP_FONT_STACK};
        font-size: {base}px;
    }}
    QDialog QFrame#DialogCard {{
        background-color: {colours['card_bg']};
        border: 1px solid {colours['card_border']};
        border-radius: 22px;
    }}
    QDialog QLabel#DialogTitle {{
        color: {colours['title']};
        font-size: {title}px;
        font-weight: 850;
    }}
    QDialog QLabel#DialogSubtitle {{
        color: {colours['muted']};
        font-size: {small}px;
        font-weight: 550;
    }}
    QDialog QLabel#FieldLabel {{
        color: {colours['label']};
        font-size: {small}px;
        font-weight: 750;
    }}
    QDialog QLineEdit,
    QDialog QComboBox,
    QDialog QTextEdit,
    QDialog QSpinBox {{
        background-color: {colours['input_bg']};
        border: 1px solid {colours['input_border']};
        border-radius: 12px;
        color: {colours['text']};
        padding: 8px 10px;
        selection-background-color: {accent};
        selection-color: #ffffff;
    }}
    QDialog QLineEdit:focus,
    QDialog QComboBox:focus,
    QDialog QTextEdit:focus,
    QDialog QSpinBox:focus {{
        border: 1px solid {accent};
    }}
    QDialog QComboBox QAbstractItemView,
    QComboBox QAbstractItemView,
    QAbstractItemView {{
        background-color: {colours['input_bg']};
        border: 1px solid {colours['input_border']};
        color: {colours['text']};
        selection-background-color: {accent};
        selection-color: #ffffff;
        outline: 0;
    }}
    QDialog QPushButton#PrimaryButton,
    QDialog QPushButton#SecondaryButton,
    QDialog QPushButton {{
        background-color: {colours['button_bg']};
        border: 1px solid {colours['input_border']};
        border-radius: 12px;
        color: {colours['text']};
        padding: 9px 14px;
        font-weight: 750;
    }}
    QDialog QPushButton#PrimaryButton {{
        background-color: {accent};
        border: 1px solid {accent};
        color: #ffffff;
    }}
    QDialog QPushButton:hover {{
        background-color: {colours['button_hover']};
    }}
    """


class ShortcutActionDialog(QDialog):
    ACTION_OPTIONS = (
        ("In-App", "section"),
        ("User", "user"),
        ("Course", "course"),
        ("Assignments", "assignment"),
        ("Path/URL", "path_or_url"),
    )

    def __init__(self, manager, action_item=None, parent=None):
        super().__init__(parent)
        self.manager = manager
        action_item = dict(action_item or {"label": "", "target": {"type": "section", "section": "Dashboard"}})
        target = normalize_action_target(action_item.get("target"))
        self._result = None

        self.setWindowTitle("Shortcut Action")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setObjectName("ThemedFormDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(widget_editor_popup_stylesheet(self.manager))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("DialogCard")
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        title = QLabel("Shortcut Action")
        title.setObjectName("DialogTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        subtitle = QLabel("Choose what this shortcut should open. It will use the same action styling as the rest of the app.")
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.label_edit = QLineEdit(action_item.get("label", "Shortcut"))
        self.label_edit.setObjectName("DialogInput")
        self.install_themed_text_context_menu(self.label_edit)
        self.type_combo = QComboBox()
        self.type_combo.setObjectName("DialogCombo")
        for label_text, value in self.ACTION_OPTIONS:
            self.type_combo.addItem(label_text, value)
        self.type_combo.setCurrentIndex(max(0, self.type_combo.findData(self.display_type_for_target(target))))

        self.section_combo = QComboBox()
        self.section_combo.setObjectName("DialogCombo")
        self.section_combo.addItems(["Dashboard", "Users", "Courses", "Assignments", "Files", "Resource Library", "Settings", "Help", "Widgets"])
        self.section_combo.setCurrentText(target.get("section", "Dashboard"))

        self.entity_combo = QComboBox()
        self.entity_combo.setObjectName("DialogCombo")
        self.path_edit = QLineEdit(target.get("value", ""))
        self.path_edit.setObjectName("DialogInput")
        self.install_themed_text_context_menu(self.path_edit)
        self._entity_payloads = []
        self.populate_entities(target)
        self.install_themed_combo_popups(self.type_combo, self.section_combo, self.entity_combo)

        self.label_row = self.make_form_row("Button label", self.label_edit)
        self.type_row = self.make_form_row("Target type", self.type_combo)
        self.section_row = self.make_form_row("Section", self.section_combo)
        self.entity_row = self.make_form_row("Entity target", self.entity_combo)
        self.path_row = self.make_form_row("Path / URL", self.path_edit)
        for row in (self.label_row, self.type_row, self.section_row, self.entity_row, self.path_row):
            layout.addWidget(row)

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

    def make_form_row(self, label_text, widget):
        host = QWidget()
        host.setObjectName("DialogField")
        host.setAutoFillBackground(False)
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        label = QLabel(label_text)
        label.setObjectName("FieldLabel")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addWidget(widget)
        return host

    def display_type_for_target(self, target):
        if target.get("type") in {"file", "folder", "url"}:
            return "path_or_url"
        return target.get("type", "section")

    def current_target_type(self):
        selected = self.type_combo.currentData()
        return str(selected or "section")

    def populate_entities(self, target):
        target_type = self.display_type_for_target(target)
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

    def refresh_visibility(self, target=None):
        target = target or {"type": self.current_target_type()}
        target_type = self.display_type_for_target(target)
        self.populate_entities(target)
        self.section_row.setVisible(target_type == "section")
        self.entity_row.setVisible(target_type in {"user", "course", "assignment"})
        self.path_row.setVisible(target_type == "path_or_url")

    def accept_if_valid(self):
        target_type = self.current_target_type()
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
                QMessageBox.information(self, "Shortcut Action", "Enter a local path or URL.")
                return
            lowered = value.lower()
            if lowered.startswith(("http://", "https://", "www.")):
                target = {"type": "url", "value": value}
            else:
                target = {"type": "file", "value": value}
        self._result = {"label": label, "target": target}
        self.accept()

    def result_value(self):
        return self._result

    def context_menu_stylesheet(self):
        return widget_editor_popup_stylesheet(self.manager)

    def install_themed_combo_popups(self, *combos):
        style = self.context_menu_stylesheet()
        for combo in combos:
            combo.view().setObjectName("ContextMenu")
            combo.view().setStyleSheet(style)

    def install_themed_text_context_menu(self, widget):
        widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        widget.customContextMenuRequested.connect(
            lambda pos, editor=widget: self.open_themed_text_context_menu(editor, pos)
        )

    def open_themed_text_context_menu(self, editor, pos):
        menu = editor.createStandardContextMenu()
        menu.setObjectName("ContextMenu")
        menu.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        menu.setStyleSheet(self.context_menu_stylesheet())
        menu.exec(editor.mapToGlobal(pos))
        menu.deleteLater()

class WidgetCanvas(QWidget):
    def __init__(self, manager, definition=None, *, preview=False, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.definition = definition or {}
        self.preview = preview
        self.note_editor = None
        self._setting_note_text = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.outer = QFrame()
        self.outer.setObjectName("DesktopWidgetOuter")
        self.outer_layout = QVBoxLayout(self.outer)
        self.outer_layout.setContentsMargins(18, 18, 18, 18)
        self.outer_layout.setSpacing(10)
        layout.addWidget(self.outer)
        self.set_definition(self.definition)

    def set_definition(self, definition):
        self.definition = definition or {}
        if self.preview:
            width = int(self.definition.get("size", {}).get("width", 420))
            height = int(self.definition.get("size", {}).get("height", 180))
            self.setFixedSize(width, height)
        self.refresh()
        if self.preview and self.parentWidget() is not None:
            self.parentWidget().adjustSize()

    def clear_layout(self):
        while self.outer_layout.count():
            item = self.outer_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def add_text(self, text, *, style):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(style)
        self.outer_layout.addWidget(label)
        return label

    def refresh(self):
        self.clear_layout()
        self.note_editor = None
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
            QPushButton {{
                background-color: {colours['pill']};
                border: 1px solid {colours['border']};
                border-radius: 12px;
                padding: 8px 10px;
                color: {colours['text']};
                font-weight: 700;
                text-align: left;
            }}
            """
        )

        template = self.definition.get("template_type", TEMPLATE_ASSIGNMENT)
        config = dict(self.definition.get("template_config") or {})
        note_template_active = template == TEMPLATE_NOTE
        zoom_percent = getattr(self.manager.main_window, "ui_zoom_percent", 100)
        title_style = f"color: {colours['text']}; font-size: {scaled_font_px(16, zoom_percent, 13)}px; font-weight: 800;"
        meta_style = f"color: {colours['muted']}; font-size: {scaled_font_px(13, zoom_percent, 11)}px; font-weight: 500;"
        hero_style = f"color: {colours['accent']}; font-size: {scaled_font_px(42, zoom_percent, 28)}px; font-weight: 800;"

        if template == TEMPLATE_ASSIGNMENT:
            self.add_text(config.get("title", "Assignment details"), style=title_style)
            resolved = self.manager.resolve_assignment_reference(config)
            if not resolved:
                self.add_text("Assignment unavailable", style=hero_style.replace(colours["accent"], colours["muted"]))
            else:
                assignment = resolved["assignment"]
                course = resolved["course"] or {}
                due_text = assignment.get("canvas_due_at") or assignment.get("due_date") or ""
                self.add_text(self.manager.main_window.due_countdown_text(due_text), style=hero_style)
                if config.get("show_assignment_title", True):
                    self.add_text(assignment.get("title", "Untitled assignment"), style=title_style)
                if config.get("show_course_label", True):
                    self.add_text(course.get("code") or course.get("name") or "Course", style=meta_style)
                if config.get("show_due_label", True):
                    self.add_text(f"Due: {format_due_datetime(due_text)}", style=meta_style)
        elif template == TEMPLATE_SHORTCUTS:
            self.add_text(config.get("title", "Quick Links"), style=title_style)
            for item in config.get("items", []):
                button = QPushButton(item.get("label", "Shortcut"))
                button.clicked.connect(lambda checked=False, target=item.get("target"): self.manager.open_action(target))
                self.outer_layout.addWidget(button)
        else:
            self.add_text(config.get("title", "Pinned Note"), style=title_style)
            allow_inline_edit = bool(config.get("allow_inline_edit", False))
            note_editor = ImagePasteNoteEdit(
                image_cache_callback=lambda image: self.manager.cache_note_image(self.definition.get("id", ""), image)
            )
            note_editor.setObjectName("DesktopWidgetNote")
            self._setting_note_text = True
            set_note_editor_content(note_editor, config)
            self._setting_note_text = False
            note_editor.setReadOnly(not allow_inline_edit or self.preview)
            note_editor.setPlaceholderText("Add a reminder, planning note, or study checklist here.")
            note_editor.setFrameShape(QFrame.Shape.NoFrame)
            note_editor.setMinimumHeight(84)
            note_editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            note_editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            note_editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            note_editor.setStyleSheet(
                f"""
                QTextEdit#DesktopWidgetNote {{
                    background-color: {colours['surface_alt']};
                    border: 1px solid {colours['border']};
                    border-radius: 16px;
                    padding: 10px 12px;
                    color: {colours['text']};
                    font-size: 14px;
                    font-weight: 500;
                }}
                """
            )
            if allow_inline_edit and not self.preview:
                note_editor.textChanged.connect(self.handle_note_changed)
            self.note_editor = note_editor
            self.outer_layout.addWidget(note_editor, 1)
        if not note_template_active:
            self.outer_layout.addStretch()

    def handle_note_changed(self):
        if self.preview or self._setting_note_text or self.note_editor is None:
            return
        text, text_format = note_editor_content(
            self.note_editor,
            prefer_html=note_content_is_html(self.definition.get("template_config") or {}),
        )
        self.manager.update_note_text_from_widget(self.definition.get("id", ""), text, text_format)


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

    def note_inline_edit_enabled(self):
        if self.definition.get("template_type") != TEMPLATE_NOTE:
            return False
        config = dict(self.definition.get("template_config") or {})
        return bool(config.get("allow_inline_edit", False))

    def install_drag_filters(self):
        for widget in [self, self.canvas, self.canvas.outer, *self.canvas.findChildren(QWidget)]:
            if isinstance(widget, QPushButton):
                continue
            if widget is self.canvas.note_editor and widget is not None and not widget.isReadOnly():
                continue
            widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self.canvas.note_editor and watched is not None and not watched.isReadOnly():
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self.raise_()
                self.activateWindow()
                watched.setFocus(Qt.FocusReason.MouseFocusReason)
            return super().eventFilter(watched, event)
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
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, not self.note_inline_edit_enabled())
        if self.note_inline_edit_enabled():
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        else:
            self.clearFocus()
        self.resize(
            int(definition.get("size", {}).get("width", 420)),
            int(definition.get("size", {}).get("height", 180)),
        )
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

    def window_handle_int(self):
        return int(self.winId())

    def apply_visibility(self, visible):
        if visible and not self.isVisible():
            self.show()
        elif not visible and self.isVisible():
            self.hide()


class WidgetBrowserRow(QFrame):
    """Themeable widget-list row with a dedicated enabled toggle."""

    selectedRequested = Signal(str)
    toggleRequested = Signal(str)

    def __init__(self, manager, widget, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.widget_id = widget.get("id", "")
        self.setObjectName("WidgetBrowserRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("WidgetBrowserIcon")
        self.icon_label.setFixedSize(32, 32)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)
        self.name_label = QLabel()
        self.name_label.setObjectName("WidgetBrowserTitle")
        self.name_label.setWordWrap(False)
        self.summary_label = QLabel()
        self.summary_label.setObjectName("WidgetBrowserSummary")
        self.summary_label.setWordWrap(False)
        text_layout.addWidget(self.name_label)
        text_layout.addWidget(self.summary_label)
        layout.addLayout(text_layout, 1)

        self.toggle_btn = QPushButton()
        self.toggle_btn.setObjectName("WidgetToggleButton")
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setFixedSize(60, 32)
        self.toggle_btn.setContentsMargins(0, 0, 0, 0)
        self.toggle_btn.clicked.connect(lambda _checked=False: self.toggleRequested.emit(self.widget_id))
        layout.addWidget(self.toggle_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.apply_zoom_metrics(getattr(self.manager.main_window, "ui_zoom_percent", 100))
        self.update_from_widget(widget)

    def mousePressEvent(self, event):
        self.selectedRequested.emit(self.widget_id)
        super().mousePressEvent(event)

    def template_icon_name(self, widget):
        template = widget.get("template_type", TEMPLATE_ASSIGNMENT)
        if template == TEMPLATE_SHORTCUTS:
            return "link"
        if template == TEMPLATE_NOTE:
            return "note"
        return "assignment"

    def update_from_widget(self, widget, selected=False):
        enabled = bool(widget.get("enabled"))
        summary = self.manager.template_summary(widget)
        template = widget.get("template_type", TEMPLATE_ASSIGNMENT)

        icon = load_icon(self.template_icon_name(widget))
        pixmap = icon.pixmap(QSize(22, 22))
        self.icon_label.setPixmap(pixmap)
        self.name_label.setText(widget.get("name", "Widget"))
        self.summary_label.setText(f"{template} / {summary}")
        self.setToolTip(f"{template}\n{summary}")
        self.toggle_btn.setText("ON" if enabled else "OFF")
        self.toggle_btn.setToolTip("Disable widget" if enabled else "Enable widget")

        self.setProperty("enabledState", "true" if enabled else "false")
        self.setProperty("selected", "true" if selected else "false")
        self.toggle_btn.setProperty("enabledState", "true" if enabled else "false")
        self.refresh_style()

    def refresh_style(self):
        for widget in (self, self.toggle_btn, self.icon_label, self.name_label, self.summary_label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def apply_zoom_metrics(self, zoom_percent):
        icon_well = scaled_font_px(32, zoom_percent, 24)
        toggle_width = scaled_font_px(60, zoom_percent, 52)
        toggle_height = scaled_font_px(32, zoom_percent, 28)
        self.icon_label.setFixedSize(icon_well, icon_well)
        self.toggle_btn.setFixedSize(toggle_width, toggle_height)


class WidgetsManagerWindow(QMainWindow):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.selected_widget_id = None
        self._loading = False
        self._row_widgets = {}
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self.apply_live_changes)

        self.setWindowTitle("Desktop Widgets")
        self.setObjectName("WidgetsManagerWindow")
        self.setWindowFlag(Qt.WindowType.Window, True)
        available = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
        if available:
            self.resize(min(available.width() - 40, 1280), min(available.height() - 40, 820))
        else:
            self.resize(1220, 800)
        self.setMinimumSize(980, 680)
        self.apply_theme_styling()

        container = QWidget()
        container.setObjectName("WidgetsManagerRoot")
        outer = QVBoxLayout(container)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        title = QLabel("Desktop Widgets")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Choose a widget template, connect it to your data, and keep it running from the tray.")
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
        splitter.setSizes([250, 540, 400])

        self.setCentralWidget(container)
        self.apply_responsive_metrics()
        self.refresh_action_states()

    def zpx(self, value, minimum=1):
        zoom_percent = getattr(self.manager.main_window, "ui_zoom_percent", 100)
        return max(minimum, int(round(value * (zoom_percent / 100.0))))

    def apply_responsive_metrics(self):
        self.setMinimumSize(self.zpx(980, 820), self.zpx(680, 560))
        if hasattr(self, "shortcuts_list"):
            self.shortcuts_list.setMaximumHeight(self.zpx(140, 96))
        if hasattr(self, "widget_list"):
            for row_widget in self._row_widgets.values():
                row_widget.apply_zoom_metrics(getattr(self.manager.main_window, "ui_zoom_percent", 100))

    def closeEvent(self, event):
        self.manager.manager_window = None
        super().closeEvent(event)

    def build_top_bar(self):
        bar = QFrame()
        bar.setObjectName("WidgetsToolbarCard")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        self.add_widget_btn = QPushButton("Add Widget")
        self.duplicate_widget_btn = QPushButton("Duplicate")
        self.rename_widget_btn = QPushButton("Rename")
        self.delete_widget_btn = QPushButton("Delete")
        self.save_now_btn = QPushButton("Save Now")
        for button in (
            self.add_widget_btn,
            self.duplicate_widget_btn,
            self.rename_widget_btn,
            self.delete_widget_btn,
            self.save_now_btn,
        ):
            button.setObjectName("SmallButton")
        self.live_status_label = QLabel("Live updates on")
        self.live_status_label.setObjectName("CardBody")

        layout.addWidget(self.add_widget_btn)
        layout.addWidget(self.duplicate_widget_btn)
        layout.addWidget(self.rename_widget_btn)
        layout.addWidget(self.delete_widget_btn)
        layout.addStretch()
        layout.addWidget(self.live_status_label)
        layout.addWidget(self.save_now_btn)

        self.add_widget_btn.clicked.connect(self.create_widget)
        self.duplicate_widget_btn.clicked.connect(self.duplicate_widget)
        self.rename_widget_btn.clicked.connect(self.rename_widget)
        self.delete_widget_btn.clicked.connect(self.delete_widget)
        self.save_now_btn.clicked.connect(self.force_save_now)
        return bar

    def build_left_panel(self):
        panel = QFrame()
        panel.setObjectName("WidgetsPanelCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        label = QLabel("Widgets")
        label.setObjectName("CardTitle")
        layout.addWidget(label)

        self.widget_list = QListWidget()
        self.widget_list.setObjectName("WidgetsList")
        self.widget_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.widget_list.setSpacing(8)
        layout.addWidget(self.widget_list, 1)

        helper = QLabel("Pick a template-backed widget, then connect it to an assignment, note, or shortcuts.")
        helper.setObjectName("CardBody")
        helper.setWordWrap(True)
        layout.addWidget(helper)

        self.widget_list.currentItemChanged.connect(self.on_widget_selected)
        self.widget_list.customContextMenuRequested.connect(self.open_widget_list_context_menu)
        return panel

    def build_preview_panel(self):
        panel = QFrame()
        panel.setObjectName("WidgetsPanelCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Live Preview")
        title.setObjectName("CardTitle")
        layout.addWidget(title)
        helper = QLabel("This preview mirrors the live desktop widget. Changes save automatically.")
        helper.setObjectName("CardBody")
        helper.setWordWrap(True)
        layout.addWidget(helper)

        host = QWidget()
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(12, 12, 12, 12)
        host_layout.setSpacing(0)
        host_layout.addStretch()
        self.preview_canvas = WidgetCanvas(self.manager, preview=True, parent=host)
        host_layout.insertWidget(0, self.preview_canvas, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(host)
        layout.addWidget(scroll, 1)
        return panel

    def build_right_panel(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("WidgetsInspectorScroll")

        host = QWidget()
        host.setObjectName("WidgetsInspectorHost")
        self.inspector = QVBoxLayout(host)
        self.inspector.setContentsMargins(0, 0, 0, 0)
        self.inspector.setSpacing(12)

        widget_card = QFrame()
        widget_card.setObjectName("WidgetsPanelCard")
        widget_layout = QVBoxLayout(widget_card)
        widget_layout.setContentsMargins(14, 14, 14, 14)
        widget_layout.setSpacing(10)
        header = QLabel("Widget Settings")
        header.setObjectName("CardTitle")
        widget_layout.addWidget(header)

        self.widget_name = QLineEdit()
        self.widget_x = QSpinBox()
        self.widget_x.setRange(-5000, 5000)
        self.widget_y = QSpinBox()
        self.widget_y.setRange(-5000, 5000)
        self.widget_width = QSpinBox()
        self.widget_width.setRange(240, MAX_WIDGET_WIDTH)
        self.widget_height = QSpinBox()
        self.widget_height.setRange(140, MAX_WIDGET_HEIGHT)
        self.widget_theme = QComboBox()
        self.widget_theme.addItems(["app", "dark", "light"])
        self.widget_display_mode = QComboBox()
        self.widget_display_mode.addItems(["desktop_only", "always_visible"])
        self.widget_opacity = QSlider(Qt.Orientation.Horizontal)
        self.widget_opacity.setRange(55, 100)
        self.widget_enabled = QCheckBox("Widget enabled")
        self.widget_locked = QCheckBox("Lock desktop position")
        widget_layout.addWidget(self.form_row("Name", self.widget_name))
        widget_layout.addWidget(self.dual_row("Position X", self.widget_x, "Position Y", self.widget_y))
        widget_layout.addWidget(self.dual_row("Width", self.widget_width, "Height", self.widget_height))
        widget_layout.addWidget(self.section_label("Appearance"))
        widget_layout.addWidget(self.dual_row("Theme", self.widget_theme, "Display mode", self.widget_display_mode))
        widget_layout.addWidget(self.form_row("Opacity", self.widget_opacity))
        widget_layout.addWidget(self.widget_enabled)
        widget_layout.addWidget(self.widget_locked)

        self.inspector.addWidget(widget_card)

        self.template_card = QFrame()
        self.template_card.setObjectName("WidgetsPanelCard")
        template_layout = QVBoxLayout(self.template_card)
        template_layout.setContentsMargins(14, 14, 14, 14)
        template_layout.setSpacing(10)
        template_title = QLabel("Template")
        template_title.setObjectName("CardTitle")
        template_layout.addWidget(template_title)

        self.template_type = QComboBox()
        self.template_type.addItems([TEMPLATE_ASSIGNMENT, TEMPLATE_SHORTCUTS, TEMPLATE_NOTE])
        template_layout.addWidget(self.form_row("Widget template", self.template_type))

        self.assignment_group = QWidget()
        assignment_layout = QVBoxLayout(self.assignment_group)
        assignment_layout.setContentsMargins(0, 0, 0, 0)
        assignment_layout.setSpacing(8)
        self.assignment_title = QLineEdit()
        self.assignment_target = QComboBox()
        self.assignment_show_title = QCheckBox("Show assignment title")
        self.assignment_show_course = QCheckBox("Show course label")
        self.assignment_show_due = QCheckBox("Show due label")
        assignment_layout.addWidget(self.form_row("Header", self.assignment_title))
        assignment_layout.addWidget(self.form_row("Assignment", self.assignment_target))
        assignment_layout.addWidget(self.assignment_show_title)
        assignment_layout.addWidget(self.assignment_show_course)
        assignment_layout.addWidget(self.assignment_show_due)
        template_layout.addWidget(self.assignment_group)

        self.shortcuts_group = QWidget()
        shortcuts_layout = QVBoxLayout(self.shortcuts_group)
        shortcuts_layout.setContentsMargins(0, 0, 0, 0)
        shortcuts_layout.setSpacing(8)
        self.shortcuts_title = QLineEdit()
        self.shortcuts_list = QListWidget()
        self.shortcuts_list.setObjectName("ShortcutsList")
        self.shortcuts_list.setMaximumHeight(140)
        shortcut_buttons = QHBoxLayout()
        self.shortcut_add_btn = QPushButton("Add Action")
        self.shortcut_edit_btn = QPushButton("Edit Action")
        self.shortcut_delete_btn = QPushButton("Delete Action")
        for button in (self.shortcut_add_btn, self.shortcut_edit_btn, self.shortcut_delete_btn):
            button.setObjectName("SmallButton")
            shortcut_buttons.addWidget(button)
        shortcuts_layout.addWidget(self.form_row("Header", self.shortcuts_title))
        shortcuts_layout.addWidget(self.shortcuts_list)
        shortcuts_layout.addLayout(shortcut_buttons)
        template_layout.addWidget(self.shortcuts_group)

        self.note_group = QWidget()
        note_layout = QVBoxLayout(self.note_group)
        note_layout.setContentsMargins(0, 0, 0, 0)
        note_layout.setSpacing(8)
        self.note_title = QLineEdit()
        self.note_text = ImagePasteNoteEdit(image_cache_callback=self.cache_note_editor_image)
        self.note_inline_edit = QCheckBox("Allow editing directly in the desktop widget")
        self.install_themed_text_context_menu(
            self.widget_name,
            self.assignment_title,
            self.shortcuts_title,
            self.note_title,
            self.note_text,
        )
        self.install_themed_combo_popups(
            self.widget_theme,
            self.widget_display_mode,
            self.template_type,
            self.assignment_target,
        )
        note_layout.addWidget(self.form_row("Header", self.note_title))
        note_layout.addWidget(self.note_inline_edit)
        note_layout.addWidget(self.form_row("Note", self.note_text))
        template_layout.addWidget(self.note_group)

        self.inspector.addWidget(self.template_card)
        self.inspector.addStretch()
        scroll.setWidget(host)

        self.widget_name.textChanged.connect(self.queue_live_update)
        self.assignment_title.textChanged.connect(self.queue_live_update)
        self.shortcuts_title.textChanged.connect(self.queue_live_update)
        self.note_title.textChanged.connect(self.queue_live_update)
        self.note_text.textChanged.connect(self.queue_live_update)
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
            self.template_type,
            self.assignment_target,
            self.assignment_show_title,
            self.assignment_show_course,
            self.assignment_show_due,
            self.note_inline_edit,
        ]:
            if isinstance(widget, QCheckBox):
                widget.toggled.connect(self.apply_live_changes)
            elif isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self.apply_live_changes)
            elif isinstance(widget, (QSpinBox, QSlider)):
                widget.valueChanged.connect(self.apply_live_changes)

        self.shortcut_add_btn.clicked.connect(self.add_shortcut_action)
        self.shortcut_edit_btn.clicked.connect(self.edit_shortcut_action)
        self.shortcut_delete_btn.clicked.connect(self.delete_shortcut_action)
        return scroll

    def section_label(self, text):
        label = QLabel(text)
        label.setObjectName("SectionLabel")
        return label

    def build_manager_stylesheet(self):
        accent = self.manager.main_window.app_settings.get_accent_color()
        theme = self.manager.main_window.effective_theme_mode()
        zoom_percent = getattr(self.manager.main_window, "ui_zoom_percent", 100)
        colours = manager_editor_colours(theme, accent)
        base = scaled_font_px(17, zoom_percent)
        secondary = scaled_font_px(16, zoom_percent)
        small = scaled_font_px(15, zoom_percent)
        title = scaled_font_px(20, zoom_percent)
        page_title = scaled_font_px(34, zoom_percent)
        return f"""
        QMainWindow#WidgetsManagerWindow {{
            background-color: {colours['window_bg']};
        }}
        QMainWindow#WidgetsManagerWindow QWidget#WidgetsManagerRoot {{
            background-color: {colours['window_bg']};
        }}
        QMainWindow#WidgetsManagerWindow QWidget {{
            color: {colours['text']};
            background-color: transparent;
            font-family: {APP_FONT_STACK};
            font-size: {base}px;
        }}
        QMainWindow#WidgetsManagerWindow QLabel {{
            color: {colours['text']};
            background-color: transparent;
            font-family: {APP_FONT_STACK};
            font-size: {base}px;
        }}
        QMainWindow#WidgetsManagerWindow QLabel#PageTitle {{
            color: {colours['title']};
            font-size: {page_title}px;
            font-weight: 800;
        }}
        QMainWindow#WidgetsManagerWindow QLabel#PageSubtitle,
        QMainWindow#WidgetsManagerWindow QLabel#CardBody {{
            color: {colours['muted']};
            font-size: {base}px;
            font-weight: 500;
        }}
        QMainWindow#WidgetsManagerWindow QLabel#CardTitle {{
            color: {colours['title']};
            font-size: {title}px;
            font-weight: 800;
        }}
        QMainWindow#WidgetsManagerWindow QLabel#SectionLabel,
        QMainWindow#WidgetsManagerWindow QLabel#FieldLabel {{
            color: {colours['label']};
            font-size: {small}px;
            font-weight: 700;
            letter-spacing: 0.3px;
        }}
        QMainWindow#WidgetsManagerWindow QFrame#WidgetsToolbarCard,
        QMainWindow#WidgetsManagerWindow QFrame#WidgetsPanelCard {{
            background-color: {colours['card_bg']};
            border: 1px solid {colours['card_border']};
            border-radius: 22px;
        }}
        QMainWindow#WidgetsManagerWindow QSplitter::handle {{
            background-color: transparent;
        }}
        QMainWindow#WidgetsManagerWindow QLineEdit,
        QMainWindow#WidgetsManagerWindow QComboBox,
        QMainWindow#WidgetsManagerWindow QSpinBox,
        QMainWindow#WidgetsManagerWindow QTextEdit {{
            background-color: {colours['input_bg']};
            border: 1px solid {colours['input_border']};
            border-radius: 14px;
            color: {colours['text']};
            padding: 8px 10px;
            selection-background-color: {accent};
            selection-color: #ffffff;
        }}
        QMainWindow#WidgetsManagerWindow QTextEdit {{
            padding: 10px 12px;
        }}
        QMainWindow#WidgetsManagerWindow QComboBox QAbstractItemView {{
            background-color: {colours['input_bg']};
            border: 1px solid {colours['input_border']};
            color: {colours['text']};
            selection-background-color: {accent};
            selection-color: #ffffff;
            outline: 0;
        }}
        QMainWindow#WidgetsManagerWindow QListWidget {{
            background-color: {colours['input_bg']};
            border: 1px solid {colours['input_border']};
            border-radius: 14px;
            color: {colours['text']};
            outline: 0;
            selection-background-color: transparent;
        }}
        QMainWindow#WidgetsManagerWindow QListWidget#WidgetsList,
        QMainWindow#WidgetsManagerWindow QListWidget#ShortcutsList {{
            padding: 8px;
        }}
        QMainWindow#WidgetsManagerWindow QListWidget#WidgetsList::item {{
            border: 0px;
            background-color: transparent;
            padding: 0px;
            margin: 0px;
        }}
        QMainWindow#WidgetsManagerWindow QListWidget#WidgetsList::item:selected,
        QMainWindow#WidgetsManagerWindow QListWidget#WidgetsList::item:hover {{
            background-color: transparent;
        }}
        QMainWindow#WidgetsManagerWindow QListWidget::item {{
            min-height: 34px;
            margin: 3px 0px;
            padding: 10px 12px;
            border-radius: 12px;
        }}
        QMainWindow#WidgetsManagerWindow QListWidget::item:hover {{
            background-color: {colours['item_hover']};
        }}
        QMainWindow#WidgetsManagerWindow QListWidget::item:selected {{
            background-color: {accent};
            color: #ffffff;
        }}
        QMainWindow#WidgetsManagerWindow QFrame#WidgetBrowserRow {{
            background-color: {colours['item_bg']};
            border: 1px solid {colours['input_border']};
            border-radius: 14px;
        }}
        QMainWindow#WidgetsManagerWindow QFrame#WidgetBrowserRow:hover {{
            background-color: {colours['item_hover']};
            border: 1px solid {colours['checkbox_border']};
        }}
        QMainWindow#WidgetsManagerWindow QFrame#WidgetBrowserRow[selected="true"] {{
            background-color: {colours['item_selected']};
            border: 1px solid {accent};
        }}
        QMainWindow#WidgetsManagerWindow QFrame#WidgetBrowserRow[enabledState="false"] {{
            background-color: {colours['item_disabled']};
        }}
        QMainWindow#WidgetsManagerWindow QLabel#WidgetBrowserIcon {{
            background-color: {colours['button_bg']};
            border: 1px solid {colours['input_border']};
            border-radius: 10px;
        }}
        QMainWindow#WidgetsManagerWindow QLabel#WidgetBrowserTitle {{
            color: {colours['title']};
            font-size: {secondary}px;
            font-weight: 800;
        }}
        QMainWindow#WidgetsManagerWindow QLabel#WidgetBrowserSummary {{
            color: {colours['muted']};
            font-size: {small}px;
            font-weight: 600;
        }}
        QMainWindow#WidgetsManagerWindow QPushButton#WidgetToggleButton {{
            background-color: {colours['pill_off_bg']};
            border: 1px solid {colours['checkbox_border']};
            border-radius: 15px;
            color: {colours['pill_off_text']};
            font-size: {small}px;
            font-weight: 900;
            min-width: {scaled_font_px(60, zoom_percent, 52)}px;
            max-width: {scaled_font_px(60, zoom_percent, 52)}px;
            min-height: {scaled_font_px(32, zoom_percent, 28)}px;
            max-height: {scaled_font_px(32, zoom_percent, 28)}px;
            margin: 0px;
            padding: 0px;
            text-align: center;
        }}
        QMainWindow#WidgetsManagerWindow QPushButton#WidgetToggleButton[enabledState="true"] {{
            background-color: {colours['pill_on_bg']};
            border: 1px solid {colours['pill_on_bg']};
            color: #ffffff;
        }}
        QMenu#ContextMenu {{
            background-color: {colours['menu_bg']};
            border: 1px solid {colours['menu_border']};
            border-radius: 12px;
            padding: 6px;
            color: {colours['text']};
        }}
        QMenu#ContextMenu::item {{
            background-color: transparent;
            border-radius: 8px;
            color: {colours['text']};
            padding: 8px 28px 8px 28px;
            min-height: 24px;
        }}
        QMenu#ContextMenu::item:selected {{
            background-color: {colours['menu_hover']};
            color: {colours['title']};
        }}
        QMenu#ContextMenu::item:disabled {{
            color: {colours['muted']};
        }}
        QMenu#ContextMenu::separator {{
            height: 1px;
            background-color: {colours['menu_border']};
            margin: 6px 8px;
        }}
        QMainWindow#WidgetsManagerWindow QLineEdit:focus,
        QMainWindow#WidgetsManagerWindow QComboBox:focus,
        QMainWindow#WidgetsManagerWindow QSpinBox:focus,
        QMainWindow#WidgetsManagerWindow QTextEdit:focus,
        QMainWindow#WidgetsManagerWindow QListWidget:focus {{
            border: 1px solid {accent};
        }}
        QMainWindow#WidgetsManagerWindow QScrollArea,
        QMainWindow#WidgetsManagerWindow QScrollArea QWidget,
        QMainWindow#WidgetsManagerWindow QAbstractScrollArea,
        QMainWindow#WidgetsManagerWindow QAbstractScrollArea::viewport,
        QMainWindow#WidgetsManagerWindow QListWidget::viewport,
        QMainWindow#WidgetsManagerWindow QWidget#WidgetsInspectorHost,
        QMainWindow#WidgetsManagerWindow QScrollArea > QWidget > QWidget {{
            background-color: transparent;
        }}
        QMainWindow#WidgetsManagerWindow QPushButton#SmallButton {{
            background-color: {colours['button_bg']};
            border: 1px solid {colours['input_border']};
            border-radius: 12px;
            color: {colours['text']};
            padding: 10px 14px;
            font-size: {secondary}px;
            font-weight: 700;
        }}
        QMainWindow#WidgetsManagerWindow QPushButton#SmallButton:hover {{
            background-color: {colours['button_hover']};
            border: 1px solid {colours['checkbox_border']};
        }}
        QMainWindow#WidgetsManagerWindow QPushButton#SmallButton:pressed {{
            background-color: {colours['button_pressed']};
        }}
        QMainWindow#WidgetsManagerWindow QCheckBox {{
            spacing: 10px;
            color: {colours['text']};
            font-size: {base}px;
            font-weight: 600;
        }}
        QMainWindow#WidgetsManagerWindow QCheckBox::indicator {{
            width: {scaled_font_px(18, zoom_percent, 14)}px;
            height: {scaled_font_px(18, zoom_percent, 14)}px;
            border-radius: {scaled_font_px(6, zoom_percent, 4)}px;
            border: 1px solid {colours['checkbox_border']};
            background-color: {colours['checkbox_bg']};
        }}
        QMainWindow#WidgetsManagerWindow QCheckBox::indicator:checked {{
            background-color: {accent};
            border: 1px solid {accent};
        }}
        QMainWindow#WidgetsManagerWindow QSlider::groove:horizontal {{
            height: {scaled_font_px(8, zoom_percent, 6)}px;
            border-radius: {scaled_font_px(4, zoom_percent, 3)}px;
            border: 0px;
            background-color: {colours['slider_groove']};
        }}
        QMainWindow#WidgetsManagerWindow QSlider::sub-page:horizontal {{
            border-radius: {scaled_font_px(4, zoom_percent, 3)}px;
            border: 0px;
            background-color: {accent};
        }}
        QMainWindow#WidgetsManagerWindow QSlider::add-page:horizontal {{
            border-radius: {scaled_font_px(4, zoom_percent, 3)}px;
            border: 0px;
            background-color: {colours['slider_groove']};
        }}
        QMainWindow#WidgetsManagerWindow QSlider::handle:horizontal {{
            width: {scaled_font_px(18, zoom_percent, 14)}px;
            margin: {-scaled_font_px(5, zoom_percent, 4)}px 0;
            border-radius: {scaled_font_px(9, zoom_percent, 7)}px;
            background-color: {colours['slider_handle']};
            border: 1px solid {colours['slider_handle_border']};
        }}
        """

    def apply_theme_styling(self):
        self.setStyleSheet(self.build_manager_stylesheet())
        self.apply_responsive_metrics()

    def context_menu_stylesheet(self):
        return widget_editor_popup_stylesheet(self.manager)

    def install_themed_combo_popups(self, *combos):
        style = self.context_menu_stylesheet()
        for combo in combos:
            combo.view().setObjectName("ContextMenu")
            combo.view().setStyleSheet(style)

    def install_themed_text_context_menu(self, *widgets):
        for widget in widgets:
            widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            widget.customContextMenuRequested.connect(
                lambda pos, editor=widget: self.open_themed_text_context_menu(editor, pos)
            )

    def open_themed_text_context_menu(self, editor, pos):
        menu = editor.createStandardContextMenu()
        menu.setObjectName("ContextMenu")
        menu.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        menu.setStyleSheet(self.context_menu_stylesheet())
        menu.exec(editor.mapToGlobal(pos))
        menu.deleteLater()

    def cache_note_editor_image(self, image):
        widget = self.current_widget()
        if not widget:
            return ""
        return self.manager.cache_note_image(widget.get("id", ""), image)

    def prepare_editor_dialog(self, dialog):
        dialog.setStyleSheet(self.context_menu_stylesheet())
        for combo in dialog.findChildren(QComboBox):
            combo.view().setObjectName("ContextMenu")
            combo.view().setStyleSheet(self.context_menu_stylesheet())
        for editor in dialog.findChildren(QLineEdit):
            self.install_themed_text_context_menu(editor)
        for editor in dialog.findChildren(QTextEdit):
            self.install_themed_text_context_menu(editor)
        return dialog

    def form_row(self, label_text, widget):
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
        layout.addWidget(self.form_row(left_label, left_widget))
        layout.addWidget(self.form_row(right_label, right_widget))
        return wrapper

    def current_widget(self):
        if not self.selected_widget_id:
            return None
        return self.manager.get_widget(self.selected_widget_id)

    def queue_live_update(self, *_args):
        if self._loading:
            return
        self.live_status_label.setText("Saving...")
        self._debounce_timer.start(220)

    def force_save_now(self):
        self._debounce_timer.stop()
        self.apply_live_changes()

    def refresh_widget_list_labels(self):
        selected_id = self.selected_widget_id
        for row in range(self.widget_list.count()):
            item = self.widget_list.item(row)
            widget_id = item.data(Qt.ItemDataRole.UserRole)
            widget = self.manager.get_widget(widget_id)
            if widget:
                summary = self.manager.template_summary(widget)
                item.setToolTip(f"{widget.get('template_type', TEMPLATE_ASSIGNMENT)}\n{summary}")
                row_widget = self.widget_list.itemWidget(item)
                if isinstance(row_widget, WidgetBrowserRow):
                    row_widget.update_from_widget(widget, selected=widget_id == selected_id)
                    item.setSizeHint(row_widget.sizeHint())
                else:
                    status = "ON" if widget.get("enabled") else "OFF"
                    item.setText(f"{widget['name']} [{status}]")
                item.setToolTip(f"{widget.get('template_type', TEMPLATE_ASSIGNMENT)}\n{summary}")

    def reload_from_manager(self, keep_selection=False):
        selected_widget_id = self.selected_widget_id if keep_selection else None
        self._loading = True
        self.widget_list.clear()
        self._row_widgets = {}
        for widget in self.manager.widgets:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, widget["id"])
            row_widget = WidgetBrowserRow(self.manager, widget, self.widget_list)
            row_widget.selectedRequested.connect(self.select_widget_by_id)
            row_widget.toggleRequested.connect(self.toggle_widget_enabled)
            item.setSizeHint(row_widget.sizeHint())
            self.widget_list.addItem(item)
            self.widget_list.setItemWidget(item, row_widget)
            self._row_widgets[widget["id"]] = row_widget
            if widget["id"] == selected_widget_id:
                self.widget_list.setCurrentItem(item)
        self.refresh_widget_list_labels()
        if self.widget_list.currentItem() is None and self.widget_list.count():
            self.widget_list.setCurrentRow(0)
        self._loading = False
        self.apply_responsive_metrics()
        if self.widget_list.currentItem() is not None:
            self.on_widget_selected(self.widget_list.currentItem(), None)
        else:
            self.selected_widget_id = None
            self.preview_canvas.set_definition({})
            self.refresh_action_states()

    def select_widget_by_id(self, widget_id):
        if not widget_id:
            return
        for row in range(self.widget_list.count()):
            item = self.widget_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == widget_id:
                self.widget_list.setCurrentItem(item)
                return

    def toggle_widget_enabled(self, widget_id=None):
        if self._loading:
            return
        widget = self.manager.get_widget(widget_id or self.selected_widget_id)
        if not widget:
            return

        widget["enabled"] = not bool(widget.get("enabled"))
        normalized = self.manager.apply_widget_changes(widget["id"], refresh_manager=False)
        if normalized is None:
            return

        if self.selected_widget_id == normalized["id"]:
            self._loading = True
            self.widget_enabled.setChecked(bool(normalized.get("enabled")))
            self._loading = False
            self.preview_canvas.set_definition(normalized)
        self.refresh_widget_list_labels()
        self.live_status_label.setText("Saved live")

    def on_widget_selected(self, current, previous):
        if self._loading:
            return
        self.selected_widget_id = current.data(Qt.ItemDataRole.UserRole) if current else None
        widget = self.current_widget()
        self._loading = True
        if not widget:
            self.preview_canvas.set_definition({})
            self._loading = False
            self.refresh_action_states()
            return

        config = dict(widget.get("template_config") or {})
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
        template_type = widget.get("template_type", TEMPLATE_ASSIGNMENT)
        self.template_type.setCurrentText(template_type)
        self.assignment_title.setText(config.get("title", "Assignment details"))
        self.populate_assignment_combo(config)
        self.assignment_show_title.setChecked(bool(config.get("show_assignment_title", True)))
        self.assignment_show_course.setChecked(bool(config.get("show_course_label", True)))
        self.assignment_show_due.setChecked(bool(config.get("show_due_label", True)))

        self.shortcuts_title.setText(config.get("title", "Quick Links"))
        self.populate_shortcuts_list(config.get("items", []))

        self.note_title.setText(config.get("title", "Pinned Note"))
        set_note_editor_content(self.note_text, config)
        self.note_inline_edit.setChecked(bool(config.get("allow_inline_edit", False)))

        self.preview_canvas.set_definition(widget)
        self.update_template_visibility(template_type)
        self._loading = False
        self.refresh_action_states()
        self.refresh_widget_list_labels()
        self.live_status_label.setText("Live updates on")

    def populate_assignment_combo(self, config):
        self.assignment_target.clear()
        bindings = self.manager.all_assignment_bindings()
        if not bindings:
            self.assignment_target.addItem("No assignments available")
            return
        selected = (
            str(config.get("user_id") or ""),
            str(config.get("course_id") or ""),
            str(config.get("assignment_id") or ""),
        )
        current_index = 0
        for index, binding in enumerate(bindings):
            self.assignment_target.addItem(f"{binding['label']}  |  {binding['due_display']}")
            self.assignment_target.setItemData(index, (binding["user_id"], binding["course_id"], binding["assignment_id"]), Qt.ItemDataRole.UserRole)
            if (binding["user_id"], binding["course_id"], binding["assignment_id"]) == selected:
                current_index = index
        self.assignment_target.setCurrentIndex(current_index)

    def populate_shortcuts_list(self, items):
        self.shortcuts_list.clear()
        for item in items or []:
            self.shortcuts_list.addItem(f"{item.get('label', 'Shortcut')} -> {self.manager.describe_action_target(item.get('target'))}")
        has_items = self.shortcuts_list.count() > 0
        self.shortcut_edit_btn.setEnabled(has_items)
        self.shortcut_delete_btn.setEnabled(has_items)

    def update_template_visibility(self, template_type):
        self.assignment_group.setVisible(template_type == TEMPLATE_ASSIGNMENT)
        self.shortcuts_group.setVisible(template_type == TEMPLATE_SHORTCUTS)
        self.note_group.setVisible(template_type == TEMPLATE_NOTE)

    def write_widget_state(self, widget):
        widget["name"] = self.widget_name.text().strip() or "Widget"
        widget["position"] = {"x": self.widget_x.value(), "y": self.widget_y.value()}
        widget["size"] = {"width": self.widget_width.value(), "height": self.widget_height.value()}
        widget["theme_mode"] = self.widget_theme.currentText()
        widget["display_mode"] = self.widget_display_mode.currentText()
        widget["opacity"] = self.widget_opacity.value() / 100.0
        widget["enabled"] = self.widget_enabled.isChecked()
        widget["locked"] = self.widget_locked.isChecked()

        template_type = self.template_type.currentText()
        widget["template_type"] = template_type
        config = dict(widget.get("template_config") or {})
        if template_type == TEMPLATE_ASSIGNMENT:
            payload = self.assignment_target.currentData(Qt.ItemDataRole.UserRole)
            config = {
                "title": self.assignment_title.text().strip() or "Assignment details",
                "user_id": payload[0] if payload else "",
                "course_id": payload[1] if payload else "",
                "assignment_id": payload[2] if payload else "",
                "show_assignment_title": self.assignment_show_title.isChecked(),
                "show_course_label": self.assignment_show_course.isChecked(),
                "show_due_label": self.assignment_show_due.isChecked(),
            }
        elif template_type == TEMPLATE_SHORTCUTS:
            config = {
                "title": self.shortcuts_title.text().strip() or "Quick Links",
                "items": list(config.get("items", [])) or [default_shortcut_item()],
            }
        else:
            note_text, note_format = note_editor_content(
                self.note_text,
                prefer_html=note_content_is_html(config),
            )
            config = {
                "title": self.note_title.text().strip() or "Pinned Note",
                "text": note_text.strip(),
                "text_format": note_format,
                "allow_inline_edit": self.note_inline_edit.isChecked(),
            }
        widget["template_config"] = config

    def apply_live_changes(self, *_args):
        if self._loading:
            return
        widget = self.current_widget()
        if not widget:
            return
        self.write_widget_state(widget)
        normalized = self.manager.apply_widget_changes(widget["id"], refresh_manager=False)
        if normalized is None:
            return
        self.refresh_widget_list_labels()
        self.preview_canvas.set_definition(normalized)
        self.update_template_visibility(normalized.get("template_type", TEMPLATE_ASSIGNMENT))
        self.live_status_label.setText("Saved live")

    def create_widget(self):
        dialog = ThemedFormDialog(
            self,
            title="Create Widget",
            subtitle="Choose a template for the new desktop widget.",
            fields=[
                FormField(
                    "preset",
                    "Widget template",
                    kind="combo",
                    default="Assignment Countdown",
                    options=("Assignment Countdown", "Shortcut Panel", "Note Widget"),
                )
            ],
            accept_text="Create Widget",
        )
        self.prepare_editor_dialog(dialog)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not values:
            return
        widget = self.manager.add_widget_from_preset(values["preset"])
        self.reload_from_manager()
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
        for row in range(self.widget_list.count()):
            item = self.widget_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == duplicated["id"]:
                self.widget_list.setCurrentItem(item)
                break

    def rename_widget(self):
        widget = self.current_widget()
        if not widget:
            return
        dialog = ThemedFormDialog(
            self,
            title="Rename Widget",
            subtitle="Choose a clearer display name for this widget.",
            fields=[FormField("name", "Widget name", default=widget.get("name", "Widget"), required=True)],
            accept_text="Rename",
        )
        self.prepare_editor_dialog(dialog)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not values:
            return
        widget["name"] = values["name"].strip() or "Widget"
        self.manager.apply_widget_changes(widget["id"], refresh_manager=False)
        self.reload_from_manager(keep_selection=True)

    def delete_widget(self):
        widget = self.current_widget()
        if not widget:
            return
        dialog = ThemedFormDialog(
            self,
            title="Delete Widget",
            subtitle=f"Delete '{widget.get('name', 'Widget')}'? This removes the widget from the editor and desktop.",
            accept_text="Delete",
            cancel_text="Cancel",
            minimum_width=500,
        )
        self.prepare_editor_dialog(dialog)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.manager.delete_widget(widget["id"])
        self.reload_from_manager()

    def current_shortcuts(self):
        widget = self.current_widget()
        if not widget:
            return []
        return widget.setdefault("template_config", {}).setdefault("items", [default_shortcut_item()])

    def add_shortcut_action(self):
        widget = self.current_widget()
        if not widget or widget.get("template_type") != TEMPLATE_SHORTCUTS:
            return
        dialog = ShortcutActionDialog(self.manager, parent=self)
        self.prepare_editor_dialog(dialog)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.result_value():
            return
        self.current_shortcuts().append(dialog.result_value())
        self.apply_live_changes()
        self.populate_shortcuts_list(self.current_shortcuts())

    def edit_shortcut_action(self):
        widget = self.current_widget()
        if not widget or widget.get("template_type") != TEMPLATE_SHORTCUTS:
            return
        row = self.shortcuts_list.currentRow()
        items = self.current_shortcuts()
        if row < 0 or row >= len(items):
            return
        dialog = ShortcutActionDialog(self.manager, action_item=items[row], parent=self)
        self.prepare_editor_dialog(dialog)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.result_value():
            return
        items[row] = dialog.result_value()
        self.apply_live_changes()
        self.populate_shortcuts_list(items)

    def delete_shortcut_action(self):
        widget = self.current_widget()
        if not widget or widget.get("template_type") != TEMPLATE_SHORTCUTS:
            return
        row = self.shortcuts_list.currentRow()
        items = self.current_shortcuts()
        if row < 0 or row >= len(items):
            return
        items.pop(row)
        if not items:
            items.append(default_shortcut_item())
        self.apply_live_changes()
        self.populate_shortcuts_list(items)

    def refresh_action_states(self):
        has_widget = self.current_widget() is not None
        for control in (
            self.duplicate_widget_btn,
            self.rename_widget_btn,
            self.delete_widget_btn,
            self.save_now_btn,
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
            self.template_type,
            self.assignment_title,
            self.assignment_target,
            self.assignment_show_title,
            self.assignment_show_course,
            self.assignment_show_due,
            self.shortcuts_title,
            self.shortcuts_list,
            self.shortcut_add_btn,
            self.shortcut_edit_btn,
            self.shortcut_delete_btn,
            self.note_title,
            self.note_inline_edit,
            self.note_text,
        ):
            control.setEnabled(has_widget)

    def open_widget_list_context_menu(self, pos):
        item = self.widget_list.itemAt(pos)
        if item:
            self.widget_list.setCurrentItem(item)
        menu = AppContextMenu(self)
        accent = self.manager.main_window.app_settings.get_accent_color()
        theme = self.manager.main_window.effective_theme_mode()
        menu.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        menu.setStyleSheet(build_context_menu_styles(theme, accent))
        add_menu_action(menu, "Add Widget", "plus", self.create_widget, shortcut="Ctrl+N")
        widget = self.current_widget()
        if widget:
            toggle_label = "Disable Widget" if widget.get("enabled") else "Enable Widget"
            toggle_icon = "ban" if widget.get("enabled") else "check"
            add_menu_action(menu, toggle_label, toggle_icon, lambda: self.toggle_widget_enabled(widget["id"]))
            menu.add_separator_if_needed()
            add_menu_action(menu, "Duplicate Widget", "copy", self.duplicate_widget, shortcut="Ctrl+D")
            add_menu_action(menu, "Rename Widget", "edit", self.rename_widget, shortcut="F2")
            add_menu_action(menu, "Delete Widget", "delete", self.delete_widget, shortcut="Delete")
        menu.exec(self.widget_list.mapToGlobal(pos))

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
        if modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_D and not editing_focus:
            self.duplicate_widget()
            return
        if key == Qt.Key.Key_F2 and not editing_focus:
            self.rename_widget()
            return
        if key == Qt.Key.Key_Delete and not editing_focus and self.widget_list.hasFocus():
            self.delete_widget()
            return
        super().keyPressEvent(event)
