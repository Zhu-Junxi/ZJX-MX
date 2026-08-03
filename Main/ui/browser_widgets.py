from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QSize, QRect, QTimer, QPoint
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QPixmap, QPainterPath
from PySide6.QtWidgets import QApplication, QAbstractItemView, QLabel, QListWidget, QRubberBand, QStyle, QStyledItemDelegate, QTreeWidget

from ui.icons import load_icon
from ui.drag_export import run_safe_file_drag, run_safe_link_drag
from ui.file_explorer_dragdrop import (
    build_drag_preview_pixmap,
    drop_target_from_item,
    external_payload,
    local_paths_from_mime,
    selected_payloads,
)
from ui.tree_selection_delegate import FullRowSelectionDelegate


class BrowserItemDelegate(QStyledItemDelegate):
    """Paints the middle-browser list without per-row QWidget objects.

    Normal navigation items are painted as cards. Settings items use a more
    compact menu layout so the Settings page matches the simple grouped design
    used before the browser-card infrastructure was introduced.
    """

    TITLE_ROLE = Qt.ItemDataRole.UserRole + 101
    SUBTITLE_ROLE = Qt.ItemDataRole.UserRole + 102
    META_ROLE = Qt.ItemDataRole.UserRole + 103
    BADGE_ROLE = Qt.ItemDataRole.UserRole + 104
    ACTIVE_ROLE = Qt.ItemDataRole.UserRole + 105
    ICON_NAME_ROLE = Qt.ItemDataRole.UserRole + 106
    BADGE_TONE_ROLE = Qt.ItemDataRole.UserRole + 107
    AVATAR_PATH_ROLE = Qt.ItemDataRole.UserRole + 108

    def __init__(self, parent=None, theme="dark", accent="#2563eb"):
        super().__init__(parent)
        self.zoom_percent = 100
        self.set_theme(theme, accent)

    def set_zoom_percent(self, zoom_percent=100):
        try:
            zoom_percent = int(zoom_percent)
        except (TypeError, ValueError):
            zoom_percent = 100
        self.zoom_percent = max(60, min(200, zoom_percent))

    def set_theme(self, theme="dark", accent="#2563eb"):
        self.theme = "light" if str(theme).lower() == "light" else "dark"
        self.accent = QColor(accent if isinstance(accent, str) and accent.startswith("#") else "#2563eb")
        self.accent_hover = self._adjust_colour(self.accent, 1.22)
        self.accent_dark = self._adjust_colour(self.accent, 0.72)

        if self.theme == "light":
            self.palette = {
                "header": QColor("#64748b"),
                "header_subtitle": QColor("#7c8aa0"),
                "card": QColor("#ffffff"),
                "card_hover": QColor("#eef4ff"),
                "card_selected": QColor("#dbeafe"),
                "card_active": QColor("#eef4ff"),
                "border": QColor("#d7deea"),
                "border_hover": self.accent_hover,
                "border_selected": self.accent,
                "icon_bg": QColor("#f1f5f9"),
                "icon_border": QColor("#d1d9e6"),
                "title": QColor("#0f172a"),
                "subtitle": QColor("#334155"),
                "meta": QColor("#64748b"),
                "badge_off_bg": QColor("#e2e8f0"),
                "badge_off_border": QColor("#cbd5e1"),
                "badge_off_text": QColor("#475569"),
                "badge_on_bg": QColor("#dcfce7"),
                "badge_on_border": QColor("#22c55e"),
                "badge_on_text": QColor("#166534"),
                "badge_default_bg": QColor("#dbeafe"),
                "badge_default_border": self.accent,
                "badge_default_text": QColor("#1e3a8a"),
                "badge_safe_bg": QColor("#dcfce7"),
                "badge_safe_border": QColor("#22c55e"),
                "badge_safe_text": QColor("#166534"),
                "badge_warning_bg": QColor("#fef3c7"),
                "badge_warning_border": QColor("#f59e0b"),
                "badge_warning_text": QColor("#92400e"),
                "badge_danger_bg": QColor("#fee2e2"),
                "badge_danger_border": QColor("#ef4444"),
                "badge_danger_text": QColor("#991b1b"),
                "badge_neutral_bg": QColor("#e2e8f0"),
                "badge_neutral_border": QColor("#cbd5e1"),
                "badge_neutral_text": QColor("#475569"),
            }
        else:
            self.palette = {
                "header": QColor("#8ea1bd"),
                "header_subtitle": QColor("#64748b"),
                "card": QColor("#141b2a"),
                "card_hover": QColor("#182132"),
                "card_selected": self.accent_dark,
                "card_active": QColor("#17223a"),
                "border": QColor("#243042"),
                "border_hover": self.accent,
                "border_selected": self.accent_hover,
                "icon_bg": QColor("#111827"),
                "icon_border": QColor("#293548"),
                "title": QColor("#f8fafc"),
                "subtitle": QColor("#c9d6ea"),
                "meta": QColor("#8ea1bd"),
                "badge_off_bg": QColor("#334155"),
                "badge_off_border": QColor("#64748b"),
                "badge_off_text": QColor("#e2e8f0"),
                "badge_on_bg": QColor("#064e3b"),
                "badge_on_border": QColor("#10b981"),
                "badge_on_text": QColor("#d1fae5"),
                "badge_default_bg": QColor("#2d4f9e"),
                "badge_default_border": QColor("#5d8cff"),
                "badge_default_text": QColor("#f8fbff"),
                "badge_safe_bg": QColor("#14532d"),
                "badge_safe_border": QColor("#22c55e"),
                "badge_safe_text": QColor("#dcfce7"),
                "badge_warning_bg": QColor("#78350f"),
                "badge_warning_border": QColor("#f59e0b"),
                "badge_warning_text": QColor("#fef3c7"),
                "badge_danger_bg": QColor("#7f1d1d"),
                "badge_danger_border": QColor("#ef4444"),
                "badge_danger_text": QColor("#fee2e2"),
                "badge_neutral_bg": QColor("#334155"),
                "badge_neutral_border": QColor("#64748b"),
                "badge_neutral_text": QColor("#e2e8f0"),
            }

    def _adjust_colour(self, colour: QColor, factor: float) -> QColor:
        r, g, b = colour.red(), colour.green(), colour.blue()
        if factor >= 1:
            r = int(r + (255 - r) * (factor - 1))
            g = int(g + (255 - g) * (factor - 1))
            b = int(b + (255 - b) * (factor - 1))
        else:
            r = int(r * factor)
            g = int(g * factor)
            b = int(b * factor)
        return QColor(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

    def zoom_factor(self, option=None):
        return self.zoom_percent / 100.0

    def sp(self, option, value):
        return max(1, int(round(value * self.zoom_factor(option))))

    def font_with_size(self, option, point_size, bold=False):
        font = QFont(option.font)
        font.setPointSizeF(max(1.0, point_size * self.zoom_factor(option)))
        font.setBold(bold)
        return font

    def sizeHint(self, option, index):
        item_data = index.data(Qt.ItemDataRole.UserRole) or {}
        item_type = item_data.get("type")

        if item_type == "setting_header":
            return QSize(self.sp(option, 260), self.sp(option, 86))

        if item_type == "setting":
            return QSize(self.sp(option, 260), self.sp(option, 118))

        return QSize(self.sp(option, 260), self.sp(option, 118))

    def paint(self, painter, option, index):
        item_data = index.data(Qt.ItemDataRole.UserRole) or {}
        item_type = item_data.get("type")

        if item_type == "setting_header":
            self.paint_settings_header(painter, option, index)
            return

        if item_type == "setting":
            self.paint_browser_card(painter, option, index)
            return

        self.paint_browser_card(painter, option, index)

    def paint_settings_header(self, painter, option, index):
        painter.save()
        rect = option.rect.adjusted(self.sp(option, 14), self.sp(option, 8), -self.sp(option, 14), -self.sp(option, 4))
        title = index.data(self.TITLE_ROLE) or index.data(Qt.ItemDataRole.DisplayRole) or ""
        subtitle = index.data(self.SUBTITLE_ROLE) or ""

        title_font = self.font_with_size(option, 13, True)
        title_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 112)
        painter.setFont(title_font)
        painter.setPen(self.palette["header"])
        title_rect = QRect(rect.left(), rect.top() + self.sp(option, 4), rect.width(), self.sp(option, 28))
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, str(title).upper())

        if subtitle:
            subtitle_font = self.font_with_size(option, 11)
            painter.setFont(subtitle_font)
            painter.setPen(self.palette["header_subtitle"])
            subtitle_rect = QRect(rect.left(), title_rect.bottom() + self.sp(option, 2), rect.width(), self.sp(option, 30))
            elided_subtitle = painter.fontMetrics().elidedText(str(subtitle), Qt.TextElideMode.ElideRight, subtitle_rect.width())
            painter.drawText(subtitle_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_subtitle)

        painter.restore()

    def paint_settings_action(self, painter, option, index):
        painter.save()
        rect = option.rect.adjusted(self.sp(option, 10), self.sp(option, 4), -self.sp(option, 10), -self.sp(option, 4))

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if selected:
            painter.setBrush(self.palette["card_selected"])
            painter.setPen(QPen(self.palette["border_selected"], 1))
            painter.drawRoundedRect(rect, 12, 12)
        elif hovered:
            painter.setBrush(self.palette["card_hover"])
            painter.setPen(QPen(self.palette["border_hover"], 1))
            painter.drawRoundedRect(rect, 12, 12)

        icon_name = index.data(self.ICON_NAME_ROLE) or "settings"
        icon_rect = QRect(rect.left() + self.sp(option, 20), rect.top() + self.sp(option, 18), self.sp(option, 22), self.sp(option, 22))
        icon = load_icon(icon_name)
        icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter)

        title = index.data(self.TITLE_ROLE) or index.data(Qt.ItemDataRole.DisplayRole) or ""
        title_font = self.font_with_size(option, 13)
        painter.setFont(title_font)
        painter.setPen(self.palette["title"])
        title_rect = QRect(icon_rect.right() + self.sp(option, 12), rect.top() + self.sp(option, 8), max(self.sp(option, 40), rect.width() - self.sp(option, 70)), rect.height() - self.sp(option, 16))
        elided_title = painter.fontMetrics().elidedText(str(title), Qt.TextElideMode.ElideRight, title_rect.width())
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_title)

        painter.restore()

    def paint_browser_card(self, painter, option, index):
        painter.save()
        rect = option.rect.adjusted(self.sp(option, 4), self.sp(option, 4), -self.sp(option, 4), -self.sp(option, 4))

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        active = bool(index.data(self.ACTIVE_ROLE))

        if selected:
            background = self.palette["card_selected"]
            border = self.palette["border_selected"]
        elif hovered:
            background = self.palette["card_hover"]
            border = self.palette["border_hover"]
        elif active:
            background = self.palette["card_active"]
            border = self.accent
        else:
            background = self.palette["card"]
            border = self.palette["border"]

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(background)
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(rect, 16, 16)

        icon_rect = QRect(rect.left() + self.sp(option, 14), rect.top() + self.sp(option, 18), self.sp(option, 42), self.sp(option, 42))
        painter.setBrush(self.palette["icon_bg"])
        painter.setPen(QPen(self.palette["icon_border"], 1))
        painter.drawRoundedRect(icon_rect, self.sp(option, 10), self.sp(option, 10))

        avatar = self.avatar_pixmap(index.data(self.AVATAR_PATH_ROLE), icon_rect.size())
        if not avatar.isNull():
            avatar_rect = QRect(
                icon_rect.left() + (icon_rect.width() - avatar.width()) // 2,
                icon_rect.top() + (icon_rect.height() - avatar.height()) // 2,
                avatar.width(),
                avatar.height(),
            )
            painter.drawPixmap(avatar_rect, avatar)
        else:
            icon_name = index.data(self.ICON_NAME_ROLE) or "file"
            icon = load_icon(icon_name)
            icon.paint(painter, icon_rect.adjusted(self.sp(option, 7), self.sp(option, 7), -self.sp(option, 7), -self.sp(option, 7)), Qt.AlignmentFlag.AlignCenter)

        text_left = icon_rect.right() + self.sp(option, 12)
        text_right = rect.right() - self.sp(option, 16)
        badge = index.data(self.BADGE_ROLE) or ""

        if badge:
            badge_font = self.font_with_size(option, 10, True)
            painter.setFont(badge_font)
            badge_width = painter.fontMetrics().horizontalAdvance(badge) + self.sp(option, 18)
            badge_rect = QRect(rect.right() - badge_width - self.sp(option, 14), rect.top() + self.sp(option, 14), badge_width, self.sp(option, 30))
            badge_upper = str(badge).upper()
            badge_tone = str(index.data(self.BADGE_TONE_ROLE) or "").lower()
            if badge_tone in {"safe", "success"}:
                badge_background = self.palette["badge_safe_bg"]
                badge_border = self.palette["badge_safe_border"]
                badge_text_colour = self.palette["badge_safe_text"]
            elif badge_tone in {"warning", "soon"}:
                badge_background = self.palette["badge_warning_bg"]
                badge_border = self.palette["badge_warning_border"]
                badge_text_colour = self.palette["badge_warning_text"]
            elif badge_tone in {"danger", "urgent", "overdue"}:
                badge_background = self.palette["badge_danger_bg"]
                badge_border = self.palette["badge_danger_border"]
                badge_text_colour = self.palette["badge_danger_text"]
            elif badge_tone in {"none", "neutral", "completed"}:
                badge_background = self.palette["badge_neutral_bg"]
                badge_border = self.palette["badge_neutral_border"]
                badge_text_colour = self.palette["badge_neutral_text"]
            elif str(badge).startswith("#") and QColor(str(badge)).isValid():
                badge_background = QColor(str(badge))
                badge_border = self._adjust_colour(badge_background, 0.78)
                brightness = (badge_background.red() * 0.299) + (badge_background.green() * 0.587) + (badge_background.blue() * 0.114)
                badge_text_colour = QColor("#0f172a" if brightness > 165 else "#ffffff")
            elif badge_upper in {"OFF", "DISABLED", "HIDDEN", "NEVER"}:
                badge_background = self.palette["badge_off_bg"]
                badge_border = self.palette["badge_off_border"]
                badge_text_colour = self.palette["badge_off_text"]
            elif badge_upper in {"ON", "ENABLED", "SHOWN", "SYNCED"}:
                badge_background = self.palette["badge_on_bg"]
                badge_border = self.palette["badge_on_border"]
                badge_text_colour = self.palette["badge_on_text"]
            else:
                badge_background = self.palette["badge_default_bg"]
                badge_border = self.palette["badge_default_border"]
                badge_text_colour = self.palette["badge_default_text"]

            painter.setBrush(badge_background)
            painter.setPen(QPen(badge_border, 1))
            painter.drawRoundedRect(badge_rect, 10, 10)
            painter.setPen(badge_text_colour)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge)
            text_right = badge_rect.left() - self.sp(option, 10)

        title = index.data(self.TITLE_ROLE) or ""
        subtitle = index.data(self.SUBTITLE_ROLE) or ""
        meta = index.data(self.META_ROLE) or ""

        title_font = self.font_with_size(option, 14, True)
        painter.setFont(title_font)
        painter.setPen(self.palette["title"])
        title_rect = QRect(text_left, rect.top() + self.sp(option, 14), max(self.sp(option, 40), text_right - text_left), self.sp(option, 32))
        elided_title = painter.fontMetrics().elidedText(str(title), Qt.TextElideMode.ElideRight, title_rect.width())
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_title)

        subtitle_font = self.font_with_size(option, 12, True)
        painter.setFont(subtitle_font)
        painter.setPen(self.palette["subtitle"])
        subtitle_rect = QRect(text_left, rect.top() + self.sp(option, 47), max(self.sp(option, 40), rect.right() - text_left - self.sp(option, 16)), self.sp(option, 26))
        elided_subtitle = painter.fontMetrics().elidedText(str(subtitle), Qt.TextElideMode.ElideRight, subtitle_rect.width())
        painter.drawText(subtitle_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_subtitle)

        meta_font = self.font_with_size(option, 11)
        painter.setFont(meta_font)
        painter.setPen(self.palette["meta"])
        meta_rect = QRect(text_left, rect.top() + self.sp(option, 75), max(self.sp(option, 40), rect.right() - text_left - self.sp(option, 16)), self.sp(option, 24))
        elided_meta = painter.fontMetrics().elidedText(str(meta), Qt.TextElideMode.ElideRight, meta_rect.width())
        painter.drawText(meta_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_meta)

        painter.restore()

    def avatar_pixmap(self, avatar_path, target_size):
        if not avatar_path:
            return QPixmap()

        path = Path(str(avatar_path))
        if not path.exists():
            return QPixmap()

        source = QPixmap()
        try:
            source.loadFromData(path.read_bytes())
        except OSError:
            return QPixmap()

        if source.isNull():
            return QPixmap()

        side = max(1, min(target_size.width(), target_size.height()) - self.sp(None, 8))
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
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, side, side, self.sp(None, 8), self.sp(None, 8))
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        return rounded


