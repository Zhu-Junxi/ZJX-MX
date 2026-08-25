from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QEvent, QIODevice, Qt, QUrl, QTimer, QItemSelectionModel, QSize, QMimeData, QPersistentModelIndex
from PySide6.QtGui import QDesktopServices, QPalette, QColor, QPixmap, QDrag, QPainter, QPen
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.helpers import unique_folder_path, unique_path
from core.file_operations import move_path, remove_path, rename_path
from core.file_manager import FileManager, ResourceScope
from core.file_types import TEXT_PREVIEW_SUFFIXES
from core.url_shortcuts import read_url_shortcut
from services.app_logging import log_user_visible_error
from services.file_preview import can_preview_with_handler, preview_kind, structured_preview_html
from core.models import resource_type_display, resource_type_icon
from ui.icons import load_icon, icon_for_resource_type
from ui.scroll_tuning import ScrollTuner
from ui.themed_forms import FormField, ThemedFormDialog, ThemedMessageDialog
from ui.tree_selection_delegate import FullRowSelectionDelegate
from ui.context_menus import AppContextMenu, QuickMenuAction, add_menu_action, add_quick_action_bar, add_separator_if_needed
from services.command_history import FileRenameAction, ResourceLibraryMultiContextAction, SnapshotRestoreError
from app.styles import build_app_stylesheet, scaled_font_px
from ui.keyboard_shortcuts import shortcut_text_from_key_event


_TRANSIENT_RESOURCE_KEYS = {
    "user_name",
    "course_code",
    "course_name",
    "assignment_title",
}



