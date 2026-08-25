from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget


def card_frame(object_name="DetailsCard", margins=(18, 16, 18, 16), spacing=10):
    """Create a styled frame and its vertical layout."""
    card = QFrame()
    card.setObjectName(object_name)

    layout = QVBoxLayout(card)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)

    return card, layout


def text_label(text, object_name, word_wrap=True, selectable=False):
    """Create a QLabel with the standard object-name styling contract."""
    label = QLabel(str(text))
    label.setObjectName(object_name)
    label.setWordWrap(word_wrap)
    label.setMinimumWidth(0)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    if selectable:
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def action_button(text, object_name="SmallButton", tooltip=None):
    """Create a consistently styled command button."""
    button = QPushButton(text)
    button.setObjectName(object_name)
    if tooltip:
        button.setToolTip(tooltip)
    return button


def section_header(title, subtitle=None):
    """Create the standard section header used by dashboards and panels."""
    header = QWidget()
    header.setObjectName("SectionHeader")
    header.setAutoFillBackground(False)
    layout = QVBoxLayout(header)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    title_label = text_label(title, "SectionTitle")
    layout.addWidget(title_label)

    if subtitle:
        subtitle_label = text_label(subtitle, "SectionSubtext")
        layout.addWidget(subtitle_label)

    return header


def metric_card(title, value="0"):
    """Create the standard compact metric card and return its value label."""
    card, layout = card_frame("MetricCard", margins=(14, 14, 14, 14), spacing=8)

    title_label = text_label(title, "MetricTitle", word_wrap=True)
    value_label = text_label(value, "MetricValue", word_wrap=False)

    layout.addWidget(title_label)
    layout.addWidget(value_label)
    layout.addStretch()

    return card, value_label
