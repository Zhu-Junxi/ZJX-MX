from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPalette, QPolygon
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem


class FullRowSelectionDelegate(QStyledItemDelegate):
    """Paint tree hover/selection as one full-width flat row.

    Qt's tree stylesheet handling paints the branch/indent area separately from
    the item cell. Drawing the row background here keeps the file browser and
    Resource Library from showing detached selection blocks on Windows.
    """

    def __init__(
        self,
        parent=None,
        *,
        selected="#25509e",
        selected_hover="#2f67c8",
        hover="#1a2940",
        text="#d8e8ff",
        selected_text="#ffffff",
        arrow="#c6d6eb",
    ):
        super().__init__(parent)
        self.selected_colour = QColor(selected)
        self.selected_hover_colour = QColor(selected_hover)
        self.hover_colour = QColor(hover)
        self.text_colour = QColor(text)
        self.selected_text_colour = QColor(selected_text)
        self.arrow_colour = QColor(arrow)

    def set_colours(
        self,
        selected="#25509e",
        selected_hover="#2f67c8",
        hover="#1a2940",
        text="#d8e8ff",
        selected_text="#ffffff",
        arrow="#c6d6eb",
    ):
        self.selected_colour = QColor(selected)
        self.selected_hover_colour = QColor(selected_hover)
        self.hover_colour = QColor(hover)
        self.text_colour = QColor(text)
        self.selected_text_colour = QColor(selected_text)
        self.arrow_colour = QColor(arrow)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        has_children = bool(index.model() and index.model().hasChildren(index))

        row_rect = self.full_row_rect(option)
        if selected or hovered:
            if selected and hovered:
                colour = self.selected_hover_colour
            elif selected:
                colour = self.selected_colour
            else:
                colour = self.hover_colour

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colour)
            painter.drawRect(row_rect)
            painter.restore()

        text_colour = self.selected_text_colour if selected else self.text_colour

        clean = QStyleOptionViewItem(option)
        clean.state &= ~QStyle.StateFlag.State_Selected
        clean.state &= ~QStyle.StateFlag.State_MouseOver
        clean.state &= ~QStyle.StateFlag.State_HasFocus
        clean.showDecorationSelected = False
        clean.backgroundBrush = Qt.BrushStyle.NoBrush
        if has_children:
            clean.rect = clean.rect.adjusted(self.arrow_space(option), 0, 0, 0)
        clean.palette.setColor(QPalette.ColorRole.Text, text_colour)
        clean.palette.setColor(QPalette.ColorRole.HighlightedText, text_colour)
        clean.palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 0, 0, 0))
        super().paint(painter, clean, index)

        if has_children:
            self.paint_arrow(painter, option, index, selected)

    def full_row_rect(self, option: QStyleOptionViewItem):
        rect = QRect(option.rect)
        viewport = getattr(option.widget, "viewport", lambda: None)()
        if viewport is not None:
            rect.setLeft(0)
            rect.setWidth(viewport.width())
        return rect

    def arrow_space(self, option: QStyleOptionViewItem):
        return self.arrow_space_for_metrics(option.fontMetrics)

    def arrow_rect(self, option: QStyleOptionViewItem):
        return self.arrow_rect_from_rect(option.rect, option.fontMetrics)

    def arrow_space_for_metrics(self, metrics):
        return max(18, int(round(metrics.height() * 1.25)))

    def arrow_rect_from_rect(self, rect: QRect, metrics):
        size = max(8, min(12, int(round(metrics.height() * 0.7))))
        left = rect.left() + max(4, (self.arrow_space_for_metrics(metrics) - size) // 2)
        top = rect.center().y() - size // 2
        return QRect(left, top, size, size)

    def arrow_rect_for_index(self, view, index):
        return self.arrow_rect_from_rect(view.visualRect(index), view.fontMetrics())

    def paint_arrow(self, painter: QPainter, option: QStyleOptionViewItem, index, selected=False):
        rect = self.arrow_rect(option)
        expanded = bool(option.widget and option.widget.isExpanded(index))
        if expanded:
            points = [
                QPoint(rect.left() + 1, rect.top() + 3),
                QPoint(rect.right() - 1, rect.top() + 3),
                QPoint(rect.center().x(), rect.bottom() - 1),
            ]
        else:
            points = [
                QPoint(rect.left() + 3, rect.top() + 1),
                QPoint(rect.left() + 3, rect.bottom() - 1),
                QPoint(rect.right() - 1, rect.center().y()),
            ]

        colour = self.selected_text_colour if selected else self.arrow_colour
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour)
        painter.drawPolygon(QPolygon(points))
        painter.restore()
