from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QEvent, Qt, QSize
from core.validation import DEFAULT_CANVAS_BASE_URL, ValidationError, validate_user_payload
from services.app_logging import log_user_visible_error
from ui.icons import load_icon
from ui.keyboard_shortcuts import shortcut_text_from_key_event


def zoomed_px(parent, value, minimum=1):
    zoom_percent = getattr(parent, "ui_zoom_percent", None)
    if zoom_percent is None and parent is not None:
        zoom_percent = getattr(getattr(parent, "main_window", None), "ui_zoom_percent", 100)
    try:
        scale = float(zoom_percent or 100) / 100.0
    except (TypeError, ValueError):
        scale = 1.0
    return max(minimum, int(round(value * scale)))


class TextEditorWindow(QMainWindow):
    """Small in-app editor for simple text-like files.

    The editor writes through a callback supplied by MainWindow so saves can
    participate in the app's undo/history system.
    """

    def __init__(self, path, on_save, parent=None):
        super().__init__(parent)
        self.path = Path(path)
        self.on_save = on_save
        self.saved_text = self.read_initial_text()

        self.setWindowTitle(f"Text Editor — {self.path.name}")
        self.resize(980, 720)
        self.setMinimumSize(zoomed_px(parent, 820, 720), zoomed_px(parent, 560, 420))
        if parent:
            self.setStyleSheet(parent.styleSheet())

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(zoomed_px(parent, 18), zoomed_px(parent, 18), zoomed_px(parent, 18), zoomed_px(parent, 18))
        layout.setSpacing(zoomed_px(parent, 12))

        header = QFrame()
        header.setObjectName("ContentPanel")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(zoomed_px(parent, 16), zoomed_px(parent, 14), zoomed_px(parent, 16), zoomed_px(parent, 14))
        header_layout.setSpacing(zoomed_px(parent, 6))

        title = QLabel(self.path.name)
        title.setObjectName("CardTitle")
        title.setWordWrap(True)

        location = QLabel(str(self.path))
        location.setObjectName("CardMeta")
        location.setWordWrap(True)
        location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        header_layout.addWidget(title)
        header_layout.addWidget(location)

        editor_panel = QFrame()
        editor_panel.setObjectName("ContentPanel")
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.setContentsMargins(zoomed_px(parent, 12), zoomed_px(parent, 12), zoomed_px(parent, 12), zoomed_px(parent, 12))
        editor_layout.setSpacing(zoomed_px(parent, 10))

        self.editor = QPlainTextEdit()
        self.editor.setObjectName("CodePreview")
        self.editor.setPlainText(self.saved_text)
        self.editor.textChanged.connect(self.update_dirty_state)
        editor_layout.addWidget(self.editor)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(zoomed_px(parent, 10))

        self.status_label = QLabel("Saved")
        self.status_label.setObjectName("CardMeta")

        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("SmallButton")
        self.save_button.clicked.connect(self.save)

        save_close_button = QPushButton("Save & Close")
        save_close_button.setObjectName("SmallButton")
        save_close_button.clicked.connect(self.save_and_close)

        close_button = QPushButton("Close")
        close_button.setObjectName("SmallButton")
        close_button.clicked.connect(self.close)

        footer.addWidget(self.status_label)
        footer.addStretch()
        footer.addWidget(self.save_button)
        footer.addWidget(save_close_button)
        footer.addWidget(close_button)

        layout.addWidget(header)
        layout.addWidget(editor_panel, 1)
        layout.addLayout(footer)
        self.setCentralWidget(container)
        self.editor.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress and self.handle_shortcut_key(event):
            return True

        return super().eventFilter(watched, event)

    def keyPressEvent(self, event):
        if self.handle_shortcut_key(event):
            event.accept()
            return

        super().keyPressEvent(event)

    def handle_shortcut_key(self, event):
        if shortcut_text_from_key_event(event) != "Ctrl+S":
            return False

        self.save()
        event.accept()
        return True

    def read_initial_text(self):
        try:
            return self.path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""

    def is_dirty(self):
        return self.editor.toPlainText() != self.saved_text

    def update_dirty_state(self):
        self.status_label.setText("Unsaved changes" if self.is_dirty() else "Saved")

    def save(self):
        new_text = self.editor.toPlainText()
        if new_text == self.saved_text:
            self.update_dirty_state()
            return True

        try:
            if self.on_save(self.path, new_text):
                self.saved_text = new_text
                self.update_dirty_state()
                return True
        except Exception as error:
            message = "The file could not be saved."
            parent = self.parent()
            if parent is not None and hasattr(parent, "show_user_warning"):
                parent.show_user_warning("Save Failed", message, error=error, context={"path": self.path})
            else:
                log_user_visible_error("Save Failed", message, error=error, context={"path": self.path})
                QMessageBox.warning(self, "Save Failed", message)

        return False

    def save_and_close(self):
        if self.save():
            self.close()

    def closeEvent(self, event):
        if not self.is_dirty():
            event.accept()
            return

        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "Save changes before closing?",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No |
            QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Cancel:
            event.ignore()
            return

        if reply == QMessageBox.StandardButton.Yes and not self.save():
            event.ignore()
            return

        event.accept()


