from pathlib import Path

from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QEvent, QTimer, QVariantAnimation, QSize, Signal
from PySide6.QtGui import QFont, QColor, QPalette, QIcon, QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QCheckBox,
    QDialog,
    QVBoxLayout,
    QWidget,
)

from app.app_info import APP_NAME, APP_VERSION, APP_ORGANIZATION, APP_DESCRIPTION
from app.settings import AppSettings
from app.styles import APP_FONT_PRIMARY, build_app_stylesheet, build_zoom_stylesheet
from app.ui_content import HELP_TOPIC_ORDER, HELP_TOPICS
from app.actions import AppActionsMixin
from app.dashboard_views import DashboardViewsMixin
from app.resource_tree import ResourceTreeMixin
from app.settings_views import SettingsViewsMixin
from app.startup_manager import StartupManager
from app.text_preview_views import TextPreviewViewsMixin
from app.tray_controller import TrayController
from app.widget_manager import WidgetManager
from core.helpers import format_due_datetime
from core.detail_text import make_wrap_friendly_text
from core.file_manager import FileManager
from ui.browser_widgets import BrowserItemDelegate, ResourceTreeWidget, TunedListWidget
from ui.file_explorer_dragdrop import drop_target_from_item
from ui.scroll_tuning import ScrollTuner
from ui.dialogs import CreateUserDialog
from ui.icons import load_icon, icon_for_resource_type, set_icon_theme, app_icon_path
from core.vault_manager import VaultManager
from services.command_history import CommandHistory, CompositeAction, UserCreateAction