class ResourceLibraryTreeWidget(QTreeWidget):
    """Natural global resource tree with drag/drop support."""

    INTERNAL_MIME_TYPE = "application/x-zjx-resource-library-items"

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self._wheel_handler = None

        self.setHeaderHidden(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setRootIsDecorated(False)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setMouseTracking(True)
        self.setItemDelegate(FullRowSelectionDelegate(self))
        self._drop_indicator_index = QPersistentModelIndex()
        self._drop_indicator_valid = False

    def set_wheel_handler(self, handler):
        self._wheel_handler = handler

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.Wheel and self._wheel_handler and self._wheel_handler(event):
            return True

        return super().viewportEvent(event)

    def wheelEvent(self, event):
        if self._wheel_handler and self._wheel_handler(event):
            return

        super().wheelEvent(event)

    def toggle_expander_at(self, position):
        index = self.indexAt(position)
        if not index.isValid() or not self.model().hasChildren(index):
            return False

        delegate = self.itemDelegate(index)
        if not hasattr(delegate, "arrow_rect_for_index"):
            return False

        if not delegate.arrow_rect_for_index(self, index).contains(position):
            return False

        self.setExpanded(index, not self.isExpanded(index))
        self.viewport().update()
        return True

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.toggle_expander_at(event.position().toPoint()):
            event.accept()
            return

        super().mousePressEvent(event)


    def external_drag_payload(self):
        """Return selected local resource paths and link URLs for drag-out."""
        paths = []
        urls = []
        for item in self.selectedItems() or ([self.currentItem()] if self.currentItem() else []):
            data = item.data(0, Qt.ItemDataRole.UserRole) or {}
            path = None
            if data.get("type") == "file_system_entry":
                path = Path(data.get("path", ""))
            elif data.get("type") == "resource":
                resource = data.get("resource", {}) or {}
                if resource.get("path") and hasattr(self.owner, "vault"):
                    path = self.owner.vault.resource_absolute_path(resource)
                elif resource.get("url"):
                    url = str(resource.get("url") or "").strip()
                    if url and url not in urls:
                        urls.append(url)
            if path and Path(path).exists():
                resolved = Path(path).resolve()
                if resolved not in paths:
                    paths.append(resolved)
        return paths, urls

    def external_drag_paths(self):
        paths, _urls = self.external_drag_payload()
        return paths

    def selected_draggable_items(self):
        items = self.selectedItems() or ([self.currentItem()] if self.currentItem() else [])
        return [
            item for item in items
            if (item.data(0, Qt.ItemDataRole.UserRole) or {}).get("type") in {"resource", "file_system_entry"}
        ]

    def selected_draggable_payloads(self):
        payloads = []
        for item in self.selected_draggable_items():
            data = item.data(0, Qt.ItemDataRole.UserRole) or {}
            if data.get("type") in {"resource", "file_system_entry"}:
                payloads.append(dict(data))
        return payloads

    def startDrag(self, supported_actions):
        """Start a conservative in-library move drag.

        External file drags use native URL negotiation on Windows, which is not
        stable when the same gesture is also meant to be accepted by this tree.
        Keep the Resource Library move payload internal-only so dragging between
        library folders/contexts cannot crash the process.
        """
        payloads = self.selected_draggable_payloads()
        if not payloads:
            return super().startDrag(supported_actions)

        mime_data = QMimeData()
        item_keys = [self.owner.item_key(item) or str(index) for index, item in enumerate(self.selected_draggable_items())]
        mime_data.setData(self.INTERNAL_MIME_TYPE, "\n".join(item_keys).encode("utf-8"))

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        self._active_drag_payload = {
            "drag": drag,
            "mime_data": mime_data,
            "payloads": payloads,
        }

        drag.exec(
            Qt.DropAction.MoveAction,
            Qt.DropAction.MoveAction,
        )
        QTimer.singleShot(1000, lambda: setattr(self, "_active_drag_payload", None))

    def paintEvent(self, event):
        super().paintEvent(event)
        self.paint_drop_indicator()

    def paint_drop_indicator(self):
        index = self._drop_indicator_index
        if not index.isValid() or not self._drop_indicator_valid:
            return

        rect = self.visualRect(index)
        if not rect.isValid():
            return

        rect.setLeft(0)
        rect.setWidth(self.viewport().width())
        rect = rect.adjusted(3, 3, -3, -3)

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        fill = QColor("#2563eb")
        fill.setAlpha(58)
        border = QColor("#38bdf8")
        pen = QPen(border, 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setDashPattern([4, 3])

        painter.setBrush(fill)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 8, 8)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#38bdf8"))
        painter.drawRoundedRect(rect.left(), rect.top(), 5, rect.height(), 3, 3)
        painter.end()

    def clear_drop_indicator(self):
        if self._drop_indicator_index.isValid() or self._drop_indicator_valid:
            self._drop_indicator_index = QPersistentModelIndex()
            self._drop_indicator_valid = False
            self.viewport().update()

    def update_drop_indicator(self, event):
        position = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target_item = self.itemAt(position)
        valid = False
        if target_item is not None and hasattr(self.owner, "target_from_item"):
            _target_folder, target_context = self.owner.target_from_item(target_item)
            valid = target_context is not None

        target_index = QPersistentModelIndex(self.indexAt(position)) if target_item is not None else QPersistentModelIndex()
        changed = target_index != self._drop_indicator_index or valid != self._drop_indicator_valid
        self._drop_indicator_index = target_index
        self._drop_indicator_valid = valid
        if changed:
            self.viewport().update()
        return valid

    def dropEvent(self, event):
        position = event.position().toPoint() if hasattr(event, "position") else event.pos()
        target_item = self.itemAt(position)

        try:
            if event.source() is self:
                payload = getattr(self, "_active_drag_payload", {}) or {}
                source_payloads = payload.get("payloads") or self.selected_draggable_payloads()
                self.clear_drop_indicator()
                if self.owner.handle_internal_payload_drop(source_payloads, target_item):
                    self.clear_drop_indicator()
                    event.setDropAction(Qt.DropAction.MoveAction)
                    event.accept()
                    return
                self.clear_drop_indicator()
                event.ignore()
                return

            mime_data = event.mimeData()
            if mime_data and mime_data.hasUrls():
                paths = [Path(url.toLocalFile()) for url in mime_data.urls() if url.isLocalFile()]
                self.clear_drop_indicator()
                if paths and self.owner.handle_external_drop(paths, target_item):
                    self.clear_drop_indicator()
                    event.setDropAction(Qt.DropAction.CopyAction)
                    event.accept()
                    return
        except Exception as error:
            self.clear_drop_indicator()
            if hasattr(self.owner, "show_library_warning"):
                self.owner.show_library_warning("Drop Failed", "The Resource Library drop could not be completed.", error=error)
            else:
                log_user_visible_error("Drop Failed", "The Resource Library drop could not be completed.", error=error)
                QMessageBox.warning(self.owner, "Drop Failed", "The Resource Library drop could not be completed.")

        self.clear_drop_indicator()
        event.ignore()

    def dragEnterEvent(self, event):
        if self.can_accept_drag_event(event):
            self.update_drop_indicator(event)
            event.setDropAction(Qt.DropAction.MoveAction if event.source() is self else Qt.DropAction.CopyAction)
            event.accept()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self.can_accept_drag_event(event):
            if self.update_drop_indicator(event):
                event.setDropAction(Qt.DropAction.MoveAction if event.source() is self else Qt.DropAction.CopyAction)
                event.accept()
            else:
                event.ignore()
            return
        self.clear_drop_indicator()
        super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self.clear_drop_indicator()
        super().dragLeaveEvent(event)

    def can_accept_drag_event(self, event):
        mime_data = event.mimeData()
        if event.source() is self:
            return bool(mime_data and mime_data.hasFormat(self.INTERNAL_MIME_TYPE))
        return bool(mime_data and mime_data.hasUrls())


class ResourceLibraryWindow(QMainWindow):
    """Natural global resource browser.

    This window intentionally stays simpler than the main Files explorer.
    It supports:
    - global natural browsing by user/course/assignment;
    - recursive folder display;
    - preview/details;
    - open;
    - refresh;
    - drag/drop moves and imports across valid vault locations.

    Advanced edit/delete/rename stays in the main Files explorer where the active
    context is clearer and safer.
    """

    def __init__(self, main_window):
        super().__init__()

        self.main_window = main_window
        self.vault = main_window.vault
        self.file_manager = getattr(main_window, "file_manager", None) or FileManager(self.vault)
        self.filter_mode = "all"
        self.scroll_tuner = ScrollTuner(main_window.get_scroll_speed_percent, main_window.get_smooth_scrolling_enabled, self)
        self._library_drop_targets = []
        self._drop_operation_in_progress = False

        self.setWindowTitle("Resource Library")
        available_geometry = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
        if available_geometry:
            self.resize(
                min(1250, max(840, int(available_geometry.width() * 0.82))),
                min(720, max(560, int(available_geometry.height() * 0.78))),
            )
        else:
            self.resize(1100, 680)
        self.setMinimumSize(760, 500)
        self.setAcceptDrops(True)

        self.apply_theme()

        container = QWidget()
        self.install_library_drop_target(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        header = QFrame()
        header.setObjectName("LibraryHeader")
        self.install_library_drop_target(header)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(2)
        title_host = QWidget()
        title_host.setObjectName("LibraryTitleHost")
        title_host_layout = QVBoxLayout(title_host)
        title_host_layout.setContentsMargins(0, 0, 0, 0)
        title_host_layout.setSpacing(2)

        title = QLabel("Resource Library")
        title.setObjectName("LibraryTitle")
        subtitle = QLabel("Global vault browser for active and archived course resources.")
        subtitle.setObjectName("LibrarySubtitle")
        subtitle.setWordWrap(True)

        title_host_layout.addWidget(title)
        title_host_layout.addWidget(subtitle)
        title_box.addWidget(title_host)

        self.library_filter_combo = QComboBox()
        self.library_filter_combo.setObjectName("LibraryFilter")
        self.library_filter_combo.addItem("All Resources", "all")
        self.library_filter_combo.addItem("Archived Courses", "archived_courses")
        self.library_filter_combo.addItem("Archived Assignments", "archived")
        self.library_filter_combo.setToolTip("Filter the library tree")
        self.library_filter_combo.currentIndexChanged.connect(self.change_filter_mode)

        self.expand_all_btn = QPushButton("Expand")
        self.expand_all_btn.setObjectName("SmallButton")
        self.expand_all_btn.setIcon(load_icon("expand"))
        self.expand_all_btn.setToolTip("Expand every visible item in the library")
        self.expand_all_btn.clicked.connect(self.expand_all_items)

        self.collapse_all_btn = QPushButton("Collapse")
        self.collapse_all_btn.setObjectName("SmallButton")
        self.collapse_all_btn.setIcon(load_icon("collapse"))
        self.collapse_all_btn.setToolTip("Collapse every visible item in the library")
        self.collapse_all_btn.clicked.connect(self.collapse_all_items)
        self.refresh_btn = QPushButton("")
        self.refresh_btn.setIcon(load_icon("refresh"))
        self.refresh_btn.setObjectName("IconButton")
        self.refresh_btn.setToolTip("Refresh Resource Library")
        self.refresh_btn.setFixedWidth(42)
        self.refresh_btn.clicked.connect(self.refresh_tree)

        header_layout.addLayout(title_box, 1)
        header_layout.addWidget(self.library_filter_combo, 0)
        header_layout.addWidget(self.expand_all_btn, 0)
        header_layout.addWidget(self.collapse_all_btn, 0)
        header_layout.addWidget(self.refresh_btn, 0)

        self.tree_panel = QFrame()
        self.tree_panel.setObjectName("LibraryPanel")
        self.install_library_drop_target(self.tree_panel)
        tree_panel_layout = QVBoxLayout(self.tree_panel)
        tree_panel_layout.setContentsMargins(12, 12, 12, 12)
        tree_panel_layout.setSpacing(10)
        tree_header = QHBoxLayout()
        tree_header.setContentsMargins(0, 0, 0, 0)
        tree_header.setSpacing(8)
        tree_title = QLabel("Vault")
        tree_title.setObjectName("LibraryPanelTitle")
        tree_hint = QLabel("Drag resources between scopes")
        tree_hint.setObjectName("LibraryPanelHint")
        tree_header.addWidget(tree_title)
        tree_header.addStretch()
        tree_header.addWidget(tree_hint)

        self.tree = ResourceLibraryTreeWidget(self)
        self.tree.setObjectName("LibraryTree")
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setAnimated(True)
        self.tree.setAllColumnsShowFocus(True)
        zoom = getattr(main_window, "ui_zoom_percent", 100)
        tree_icon_size = max(18, int(round(24 * (zoom / 100.0))))
        self.tree.setIconSize(QSize(tree_icon_size, tree_icon_size))
        self.tree.setIndentation(24)
        self.tree.setUniformRowHeights(True)

        tree_palette = self.tree.palette()
        tree_palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 0, 0, 0))
        tree_palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.tree.setPalette(tree_palette)

        tree_panel_layout.addLayout(tree_header)
        tree_panel_layout.addWidget(self.tree, 1)

        self.preview_panel = QFrame()
        self.preview_panel.setObjectName("LibraryPanel")
        self.install_library_drop_target(self.preview_panel)
        preview_panel_layout = QVBoxLayout(self.preview_panel)
        preview_panel_layout.setContentsMargins(12, 12, 12, 12)
        preview_panel_layout.setSpacing(10)
        preview_header = QHBoxLayout()
        preview_header.setContentsMargins(0, 0, 0, 0)
        preview_header.setSpacing(8)
        preview_title = QLabel("Preview")
        preview_title.setObjectName("LibraryPanelTitle")
        preview_hint = QLabel("Details, media, and quick inspection")
        preview_hint.setObjectName("LibraryPanelHint")
        preview_header.addWidget(preview_title)
        preview_header.addStretch()
        preview_header.addWidget(preview_hint)

        self.preview_stack = QStackedWidget()
        self.preview_stack.setObjectName("LibraryPreviewStack")
        self.install_library_drop_target(self.preview_stack)
        self.details = QTextEdit()
        self.details.setObjectName("LibraryDetails")
        self.details.setReadOnly(True)
        self.details.setFrameShape(QFrame.Shape.NoFrame)
        self.install_library_drop_target(self.details)
        self.preview_stack.addWidget(self.details)

        self.library_image_scroll = QScrollArea()
        self.install_library_drop_target(self.library_image_scroll)
        self.library_image_scroll.setWidgetResizable(True)
        self.library_image_scroll.setFrameShape(QFrame.Shape.NoFrame)
        image_host = QFrame()
        image_host.setObjectName("PreviewCard")
        self.install_library_drop_target(image_host)
        image_layout = QVBoxLayout(image_host)
        image_layout.setContentsMargins(18, 18, 18, 18)
        image_layout.setSpacing(12)
        image_title = QLabel("Image Preview")
        image_title.setObjectName("CardTitle")
        self.library_image_label = QLabel()
        self.library_image_label.setObjectName("ImagePreview")
        self.library_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.library_image_label.setMinimumHeight(420)
        self.library_image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        image_layout.addWidget(image_title)
        image_layout.addWidget(self.library_image_label, 1)
        self.library_image_scroll.setWidget(image_host)
        self.preview_stack.addWidget(self.library_image_scroll)

        self.library_pdf_document = QPdfDocument(self)
        self.library_pdf_view = QPdfView()
        self.library_pdf_view.setObjectName("PdfPreview")
        self.install_library_drop_target(self.library_pdf_view)
        self.library_pdf_view.setDocument(self.library_pdf_document)
        self.library_pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self.library_pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.library_pdf_view.setPageSpacing(10)
        self.preview_stack.addWidget(self.library_pdf_view)

        self.library_media_page = QWidget()
        self.install_library_drop_target(self.library_media_page)
        media_page_layout = QVBoxLayout(self.library_media_page)
        media_page_layout.setContentsMargins(0, 0, 0, 0)
        media_page_layout.setSpacing(0)
        self.library_media_page_layout = media_page_layout
        self.library_media_page.setMaximumHeight(16777215)
        self.library_media_player = QMediaPlayer(self)
        self.library_media_audio = QAudioOutput(self)
        self.library_media_audio.setVolume(0.75)
        self.library_media_player.setAudioOutput(self.library_media_audio)
        media_panel = QFrame()
        media_panel.setObjectName("PreviewCard")
        self.install_library_drop_target(media_panel)
        self.library_media_preview_panel = media_panel
        media_layout = QVBoxLayout(media_panel)
        media_layout.setContentsMargins(18, 18, 18, 18)
        media_layout.setSpacing(14)
        self.library_media_layout = media_layout
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        self.library_media_title = QLabel("Media Preview")
        self.library_media_title.setObjectName("CardTitle")
        self.library_media_open_button = QPushButton("Open Externally")
        self.library_media_open_button.setObjectName("SmallButton")
        self.library_media_open_button.clicked.connect(self.open_selected_item)
        top_row.addWidget(self.library_media_title)
        top_row.addStretch()
        top_row.addWidget(self.library_media_open_button)
        self.library_video_widget = QVideoWidget()
        self.library_video_widget.setObjectName("MediaPreview")
        self.install_library_drop_target(self.library_video_widget)
        self.library_video_widget.setMinimumHeight(360)
        self.library_media_player.setVideoOutput(self.library_video_widget)
        control_row = QHBoxLayout()
        control_row.setContentsMargins(0, 8, 0, 2)
        control_row.setSpacing(14)
        self.library_media_button = QPushButton("Play")
        self.library_media_button.setObjectName("SmallButton")
        self.library_media_button.setMinimumWidth(78)
        self.library_media_button.setMinimumHeight(34)
        self.library_media_button.clicked.connect(self.toggle_library_media)
        self.library_media_slider = QSlider(Qt.Orientation.Horizontal)
        self.library_media_slider.setObjectName("MediaSlider")
        self.library_media_slider.setMinimumWidth(180)
        self.library_media_slider.setMinimumHeight(36)
        self.library_media_slider.sliderMoved.connect(self.seek_library_media_position)
        self.library_media_time = QLabel("00:00 / 00:00")
        self.library_media_time.setObjectName("CardMeta")
        self.library_media_time.setMinimumWidth(104)
        self.library_media_volume = QSlider(Qt.Orientation.Horizontal)
        self.library_media_volume.setObjectName("MediaVolume")
        self.library_media_volume.setRange(0, 100)
        self.library_media_volume.setValue(75)
        self.library_media_volume.setMinimumWidth(120)
        self.library_media_volume.setMaximumWidth(170)
        self.library_media_volume.setMinimumHeight(36)
        self.library_media_volume.valueChanged.connect(self.set_library_media_volume)
        self.library_media_volume_label = QLabel("Volume")
        self.library_media_volume_label.setObjectName("CardMeta")
        self.library_media_volume_label.setMinimumWidth(52)
        control_row.addWidget(self.library_media_button)
        control_row.addWidget(self.library_media_slider, 1)
        control_row.addWidget(self.library_media_time)
        control_row.addSpacing(4)
        control_row.addWidget(self.library_media_volume_label)
        control_row.addWidget(self.library_media_volume)
        media_layout.addLayout(top_row)
        media_layout.addWidget(self.library_video_widget, 1)
        media_layout.addLayout(control_row)
        self.connect_library_media_player_signals()
        media_page_layout.addWidget(media_panel)
        self.preview_stack.addWidget(self.library_media_page)

        preview_panel_layout.addLayout(preview_header)
        preview_panel_layout.addWidget(self.preview_stack, 1)

        self.scroll_tuner.register(self.tree)
        self.scroll_tuner.register(self.details)
        self.scroll_tuner.register(self.library_image_scroll)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("LibrarySplitter")
        self.splitter = splitter
        self.install_library_drop_target(splitter)
        splitter.addWidget(self.tree_panel)
        splitter.addWidget(self.preview_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([340, 820])

        layout.addWidget(header)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(container)

        self.tree.itemClicked.connect(self.show_tree_item_detail)
        self.tree.itemDoubleClicked.connect(self.open_tree_item)
        self.tree.customContextMenuRequested.connect(self.open_context_menu)

        self.setup_shortcuts()
        self.apply_responsive_metrics()
        self.refresh_tree()

    def show_library_warning(self, title, message, *, error=None, context=None):
        if hasattr(self.main_window, "show_user_warning"):
            self.main_window.show_user_warning(title, message, error=error, context=context)
            return
        if error is not None or context:
            log_user_visible_error(title, message, error=error, context=context)
        QMessageBox.warning(self, title, message)

    def zpx(self, value, minimum=1):
        zoom_percent = getattr(self.main_window, "ui_zoom_percent", 100)
        return max(minimum, int(round(value * (zoom_percent / 100.0))))

    def apply_responsive_metrics(self):
        self.setMinimumSize(self.zpx(760, 640), self.zpx(500, 420))
        if hasattr(self, "refresh_btn"):
            self.refresh_btn.setFixedSize(self.zpx(42, 34), self.zpx(38, 32))
            self.refresh_btn.setIconSize(QSize(self.zpx(18, 16), self.zpx(18, 16)))
        for button_name in ("expand_all_btn", "collapse_all_btn"):
            button = getattr(self, button_name, None)
            if button is not None:
                button.setMinimumHeight(self.zpx(38, 32))
                button.setIconSize(QSize(self.zpx(18, 16), self.zpx(18, 16)))
        if hasattr(self, "library_filter_combo"):
            self.library_filter_combo.setMinimumHeight(self.zpx(38, 32))
        if hasattr(self, "library_image_label"):
            self.library_image_label.setMinimumHeight(self.zpx(420, 260))
        if hasattr(self, "library_video_widget"):
            self.library_video_widget.setMinimumHeight(self.zpx(360, 240))
        if hasattr(self, "library_media_button"):
            self.library_media_button.setMinimumWidth(self.zpx(78, 62))
            self.library_media_button.setMinimumHeight(self.zpx(34, 30))
        if hasattr(self, "library_media_open_button"):
            self.library_media_open_button.setMinimumHeight(self.zpx(34, 30))
        if hasattr(self, "library_media_slider"):
            self.library_media_slider.setMinimumWidth(self.zpx(180, 140))
            self.library_media_slider.setMinimumHeight(self.zpx(36, 30))
        if hasattr(self, "library_media_time"):
            self.library_media_time.setMinimumWidth(self.zpx(104, 88))
        if hasattr(self, "library_media_volume"):
            self.library_media_volume.setMinimumWidth(self.zpx(120, 96))
            self.library_media_volume.setMaximumWidth(self.zpx(170, 140))
            self.library_media_volume.setMinimumHeight(self.zpx(36, 30))
        if hasattr(self, "library_media_volume_label"):
            self.library_media_volume_label.setMinimumWidth(self.zpx(52, 42))
        if hasattr(self, "tree"):
            self.tree.setIndentation(self.zpx(24, 18))
        if hasattr(self, "splitter"):
            self.splitter.setHandleWidth(self.zpx(9, 7))

    def closeEvent(self, event):
        self.release_library_preview_handles()
        app = QApplication.instance()
        if getattr(self, "_external_drag_in_progress", False) or getattr(app, "_external_drag_in_progress", False):
            event.ignore()
            QTimer.singleShot(15000, lambda: setattr(self, "_external_drag_in_progress", False))
            return
        super().closeEvent(event)

    def install_library_drop_target(self, widget):
        widget.setAcceptDrops(True)
        widget.installEventFilter(self)
        self._library_drop_targets.append(widget)

    def eventFilter(self, watched, event):
        if watched in getattr(self, "_library_drop_targets", []):
            event_type = event.type()
            if event_type in {
                QEvent.Type.DragEnter,
                QEvent.Type.DragMove,
                QEvent.Type.Drop,
            }:
                return self.handle_library_surface_drag_event(event)

        return super().eventFilter(watched, event)

    def dragEnterEvent(self, event):
        if self.handle_library_surface_drag_event(event):
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self.handle_library_surface_drag_event(event):
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        if self.handle_library_surface_drag_event(event):
            return
        super().dropEvent(event)

    def handle_library_surface_drag_event(self, event):
        if getattr(self, "_drop_operation_in_progress", False):
            event.ignore()
            return True

        if not self.local_paths_from_drag_event(event):
            return False

        event_type = event.type()
        if event_type in {QEvent.Type.DragEnter, QEvent.Type.DragMove}:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            return True

        if event_type == QEvent.Type.Drop:
            paths = self.local_paths_from_drag_event(event)
            target_item = self.tree.currentItem()
            if self.handle_external_drop(paths, target_item):
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
                return True
            event.ignore()
            return True

        return False

    def local_paths_from_drag_event(self, event):
        if event.source() is self.tree:
            return []
        mime_data = event.mimeData()
        if not mime_data or not mime_data.hasUrls():
            return []
        return [Path(url.toLocalFile()) for url in mime_data.urls() if url.isLocalFile()]

    def apply_theme(self):
        theme = self.main_window.effective_theme_mode() if hasattr(self.main_window, "effective_theme_mode") else "dark"
        accent = self.main_window.app_settings.get_accent_color() if hasattr(self.main_window, "app_settings") else "#2563eb"
        if hasattr(self, "tree"):
            zoom = getattr(self.main_window, "ui_zoom_percent", 100)
            tree_icon_size = max(18, int(round(24 * (zoom / 100.0))))
            self.tree.setIconSize(QSize(tree_icon_size, tree_icon_size))
        tree_palette = self.tree.palette() if hasattr(self, "tree") else self.palette()
        tree_palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 0, 0, 0))
        tree_palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        if hasattr(self, "tree"):
            self.tree.setPalette(tree_palette)
            delegate = self.tree.itemDelegate()
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
        for attr_name, icon_name in (("expand_all_btn", "expand"), ("collapse_all_btn", "collapse"), ("refresh_btn", "refresh")):
            button = getattr(self, attr_name, None)
            if button is not None:
                button.setIcon(load_icon(icon_name))
        if hasattr(self, "tree"):
            self.refresh_tree()
        zoom = getattr(self.main_window, "ui_zoom_percent", 100)
        title_size = scaled_font_px(22, zoom, 16)
        subtitle_size = scaled_font_px(13, zoom, 11)
        combo_padding_y = scaled_font_px(7, zoom, 6)
        combo_padding_x = scaled_font_px(12, zoom, 10)
        combo_min_width = scaled_font_px(165, zoom, 140)
        dropdown_width = scaled_font_px(24, zoom, 18)
        splitter_width = scaled_font_px(9, zoom, 7)
        is_light = theme == "light"
        window_bg = "#f4f7fb" if is_light else "#0f1117"
        panel_bg = "#ffffff" if is_light else "#141b2a"
        panel_alt = "#f8fbff" if is_light else "#101827"
        panel_border = "#d7deea" if is_light else "#243042"
        muted = "#64748b" if is_light else "#8ea1bd"
        title = "#0f172a" if is_light else "#f8fafc"
        font_style = self.main_window.app_settings.get_font_style() if hasattr(self.main_window, "app_settings") else "default"
        self.setStyleSheet(build_app_stylesheet(theme, accent, zoom, font_style) + f"""
            QWidget {{
                background-color: {window_bg};
            }}
            QFrame#LibraryHeader {{
                background-color: {panel_bg};
                border: 1px solid {panel_border};
                border-radius: 12px;
            }}
            QWidget#LibraryTitleHost,
            QFrame#LibraryHeader QLabel {{
                background-color: transparent;
                border: none;
            }}
            QLabel#LibraryTitle {{
                color: {title};
                font-size: {title_size}px;
                font-weight: 800;
            }}
            QLabel#LibrarySubtitle {{
                color: {muted};
                font-size: {subtitle_size}px;
            }}
            QFrame#LibraryPanel {{
                background-color: {panel_bg};
                border: 1px solid {panel_border};
                border-radius: 12px;
            }}
            QLabel#LibraryPanelTitle {{
                color: {title};
                font-size: {scaled_font_px(15, zoom, 13)}px;
                font-weight: 800;
                background: transparent;
            }}
            QLabel#LibraryPanelHint {{
                color: {muted};
                font-size: {scaled_font_px(12, zoom, 10)}px;
                font-weight: 650;
                background: transparent;
            }}
            QComboBox#LibraryFilter {{
                background-color: {panel_alt};
                border: 1px solid {panel_border};
                border-radius: 10px;
                color: {title};
                padding: {combo_padding_y}px {combo_padding_x}px;
                min-width: {combo_min_width}px;
                font-weight: 700;
            }}
            QComboBox#LibraryFilter:hover {{
                border: 1px solid {accent};
            }}
            QComboBox#LibraryFilter::drop-down {{
                border: none;
                width: {dropdown_width}px;
            }}
            QStackedWidget#LibraryPreviewStack {{
                background-color: transparent;
                border: none;
            }}
            QTextEdit#LibraryDetails {{
                background-color: {panel_alt};
                border: 1px solid {panel_border};
                border-radius: 12px;
                padding: {scaled_font_px(14, zoom, 10)}px;
                color: {title};
            }}
            QFrame#PreviewCard {{
                background-color: {panel_alt};
                border: 1px solid {panel_border};
                border-radius: 12px;
            }}
            QLabel#ImagePreview,
            QVideoWidget#MediaPreview {{
                background-color: {'#eef4ff' if is_light else '#0b1220'};
                border: 1px solid {panel_border};
                border-radius: 12px;
            }}
            QSplitter#LibrarySplitter::handle {{
                background-color: transparent;
                border: none;
                width: {splitter_width}px;
            }}
            QSplitter#LibrarySplitter::handle:hover {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 transparent,
                    stop:0.44 transparent,
                    stop:0.45 {accent},
                    stop:0.55 {accent},
                    stop:0.56 transparent,
                    stop:1 transparent
                );
                border: none;
            }}
        """)
        self.apply_responsive_metrics()

    # =========================================================
    # Basic item/state helpers
    # =========================================================

    def setup_shortcuts(self):
        self._library_shortcuts = {
            "F5": self.refresh_tree,
            "Return": self.open_selected_item,
            "Enter": self.open_selected_item,
            "Ctrl+E": self.expand_all_items,
            "Ctrl+Shift+E": self.collapse_all_items,
        }
        self.tree.installEventFilter(self)
        self.tree.viewport().installEventFilter(self)

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
        key_sequence = shortcut_text_from_key_event(event)
        callback = getattr(self, "_library_shortcuts", {}).get(key_sequence)
        if not callback:
            return False

        callback()
        event.accept()
        return True

    def change_filter_mode(self):
        self.filter_mode = self.library_filter_combo.currentData() or "all"
        self.refresh_tree()

    def expand_all_items(self):
        self.tree.expandAll()

    def collapse_all_items(self):
        self.tree.collapseAll()

    def clean_resource(self, resource):
        return {
            key: value for key, value in dict(resource).items()
            if key not in _TRANSIENT_RESOURCE_KEYS
        }

    def set_interactive_flags(self, item, can_drag=False, can_drop=False):
        flags = item.flags() | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if can_drag:
            flags |= Qt.ItemFlag.ItemIsDragEnabled
        if can_drop:
            flags |= Qt.ItemFlag.ItemIsDropEnabled
        item.setFlags(flags)
        return item

    def current_item_data(self):
        item = self.tree.currentItem()
        if not item:
            return {}
        return item.data(0, Qt.ItemDataRole.UserRole) or {}

    def selected_action_items(self):
        items = []
        for item in self.tree.selectedItems():
            data = item.data(0, Qt.ItemDataRole.UserRole) or {}
            if data.get("type") in {"resource", "file_system_entry"}:
                items.append(item)
        return items

    def item_key(self, item):
        if not item:
            return None

        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        item_type = data.get("type")

        if item_type == "resource":
            resource = data.get("resource", {})
            return f"resource:{resource.get('id')}"

        if item_type == "file_system_entry":
            return f"fs:{data.get('path')}"

        if item_type == "context":
            context = data.get("context", {})
            return f"context:{context.get('user_id')}:{context.get('course_id')}:{context.get('assignment_id')}"

        return f"node:{item.text(0)}"

    def capture_state(self):
        expanded = set()
        selected = set()

        def walk(item):
            key = self.item_key(item)
            if key:
                if item.isExpanded():
                    expanded.add(key)
                if item.isSelected():
                    selected.add(key)
            for index in range(item.childCount()):
                walk(item.child(index))

        root = self.tree.invisibleRootItem()
        for index in range(root.childCount()):
            walk(root.child(index))

        return {
            "expanded": expanded,
            "selected": selected,
            "scroll": self.tree.verticalScrollBar().value(),
        }

    def restore_state(self, state):
        if not state:
            self.tree.expandToDepth(2)
            return

        expanded = state.get("expanded", set())
        selected = state.get("selected", set())

        def walk(item):
            key = self.item_key(item)
            if key:
                item.setExpanded(key in expanded)
                item.setSelected(key in selected)
            for index in range(item.childCount()):
                walk(item.child(index))

        root = self.tree.invisibleRootItem()
        for index in range(root.childCount()):
            walk(root.child(index))

        self.tree.verticalScrollBar().setValue(state.get("scroll", 0))

    # =========================================================
    # Context/resource/path maps
    # =========================================================

    def context_tuple(self, context):
        return (
            context.get("user_id"),
            context.get("course_id"),
            context.get("assignment_id"),
        )

    def context_from_resource(self, resource):
        return {
            "user_id": resource.get("user_id"),
            "course_id": resource.get("course_id"),
            "assignment_id": resource.get("assignment_id"),
        }

    def context_dir(self, context):
        return self.vault.context_dir(
            context.get("user_id"),
            context.get("course_id"),
            context.get("assignment_id"),
        )

    def resource_scope_from_context(self, context):
        return ResourceScope(
            context.get("user_id"),
            context.get("course_id"),
            context.get("assignment_id"),
        )

    def context_resources(self, context):
        return self.file_manager.metadata.list(self.resource_scope_from_context(context), sync=True)

    def save_context_resources(self, context, resources):
        self.file_manager.metadata.save(self.resource_scope_from_context(context), resources)

    def relative_to_context(self, path, context):
        return str(Path(path).relative_to(self.context_dir(context)))

    def build_resource_path_map(self, resources):
        path_map = {}
        for resource in resources:
            if not resource.get("path"):
                continue
            path = self.vault.resource_absolute_path(resource)
            if not path:
                continue
            try:
                path_key = str(path.resolve())
            except FileNotFoundError:
                path_key = str(path)
            key = (*self.context_tuple(self.context_from_resource(resource)), path_key)
            path_map[key] = resource
        return path_map

    def build_metadata_container_map(self, resources):
        container_map = {}
        for resource in resources:
            if resource.get("path"):
                continue
            container_path = resource.get("container_path")
            context = self.context_from_resource(resource)
            key = (*self.context_tuple(context), container_path or "")
            container_map.setdefault(key, []).append(resource)
        return container_map

    def resource_path_key(self, path, context):
        try:
            path_key = str(Path(path).resolve())
        except FileNotFoundError:
            path_key = str(path)
        return (*self.context_tuple(context), path_key)

    def folder_relative_path(self, folder_path, context):
        try:
            return self.relative_to_context(folder_path, context)
        except ValueError:
            return None

    def resource_is_inside_folder_resource(self, resource, folder_resources):
        if not resource.get("path"):
            return False

        resource_path = self.vault.resource_absolute_path(resource)
        if not resource_path:
            return False

        try:
            resource_path = resource_path.resolve()
        except FileNotFoundError:
            return False

        resource_context = self.context_tuple(self.context_from_resource(resource))

        for folder_resource in folder_resources:
            if folder_resource.get("id") == resource.get("id"):
                continue
            if self.context_tuple(self.context_from_resource(folder_resource)) != resource_context:
                continue
            if folder_resource.get("type") != "local_folder":
                continue

            folder_path = self.vault.resource_absolute_path(folder_resource)
            if not folder_path:
                continue
            try:
                resource_path.relative_to(folder_path.resolve())
                return True
            except (ValueError, FileNotFoundError):
                continue

        return False

    # =========================================================
    # Natural tree building
    # =========================================================

    def assignment_is_archived(self, assignment):
        if not assignment:
            return False

        return bool(assignment.get("completed"))

    def course_is_archived(self, course):
        return bool((course or {}).get("archived"))

    def refresh_tree(self):
        state = self.capture_state() if self.tree.topLevelItemCount() else None
        self.tree.clear()

        archived_only = self.filter_mode == "archived"
        archived_courses_only = self.filter_mode == "archived_courses"
        users = self.vault.get_users()
        all_resources = [self.clean_resource(resource) for resource in self.vault.collect_all_resources()]
        resource_path_map = self.build_resource_path_map(all_resources)
        metadata_container_map = self.build_metadata_container_map(all_resources)

        if not users:
            self.show_library_text("No users found.")
            self.tree.addTopLevelItem(QTreeWidgetItem(["No users found"]))
            return

        visible_user_count = 0
        visible_assignment_count = 0
        visible_course_count = 0

        for user in sorted(users, key=lambda item: item.get("name", "").lower()):
            user_node = QTreeWidgetItem([user.get('name', 'Unknown User')])
            user_node.setIcon(0, load_icon("user"))
            self.set_interactive_flags(user_node, can_drop=False)

            courses = self.vault.get_courses(user.get("id"))
            for course in sorted(courses, key=lambda item: item.get("code", "").lower()):
                assignments = self.vault.get_assignments(user.get("id"), course.get("id"))
                active_assignments = [
                    assignment for assignment in assignments
                    if not self.assignment_is_archived(assignment)
                ]
                archived_assignments = [
                    assignment for assignment in assignments
                    if self.assignment_is_archived(assignment)
                ]
                course_archived = self.course_is_archived(course)

                if archived_only and not archived_assignments:
                    continue
                if archived_courses_only and not course_archived:
                    continue

                course_node = QTreeWidgetItem([f"{course.get('code')} - {course.get('name')}"])
                course_node.setIcon(0, load_icon("course"))
                course_node.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "course",
                    "user_id": user.get("id"),
                    "course": dict(course),
                    "archived": course_archived,
                })
                self.set_interactive_flags(course_node, can_drop=False)
                user_node.addChild(course_node)
                if course_archived:
                    visible_course_count += 1

                if not archived_only:
                    self.add_context_node(
                        parent=course_node,
                        label="General Course Resources",
                        context={
                            "user_id": user.get("id"),
                            "course_id": course.get("id"),
                            "assignment_id": None,
                        },
                        all_resources=all_resources,
                        resource_path_map=resource_path_map,
                        metadata_container_map=metadata_container_map,
                    )

                    for assignment in sorted(active_assignments, key=lambda item: item.get("title", "").lower()):
                        self.add_context_node(
                            parent=course_node,
                            label=f"{assignment.get('title', 'Untitled Assignment')}",
                            context={
                                "user_id": user.get("id"),
                                "course_id": course.get("id"),
                                "assignment_id": assignment.get("id"),
                            },
                            all_resources=all_resources,
                            resource_path_map=resource_path_map,
                            metadata_container_map=metadata_container_map,
                            assignment=assignment,
                            archived=False,
                        )

                if archived_assignments:
                    archived_node = QTreeWidgetItem(["Archived Assignments"])
                    archived_node.setIcon(0, load_icon("assignment"))
                    archived_node.setData(0, Qt.ItemDataRole.UserRole, {"type": "past_assignments"})
                    self.set_interactive_flags(archived_node, can_drop=False)
                    course_node.addChild(archived_node)

                    for assignment in sorted(archived_assignments, key=lambda item: item.get("title", "").lower()):
                        visible_assignment_count += 1
                        self.add_context_node(
                            parent=archived_node,
                            label=f"{assignment.get('title', 'Untitled Assignment')}",
                            context={
                                "user_id": user.get("id"),
                                "course_id": course.get("id"),
                                "assignment_id": assignment.get("id"),
                            },
                            all_resources=all_resources,
                            resource_path_map=resource_path_map,
                            metadata_container_map=metadata_container_map,
                            assignment=assignment,
                            archived=True,
                        )

            if user_node.childCount() > 0:
                self.tree.addTopLevelItem(user_node)
                visible_user_count += 1

        if visible_user_count == 0:
            if archived_only:
                empty_text = "No archived assignments found."
            elif archived_courses_only:
                empty_text = "No archived courses found."
            else:
                empty_text = "No resources found."
            self.show_library_text(empty_text)
            self.tree.addTopLevelItem(QTreeWidgetItem([empty_text]))
            return

        self.restore_state(state)
        if not state:
            self.tree.expandToDepth(2)

        if archived_only:
            self.show_library_text(
                "Archived Assignments\n\n"
                f"Showing {visible_assignment_count} archived assignment scope(s).\n"
                "Use Expand All to inspect every archived resource at once."
            )
        elif archived_courses_only:
            self.show_library_text(
                "Archived Courses\n\n"
                f"Showing {visible_course_count} archived course workspace(s).\n"
                "Right-click an archived course to return it to the active Courses section."
            )
        else:
            self.show_library_text(
                "Resource Library\n\n"
                "Global resource overview across all users, courses, and assignments.\n"
                "Use the filter above to focus on archived courses or assignments."
            )

    
        self.scroll_tuner.refresh()
    def add_context_node(self, parent, label, context, all_resources, resource_path_map, metadata_container_map, assignment=None, archived=False):
        node = QTreeWidgetItem([label])
        node.setIcon(0, load_icon("course" if label == "General Course Resources" else "assignment"))
        data = {
            "type": "context",
            "context": dict(context),
        }
        if assignment:
            data["assignment"] = dict(assignment)
            data["archived"] = bool(archived)
        node.setData(0, Qt.ItemDataRole.UserRole, data)
        self.set_interactive_flags(node, can_drop=True)
        parent.addChild(node)

        resources = [
            resource for resource in all_resources
            if self.context_tuple(self.context_from_resource(resource)) == self.context_tuple(context)
        ]

        folder_resources = [
            resource for resource in resources
            if resource.get("type") == "local_folder" and resource.get("path")
        ]

        # Metadata-only resources with no container show at context root.
        root_metadata = sorted(
            [resource for resource in resources if not resource.get("path") and not resource.get("container_path")],
            key=lambda resource: resource.get("title", "").lower(),
        )

        visible_resources = [
            resource for resource in resources
            if resource.get("path") and not self.resource_is_inside_folder_resource(resource, folder_resources)
        ]

        visible_resources.sort(key=self.natural_resource_sort_key)

        if not visible_resources and not root_metadata:
            empty = QTreeWidgetItem(["Empty"])
            empty.setData(0, Qt.ItemDataRole.UserRole, {"type": "empty"})
            self.set_interactive_flags(empty)
            node.addChild(empty)
            return

        for resource in visible_resources:
            self.add_resource_tree_item(
                parent=node,
                resource=resource,
                resource_path_map=resource_path_map,
                metadata_container_map=metadata_container_map,
            )

        for resource in root_metadata:
            self.add_resource_tree_item(
                parent=node,
                resource=resource,
                resource_path_map=resource_path_map,
                metadata_container_map=metadata_container_map,
            )

    def natural_resource_sort_key(self, resource):
        resource_type = resource.get("type", "")
        is_folder = resource_type == "local_folder"
        return (0 if is_folder else 1, resource.get("title", "").lower())

    def add_resource_tree_item(self, parent, resource, resource_path_map, metadata_container_map):
        resource_type = resource.get("type", "unknown")
        title = resource.get("title", "Untitled")

        item = QTreeWidgetItem([title])
        item.setIcon(0, icon_for_resource_type(resource_type))
        item.setData(0, Qt.ItemDataRole.UserRole, {
            "type": "resource",
            "resource": resource,
            "context": self.context_from_resource(resource),
        })
        self.set_interactive_flags(item, can_drag=True, can_drop=resource_type == "local_folder")
        parent.addChild(item)

        if resource_type == "local_folder":
            folder_path = self.vault.resource_absolute_path(resource)
            self.add_folder_contents(
                parent=item,
                folder_path=folder_path,
                context=self.context_from_resource(resource),
                resource_path_map=resource_path_map,
                metadata_container_map=metadata_container_map,
            )

        return item

    def add_folder_contents(self, parent, folder_path, context, resource_path_map, metadata_container_map):
        folder_path = Path(folder_path) if folder_path else None

        if not folder_path or not folder_path.exists() or not folder_path.is_dir():
            missing = QTreeWidgetItem(["Folder missing"])
            missing.setIcon(0, load_icon("warning"))
            missing.setData(0, Qt.ItemDataRole.UserRole, {"type": "folder_missing"})
            self.set_interactive_flags(missing)
            parent.addChild(missing)
            return

        try:
            children = sorted(folder_path.iterdir(), key=lambda path: (path.is_file(), path.name.lower()))
        except PermissionError:
            denied = QTreeWidgetItem(["Permission denied"])
            denied.setIcon(0, load_icon("warning"))
            denied.setData(0, Qt.ItemDataRole.UserRole, {"type": "folder_permission_denied"})
            self.set_interactive_flags(denied)
            parent.addChild(denied)
            return

        relative_folder = self.folder_relative_path(folder_path, context) or ""
        metadata_key = (*self.context_tuple(context), relative_folder)
        metadata_children = sorted(
            metadata_container_map.get(metadata_key, []),
            key=lambda resource: resource.get("title", "").lower(),
        )

        if not children and not metadata_children:
            empty = QTreeWidgetItem(["Empty folder"])
            empty.setData(0, Qt.ItemDataRole.UserRole, {"type": "empty_folder"})
            self.set_interactive_flags(empty)
            parent.addChild(empty)
            return

        for child_path in children:
            resource = resource_path_map.get(self.resource_path_key(child_path, context))
            if resource:
                self.add_resource_tree_item(
                    parent=parent,
                    resource=resource,
                    resource_path_map=resource_path_map,
                    metadata_container_map=metadata_container_map,
                )
                continue

            item = QTreeWidgetItem([child_path.name])
            item.setIcon(0, load_icon("folder" if child_path.is_dir() else "file"))
            item.setData(0, Qt.ItemDataRole.UserRole, {
                "type": "file_system_entry",
                "path": str(child_path),
                "context": dict(context),
            })
            self.set_interactive_flags(item, can_drag=True, can_drop=child_path.is_dir())
            parent.addChild(item)

            if child_path.is_dir() and not child_path.is_symlink():
                self.add_folder_contents(
                    parent=item,
                    folder_path=child_path,
                    context=context,
                    resource_path_map=resource_path_map,
                    metadata_container_map=metadata_container_map,
                )

        for resource in metadata_children:
            self.add_resource_tree_item(
                parent=parent,
                resource=resource,
                resource_path_map=resource_path_map,
                metadata_container_map=metadata_container_map,
            )

    # =========================================================
    # Preview/details/open
    # =========================================================

    def show_tree_item_detail(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        item_type = data.get("type")

        if item_type == "resource":
            self.preview_resource(data.get("resource", {}))
            return

        if item_type == "file_system_entry":
            self.preview_file_system_entry(Path(data.get("path", "")), data.get("context", {}))
            return

        if item_type == "context":
            self.preview_context(data.get("context", {}))
            return

        self.show_library_text(item.text(0))

    def open_tree_item(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        self.open_data_item(data)

    def open_selected_item(self):
        self.open_data_item(self.current_item_data())

    def open_data_item(self, data):
        item_type = data.get("type")

        if item_type == "resource":
            self.open_resource(data.get("resource", {}))
            return

        if item_type == "file_system_entry":
            path = Path(data.get("path", ""))
            if path.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def open_resource(self, resource):
        resource_type = resource.get("type")
        if resource_type in {"local_file", "local_folder", "note"}:
            path = self.vault.resource_absolute_path(resource)
            if path and path.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            return

        url = resource.get("url")
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def preview_context(self, context):
        resources = self.context_resources(context)
        self.show_library_text(
            "Context\n\n"
            f"User ID: {context.get('user_id')}\n"
            f"Course ID: {context.get('course_id')}\n"
            f"Assignment ID: {context.get('assignment_id') or 'General Course Resources'}\n"
            f"Resources: {len(resources)}\n\n"
            "You can drop files/folders/resources here to move/import them into this context root."
        )

    def preview_resource(self, resource):
        resource_type = resource.get("type")
        lines = [
            "Resource",
            "",
            f"Title: {resource.get('title', 'Untitled')}",
            f"Type: {resource_type_display(resource_type)}",
            f"User ID: {resource.get('user_id')}",
            f"Course ID: {resource.get('course_id')}",
            f"Assignment ID: {resource.get('assignment_id') or 'General Course Resources'}",
            f"Created: {resource.get('created_at', 'Unknown')}",
            f"Updated: {resource.get('updated_at', 'Unknown')}",
        ]

        path = self.vault.resource_absolute_path(resource) if resource.get("path") else None
        if path:
            lines.append(f"Path: {path}")
            if path.exists():
                lines.extend(self.path_extra_details(path))
                self.show_library_path_preview(path, "\n".join(lines))
                return
            else:
                lines.append("Status: Missing")

        if resource.get("url"):
            lines.append(f"URL: {resource.get('url')}")

        self.show_library_text("\n".join(lines))

    def preview_file_system_entry(self, path, context):
        lines = [
            "File-System Entry",
            "",
            f"Name: {path.name}",
            f"Path: {path}",
            f"User ID: {context.get('user_id')}",
            f"Course ID: {context.get('course_id')}",
            f"Assignment ID: {context.get('assignment_id') or 'General Course Resources'}",
        ]

        if path.exists():
            lines.extend(self.path_extra_details(path))
            self.show_library_path_preview(path, "\n".join(lines))
            return
        else:
            lines.append("Status: Missing")

        self.show_library_text("\n".join(lines))

    def show_library_path_preview(self, path, details):
        kind = preview_kind(path)
        self.stop_library_media()

        if kind == "image":
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.preview_stack.setCurrentWidget(self.library_image_scroll)
                self.library_image_label.setPixmap(
                    pixmap.scaled(900, 560, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )
                return

        if kind == "pdf":
            self.preview_stack.setCurrentWidget(self.library_pdf_view)
            self.load_library_pdf_preview_from_memory(path)
            return

        if kind in {"video", "audio"}:
            self.preview_stack.setCurrentWidget(self.library_media_page)
            audio_mode = kind == "audio"
            self.library_media_title.setText("Audio Preview" if audio_mode else "Video Preview")
            self.library_video_widget.setVisible(not audio_mode)
            self.library_video_widget.setMinimumHeight(0 if audio_mode else self.zpx(360, 240))
            self.library_video_widget.setMaximumHeight(0 if audio_mode else 16777215)
            self.library_media_player.setVideoOutput(None if audio_mode else self.library_video_widget)
            self.library_media_layout.setStretch(1, 0 if audio_mode else 1)
            self.library_media_layout.setStretch(2, 0)
            self.library_media_page.setMinimumHeight(150 if audio_mode else 0)
            self.library_media_page.setMaximumHeight(190 if audio_mode else 16777215)
            self.library_media_preview_panel.setMinimumHeight(150 if audio_mode else 0)
            self.library_media_preview_panel.setMaximumHeight(190 if audio_mode else 16777215)
            self.library_video_widget.updateGeometry()
            self.library_media_preview_panel.updateGeometry()
            self.library_media_page.updateGeometry()
            self.library_media_player.stop()
            self.library_media_player.setAudioOutput(self.library_media_audio)
            self.library_media_player.setSource(QUrl.fromLocalFile(str(path)))
            self.set_library_media_volume(self.library_media_volume.value())
            self.library_media_slider.setValue(0)
            self.library_media_time.setText("00:00 / 00:00")
            self.update_library_media_button()
            return

        preview = structured_preview_html(path) if can_preview_with_handler(path) else self.read_text_preview(path)
        if preview:
            self.show_library_text(details, preview)
            return

        self.show_library_text(details + "\n\nPreview is not available for this file type.")

    def show_library_text(self, details, preview=None):
        self.stop_library_media()
        self.preview_stack.setCurrentWidget(self.details)
        if preview and "class=\"structured-preview\"" in preview:
            html = (
                "<pre style='white-space: pre-wrap; font-family: Inter, Segoe UI, sans-serif;'>"
                + escape(details)
                + "</pre><hr>"
                + preview
            )
            self.details.setHtml(html)
            return

        text = details
        if preview:
            text += "\n\n==================== PREVIEW ====================\n\n" + preview
        self.details.setText(text)

    def stop_library_media(self):
        player = getattr(self, "library_media_player", None)
        if player is not None:
            player.stop()

    def seek_library_media_position(self, position):
        player = getattr(self, "library_media_player", None)
        if player is not None:
            player.setPosition(position)

    def process_library_preview_release_events(self, cycles=4):
        app = QApplication.instance()
        if app is not None:
            for _ in range(cycles):
                app.processEvents()

    def connect_library_media_player_signals(self):
        self.library_media_player.positionChanged.connect(self.update_library_media_position)
        self.library_media_player.durationChanged.connect(self.update_library_media_duration)
        self.library_media_player.playbackStateChanged.connect(self.update_library_media_button)

    def rebuild_library_media_backend(self):
        if not hasattr(self, "library_video_widget"):
            return

        volume_value = getattr(getattr(self, "library_media_volume", None), "value", lambda: 75)()

        old_player = getattr(self, "library_media_player", None)
        if old_player is not None:
            try:
                old_player.stop()
                old_player.setSource(QUrl())
                old_player.setVideoOutput(None)
                old_player.setAudioOutput(None)
            except RuntimeError:
                pass
            old_player.deleteLater()

        old_audio = getattr(self, "library_media_audio", None)
        if old_audio is not None:
            old_audio.deleteLater()

        self.library_media_player = QMediaPlayer(self)
        self.library_media_audio = QAudioOutput(self)
        self.library_media_audio.setVolume(max(0.0, min(1.0, float(volume_value or 0) / 100.0)))
        self.library_media_audio.setMuted((volume_value or 0) <= 0)
        self.library_media_player.setAudioOutput(self.library_media_audio)
        self.library_media_player.setVideoOutput(self.library_video_widget)
        self.connect_library_media_player_signals()
        self.update_library_media_button()

    def release_library_preview_handles(self):
        """Release preview-held file handles before moving/deleting files.

        On Windows, QMediaPlayer and QPdfDocument can keep the current file open
        even after playback stops. Clear those sources before resource actions so
        drag/drop moves do not fail with WinError 32.
        """
        player = getattr(self, "library_media_player", None)
        if player is not None:
            player.stop()
            player.setSource(QUrl())
            player.setVideoOutput(None)
            player.setAudioOutput(None)
            self.process_library_preview_release_events()
            self.rebuild_library_media_backend()

        document = getattr(self, "library_pdf_document", None)
        if document is not None:
            if hasattr(document, "close"):
                document.close()
            else:
                document.load("")

        pdf_buffer = getattr(self, "_library_pdf_preview_buffer", None)
        if pdf_buffer is not None:
            pdf_buffer.close()
            pdf_buffer.deleteLater()

        image_label = getattr(self, "library_image_label", None)
        if image_label is not None:
            image_label.clear()

        self._library_pdf_preview_buffer = None
        self._library_pdf_preview_bytes = None

        self.process_library_preview_release_events()

    def release_all_preview_handles(self):
        self.release_library_preview_handles()
        if hasattr(self.main_window, "release_current_preview_handles"):
            self.main_window.release_current_preview_handles()

    def load_library_pdf_preview_from_memory(self, path):
        self.library_pdf_document.close()

        pdf_buffer = getattr(self, "_library_pdf_preview_buffer", None)
        if pdf_buffer is not None:
            pdf_buffer.close()
            pdf_buffer.deleteLater()

        self._library_pdf_preview_bytes = QByteArray(Path(path).read_bytes())
        self._library_pdf_preview_buffer = QBuffer(self)
        self._library_pdf_preview_buffer.setData(self._library_pdf_preview_bytes)
        self._library_pdf_preview_buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self.library_pdf_document.load(self._library_pdf_preview_buffer)

    def toggle_library_media(self):
        if self.library_media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.library_media_player.pause()
        else:
            self.library_media_player.play()

    def update_library_media_position(self, position):
        if not self.library_media_slider.isSliderDown():
            self.library_media_slider.setValue(position)
        self.update_library_media_time()

    def update_library_media_duration(self, duration):
        self.library_media_slider.setRange(0, max(0, duration))
        self.update_library_media_time()

    def set_library_media_volume(self, value):
        volume = max(0.0, min(1.0, float(value or 0) / 100.0))
        self.library_media_audio.setMuted(volume <= 0)
        self.library_media_audio.setVolume(volume)

    def update_library_media_button(self):
        self.library_media_button.setText(
            "Pause" if self.library_media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState else "Play"
        )

    def update_library_media_time(self):
        self.library_media_time.setText(
            f"{self.format_media_time(self.library_media_player.position())} / {self.format_media_time(self.library_media_player.duration())}"
        )

    def format_media_time(self, milliseconds):
        seconds = max(0, int(milliseconds or 0) // 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def path_extra_details(self, path):
        lines = [f"Type: {'Folder' if path.is_dir() else 'File'}"]
        if path.is_file():
            lines.append(f"Size: {path.stat().st_size} bytes")
        if path.is_dir():
            try:
                lines.append(f"Items: {len(list(path.iterdir()))}")
            except PermissionError:
                lines.append("Items: Permission denied")
        lines.append(f"Last modified: {datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
        return lines

    def read_text_preview(self, path, max_chars=20000):
        path = Path(path)
        if not path.is_file() or path.suffix.lower() not in TEXT_PREVIEW_SUFFIXES:
            return ""

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as error:
            return f"Could not read preview: {error}"

        if path.suffix.lower() == ".json":
            try:
                text = json.dumps(json.loads(text), indent=4, ensure_ascii=False)
            except json.JSONDecodeError:
                pass

        if path.suffix.lower() == ".csv":
            lines = text.splitlines()
            text = "\n".join(lines[:40])
            if len(lines) > 40:
                text += f"\n\n... showing first 40 lines out of {len(lines)}"

        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n... preview truncated"

        return text

    # =========================================================
    # Drag/drop target/source handling
    # =========================================================

    def data_from_item(self, item):
        if not item:
            return {}
        return item.data(0, Qt.ItemDataRole.UserRole) or {}

    def target_from_item(self, item, source_kind="file"):
        """Return (destination_folder, target_context).

        destination_folder may be None, meaning context root. In that case each
        moved/imported item chooses its natural top-level directory inside the context.
        """
        cursor = item
        while cursor:
            data = self.data_from_item(cursor)
            item_type = data.get("type")

            if item_type == "context":
                return None, data.get("context", {})

            if item_type == "resource":
                resource = data.get("resource", {})
                context = self.context_from_resource(resource)
                if resource.get("type") == "local_folder":
                    path = self.vault.resource_absolute_path(resource)
                    if path and Path(path).exists() and Path(path).is_dir():
                        return Path(path), context
                # Dropping onto a file/resource should mean dropping beside it.
                if resource.get("path"):
                    path = self.vault.resource_absolute_path(resource)
                    if path and Path(path).exists():
                        return Path(path).parent, context
                return None, context

            if item_type == "file_system_entry":
                path = Path(data.get("path", ""))
                context = data.get("context", {})
                if path.exists() and path.is_dir():
                    return path, context
                if path.exists():
                    return path.parent, context
                return None, context

            cursor = cursor.parent()

        return None, None

    def natural_root_destination(self, path, context, resource_type=None):
        if resource_type == "note":
            return self.vault.context_notes_dir(**context)
        if Path(path).is_dir() or resource_type == "local_folder":
            return self.vault.context_folders_dir(**context)
        return self.vault.context_files_dir(**context)

    def get_source_payloads(self, source_items, target_item):
        payloads = []
        for item in source_items:
            if not item or item is target_item:
                continue
            data = self.data_from_item(item)
            if data.get("type") in {"resource", "file_system_entry"}:
                payloads.append(data)
        return payloads

    def handle_internal_drop(self, source_items, target_item):
        return self.handle_internal_payload_drop(self.get_source_payloads(source_items, target_item), target_item)

    def handle_internal_payload_drop(self, payloads, target_item):
        if getattr(self, "_drop_operation_in_progress", False):
            return False

        target_folder, target_context = self.target_from_item(target_item)
        if target_context is None:
            QMessageBox.information(self, "Move", "Drop items onto a folder or assignment/course context.")
            return False

        payloads = [dict(payload) for payload in payloads if payload and payload.get("type") in {"resource", "file_system_entry"}]
        if not payloads:
            return False

        self._drop_operation_in_progress = True
        self.release_all_preview_handles()
        source_contexts = [self.source_context_for_payload(payload) for payload in payloads]
        contexts = [context for context in source_contexts + [target_context] if context]
        command = self.begin_multi_context_action(f"Move {len(payloads)} Resource Library item(s)", contexts)

        moved_count = 0
        failures = []
        try:
            for payload in payloads:
                try:
                    if payload.get("type") == "resource":
                        if self.move_resource_payload(payload.get("resource", {}), target_folder, target_context):
                            moved_count += 1
                    elif payload.get("type") == "file_system_entry":
                        if self.move_file_system_payload(Path(payload.get("path", "")), payload.get("context", {}), target_folder, target_context):
                            moved_count += 1
                except Exception as error:
                    failures.append({"item": payload.get("path") or (payload.get("resource") or {}).get("title"), "error": repr(error)})

            self.finish_multi_context_action(command, changed=moved_count > 0)
            if moved_count:
                self.refresh_after_action()
            if failures:
                self.show_library_warning(
                    "Move Partially Failed",
                    f"{len(failures)} item(s) could not be moved.",
                    context={"failures": failures[:10]},
                )
            return moved_count > 0
        except Exception:
            self.discard_multi_context_action(command)
            raise
        finally:
            self._drop_operation_in_progress = False

    def handle_external_drop(self, paths, target_item):
        if getattr(self, "_drop_operation_in_progress", False):
            return False

        target_folder, target_context = self.target_from_item(target_item)
        if target_context is None:
            QMessageBox.information(self, "Import", "Drop external files/folders onto a folder or assignment/course context.")
            return False

        self._drop_operation_in_progress = True
        self.release_library_preview_handles()
        command = self.begin_multi_context_action(f"Import {len(paths)} Resource Library item(s)", [target_context])
        imported_count = 0
        failures = []
        try:
            for source in paths:
                try:
                    source = Path(source)
                    target_scope = ResourceScope(
                        target_context.get("user_id"),
                        target_context.get("course_id"),
                        target_context.get("assignment_id"),
                    )
                    if source.is_file():
                        shortcut = read_url_shortcut(source)
                        destination_parent = target_folder or self.natural_root_destination(
                            source,
                            target_context,
                            resource_type=shortcut["type"] if shortcut else None,
                        )
                        self.file_manager.import_file(
                            source,
                            target_scope,
                            destination_parent=destination_parent,
                        )
                        imported_count += 1
                    elif source.is_dir():
                        destination_parent = target_folder or self.natural_root_destination(source, target_context)
                        self.file_manager.import_folder(
                            source,
                            target_scope,
                            destination_parent=destination_parent,
                        )
                        imported_count += 1
                except Exception as error:
                    failures.append({"source": str(source), "error": repr(error)})

            self.finish_multi_context_action(command, changed=imported_count > 0)
            if imported_count:
                self.refresh_after_action()
            if failures:
                self.show_library_warning(
                    "Import Partially Failed",
                    f"{len(failures)} item(s) could not be imported.",
                    context={"failures": failures[:10]},
                )
            return imported_count > 0
        except Exception:
            self.discard_multi_context_action(command)
            raise
        finally:
            self._drop_operation_in_progress = False

    def source_context_for_payload(self, payload):
        if payload.get("type") == "resource":
            return self.context_from_resource(payload.get("resource", {}))
        if payload.get("type") == "file_system_entry":
            return payload.get("context", {})
        return None

    # =========================================================
    # Move/import internals
    # =========================================================

    def safe_move_path(self, source_path, destination_parent):
        source_path = Path(source_path)
        destination_parent = Path(destination_parent)
        destination_parent.mkdir(parents=True, exist_ok=True)

        if not source_path.exists():
            raise ValueError(f"Source no longer exists: {source_path}")

        if source_path.is_dir():
            try:
                destination_parent.resolve().relative_to(source_path.resolve())
                raise ValueError("You cannot move a folder into itself or one of its own subfolders.")
            except ValueError as error:
                if "cannot move" in str(error):
                    raise

        if source_path.parent.resolve() == destination_parent.resolve():
            return source_path

        self.release_library_preview_handles()
        if hasattr(self.main_window, "release_file_explorer_handles"):
            self.main_window.release_file_explorer_handles()

        destination = unique_folder_path(destination_parent, source_path.name) if source_path.is_dir() else unique_path(destination_parent, source_path.name)
        move_path(source_path, destination)
        return destination

    def move_resource_payload(self, resource, target_folder, target_context):
        if not resource:
            return False

        source_context = self.context_from_resource(resource)
        resource_type = resource.get("type")

        # Metadata-only resources move visually through container metadata.
        if not resource.get("path"):
            return self.move_metadata_resource(resource, source_context, target_folder, target_context)

        source_path = self.vault.resource_absolute_path(resource)
        if not source_path or not Path(source_path).exists():
            raise ValueError(f"Resource file missing: {resource.get('title', 'Untitled')}")

        old_path = Path(source_path)
        destination_parent = target_folder or self.natural_root_destination(source_path, target_context, resource_type=resource_type)
        new_path = self.safe_move_path(source_path, destination_parent)

        if resource_type == "local_folder":
            self.update_nested_resources_after_folder_move(
                source_context=source_context,
                target_context=target_context,
                old_folder_path=old_path,
                new_folder_path=Path(new_path),
                exclude_resource_id=resource.get("id"),
            )

        if self.context_tuple(source_context) != self.context_tuple(target_context):
            self.remove_resource_from_context(resource, source_context)
            resource = dict(resource)
            resource["user_id"] = target_context.get("user_id")
            resource["course_id"] = target_context.get("course_id")
            resource["assignment_id"] = target_context.get("assignment_id")
            resource["path"] = self.relative_to_context(new_path, target_context)
            resource.pop("container_path", None)
            self.append_resource_to_context(resource, target_context)
        else:
            resource["path"] = self.relative_to_context(new_path, target_context)
            resource.pop("container_path", None)
            self.file_manager.metadata.update(resource)

        return True

    def move_metadata_resource(self, resource, source_context, target_folder, target_context):
        resource = dict(resource)
        if target_folder:
            resource["container_path"] = self.relative_to_context(target_folder, target_context)
        else:
            resource.pop("container_path", None)

        if self.context_tuple(source_context) != self.context_tuple(target_context):
            self.remove_resource_from_context(resource, source_context)
            resource["user_id"] = target_context.get("user_id")
            resource["course_id"] = target_context.get("course_id")
            resource["assignment_id"] = target_context.get("assignment_id")
            self.append_resource_to_context(resource, target_context)
        else:
            self.file_manager.metadata.update(resource)

        return True

    def move_file_system_payload(self, source_path, source_context, target_folder, target_context):
        source_path = Path(source_path)
        old_path = Path(source_path)
        destination_parent = target_folder or self.natural_root_destination(source_path, target_context)
        new_path = self.safe_move_path(source_path, destination_parent)

        if old_path.is_dir():
            self.update_nested_resources_after_folder_move(
                source_context=source_context,
                target_context=target_context,
                old_folder_path=old_path,
                new_folder_path=Path(new_path),
                exclude_resource_id=None,
            )

        return True

    def relative_path_inside_folder(self, path, folder_path):
        try:
            return Path(path).resolve().relative_to(Path(folder_path).resolve())
        except (ValueError, FileNotFoundError):
            return None

    def relative_container_inside_folder(self, container_path, old_folder_relative):
        if not container_path or not old_folder_relative:
            return None

        container = Path(container_path)
        old_folder = Path(old_folder_relative)

        if container == old_folder:
            return Path()

        try:
            return container.relative_to(old_folder)
        except ValueError:
            return None

    def update_nested_resources_after_folder_move(self, source_context, target_context, old_folder_path, new_folder_path, exclude_resource_id=None):
        """Keep managed children valid after a folder is moved.

        Folder resources can contain other registered resources and metadata-only
        resources. When the folder moves, those nested resources must follow the
        folder instead of keeping stale paths/container metadata.
        """
        source_resources = list(self.context_resources(source_context))
        old_folder_path = Path(old_folder_path)
        new_folder_path = Path(new_folder_path)

        try:
            old_folder_relative = self.relative_to_context(old_folder_path, source_context)
        except ValueError:
            old_folder_relative = None

        try:
            new_folder_relative = self.relative_to_context(new_folder_path, target_context)
        except ValueError:
            new_folder_relative = None

        for child_resource in source_resources:
            if child_resource.get("id") == exclude_resource_id:
                continue

            if child_resource.get("path"):
                child_path = self.vault.resource_absolute_path(child_resource)
                relative_inside = self.relative_path_inside_folder(child_path, old_folder_path)
                if relative_inside is None:
                    continue

                new_child_path = new_folder_path / relative_inside
                self.move_resource_metadata_to_context(
                    resource=child_resource,
                    source_context=source_context,
                    target_context=target_context,
                    new_path=new_child_path,
                    new_container_path=None,
                )
                continue

            container_inside = self.relative_container_inside_folder(
                child_resource.get("container_path"),
                old_folder_relative,
            )
            if container_inside is None:
                continue

            if new_folder_relative is None:
                continue

            new_container = str(Path(new_folder_relative) / container_inside) if str(container_inside) != "." else new_folder_relative
            self.move_resource_metadata_to_context(
                resource=child_resource,
                source_context=source_context,
                target_context=target_context,
                new_path=None,
                new_container_path=new_container,
            )

    def move_resource_metadata_to_context(self, resource, source_context, target_context, new_path=None, new_container_path=None):
        updated = dict(resource)
        updated["user_id"] = target_context.get("user_id")
        updated["course_id"] = target_context.get("course_id")
        updated["assignment_id"] = target_context.get("assignment_id")

        if new_path is not None:
            updated["path"] = self.relative_to_context(new_path, target_context)
            updated.pop("container_path", None)
        elif new_container_path is not None:
            updated["container_path"] = new_container_path

        if self.context_tuple(source_context) != self.context_tuple(target_context):
            self.remove_resource_from_context(resource, source_context)
            self.append_resource_to_context(updated, target_context)
        else:
            self.file_manager.metadata.update(updated)

        return updated

    def remove_resource_from_context(self, resource, context):
        resources = self.context_resources(context)
        resources = [item for item in resources if item.get("id") != resource.get("id")]
        self.save_context_resources(context, resources)

    def append_resource_to_context(self, resource, context):
        resources = self.context_resources(context)
        resource["updated_at"] = datetime.now().isoformat(timespec="seconds")
        resources.append(resource)
        self.save_context_resources(context, resources)
        return resource

    # =========================================================
    # Undo snapshot integration
    # =========================================================

    def begin_multi_context_action(self, description, contexts):
        context_dirs = [self.context_dir(context) for context in contexts if context]
        command = ResourceLibraryMultiContextAction(description, context_dirs)
        command.capture_before()
        return command

    def finish_multi_context_action(self, command, changed):
        if not command:
            return
        command.capture_after()
        if changed and command.has_changes():
            self.main_window.command_history.push_done(command)
            self.main_window.update_history_panel()
        else:
            command.cleanup()

    def discard_multi_context_action(self, command):
        if command:
            command.cleanup()

    # =========================================================
    # Context menu and refresh integration
    # =========================================================

    def add_menu_action(self, menu, label, icon_name=None, callback=None, enabled=True, shortcut=None):
        return add_menu_action(menu, label, icon_name, callback, enabled, shortcut)


    def show_selected_in_file_explorer(self):
        data = self.current_item_data()
        item_type = data.get("type")

        if item_type == "resource":
            resource = data.get("resource", {})
            path = self.vault.resource_absolute_path(resource) if resource.get("path") else None
        elif item_type == "file_system_entry":
            path = Path(data.get("path", ""))
        else:
            path = None

        if not path:
            QMessageBox.information(self, "No Local File", "This item does not have a local file or folder.")
            return

        path = Path(path)
        if not path.exists():
            QMessageBox.warning(self, "Missing Item", "The local file or folder no longer exists.")
            return

        target = path if path.is_dir() else path.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def path_from_data(self, data):
        if not data:
            return None

        item_type = data.get("type")
        if item_type == "resource":
            resource = data.get("resource", {})
            if resource.get("path") and resource.get("type") in {"local_file", "local_folder", "note"}:
                return self.vault.resource_absolute_path(resource)
            return None

        if item_type == "file_system_entry":
            return Path(data.get("path", ""))

        return None

    def is_text_editable_data(self, data):
        path = self.path_from_data(data)
        return bool(path and Path(path).exists() and Path(path).is_file() and Path(path).suffix.lower() in TEXT_PREVIEW_SUFFIXES)

    def edit_selected_text_item(self):
        data = self.current_item_data()
        item_type = data.get("type")

        if item_type == "resource":
            self.main_window.open_text_editor_for_resource(data.get("resource", {}))
            return

        if item_type == "file_system_entry":
            self.main_window.open_text_editor_for_path(
                Path(data.get("path", "")),
                context=data.get("context", {}),
            )

    def edit_selected_item(self):
        data = self.current_item_data()
        item_type = data.get("type")

        if item_type == "resource":
            self.main_window.edit_resource(data.get("resource", {}))
            self.refresh_after_action()
            return

        if item_type == "file_system_entry":
            self.rename_file_system_entry(Path(data.get("path", "")), data.get("context", {}))

    def rename_file_system_entry(self, path, context):
        path = Path(path)
        if not path.exists():
            QMessageBox.warning(self, "Missing Item", "This file or folder no longer exists.")
            return

        values = ThemedFormDialog.ask(
            self,
            title="Rename Item",
            subtitle="Update this file or folder name.",
            fields=[
                FormField("name", "New name", default=path.name, required=True),
            ],
            accept_text="Rename",
        )
        if not values:
            return

        new_name = values["name"].strip()
        if path.is_file() and "." not in Path(new_name).name and path.suffix:
            new_name += path.suffix

        new_path = path.with_name(new_name)
        if new_path.exists():
            QMessageBox.warning(self, "Rename Failed", "A file or folder with that name already exists.")
            return

        try:
            self.release_all_preview_handles()
            action = FileRenameAction(
                path,
                new_path,
                description=f"Renamed file: {path.name} -> {new_path.name}",
            )
            self.main_window.command_history.perform(action)
            self.main_window.update_history_panel()
            self.refresh_after_action()
        except Exception as error:
            self.show_library_warning(
                "Rename Failed",
                "The item could not be renamed.",
                error=error,
                context={"path": path, "new_path": new_path},
            )

    def move_selected_item_to_context_root(self):
        payloads = [self.data_from_item(item) for item in self.selected_action_items()]
        payloads = [payload for payload in payloads if payload.get("type") in {"resource", "file_system_entry"}]
        if not payloads:
            return

        contexts = [self.source_context_for_payload(payload) for payload in payloads]
        self.release_library_preview_handles()
        command = self.begin_multi_context_action(f"Move {len(payloads)} item(s) to root", contexts)
        moved_count = 0
        failures = []
        try:
            for payload in payloads:
                try:
                    source_context = self.source_context_for_payload(payload)
                    if payload.get("type") == "resource":
                        if self.move_resource_payload(payload.get("resource", {}), None, source_context):
                            moved_count += 1
                    elif payload.get("type") == "file_system_entry":
                        if self.move_file_system_payload(Path(payload.get("path", "")), payload.get("context", {}), None, source_context):
                            moved_count += 1
                except Exception as error:
                    failures.append({"item": payload.get("path") or (payload.get("resource") or {}).get("title"), "error": repr(error)})

            self.finish_multi_context_action(command, changed=moved_count > 0)
            if moved_count:
                self.refresh_after_action()
            if failures:
                self.show_library_warning(
                    "Move Failed",
                    f"{len(failures)} item(s) could not be moved.",
                    context={"failures": failures[:10]},
                )
        except Exception:
            self.discard_multi_context_action(command)
            raise

    def delete_selected_items(self):
        items = self.selected_action_items()
        if not items:
            return

        resources = []
        file_payloads = []
        for item in items:
            data = self.data_from_item(item)
            if data.get("type") == "resource":
                resources.append(data.get("resource", {}))
            elif data.get("type") == "file_system_entry":
                file_payloads.append(data)

        changed = False
        self.release_library_preview_handles()
        if resources:
            if len(resources) == 1:
                changed = self.main_window.delete_resource_from_library(resources[0]) or changed
            else:
                changed = self.main_window.delete_resources_from_library(resources) or changed

        if file_payloads:
            reply = QMessageBox.question(
                self,
                "Delete File Items",
                f"Delete {len(file_payloads)} unmanaged file/folder item(s) from the vault?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                contexts = [payload.get("context", {}) for payload in file_payloads]
                command = self.begin_multi_context_action(f"Delete {len(file_payloads)} file item(s)", contexts)
                try:
                    for payload in file_payloads:
                        path = Path(payload.get("path", ""))
                        remove_path(path)
                    self.finish_multi_context_action(command, changed=True)
                    changed = True
                except Exception as error:
                    self.discard_multi_context_action(command)
                    self.show_library_warning(
                        "Delete Failed",
                        "The selected item(s) could not be deleted.",
                        error=error,
                        context={"items": [payload.get("path") for payload in file_payloads[:10]]},
                    )

        if changed:
            self.refresh_after_action()

    def unarchive_selected_assignment(self):
        data = self.current_item_data()
        if data.get("type") != "context" or not data.get("assignment"):
            return

        context = data.get("context", {})
        assignment = data.get("assignment", {})
        user_id = context.get("user_id")
        course_id = context.get("course_id")
        assignment_id = context.get("assignment_id")
        if not user_id or not course_id or not assignment_id:
            return

        should_unarchive = ThemedMessageDialog.confirm(
            self,
            title="Unarchive Assignment?",
            subtitle=assignment.get("title", "Untitled assignment"),
            body=(
                "This assignment will return to the active list with no due date. "
                "You can edit it afterwards to add a new due date."
            ),
            accept_text="Unarchive",
            cancel_text="Keep Archived",
            minimum_width=620,
        )
        if not should_unarchive:
            return

        command = self.begin_multi_context_action(
            f"Unarchive {assignment.get('title', 'assignment')}",
            [context],
        )
        try:
            self.vault.update_assignment_fields(
                user_id,
                course_id,
                assignment_id,
                completed=False,
                status="Not started",
                completed_at="",
                due_date="",
                canvas_due_at="",
                due_date_overridden_by_user=True,
                archive_prompted_due_text="",
                archive_prompted_at="",
            )
            self.finish_multi_context_action(command, changed=True)
            if self.main_window.current_course_id == course_id and self.main_window.current_assignment_id is None:
                self.main_window.set_current_assignment(assignment_id)
            self.refresh_after_action()
        except Exception:
            self.discard_multi_context_action(command)
            raise

    def unarchive_selected_course(self):
        data = self.current_item_data()
        if data.get("type") != "course" or not data.get("archived"):
            return

        course = data.get("course", {})
        user_id = data.get("user_id")
        if not user_id or not course:
            return

        should_unarchive = ThemedMessageDialog.confirm(
            self,
            title="Unarchive Course?",
            subtitle=f"{course.get('code', '')} - {course.get('name', 'Untitled course')}",
            body="This course will return to the active Courses section with its existing assignments and resources intact.",
            accept_text="Unarchive",
            cancel_text="Keep Archived",
            minimum_width=620,
        )
        if not should_unarchive:
            return

        self.main_window.set_course_archived(course, False, user_id=user_id)
        if self.main_window.current_user_id == user_id:
            self.main_window.set_current_course(course.get("id"))
        self.refresh_after_action()

    def open_context_menu(self, position):
        clicked_item = self.tree.itemAt(position)
        if clicked_item:
            if clicked_item.isSelected():
                self.tree.selectionModel().setCurrentIndex(
                    self.tree.indexFromItem(clicked_item),
                    QItemSelectionModel.SelectionFlag.NoUpdate,
                )
            else:
                self.tree.clearSelection()
                clicked_item.setSelected(True)
                self.tree.setCurrentItem(clicked_item)
        else:
            self.tree.clearSelection()
            self.tree.setCurrentItem(None)

        menu = AppContextMenu(self)

        data = self.data_from_item(clicked_item) if clicked_item else {}
        item_type = data.get("type")
        selected_count = len(self.selected_action_items()) if clicked_item else 0
        selected_is_manageable = selected_count == 1 and item_type in {"resource", "file_system_entry"}
        selected_local_path = self.path_from_data(data)
        has_selection = selected_count > 0
        selected_is_archived_assignment = item_type == "context" and bool(data.get("assignment")) and bool(data.get("archived"))
        selected_is_archived_course = item_type == "course" and bool(data.get("archived"))

        # Compact top command strip for the library. Unsupported commands are
        # intentionally omitted here; this window does not own copy/cut.
        quick_actions = [
            QuickMenuAction("Open", "open", self.open_selected_item, selected_is_manageable, "Enter"),
            QuickMenuAction("Rename / Edit", "edit", self.edit_selected_item, selected_is_manageable, "F2"),
            QuickMenuAction("Delete", "delete", self.delete_selected_items, has_selection, "Del"),
            QuickMenuAction("Refresh", "refresh", self.refresh_tree, True, "F5"),
        ]
        add_quick_action_bar(menu, quick_actions, self)
        add_separator_if_needed(menu)

        if selected_count > 1:
            self.add_menu_action(menu, f"Delete {selected_count} Items", "delete", self.delete_selected_items)
        elif selected_is_manageable:
            self.add_menu_action(menu, "Open", "open", self.open_selected_item, shortcut="Enter")
            if self.is_text_editable_data(data):
                self.add_menu_action(menu, "Edit Text", "edit", self.edit_selected_text_item)
            self.add_menu_action(menu, "Move To Root", "move", self.move_selected_item_to_context_root)
            if selected_local_path and Path(selected_local_path).exists():
                self.add_menu_action(menu, "Open File Location", "folder", self.show_selected_in_file_explorer)
            add_separator_if_needed(menu)
        elif selected_is_archived_assignment:
            self.add_menu_action(menu, "Unarchive Assignment", "check", self.unarchive_selected_assignment)
            add_separator_if_needed(menu)
        elif selected_is_archived_course:
            self.add_menu_action(menu, "Unarchive Course", "check", self.unarchive_selected_course)
            add_separator_if_needed(menu)

        self.add_menu_action(menu, "Refresh", "refresh", self.refresh_tree, shortcut="F5")
        self.add_menu_action(menu, "Expand All", "expand", self.expand_all_items, shortcut="Ctrl+E")
        self.add_menu_action(menu, "Collapse All", "collapse", self.collapse_all_items, shortcut="Ctrl+Shift+E")
        archive_label = "Show All" if self.filter_mode in {"archived", "archived_courses"} else "Archived Assignments"
        self.add_menu_action(menu, archive_label, "archive", self.toggle_archived_filter)

        menu.exec(self.tree.mapToGlobal(position))

    def toggle_archived_filter(self):
        target = "all" if self.filter_mode in {"archived", "archived_courses"} else "archived"
        self.filter_mode = target
        index = self.library_filter_combo.findData(target)
        if index >= 0:
            self.library_filter_combo.setCurrentIndex(index)
        else:
            self.refresh_tree()

    def refresh_after_action(self):
        self.refresh_tree()
        if self.main_window.current_section == "Files":
            self.main_window.refresh_resource_tree_preserving_state()
        elif self.main_window.current_section in {"Courses", "Assignments"}:
            self.main_window.change_section(self.main_window.current_section)
        self.main_window.update_history_panel()