class CreateUserDialog(QDialog):
    """Create/edit dialog for local user and Canvas connection details."""

    def __init__(self, parent=None, required=False, user=None):
        super().__init__(parent)

        self.user = user or {}
        self.editing = bool(user)

        self.setWindowTitle("Edit User / Canvas Settings" if self.editing else "Create New User")
        self.setModal(True)
        self.setMinimumWidth(zoomed_px(parent, 560, 420))

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(zoomed_px(parent, 22), zoomed_px(parent, 22), zoomed_px(parent, 22), zoomed_px(parent, 22))
        outer_layout.setSpacing(zoomed_px(parent, 14))

        title = QLabel("Edit user and Canvas settings" if self.editing else "Create your ZJX-LMS user")
        title.setObjectName("CardTitle")
        title.setWordWrap(True)

        description = QLabel(
            "The Canvas token is stored in this user's local profile.json/users.json. "
            "ZJX LMS uses it only when you manually run a Canvas sync."
        )
        description.setObjectName("CardBody")
        description.setWordWrap(True)

        form = QFormLayout()
        form.setContentsMargins(0, 6, 0, 0)
        form.setHorizontalSpacing(zoomed_px(parent, 14))
        form.setVerticalSpacing(zoomed_px(parent, 12))

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. Harry")
        self.name_input.setText(self.user.get("name", ""))

        self.university_input = QLineEdit()
        self.university_input.setPlaceholderText("e.g. UNSW / USYD / UTS")
        self.university_input.setText(self.user.get("university", ""))

        self.canvas_url_input = QLineEdit()
        self.canvas_url_input.setPlaceholderText("https://canvas.sydney.edu.au")
        self.canvas_url_input.setText(self.user.get("canvas_base_url") or DEFAULT_CANVAS_BASE_URL)

        self.canvas_token_input = QLineEdit()
        self.canvas_token_input.setPlaceholderText("Canvas access token")
        self.canvas_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.canvas_token_input.setText(self.user.get("canvas_access_token", ""))

        form.addRow("Name", self.name_input)
        form.addRow("University", self.university_input)
        form.addRow("Canvas URL", self.canvas_url_input)
        form.addRow("Canvas token", self.canvas_token_input)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Save Changes" if self.editing else "Create User"
        )
        self.buttons.accepted.connect(self.validate_and_accept)
        self.buttons.rejected.connect(self.reject)

        if required and not self.editing:
            self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Skip for now")

        outer_layout.addWidget(title)
        outer_layout.addWidget(description)
        outer_layout.addLayout(form)
        outer_layout.addWidget(self.buttons)

        self.name_input.setFocus()

    def validate_and_accept(self):
        try:
            validate_user_payload(self.user_payload())
        except ValidationError as error:
            QMessageBox.warning(self, "Invalid User Details", str(error))
            return

        self.accept()

    def user_payload(self):
        return {
            "name": self.name_input.text().strip(),
            "university": self.university_input.text().strip(),
            "canvas_base_url": self.canvas_url_input.text().strip(),
            "canvas_access_token": self.canvas_token_input.text().strip(),
        }