class SidebarNavButton(QWidget):
    """Sidebar row with a separate icon well and label."""

    clicked = Signal()

    def __init__(self, text="", parent=None, *, variant="nav"):
        super().__init__(parent)
        self._icon = QIcon()
        self._icon_size = QSize(22, 22)
        self._avatar_path = ""
        self._zoom_percent = 100
        self._collapsed = False
        self.variant = variant
        self.profile_name = text
        self.profile_school = ""
        self.profile_badge = ""

        self.setObjectName("SidebarButton")
        self.setProperty("variant", variant)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(54)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(10, 8, 14, 8)
        self._layout.setSpacing(12)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("SidebarButtonIcon")
        self.icon_label.setProperty("variant", variant)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.icon_label.setProperty("pressed", False)
        self.icon_label.setProperty("active", False)
        self.icon_label.setFixedSize(36, 36)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.text_label = QLabel(text)
        self.text_label.setObjectName("SidebarButtonText")
        self.text_label.setProperty("variant", variant)
        self.text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.text_label.setProperty("pressed", False)
        self.text_label.setProperty("active", False)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        if variant == "profile":
            self.profile_text_stack = QWidget()
            self.profile_text_stack.setObjectName("SidebarProfileTextStack")
            self.profile_text_stack.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            profile_text_layout = QVBoxLayout(self.profile_text_stack)
            profile_text_layout.setContentsMargins(0, 0, 0, 0)
            profile_text_layout.setSpacing(2)
            profile_text_layout.addWidget(self.text_label)

            self.profile_school_label = QLabel("")
            self.profile_school_label.setObjectName("SidebarProfileSchool")
            self.profile_school_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.profile_school_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.profile_school_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            profile_text_layout.addWidget(self.profile_school_label)

            self.profile_badge_label = QLabel("")
            self.profile_badge_label.setObjectName("SidebarProfileBadge")
            self.profile_badge_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.profile_badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.profile_badge_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

            self._layout.addWidget(self.profile_text_stack, 1, Qt.AlignmentFlag.AlignVCenter)
            self._layout.addWidget(self.profile_badge_label, 0, Qt.AlignmentFlag.AlignVCenter)
            self.setMinimumHeight(118)
        else:
            self.profile_text_stack = None
            self.profile_school_label = None
            self.profile_badge_label = None
            self._layout.addWidget(self.text_label, 1)

        self.setProperty("pressed", False)
        self.setProperty("active", False)
        self.apply_zoom_metrics(self._zoom_percent)

    def setIcon(self, icon):
        self._icon = icon
        self._refresh_icon_pixmap()

    def setAvatarPath(self, avatar_path):
        self._avatar_path = str(avatar_path or "")
        self._refresh_icon_pixmap()

    def setIconSize(self, size):
        self._icon_size = size
        self.apply_zoom_metrics(self._zoom_percent)

    def setText(self, text):
        self.text_label.setText(text)
        self._sync_layout_state()

    def text(self):
        return self.text_label.text()

    def setProfileDetails(self, name, school="", badge=""):
        self.profile_name = "Users" if name is None else name
        self.profile_school = school or ""
        self.profile_badge = badge or ""
        self.setText(self.profile_name)

        if self.profile_school_label is not None:
            self.profile_school_label.setText(self.profile_school)
            self.profile_school_label.setVisible((not self._collapsed) and bool(self.profile_school) and bool(self.profile_name))

        if self.profile_badge_label is not None:
            self.profile_badge_label.setText(self.profile_badge)
            self.profile_badge_label.setVisible((not self._collapsed) and bool(self.profile_badge) and bool(self.profile_name))

        self._sync_layout_state()

    def setToolTip(self, text):
        super().setToolTip(text)
        self.icon_label.setToolTip(text)
        self.text_label.setToolTip(text)
        if self.profile_school_label is not None:
            self.profile_school_label.setToolTip(text)
        if self.profile_badge_label is not None:
            self.profile_badge_label.setToolTip(text)

    def setProperty(self, name, value):
        changed = super().setProperty(name, value)
        if name in {"active", "pressed"} and hasattr(self, "icon_label") and hasattr(self, "text_label"):
            self.icon_label.setProperty(name, value)
            self.text_label.setProperty(name, value)
            self.refresh_style_state()
        return changed

    def apply_zoom_metrics(self, zoom_percent):
        self._zoom_percent = max(50, int(zoom_percent or 100))
        self._sync_layout_state()

    def apply_collapsed_state(self, collapsed):
        self._collapsed = bool(collapsed)
        super().setProperty("collapsed", self._collapsed)
        self._sync_layout_state()

    def refresh_style_state(self):
        widgets = [self, self.icon_label, self.text_label]
        if self.profile_text_stack is not None:
            widgets.append(self.profile_text_stack)
        if self.profile_school_label is not None:
            widgets.append(self.profile_school_label)
        if self.profile_badge_label is not None:
            widgets.append(self.profile_badge_label)
        for widget in widgets:
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.updateGeometry()
            widget.update()
        self.updateGeometry()

    def collapsed_width_hint(self):
        margins = self._collapsed_margins()
        frame = max(self.icon_label.width(), self.icon_label.sizeHint().width())
        return frame + margins[0] + margins[2]

    def _scale_px(self, value):
        return max(1, int(round(value * (self._zoom_percent / 100.0))))

    def _collapsed_margins(self):
        inset = self._scale_px(8)
        return inset, inset, inset, inset

    def _expanded_margins(self):
        if self.variant == "profile":
            return self._scale_px(12), self._scale_px(14), self._scale_px(12), self._scale_px(14)
        return self._scale_px(10), self._scale_px(8), self._scale_px(14), self._scale_px(8)

    def _sync_layout_state(self):
        collapsed = self._collapsed or not bool(self.text_label.text())
        target_height = 54 if collapsed else (118 if self.variant == "profile" else 54)
        self.setMinimumHeight(max(44, self._scale_px(target_height)))
        self.setMaximumHeight(self._scale_px(target_height) if collapsed else 16777215)

        if collapsed:
            icon_padding = self._scale_px(12)
            base_well = self._scale_px(42)
        else:
            icon_padding = self._scale_px(18 if self.variant == "profile" else 14)
            base_well = self._scale_px(58 if self.variant == "profile" else 36)
        icon_well = max(base_well, self._icon_size.width() + icon_padding, self._icon_size.height() + icon_padding)
        self.icon_label.setFixedSize(icon_well, icon_well)

        margins = self._collapsed_margins() if collapsed else self._expanded_margins()
        self._layout.setContentsMargins(*margins)
        self._layout.setSpacing(0 if collapsed else self._scale_px(12))

        if self.variant == "profile" and self.profile_text_stack is not None:
            self.profile_text_stack.setVisible(not collapsed and bool(self.profile_name))
            if self.profile_school_label is not None:
                self.profile_school_label.setVisible(not collapsed and bool(self.profile_school) and bool(self.profile_name))
            if self.profile_badge_label is not None:
                self.profile_badge_label.setVisible(not collapsed and bool(self.profile_badge) and bool(self.profile_name))
        else:
            self.text_label.setVisible(not collapsed)

        self._refresh_icon_pixmap()
        self.refresh_style_state()

    def _refresh_icon_pixmap(self):
        if self._avatar_path:
            avatar = self._circular_avatar_pixmap(self._avatar_path)
            if not avatar.isNull():
                self.icon_label.setPixmap(avatar)
                return

        if self._icon.isNull():
            self.icon_label.clear()
            return
        pixmap = self._icon.pixmap(self._icon_size)
        self.icon_label.setPixmap(pixmap)

    def _circular_avatar_pixmap(self, avatar_path):
        source = QPixmap()
        try:
            source.loadFromData(Path(avatar_path).read_bytes())
        except OSError:
            return QPixmap()
        if source.isNull():
            return QPixmap()

        side = max(1, min(self.icon_label.width(), self.icon_label.height()) - self._scale_px(8))
        scaled = source.scaled(
            side,
            side,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

        x = max(0, (scaled.width() - side) // 2)
        y = max(0, (scaled.height() - side) // 2)
        cropped = scaled.copy(x, y, side, side)

        rounded = QPixmap(side, side)
        rounded.fill(Qt.GlobalColor.transparent)

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addEllipse(0, 0, side, side)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        return rounded

    def set_pressed(self, pressed):
        self.setProperty("pressed", bool(pressed))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_pressed(True)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        was_pressed = bool(self.property("pressed"))
        self.set_pressed(False)
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            if was_pressed:
                self.clicked.emit()
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self.set_pressed(False)
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.set_pressed(True)
            self.clicked.emit()
            QTimer.singleShot(90, lambda: self.set_pressed(False))
            return
        super().keyPressEvent(event)


class MainWindow(AppActionsMixin, DashboardViewsMixin, ResourceTreeMixin, SettingsViewsMixin, TextPreviewViewsMixin, QMainWindow):
    """Main application coordinator.

    This class owns application state and wires UI events to storage operations.
    Core storage remains in VaultManager; the universal library window remains in ui/.
    """

    def __init__(self, *, started_from_startup=False, startup_launch_mode=None):
        super().__init__()

        self.app_settings = AppSettings()
        self.startup_manager = StartupManager()
        self.started_from_startup = bool(started_from_startup)
        self.startup_launch_mode = startup_launch_mode or self.app_settings.get_startup_launch_mode()
        if self.startup_manager.is_supported():
            self.app_settings.set_run_on_startup_enabled(self.startup_manager.is_enabled())
        else:
            self.app_settings.set_run_on_startup_enabled(False)

        available_geometry = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
        if available_geometry:
            self.window_width = min(1500, max(960, int(available_geometry.width() * 0.92)))
            self.window_height = min(850, max(640, int(available_geometry.height() * 0.90)))
        else:
            self.window_width = 1280
            self.window_height = 760

        saved_window_size = self.app_settings.get_window_size()
        if saved_window_size:
            self.window_width, self.window_height = saved_window_size

        self.ui_zoom_percent = self.app_settings.get_ui_zoom_percent()
        self.scroll_tuner = ScrollTuner(self.get_scroll_speed_percent, self.get_smooth_scrolling_enabled, self)
        self.default_vault_path = self.app_settings.default_vault_path
        self.vault = VaultManager(self.app_settings.get_vault_path())
        self.file_manager = FileManager(self.vault)

        self.current_section = "Dashboard"
        self.current_user_id = None
        self.current_course_id = None
        self.current_assignment_id = None

        # The dashboard preview can show a course/assignment that is not the
        # active middle-panel selection, so keep its context separately.
        self.course_dashboard_user_id = None
        self.course_dashboard_course_id = None
        self.course_dashboard_show_all_announcements = False
        self.course_dashboard_show_all_assignments = False
        self.course_announcements_collapsed = False
        self.assignment_dashboard_user_id = None
        self.assignment_dashboard_course_id = None
        self.assignment_dashboard_assignment_id = None

        self.library_window = None
        self.editor_windows = []
        self._startup_auto_sync_started = False
        self.force_quit_requested = False

        # Files are shown naturally by default. Users can toggle type grouping.
        self.resource_view_mode = "natural"
        self.pending_resource_tree_state = None
        self.resource_clipboard = {"mode": None, "entries": []}
        self.command_history = CommandHistory(max_commands=50)
        self.history_panel_visible = self.app_settings.get_history_panel_visible()
        self._drop_enabled_widgets = []

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        icon_path = app_icon_path()
        if icon_path.exists():
            self.setWindowIcon(load_icon("app_icon") if False else QIcon(str(icon_path)))
        self.resize(self.window_width, self.window_height)
        self.setMinimumSize(860, 600)
        self.apply_current_theme()

        self.load_context_from_settings()
        self.setup_ui()
        self.register_app_scroll_widgets()
        self.update_sidebar_user_label()
        self.setup_resource_shortcuts()
        self.update_history_panel()
        self.tray_controller = TrayController(self)
        self.widget_manager = WidgetManager(self)
        self.apply_launch_preferences()

        QTimer.singleShot(0, self.run_initial_onboarding_if_needed)
        QTimer.singleShot(0, self.trigger_reminder_check)


    def closeEvent(self, event):
        app = QApplication.instance()
        if getattr(self, "_external_drag_in_progress", False) or getattr(app, "_external_drag_in_progress", False):
            event.ignore()
            QTimer.singleShot(15000, lambda: setattr(self, "_external_drag_in_progress", False))
            return
        self.app_settings.set_window_size(self.width(), self.height())
        self.app_settings.set_ui_zoom_percent(self.ui_zoom_percent)
        self.stop_media_preview()
        close_result = self.close_to_tray_decision()
        if close_result == "cancel":
            event.ignore()
            return
        if close_result == "minimize":
            event.ignore()
            self.hide()
            return
        if hasattr(self, "widget_manager"):
            self.widget_manager.shutdown()
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.trigger_reminder_check)

    def close_to_tray_decision(self):
        if getattr(self, "force_quit_requested", False):
            return "quit"

        tray = getattr(self, "tray_controller", None)
        if not tray or not tray.tray_can_run():
            return "quit"

        close_action = self.app_settings.get_close_action()
        if close_action == "quit":
            return "quit"
        if close_action == "minimize_to_tray":
            return "minimize"

        reply = QMessageBox.question(
            self,
            "Keep ZJX LMS Running?",
            "Minimize to the system tray so assignment reminders can keep running?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return "cancel"
        if reply == QMessageBox.StandardButton.Yes:
            self.app_settings.set_close_action("minimize_to_tray")
            return "minimize"

        self.app_settings.set_close_action("quit")
        return "quit"

    def trigger_reminder_check(self):
        tray = getattr(self, "tray_controller", None)
        if tray:
            QTimer.singleShot(0, tray.check_reminders)
        if hasattr(self, "prompt_to_archive_overdue_assignments"):
            QTimer.singleShot(0, self.prompt_to_archive_overdue_assignments)

    def should_start_hidden_to_tray(self):
        if not self.started_from_startup:
            return False
        if self.startup_launch_mode != "background_to_tray":
            return False

        tray = getattr(self, "tray_controller", None)
        return bool(tray and tray.tray_can_run())

    def should_show_on_launch(self):
        return not self.should_start_hidden_to_tray()

    def apply_launch_preferences(self):
        if self.started_from_startup and self.startup_launch_mode == "open_dashboard":
            self.change_section("Dashboard")

    # =========================================================
    # THEME / ACCENT
    # =========================================================

    def effective_theme_mode(self):
        if not self.app_settings.get_follow_system_theme():
            return self.app_settings.get_theme_mode()

        palette = QApplication.instance().palette() if QApplication.instance() else self.palette()
        window_color = palette.color(QPalette.ColorRole.Window)
        brightness = (window_color.red() * 0.299) + (window_color.green() * 0.587) + (window_color.blue() * 0.114)
        return "dark" if brightness < 128 else "light"

    def apply_current_theme(self):
        theme = self.effective_theme_mode()
        accent = self.app_settings.get_accent_color()
        set_icon_theme(theme)
        stylesheet = build_app_stylesheet(theme, accent, self.ui_zoom_percent)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(stylesheet)
        self.setStyleSheet(stylesheet)

        if hasattr(self, "browser_delegate"):
            self.browser_delegate.set_theme(theme, accent)
            if hasattr(self, "item_list"):
                self.item_list.viewport().update()

        if hasattr(self, "resource_tree"):
            tree_palette = self.resource_tree.palette()
            tree_palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 0, 0, 0))
            tree_palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
            self.resource_tree.setPalette(tree_palette)
            delegate = self.resource_tree.itemDelegate()
            if hasattr(delegate, "set_colours"):
                if theme == "light":
                    delegate.set_colours(
                        selected="#c7ddff",
                        selected_hover="#b8d4ff",
                        hover="#eef5ff",
                        text="#12304f",
                        selected_text="#0f172a",
                        arrow="#486580",
                    )
                else:
                    delegate.set_colours(
                        selected="#25509e",
                        selected_hover="#2f67c8",
                        hover="#1a2940",
                        text="#d8e8ff",
                        selected_text="#ffffff",
                        arrow="#c6d6eb",
                    )
                self.resource_tree.viewport().update()

        if hasattr(self, "theme_toggle_btn"):
            self.update_theme_toggle_button()
        self.refresh_themed_icons()
        if self.library_window and hasattr(self.library_window, "apply_theme"):
            self.library_window.apply_theme()
        if hasattr(self, "widget_manager"):
            self.widget_manager.apply_theme_refresh()

    def apply_zoom_font(self):
        app = QApplication.instance()
        if not app:
            return
        font = app.font()
        font.setFamily(APP_FONT_PRIMARY)
        font.setPointSizeF(12.0)
        app.setFont(font)

    def build_zoom_stylesheet(self):
        return build_zoom_stylesheet(self.ui_zoom_percent)

    def zpx(self, value):
        return max(1, int(round(value * (self.ui_zoom_percent / 100.0))))

    def update_sidebar_logo_button_metrics(self):
        if not hasattr(self, "sidebar_toggle_btn"):
            return

        collapsed = getattr(self, "sidebar_is_collapsed", False)
        collapsed_margin = self.zpx(8)
        collapsed_button_size = self.sidebar_collapsed_width - (collapsed_margin * 2)
        if collapsed:
            button_size = collapsed_button_size
        else:
            expanded_margin = self.zpx(12)
            collapsed_center = collapsed_margin + (collapsed_button_size / 2)
            button_size = max(self.zpx(42), int(round((collapsed_center - expanded_margin) * 2)))
        icon_size = self.zpx(34)
        self.sidebar_toggle_btn.setFixedSize(button_size, button_size)
        self.sidebar_toggle_btn.setIconSize(QSize(icon_size, icon_size))

    def sidebar_width_bounds(self):
        collapsed_width = self.zpx(76)
        min_expanded = max(self.zpx(260), collapsed_width + self.zpx(150))
        ideal_width = max(min_expanded, int(self.window_width * 0.18))
        max_width = min(self.zpx(520), max(min_expanded, int(self.window_width * 0.42)))
        return collapsed_width, min_expanded, max_width, ideal_width

    def clamp_sidebar_expanded_width(self, width):
        _collapsed_width, min_expanded, max_width, _ideal_width = self.sidebar_width_bounds()
        return max(min_expanded, min(max_width, int(width)))

    def refresh_ui_scaling(self, *, preserve_sidebar_width=True):
        self.apply_zoom_font()
        self.apply_current_theme()
        self.apply_zoom_dimensions()
        self.apply_responsive_layout_metrics(
            preserve_sidebar_width=preserve_sidebar_width,
            update_splitters=True,
        )
        self.refresh_list_item_size_hints()
        self.refresh_middle_panel_scaling()

    def apply_zoom_dimensions(self):
        if hasattr(self, "sidebar_toggle_btn"):
            self.update_sidebar_logo_button_metrics()
        if hasattr(self, "sidebar_title_button"):
            self.sidebar_title_button.updateGeometry()
            self.sidebar_title_button.update()
        if hasattr(self, "theme_toggle_btn"):
            self.theme_toggle_btn.setFixedSize(self.zpx(54), self.zpx(54))
            self.theme_toggle_btn.setIconSize(QSize(self.zpx(18), self.zpx(18)))
        if hasattr(self, "history_list"):
            row_count = self.history_list.count()
            row_height = self.zpx(28)
            target_height = self.zpx(34) if row_count <= 1 else min(self.zpx(116), self.zpx(8) + (row_count * row_height))
            self.history_list.setFixedHeight(target_height)
        if hasattr(self, "history_panel"):
            self.history_panel.setMaximumHeight(self.zpx(210))
        if hasattr(self, "resource_view_btn"):
            self.resource_view_btn.setFixedHeight(self.zpx(46))
            self.resource_view_btn.setFixedWidth(self.zpx(180))
        if hasattr(self, "resource_refresh_btn"):
            file_header_button_size = self.zpx(46)
            self.resource_refresh_btn.setFixedSize(file_header_button_size, file_header_button_size)
            self.resource_refresh_btn.setIconSize(QSize(self.zpx(18), self.zpx(18)))
        if hasattr(self, "course_announcements_toggle_btn"):
            self.course_announcements_toggle_btn.setFixedWidth(self.zpx(124))
        if hasattr(self, "course_announcements_collapse_btn"):
            self.course_announcements_collapse_btn.setFixedWidth(self.zpx(116))
        if hasattr(self, "course_assignments_toggle_btn"):
            self.course_assignments_toggle_btn.setFixedWidth(self.zpx(124))
        if hasattr(self, "assignment_add_todo_btn"):
            self.assignment_add_todo_btn.setFixedWidth(self.zpx(136))
        if hasattr(self, "assignment_canvas_btn"):
            self.assignment_canvas_btn.setFixedWidth(self.zpx(160))
        if hasattr(self, "resource_tree"):
            icon_size = max(18, self.zpx(24))
            self.resource_tree.setIconSize(QSize(icon_size, icon_size))
        if hasattr(self, "sidebar_button_specs"):
            for button, _icon_name, _label, _section_name in self.sidebar_button_specs:
                button.apply_zoom_metrics(self.ui_zoom_percent)
        if hasattr(self, "sidebar_layout"):
            self.sidebar_layout.setContentsMargins(self.zpx(12), self.zpx(12), self.zpx(12), self.zpx(12))
            self.sidebar_layout.setSpacing(self.zpx(8))
        if hasattr(self, "sidebar_header_row"):
            self.sidebar_header_row.setSpacing(self.zpx(6))
        if hasattr(self, "bottom_row"):
            self.bottom_row.setSpacing(self.zpx(6))
        if hasattr(self, "history_layout"):
            self.history_layout.setContentsMargins(self.zpx(10), self.zpx(10), self.zpx(10), self.zpx(10))
            self.history_layout.setSpacing(self.zpx(5))
        if hasattr(self, "middle_layout"):
            self.middle_layout.setContentsMargins(self.zpx(16), self.zpx(16), self.zpx(16), self.zpx(16))
            self.middle_layout.setSpacing(self.zpx(12))
        if hasattr(self, "title_row"):
            self.title_row.setSpacing(self.zpx(10))
        if hasattr(self, "course_actions_layout"):
            self.course_actions_layout.setContentsMargins(self.zpx(10), self.zpx(8), self.zpx(10), self.zpx(8))
            self.course_actions_layout.setSpacing(self.zpx(8))
        if hasattr(self, "item_list"):
            self.item_list.setSpacing(self.zpx(8))
        if hasattr(self, "browser_context_label"):
            self.browser_context_label.updateGeometry()
            self.browser_context_label.update()
        for button_name in (
            "add_course_btn",
            "sync_canvas_btn",
            "course_blacklist_btn",
            "course_favourites_btn",
        ):
            button = getattr(self, button_name, None)
            if button is not None:
                button.setMinimumHeight(self.zpx(44))
                button.setIconSize(QSize(self.zpx(18), self.zpx(18)))
        if hasattr(self, "resource_tree"):
            self.resource_tree.setIndentation(self.zpx(24))
        if hasattr(self, "main_splitter"):
            self.main_splitter.setHandleWidth(self.zpx(9))
        if hasattr(self, "content_splitter"):
            self.content_splitter.setHandleWidth(self.zpx(9))
        if hasattr(self, "browser_delegate"):
            self.browser_delegate.set_zoom_percent(self.ui_zoom_percent)

    def refresh_middle_panel_scaling(self):
        if hasattr(self, "item_list"):
            self.item_list.doItemsLayout()
            self.item_list.viewport().update()
            self.item_list.updateGeometry()
        if hasattr(self, "resource_tree"):
            self.resource_tree.viewport().update()
            self.resource_tree.updateGeometry()
        if hasattr(self, "browser_stack"):
            self.browser_stack.updateGeometry()
            self.browser_stack.update()
        if hasattr(self, "course_actions_bar"):
            self.course_actions_bar.updateGeometry()
            self.course_actions_bar.update()
        if hasattr(self, "browser_context_label"):
            self.browser_context_label.updateGeometry()
            self.browser_context_label.update()
        if hasattr(self, "section_title"):
            self.section_title.updateGeometry()
            self.section_title.update()

    def apply_responsive_layout_metrics(self, *, preserve_sidebar_width=True, update_splitters=True):
        collapsed_width, _min_expanded, max_width, ideal_width = self.sidebar_width_bounds()
        self.sidebar_collapsed_width = collapsed_width
        if preserve_sidebar_width:
            current_width = getattr(self, "sidebar_expanded_width", ideal_width)
        else:
            current_width = ideal_width
        self.sidebar_expanded_width = self.clamp_sidebar_expanded_width(current_width)

        if hasattr(self, "sidebar"):
            self.sidebar.setMinimumWidth(self.sidebar_collapsed_width)
            self.sidebar.setMaximumWidth(max_width)
            target_width = self.sidebar_collapsed_width if getattr(self, "sidebar_is_collapsed", False) else self.sidebar_expanded_width
            current_sidebar_width = self.sidebar.width()
            needs_sidebar_update = update_splitters or current_sidebar_width > max_width or current_sidebar_width < self.sidebar_collapsed_width or (
                not getattr(self, "sidebar_is_collapsed", False) and current_sidebar_width < self.sidebar_collapsed_width
            )
            if needs_sidebar_update:
                self.set_sidebar_splitter_width(target_width)

        if hasattr(self, "middle_panel"):
            self.middle_panel.setMinimumWidth(max(self.zpx(280), int(self.window_width * 0.22)))
        if hasattr(self, "right_panel"):
            self.right_panel.setMinimumWidth(max(self.zpx(380), int(self.window_width * 0.30)))

        if hasattr(self, "content_splitter") and not getattr(self, "dashboard_full_width_active", False):
            sizes = self.content_splitter.sizes()
            if len(sizes) >= 2:
                left_width, right_width = sizes[0], sizes[1]
                total_width = max(1, left_width + right_width)
                left_min = self.middle_panel.minimumWidth()
                right_min = self.right_panel.minimumWidth()
                if left_width < left_min or right_width < right_min:
                    left_width = max(left_min, min(total_width - right_min, left_width))
                    right_width = max(right_min, total_width - left_width)
                    self.content_splitter.setSizes([left_width, right_width])

        self.update_sidebar_collapsed_state()

    def set_ui_zoom_percent(self, percent):
        self.ui_zoom_percent = self.app_settings.set_ui_zoom_percent(percent)
        self.refresh_ui_scaling()
        if self.current_section == "Settings":
            self.show_settings_section()

    def scaled_size(self, width, height):
        scale = self.ui_zoom_percent / 100.0
        return QSize(max(1, int(round(width * scale))), max(1, int(round(height * scale))))

    def refresh_list_item_size_hints(self):
        if not hasattr(self, "item_list"):
            return
        for row in range(self.item_list.count()):
            item = self.item_list.item(row)
            data = item.data(Qt.ItemDataRole.UserRole) or {}
            if data.get("type") == "setting_header":
                item.setSizeHint(self.scaled_size(260, 86))
            else:
                item.setSizeHint(self.scaled_size(260, 118))
        self.item_list.doItemsLayout()
        self.item_list.viewport().update()

    def adjust_ui_zoom(self, delta):
        self.set_ui_zoom_percent(self.ui_zoom_percent + delta)

    def toggle_theme_mode(self):
        current = self.effective_theme_mode()
        new_mode = "light" if current == "dark" else "dark"
        self.app_settings.set_follow_system_theme(False)
        self.app_settings.set_theme_mode(new_mode)
        self.apply_current_theme()
        if self.current_section == "Settings":
            self.show_settings_section()

    def update_theme_toggle_button(self):
        mode = self.effective_theme_mode()
        self.theme_toggle_btn.setIcon(load_icon("sun" if mode == "dark" else "moon"))
        self.theme_toggle_btn.setToolTip("Switch to light mode" if mode == "dark" else "Switch to dark mode")
    def refresh_themed_icons(self):
        """Refresh persistent QIcon objects after a theme/accent change.

        Painted browser cards call load_icon() during paint, but QPushButton
        and QTreeWidgetItem instances keep a QIcon object. Re-assign those
        icons so light mode gets the darker SVG set and dark mode gets the
        lighter SVG set.
        """
        if hasattr(self, "sidebar_button_specs"):
            self.update_sidebar_collapsed_state()

        toolbar_icons = [
            ("add_course_btn", "plus"),
            ("sync_canvas_btn", "sync"),
            ("course_blacklist_btn", "ban"),
            ("course_favourites_btn", "star"),
        ]
        for attr_name, icon_name in toolbar_icons:
            button = getattr(self, attr_name, None)
            if button is not None:
                button.setIcon(load_icon(icon_name))

        refresh_button = getattr(self, "resource_refresh_btn", None)
        if refresh_button is not None:
            refresh_button.setText("")
            refresh_button.setIcon(load_icon("refresh"))

        if hasattr(self, "resource_tree"):
            self.refresh_resource_tree_icons()
            self.resource_tree.viewport().update()

    def refresh_resource_tree_icons(self):
        """Re-apply themed icons to the current file/resource tree."""
        if not hasattr(self, "resource_tree"):
            return

        def update_item(item):
            data = item.data(0, Qt.ItemDataRole.UserRole) or {}
            item_type = data.get("type")

            if item_type == "resource":
                resource = data.get("resource", {})
                item.setIcon(0, icon_for_resource_type(resource.get("type", "local_file")))
            elif item_type == "file_system_entry":
                path = Path(data.get("path", ""))
                item.setIcon(0, load_icon("folder" if path.is_dir() else "file"))
            elif item_type in {"folder_missing", "folder_permission_denied"}:
                item.setIcon(0, load_icon("warning"))
            elif item_type == "group":
                item.setIcon(0, icon_for_resource_type(data.get("resource_type", "note")))

            for row in range(item.childCount()):
                update_item(item.child(row))

        root = self.resource_tree.invisibleRootItem()
        for row in range(root.childCount()):
            update_item(root.child(row))


    # =========================================================
    # GLOBAL DRAG AND DROP IMPORT
    # =========================================================

    def enable_global_drop_import(self, widgets):
        """Allow file/folder drops across the main application surface.

        Dropped local files/folders are imported into the current
        User → Course → Assignment/General scope.
        """
        for widget in widgets:
            if widget is None:
                continue

            widget.setAcceptDrops(True)
            widget.installEventFilter(self)
            self._drop_enabled_widgets.append(widget)

    def eventFilter(self, watched, event):
        if (
            watched == getattr(getattr(self, "image_scroll_area", None), "viewport", lambda: None)()
            and event.type() == QEvent.Type.Resize
            and hasattr(self, "update_image_preview_scale")
        ):
            self.update_image_preview_scale()

        if self.handle_app_shortcut_event(watched, event):
            return True

        if watched in {
            getattr(self, "resource_tree", None),
            getattr(getattr(self, "resource_tree", None), "viewport", lambda: None)(),
        }:
            if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop):
                return False

        if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            if self.drag_event_has_local_paths(event) and self.current_user_id and self.current_course_id:
                event.acceptProposedAction()
                return True
            
        if event.type() == QEvent.Type.Drop:
            paths = self.local_paths_from_drop_event(event)

            if paths:
                target_item = None

                if watched in {
                    getattr(self, "resource_tree", None),
                    getattr(self.resource_tree, "viewport", lambda: None)(),
                }:
                    position = event.position().toPoint() if hasattr(event, "position") else event.pos()
                    target_item = self.resource_tree.itemAt(position)
                    drop_target = drop_target_from_item(target_item, self)
                else:
                    drop_target = None

                event.acceptProposedAction()

                # Defer the import until after Qt finishes processing the drop event.
                # This prevents the first dropped item from being imported but not visually shown.
                QTimer.singleShot(
                    0,
                    lambda dropped_paths=paths, plain_target=drop_target: self.import_dropped_paths(
                        dropped_paths,
                        drop_target=plain_target,
                    )
                )

                return True

        return super().eventFilter(watched, event)

    def drag_event_has_local_paths(self, event):
        mime_data = event.mimeData()

        if not mime_data or not mime_data.hasUrls():
            return False

        return any(url.isLocalFile() for url in mime_data.urls())

    def local_paths_from_drop_event(self, event):
        mime_data = event.mimeData()

        if not mime_data or not mime_data.hasUrls():
            return []

        paths = []

        for url in mime_data.urls():
            if url.isLocalFile():
                paths.append(Path(url.toLocalFile()))

        return paths


    def import_dropped_paths(self, paths, target_item=None, drop_target=None):
        if not self.ensure_course_context():
            return False

        imported_count = 0
        failed = []
        target_folder = Path(drop_target["folder_path"]) if isinstance(drop_target, dict) and drop_target.get("folder_path") else self.target_folder_path_from_item(target_item)
        actions = []
        reserved_paths = set()

        try:
            for source in paths:
                try:
                    if source.is_dir():
                        item_actions, destination = self.build_folder_resource_import_actions(
                            source,
                            destination_parent=target_folder,
                            reserved_paths=reserved_paths,
                        )
                        actions.extend(item_actions)
                        reserved_paths.add(destination)
                        imported_count += 1
                    elif source.is_file():
                        item_actions, destination = self.build_file_resource_import_actions(
                            source,
                            destination_parent=target_folder,
                            reserved_paths=reserved_paths,
                        )
                        actions.extend(item_actions)
                        reserved_paths.add(destination)
                        imported_count += 1
                except Exception as error:
                    failed.append({"source": str(source), "error": repr(error)})

            if imported_count:
                action = CompositeAction(
                    f"Imported {imported_count} dropped item(s)",
                    actions,
                    action_type="import_dropped_items",
                )
                self.command_history.perform(action)
                self.update_history_panel()
                state = self.capture_resource_tree_state()
                self.refresh_files_tree_after_move(state)

                destination_text = str(target_folder) if target_folder else "the current scope"
                self.show_text_page(
                    "Imported Resources",
                    self.current_context_label(),
                    f"Successfully imported {imported_count} item(s) into {destination_text}.\n\n"
                    "Dropped items are copied into the vault, so the app keeps its own managed copy."
                )

        except Exception:
            raise

        if failed:
            self.show_user_warning(
                "Some Items Could Not Be Imported",
                f"{len(failed)} item(s) could not be imported.",
                context={"failures": failed[:10]},
            )

        return imported_count > 0

    def import_external_paths(self, paths, target_item=None, drop_target=None):
        try:
            return self.import_dropped_paths(paths, target_item=target_item, drop_target=drop_target)
        except Exception as error:
            self.show_user_warning(
                "Import Failed",
                "Items could not be imported.",
                error=error,
                context={"paths": [str(path) for path in paths[:10]]},
            )
            return False

    def mask_token(self, token):
        token = (token or "").strip()

        if not token:
            return "Not provided"

        if len(token) <= 10:
            return "•" * len(token)

        return f"{token[:6]}...{token[-4:]}"

    def run_initial_onboarding_if_needed(self):
        users = self.vault.get_users()

        if users:
            self.app_settings.set_onboarding_completed(True)
            self.run_startup_auto_sync_if_enabled()
            return

        if self.app_settings.get_onboarding_completed():
            return

        self.show_create_user_dialog(required=True)

    def show_create_user_dialog(self, required=False):
        dialog = CreateUserDialog(self, required=required)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            if required and not self.vault.get_users():
                self.change_section("Users")
                self.show_text_page(
                    "No User Created",
                    "Onboarding skipped",
                    "Create a user from the Users section when you are ready. "
                    "The app needs a user profile before course, assignment, and file data can be attached.",
                )
            return None

        payload = dialog.user_payload()
        action = UserCreateAction(
            self.vault,
            payload["name"],
            university=payload.get("university", ""),
            canvas_access_token=payload.get("canvas_access_token", ""),
            canvas_base_url=payload.get("canvas_base_url", "https://canvas.sydney.edu.au"),
            description=f"Created user: {payload['name']}",
        )
        self.command_history.perform(action)
        self.update_history_panel()
        user = action.user

        self.app_settings.set_onboarding_completed(True)
        self.set_current_user(user["id"])
        self.change_section("Users")
        self.show_user_detail(user)
        return user

    def get_vault_path(self):
        return self.app_settings.get_vault_path()

    def set_vault_path(self, path):
        vault_path = self.app_settings.set_vault_path(path)
        self.vault = VaultManager(vault_path)
        self.file_manager = FileManager(self.vault)
        self.load_context_from_settings()
        if hasattr(self, "widget_manager"):
            self.widget_manager.update_vault(self.vault)

    def open_widgets_manager(self):
        self.update_sidebar_active_state("Widgets")
        if hasattr(self, "widget_manager"):
            self.widget_manager.show_manager_window()

    def get_scroll_speed_percent(self):
        return self.app_settings.get_scroll_speed_percent()

    def set_scroll_speed_percent(self, percent):
        percent = self.app_settings.set_scroll_speed_percent(percent)
        if self.current_section == "Settings":
            self.show_settings_section()
        return percent

    def get_smooth_scrolling_enabled(self):
        return self.app_settings.get_smooth_scrolling_enabled()

    def set_smooth_scrolling_enabled(self, enabled):
        enabled = self.app_settings.set_smooth_scrolling_enabled(enabled)
        if self.current_section == "Settings":
            self.show_settings_section()
        return enabled

    def get_canvas_auto_sync_enabled(self):
        return self.app_settings.get_canvas_auto_sync_enabled()

    def run_startup_auto_sync_if_enabled(self):
        if self._startup_auto_sync_started:
            return
        if not self.app_settings.get_canvas_auto_sync_enabled():
            return

        user = self.get_current_user()
        if not user or not user.get("canvas_access_token"):
            return

        self._startup_auto_sync_started = True
        QTimer.singleShot(700, lambda: self.sync_canvas_data_for_user(user, automatic=True, show_intro=False))

    def register_app_scroll_widgets(self):
        """Apply the user-configured scroll speed to every main scroll surface."""
        for widget in [
            getattr(self, "item_list", None),
            getattr(self, "resource_tree", None),
            getattr(self, "history_list", None),
            getattr(self, "text_scroll_area", None),
            getattr(self, "image_scroll_area", None),
            getattr(self, "global_timeline_scroll", None),
            getattr(self, "global_dashboard_scroll", None),
            getattr(self, "course_dashboard_scroll", None),
            getattr(self, "assignment_dashboard_scroll", None),
        ]:
            if widget is not None:
                self.scroll_tuner.register(widget)

    def load_context_from_settings(self):
        users = self.vault.get_users()

        if not users:
            self.current_user_id = None
            self.current_course_id = None
            self.current_assignment_id = None
            self.app_settings.set_current_user_id(None)
            self.app_settings.set_current_course_id(None)
            self.app_settings.set_current_assignment_id(None)
            self.update_sidebar_user_label()
            return

        saved_user_id = self.app_settings.get_current_user_id()
        user_ids = {user["id"] for user in users}

        if saved_user_id not in user_ids:
            saved_user_id = users[0]["id"]

        self.current_user_id = saved_user_id
        self.app_settings.set_current_user_id(self.current_user_id)

        courses = self.get_visible_courses(self.current_user_id)

        if courses:
            saved_course_id = self.app_settings.get_current_course_id()
            course_ids = {course["id"] for course in courses}

            if saved_course_id not in course_ids:
                saved_course_id = courses[0]["id"]

            self.current_course_id = saved_course_id
            self.app_settings.set_current_course_id(self.current_course_id)
        else:
            self.current_course_id = None
            self.app_settings.set_current_course_id(None)

        assignments = self.get_current_assignments()
        assignment_ids = {assignment["id"] for assignment in assignments}
        saved_assignment_id = self.app_settings.get_current_assignment_id()

        if saved_assignment_id in assignment_ids:
            self.current_assignment_id = saved_assignment_id
        else:
            self.current_assignment_id = None
            self.app_settings.set_current_assignment_id(None)

        self.update_sidebar_user_label()
        self.update_course_action_buttons()

    def set_current_user(self, user_id):
        self.current_user_id = user_id
        self.app_settings.set_current_user_id(user_id)

        courses = self.get_visible_courses(user_id)

        if courses:
            self.current_course_id = courses[0]["id"]
            self.app_settings.set_current_course_id(self.current_course_id)
        else:
            self.current_course_id = None
            self.app_settings.set_current_course_id(None)

        self.current_assignment_id = None
        self.app_settings.set_current_assignment_id(None)
        self.update_sidebar_user_label()
        self.update_course_action_buttons()

    def set_current_course(self, course_id):
        self.current_course_id = course_id
        self.app_settings.set_current_course_id(course_id)

        self.current_assignment_id = None
        self.app_settings.set_current_assignment_id(None)

    def set_current_assignment(self, assignment_id):
        self.current_assignment_id = assignment_id
        self.app_settings.set_current_assignment_id(assignment_id)

    def get_current_user(self):
        if not self.current_user_id:
            return None
        return self.vault.get_user(self.current_user_id)

    def get_current_course(self):
        if not self.current_user_id or not self.current_course_id:
            return None
        return self.vault.get_course(self.current_user_id, self.current_course_id)

    def get_current_assignments(self):
        if not self.current_user_id or not self.current_course_id:
            return []
        return self.vault.get_assignments(self.current_user_id, self.current_course_id)

    def course_canvas_id(self, course):
        return str((course or {}).get("canvas_id") or "").strip()

    def user_canvas_blacklist(self, user_id=None):
        user = self.vault.get_user(user_id or self.current_user_id)
        return {str(item) for item in (user or {}).get("canvas_blacklisted_course_ids", [])}

    def user_canvas_favourites(self, user_id=None):
        user = self.vault.get_user(user_id or self.current_user_id)
        return {str(item) for item in (user or {}).get("canvas_favourite_course_ids", [])}

    def course_is_blacklisted(self, course, user_id=None):
        canvas_id = self.course_canvas_id(course)
        return bool(canvas_id and canvas_id in self.user_canvas_blacklist(user_id))

    def course_is_favourite(self, course, user_id=None):
        canvas_id = self.course_canvas_id(course)
        return bool(canvas_id and canvas_id in self.user_canvas_favourites(user_id))

    def course_is_archived(self, course):
        return bool((course or {}).get("archived"))

    def get_visible_courses(self, user_id=None):
        user_id = user_id or self.current_user_id
        if not user_id:
            return []

        courses = [
            course for course in self.vault.get_courses(user_id)
            if not self.course_is_archived(course)
            and not self.course_is_blacklisted(course, user_id)
        ]

        favourite_ids = self.user_canvas_favourites(user_id)
        return sorted(
            courses,
            key=lambda course: (
                0 if self.course_canvas_id(course) in favourite_ids else 1,
                0 if course.get("source") == "canvas" else 1,
                (course.get("code") or course.get("name") or "").lower(),
                (course.get("name") or "").lower(),
            ),
        )

    def get_current_assignment(self):
        if not self.current_assignment_id:
            return None
        return self.vault.get_assignment(
            self.current_user_id,
            self.current_course_id,
            self.current_assignment_id,
        )

    def current_context_label(self):
        user = self.get_current_user()
        course = self.get_current_course()
        assignment = self.get_current_assignment()

        user_name = user["name"] if user else "No user"
        course_name = f"{course['code']} - {course['name']}" if course else "No course"
        assignment_name = assignment["title"] if assignment else "General Course Resources"

        return f"User: {user_name}  |  Course: {course_name}  |  Scope: {assignment_name}"

    # =========================================================
    # UI SETUP
    # =========================================================

    def setup_ui(self):
        main_container = QWidget()
        self.setCentralWidget(main_container)

        main_layout = QHBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = self.build_sidebar()
        middle_panel = self.build_middle_panel()
        right_panel = self.build_right_panel()
        self.middle_panel = middle_panel
        self.right_panel = right_panel
        self.dashboard_full_width_active = False
        self.pre_dashboard_splitter_sizes = None

        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.content_splitter.setObjectName("ContentSplitter")
        self.content_splitter.setChildrenCollapsible(False)
        self.content_splitter.setHandleWidth(9)
        self.content_splitter.addWidget(middle_panel)
        self.content_splitter.addWidget(right_panel)
        self.content_splitter.setStretchFactor(0, 1)
        self.content_splitter.setStretchFactor(1, 3)

        saved_splitter_state = self.app_settings.get_main_splitter_state()
        if saved_splitter_state:
            self.content_splitter.restoreState(saved_splitter_state)
        else:
            available_content_width = max(700, self.window_width - self.sidebar_expanded_width)
            middle_width = self.zpx(300)
            self.content_splitter.setSizes([
                max(320, int(available_content_width * 0.34)),
                max(420, int(available_content_width * 0.66)),
            ])

        self.content_splitter.splitterMoved.connect(self.handle_content_splitter_moved)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setObjectName("MainSplitter")
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(9)
        self.main_splitter.addWidget(sidebar)
        self.main_splitter.addWidget(self.content_splitter)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        saved_sidebar_width = self.app_settings.get_sidebar_width(self.sidebar_expanded_width)
        self.sidebar_expanded_width = self.clamp_sidebar_expanded_width(saved_sidebar_width)
        self.main_splitter.setSizes([
            self.sidebar_expanded_width,
            max(1, self.window_width - self.sidebar_expanded_width),
        ])
        self.main_splitter.splitterMoved.connect(self.handle_main_splitter_moved)

        main_layout.addWidget(self.main_splitter, 1)

        self.enable_global_drop_import([
            self,
            main_container,
            sidebar,
            self.content_splitter,
            middle_panel,
            right_panel,
            self.item_list,
            self.resource_tree,
            self.resource_tree.viewport(),
            self.browser_stack,
            self.detail_stack,
            self.text_page,
        ])

        self.refresh_ui_scaling()
        self.connect_signals()
        self.change_section("Dashboard")

    def handle_content_splitter_moved(self, *_):
        if getattr(self, "dashboard_full_width_active", False):
            return
        self.app_settings.set_main_splitter_state(self.content_splitter.saveState())

    def handle_main_splitter_moved(self, *_):
        if getattr(self, "sidebar_is_collapsed", False):
            return
        self.sidebar_expanded_width = self.clamp_sidebar_expanded_width(max(self.sidebar_collapsed_width, self.sidebar.width()))
        self.app_settings.set_sidebar_width(self.sidebar_expanded_width)

    def set_sidebar_splitter_width(self, width):
        width = int(width)
        if hasattr(self, "main_splitter"):
            total = max(1, sum(self.main_splitter.sizes()) or self.main_splitter.width())
            self.main_splitter.setSizes([width, max(1, total - width)])

    def set_dashboard_full_width_mode(self, enabled):
        if not hasattr(self, "content_splitter") or not hasattr(self, "middle_panel"):
            return

        if enabled:
            if self.dashboard_full_width_active:
                return
            sizes = self.content_splitter.sizes()
            if sizes and sizes[0] > 0:
                self.pre_dashboard_splitter_sizes = sizes
            self.dashboard_full_width_active = True
            self.middle_panel.setVisible(False)
            self.content_splitter.setSizes([0, max(1, self.content_splitter.width())])
            return

        if not self.dashboard_full_width_active:
            return
        self.middle_panel.setVisible(True)
        self.dashboard_full_width_active = False
        if self.pre_dashboard_splitter_sizes:
            self.content_splitter.setSizes(self.pre_dashboard_splitter_sizes)
        else:
            saved_splitter_state = self.app_settings.get_main_splitter_state()
            if saved_splitter_state:
                self.content_splitter.restoreState(saved_splitter_state)
        self.pre_dashboard_splitter_sizes = None

    def build_sidebar(self):
        self.sidebar_collapsed_width, _min_expanded, _max_width, self.sidebar_expanded_width = self.sidebar_width_bounds()
        self.sidebar_is_collapsed = False

        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setMinimumWidth(self.sidebar_collapsed_width)
        sidebar.setMaximumWidth(self.sidebar_width_bounds()[2])
        self.sidebar = sidebar

        sidebar_layout = QVBoxLayout(sidebar)
        self.sidebar_layout = sidebar_layout
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.setSpacing(8)

        header_row = QHBoxLayout()
        self.sidebar_header_row = header_row
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        self.sidebar_toggle_btn = QPushButton()
        self.sidebar_toggle_btn.setObjectName("SidebarLogoButton")
        self.sidebar_toggle_btn.setFixedSize(42, 42)
        self.sidebar_toggle_btn.setIconSize(QSize(30, 30))
        self.sidebar_toggle_btn.setIcon(QIcon(str(app_icon_path())))
        self.sidebar_toggle_btn.setToolTip("Toggle sidebar")

        self.sidebar_title_button = QPushButton("ZJX LMS")
        self.sidebar_title_button.setObjectName("SidebarTitleButton")
        self.sidebar_title_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_title_button.setToolTip("Collapse sidebar")

        header_row.addWidget(self.sidebar_toggle_btn)
        header_row.addWidget(self.sidebar_title_button)
        header_row.addStretch()

        self.users_btn = SidebarNavButton("Users", variant="profile")
        self.dashboard_btn = SidebarNavButton("Dashboard")
        self.courses_btn = SidebarNavButton("Courses")
        self.assignments_btn = SidebarNavButton("Assignments")
        self.files_btn = SidebarNavButton("Files")
        self.library_btn = SidebarNavButton("Resource Library")
        self.widgets_btn = SidebarNavButton("Widgets")
        self.help_btn = SidebarNavButton("Help")
        self.settings_btn = SidebarNavButton("Settings")

        self.sidebar_button_specs = [
            (self.users_btn, "user", "Users", "Users"),
            (self.dashboard_btn, "dashboard", "Dashboard", "Dashboard"),
            (self.courses_btn, "course", "Courses", "Courses"),
            (self.assignments_btn, "assignment", "Assignments", "Assignments"),
            (self.files_btn, "folder", "Files", "Files"),
            (self.library_btn, "library", "Resource Library", "Resource Library"),
            (self.widgets_btn, "dashboard", "Widgets", "Widgets"),
            (self.help_btn, "help", "Help", "Help"),
            (self.settings_btn, "settings", "Settings", "Settings"),
        ]

        for button, icon_name, label, section_name in self.sidebar_button_specs:
            button.setIcon(load_icon(icon_name))
            if section_name == "Users":
                button.setIconSize(QSize(28, 28))
                button.setMinimumHeight(118)
            else:
                button.setIconSize(QSize(22, 22))
                button.setMinimumHeight(54)
            button.setToolTip(label)

        sidebar_layout.addLayout(header_row)
        sidebar_layout.addSpacing(10)
        sidebar_layout.addWidget(self.users_btn)
        sidebar_layout.addWidget(self.dashboard_btn)

        sidebar_layout.addWidget(self.courses_btn)
        sidebar_layout.addWidget(self.assignments_btn)
        sidebar_layout.addWidget(self.files_btn)
        sidebar_layout.addSpacing(10)
        sidebar_layout.addWidget(self.library_btn)
        sidebar_layout.addWidget(self.widgets_btn)
        sidebar_layout.addStretch()

        self.history_panel = QFrame()
        self.history_panel.setObjectName("HistoryPanel")
        self.history_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        history_layout = QVBoxLayout(self.history_panel)
        self.history_layout = history_layout
        history_layout.setContentsMargins(10, 10, 10, 10)
        history_layout.setSpacing(5)

        history_title = QLabel("Recent Changes")
        history_title.setObjectName("SectionCaption")

        self.history_list = QListWidget()
        self.history_list.setObjectName("HistoryList")
        self.history_list.setFixedHeight(34)
        self.history_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.history_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        history_button_row = QHBoxLayout()
        history_button_row.setContentsMargins(0, 0, 0, 0)
        history_button_row.setSpacing(8)

        self.undo_btn = QPushButton("↶ Undo")
        self.redo_btn = QPushButton("↷ Redo")
        self.undo_btn.setObjectName("SmallButton")
        self.redo_btn.setObjectName("SmallButton")
        self.undo_btn.setEnabled(False)
        self.redo_btn.setEnabled(False)

        history_button_row.addWidget(self.undo_btn)
        history_button_row.addWidget(self.redo_btn)

        self.history_toggle = QCheckBox("Show history")
        self.history_toggle.setChecked(self.history_panel_visible)

        history_layout.addWidget(history_title)
        history_layout.addWidget(self.history_list)
        history_layout.addLayout(history_button_row)
        history_layout.addWidget(self.history_toggle)

        self.history_panel.setVisible(self.history_panel_visible)

        sidebar_layout.addWidget(self.history_panel)

        bottom_row = QHBoxLayout()
        self.bottom_row = bottom_row
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(6)

        self.theme_toggle_btn = QPushButton()
        self.theme_toggle_btn.setObjectName("SidebarIconButton")
        self.theme_toggle_btn.setFixedSize(54, 54)
        self.theme_toggle_btn.setIconSize(QSize(18, 18))
        self.update_theme_toggle_button()
        bottom_row.addWidget(self.help_btn, 1)
        bottom_row.addWidget(self.theme_toggle_btn, 0)
        sidebar_layout.addLayout(bottom_row)
        sidebar_layout.addWidget(self.settings_btn)

        return sidebar

    def build_middle_panel(self):
        middle_panel = QWidget()
        middle_panel.setObjectName("MiddlePanel")
        middle_panel.setMinimumWidth(300)
        middle_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        middle_layout = QVBoxLayout(middle_panel)
        self.middle_layout = middle_layout
        middle_layout.setContentsMargins(16, 16, 16, 16)
        middle_layout.setSpacing(12)

        self.section_title = QLabel("Courses")
        self.section_title.setObjectName("SectionTitle")
        self.section_title.setWordWrap(True)
        self.section_title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.resource_view_btn = QPushButton("View: Natural")
        self.resource_view_btn.setToolTip("Current file browser view mode")
        self.resource_view_btn.setFixedWidth(180)
        self.resource_view_btn.setFixedHeight(46)
        self.resource_view_btn.setVisible(False)

        self.resource_refresh_btn = QPushButton()
        self.resource_refresh_btn.setObjectName("FileHeaderIconButton")
        self.resource_refresh_btn.setIcon(load_icon("refresh"))
        self.resource_refresh_btn.setIconSize(QSize(18, 18))
        self.resource_refresh_btn.setToolTip("Refresh file explorer")
        self.resource_refresh_btn.setFixedSize(46, 46)
        self.resource_refresh_btn.setVisible(False)

        self.course_actions_bar = QFrame()
        self.course_actions_bar.setObjectName("SectionActionBar")
        self.course_actions_bar.setVisible(False)
        course_actions_layout = QHBoxLayout(self.course_actions_bar)
        self.course_actions_layout = course_actions_layout
        course_actions_layout.setContentsMargins(10, 8, 10, 8)
        course_actions_layout.setSpacing(8)

        self.add_course_btn = QPushButton("Add")
        self.sync_canvas_btn = QPushButton("Sync")
        self.course_blacklist_btn = QPushButton("Skip")
        self.course_favourites_btn = QPushButton("Pin")

        for button in (
            self.add_course_btn,
            self.sync_canvas_btn,
            self.course_blacklist_btn,
            self.course_favourites_btn,
        ):
            button.setObjectName("ToolbarButton")
            button.setMinimumHeight(44)
            button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setIconSize(QSize(18, 18))

        self.add_course_btn.setIcon(load_icon("plus"))
        self.sync_canvas_btn.setIcon(load_icon("sync"))
        self.course_blacklist_btn.setIcon(load_icon("ban"))
        self.course_favourites_btn.setIcon(load_icon("star"))

        # Give every action the same share of the toolbar width.
        # This avoids the awkward empty gap on the right and keeps the
        # course toolbar visually aligned with the rest of the app.
        course_actions_layout.addWidget(self.add_course_btn, 1)
        course_actions_layout.addWidget(self.sync_canvas_btn, 1)
        course_actions_layout.addWidget(self.course_blacklist_btn, 1)
        course_actions_layout.addWidget(self.course_favourites_btn, 1)

        title_row = QHBoxLayout()
        self.title_row = title_row
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(10)
        title_row.addWidget(self.section_title)
        title_row.addStretch()
        title_row.addWidget(self.resource_refresh_btn)
        title_row.addWidget(self.resource_view_btn)

        self.browser_context_label = QLabel("")
        self.browser_context_label.setObjectName("ScopeContextBar")
        self.browser_context_label.setWordWrap(True)
        self.browser_context_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.browser_context_label.setVisible(False)

        self.browser_stack = QStackedWidget()

        self.item_list = TunedListWidget()
        self.item_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.item_list.setSpacing(8)
        self.item_list.setMouseTracking(True)
        self.browser_delegate = BrowserItemDelegate(
            self.item_list,
            self.effective_theme_mode(),
            self.app_settings.get_accent_color(),
        )
        self.browser_delegate.set_zoom_percent(self.ui_zoom_percent)
        self.item_list.setItemDelegate(self.browser_delegate)

        self.resource_tree = ResourceTreeWidget(self)
        self.resource_tree.setObjectName("ResourceTree")
        self.resource_tree.setHeaderHidden(True)
        self.resource_tree.setRootIsDecorated(False)
        self.resource_tree.setAnimated(True)
        self.resource_tree.setAllColumnsShowFocus(True)
        resource_icon_size = max(18, int(round(24 * (self.ui_zoom_percent / 100.0))))
        self.resource_tree.setIconSize(QSize(resource_icon_size, resource_icon_size))
        self.resource_tree.setIndentation(24)
        self.resource_tree.setUniformRowHeights(True)
        self.resource_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Full-row hover/selection is painted by the tree delegate. Keep Qt's
        # native branch highlight transparent so it cannot form a detached block.
        tree_palette = self.resource_tree.palette()
        tree_palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 0, 0, 0))
        tree_palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.resource_tree.setPalette(tree_palette)

        self.resource_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )

        self.resource_tree.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.browser_stack.addWidget(self.item_list)
        self.browser_stack.addWidget(self.resource_tree)

        middle_layout.addLayout(title_row)
        middle_layout.addWidget(self.course_actions_bar)
        middle_layout.addWidget(self.browser_context_label)
        middle_layout.addWidget(self.browser_stack)

        self.browser_opacity_effect = QGraphicsOpacityEffect(self.browser_stack)
        self.browser_stack.setGraphicsEffect(self.browser_opacity_effect)
        self.browser_animation = QPropertyAnimation(self.browser_opacity_effect, b"opacity", self)
        self.browser_animation.setDuration(160)
        self.browser_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        return middle_panel

    def build_right_panel(self):
        right_panel = QWidget()
        right_panel.setObjectName("RightPanel")
        right_panel.setMinimumWidth(460)
        right_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(14)

        self.detail_title = QLabel("Dashboard")
        self.detail_title.setObjectName("PageTitle")
        self.detail_title.setWordWrap(True)
        self.detail_title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.detail_subtitle = QLabel(self.current_context_label())
        self.detail_subtitle.setObjectName("PageSubtitle")
        self.detail_subtitle.setWordWrap(True)

        self.detail_stack = QStackedWidget()

        self.text_page = self.build_text_page()
        self.image_page = self.build_image_page()
        self.pdf_page = self.build_pdf_page()
        self.media_page = self.build_media_page()
        self.global_dashboard_page = self.build_global_dashboard_page()
        self.course_dashboard_page = self.build_course_dashboard_page()
        self.assignment_dashboard_page = self.build_assignment_dashboard_page()

        self.detail_stack.addWidget(self.text_page)
        self.detail_stack.addWidget(self.image_page)
        self.detail_stack.addWidget(self.pdf_page)
        self.detail_stack.addWidget(self.media_page)
        self.detail_stack.addWidget(self.global_dashboard_page)
        self.detail_stack.addWidget(self.course_dashboard_page)
        self.detail_stack.addWidget(self.assignment_dashboard_page)

        self.detail_opacity_effect = QGraphicsOpacityEffect(self.detail_stack)
        self.detail_stack.setGraphicsEffect(self.detail_opacity_effect)
        self.detail_animation = QPropertyAnimation(self.detail_opacity_effect, b"opacity", self)
        self.detail_animation.setDuration(180)
        self.detail_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        right_layout.addWidget(self.detail_title)
        right_layout.addWidget(self.detail_subtitle)
        right_layout.addWidget(self.detail_stack)

        return right_panel

    def connect_signals(self):
        self.users_btn.clicked.connect(lambda: self.change_section("Users"))
        self.dashboard_btn.clicked.connect(lambda: self.change_section("Dashboard"))
        self.courses_btn.clicked.connect(lambda: self.change_section("Courses"))
        self.assignments_btn.clicked.connect(lambda: self.change_section("Assignments"))
        self.files_btn.clicked.connect(lambda: self.change_section("Files"))
        self.library_btn.clicked.connect(self.open_resource_library)
        self.widgets_btn.clicked.connect(self.open_widgets_manager)
        self.help_btn.clicked.connect(lambda: self.change_section("Help"))
        self.theme_toggle_btn.clicked.connect(self.toggle_theme_mode)
        self.settings_btn.clicked.connect(lambda: self.change_section("Settings"))
        self.undo_btn.clicked.connect(self.undo_last_change)
        self.redo_btn.clicked.connect(self.redo_last_change)
        self.history_toggle.toggled.connect(self.set_history_panel_visible)
        self.sidebar_toggle_btn.clicked.connect(self.toggle_sidebar)
        self.sidebar_title_button.clicked.connect(self.toggle_sidebar)
        self.resource_view_btn.clicked.connect(self.toggle_resource_view_mode)
        self.resource_refresh_btn.clicked.connect(self.manual_refresh_file_explorer)
        self.add_course_btn.clicked.connect(self.add_course_dialog)
        self.sync_canvas_btn.clicked.connect(lambda checked=False: self.sync_canvas_data_for_user(self.get_current_user()))
        self.course_blacklist_btn.clicked.connect(lambda checked=False: self.manage_canvas_course_preferences("blacklist"))
        self.course_favourites_btn.clicked.connect(lambda checked=False: self.manage_canvas_course_preferences("favourites"))

        self.item_list.itemClicked.connect(self.show_list_item_detail)
        self.item_list.itemDoubleClicked.connect(self.open_list_item)
        self.item_list.currentItemChanged.connect(self.update_item_list_selection_state)
        self.item_list.customContextMenuRequested.connect(self.open_item_list_context_menu)

        self.resource_tree.itemClicked.connect(self.show_resource_tree_item_detail)
        self.resource_tree.itemDoubleClicked.connect(self.open_resource_tree_item)
        self.resource_tree.customContextMenuRequested.connect(self.open_resource_tree_context_menu)

        # Course dashboard cards handle their own double-click behaviour.

    # =========================================================
    # RESOURCE TREE STATE PRESERVATION
    # =========================================================

    def resource_tree_item_key(self, item):
        """Return a stable key so expansion/selection survives refreshes."""
        if not item:
            return None

        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        item_type = data.get("type")

        if item_type == "resource":
            resource = data.get("resource", {})
            return f"resource:{resource.get('id')}"

        if item_type == "file_system_entry":
            return f"fs:{data.get('path')}"

        if item_type == "group":
            return f"group:{data.get('resource_type')}:{item.text(0)}"

        if item_type == "scope_info":
            return "scope_info"

        if item_type in {"empty", "empty_folder", "folder_missing", "folder_permission_denied"}:
            return f"{item_type}:{item.text(0)}"

        return f"text:{item.text(0)}"

    def capture_resource_tree_state(self):
        if not hasattr(self, "resource_tree"):
            return None

        expanded_keys = set()
        selected_key = None

        current_item = self.resource_tree.currentItem()
        if current_item:
            selected_key = self.resource_tree_item_key(current_item)

        def walk(item):
            key = self.resource_tree_item_key(item)

            if key and item.isExpanded():
                expanded_keys.add(key)

            for index in range(item.childCount()):
                walk(item.child(index))

        root = self.resource_tree.invisibleRootItem()

        for index in range(root.childCount()):
            walk(root.child(index))

        return {
            "expanded_keys": expanded_keys,
            "selected_key": selected_key,
            "scroll_value": self.resource_tree.verticalScrollBar().value(),
        }

    def restore_resource_tree_state(self, state=None):
        key_to_item = {}

        def walk(item):
            key = self.resource_tree_item_key(item)

            if key:
                key_to_item[key] = item

            for index in range(item.childCount()):
                walk(item.child(index))

        root = self.resource_tree.invisibleRootItem()

        for index in range(root.childCount()):
            walk(root.child(index))

        if state:
            expanded_keys = state.get("expanded_keys", set())

            for key in expanded_keys:
                item = key_to_item.get(key)
                if item:
                    item.setExpanded(True)

            selected_key = state.get("selected_key")
            selected_item = key_to_item.get(selected_key)

            if selected_item:
                self.resource_tree.setCurrentItem(selected_item)
                self.resource_tree.scrollToItem(selected_item)

            self.resource_tree.verticalScrollBar().setValue(state.get("scroll_value", 0))
            return

        # First-load default: expand only high-level groups, not every imported folder.
        for index in range(root.childCount()):
            top_item = root.child(index)
            data = top_item.data(0, Qt.ItemDataRole.UserRole) or {}

            if data.get("type") in {"scope_info", "group"}:
                top_item.setExpanded(True)

    # =========================================================
    # LIGHTWEIGHT TRANSITIONS / FILE VIEW MODE
    # =========================================================

    def animate_detail_change(self):
        if not hasattr(self, "detail_animation"):
            return

        self.detail_animation.stop()
        self.detail_opacity_effect.setOpacity(0.30)
        self.detail_animation.setStartValue(0.30)
        self.detail_animation.setEndValue(1.0)
        self.detail_animation.start()

    def animate_browser_change(self):
        if not hasattr(self, "browser_animation"):
            return

        self.browser_animation.stop()
        self.browser_opacity_effect.setOpacity(0.45)
        self.browser_animation.setStartValue(0.45)
        self.browser_animation.setEndValue(1.0)
        self.browser_animation.start()

    def toggle_sidebar(self):
        if not hasattr(self, "sidebar"):
            return

        if not self.sidebar_is_collapsed:
            self.sidebar_expanded_width = self.clamp_sidebar_expanded_width(max(self.sidebar_collapsed_width, self.sidebar.width()))
            self.app_settings.set_sidebar_width(self.sidebar_expanded_width)

        self.sidebar_is_collapsed = not self.sidebar_is_collapsed
        target_width = self.sidebar_collapsed_width if self.sidebar_is_collapsed else self.sidebar_expanded_width
        start_width = self.sidebar.width()

        if not self.sidebar_is_collapsed:
            self.sidebar.setMinimumWidth(self.sidebar_collapsed_width)
            self.sidebar.setMaximumWidth(self.sidebar_width_bounds()[2])

        self.sidebar_width_animation = QVariantAnimation(self)
        self.sidebar_width_animation.setStartValue(start_width)
        self.sidebar_width_animation.setEndValue(target_width)
        self.sidebar_width_animation.setDuration(220)
        self.sidebar_width_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.sidebar_width_animation.valueChanged.connect(self.animate_sidebar_splitter_width)
        self.sidebar_width_animation.finished.connect(self.finish_sidebar_resize_animation)
        self.sidebar_width_animation.start()

        self.update_sidebar_collapsed_state()

    def finish_sidebar_resize_animation(self):
        if not hasattr(self, "sidebar"):
            return
        if self.sidebar_is_collapsed:
            self.sidebar.setFixedWidth(self.sidebar_collapsed_width)
        else:
            self.sidebar.setMinimumWidth(self.sidebar_collapsed_width)
            self.sidebar.setMaximumWidth(self.sidebar_width_bounds()[2])
            self.sidebar.setMinimumWidth(self.sidebar_collapsed_width)
            self.sidebar.setMaximumWidth(self.sidebar_width_bounds()[2])
            self.sidebar_expanded_width = self.clamp_sidebar_expanded_width(max(self.sidebar_collapsed_width, self.sidebar.width()))
            self.app_settings.set_sidebar_width(self.sidebar_expanded_width)
        if hasattr(self, "sidebar"):
            if self.sidebar_is_collapsed:
                self.sidebar.setFixedWidth(self.sidebar_collapsed_width)
            else:
                self.sidebar.setMinimumWidth(self.sidebar_collapsed_width)
                self.sidebar.setMaximumWidth(self.sidebar_width_bounds()[2])
        self.update_sidebar_collapsed_state()

    def update_sidebar_collapsed_state(self):
        if not hasattr(self, "sidebar_button_specs"):
            return

        collapsed = self.sidebar_is_collapsed

        self.sidebar_title_button.setVisible(not collapsed)
        self.sidebar_toggle_btn.setText("")
        self.sidebar_toggle_btn.setIcon(QIcon(str(app_icon_path())))
        self.sidebar_toggle_btn.setVisible(True)
        self.sidebar_toggle_btn.setToolTip("Toggle sidebar")
        self.sidebar_title_button.setToolTip("Collapse sidebar")

        sidebar_margin = self.zpx(8 if collapsed else 12)
        if hasattr(self, "sidebar_layout"):
            self.sidebar_layout.setContentsMargins(sidebar_margin, self.zpx(12), sidebar_margin, self.zpx(12))
        self.update_sidebar_logo_button_metrics()

        for button, icon_name, label, section_name in self.sidebar_button_specs:
            button.setIcon(load_icon(icon_name))
            if collapsed:
                icon_size = self.zpx(22)
            else:
                icon_size = self.zpx(28) if section_name == "Users" else self.zpx(22)
            button.setIconSize(QSize(icon_size, icon_size))
            button.apply_collapsed_state(collapsed)

            if section_name == "Users":
                display_label = self.current_user_sidebar_label()
                tooltip = self.current_user_sidebar_tooltip()
            else:
                display_label = label
                tooltip = label

            button.setText("" if collapsed else display_label)
            button.setToolTip(tooltip)

            if collapsed:
                compact_width = self.sidebar_collapsed_width - (sidebar_margin * 2)
                button.setFixedWidth(max(compact_width, button.collapsed_width_hint()))
            else:
                button.setMaximumWidth(16777215)
                button.setMinimumWidth(0)
                button.setMinimumSize(0, 0)
                button.updateGeometry()
                button.adjustSize()

        self.update_sidebar_user_label()

        if hasattr(self, "history_panel"):
            self.history_panel.setVisible(self.history_panel_visible and not collapsed)

        if hasattr(self, "theme_toggle_btn"):
            self.theme_toggle_btn.setVisible(not collapsed)
            self.theme_toggle_btn.updateGeometry()
            self.theme_toggle_btn.update()

        if hasattr(self, "sidebar"):
            self.sidebar.updateGeometry()
            self.sidebar.update()

    def current_user_avatar_path(self):
        user = self.get_current_user()
        if not user:
            return ""

        avatar_path = user.get("canvas_avatar_path") or ""
        if avatar_path and Path(avatar_path).exists():
            return avatar_path

        return ""

    def animate_sidebar_splitter_width(self, width):
        if hasattr(self, "sidebar"):
            self.sidebar.setFixedWidth(int(width))
        if hasattr(self, "main_splitter"):
            total = max(1, sum(self.main_splitter.sizes()) or self.main_splitter.width())
            self.main_splitter.setSizes([int(width), max(1, total - int(width))])

    def resizeEvent(self, event):
        self.window_width = max(1, self.width())
        self.window_height = max(1, self.height())
        super().resizeEvent(event)
        if (
            getattr(self, "detail_stack", None)
            and getattr(self, "image_page", None)
            and self.detail_stack.currentWidget() == self.image_page
            and hasattr(self, "update_image_preview_scale")
        ):
            self.update_image_preview_scale()


    def current_user_sidebar_label(self):
        user = self.get_current_user()

        if not user:
            return "Users"

        return user.get("name") or "Unnamed User"

    def current_user_sidebar_school(self):
        user = self.get_current_user()

        if not user:
            return "Select or create a profile"

        return user.get("university") or "School not set"

    def current_user_sidebar_sync_badge(self):
        user = self.get_current_user()

        if not user:
            return "NEW"

        last_sync = self.parse_canvas_sync_datetime(user.get("canvas_last_sync_at"))

        if last_sync:
            now = datetime.now(last_sync.tzinfo) if last_sync.tzinfo else datetime.now()
            if now - last_sync <= timedelta(hours=24):
                return "SYNCED"
            return last_sync.strftime("%d %b %H:%M").upper()

        if user.get("canvas_access_token"):
            return "READY"

        return "SETUP"

    def parse_canvas_sync_datetime(self, value):
        text = str(value or "").strip()

        if not text:
            return None

        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

        if parsed.tzinfo is not None:
            return parsed.astimezone()

        return parsed

    def current_user_sidebar_tooltip(self):
        user = self.get_current_user()

        if not user:
            return "Users"

        name = user.get("name") or "Unnamed User"
        university = user.get("university") or "University not set"
        uid = user.get("uid", user.get("id", "Unknown"))
        return f"Selected user: {name}\nUniversity: {university}\nUID: {uid}"

    def update_sidebar_user_label(self):
        if not hasattr(self, "users_btn"):
            return

        collapsed = getattr(self, "sidebar_is_collapsed", False)
        self.users_btn.setAvatarPath(self.current_user_avatar_path())
        self.users_btn.setProfileDetails(
            "" if collapsed else self.current_user_sidebar_label(),
            "" if collapsed else self.current_user_sidebar_school(),
            "" if collapsed else self.current_user_sidebar_sync_badge(),
        )
        self.users_btn.setToolTip(self.current_user_sidebar_tooltip())

    def update_sidebar_active_state(self, active_section=None):
        if not hasattr(self, "sidebar_button_specs"):
            return

        active_section = active_section or self.current_section

        for button, _, _, section_name in self.sidebar_button_specs:
            is_active = section_name == active_section
            button.setProperty("active", is_active)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def toggle_resource_view_mode(self):
        self.resource_view_mode = "type" if self.resource_view_mode == "natural" else "natural"
        self.update_resource_view_button()

        if self.current_section == "Files":
            self.show_files_section()

    def update_resource_view_button(self):
        if not hasattr(self, "resource_view_btn"):
            return

        if self.resource_view_mode == "natural":
            self.resource_view_btn.setText("View: Natural")
            self.resource_view_btn.setToolTip("Current file browser view mode")
        else:
            self.resource_view_btn.setText("View: By Type")
            self.resource_view_btn.setToolTip("Current file browser view mode")


    def update_course_action_buttons(self):
        """Keep course-level sync controls visible but compact above the list."""
        if not hasattr(self, "sync_canvas_btn"):
            return

        user = self.get_current_user()
        has_user = bool(user)
        blacklist_count = len(user.get("canvas_blacklisted_course_ids", [])) if user else 0
        favourite_count = len(user.get("canvas_favourite_course_ids", [])) if user else 0

        self.add_course_btn.setEnabled(has_user)
        self.sync_canvas_btn.setEnabled(has_user)
        self.course_blacklist_btn.setEnabled(has_user)
        self.course_favourites_btn.setEnabled(has_user)

        self.course_blacklist_btn.setText(f"Skip {blacklist_count}" if blacklist_count else "Skip")
        self.course_favourites_btn.setText(f"Pin {favourite_count}" if favourite_count else "Pin")
        self.sync_canvas_btn.setToolTip("Sync Canvas courses, assignments, and announcements. Finished and blacklisted courses are hidden from the active list.")
        self.course_blacklist_btn.setToolTip("Blacklist Canvas courses so they are skipped during future syncs.")
        self.course_favourites_btn.setToolTip("Favourite Canvas courses so they are pinned at the top of the Courses list.")


    # =========================================================
    # RIGHT PANEL PAGES
    # =========================================================

    def change_section(self, section_name):
        self.stop_media_preview()
        preserving_resource_tree = (
            hasattr(self, "resource_tree")
            and section_name == self.current_section
            and section_name == "Files"
        )
        self.pending_resource_tree_state = (
            self.capture_resource_tree_state() if preserving_resource_tree else None
        )

        self.current_section = section_name
        self.set_dashboard_full_width_mode(section_name == "Dashboard")
        self.update_sidebar_active_state(section_name)
        self.section_title.setText(section_name)
        files_section_active = section_name == "Files"
        self.resource_view_btn.setVisible(files_section_active)
        self.resource_refresh_btn.setVisible(files_section_active)
        if hasattr(self, "course_actions_bar"):
            self.course_actions_bar.setVisible(section_name == "Courses")
            self.update_course_action_buttons()
        if hasattr(self, "browser_context_label"):
            self.browser_context_label.setVisible(files_section_active)
        self.update_resource_view_button()

        if section_name == "Files":
            self.browser_stack.setCurrentWidget(self.resource_tree)
            self.resource_tree.clear()
        else:
            self.browser_stack.setCurrentWidget(self.item_list)
            self.item_list.clear()

        if section_name == "Users":
            self.show_users_section()
        elif section_name == "Dashboard":
            self.show_global_dashboard_section()
        elif section_name == "Courses":
            self.show_courses_section()
        elif section_name == "Assignments":
            self.show_assignments_section()
        elif section_name == "Files":
            self.show_files_section()
        elif section_name == "Settings":
            self.show_settings_section()
        elif section_name == "Help":
            self.show_help_section()

        self.pending_resource_tree_state = None
        self.animate_browser_change()


    def update_item_list_selection_state(self, current=None, previous=None):
        current_item = current or self.item_list.currentItem()
        for row in range(self.item_list.count()):
            item = self.item_list.item(row)
            widget = self.item_list.itemWidget(item)
            if hasattr(widget, "set_selected"):
                widget.set_selected(item is current_item)

    def add_browser_list_item(self, title, data, icon_name, subtitle="", meta="", active=False, badge_text=None, badge_tone=None, avatar_path=None):
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, data)
        item.setData(BrowserItemDelegate.TITLE_ROLE, title)
        item.setData(BrowserItemDelegate.SUBTITLE_ROLE, subtitle)
        item.setData(BrowserItemDelegate.META_ROLE, meta)
        item.setData(BrowserItemDelegate.BADGE_ROLE, badge_text or "")
        item.setData(BrowserItemDelegate.BADGE_TONE_ROLE, badge_tone or "")
        item.setData(BrowserItemDelegate.ACTIVE_ROLE, active)
        item.setData(BrowserItemDelegate.ICON_NAME_ROLE, icon_name)
        item.setData(BrowserItemDelegate.AVATAR_PATH_ROLE, avatar_path or "")
        item.setToolTip("\n".join(part for part in [title, subtitle, meta] if part))
        item.setSizeHint(self.scaled_size(260, 118))
        self.item_list.addItem(item)

        if active:
            self.item_list.setCurrentItem(item)

        return item

    # =========================================================
    # SECTION POPULATION
    # =========================================================

    def show_users_section(self):
        self.item_list.clear()

        self.add_browser_list_item(
            title="Create New User",
            data={"type": "create_user"},
            icon_name="user",
            subtitle="Add a local profile for a learner",
            meta="Name • University • Canvas token placeholder",
        )

        for user in self.vault.get_users():
            course_count = len(self.vault.get_courses(user["id"]))
            university = user.get("university") or "University not set"
            self.add_browser_list_item(
                title=user.get("name", "Unnamed User"),
                data={"type": "user", "user": user},
                icon_name="user",
                subtitle="Selected user" if user["id"] == self.current_user_id else university,
                meta=f"{course_count} course{'s' if course_count != 1 else ''} • UID: {user.get('uid', user['id'])}",
                active=user["id"] == self.current_user_id,
                badge_text="SELECTED" if user["id"] == self.current_user_id else None,
                avatar_path=user.get("canvas_avatar_path") if Path(user.get("canvas_avatar_path") or "").exists() else "",
            )

        current_user = self.get_current_user()
        self.section_title.setText(
            f"Users · {current_user.get('name', 'Unnamed User')}" if current_user else "Users"
        )

        self.update_sidebar_user_label()

        if current_user:
            self.show_user_detail(current_user)
        else:
            self.show_text_page(
                "Users",
                "No selected user",
                "Create a user to start attaching courses, assignments, resources, and future Canvas data.",
            )

    def show_user_detail(self, user):
        courses = self.vault.get_courses(user["id"])
        token = user.get("canvas_access_token", "")
        token_status = "Provided" if token else "Not provided"
        user_folder = self.vault.user_dir(user["id"])
        selected_label = "Selected user details" if user["id"] == self.current_user_id else "User preview"

        profile_card = self.create_details_card(
            "Profile",
            "\n".join([
                f"Name: {user.get('name', 'Unnamed User')}",
                f"University: {user.get('university') or 'Not provided'}",
                f"UID: {user.get('uid', user['id'])}",
                f"Created: {user.get('created_at', 'Unknown')}",
                f"Courses: {len(courses)}",
            ]),
        )

        canvas_card = self.create_details_card(
            "Canvas Setup",
            "\n".join([
                f"Canvas URL: {user.get('canvas_base_url') or 'Not provided'}",
                f"Canvas token status: {token_status}",
                f"Canvas access token: {self.mask_token(token)}",
                f"Last sync: {user.get('canvas_last_sync_at') or 'Never'}",
                f"Last sync result: {user.get('canvas_last_sync_result') or 'Never synced'}",
                f"Blacklisted Canvas courses: {len(user.get('canvas_blacklisted_course_ids', []))}",
                f"Favourite Canvas courses: {len(user.get('canvas_favourite_course_ids', []))}",
            ]),
        )

        actions_card = self.create_canvas_actions_card(user)

        storage_card = self.create_details_card(
            "Vault Storage",
            "\n".join([
                f"User folder: {user_folder}",
                "Folder naming: UID based to avoid duplicate-name conflicts",
            ]),
        )

        self.show_card_page(
            user.get("name", "Unnamed User"),
            selected_label,
            [profile_card, canvas_card, actions_card, storage_card],
        )

    def create_canvas_actions_card(self, user):
        card = QFrame()
        card.setObjectName("DetailsCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("Canvas Actions")
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        body = QLabel("Import Canvas courses and assignments into this user's local vault. Finished Canvas courses are archived automatically.")
        body.setObjectName("CardBody")
        body.setWordWrap(True)
        layout.addWidget(body)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(10)

        edit_button = QPushButton("Edit User / Canvas Settings")
        edit_button.setObjectName("SmallButton")
        edit_button.clicked.connect(lambda checked=False, selected_user=user: self.edit_user_dialog(selected_user))

        sync_button = QPushButton("Sync Canvas Data")
        sync_button.setObjectName("SmallButton")
        sync_button.clicked.connect(lambda checked=False, selected_user=user: self.sync_canvas_data_for_user(selected_user))

        blacklist_button = QPushButton("Course Blacklist")
        blacklist_button.setObjectName("SmallButton")
        blacklist_button.clicked.connect(lambda checked=False, selected_user=user: self.manage_canvas_course_preferences("blacklist", selected_user))

        favourites_button = QPushButton("Favourites")
        favourites_button.setObjectName("SmallButton")
        favourites_button.clicked.connect(lambda checked=False, selected_user=user: self.manage_canvas_course_preferences("favourites", selected_user))

        button_row.addWidget(edit_button)
        button_row.addWidget(sync_button)
        button_row.addWidget(blacklist_button)
        button_row.addWidget(favourites_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        return card


    def show_courses_section(self):
        self.item_list.clear()

        if not self.current_user_id:
            self.show_text_page("No User Selected", "Select or create a user first.", "Go to Users and select a user.")
            return

        self.update_course_action_buttons()
        courses = self.get_visible_courses(self.current_user_id)

        for course in courses:
            assignments = self.vault.get_assignments(self.current_user_id, course["id"])
            resources = self.vault.collect_course_resources(self.current_user_id, course["id"])
            source_label = "Canvas" if course.get("source") == "canvas" else "Manual"
            favourite_label = "Favourite • " if self.course_is_favourite(course, self.current_user_id) else ""
            badge = "CURRENT" if course["id"] == self.current_course_id else ("★ FAV" if self.course_is_favourite(course, self.current_user_id) else None)
            self.add_browser_list_item(
                title=course["code"],
                data={"type": "course", "course": course},
                icon_name="course",
                subtitle=course["name"],
                meta=f"{favourite_label}{source_label} • {len(assignments)} assignments • {len(resources)} resources",
                active=course["id"] == self.current_course_id,
                badge_text=badge,
            )

        if not courses:
            self.add_browser_list_item(
                title="No active courses",
                data={"type": "empty_courses"},
                icon_name="course",
                subtitle="Use the buttons above to add a course or sync Canvas.",
                meta="Archived and blacklisted Canvas courses are hidden from this list",
            )

        self.show_course_dashboard_page(self.get_current_course(), preview_mode=False)

    def show_assignments_section(self):
        self.item_list.clear()

        if not self.current_course_id:
            self.show_text_page("No Course Selected", "Select a course first.", "Use the Dashboard or Courses section to choose a course.")
            return

        general_resources = self.vault.load_resources(self.current_user_id, self.current_course_id, assignment_id=None)
        self.add_browser_list_item(
            title="General Course Resources",
            data={"type": "assignment_general"},
            icon_name="folder",
            subtitle="Shared files for the current course",
            meta=f"{len(general_resources)} resources",
            active=self.current_assignment_id is None,
            badge_text="CURRENT" if self.current_assignment_id is None else None,
        )

        active_assignments = [
            assignment for assignment in self.get_current_assignments()
            if not self.assignment_is_completed(assignment)
        ]
        active_assignment_ids = {assignment["id"] for assignment in active_assignments}

        if self.current_assignment_id and self.current_assignment_id not in active_assignment_ids:
            self.set_current_assignment(None)

        for assignment in active_assignments:
            resources = self.vault.load_resources(self.current_user_id, self.current_course_id, assignment["id"])
            due_text = self.assignment_due_source(assignment)
            due = format_due_datetime(due_text)
            time_left = self.due_countdown_text(due_text)
            status = assignment.get("status") or "Not started"
            source_label = "Canvas" if assignment.get("source") == "canvas" else "Manual"
            self.add_browser_list_item(
                title=assignment["title"],
                data={"type": "assignment", "assignment": assignment},
                icon_name="assignment",
                subtitle=f"Due: {due} • {time_left}",
                meta=f"{source_label} • {status} • {len(resources)} resources",
                active=assignment["id"] == self.current_assignment_id,
                badge_text=self.assignment_due_badge(assignment),
                badge_tone=self.assignment_due_badge_tone(assignment),
            )

        if not active_assignments:
            self.add_browser_list_item(
                title="No active assignments",
                data={"type": "empty_assignments"},
                icon_name="assignment",
                subtitle="Completed assignments are archived",
                meta="Overdue work stays active until you archive it",
            )

        if self.current_assignment_id:
            self.show_assignment_dashboard_page(self.get_current_assignment(), general=False, preview_mode=False)
        else:
            self.show_assignment_dashboard_page(assignment=None, general=True, preview_mode=False)

    def help_topic_cards(self, topic):
        topic_data = HELP_TOPICS.get(topic, HELP_TOPICS["shortcuts"])
        cards = []

        for card_data in topic_data["cards"]:
            if card_data["kind"] == "details":
                cards.append(
                    self.create_details_card(
                        card_data["title"],
                        "\n".join(card_data["rows"]),
                    )
                )
            elif card_data["kind"] == "tips":
                cards.append(
                    self.create_tip_card(
                        card_data["title"],
                        card_data["tips"],
                        subtitle=card_data.get("subtitle"),
                    )
                )

        return topic_data["title"], topic_data["subtitle"], cards

    def show_help_topic(self, topic):
        title, subtitle, cards = self.help_topic_cards(topic)

        for row in range(self.item_list.count()):
            item = self.item_list.item(row)
            data = item.data(Qt.ItemDataRole.UserRole) or {}
            item.setData(BrowserItemDelegate.ACTIVE_ROLE, data.get("topic") == topic)

        self.item_list.viewport().update()
        self.show_card_page(title, subtitle, cards)

    def show_help_section(self):
        self.item_list.clear()
        first_item = None

        for index, topic_key in enumerate(HELP_TOPIC_ORDER):
            topic_data = HELP_TOPICS[topic_key]
            item = self.add_browser_list_item(
                title=topic_data["title"],
                data={"type": "help_topic", "topic": topic_key},
                icon_name=topic_data["icon"],
                subtitle=topic_data["list_subtitle"],
                meta=topic_data["list_meta"],
                active=index == 0,
            )
            first_item = first_item or item

        if first_item:
            self.item_list.setCurrentItem(first_item)
            self.show_help_topic(HELP_TOPIC_ORDER[0])