class TunedListWidget(QListWidget):
    """QListWidget with a direct hook for app scroll tuning."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._wheel_handler = None

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

class ResourceTreeWidget(QTreeWidget):
    """Resource browser tree with internal drag/drop support.

    The widget delegates actual file/resource moves to MainWindow so the
    visual tree, metadata JSON, and physical vault stay in sync.
    """

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self._wheel_handler = None

        self.setDragEnabled(False)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setRootIsDecorated(False)
        self.setMouseTracking(True)
        self.setItemDelegate(FullRowSelectionDelegate(self))

        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.viewport())
        self.rubber_band.setStyleSheet(
            "QRubberBand { border: 1px dashed #38bdf8; background: rgba(56, 189, 248, 22); }"
        )
        self.rubber_origin = None
        self.rubber_additive = False
        self._rubber_base_selection = set()

        self.resource_clipboard = {
            "mode": None,      # "copy" or "cut"
            "items": []
        }
        self._active_internal_drag_payload = None
        self._pending_internal_drop_request = None
        self._processing_internal_drop_request = False
        self._internal_drop_in_progress = False
        self._external_drop_in_progress = False
        self._manual_drag_start_pos = None
        self._manual_drag_payloads = []
        self._manual_drag_active = False
        self._manual_drag_preview = None
        self._manual_drag_external_started = False
        self._manual_drag_external_launch_pending = False
        self._manual_drag_mode = "move"

        app = QApplication.instance()
        if app is not None:
            try:
                app.applicationStateChanged.connect(self._handle_application_state_changed)
            except Exception:
                pass

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

    def event(self, event):
        if event.type() in {QEvent.Type.WindowDeactivate, QEvent.Type.ApplicationDeactivate}:
            self._export_active_manual_drag()
        return super().event(event)

    def _handle_application_state_changed(self, state):
        if state != Qt.ApplicationState.ApplicationActive:
            self._export_active_manual_drag()

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


    def _walk_tree_items(self):
        root = self.invisibleRootItem()

        def walk(item):
            if not item:
                return
            yield item
            for index in range(item.childCount()):
                yield from walk(item.child(index))

        for index in range(root.childCount()):
            yield from walk(root.child(index))

    def _apply_rubber_band_selection(self, selection_rect):
        """Update rubber-band multi-selection live, before mouse release."""
        for item in self._walk_tree_items():
            rect = self.visualItemRect(item)
            in_band = rect.isValid() and selection_rect.intersects(rect)
            should_select = in_band or (self.rubber_additive and item in self._rubber_base_selection)
            if item.isSelected() != should_select:
                item.setSelected(should_select)
        self.viewport().update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.toggle_expander_at(event.position().toPoint()):
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self.itemAt(event.position().toPoint()) is None:
            self.rubber_origin = event.position().toPoint()
            self.rubber_additive = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            self._rubber_base_selection = set(self.selectedItems())

            if not self.rubber_additive:
                self.clearSelection()

            self.rubber_band.setGeometry(QRect(self.rubber_origin, QSize()))
            self.rubber_band.show()
            event.accept()
            return

        super().mousePressEvent(event)

        if event.button() == Qt.MouseButton.LeftButton and self.itemAt(event.position().toPoint()) is not None:
            payloads = selected_payloads(self)
            if payloads:
                self._manual_drag_start_pos = event.position().toPoint()
                self._manual_drag_payloads = self._copy_payloads(payloads)
                self._manual_drag_active = False

    def mouseMoveEvent(self, event):
        if self.rubber_origin is not None:
            current_pos = event.position().toPoint()
            selection_rect = QRect(self.rubber_origin, current_pos).normalized()
            self.rubber_band.setGeometry(selection_rect)
            self._apply_rubber_band_selection(selection_rect)
            event.accept()
            return

        if self._manual_drag_payloads and event.buttons() & Qt.MouseButton.LeftButton:
            current_pos = event.position().toPoint()
            if not self._manual_drag_active:
                drag_distance = (current_pos - self._manual_drag_start_pos).manhattanLength()
                if drag_distance >= QApplication.startDragDistance():
                    self._manual_drag_active = True
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                    self._show_manual_drag_preview(current_pos)
                    event.accept()
                    return
            else:
                global_pos = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else self.viewport().mapToGlobal(current_pos)
                if self._cursor_is_outside_app_drag_surface(global_pos):
                    self._export_active_manual_drag()
                    event.accept()
                    return
                self._move_manual_drag_preview(current_pos)
                event.accept()
                return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.rubber_origin is not None and event.button() == Qt.MouseButton.LeftButton:
            selection_rect = self.rubber_band.geometry()
            self._apply_rubber_band_selection(selection_rect)
            self.rubber_band.hide()
            self.rubber_origin = None
            self._rubber_base_selection = set()

            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self._manual_drag_payloads:
            if self._manual_drag_external_started:
                self._reset_manual_drag()
                event.accept()
                return

            if self._manual_drag_active:
                position = event.position().toPoint()
                target_item = self.itemAt(position)
                drop_target = drop_target_from_item(target_item, self.owner)
                payloads = self._copy_payloads(self._manual_drag_payloads)
                self._reset_manual_drag()
                event.accept()
                QTimer.singleShot(
                    0,
                    lambda move_payloads=payloads, move_target=dict(drop_target or {}): self.owner.move_file_explorer_payloads(
                        move_payloads,
                        move_target,
                        refresh=True,
                    ),
                )
                return
            self._reset_manual_drag()

        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        if self._manual_drag_active:
            self._hide_manual_drag_preview()
        super().leaveEvent(event)

    def _copy_payloads(self, payloads):
        copied_payloads = []
        for payload in payloads or []:
            copied = dict(payload)
            if copied.get("type") == "resource":
                copied["resource"] = dict(copied.get("resource") or {})
            copied_payloads.append(copied)
        return copied_payloads

    def _show_manual_drag_preview(self, position):
        pixmap = build_drag_preview_pixmap(self._manual_drag_payloads, action="Move")
        if self._manual_drag_preview is None:
            self._manual_drag_preview = QLabel(self.viewport())
            self._manual_drag_preview.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._manual_drag_preview.setPixmap(pixmap)
        self._manual_drag_preview.resize(pixmap.size())
        self._move_manual_drag_preview(position)
        self._manual_drag_preview.show()
        self._manual_drag_preview.raise_()

    def _move_manual_drag_preview(self, position):
        if self._manual_drag_preview is None:
            return
        offset = QPoint(18, 18)
        target = position + offset
        max_x = max(0, self.viewport().width() - self._manual_drag_preview.width() - 6)
        max_y = max(0, self.viewport().height() - self._manual_drag_preview.height() - 6)
        self._manual_drag_preview.move(min(target.x(), max_x), min(target.y(), max_y))

    def _hide_manual_drag_preview(self):
        if self._manual_drag_preview is not None:
            self._manual_drag_preview.hide()

    def _reset_manual_drag(self):
        self._hide_manual_drag_preview()
        self.unsetCursor()
        self._manual_drag_start_pos = None
        self._manual_drag_payloads = []
        self._manual_drag_active = False
        self._manual_drag_external_started = False
        self._manual_drag_external_launch_pending = False
        self._manual_drag_mode = "move"

    def _cursor_is_outside_app_drag_surface(self, global_pos):
        local_pos = self.viewport().mapFromGlobal(global_pos)
        return not self.viewport().rect().adjusted(-6, -6, 6, 6).contains(local_pos)

    def _external_payload_from_manual_payloads(self):
        return external_payload(self._manual_drag_payloads, self.owner)

    def _export_active_manual_drag(self):
        if (
            not self._manual_drag_active
            or not self._manual_drag_payloads
            or self._manual_drag_external_launch_pending
        ):
            return False

        payloads = self._copy_payloads(self._manual_drag_payloads)
        self._manual_drag_mode = "export"
        self._manual_drag_external_started = True
        self._manual_drag_external_launch_pending = True
        self._hide_manual_drag_preview()
        self.unsetCursor()
        self._reset_manual_drag()
        QTimer.singleShot(
            0,
            lambda export_payloads=payloads: self._start_external_drag_for_payloads(export_payloads),
        )
        return True

    def _start_external_drag_from_manual_payloads(self):
        return self._start_external_drag_for_payloads(self._manual_drag_payloads)

    def _start_external_drag_for_payloads(self, payloads):
        self._manual_drag_external_launch_pending = False
        paths, urls = external_payload(payloads, self.owner)

        if paths:
            if urls:
                try:
                    clipboard = QApplication.clipboard()
                    if clipboard:
                        clipboard.setText("\n".join(urls))
                except Exception:
                    pass
            return run_safe_file_drag(self, self.owner, paths)

        if urls:
            return run_safe_link_drag(self, self.owner, urls)

        return False


    def external_drag_payload(self):
        """Return selected local paths and link URLs for external drag-out."""
        return external_payload(selected_payloads(self), self.owner)

    def external_drag_paths(self):
        paths, _urls = self.external_drag_payload()
        return paths

    def startDrag(self, supported_actions):
        """Internal Files moves are handled by the manual mouse controller."""
        return super().startDrag(supported_actions)

    def clear_active_internal_drag(self):
        self._active_internal_drag_payload = None

    def _queue_internal_drop(self, payloads, drop_target):
        if self._pending_internal_drop_request is not None or self._processing_internal_drop_request:
            return False
        safe_payloads = []
        for payload in payloads or []:
            copied = dict(payload)
            if copied.get("type") == "resource":
                copied["resource"] = dict(copied.get("resource") or {})
            safe_payloads.append(copied)
        if not safe_payloads:
            return False
        self._pending_internal_drop_request = {
            "payloads": safe_payloads,
            "drop_target": dict(drop_target or {}),
        }
        return True

    def _process_pending_internal_drop(self):
        request = self._pending_internal_drop_request
        if not request or self._processing_internal_drop_request:
            self._pending_internal_drop_request = None
            return

        self._processing_internal_drop_request = True
        self._pending_internal_drop_request = None
        try:
            self.owner.move_file_explorer_payloads(
                request.get("payloads") or [],
                request.get("drop_target") or {},
                refresh=True,
            )
        finally:
            self._processing_internal_drop_request = False

    def dragEnterEvent(self, event):
        if self.can_accept_internal_drag(event):
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return
        if self.can_accept_external_drop(event):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self.can_accept_internal_drag(event):
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
            return
        if self.can_accept_external_drop(event):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def can_accept_internal_drag(self, event):
        return False

    def can_accept_external_drop(self, event):
        if event.source() is self:
            return False
        return bool(local_paths_from_mime(event.mimeData()))

    def dropEvent(self, event):
        if self.can_accept_external_drop(event):
            if self._external_drop_in_progress:
                event.ignore()
                return
            paths = local_paths_from_mime(event.mimeData())
            position = event.position().toPoint() if hasattr(event, "position") else event.pos()
            target_item = self.itemAt(position)
            drop_target = drop_target_from_item(target_item, self.owner)
            self._external_drop_in_progress = True
            try:
                if self.owner.import_external_paths(paths, drop_target=drop_target):
                    event.acceptProposedAction()
                else:
                    event.ignore()
            finally:
                self._external_drop_in_progress = False
            return

        super().dropEvent(event)