class CourseSyncPreferencesDialog(QDialog):
    """Choose Canvas courses for blacklist/favourite sync preferences."""

    def __init__(self, parent=None, *, mode="blacklist", courses=None, selected_ids=None, user_name=""):
        super().__init__(parent)
        self.mode = mode
        self.courses = courses or []
        self.selected_ids = {str(item) for item in (selected_ids or [])}

        if mode == "favourites":
            window_title = "Favourite Canvas Courses"
            heading = "Favourite Canvas courses"
            description = (
                "Favourite courses always stay at the top of the Courses section. "
                "This does not change Canvas; it only affects the local ZJX LMS view."
            )
            checkbox_hint = "Tick the Canvas courses you want pinned to the top."
        else:
            window_title = "Canvas Course Blacklist"
            heading = "Blacklist Canvas courses"
            description = (
                "Blacklisted Canvas courses are skipped during the next sync and hidden from the active Courses list. "
                "Use this to stop old or irrelevant Canvas shells from flooding the app."
            )
            checkbox_hint = "Tick the Canvas courses you do not want to sync."

        self.setWindowTitle(window_title)
        self.setModal(True)
        self.resize(720, 620)
        self.setMinimumSize(zoomed_px(parent, 620, 480), zoomed_px(parent, 480, 360))

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(zoomed_px(parent, 22), zoomed_px(parent, 22), zoomed_px(parent, 22), zoomed_px(parent, 22))
        outer_layout.setSpacing(zoomed_px(parent, 14))

        header = QFrame()
        header.setObjectName("ContentPanel")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(zoomed_px(parent, 18), zoomed_px(parent, 16), zoomed_px(parent, 18), zoomed_px(parent, 16))
        header_layout.setSpacing(zoomed_px(parent, 8))

        title = QLabel(heading)
        title.setObjectName("PageTitle")
        title.setWordWrap(True)

        subtitle = QLabel("Canvas sync preferences" + (f" for {user_name}" if user_name else ""))
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)

        body = QLabel(description)
        body.setObjectName("CardBody")
        body.setWordWrap(True)

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addWidget(body)

        hint = QLabel(checkbox_hint)
        hint.setObjectName("CardMeta")
        hint.setWordWrap(True)

        self.course_list = QListWidget()
        self.course_list.setObjectName("CoursePreferenceList")
        self.course_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        if self.courses:
            for course in self.courses:
                self.add_course_row(course)
        else:
            empty = QListWidgetItem("No Canvas courses available yet. Sync once, or check that this user has a Canvas token.")
            empty.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.course_list.addItem(empty)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(zoomed_px(parent, 10))

        select_all = QPushButton("Select All")
        select_all.setObjectName("SmallButton")
        select_all.clicked.connect(lambda: self.set_all_checked(True))

        clear_all = QPushButton("Clear All")
        clear_all.setObjectName("SmallButton")
        clear_all.clicked.connect(lambda: self.set_all_checked(False))

        controls.addWidget(select_all)
        controls.addWidget(clear_all)
        controls.addStretch()

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Save Preferences")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        outer_layout.addWidget(header)
        outer_layout.addWidget(hint)
        outer_layout.addWidget(self.course_list, 1)
        outer_layout.addLayout(controls)
        outer_layout.addWidget(self.buttons)

    def add_course_row(self, course):
        canvas_id = str(course.get("canvas_id") or course.get("id") or "").strip()
        title = str(course.get("code") or course.get("name") or f"Canvas course {canvas_id}").strip()
        subtitle = str(course.get("name") or "").strip()
        source_note = "Already imported" if course.get("imported") else "Available from Canvas"

        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, canvas_id)
        item.setSizeHint(QSize(0, zoomed_px(self.parent(), 74, 56)))

        widget = QFrame()
        widget.setObjectName("ContentPanel")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(zoomed_px(self.parent(), 14), zoomed_px(self.parent(), 10), zoomed_px(self.parent(), 14), zoomed_px(self.parent(), 10))
        layout.setSpacing(zoomed_px(self.parent(), 12))

        checkbox = QCheckBox()
        checkbox.setChecked(canvas_id in self.selected_ids)
        checkbox.setProperty("canvas_id", canvas_id)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(zoomed_px(self.parent(), 4))

        label = QLabel(title)
        label.setObjectName("CardTitle")
        label.setWordWrap(True)

        meta_parts = [part for part in [subtitle if subtitle != title else "", source_note, f"Canvas ID: {canvas_id}" if canvas_id else ""] if part]
        meta = QLabel(" • ".join(meta_parts))
        meta.setObjectName("CardMeta")
        meta.setWordWrap(True)

        text_layout.addWidget(label)
        text_layout.addWidget(meta)

        layout.addWidget(checkbox)
        layout.addLayout(text_layout, 1)

        self.course_list.addItem(item)
        self.course_list.setItemWidget(item, widget)

    def set_all_checked(self, checked):
        for row in range(self.course_list.count()):
            item = self.course_list.item(row)
            widget = self.course_list.itemWidget(item)
            if not widget:
                continue
            checkbox = widget.findChild(QCheckBox)
            if checkbox:
                checkbox.setChecked(checked)

    def chosen_course_ids(self):
        selected = []
        for row in range(self.course_list.count()):
            item = self.course_list.item(row)
            widget = self.course_list.itemWidget(item)
            if not widget:
                continue
            checkbox = widget.findChild(QCheckBox)
            canvas_id = item.data(Qt.ItemDataRole.UserRole)
            if checkbox and checkbox.isChecked() and canvas_id:
                selected.append(str(canvas_id))
        return selected


