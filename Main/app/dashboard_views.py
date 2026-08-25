from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QUrl, QSize, QRectF
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QToolButton, QVBoxLayout, QWidget

from core.dashboard.dashboard_models import DashboardSettings, GROUP_ORDER, GROUP_TITLES
from core.dashboard.dashboard_service import build_dashboard_data
from core.dashboard.dashboard_settings import DEFAULT_DASHBOARD_SETTINGS
from core.dashboard.dashboard_time import display_due_text
from core.helpers import due_date_has_explicit_time, format_due_datetime, is_due_date_past, parse_due_date, seconds_until_due
from services.command_history import AssignmentUpdateAction
from ui.components import metric_card, section_header
from ui.context_menus import AppContextMenu
from ui.icons import load_icon
from ui.themed_forms import FormField, ThemedFormDialog, ThemedMessageDialog


class TimelineElidedLabel(QLabel):
    """Single-line timeline label that uses ... when text exceeds its width."""

    def __init__(self, text="", parent=None):
        super().__init__("", parent)
        self._full_text = ""
        self.setWordWrap(False)
        self.setMinimumWidth(0)
        self.setText(text)

    def setText(self, text):
        self._full_text = str(text or "")
        self.setToolTip(self._full_text)
        self._refresh_text()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_text()

    def _refresh_text(self):
        if self.width() <= 2:
            QLabel.setText(self, self._full_text)
            return
        QLabel.setText(
            self,
            self.fontMetrics().elidedText(
                self._full_text,
                Qt.TextElideMode.ElideRight,
                self.width() - 2,
            ),
        )


SUMMARY_METRIC_CHOICES = (
    ("overdue", "Overdue", "Open past due"),
    ("due_today", "Due Today", "Open today"),
    ("due_tomorrow", "Due Tomorrow", "Open tomorrow"),
    ("due_this_week", "This Week", "Open next 7 days"),
    ("no_due_date", "No Due Date", "No deadline set"),
    ("later", "Later", "After this week"),
    ("open_total", "Open Total", "Visible assignments"),
    ("open_todos", "Open Todos", "Across visible assignments"),
    ("resources_total", "Total Resources", "Created resources"),
    ("with_todos", "With Todos", "Assignments with todos"),
    ("low_readiness", "Low Readiness", "Below 50% ready"),
)
SUMMARY_METRIC_LABEL_TO_KEY = {label: key for key, label, _ in SUMMARY_METRIC_CHOICES}
SUMMARY_METRIC_KEY_TO_DETAILS = {key: (label, subtext) for key, label, subtext in SUMMARY_METRIC_CHOICES}
SUMMARY_METRIC_LABELS = tuple(label for _, label, _ in SUMMARY_METRIC_CHOICES)


class TimelineClusterEntry:
    """Stable timeline entry representing several assignments due on one day."""

    def __init__(self, key, due_at, due_text, items):
        self.cluster_key = key
        self.due_at = due_at
        self.due_text = due_text
        self.items = tuple(items or ())
        self.title = f"{len(self.items)} assignments"
        self.course_code = self.cluster_course_summary()

    def cluster_course_summary(self):
        course_codes = []
        for item in self.items:
            code = getattr(item, "course_code", "")
            if code and code not in course_codes:
                course_codes.append(code)
        if not course_codes:
            return "Same day"
        if len(course_codes) <= 2:
            return " • ".join(course_codes)
        return f"{' • '.join(course_codes[:2])} +{len(course_codes) - 2}"


class DeadlineProgressRing(QWidget):
    """Compact circular assignment progress indicator for deadline cards."""

    def __init__(self, parent=None, diameter=70, pen_width=7, main_font_size=17, sub_font_size=0):
        super().__init__(parent)
        self.setObjectName("DeadlineProgressRing")
        self.setFixedSize(diameter, diameter)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.text = "-"
        self.sub_text = ""
        self.progress = 0
        self.pen_width = pen_width
        self.main_font_size = main_font_size
        self.sub_font_size = sub_font_size
        self.ring_color = QColor("#4f46e5")
        self.text_color = QColor("#f8fafc")
        self.sub_text_color = QColor("#9fb4d6")
        self.background_color = QColor("#0b1220")

    def set_state(self, text, progress, ring_color, text_color="#f8fafc", sub_text="", sub_text_color="#9fb4d6"):
        self.text = str(text or "-")
        self.sub_text = str(sub_text or "")
        try:
            self.progress = max(0, min(100, int(progress)))
        except (TypeError, ValueError):
            self.progress = 0
        self.ring_color = QColor(ring_color or "#4f46e5")
        self.text_color = QColor(text_color or "#f8fafc")
        self.sub_text_color = QColor(sub_text_color or "#9fb4d6")
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pen_width = self.pen_width
        rect = QRectF(
            pen_width / 2 + 2,
            pen_width / 2 + 2,
            self.width() - pen_width - 4,
            self.height() - pen_width - 4,
        )

        painter.setBrush(self.background_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(rect)

        track_color = QColor(self.ring_color)
        track_color.setAlpha(72)
        track_pen = QPen(track_color, pen_width)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect, 90 * 16, -360 * 16)

        if self.progress > 0:
            progress_pen = QPen(self.ring_color, pen_width)
            progress_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(progress_pen)
            painter.drawArc(rect, 90 * 16, -int(360 * 16 * (self.progress / 100)))

        painter.setPen(self.text_color)
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(self.countdown_font_size(self.text))
        painter.setFont(font)

        if self.sub_text and self.sub_font_size:
            main_rect = self.rect().adjusted(8, int(self.height() * 0.31), -8, -int(self.height() * 0.42))
            sub_rect = self.rect().adjusted(8, int(self.height() * 0.54), -8, -int(self.height() * 0.24))
            painter.drawText(main_rect, Qt.AlignmentFlag.AlignCenter, self.text)

            painter.setPen(self.sub_text_color)
            sub_font = painter.font()
            sub_font.setBold(True)
            sub_font.setPixelSize(self.sub_font_size)
            painter.setFont(sub_font)
            painter.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, self.sub_text)
        else:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text)

    def countdown_font_size(self, text):
        length = len(str(text or ""))
        if length <= 5:
            return self.main_font_size
        if length <= 7:
            return max(10, self.main_font_size - 2)
        return max(10, self.main_font_size - 5)