class ExportVaultDialog(QDialog):
    """Choose the destination and user/course scope for a vault export."""

    def __init__(self, parent=None, *, vault):
        super().__init__(parent)
        self.vault = vault
        self._syncing_checks = False

        self.setObjectName("ThemedFormDialog")
        self.setWindowTitle("Export Vault Archive")
        self.setModal(True)
        self.resize(760, 680)
        self.setMinimumSize(zoomed_px(parent, 660, 520), zoomed_px(parent, 560, 420))
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        desktop = Path.home() / "Desktop"
        self.destination_path = desktop if desktop.exists() else Path.home()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(zoomed_px(parent, 18), zoomed_px(parent, 18), zoomed_px(parent, 18), zoomed_px(parent, 18))
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("DialogCard")
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(zoomed_px(parent, 22), zoomed_px(parent, 20), zoomed_px(parent, 22), zoomed_px(parent, 18))
        layout.setSpacing(zoomed_px(parent, 14))

        title = QLabel("Export Vault Archive")
        title.setObjectName("DialogTitle")
        title.setWordWrap(True)

        subtitle = QLabel("Choose which users and courses to include, then save a human-readable zip archive.")
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        path_field = QWidget()
        path_field.setObjectName("DialogField")
        path_layout = QVBoxLayout(path_field)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(zoomed_px(parent, 7))

        path_label = QLabel("Save location")
        path_label.setObjectName("FieldLabel")
        self.path_input = QLineEdit(str(self.destination_path))
        self.path_input.setObjectName("DialogInput")
        self.path_input.setReadOnly(True)

        browse_button = QPushButton("Browse")
        browse_button.setObjectName("SecondaryButton")
        browse_button.clicked.connect(self.choose_destination)

        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(zoomed_px(parent, 10))
        path_row.addWidget(self.path_input, 1)
        path_row.addWidget(browse_button)

        path_layout.addWidget(path_label)
        path_layout.addLayout(path_row)
        layout.addWidget(path_field)

        tree_header = QHBoxLayout()
        tree_header.setContentsMargins(0, 0, 0, 0)
        tree_header.setSpacing(zoomed_px(parent, 10))

        tree_label = QLabel("Vault content")
        tree_label.setObjectName("FieldLabel")

        select_all = QPushButton("Select All")
        select_all.setObjectName("SecondaryButton")
        select_all.clicked.connect(lambda: self.set_all_checked(True))

        clear_all = QPushButton("Clear All")
        clear_all.setObjectName("SecondaryButton")
        clear_all.clicked.connect(lambda: self.set_all_checked(False))

        tree_header.addWidget(tree_label)
        tree_header.addStretch()
        tree_header.addWidget(select_all)
        tree_header.addWidget(clear_all)
        layout.addLayout(tree_header)

        instruction = QLabel("Tick users, courses, or sections to include in the export.")
        instruction.setObjectName("ExportInstruction")
        instruction.setWordWrap(True)
        layout.addWidget(instruction)

        self.tree = QTreeWidget()
        self.tree.setObjectName("ExportVaultTree")
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tree.setIndentation(zoomed_px(parent, 22, 18))
        self.tree.setIconSize(QSize(zoomed_px(parent, 18, 16), zoomed_px(parent, 18, 16)))
        self.tree.setUniformRowHeights(False)
        self.tree.itemChanged.connect(self.handle_item_changed)
        layout.addWidget(self.tree, 1)

        summary_strip = QFrame()
        summary_strip.setObjectName("ExportSummaryStrip")
        summary_layout = QHBoxLayout(summary_strip)
        summary_layout.setContentsMargins(zoomed_px(parent, 14), zoomed_px(parent, 10), zoomed_px(parent, 14), zoomed_px(parent, 10))
        summary_layout.setSpacing(zoomed_px(parent, 10))
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("ExportSummary")
        self.summary_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_label, 1)
        layout.addWidget(summary_strip)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Start Export")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.populate_tree()
        self.refresh_state()

    def populate_tree(self):
        self._syncing_checks = True
        self.tree.clear()
        users = sorted(self.vault.get_users(), key=lambda item: item.get("name", "").lower())
        for user in users:
            user_id = user.get("id")
            courses = sorted(
                self.vault.get_courses(user_id),
                key=lambda item: (item.get("code", "").lower(), item.get("name", "").lower()),
            )
            user_item = QTreeWidgetItem([self.user_label(user, len(courses))])
            user_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "user", "user_id": user.get("id")})
            user_item.setFlags(user_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
            user_item.setCheckState(0, Qt.CheckState.Checked)
            self.prepare_tree_item(user_item, "user")
            self.tree.addTopLevelItem(user_item)

            for course in courses:
                general_count = self.resource_count(user_id, course.get("id"), None)
                assignments = sorted(
                    self.vault.get_assignments(user_id, course.get("id")),
                    key=lambda item: item.get("title", "").lower(),
                )
                assignment_counts = {
                    str(assignment.get("id")): self.resource_count(user_id, course.get("id"), assignment.get("id"))
                    for assignment in assignments
                }
                total_resources = general_count + sum(assignment_counts.values())
                label = self.course_label(course, total_resources, len(assignments) + 1)
                course_item = QTreeWidgetItem([label])
                course_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {"type": "course", "user_id": user.get("id"), "course_id": course.get("id")},
                )
                course_item.setFlags(
                    course_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate
                )
                course_item.setCheckState(0, Qt.CheckState.Checked)
                self.prepare_tree_item(course_item, "course")
                user_item.addChild(course_item)

                general_item = QTreeWidgetItem([self.general_label(general_count)])
                general_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {"type": "general", "user_id": user.get("id"), "course_id": course.get("id")},
                )
                general_item.setFlags(general_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                general_item.setCheckState(0, Qt.CheckState.Checked)
                self.prepare_tree_item(general_item, "general")
                course_item.addChild(general_item)

                for assignment in assignments:
                    assignment_item = QTreeWidgetItem(
                        [self.assignment_label(assignment, assignment_counts.get(str(assignment.get("id")), 0))]
                    )
                    assignment_item.setData(
                        0,
                        Qt.ItemDataRole.UserRole,
                        {
                            "type": "assignment",
                            "user_id": user.get("id"),
                            "course_id": course.get("id"),
                            "assignment_id": assignment.get("id"),
                        },
                    )
                    assignment_item.setFlags(assignment_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    assignment_item.setCheckState(0, Qt.CheckState.Checked)
                    self.prepare_tree_item(assignment_item, "assignment")
                    course_item.addChild(assignment_item)

            if not courses:
                empty = QTreeWidgetItem(["No courses available"])
                empty.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.prepare_tree_item(empty, "empty")
                user_item.addChild(empty)

            user_item.setExpanded(True)
            for child_index in range(user_item.childCount()):
                child = user_item.child(child_index)
                child.setExpanded(True)
        self._syncing_checks = False

    def prepare_tree_item(self, item, item_type):
        icon_name = {
            "user": "user",
            "course": "course",
            "general": "folder",
            "assignment": "assignment",
            "empty": "info",
        }.get(item_type, "file")
        item.setIcon(0, load_icon(icon_name))
        item.setSizeHint(0, QSize(0, zoomed_px(self.parent(), 42, 34)))

    def user_label(self, user, course_count):
        name = user.get("name") or user.get("id") or "Unnamed User"
        return f"{name} ({course_count} {'course' if course_count == 1 else 'courses'})"

    def course_label(self, course, resource_count=0, section_count=1):
        code = str(course.get("code") or course.get("id") or "Course").strip()
        name = str(course.get("name") or "").strip()
        label = code
        if name and name.lower() != code.lower():
            label = f"{code} - {name}"
        resource_word = "resource" if resource_count == 1 else "resources"
        section_word = "section" if section_count == 1 else "sections"
        return f"{label} ({resource_count} {resource_word} across {section_count} {section_word})"

    def general_label(self, resource_count):
        resource_word = "resource" if resource_count == 1 else "resources"
        return f"General Course Resources ({resource_count} {resource_word})"

    def assignment_label(self, assignment, resource_count):
        title = assignment.get("title") or assignment.get("id") or "Assignment"
        resource_word = "resource" if resource_count == 1 else "resources"
        return f"{title} ({resource_count} {resource_word})"

    def resource_count(self, user_id, course_id, assignment_id):
        return len(self.vault.load_resources(user_id, course_id, assignment_id))

    def choose_destination(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose Export Destination", str(self.destination_path))
        if not folder:
            return
        self.destination_path = Path(folder)
        self.path_input.setText(str(self.destination_path))
        self.refresh_state()

    def handle_item_changed(self, item, column):
        if self._syncing_checks:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        if data.get("type") in {"user", "course"} and item.checkState(0) != Qt.CheckState.PartiallyChecked:
            self._syncing_checks = True
            state = item.checkState(0)
            self._set_descendant_check_state(item, state)
            self._syncing_checks = False
        self.refresh_state()

    def _set_descendant_check_state(self, item, state):
        for child_index in range(item.childCount()):
            child = item.child(child_index)
            child_data = child.data(0, Qt.ItemDataRole.UserRole) or {}
            if child_data.get("type") in {"course", "general", "assignment"}:
                child.setCheckState(0, state)
            self._set_descendant_check_state(child, state)

    def set_all_checked(self, checked):
        self._syncing_checks = True
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.tree.topLevelItemCount()):
            user_item = self.tree.topLevelItem(row)
            user_item.setCheckState(0, state)
            self._set_descendant_check_state(user_item, state)
        self._syncing_checks = False
        self.refresh_state()

    def selected_course_ids_by_user(self):
        selected = {}
        for row in range(self.tree.topLevelItemCount()):
            user_item = self.tree.topLevelItem(row)
            user_data = user_item.data(0, Qt.ItemDataRole.UserRole) or {}
            user_id = user_data.get("user_id")
            if not user_id:
                continue
            for child_index in range(user_item.childCount()):
                child = user_item.child(child_index)
                data = child.data(0, Qt.ItemDataRole.UserRole) or {}
                if data.get("type") != "course":
                    continue
                course_id = data.get("course_id")
                if not course_id:
                    continue
                if self._course_has_selection(child):
                    selected.setdefault(str(user_id), set()).add(str(course_id))
        return selected

    def selected_general_course_ids_by_user(self):
        selected = {}
        for row in range(self.tree.topLevelItemCount()):
            user_item = self.tree.topLevelItem(row)
            user_data = user_item.data(0, Qt.ItemDataRole.UserRole) or {}
            user_id = user_data.get("user_id")
            if not user_id:
                continue
            for child_index in range(user_item.childCount()):
                course_item = user_item.child(child_index)
                course_data = course_item.data(0, Qt.ItemDataRole.UserRole) or {}
                if course_data.get("type") != "course":
                    continue
                course_id = course_data.get("course_id")
                if not course_id:
                    continue
                for section_index in range(course_item.childCount()):
                    section_item = course_item.child(section_index)
                    section_data = section_item.data(0, Qt.ItemDataRole.UserRole) or {}
                    if section_data.get("type") == "general" and section_item.checkState(0) == Qt.CheckState.Checked:
                        selected.setdefault(str(user_id), set()).add(str(course_id))
        return selected

    def selected_assignment_ids_by_course(self):
        selected = {}
        for row in range(self.tree.topLevelItemCount()):
            user_item = self.tree.topLevelItem(row)
            user_data = user_item.data(0, Qt.ItemDataRole.UserRole) or {}
            user_id = user_data.get("user_id")
            if not user_id:
                continue
            for child_index in range(user_item.childCount()):
                course_item = user_item.child(child_index)
                course_data = course_item.data(0, Qt.ItemDataRole.UserRole) or {}
                if course_data.get("type") != "course":
                    continue
                course_id = course_data.get("course_id")
                if not course_id:
                    continue
                for section_index in range(course_item.childCount()):
                    section_item = course_item.child(section_index)
                    section_data = section_item.data(0, Qt.ItemDataRole.UserRole) or {}
                    if (
                        section_data.get("type") == "assignment"
                        and section_item.checkState(0) == Qt.CheckState.Checked
                        and section_data.get("assignment_id")
                    ):
                        selected.setdefault(str(user_id), {}).setdefault(str(course_id), set()).add(
                            str(section_data.get("assignment_id"))
                        )
        return selected

    def selected_user_ids(self):
        return set(self.selected_course_ids_by_user().keys())

    def selected_course_count(self):
        return sum(len(course_ids) for course_ids in self.selected_course_ids_by_user().values())

    def selected_general_section_count(self):
        return sum(len(course_ids) for course_ids in self.selected_general_course_ids_by_user().values())

    def selected_assignment_count(self):
        return sum(
            len(assignment_ids)
            for course_map in self.selected_assignment_ids_by_course().values()
            for assignment_ids in course_map.values()
        )

    def selected_section_count(self):
        return self.selected_general_section_count() + self.selected_assignment_count()

    def _course_has_selection(self, course_item):
        for child_index in range(course_item.childCount()):
            section_item = course_item.child(child_index)
            section_data = section_item.data(0, Qt.ItemDataRole.UserRole) or {}
            if section_data.get("type") in {"general", "assignment"} and section_item.checkState(0) == Qt.CheckState.Checked:
                return True
        return False

    def refresh_state(self):
        selected_course_count = self.selected_course_count()
        selected_general_count = self.selected_general_section_count()
        selected_assignment_count = self.selected_assignment_count()
        selected_section_count = selected_general_count + selected_assignment_count
        destination_ok = self.destination_path.exists() and self.destination_path.is_dir()
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(selected_section_count > 0 and destination_ok)
        summary = (
            f"{selected_course_count} {'course' if selected_course_count == 1 else 'courses'} selected, "
            f"{selected_section_count} {'section' if selected_section_count == 1 else 'sections'} included "
            f"({selected_general_count} general, {selected_assignment_count} assignments)"
        )
        if selected_section_count == 0:
            summary = "No export sections selected"
        if not destination_ok:
            summary += " - choose a valid save folder"
        self.summary_label.setText(summary)

    def export_options(self):
        from services.vault_exporter import ExportOptions

        return ExportOptions(
            destination_dir=self.destination_path,
            selected_user_ids=self.selected_user_ids(),
            selected_course_ids_by_user=self.selected_course_ids_by_user(),
            selected_general_course_ids_by_user=self.selected_general_course_ids_by_user(),
            selected_assignment_ids_by_course=self.selected_assignment_ids_by_course(),
        )