class ScaledTimelineWidget(QWidget):
    """Paint a scaled deadline axis and position persistent assignment cards on it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ScaledTimeline")
        self.setMinimumHeight(154)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.cards = []
        self.items = []
        self.now = datetime.now()
        self._card_positions = []
        self._timeline_order = []
        self._timeline_markers = []
        self._visible_items = []
        self._card_width = 150
        self._card_height = 76
        self._today_x = 0
        self._axis_start_x = 0
        self._axis_end_x = 0
        self.setMouseTracking(True)

    def set_cards(self, cards):
        self.cards = list(cards or [])
        for card in self.cards:
            card.setParent(self)
            card.setMouseTracking(True)
            card.hide()

    def set_items(self, items, now=None):
        self.items = list(items or [])
        self.now = now or datetime.now()
        self._update_width_hint()
        self._position_cards()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_cards()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.items or not self._card_positions:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        axis_y = 28
        line_pen = QPen(QColor("#3b4b69"), 2)
        line_pen.setStyle(Qt.PenStyle.DotLine)
        line_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(line_pen)
        painter.drawLine(int(self._axis_start_x), axis_y, int(self._axis_end_x), axis_y)
        self._paint_end_marker(painter, axis_y)

        progress_pen = QPen(QColor("#4f8cff"), 3)
        progress_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(progress_pen)
        progress_end = max(self._axis_start_x, min(self._today_x, self._axis_end_x))
        painter.drawLine(int(self._axis_start_x), axis_y, int(progress_end), axis_y)

        marker_pen = QPen(QColor("#93c5fd"), 2)
        marker_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(marker_pen)
        marker_x = int(max(self._axis_start_x, min(self._today_x, self._axis_end_x)))
        painter.drawLine(marker_x, axis_y - 9, marker_x, axis_y + 9)
        painter.setPen(QColor("#9fb4d6"))
        label_x = marker_x + 7
        if label_x > self.width() - 52:
            label_x = marker_x - 46
        painter.drawText(label_x, axis_y - 10, "Today")
        self._paint_interval_labels(painter, axis_y)

    def _paint_end_marker(self, painter, axis_y):
        label = "END"
        painter.setPen(QColor("#3b4b69"))
        metrics = painter.fontMetrics()
        label_width = metrics.horizontalAdvance(label)
        label_x = int(max(4, min(self._axis_end_x - label_width, self.width() - label_width - 4)))
        painter.drawText(label_x, axis_y + 22, label)

    def _paint_interval_labels(self, painter, axis_y):
        if len(self._timeline_markers) < 2:
            return

        painter.setPen(QColor("#3b4b69"))
        metrics = painter.fontMetrics()
        for left_marker, right_marker in zip(self._timeline_markers, self._timeline_markers[1:]):
            left_due = left_marker["due_at"]
            right_due = right_marker["due_at"]
            if not left_due or not right_due:
                continue

            left_x = left_marker["center_x"]
            right_x = right_marker["center_x"]
            if right_x - left_x < 58:
                continue

            label = self._timeline_interval_label(right_due - left_due)
            label_width = metrics.horizontalAdvance(label)
            label_x = int((left_x + right_x - label_width) / 2)
            painter.drawText(label_x, axis_y + 22, label)

    def _timeline_interval_label(self, delta):
        seconds = max(0, int(delta.total_seconds()))
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes = remainder // 60

        if days and hours:
            return f"{days}d {hours}h"
        if days:
            return f"{days}d"
        if hours:
            return f"{hours}h"
        if minutes:
            return f"{minutes}m"
        return "same time"

    def _update_width_hint(self):
        self._update_card_metrics()
        card_width = self._card_width
        margin = 8
        min_gap = 10
        visible_items = self.items[:len(self.cards)]
        due_values = [item.due_at for item in visible_items if item.due_at]

        parent_width = self.parentWidget().width() if self.parentWidget() else self.width()
        base_width = max(320, parent_width)
        visible_unit_count = sum(1 for item in visible_items if item.due_at)
        count_width = (max(1, visible_unit_count) * (card_width + min_gap)) + (2 * margin)
        scaled_width = base_width

        if due_values:
            start = min(min(due_values), self.now)
            end = max(max(due_values), self.now)
            span_days = max(1, int(((end - start).total_seconds() + 86399) // 86400))
            scaled_width = (span_days * max(72, min(110, int(parent_width * 0.16)))) + card_width + (2 * margin)

        desired_width = min(6000, max(base_width, count_width, scaled_width))
        if self.width() != desired_width:
            self.setFixedWidth(desired_width)

    def _position_cards(self):
        if not self.cards:
            return

        self._update_card_metrics()
        card_width = self._card_width
        card_height = self._card_height
        card_top = 62
        margin = 8
        min_gap = 10

        for card in self.cards:
            card.setFixedSize(card_width, card_height)
            card.hide()

        visible_items = self.items[:len(self.cards)]
        self._visible_items = visible_items
        if not visible_items:
            self._card_positions = []
            self._timeline_order = []
            self._timeline_markers = []
            self._axis_start_x = margin
            self._axis_end_x = max(margin, self.width() - margin)
            self._today_x = self._axis_start_x
            return

        due_values = [item.due_at for item in visible_items if item.due_at]
        if not due_values:
            self._card_positions = []
            self._timeline_order = []
            self._timeline_markers = []
            return

        start = min(min(due_values), self.now)
        end = max(max(due_values), self.now)
        total_seconds = max(1, int((end - start).total_seconds()))
        available = max(1, self.width() - (2 * margin) - card_width)

        units = []
        for index, item in enumerate(visible_items):
            if not item.due_at:
                continue
            ratio = max(0, min(1, (item.due_at - start).total_seconds() / total_seconds))
            units.append({
                "key": f"item:{index}",
                "index": index,
                "due_at": item.due_at,
                "left": margin + int(round(ratio * available)),
                "width": card_width,
            })

        if not units:
            self._card_positions = []
            self._timeline_order = []
            self._timeline_markers = []
            return

        units.sort(key=lambda unit: (unit["left"], unit["due_at"], unit["key"]))
        for index in range(1, len(units)):
            minimum_x = units[index - 1]["left"] + units[index - 1]["width"] + min_gap
            if units[index]["left"] < minimum_x:
                units[index]["left"] = minimum_x

        overflow = units[-1]["left"] + units[-1]["width"] - (self.width() - margin)
        if overflow > 0:
            for unit in units:
                unit["left"] -= overflow
        underflow = margin - units[0]["left"]
        if underflow > 0:
            for unit in units:
                unit["left"] += underflow

        adjusted_positions = [0] * len(visible_items)
        markers = []
        order = []

        for unit in units:
            item_index = unit["index"]
            card_x = int(unit["left"])
            self._place_timeline_card(item_index, card_x, card_top)
            adjusted_positions[item_index] = card_x
            markers.append({
                "due_at": unit["due_at"],
                "center_x": unit["left"] + (unit["width"] / 2),
                "key": unit["key"],
            })
            order.append(item_index)

        self._card_positions = adjusted_positions
        self._timeline_order = order
        self._timeline_markers = sorted(markers, key=lambda marker: (marker["center_x"], marker["due_at"]))
        self._axis_start_x = margin + (card_width / 2)
        self._axis_end_x = margin + available + (card_width / 2)
        today_ratio = max(0, min(1, (self.now - start).total_seconds() / total_seconds))
        self._today_x = margin + (today_ratio * available) + (card_width / 2)

    def _place_timeline_card(self, index, x, y):
        card = self.cards[index]
        card.move(int(x), int(y))
        card.show()
        card.raise_()

    def _update_card_metrics(self):
        parent_width = self.parentWidget().width() if self.parentWidget() else self.width()
        self._card_width = max(132, min(180, int(parent_width * 0.28))) if parent_width else 150
        self._card_height = 92 if self._card_width < 150 else 82


class DashboardViewsMixin:
    """Global, course, assignment, announcement, and todo dashboard views."""

    def build_metric_card(self, title, value="0"):
        return metric_card(title, value)

    def make_section_header(self, title, subtitle=None):
        return section_header(title, subtitle)

    def make_announcement_card(self, announcement, course):
        card = QFrame()
        card.setObjectName("DashboardItemCard")
        card.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        title_label = QLabel(announcement.get("title", "Untitled announcement"))
        title_label.setObjectName("CardTitle")
        title_label.setWordWrap(True)

        source_label = QLabel(announcement.get("source", "Course"))
        source_label.setObjectName("StatusPill")
        source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        top_row.addWidget(title_label, 1)
        top_row.addWidget(source_label, 0)

        meta_label = QLabel(announcement.get("date", "No date"))
        meta_label.setObjectName("CardMeta")
        meta_label.setWordWrap(True)

        body = announcement.get("body", "No announcement details available yet.")
        body_preview = body.strip().replace("\n", " ")
        if len(body_preview) > 180:
            body_preview = body_preview[:180] + "..."

        body_label = QLabel(body_preview)
        body_label.setObjectName("CardBody")
        body_label.setWordWrap(True)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(10)

        hint_label = QLabel("Double-click to view details")
        hint_label.setObjectName("CardHint")
        action_row.addWidget(hint_label, 1)

        canvas_url = self.announcement_canvas_url(announcement)
        if canvas_url:
            canvas_button = QPushButton("Open in Canvas")
            canvas_button.setObjectName("SmallButton")
            canvas_button.setToolTip("Open the original Canvas announcement page")
            canvas_button.clicked.connect(
                lambda checked=False, url=canvas_url: QDesktopServices.openUrl(QUrl(url))
            )
            action_row.addWidget(canvas_button, 0)

        layout.addLayout(top_row)
        layout.addWidget(meta_label)
        layout.addWidget(body_label)
        layout.addLayout(action_row)

        card.mouseDoubleClickEvent = lambda event, item=announcement: self.open_course_announcement_from_card(item)

        return card

    def assignment_due_source(self, assignment):
        """Return the most accurate due-date field available for an assignment."""
        if not assignment:
            return ""

        return assignment.get("canvas_due_at") or assignment.get("due_date") or ""

    def due_countdown_text(self, due_date_text, include_overdue_prefix=True):
        """Return a compact countdown using configurable day/hour/min/sec thresholds."""
        remaining_seconds = seconds_until_due(due_date_text)

        if remaining_seconds is None:
            return "No due date"

        if not due_date_has_explicit_time(due_date_text):
            days = remaining_seconds // 86400
            if days < 0:
                return f"Overdue by {abs(days)}d" if include_overdue_prefix else "Overdue"
            if days == 0:
                return "Due today"
            return f"{days}d left"

        overdue = remaining_seconds < 0
        seconds = abs(int(remaining_seconds))

        hours_threshold = self.app_settings.get_due_countdown_hours_threshold()
        minutes_threshold = self.app_settings.get_due_countdown_minutes_threshold()
        seconds_threshold = self.app_settings.get_due_countdown_seconds_threshold()

        if seconds_threshold > 0 and seconds < seconds_threshold:
            value = f"{seconds}s"
        elif seconds < minutes_threshold * 60:
            value = f"{max(1, (seconds + 59) // 60)}m"
        elif seconds < hours_threshold * 3600:
            value = f"{max(1, (seconds + 3599) // 3600)}h"
        else:
            value = f"{max(1, (seconds + 86399) // 86400)}d"

        if overdue:
            return f"Overdue by {value}" if include_overdue_prefix else "Overdue"

        return f"{value} left"

    def due_urgency_info(self, assignment):
        """Return a compact due-date tone for UI pills and badges."""
        if assignment and self.assignment_is_completed(assignment):
            return "completed", "Done"

        due_text = self.assignment_due_source(assignment)
        remaining_seconds = seconds_until_due(due_text)

        if remaining_seconds is None:
            return "none", "No due"

        if remaining_seconds < 0:
            return "danger", "Overdue"

        if remaining_seconds <= 2 * 86400:
            return "danger", self.due_countdown_text(due_text, include_overdue_prefix=False)

        if remaining_seconds <= 7 * 86400:
            return "warning", self.due_countdown_text(due_text, include_overdue_prefix=False)

        return "safe", self.due_countdown_text(due_text, include_overdue_prefix=False)

    def due_pill_object_name(self, assignment):
        tone, _ = self.due_urgency_info(assignment)
        return {
            "safe": "DuePillSafe",
            "warning": "DuePillSoon",
            "danger": "DuePillUrgent",
            "completed": "DuePillCompleted",
            "none": "DuePillNone",
        }.get(tone, "DuePill")

    def assignment_due_badge(self, assignment):
        _, label = self.due_urgency_info(assignment)
        return label.upper()

    def assignment_due_badge_tone(self, assignment):
        tone, _ = self.due_urgency_info(assignment)
        return tone

    def assignment_canvas_url(self, assignment):
        return assignment.get("canvas_html_url") or assignment.get("html_url") or ""

    def assignment_canvas_link_available(self, assignment, user_id=None):
        if not assignment:
            return False

        user = self.vault.get_user(user_id or getattr(self, "current_user_id", None))
        return bool(user and user.get("canvas_access_token") and self.assignment_canvas_url(assignment))

    def attach_assignment_card_actions(self, card, assignment, course=None):
        card.mouseDoubleClickEvent = lambda event, item=assignment, parent_course=course: self.open_course_assignment_from_card(item, parent_course)
        for widget in [card, *card.findChildren(QWidget)]:
            widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            widget.customContextMenuRequested.connect(
                lambda pos, item=assignment, parent_course=course, source_widget=widget: self.open_assignment_card_context_menu(source_widget, item, parent_course, pos)
            )

    def open_assignment_in_canvas(self, assignment):
        canvas_url = self.assignment_canvas_url(assignment)
        if canvas_url:
            QDesktopServices.openUrl(QUrl(canvas_url))
            return

        QMessageBox.information(
            self,
            "Canvas Link",
            "This assignment does not include a Canvas page URL.",
        )

    def open_current_assignment_in_canvas(self):
        user_id = getattr(self, "assignment_dashboard_user_id", None) or self.current_user_id
        course_id = getattr(self, "assignment_dashboard_course_id", None) or self.current_course_id
        assignment_id = getattr(self, "assignment_dashboard_assignment_id", None) or self.current_assignment_id
        assignment = self.vault.get_assignment(user_id, course_id, assignment_id) if user_id and course_id and assignment_id else None
        if assignment:
            self.open_assignment_in_canvas(assignment)

    def delete_assignment_from_card(self, assignment, course=None):
        if course and course.get("id") != self.current_course_id:
            self.set_current_course(course["id"])
        self.delete_assignment_dialog(assignment)

    def edit_assignment_from_card(self, assignment, course=None):
        if course and course.get("id") != self.current_course_id:
            self.set_current_course(course["id"])
        self.edit_assignment_dialog(assignment)

    def open_assignment_card_context_menu(self, card, assignment, course, pos):
        menu = AppContextMenu(self)
        canvas_url = self.assignment_canvas_url(assignment)
        self.add_menu_action(
            menu,
            "Open in Canvas",
            "canvas",
            lambda: self.open_assignment_in_canvas(assignment),
            bool(canvas_url),
        )

        complete_label = "Mark Incomplete" if self.assignment_is_completed(assignment) else "Mark Complete"
        self.add_menu_action(
            menu,
            complete_label,
            "check",
            lambda checked=False, item=assignment, parent_course=course: self.set_assignment_completed_from_dashboard(
                item,
                not self.assignment_is_completed(item),
                user_id=self.current_user_id,
                course_id=parent_course.get("id") if parent_course else self.current_course_id,
            ),
        )

        self.add_menu_action(
            menu,
            "Edit Assignment",
            "edit",
            lambda checked=False, item=assignment, parent_course=course: self.edit_assignment_from_card(item, parent_course),
        )

        self.add_menu_action(
            menu,
            "Delete",
            "delete",
            lambda: self.delete_assignment_from_card(assignment, course),
        )
        menu.exec(card.mapToGlobal(pos))

    def make_assignment_card(self, assignment, course, resource_count):
        card = QFrame()
        card.setObjectName("AssignmentListRow")
        card.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(18)

        name_col = QVBoxLayout()
        name_col.setContentsMargins(0, 0, 0, 0)
        name_col.setSpacing(6)

        title_label = QLabel(assignment.get("title", "Untitled assessment"))
        title_label.setObjectName("CardTitle")
        title_label.setWordWrap(True)

        course_label = QLabel(f"{course.get('code', 'Course')} / {course.get('name', '')}" if course else "Course")
        course_label.setObjectName("CardMeta")
        course_label.setWordWrap(True)

        name_col.addWidget(title_label)
        name_col.addWidget(course_label)

        _, due_label_text = self.due_urgency_info(assignment)
        due_label = QLabel(due_label_text)
        due_label.setObjectName(self.due_pill_object_name(assignment))
        due_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)

        complete_button = QPushButton("Complete")
        complete_button.setObjectName("AssignmentRowButton")
        complete_button.setToolTip("Mark this assignment complete")
        complete_button.clicked.connect(
            lambda checked=False, item=assignment, parent_course=course: self.mark_assignment_completed_from_card(item, parent_course)
        )
        action_row.addWidget(complete_button)

        canvas_url = self.assignment_canvas_url(assignment)
        if canvas_url:
            canvas_button = QPushButton("Canvas")
            canvas_button.setObjectName("AssignmentRowButton")
            canvas_button.setToolTip("Open this assignment in Canvas")
            canvas_button.clicked.connect(lambda checked=False, item=assignment: self.open_assignment_in_canvas(item))
            action_row.addWidget(canvas_button)

        open_files_button = QPushButton("Open")
        open_files_button.setObjectName("AssignmentRowButton")
        open_files_button.setToolTip("Open this assignment overview")
        open_files_button.clicked.connect(
            lambda checked=False, item=assignment, parent_course=course: self.open_course_assignment_from_card(item, parent_course)
        )
        action_row.addWidget(open_files_button)

        layout.addLayout(name_col, 1)
        layout.addLayout(action_row, 0)
        layout.addWidget(due_label, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.attach_assignment_card_actions(card, assignment, course)

        return card

    def create_assignment_info_card(self, title, value, subtext):
        card = QFrame()
        card.setObjectName("AssignmentInfoCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("CardMeta")
        title_label.setWordWrap(True)
        title_label.setMinimumWidth(0)

        value_label = QLabel(value)
        value_label.setObjectName("AssignmentInfoValue")
        value_label.setWordWrap(True)
        value_label.setMinimumWidth(0)

        subtext_label = QLabel(subtext)
        subtext_label.setObjectName("CardBody")
        subtext_label.setWordWrap(True)
        subtext_label.setMinimumWidth(0)

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(subtext_label)
        layout.addStretch()

        return {
            "card": card,
            "title": title_label,
            "value": value_label,
            "subtext": subtext_label,
        }

    def create_dashboard_summary_card(self, index, title, value, subtext):
        card = QFrame()
        card.setObjectName("AssignmentInfoCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 12, 12)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("CardMeta")
        title_label.setWordWrap(True)
        title_label.setMinimumWidth(0)

        edit_btn = QToolButton()
        edit_btn.setObjectName("SummaryMetricEditButton")
        edit_btn.setIcon(load_icon("edit"))
        edit_btn.setIconSize(QSize(14, 14))
        edit_btn.setFixedSize(26, 26)
        edit_btn.setToolTip("Change this metric")
        edit_btn.clicked.connect(lambda checked=False, card_index=index: self.open_summary_metric_menu(card_index))

        header_row.addWidget(title_label, 1)
        header_row.addWidget(edit_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        value_label = QLabel(value)
        value_label.setObjectName("AssignmentInfoValue")
        value_label.setWordWrap(False)
        value_label.setMinimumWidth(0)

        subtext_label = QLabel(subtext)
        subtext_label.setObjectName("CardBody")
        subtext_label.setWordWrap(True)
        subtext_label.setMinimumWidth(0)

        layout.addLayout(header_row)
        layout.addWidget(value_label)
        layout.addWidget(subtext_label)
        layout.addStretch()

        return {
            "card": card,
            "title": title_label,
            "value": value_label,
            "subtext": subtext_label,
            "edit": edit_btn,
        }


    def build_global_dashboard_page(self):
        """Build the deadline-first all-courses dashboard shown from the left sidebar."""
        page = QWidget()
        outer_layout = QVBoxLayout(page)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.global_dashboard_scroll = QScrollArea()
        self.global_dashboard_scroll.setWidgetResizable(True)
        self.global_dashboard_scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        dashboard_layout = QVBoxLayout(content)
        dashboard_layout.setContentsMargins(0, 0, 0, 0)
        dashboard_layout.setSpacing(16)
        dashboard_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        toolbar = QFrame()
        toolbar.setObjectName("DeadlineDashboardToolbar")
        toolbar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        toolbar.setFixedHeight(50)
        toolbar_layout = QGridLayout(toolbar)
        self.global_dashboard_toolbar_layout = toolbar_layout
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setHorizontalSpacing(8)
        toolbar_layout.setVerticalSpacing(8)

        toolbar_left_group = QFrame()
        toolbar_left_group.setObjectName("DeadlineToolbarGroup")
        toolbar_left_group.setFixedHeight(46)
        toolbar_left_layout = QHBoxLayout(toolbar_left_group)
        toolbar_left_layout.setContentsMargins(6, 5, 6, 5)
        toolbar_left_layout.setSpacing(8)

        toolbar_right_group = QFrame()
        toolbar_right_group.setObjectName("DeadlineToolbarGroup")
        toolbar_right_group.setFixedHeight(46)
        toolbar_right_layout = QHBoxLayout(toolbar_right_group)
        toolbar_right_layout.setContentsMargins(6, 5, 6, 5)
        toolbar_right_layout.setSpacing(8)

        self.global_dashboard_timeframe_combo = QComboBox()
        self.global_dashboard_timeframe_combo.setObjectName("DashboardControlCombo")
        self.global_dashboard_timeframe_combo.setMinimumWidth(130)
        self.global_dashboard_timeframe_combo.setMaximumWidth(190)
        self.global_dashboard_timeframe_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.global_dashboard_timeframe_combo.addItem("Today", "today")
        self.global_dashboard_timeframe_combo.addItem("Next 3 Days", "next_3_days")
        self.global_dashboard_timeframe_combo.addItem("Next 7 Days", "next_7_days")
        self.global_dashboard_timeframe_combo.addItem("Next 14 Days", "next_14_days")
        self.global_dashboard_timeframe_combo.addItem("Next 30 Days", "next_30_days")
        self.global_dashboard_timeframe_combo.addItem("All Upcoming", "all_upcoming")
        self.global_dashboard_timeframe_combo.currentIndexChanged.connect(self.save_deadline_dashboard_control_settings)

        self.global_dashboard_grid_btn = QToolButton()
        self.global_dashboard_grid_btn.setObjectName("DashboardIconToggle")
        self.global_dashboard_grid_btn.setIcon(load_icon("grid"))
        self.global_dashboard_grid_btn.setIconSize(QSize(16, 16))
        self.global_dashboard_grid_btn.setFixedSize(38, 38)
        self.global_dashboard_grid_btn.setToolTip("Grid view")
        self.global_dashboard_grid_btn.setCheckable(True)
        self.global_dashboard_grid_btn.clicked.connect(lambda checked=False: self.set_deadline_dashboard_view_mode("grid"))

        self.global_dashboard_list_btn = QToolButton()
        self.global_dashboard_list_btn.setObjectName("DashboardIconToggle")
        self.global_dashboard_list_btn.setIcon(load_icon("list"))
        self.global_dashboard_list_btn.setIconSize(QSize(16, 16))
        self.global_dashboard_list_btn.setFixedSize(38, 38)
        self.global_dashboard_list_btn.setToolTip("List view")
        self.global_dashboard_list_btn.setCheckable(True)
        self.global_dashboard_list_btn.clicked.connect(lambda checked=False: self.set_deadline_dashboard_view_mode("list"))

        self.global_dashboard_customize_btn = QPushButton("Customize")
        self.global_dashboard_customize_btn.setObjectName("SmallButton")
        self.global_dashboard_customize_btn.setIcon(load_icon("settings"))
        self.global_dashboard_customize_btn.setFixedHeight(36)
        self.global_dashboard_customize_btn.clicked.connect(self.customize_deadline_dashboard)

        self.global_dashboard_sync_btn = QPushButton("Sync")
        self.global_dashboard_sync_btn.setObjectName("SmallButton")
        self.global_dashboard_sync_btn.setIcon(load_icon("refresh"))
        self.global_dashboard_sync_btn.setFixedHeight(36)
        self.global_dashboard_sync_btn.clicked.connect(lambda checked=False: self.sync_canvas_data_for_user(self.get_current_user()))

        toolbar_left_layout.addWidget(self.global_dashboard_timeframe_combo)
        toolbar_left_layout.addStretch()

        toolbar_right_layout.addWidget(self.global_dashboard_grid_btn)
        toolbar_right_layout.addWidget(self.global_dashboard_list_btn)
        toolbar_right_layout.addWidget(self.global_dashboard_customize_btn)
        toolbar_right_layout.addWidget(self.global_dashboard_sync_btn)

        self.global_dashboard_toolbar = toolbar
        self.global_dashboard_toolbar_left_group = toolbar_left_group
        self.global_dashboard_toolbar_right_group = toolbar_right_group
        toolbar_layout.addWidget(toolbar_left_group, 0, 0)
        toolbar_layout.addWidget(toolbar_right_group, 0, 1)
        toolbar_layout.setColumnStretch(0, 1)
        toolbar_layout.setColumnStretch(1, 0)

        self.global_summary_panel = QFrame()
        self.global_summary_panel.setObjectName("DeadlineSummaryPanel")
        self.global_summary_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.global_summary_panel.setFixedHeight(112)
        summary_layout = QGridLayout(self.global_summary_panel)
        self.global_summary_layout = summary_layout
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setHorizontalSpacing(10)
        summary_layout.setVerticalSpacing(10)
        self.global_summary_cards = [
            self.create_dashboard_summary_card(0, "Overdue", "0", "Open past due"),
            self.create_dashboard_summary_card(1, "Due Today", "0", "Open today"),
            self.create_dashboard_summary_card(2, "This Week", "0", "Open next 7 days"),
            self.create_dashboard_summary_card(3, "No Due Date", "0", "No deadline set"),
        ]
        for index, metric in enumerate(self.global_summary_cards):
            summary_layout.addWidget(metric["card"], 0, index)

        self.global_next_due_panel = QFrame()
        self.global_next_due_panel.setObjectName("DeadlineHeroCard")
        self.global_next_due_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.global_next_due_panel.setMinimumHeight(152)
        hero_layout = QHBoxLayout(self.global_next_due_panel)
        hero_layout.setContentsMargins(20, 18, 20, 18)
        hero_layout.setSpacing(20)

        self.global_next_due_ring = DeadlineProgressRing(
            diameter=128,
            pen_width=8,
            main_font_size=22,
            sub_font_size=12,
        )

        hero_text = QVBoxLayout()
        hero_text.setContentsMargins(0, 0, 0, 0)
        hero_text.setSpacing(8)
        self.global_next_due_label = QLabel("NEXT DUE")
        self.global_next_due_label.setObjectName("DeadlineEyebrow")
        self.global_next_due_title = QLabel("No upcoming assignment")
        self.global_next_due_title.setObjectName("DeadlineHeroTitle")
        self.global_next_due_title.setWordWrap(True)
        self.global_next_due_meta = QLabel("Assignments across visible courses will appear here.")
        self.global_next_due_meta.setObjectName("CardMeta")
        self.global_next_due_meta.setWordWrap(True)
        self.global_next_due_stats = QLabel("")
        self.global_next_due_stats.setObjectName("DeadlineHeroStats")
        self.global_next_due_stats.setWordWrap(True)
        hero_text.addWidget(self.global_next_due_label)
        hero_text.addWidget(self.global_next_due_title)
        hero_text.addWidget(self.global_next_due_meta)
        hero_text.addWidget(self.global_next_due_stats)
        hero_text.addStretch()

        hero_actions = QVBoxLayout()
        hero_actions.setContentsMargins(0, 0, 0, 0)
        hero_actions.setSpacing(10)
        self.global_next_due_menu_btn = QToolButton()
        self.global_next_due_menu_btn.setObjectName("ContextQuickButton")
        self.global_next_due_menu_btn.setIcon(load_icon("chevron-down"))
        self.global_next_due_menu_btn.setIconSize(QSize(18, 18))
        self.global_next_due_menu_btn.setToolTip("Assignment actions")
        self.global_next_due_menu_btn.clicked.connect(self.open_next_due_actions_menu)
        hero_actions.addStretch()
        hero_actions.addWidget(
            self.global_next_due_menu_btn,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        hero_actions.addStretch()

        hero_layout.addWidget(self.global_next_due_ring)
        hero_layout.addLayout(hero_text, 1)
        hero_layout.addLayout(hero_actions)

        countdown_panel = QFrame()
        countdown_panel.setObjectName("DeadlineCountdownPanel")
        countdown_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        countdown_panel.setMinimumHeight(150)
        countdown_layout = QVBoxLayout(countdown_panel)
        countdown_layout.setContentsMargins(0, 4, 0, 0)
        countdown_layout.setSpacing(12)
        countdown_layout.addWidget(self.make_section_header("Assignment Countdown", "Grouped by deadline across visible courses."))
        self.global_countdown_empty_card = self.create_content_card(
            "No assignments in this view",
            "Try a wider timeframe or enable no-due-date assignments in Customize.",
        )
        self.global_countdown_empty_card.setMinimumHeight(88)
        self.global_countdown_empty_card.hide()
        countdown_layout.addWidget(self.global_countdown_empty_card)

        self.global_countdown_stack = QStackedWidget()
        self.global_countdown_stack.setObjectName("DeadlineCountdownStack")
        self.global_countdown_stack.setMinimumHeight(120)
        self.deadline_group_panels = {"grid": {}, "list": {}}
        self.deadline_group_counts = {"grid": {}, "list": {}}
        self.deadline_group_empty_labels = {"grid": {}, "list": {}}
        self.deadline_group_more_labels = {"grid": {}, "list": {}}
        self.deadline_group_item_layouts = {"grid": {}, "list": {}}
        self.deadline_card_pools = {"grid": {}, "list": {}}

        grid_page = QWidget()
        grid_layout = QGridLayout(grid_page)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setHorizontalSpacing(12)
        grid_layout.setVerticalSpacing(12)
        self.global_countdown_grid_layout = grid_layout

        list_page = QWidget()
        list_layout = QVBoxLayout(list_page)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(12)

        for index, group_key in enumerate(GROUP_ORDER):
            grid_panel = self.create_deadline_group_panel(group_key, "grid")
            self.deadline_group_panels["grid"][group_key] = grid_panel
            grid_layout.addWidget(grid_panel, index // 2, index % 2, Qt.AlignmentFlag.AlignTop)

            list_panel = self.create_deadline_group_panel(group_key, "list")
            self.deadline_group_panels["list"][group_key] = list_panel
            list_layout.addWidget(list_panel)

        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)
        list_layout.addStretch()

        self.global_countdown_mode_pages = {"grid": grid_page, "list": list_page}
        self.global_countdown_stack.addWidget(grid_page)
        self.global_countdown_stack.addWidget(list_page)
        countdown_layout.addWidget(self.global_countdown_stack)

        self.global_timeline_panel = QFrame()
        self.global_timeline_panel.setObjectName("ContentPanel")
        self.global_timeline_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.global_timeline_panel.setMinimumHeight(238)
        timeline_layout = QVBoxLayout(self.global_timeline_panel)
        timeline_layout.setContentsMargins(18, 16, 18, 16)
        timeline_layout.setSpacing(12)
        timeline_layout.addWidget(self.make_section_header("Upcoming Timeline", "A calm glance at the next dated deadlines."))
        self.global_timeline_empty_label = QLabel("No dated upcoming assignments.")
        self.global_timeline_empty_label.setObjectName("CardMeta")
        self.global_timeline_empty_label.setMinimumHeight(90)
        self.global_timeline_empty_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.global_timeline_empty_label.hide()
        self.global_timeline_scale = ScaledTimelineWidget()
        self.global_timeline_scroll = QScrollArea()
        self.global_timeline_scroll.setObjectName("TimelineScrollArea")
        self.global_timeline_scroll.setWidgetResizable(False)
        self.global_timeline_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.global_timeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.global_timeline_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.global_timeline_scroll.setMinimumHeight(172)
        self.global_timeline_scroll.setMaximumHeight(212)
        self.global_timeline_cards = []
        for _ in range(8):
            timeline_card = self.create_timeline_card()
            timeline_card.hide()
            self.global_timeline_cards.append(timeline_card)
        self.global_timeline_scale.set_cards(self.global_timeline_cards)
        self.global_timeline_scroll.setWidget(self.global_timeline_scale)
        timeline_layout.addWidget(self.global_timeline_scroll)
        timeline_layout.addWidget(self.global_timeline_empty_label)

        dashboard_layout.addWidget(toolbar)
        dashboard_layout.addWidget(self.global_summary_panel)
        dashboard_layout.addWidget(self.global_next_due_panel)
        dashboard_layout.addWidget(self.global_timeline_panel)
        dashboard_layout.addWidget(countdown_panel)

        self.global_dashboard_scroll.setWidget(content)
        outer_layout.addWidget(self.global_dashboard_scroll)
        return page

    def dashboard_available_width(self):
        scroll = getattr(self, "global_dashboard_scroll", None)
        if scroll is not None and scroll.viewport() is not None and scroll.viewport().width() > 0:
            return scroll.viewport().width()
        if hasattr(self, "right_panel") and self.right_panel.width() > 0:
            return self.right_panel.width()
        return max(1, getattr(self, "window_width", 960))

    def apply_dashboard_responsive_metrics(self):
        if not hasattr(self, "global_dashboard_scroll"):
            return

        width = self.dashboard_available_width()
        narrow = width < self.zpx(680) if hasattr(self, "zpx") else width < 680
        very_narrow = width < self.zpx(520) if hasattr(self, "zpx") else width < 520

        if hasattr(self, "global_dashboard_toolbar"):
            self.global_dashboard_toolbar.setFixedHeight(self.zpx(104) if narrow and hasattr(self, "zpx") else (104 if narrow else 50))
            layout = self.global_dashboard_toolbar_layout
            layout.addWidget(self.global_dashboard_toolbar_left_group, 0, 0, 1, 2 if narrow else 1)
            layout.addWidget(self.global_dashboard_toolbar_right_group, 1 if narrow else 0, 0 if narrow else 1, 1, 2 if narrow else 1)
            layout.setColumnStretch(0, 1)
            layout.setColumnStretch(1, 1 if narrow else 0)

        if hasattr(self, "global_summary_layout"):
            columns = 1 if very_narrow else (2 if narrow else 4)
            self.repack_summary_cards(columns)
            rows = (len(self.global_summary_cards) + columns - 1) // columns
            card_height = self.zpx(98) if hasattr(self, "zpx") else 98
            self.global_summary_panel.setFixedHeight(max(card_height, rows * card_height + ((rows - 1) * 10)))

        if hasattr(self, "global_next_due_panel"):
            self.global_next_due_panel.setMinimumHeight(self.zpx(190 if narrow else 152) if hasattr(self, "zpx") else (190 if narrow else 152))

        if hasattr(self, "global_timeline_scroll"):
            timeline_height = self.zpx(204 if narrow else 172) if hasattr(self, "zpx") else (204 if narrow else 172)
            self.global_timeline_scroll.setMinimumHeight(timeline_height)
            self.global_timeline_scroll.setMaximumHeight(timeline_height)
            self.global_timeline_scale._update_width_hint()

        self.deadline_dashboard_grid_columns = 1 if narrow else 2

    def repack_summary_cards(self, columns):
        self.detach_dashboard_layout_items(self.global_summary_layout)
        for index, metric in enumerate(self.global_summary_cards):
            self.global_summary_layout.addWidget(metric["card"], index // columns, index % columns)
        for column in range(max(1, columns)):
            self.global_summary_layout.setColumnStretch(column, 1)

    def deadline_dashboard_settings(self):
        if hasattr(self.app_settings, "get_deadline_dashboard_settings"):
            return self.app_settings.get_deadline_dashboard_settings(self.current_user_id)
        return DEFAULT_DASHBOARD_SETTINGS

    def set_deadline_dashboard_settings(self, settings):
        if hasattr(self.app_settings, "set_deadline_dashboard_settings"):
            return self.app_settings.set_deadline_dashboard_settings(self.current_user_id, settings)
        return settings

    def deadline_dashboard_data(self):
        settings = self.deadline_dashboard_settings()
        if settings.sort != "due_soonest":
            settings = DashboardSettings(
                timeframe=settings.timeframe,
                sort="due_soonest",
                view_mode=settings.view_mode,
                summary_metric_keys=settings.summary_metric_keys,
                show_completed=settings.show_completed,
                show_no_due_date=settings.show_no_due_date,
                show_todos=settings.show_todos,
                show_readiness=settings.show_readiness,
                show_summary_metrics=True,
                show_next_due=settings.show_next_due,
                show_timeline=settings.show_timeline,
                compact_cards=settings.compact_cards,
            )
        return build_dashboard_data(
            self.vault,
            self.current_user_id,
            settings,
            now=datetime.now(),
        )

    def create_deadline_group_panel(self, group_key, view_mode):
        panel = QFrame()
        panel.setObjectName("DeadlineGroupPanel")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        title = QLabel(GROUP_TITLES.get(group_key, group_key).upper())
        title.setObjectName("DeadlineGroupTitle")

        count = QLabel("0")
        count.setObjectName("DeadlineGroupCount")
        count.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header.addWidget(title)
        header.addWidget(count)
        header.addStretch()
        layout.addLayout(header)

        empty = QLabel("No assignments")
        empty.setObjectName("CardMeta")
        empty.hide()
        layout.addWidget(empty)

        item_layout = QVBoxLayout()
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(8)
        layout.addLayout(item_layout)

        more = QLabel("")
        more.setObjectName("DeadlineMoreLabel")
        more.setAlignment(Qt.AlignmentFlag.AlignCenter)
        more.hide()
        layout.addWidget(more)

        self.deadline_group_counts[view_mode][group_key] = count
        self.deadline_group_empty_labels[view_mode][group_key] = empty
        self.deadline_group_more_labels[view_mode][group_key] = more
        self.deadline_group_item_layouts[view_mode][group_key] = item_layout
        panel.hide()
        return panel

    def detach_dashboard_layout_widgets(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            child_layout = item.layout()
            widget = item.widget()

            if child_layout:
                self.detach_dashboard_layout_widgets(child_layout)

            if widget:
                widget.hide()

    def detach_dashboard_layout_items(self, layout):
        while layout.count():
            layout.takeAt(0)

    def sync_deadline_dashboard_controls(self, settings):
        self.global_dashboard_timeframe_combo.blockSignals(True)
        index = self.global_dashboard_timeframe_combo.findData(settings.timeframe)
        self.global_dashboard_timeframe_combo.setCurrentIndex(index if index >= 0 else 0)
        self.global_dashboard_timeframe_combo.blockSignals(False)

        self.global_dashboard_grid_btn.blockSignals(True)
        self.global_dashboard_list_btn.blockSignals(True)
        self.global_dashboard_grid_btn.setChecked(settings.view_mode == "grid")
        self.global_dashboard_list_btn.setChecked(settings.view_mode == "list")
        self.global_dashboard_grid_btn.blockSignals(False)
        self.global_dashboard_list_btn.blockSignals(False)

    def save_deadline_dashboard_control_settings(self, *args):
        if not self.current_user_id:
            return

        current = self.deadline_dashboard_settings()
        settings = DashboardSettings(
            timeframe=self.global_dashboard_timeframe_combo.currentData() or current.timeframe,
            sort="due_soonest",
            view_mode=current.view_mode,
            summary_metric_keys=current.summary_metric_keys,
            show_completed=current.show_completed,
            show_no_due_date=current.show_no_due_date,
            show_todos=current.show_todos,
            show_readiness=current.show_readiness,
            show_summary_metrics=True,
            show_next_due=current.show_next_due,
            show_timeline=current.show_timeline,
            compact_cards=current.compact_cards,
        )
        self.set_deadline_dashboard_settings(settings)
        self.show_global_dashboard_page()

    def set_deadline_dashboard_view_mode(self, view_mode):
        if view_mode not in ("grid", "list"):
            return

        current = self.deadline_dashboard_settings()
        if current.view_mode == view_mode:
            self.sync_deadline_dashboard_controls(current)
            if hasattr(self, "global_countdown_stack"):
                self.global_countdown_stack.setCurrentWidget(self.global_countdown_mode_pages[view_mode])
            return

        settings = DashboardSettings(
            timeframe=current.timeframe,
            sort="due_soonest",
            view_mode=view_mode,
            summary_metric_keys=current.summary_metric_keys,
            show_completed=current.show_completed,
            show_no_due_date=current.show_no_due_date,
            show_todos=current.show_todos,
            show_readiness=current.show_readiness,
            show_summary_metrics=True,
            show_next_due=current.show_next_due,
            show_timeline=current.show_timeline,
            compact_cards=current.compact_cards,
        )
        self.set_deadline_dashboard_settings(settings)
        self.show_global_dashboard_page()

    def customize_deadline_dashboard(self):
        settings = self.deadline_dashboard_settings()
        menu = AppContextMenu(self)
        self.add_menu_action(
            menu,
            "Show Next Due",
            "check" if settings.show_next_due else None,
            lambda checked=False: self.toggle_deadline_dashboard_section("next_due"),
            True,
        )
        self.add_menu_action(
            menu,
            "Show Timeline",
            "check" if settings.show_timeline else None,
            lambda checked=False: self.toggle_deadline_dashboard_section("timeline"),
            True,
        )
        button = self.global_dashboard_customize_btn
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def toggle_deadline_dashboard_section(self, section):
        current = self.deadline_dashboard_settings()
        show_next_due = current.show_next_due
        show_timeline = current.show_timeline
        if section == "next_due":
            show_next_due = not show_next_due
        elif section == "timeline":
            show_timeline = not show_timeline
        else:
            return

        settings = DashboardSettings(
            timeframe=current.timeframe,
            sort="due_soonest",
            view_mode=current.view_mode,
            summary_metric_keys=current.summary_metric_keys,
            show_completed=False,
            show_no_due_date=current.show_no_due_date,
            show_todos=current.show_todos,
            show_readiness=current.show_readiness,
            show_summary_metrics=True,
            show_next_due=show_next_due,
            show_timeline=show_timeline,
            compact_cards=current.compact_cards,
        )
        self.set_deadline_dashboard_settings(settings)
        self.show_global_dashboard_page()

    def set_summary_metric_key(self, index, metric_key):
        current = self.deadline_dashboard_settings()
        metric_keys = list(self.dashboard_summary_metric_keys(current))
        if not 0 <= index < len(metric_keys):
            return
        if metric_key not in SUMMARY_METRIC_KEY_TO_DETAILS:
            return

        metric_keys[index] = metric_key
        settings = DashboardSettings(
            timeframe=current.timeframe,
            sort="due_soonest",
            view_mode=current.view_mode,
            summary_metric_keys=tuple(metric_keys),
            show_completed=False,
            show_no_due_date=current.show_no_due_date,
            show_todos=current.show_todos,
            show_readiness=current.show_readiness,
            show_summary_metrics=True,
            show_next_due=current.show_next_due,
            show_timeline=current.show_timeline,
            compact_cards=current.compact_cards,
        )
        self.set_deadline_dashboard_settings(settings)
        self.show_global_dashboard_page()

    def open_summary_metric_menu(self, index):
        current = self.deadline_dashboard_settings()
        metric_keys = self.dashboard_summary_metric_keys(current)
        current_key = metric_keys[index] if 0 <= index < len(metric_keys) else ""
        menu = AppContextMenu(self)

        for metric_key, label, _ in SUMMARY_METRIC_CHOICES:
            icon_name = "check" if metric_key == current_key else None
            self.add_menu_action(
                menu,
                label,
                icon_name,
                lambda checked=False, selected_key=metric_key: self.set_summary_metric_key(index, selected_key),
                True,
            )

        button = self.global_summary_cards[index]["edit"]
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def _show_hide_text(self, visible):
        return "Show" if visible else "Hide"

    def dashboard_summary_metric_keys(self, settings):
        keys = list(getattr(settings, "summary_metric_keys", ()) or ())
        defaults = list(DEFAULT_DASHBOARD_SETTINGS.summary_metric_keys)
        cleaned = [key for key in keys if key in SUMMARY_METRIC_KEY_TO_DETAILS]
        for key in defaults:
            if len(cleaned) >= 4:
                break
            cleaned.append(key)
        return tuple(cleaned[:4])

    def summary_metric_label(self, key):
        return SUMMARY_METRIC_KEY_TO_DETAILS.get(key, SUMMARY_METRIC_KEY_TO_DETAILS["open_total"])[0]

    def group_count(self, data, group_key):
        for group in data.groups:
            if group.key == group_key:
                return len(group.items)
        return 0

    def total_visible_resources_count(self):
        if not self.current_user_id:
            return 0

        total = 0
        for course in self.get_visible_courses(self.current_user_id):
            course_id = course.get("id")
            if not course_id:
                continue

            total += len(self.vault.load_resources(self.current_user_id, course_id, assignment_id=None))
            for assignment in self.vault.get_assignments(self.current_user_id, course_id):
                assignment_id = assignment.get("id")
                if assignment_id:
                    total += len(self.vault.load_resources(self.current_user_id, course_id, assignment_id))
        return total

    def summary_metric_display(self, data, key):
        title, subtext = SUMMARY_METRIC_KEY_TO_DETAILS.get(key, SUMMARY_METRIC_KEY_TO_DETAILS["open_total"])
        values = {
            "overdue": data.summary.overdue,
            "due_today": data.summary.due_today,
            "due_tomorrow": self.group_count(data, "tomorrow"),
            "due_this_week": data.summary.due_this_week,
            "no_due_date": self.group_count(data, "no_due_date"),
            "later": self.group_count(data, "later"),
            "open_total": len(data.items),
            "open_todos": sum(item.todos.open for item in data.items),
            "resources_total": self.total_visible_resources_count(),
            "with_todos": sum(1 for item in data.items if item.todos.total),
            "low_readiness": sum(1 for item in data.items if item.readiness < 50),
        }
        return title, str(values.get(key, 0)), subtext

    def update_global_summary_metrics(self, data, settings):
        self.global_summary_panel.setVisible(True)
        for card, key in zip(self.global_summary_cards, self.dashboard_summary_metric_keys(settings)):
            title, value, subtext = self.summary_metric_display(data, key)
            card["title"].setText(title)
            card["value"].setText(value)
            card["subtext"].setText(subtext)

    def open_next_due_assignment(self):
        item = getattr(self, "_global_next_due_item", None)
        if item:
            self.open_course_assignment_from_card(item.assignment, item.course)

    def open_next_due_actions_menu(self):
        item = getattr(self, "_global_next_due_item", None)
        menu = AppContextMenu(self)
        has_item = bool(item)
        canvas_url = self.assignment_canvas_url(item.assignment) if item else ""

        self.add_menu_action(menu, "Open", "open", self.open_next_due_assignment, has_item)
        self.add_menu_action(menu, "Done", "check", self.complete_next_due_assignment, has_item)
        self.add_menu_action(menu, "Canvas", "canvas", self.open_next_due_canvas, bool(canvas_url))

        button = self.global_next_due_menu_btn
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def complete_next_due_assignment(self):
        item = getattr(self, "_global_next_due_item", None)
        if item:
            self.set_assignment_completed_from_dashboard(
                item.assignment,
                True,
                user_id=item.user_id,
                course_id=item.course_id,
            )

    def open_next_due_canvas(self):
        item = getattr(self, "_global_next_due_item", None)
        if item:
            self.open_assignment_in_canvas(item.assignment)

    def card_pool_key(self, item):
        return (item.course_id, item.assignment_id)

    def get_deadline_assignment_card(self, view_mode, item):
        key = self.card_pool_key(item)
        pool = self.deadline_card_pools[view_mode]
        if key not in pool:
            pool[key] = self.create_deadline_assignment_card()
        return pool[key]

    def create_deadline_assignment_card(self):
        card = QFrame()
        card.setObjectName("DeadlineAssignmentCard")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setMinimumHeight(92)
        card.setMaximumHeight(132)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        card._deadline_assignment = None
        card._deadline_course = None

        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        name_col = QVBoxLayout()
        name_col.setContentsMargins(0, 0, 0, 0)
        name_col.setSpacing(4)

        title = QLabel("")
        title.setObjectName("CardTitle")
        title.setWordWrap(True)
        title.setMinimumWidth(0)
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        course_label = QLabel("")
        course_label.setObjectName("CardMeta")
        course_label.setWordWrap(True)
        course_label.setMinimumWidth(0)

        detail_label = QLabel("")
        detail_label.setObjectName("CardMeta")
        detail_label.setWordWrap(True)
        detail_label.setMinimumWidth(0)

        name_col.addWidget(title)
        name_col.addWidget(course_label)
        name_col.addWidget(detail_label)

        countdown_ring = DeadlineProgressRing()

        action_menu_btn = QToolButton()
        action_menu_btn.setObjectName("ContextQuickButton")
        action_menu_btn.setIcon(load_icon("chevron-down"))
        action_menu_btn.setIconSize(QSize(18, 18))
        action_menu_btn.setToolTip("Assignment actions")
        action_menu_btn.clicked.connect(lambda checked=False, source=card: self.open_deadline_card_actions_menu(source))

        layout.addLayout(name_col, 1)
        layout.addWidget(countdown_ring, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(action_menu_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        card.title_label = title
        card.course_label = course_label
        card.detail_label = detail_label
        card.countdown_ring = countdown_ring
        card.action_menu_btn = action_menu_btn

        self.attach_reusable_deadline_card_actions(card)
        return card

    def attach_reusable_deadline_card_actions(self, card):
        card.mouseDoubleClickEvent = lambda event, source=card: self.open_deadline_card_assignment(source)
        card.mouseReleaseEvent = lambda event, source=card: self.open_timeline_cluster_from_click(source, event)
        for widget in [card, *card.findChildren(QWidget)]:
            widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            widget.customContextMenuRequested.connect(
                lambda pos, source_widget=widget, source=card: self.open_deadline_card_context_menu(source_widget, source, pos)
            )

    def open_deadline_card_assignment(self, card):
        if getattr(card, "_timeline_cluster_items", None):
            self.open_timeline_cluster_menu(card)
            return

        assignment = getattr(card, "_deadline_assignment", None)
        course = getattr(card, "_deadline_course", None)
        if assignment:
            self.open_course_assignment_from_card(assignment, course)

    def open_timeline_cluster_from_click(self, card, event):
        if getattr(card, "_timeline_cluster_items", None) and event.button() == Qt.MouseButton.LeftButton:
            self.open_timeline_cluster_menu(card)
            event.accept()
            return
        event.ignore()

    def open_timeline_cluster_menu(self, card):
        items = tuple(getattr(card, "_timeline_cluster_items", ()) or ())
        if not items:
            return

        menu = AppContextMenu(self)
        for item in items:
            title = item.title
            due_text = display_due_text(item.due_text)
            label = f"{title} · {item.course_code} · {due_text}"
            self.add_menu_action(
                menu,
                label,
                "open",
                lambda selected=item: self.open_course_assignment_from_card(selected.assignment, selected.course),
                True,
            )

        menu.exec(card.mapToGlobal(card.rect().bottomLeft()))

    def open_deadline_card_actions_menu(self, card):
        assignment = getattr(card, "_deadline_assignment", None)
        menu = AppContextMenu(self)
        has_assignment = bool(assignment)
        canvas_url = self.assignment_canvas_url(assignment) if assignment else ""

        self.add_menu_action(menu, "Open", "open", lambda: self.open_deadline_card_assignment(card), has_assignment)
        self.add_menu_action(menu, "Done", "check", lambda: self.toggle_deadline_card_completion(card), has_assignment)
        self.add_menu_action(menu, "Canvas", "canvas", lambda: self.open_deadline_card_canvas(card), bool(canvas_url))

        button = card.action_menu_btn
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def toggle_deadline_card_completion(self, card):
        assignment = getattr(card, "_deadline_assignment", None)
        if not assignment:
            return

        course = getattr(card, "_deadline_course", None)
        self.set_assignment_completed_from_dashboard(
            assignment,
            not self.assignment_is_completed(assignment),
            user_id=self.current_user_id,
            course_id=course.get("id") if course else self.current_course_id,
        )

    def open_deadline_card_canvas(self, card):
        assignment = getattr(card, "_deadline_assignment", None)
        if assignment:
            self.open_assignment_in_canvas(assignment)

    def open_deadline_card_context_menu(self, source_widget, card, pos):
        if getattr(card, "_timeline_cluster_items", None):
            self.open_timeline_cluster_menu(card)
            return

        assignment = getattr(card, "_deadline_assignment", None)
        if not assignment:
            return

        self.open_assignment_card_context_menu(
            source_widget,
            assignment,
            getattr(card, "_deadline_course", None),
            pos,
        )

    def dashboard_due_badge_object_name(self, item):
        countdown = item.countdown
        remaining = countdown.total_seconds_remaining

        if countdown.is_completed:
            return "DeadlineDueBadgeCompleted"
        if countdown.is_no_due_date or remaining is None:
            return "DeadlineDueBadgeNone"
        if countdown.is_overdue or remaining < 0:
            return "DeadlineDueBadgeDanger"
        if remaining <= 2 * 86400:
            return "DeadlineDueBadgeDanger"
        if remaining <= 7 * 86400:
            return "DeadlineDueBadgeWarning"
        return "DeadlineDueBadgeSafe"

    def dashboard_due_progress_color(self, item):
        badge_name = self.dashboard_due_badge_object_name(item)
        if badge_name == "DeadlineDueBadgeDanger":
            return "#ef4444"
        if badge_name == "DeadlineDueBadgeWarning":
            return "#f59e0b"
        if badge_name == "DeadlineDueBadgeSafe":
            return "#22c55e"
        if badge_name == "DeadlineDueBadgeCompleted":
            return "#64748b"
        return self.dashboard_accent_color()

    def dashboard_accent_color(self):
        if hasattr(self, "app_settings"):
            return self.app_settings.get_accent_color()
        return "#2563eb"

    def dashboard_due_progress_text_color(self, item):
        badge_name = self.dashboard_due_badge_object_name(item)
        if badge_name == "DeadlineDueBadgeWarning":
            return "#fef3c7"
        if badge_name == "DeadlineDueBadgeSafe":
            return "#dcfce7"
        if badge_name == "DeadlineDueBadgeDanger":
            return "#fee2e2"
        return "#f8fafc"

    def dashboard_assignment_card_object_name(self, item):
        return {
            "DeadlineDueBadgeDanger": "DeadlineAssignmentDanger",
            "DeadlineDueBadgeWarning": "DeadlineAssignmentWarning",
            "DeadlineDueBadgeSafe": "DeadlineAssignmentSafe",
            "DeadlineDueBadgeCompleted": "DeadlineAssignmentCompleted",
            "DeadlineDueBadgeNone": "DeadlineAssignmentNone",
        }.get(self.dashboard_due_badge_object_name(item), "DeadlineAssignmentCard")

    def update_deadline_assignment_card(self, card, item, settings):
        assignment = item.assignment
        course = item.course
        card._deadline_assignment = assignment
        card._deadline_course = course

        severity_name = self.dashboard_assignment_card_object_name(item)
        if card.objectName() != severity_name:
            card.setObjectName(severity_name)
            card.style().unpolish(card)
            card.style().polish(card)

        card.title_label.setText(assignment.get("title", "Untitled assignment"))
        card.course_label.setText(f"{item.course_code} • {display_due_text(item.due_text)}")

        detail_parts = []
        if settings.show_readiness:
            detail_parts.append(f"{item.readiness}% ready")
        if settings.show_todos:
            detail_parts.append(f"{item.todos.completed}/{item.todos.total} todos" if item.todos.total else "No todos")
        card.detail_label.setText(" • ".join(detail_parts))
        card.detail_label.setVisible(bool(detail_parts))
        countdown_text = "No due" if item.countdown.is_no_due_date else item.countdown.main_text
        card.countdown_ring.set_state(
            countdown_text,
            item.readiness,
            self.dashboard_due_progress_color(item),
            self.dashboard_due_progress_text_color(item),
        )
        card.action_menu_btn.setEnabled(True)

    def create_timeline_card(self):
        card = QFrame()
        card.setObjectName("DeadlineTimelineItem")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card._deadline_assignment = None
        card._deadline_course = None
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)

        due = TimelineElidedLabel("")
        due.setObjectName("DeadlineTimelineDate")

        count_badge = QLabel("")
        count_badge.setObjectName("DeadlineTimelineClusterBadge")
        count_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_badge.setFixedHeight(18)
        count_badge.hide()

        title = TimelineElidedLabel("")
        title.setObjectName("DeadlineTimelineTitle")
        course = TimelineElidedLabel("")
        course.setObjectName("CardMeta")

        header_row.addWidget(due, 1)
        header_row.addWidget(count_badge, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header_row)
        layout.addWidget(title)
        layout.addWidget(course)
        card.due_label = due
        card.count_badge = count_badge
        card.title_label = title
        card.course_label = course
        self.attach_reusable_deadline_card_actions(card)
        return card

    def update_timeline_card(self, card, item):
        cluster_items = tuple(getattr(item, "items", ()) or ())
        if cluster_items:
            if card.objectName() != "DeadlineTimelineClusterItem":
                card.setObjectName("DeadlineTimelineClusterItem")
                card.style().unpolish(card)
                card.style().polish(card)
            card._deadline_assignment = None
            card._deadline_course = None
            card._timeline_cluster_items = cluster_items
            card.due_label.setText(item.due_at.strftime("%d %b %Y") if item.due_at else "No due date")
            card.count_badge.setText(str(len(cluster_items)))
            card.count_badge.show()
            card.title_label.setText("Grouped deadlines")
            card.course_label.setText(f"{item.course_code} • click to choose")
            card.setToolTip("Open assignments due on this day")
            return

        if card.objectName() != "DeadlineTimelineItem":
            card.setObjectName("DeadlineTimelineItem")
            card.style().unpolish(card)
            card.style().polish(card)
        card._deadline_assignment = item.assignment
        card._deadline_course = item.course
        card._timeline_cluster_items = ()
        card.count_badge.hide()
        card.due_label.setText(display_due_text(item.due_text))
        card.title_label.setText(item.title)
        card.course_label.setText(item.course_code)
        card.setToolTip("Open assignment")

    def timeline_display_entries(self, items):
        groups = []
        current_key = None
        current_items = []

        for item in items:
            key = item.due_at.date().isoformat() if item.due_at else None
            if key != current_key and current_items:
                groups.append((current_key, current_items))
                current_items = []
            current_key = key
            current_items.append(item)

        if current_items:
            groups.append((current_key, current_items))

        entries = []
        for key, group_items in groups:
            if key and len(group_items) > 3:
                due_at = min(item.due_at for item in group_items if item.due_at)
                entries.append(TimelineClusterEntry(key, due_at, group_items[0].due_text, group_items))
            else:
                entries.extend(group_items)
        return tuple(entries)

    def deadline_group_visible_limit(self, view_mode, settings):
        if view_mode == "grid":
            return 4 if settings.compact_cards else 5
        return 8 if settings.compact_cards else 10

    def refresh_deadline_group(self, view_mode, group, settings):
        group_key = group.key
        panel = self.deadline_group_panels[view_mode].get(group_key)
        if not panel:
            return False

        item_layout = self.deadline_group_item_layouts[view_mode][group_key]
        count_label = self.deadline_group_counts[view_mode][group_key]
        empty_label = self.deadline_group_empty_labels[view_mode][group_key]
        more_label = self.deadline_group_more_labels[view_mode][group_key]

        count_label.setText(str(len(group.items)))
        visible_limit = self.deadline_group_visible_limit(view_mode, settings)
        visible_items = group.items[:visible_limit]
        panel.setVisible(bool(group.items))
        empty_label.setVisible(False)

        for item in visible_items:
            card = self.get_deadline_assignment_card(view_mode, item)
            self.update_deadline_assignment_card(card, item, settings)
            item_layout.addWidget(card)
            card.show()

        hidden_count = max(0, len(group.items) - len(visible_items))
        more_label.setVisible(hidden_count > 0)
        more_label.setText(f"+{hidden_count} more" if hidden_count else "")
        return bool(group.items)

    def refresh_countdown_groups(self, data, settings):
        view_mode = settings.view_mode if settings.view_mode in self.deadline_group_panels else "grid"
        self.global_countdown_stack.setCurrentWidget(self.global_countdown_mode_pages[view_mode])

        for group_key in GROUP_ORDER:
            layout = self.deadline_group_item_layouts[view_mode][group_key]
            self.detach_dashboard_layout_widgets(layout)
            self.deadline_group_panels[view_mode][group_key].hide()
            self.deadline_group_more_labels[view_mode][group_key].hide()

        visible_group_keys = []
        for group in data.groups:
            if self.refresh_deadline_group(view_mode, group, settings):
                visible_group_keys.append(group.key)

        any_visible = bool(visible_group_keys)
        if view_mode == "grid":
            self.repack_deadline_grid_groups(visible_group_keys)

        self.global_countdown_stack.setMinimumHeight(0 if any_visible else 120)
        self.global_countdown_empty_card.setVisible(not any_visible)
        self.global_countdown_stack.setVisible(any_visible)

    def repack_deadline_grid_groups(self, visible_group_keys):
        self.detach_dashboard_layout_items(self.global_countdown_grid_layout)
        columns = max(1, int(getattr(self, "deadline_dashboard_grid_columns", 2) or 2))
        for index, group_key in enumerate(visible_group_keys):
            panel = self.deadline_group_panels["grid"].get(group_key)
            if panel:
                self.global_countdown_grid_layout.addWidget(
                    panel,
                    index // columns,
                    index % columns,
                    Qt.AlignmentFlag.AlignTop,
                )
        for column in range(columns):
            self.global_countdown_grid_layout.setColumnStretch(column, 1)

    def refresh_timeline_cards(self, data, settings):
        self.global_timeline_panel.setVisible(settings.show_timeline)
        timeline_items = self.timeline_display_entries(data.timeline_items)[:len(self.global_timeline_cards)] if settings.show_timeline else ()

        for index, card in enumerate(self.global_timeline_cards):
            if index < len(timeline_items):
                self.update_timeline_card(card, timeline_items[index])
            else:
                card.hide()

        self.global_timeline_scroll.setVisible(settings.show_timeline and bool(timeline_items))
        self.global_timeline_scale.setVisible(settings.show_timeline and bool(timeline_items))
        self.global_timeline_scale.set_items(timeline_items, datetime.now())
        self.global_timeline_empty_label.setVisible(settings.show_timeline and not timeline_items)

    def show_global_dashboard_page(self):
        self.detail_title.setText("Global Dashboard")
        self.detail_subtitle.setText("Deadline-first view across visible courses.")

        data = self.deadline_dashboard_data()
        settings = data.settings
        self.sync_deadline_dashboard_controls(settings)
        self.render_global_dashboard_page(data, settings)

        first_show = self.detail_stack.currentWidget() != self.global_dashboard_page
        self.detail_stack.setCurrentWidget(self.global_dashboard_page)
        self.register_app_scroll_widgets()
        self.scroll_tuner.refresh()
        if first_show:
            self.animate_detail_change()

    def render_global_dashboard_page(self, data, settings):
        self.apply_dashboard_responsive_metrics()
        self.update_global_summary_metrics(data, settings)
        self.global_next_due_panel.setVisible(settings.show_next_due)

        self._global_next_due_item = data.next_due
        if data.next_due:
            item = data.next_due
            self.global_next_due_ring.set_state(
                item.countdown.main_text,
                item.readiness,
                self.dashboard_accent_color(),
                "#f8fafc",
                item.countdown.sub_text,
                "#9fb4d6",
            )
            self.global_next_due_title.setText(item.title)
            self.global_next_due_meta.setText(f"{item.course_code} • {item.course_name} • Due {display_due_text(item.due_text)}")
            stats = []
            if settings.show_readiness:
                stats.append(f"Readiness {item.readiness}%")
            if settings.show_todos:
                stats.append(f"Todos {item.todos.completed}/{item.todos.total}")
            self.global_next_due_stats.setText(" • ".join(stats))
            self.global_next_due_menu_btn.setEnabled(True)
        else:
            self.global_next_due_ring.set_state(
                "-",
                0,
                self.dashboard_accent_color(),
                "#f8fafc",
                "No due",
                "#9fb4d6",
            )
            self.global_next_due_title.setText("No upcoming assignment")
            self.global_next_due_meta.setText("Assignments across visible courses will appear here.")
            self.global_next_due_stats.setText("")
            self.global_next_due_menu_btn.setEnabled(False)

        self.refresh_countdown_groups(data, settings)
        self.refresh_timeline_cards(data, settings)

    def build_course_dashboard_page(self):
        page = QWidget()
        outer_layout = QVBoxLayout(page)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.course_dashboard_scroll = QScrollArea()
        self.course_dashboard_scroll.setWidgetResizable(True)
        self.course_dashboard_scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self.course_dashboard_layout = QVBoxLayout(content)
        self.course_dashboard_layout.setContentsMargins(0, 0, 0, 0)
        self.course_dashboard_layout.setSpacing(16)

        announcements_panel = QFrame()
        announcements_panel.setObjectName("ContentPanel")
        self.course_announcements_panel = announcements_panel
        announcements_panel_layout = QVBoxLayout(announcements_panel)
        announcements_panel_layout.setContentsMargins(18, 16, 18, 16)
        announcements_panel_layout.setSpacing(12)

        announcements_header_row = QHBoxLayout()
        announcements_header_row.setContentsMargins(0, 0, 0, 0)
        announcements_header_row.setSpacing(10)
        announcements_header_row.addWidget(
            self.make_section_header(
                "Recent Announcements",
                "Top 5 most recent course updates and notices."
            ),
            1,
        )
        self.course_announcements_toggle_btn = QPushButton("Show All")
        self.course_announcements_toggle_btn.setObjectName("SmallButton")
        self.course_announcements_toggle_btn.setFixedWidth(100)
        self.course_announcements_toggle_btn.clicked.connect(self.toggle_course_announcements_limit)
        announcements_header_row.addWidget(self.course_announcements_toggle_btn, 0, Qt.AlignmentFlag.AlignTop)

        self.course_announcements_collapse_btn = QPushButton("Minimise")
        self.course_announcements_collapse_btn.setObjectName("SmallButton")
        self.course_announcements_collapse_btn.setFixedWidth(92)
        self.course_announcements_collapse_btn.setToolTip("Collapse the announcements list while keeping the panel header visible")
        self.course_announcements_collapse_btn.clicked.connect(self.toggle_course_announcements_collapsed)
        announcements_header_row.addWidget(self.course_announcements_collapse_btn, 0, Qt.AlignmentFlag.AlignTop)
        announcements_panel_layout.addLayout(announcements_header_row)

        self.course_announcements_layout = QVBoxLayout()
        self.course_announcements_layout.setContentsMargins(0, 0, 0, 0)
        self.course_announcements_layout.setSpacing(10)
        announcements_panel_layout.addLayout(self.course_announcements_layout)

        assignments_panel = QFrame()
        assignments_panel.setObjectName("ContentPanel")
        assignments_panel_layout = QVBoxLayout(assignments_panel)
        assignments_panel_layout.setContentsMargins(18, 16, 18, 16)
        assignments_panel_layout.setSpacing(12)

        assignments_header_row = QHBoxLayout()
        assignments_header_row.setContentsMargins(0, 0, 0, 0)
        assignments_header_row.setSpacing(10)
        assignments_header_row.addWidget(
            self.make_section_header(
                "Urgent Assignments",
                "Top 5 active assessments ordered by due date."
            ),
            1,
        )
        self.course_assignments_toggle_btn = QPushButton("Show All")
        self.course_assignments_toggle_btn.setObjectName("SmallButton")
        self.course_assignments_toggle_btn.setFixedWidth(100)
        self.course_assignments_toggle_btn.clicked.connect(self.toggle_course_assignments_limit)
        assignments_header_row.addWidget(self.course_assignments_toggle_btn, 0, Qt.AlignmentFlag.AlignTop)
        assignments_panel_layout.addLayout(assignments_header_row)

        self.course_assignments_layout = QVBoxLayout()
        self.course_assignments_layout.setContentsMargins(0, 0, 0, 0)
        self.course_assignments_layout.setSpacing(10)
        assignments_panel_layout.addLayout(self.course_assignments_layout)

        self.course_dashboard_layout.addWidget(announcements_panel)
        self.course_dashboard_layout.addWidget(assignments_panel)
        self.course_dashboard_layout.addStretch()

        self.course_dashboard_scroll.setWidget(content)
        outer_layout.addWidget(self.course_dashboard_scroll)

        return page

    def build_assignment_dashboard_page(self):
        page = QWidget()
        outer_layout = QVBoxLayout(page)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.assignment_dashboard_scroll = QScrollArea()
        self.assignment_dashboard_scroll.setWidgetResizable(True)
        self.assignment_dashboard_scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self.assignment_dashboard_layout = QVBoxLayout(content)
        self.assignment_dashboard_layout.setContentsMargins(0, 0, 0, 0)
        self.assignment_dashboard_layout.setSpacing(16)

        overview_panel = QFrame()
        overview_panel.setObjectName("ContentPanel")
        overview_layout = QVBoxLayout(overview_panel)
        overview_layout.setContentsMargins(18, 16, 18, 16)
        overview_layout.setSpacing(12)

        overview_layout.addWidget(
            self.make_section_header(
                "Assignment Overview",
                "Due-date focus and study-resource progress at a glance."
            )
        )

        assignment_cards_row = QHBoxLayout()
        assignment_cards_row.setContentsMargins(0, 0, 0, 0)
        assignment_cards_row.setSpacing(12)

        self.assignment_due_card = self.create_assignment_info_card(
            "Due Date",
            "No due date",
            "No countdown yet"
        )
        self.assignment_progress_card = self.create_assignment_info_card(
            "Progress",
            "0 resources",
            "No checklist yet"
        )

        assignment_cards_row.addWidget(self.assignment_due_card["card"])
        assignment_cards_row.addWidget(self.assignment_progress_card["card"])
        overview_layout.addLayout(assignment_cards_row)

        assignment_action_row = QHBoxLayout()
        assignment_action_row.setContentsMargins(0, 0, 0, 0)
        assignment_action_row.setSpacing(10)
        assignment_action_row.addStretch()

        self.assignment_canvas_btn = QPushButton("Open in Canvas")
        self.assignment_canvas_btn.setObjectName("SmallButton")
        self.assignment_canvas_btn.setIcon(load_icon("canvas"))
        self.assignment_canvas_btn.setIconSize(QSize(16, 16))
        self.assignment_canvas_btn.setToolTip("Open this assignment in Canvas")
        self.assignment_canvas_btn.clicked.connect(self.open_current_assignment_in_canvas)
        assignment_action_row.addWidget(self.assignment_canvas_btn)

        self.assignment_complete_btn = QPushButton("Mark Assignment Complete")
        self.assignment_complete_btn.setObjectName("SmallButton")
        self.assignment_complete_btn.setToolTip("Move this assignment out of the active list and into the archive")
        self.assignment_complete_btn.clicked.connect(self.mark_current_assignment_completed)
        assignment_action_row.addWidget(self.assignment_complete_btn)

        overview_layout.addLayout(assignment_action_row)

        todo_panel = QFrame()
        todo_panel.setObjectName("ContentPanel")
        todo_layout = QVBoxLayout(todo_panel)
        todo_layout.setContentsMargins(18, 16, 18, 16)
        todo_layout.setSpacing(12)

        todo_header_row = QHBoxLayout()
        todo_header_row.setContentsMargins(0, 0, 0, 0)
        todo_header_row.setSpacing(12)
        todo_header_row.addWidget(
            self.make_section_header(
                "Todo List",
                "Break the assessment into small visible actions."
            ),
            1,
        )

        self.assignment_add_todo_btn = QPushButton("Add Todo")
        self.assignment_add_todo_btn.setObjectName("SmallButton")
        self.assignment_add_todo_btn.setFixedWidth(130)
        self.assignment_add_todo_btn.setIcon(load_icon("plus"))
        self.assignment_add_todo_btn.setIconSize(QSize(16, 16))
        self.assignment_add_todo_btn.clicked.connect(self.add_assignment_todo_dialog)
        todo_header_row.addWidget(self.assignment_add_todo_btn, 0, Qt.AlignmentFlag.AlignTop)

        todo_progress_row = QHBoxLayout()
        todo_progress_row.setContentsMargins(0, 0, 0, 0)
        todo_progress_row.setSpacing(10)

        self.assignment_todo_summary_label = QLabel("No todos yet")
        self.assignment_todo_summary_label.setObjectName("TodoSummary")

        self.assignment_todo_progress_bar = QProgressBar()
        self.assignment_todo_progress_bar.setObjectName("TodoProgressBar")
        self.assignment_todo_progress_bar.setRange(0, 100)
        self.assignment_todo_progress_bar.setValue(0)
        self.assignment_todo_progress_bar.setTextVisible(False)
        self.assignment_todo_progress_bar.setFixedHeight(8)

        todo_progress_row.addWidget(self.assignment_todo_summary_label)
        todo_progress_row.addWidget(self.assignment_todo_progress_bar, 1)

        self.assignment_todo_layout = QVBoxLayout()
        self.assignment_todo_layout.setContentsMargins(0, 0, 0, 0)
        self.assignment_todo_layout.setSpacing(10)

        todo_layout.addLayout(todo_header_row)
        todo_layout.addLayout(todo_progress_row)
        todo_layout.addLayout(self.assignment_todo_layout)

        self.assignment_dashboard_layout.addWidget(overview_panel)
        self.assignment_dashboard_layout.addWidget(todo_panel)
        self.assignment_dashboard_layout.addStretch()

        self.assignment_dashboard_scroll.setWidget(content)
        outer_layout.addWidget(self.assignment_dashboard_scroll)

        return page

    # =========================================================
    # RIGHT PANEL DISPLAY HELPERS
    # =========================================================

    def days_until_due_text(self, due_date_text):
        return self.due_countdown_text(due_date_text)

    def assignment_is_completed(self, assignment):
        if not assignment:
            return False

        return bool(assignment.get("completed"))

    def assignment_archive_prompt_due_text(self, assignment):
        if not assignment or assignment.get("completed"):
            return ""

        due_text = self.assignment_due_source(assignment)
        if not due_text or not is_due_date_past(due_text):
            return ""

        if assignment.get("archive_prompted_due_text") == due_text:
            return ""

        return due_text

    def prompt_to_archive_overdue_assignments(self, limit=3):
        if getattr(self, "_archive_prompt_in_progress", False):
            return
        if not getattr(self, "current_user_id", None):
            return
        if hasattr(self, "isVisible") and not self.isVisible():
            return

        candidates = []
        for course in self.get_visible_courses(self.current_user_id):
            for assignment in self.vault.get_assignments(self.current_user_id, course.get("id")):
                due_text = self.assignment_archive_prompt_due_text(assignment)
                if due_text:
                    candidates.append((course, assignment, due_text))

        if not candidates:
            return

        self._archive_prompt_in_progress = True
        try:
            for course, assignment, due_text in candidates[:limit]:
                should_archive = ThemedMessageDialog.confirm(
                    self,
                    title="Archive Overdue Assignment?",
                    subtitle=assignment.get("title", "Untitled assignment"),
                    body=(
                        f"This assignment was due on {format_due_datetime(due_text)}.\n\n"
                        "Archive it now to mark it complete and move it into Archived Assignments. "
                        "Keep it active if you still need to finish the task."
                    ),
                    accept_text="Archive",
                    cancel_text="Keep Active",
                    minimum_width=620,
                )
                if should_archive:
                    self.set_assignment_completed_from_dashboard(
                        assignment,
                        True,
                        user_id=self.current_user_id,
                        course_id=course.get("id"),
                    )
                    continue

                self.vault.update_assignment_fields(
                    self.current_user_id,
                    course.get("id"),
                    assignment["id"],
                    archive_prompted_due_text=due_text,
                    archive_prompted_at=datetime.now().isoformat(timespec="seconds"),
                )
        finally:
            self._archive_prompt_in_progress = False

    def set_assignment_completed_from_dashboard(self, assignment, completed, user_id=None, course_id=None):
        if not assignment:
            return

        user_id = user_id or getattr(self, "assignment_dashboard_user_id", None) or self.current_user_id
        course_id = course_id or getattr(self, "assignment_dashboard_course_id", None) or self.current_course_id

        if not user_id or not course_id:
            return

        completed = bool(completed)
        updates = {
            "completed": completed,
            "status": "Completed" if completed else "Not started",
            "completed_at": datetime.now().isoformat(timespec="seconds") if completed else "",
            "archive_prompted_due_text": "",
            "archive_prompted_at": "",
        }

        try:
            action = AssignmentUpdateAction(
                self.vault,
                user_id,
                course_id,
                assignment,
                updates,
                description=f"Mark assignment {'complete' if completed else 'active'}: {assignment.get('title', 'assignment')}",
            )
            self.command_history.perform(action)
            self.update_history_panel()
        except Exception:
            raise

        if completed and self.current_course_id == course_id and self.current_assignment_id == assignment.get("id"):
            self.set_current_assignment(None)

        if self.current_section == "Dashboard":
            self.show_global_dashboard_section()
        elif self.current_section == "Assignments" and self.current_course_id == course_id:
            self.show_assignments_section()
        else:
            refreshed_course = self.vault.get_course(user_id, course_id)
            if refreshed_course:
                self.show_course_dashboard_page(refreshed_course, preview_mode=course_id != self.current_course_id)

        if self.library_window and hasattr(self.library_window, "refresh_tree"):
            self.library_window.refresh_tree()
        self.trigger_reminder_check()

    def upcoming_assignments_for_course(self, user_id, course_id):
        assignments = [
            assignment for assignment in self.vault.get_assignments(user_id, course_id)
            if not self.assignment_is_completed(assignment)
        ]

        def sort_key(assignment):
            due = parse_due_date(self.assignment_due_source(assignment))
            if due and due.tzinfo is not None:
                due = due.astimezone().replace(tzinfo=None)
            return due or datetime.max

        return sorted(assignments, key=sort_key)

    def get_course_announcements(self, course):
        """Return Canvas-backed announcements stored on the course metadata."""
        announcements = course.get("announcements") or []
        return sorted(announcements, key=lambda item: item.get("date") or "", reverse=True)

    def toggle_course_announcements_limit(self):
        self.course_dashboard_show_all_announcements = not self.course_dashboard_show_all_announcements
        course = self.vault.get_course(self.course_dashboard_user_id, self.course_dashboard_course_id)
        if course:
            self.show_course_dashboard_page(course, preview_mode=self.current_section == "Courses" and course.get("id") != self.current_course_id)

    def toggle_course_announcements_collapsed(self):
        """Collapse the announcements panel body while keeping the panel header visible."""
        self.course_announcements_collapsed = not self.course_announcements_collapsed
        self.app_settings.set_course_announcements_collapsed(
            self.course_dashboard_user_id or self.current_user_id,
            self.course_dashboard_course_id,
            self.course_announcements_collapsed,
        )
        course = self.vault.get_course(self.course_dashboard_user_id, self.course_dashboard_course_id)
        if course:
            self.show_course_dashboard_page(course, preview_mode=self.current_section == "Courses" and course.get("id") != self.current_course_id)

    def toggle_course_assignments_limit(self):
        self.course_dashboard_show_all_assignments = not self.course_dashboard_show_all_assignments
        course = self.vault.get_course(self.course_dashboard_user_id, self.course_dashboard_course_id)
        if course:
            self.show_course_dashboard_page(course, preview_mode=self.current_section == "Courses" and course.get("id") != self.current_course_id)

    def announcement_canvas_url(self, announcement):
        """Return the best available Canvas URL for an announcement."""
        if not announcement:
            return ""

        return (
            announcement.get("canvas_html_url")
            or announcement.get("html_url")
            or announcement.get("url")
            or ""
        )

    def open_announcement_in_canvas(self, announcement):
        """Open the Canvas page for an announcement when Canvas supplied a URL."""
        canvas_url = self.announcement_canvas_url(announcement)
        if not canvas_url:
            QMessageBox.information(
                self,
                "Canvas Announcement",
                "This announcement does not include a Canvas page URL.",
            )
            return

        QDesktopServices.openUrl(QUrl(canvas_url))

    def mark_assignment_completed_from_card(self, assignment, course=None):
        """Card-safe wrapper for completing an assignment from dashboards."""
        if not assignment:
            return

        course_id = course.get("id") if course else self.course_dashboard_course_id
        self.set_assignment_completed_from_dashboard(
            assignment,
            True,
            user_id=self.course_dashboard_user_id or self.current_user_id,
            course_id=course_id,
        )

    def mark_current_assignment_completed(self):
        """Complete the assignment currently shown in the assignment dashboard."""
        user_id = getattr(self, "assignment_dashboard_user_id", None) or self.current_user_id
        course_id = getattr(self, "assignment_dashboard_course_id", None) or self.current_course_id
        assignment_id = getattr(self, "assignment_dashboard_assignment_id", None) or self.current_assignment_id
        assignment = self.vault.get_assignment(user_id, course_id, assignment_id) if assignment_id else None
        if assignment:
            self.set_assignment_completed_from_dashboard(assignment, True, user_id=user_id, course_id=course_id)

    def show_course_dashboard_page(self, course, preview_mode=False):
        if not course:
            self.show_text_page("No Course Selected", "Create or select a course.", "Create or select a course first.")
            return

        user_id = self.current_user_id
        course_id = course["id"]

        if course_id != self.course_dashboard_course_id or user_id != self.course_dashboard_user_id:
            self.course_dashboard_show_all_announcements = False
            self.course_dashboard_show_all_assignments = False
            self.course_announcements_collapsed = self.app_settings.get_course_announcements_collapsed(
                user_id,
                course_id,
            )

        self.course_dashboard_user_id = user_id
        self.course_dashboard_course_id = course_id

        assignments = self.upcoming_assignments_for_course(user_id, course_id)
        announcements = self.get_course_announcements(course)
        announcements_visible = self.app_settings.get_course_announcements_panel_visible()
        visible_announcements = announcements if self.course_dashboard_show_all_announcements else announcements[:5]
        visible_assignments = assignments if self.course_dashboard_show_all_assignments else assignments[:5]

        self.detail_title.setText(f"{course['code']} - {course['name']}")
        self.detail_subtitle.setText(
            "Course dashboard preview."
            if preview_mode else
            "Course dashboard · recent announcements and urgent assessments."
        )

        if hasattr(self, "course_announcements_panel"):
            self.course_announcements_panel.setVisible(announcements_visible)

        if hasattr(self, "course_announcements_toggle_btn"):
            self.course_announcements_toggle_btn.setVisible(announcements_visible and len(announcements) > 5)
            self.course_announcements_toggle_btn.setEnabled(not self.course_announcements_collapsed)
            self.course_announcements_toggle_btn.setText(
                "Show Less" if self.course_dashboard_show_all_announcements else "Show All"
            )

        if hasattr(self, "course_announcements_collapse_btn"):
            self.course_announcements_collapse_btn.setVisible(announcements_visible and bool(announcements))
            self.course_announcements_collapse_btn.setText(
                "Expand" if self.course_announcements_collapsed else "Minimise"
            )

        if hasattr(self, "course_assignments_toggle_btn"):
            self.course_assignments_toggle_btn.setVisible(len(assignments) > 5)
            self.course_assignments_toggle_btn.setText(
                "Show Less" if self.course_dashboard_show_all_assignments else "Show All"
            )

        self.clear_layout(self.course_announcements_layout)
        if announcements_visible and not self.course_announcements_collapsed:
            if visible_announcements:
                for announcement in visible_announcements:
                    self.course_announcements_layout.addWidget(
                        self.make_announcement_card(announcement, course)
                    )
            else:
                self.course_announcements_layout.addWidget(
                    self.create_content_card("No announcements", "There are no announcements for this course yet.")
                )

        self.clear_layout(self.course_assignments_layout)
        if visible_assignments:
            for assignment in visible_assignments:
                assignment_resources = self.vault.load_resources(user_id, course_id, assignment["id"])
                self.course_assignments_layout.addWidget(
                    self.make_assignment_card(assignment, course, len(assignment_resources))
                )
        else:
            self.course_assignments_layout.addWidget(
                self.create_content_card(
                    "No active assignments",
                    "There are no active assignments for this course. Archived assignments remain available in the Resource Library under Archived Assignments.",
                )
            )

        self.detail_stack.setCurrentWidget(self.course_dashboard_page)
        self.register_app_scroll_widgets()
        self.scroll_tuner.refresh()
        self.animate_detail_change()

    def open_course_assignment_from_card(self, assignment, course=None):
        if not assignment:
            return

        if course and course.get("id") != self.current_course_id:
            self.set_current_course(course["id"])

        self.set_current_assignment(assignment["id"])
        self.change_section("Assignments")

    def open_course_announcement_from_card(self, announcement):
        if not announcement:
            return

        self.show_announcement_detail_page(announcement)

    def show_announcement_detail_page(self, announcement):
        self.detail_title.setText(announcement.get("title", "Announcement"))
        self.detail_subtitle.setText(f"{announcement.get('source', 'Course')} · {announcement.get('date', 'No date')}")
        self.detail_stack.setCurrentWidget(self.text_page)
        self.clear_layout(self.text_content_layout)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(10)

        back_btn = QPushButton("← Back to Dashboard")
        back_btn.setObjectName("SmallButton")
        back_btn.setFixedWidth(180)
        back_btn.clicked.connect(self.return_to_current_course_dashboard)
        action_row.addWidget(back_btn, 0)

        canvas_url = self.announcement_canvas_url(announcement)
        if canvas_url:
            open_canvas_btn = QPushButton("Open Announcement in Canvas")
            open_canvas_btn.setObjectName("SmallButton")
            open_canvas_btn.setToolTip("Open the original Canvas announcement page")
            open_canvas_btn.clicked.connect(
                lambda checked=False, item=announcement: self.open_announcement_in_canvas(item)
            )
            action_row.addWidget(open_canvas_btn, 0)

        action_row.addStretch()
        self.text_content_layout.addLayout(action_row)

        self.text_content_layout.addWidget(
            self.create_content_card(
                "Announcement",
                f"{announcement.get('title', 'Untitled announcement')}\n\n"
                f"Date: {announcement.get('date', 'No date')}\n"
                f"Source: {announcement.get('source', 'Course')}"
            )
        )
        self.text_content_layout.addWidget(
            self.create_content_card(
                "Details",
                announcement.get("body", "No announcement details available yet.")
            )
        )
        self.text_content_layout.addStretch()
        self.register_app_scroll_widgets()
        self.scroll_tuner.refresh()
        self.animate_detail_change()

    def return_to_current_course_dashboard(self):
        self.change_section("Dashboard")

    def open_course_assignment_from_table(self, table_item):
        payload = table_item.data(Qt.ItemDataRole.UserRole) if table_item else None

        if not payload:
            return

        assignment = payload.get("assignment") if isinstance(payload, dict) else payload
        course = payload.get("course") if isinstance(payload, dict) else self.get_current_course()

        if not assignment or not course:
            return

        self.set_current_course(course["id"])
        self.set_current_assignment(assignment["id"])
        self.change_section("Assignments")

    def open_course_announcement_from_table(self, table_item):
        payload = table_item.data(Qt.ItemDataRole.UserRole) if table_item else None

        if not payload:
            return

        announcement = payload.get("announcement") if isinstance(payload, dict) else payload

        if announcement:
            self.show_announcement_detail_page(announcement)

    def show_assignment_dashboard_page(self, assignment=None, general=False, preview_mode=False):
        course = self.get_current_course()
        if not course:
            self.show_text_page("No Course Selected", "Select a course first.", "Use the Dashboard or Courses section to choose a course.")
            return

        self.assignment_dashboard_user_id = self.current_user_id
        self.assignment_dashboard_course_id = course.get("id")

        if general:
            title = "General Course Resources"
            assignment_id = None
            self.assignment_dashboard_assignment_id = None
            due_value = "Course-level"
            due_subtext = "Use this area for resources that are not tied to one assessment."
            scope_label = "General course resource area"
            todos = []
        else:
            if not assignment:
                return
            assignment = self.assignment_for_dashboard_render(assignment, course) or assignment
            title = assignment.get("title", "Untitled Assignment")
            assignment_id = assignment["id"]
            self.assignment_dashboard_assignment_id = assignment_id
            due_text = self.assignment_due_source(assignment)
            due_value = format_due_datetime(due_text)
            due_subtext = self.days_until_due_text(due_text)
            scope_label = assignment.get("status") or "Not started"
            todos = assignment.get("todos") or []

        resources = self.vault.load_resources(self.current_user_id, self.current_course_id, assignment_id)
        completed_todos = sum(1 for todo in todos if todo.get("done"))
        total_todos = len(todos)
        todo_percent = int(round((completed_todos / total_todos) * 100)) if total_todos else 0

        self.detail_title.setText(title)
        self.detail_subtitle.setText(
            "Assignment preview."
            if preview_mode else
            self.current_context_label()
        )

        self.assignment_due_card["value"].setText(due_value)
        self.assignment_due_card["subtext"].setText(due_subtext)

        if general:
            progress_value = f"{len(resources)} resources"
            progress_subtext = "General resources are shared across this course."
        else:
            progress_value = f"{completed_todos}/{total_todos} todos" if total_todos else f"{len(resources)} resources"
            progress_subtext = (
                f"{todo_percent}% complete · {len(resources)} resources · {scope_label}"
                if total_todos else
                f"No checklist yet · {len(resources)} resources · {scope_label}"
            )

        self.assignment_progress_card["value"].setText(progress_value)
        self.assignment_progress_card["subtext"].setText(progress_subtext)

        self.assignment_add_todo_btn.setEnabled(not general)
        self.assignment_add_todo_btn.setToolTip(
            "Todos are available for assignments/assessments."
            if not general else
            "Select a specific assignment to create todos."
        )

        if hasattr(self, "assignment_canvas_btn"):
            canvas_available = (
                False
                if general or not assignment else
                self.assignment_canvas_link_available(assignment, self.assignment_dashboard_user_id)
            )
            self.assignment_canvas_btn.setVisible(canvas_available)
            self.assignment_canvas_btn.setEnabled(canvas_available)
            self.assignment_canvas_btn.setToolTip(
                "Open this assignment in Canvas."
                if canvas_available else
                "This assignment needs a Canvas page URL and linked Canvas access token."
            )

        if hasattr(self, "assignment_todo_summary_label"):
            if general:
                self.assignment_todo_summary_label.setText("Select an assignment to use todos")
                self.assignment_todo_progress_bar.setValue(0)
                self.assignment_todo_summary_label.setVisible(False)
                self.assignment_todo_progress_bar.setVisible(False)
            elif total_todos:
                remaining = total_todos - completed_todos
                remaining_label = "all done" if remaining == 0 else f"{remaining} open"
                self.assignment_todo_summary_label.setText(f"{completed_todos}/{total_todos} complete · {remaining_label}")
                self.assignment_todo_progress_bar.setValue(todo_percent)
                self.assignment_todo_summary_label.setVisible(True)
                self.assignment_todo_progress_bar.setVisible(True)
            else:
                self.assignment_todo_summary_label.setText("No todos yet")
                self.assignment_todo_progress_bar.setValue(0)
                self.assignment_todo_summary_label.setVisible(False)
                self.assignment_todo_progress_bar.setVisible(False)

        if hasattr(self, "assignment_complete_btn"):
            self.assignment_complete_btn.setVisible(not general)
            self.assignment_complete_btn.setEnabled(not general and bool(assignment))
            self.assignment_complete_btn.setToolTip(
                "Move this assignment out of the active list and into the Resource Library archive."
                if not general else
                "Select a specific assignment to mark it complete."
            )

        self.render_assignment_todos(assignment if not general else None)

        self.detail_stack.setCurrentWidget(self.assignment_dashboard_page)
        self.animate_detail_change()

    def assignment_for_dashboard_render(self, assignment, course):
        if not assignment or not course:
            return assignment

        assignment_id = assignment.get("id")
        user_id = getattr(self, "current_user_id", None)
        course_id = course.get("id")
        if not assignment_id or not user_id or not course_id:
            return assignment

        refreshed = self.vault.get_assignment(user_id, course_id, assignment_id)
        return refreshed or assignment

    def render_assignment_todos(self, assignment):
        self.clear_layout(self.assignment_todo_layout)

        if not assignment:
            self.assignment_todo_layout.addWidget(
                self.make_todo_empty_state(
                    "No assignment selected",
                    "Choose an assignment to keep a focused checklist beside its resources.",
                    icon_name="assignment",
                )
            )
            return

        todos = assignment.get("todos") or []

        if not todos:
            self.assignment_todo_layout.addWidget(
                self.make_todo_empty_state(
                    "No todos yet",
                    "Add a small next action so this assessment feels easier to start.",
                    icon_name="todo",
                )
            )
            return

        for todo in self.sorted_assignment_todos(todos):
            self.assignment_todo_layout.addWidget(
                self.make_todo_card(assignment, todo)
            )

    def sorted_assignment_todos(self, todos):
        indexed = list(enumerate(todos or []))
        indexed.sort(key=lambda pair: (bool(pair[1].get("done")), pair[0]))
        return [todo for _, todo in indexed]

    def make_todo_empty_state(self, title, body, icon_name="todo"):
        card = QFrame()
        card.setObjectName("TodoEmptyState")

        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        icon_label = QLabel()
        icon_label.setObjectName("TodoEmptyIcon")
        icon_label.setPixmap(load_icon(icon_name).pixmap(QSize(22, 22)))
        icon_label.setFixedSize(34, 34)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("TodoEmptyTitle")
        title_label.setWordWrap(True)

        body_label = QLabel(body)
        body_label.setObjectName("TodoEmptyBody")
        body_label.setWordWrap(True)

        text_layout.addWidget(title_label)
        text_layout.addWidget(body_label)

        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text_layout, 1)
        return card

    def make_todo_card(self, assignment, todo):
        card = QFrame()
        card.setObjectName("TodoCardDone" if todo.get("done") else "TodoCard")

        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 12, 12, 12)
        layout.setSpacing(12)

        checkbox = QCheckBox()
        checkbox.setObjectName("TodoCheckbox")
        checkbox.setFixedSize(24, 24)
        checkbox.setChecked(bool(todo.get("done")))
        checkbox.setToolTip("Mark complete" if not todo.get("done") else "Mark open")
        checkbox.toggled.connect(
            lambda checked, assignment_id=assignment["id"], todo_id=todo.get("id"): self.toggle_assignment_todo(
                assignment_id,
                todo_id,
                checked,
            )
        )

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)

        title_label = QLabel(todo.get("title", "Untitled todo"))
        title_label.setObjectName("TodoTitleDone" if todo.get("done") else "TodoTitle")
        title_label.setWordWrap(True)

        meta = self.todo_meta_text(todo)
        meta_label = QLabel(meta)
        meta_label.setObjectName("CardMeta")

        text_layout.addWidget(title_label)
        text_layout.addWidget(meta_label)

        edit_btn = QPushButton()
        edit_btn.setObjectName("IconButton")
        edit_btn.setIcon(load_icon("edit"))
        edit_btn.setIconSize(QSize(16, 16))
        edit_btn.setFixedSize(34, 34)
        edit_btn.setToolTip("Edit todo")
        edit_btn.clicked.connect(
            lambda checked=False, assignment_id=assignment["id"], todo_id=todo.get("id"): self.edit_assignment_todo_dialog(
                assignment_id,
                todo_id,
            )
        )

        delete_btn = QPushButton()
        delete_btn.setObjectName("DangerIconButton")
        delete_btn.setIcon(load_icon("delete"))
        delete_btn.setIconSize(QSize(16, 16))
        delete_btn.setFixedSize(34, 34)
        delete_btn.setToolTip("Delete todo")
        delete_btn.clicked.connect(
            lambda checked=False, assignment_id=assignment["id"], todo_id=todo.get("id"): self.delete_assignment_todo(
                assignment_id,
                todo_id,
            )
        )

        layout.addWidget(checkbox, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(text_layout, 1)
        layout.addWidget(edit_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(delete_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        return card

    def todo_meta_text(self, todo):
        if todo.get("done"):
            completed_at = todo.get("completed_at") or todo.get("updated_at") or ""
            return f"Completed {self.short_datetime_label(completed_at)}" if completed_at else "Completed"

        updated_at = todo.get("updated_at") or todo.get("created_at") or ""
        return f"Updated {self.short_datetime_label(updated_at)}" if updated_at else "Open"

    def short_datetime_label(self, value):
        if not value:
            return ""
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d %b %H:%M")
        except ValueError:
            return str(value)

    def get_assignment_for_todo_operation(self, assignment_id=None):
        assignment_id = assignment_id or getattr(self, "assignment_dashboard_assignment_id", None) or self.current_assignment_id

        if not assignment_id:
            return None

        return self.vault.get_assignment(
            self.current_user_id,
            self.current_course_id,
            assignment_id,
        )

    def save_assignment_todos(self, assignment, todos, description):
        if not assignment:
            return

        try:
            action = AssignmentUpdateAction(
                self.vault,
                self.current_user_id,
                self.current_course_id,
                assignment,
                {"todos": todos},
                description=description,
            )
            self.command_history.perform(action)
            self.update_history_panel()
            refreshed = self.vault.get_assignment(self.current_user_id, self.current_course_id, assignment["id"])
            self.show_assignment_dashboard_page(refreshed, general=False, preview_mode=False)
        except Exception:
            raise

    def add_assignment_todo_dialog(self):
        assignment = self.get_assignment_for_todo_operation()

        if not assignment:
            QMessageBox.information(self, "Add Todo", "Select a specific assignment before adding todos.")
            return

        values = ThemedFormDialog.ask(
            self,
            title="Add Todo",
            subtitle="Add a checklist item for this assignment.",
            fields=[
                FormField(
                    "title",
                    "Todo",
                    placeholder="e.g. Finish draft, review rubric, submit final file",
                    required=True,
                )
            ],
            accept_text="Add Todo",
        )
        if not values:
            return

        title = values["title"].strip()
        todos = assignment.get("todos") or []
        todos.append({
            "id": f"todo_{uuid.uuid4().hex[:10]}",
            "title": title,
            "done": False,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        })

        self.save_assignment_todos(assignment, todos, f"Add todo to {assignment.get('title', 'assignment')}")

    def edit_assignment_todo_dialog(self, assignment_id, todo_id):
        assignment = self.get_assignment_for_todo_operation(assignment_id)
        if not assignment:
            return

        todos = assignment.get("todos") or []
        todo = next((item for item in todos if item.get("id") == todo_id), None)
        if not todo:
            return

        values = ThemedFormDialog.ask(
            self,
            title="Edit Todo",
            subtitle="Update this checklist item.",
            fields=[
                FormField(
                    "title",
                    "Todo",
                    default=todo.get("title", ""),
                    required=True,
                )
            ],
            accept_text="Save Todo",
        )
        if not values:
            return

        todo["title"] = values["title"].strip()
        todo["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.save_assignment_todos(assignment, todos, f"Edit todo in {assignment.get('title', 'assignment')}")

    def toggle_assignment_todo(self, assignment_id, todo_id, checked):
        assignment = self.get_assignment_for_todo_operation(assignment_id)
        if not assignment:
            return

        todos = assignment.get("todos") or []
        changed = False

        for todo in todos:
            if todo.get("id") == todo_id:
                if bool(todo.get("done")) != bool(checked):
                    todo["done"] = bool(checked)
                    todo["updated_at"] = datetime.now().isoformat(timespec="seconds")
                    if checked:
                        todo["completed_at"] = todo["updated_at"]
                    else:
                        todo.pop("completed_at", None)
                    changed = True
                break

        if changed:
            self.save_assignment_todos(assignment, todos, f"Update todo in {assignment.get('title', 'assignment')}")

    def delete_assignment_todo(self, assignment_id, todo_id):
        assignment = self.get_assignment_for_todo_operation(assignment_id)
        if not assignment:
            return

        todos = assignment.get("todos") or []
        todo = next((item for item in todos if item.get("id") == todo_id), None)

        if not todo:
            return

        reply = QMessageBox.question(
            self,
            "Delete Todo",
            f"Delete todo '{todo.get('title', 'Untitled todo')}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        todos = [item for item in todos if item.get("id") != todo_id]
        self.save_assignment_todos(assignment, todos, f"Delete todo from {assignment.get('title', 'assignment')}")

    # =========================================================
    # SECTION SWITCHING
    # =========================================================

    def show_global_dashboard_section(self):
        self.item_list.clear()

        if not self.current_user_id:
            self.add_browser_list_item(
                title="No user selected",
                data={"type": "empty_dashboard"},
                icon_name="dashboard",
                subtitle="Select or create a user before using the dashboard.",
                meta="Dashboard metrics are user-specific",
            )
            self.show_text_page("No User Selected", "Global Dashboard", "Select or create a user first.")
            return

        data = self.deadline_dashboard_data()
        urgent = [item for item in data.items if not item.completed]

        self.add_browser_list_item(
            title="Dashboard Overview",
            data={"type": "dashboard_overview"},
            icon_name="dashboard",
            subtitle=f"{len(urgent)} open assignments in the selected view",
            meta=f"{data.summary.overdue} overdue • {data.summary.due_today} due today",
            active=True,
            badge_text="LIVE",
        )

        for item in urgent[:8]:
            course = item.course
            assignment = item.assignment
            self.add_browser_list_item(
                title=assignment.get("title", "Untitled assignment"),
                data={"type": "global_assignment", "assignment": assignment, "course": course},
                icon_name="assignment",
                subtitle=f"{item.course_code} • Due: {display_due_text(item.due_text)}",
                meta=f"{item.countdown.main_text} {item.countdown.sub_text}",
                badge_text=self.assignment_due_badge(assignment),
                badge_tone=self.assignment_due_badge_tone(assignment),
            )

        self.show_global_dashboard_page()
