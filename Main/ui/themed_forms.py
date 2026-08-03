from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


@dataclass
class FormField:
    """Declarative field definition for reusable one-page themed dialogs."""

    key: str
    label: str
    kind: str = "text"
    default: Any = ""
    placeholder: str = ""
    required: bool = False
    options: Sequence[str] = field(default_factory=tuple)
    minimum: int = 0
    maximum: int = 100
    step: int = 1
    suffix: str = ""
    hint: str = ""


class ThemedFormDialog(QDialog):
    """Reusable app-themed form dialog driven by FormField definitions."""

    def __init__(
        self,
        parent=None,
        *,
        title: str,
        subtitle: str = "",
        fields: Sequence[FormField] | None = None,
        accept_text: str = "Save",
        cancel_text: str = "Cancel",
        minimum_width: int = 560,
    ):
        super().__init__(parent)
        self.fields = list(fields or [])
        self._widgets: dict[str, QWidget] = {}
        self._slider_value_labels: dict[str, QLabel] = {}
        self._values: dict[str, Any] = {}

        self.setObjectName("ThemedFormDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(minimum_width)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("DialogCard")
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(15)

        title_label = QLabel(title)
        title_label.setObjectName("DialogTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("DialogSubtitle")
            subtitle_label.setWordWrap(True)
            layout.addWidget(subtitle_label)

        for field in self.fields:
            self._add_field(layout, field)

        self.error_label = QLabel("")
        self.error_label.setObjectName("InlineError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 4, 0, 0)
        button_row.setSpacing(10)
        button_row.addStretch()

        cancel_button = QPushButton(cancel_text)
        cancel_button.setObjectName("SecondaryButton")
        cancel_button.clicked.connect(self.reject)

        accept_button = QPushButton(accept_text)
        accept_button.setObjectName("PrimaryButton")
        accept_button.clicked.connect(self._accept_if_valid)
        accept_button.setDefault(True)

        button_row.addWidget(cancel_button)
        button_row.addWidget(accept_button)
        layout.addLayout(button_row)

    def _add_field(self, parent_layout: QVBoxLayout, field: FormField):
        wrapper = QWidget()
        wrapper.setObjectName("DialogField")
        wrapper.setAutoFillBackground(False)
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(7)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        label = QLabel(field.label)
        label.setObjectName("FieldLabel")
        label.setWordWrap(True)
        header_row.addWidget(label, 1)

        widget = self._make_widget(field)

        if field.kind == "slider":
            value_label = QLabel(self._format_slider_value(field, int(widget.value())))
            value_label.setObjectName("SliderValue")
            header_row.addWidget(value_label, 0, Qt.AlignmentFlag.AlignRight)
            self._slider_value_labels[field.key] = value_label
            widget.valueChanged.connect(
                lambda value, item=field: self._slider_value_labels[item.key].setText(
                    self._format_slider_value(item, int(value))
                )
            )

        wrapper_layout.addLayout(header_row)
        wrapper_layout.addWidget(widget)

        if field.hint:
            hint = QLabel(field.hint)
            hint.setObjectName("FieldHint")
            hint.setWordWrap(True)
            wrapper_layout.addWidget(hint)

        self._widgets[field.key] = widget
        parent_layout.addWidget(wrapper)

    def _make_widget(self, field: FormField):
        default = "" if field.default is None else str(field.default)

        if field.kind == "textarea":
            widget = QTextEdit()
            widget.setObjectName("DialogTextArea")
            widget.setMinimumHeight(140)
            widget.setPlaceholderText(field.placeholder)
            widget.setPlainText(default)
            return widget

        if field.kind == "combo":
            widget = QComboBox()
            widget.setObjectName("DialogCombo")
            widget.addItems([str(option) for option in field.options])
            if default:
                index = widget.findText(default)
                if index >= 0:
                    widget.setCurrentIndex(index)
            return widget

        if field.kind == "slider":
            widget = QSlider(Qt.Orientation.Horizontal)
            widget.setObjectName("DialogSlider")
            widget.setRange(int(field.minimum), int(field.maximum))
            widget.setSingleStep(max(1, int(field.step)))
            widget.setPageStep(max(1, int(field.step) * 5))
            widget.setMinimumHeight(44)
            widget.setAutoFillBackground(False)
            widget.setMouseTracking(True)
            try:
                value = int(field.default)
            except (TypeError, ValueError):
                value = int(field.minimum)
            widget.setValue(max(int(field.minimum), min(int(field.maximum), value)))
            return widget

        widget = QLineEdit()
        widget.setObjectName("DialogInput")
        widget.setPlaceholderText(field.placeholder)
        widget.setText(default)
        return widget

    def _format_slider_value(self, field: FormField, value: int) -> str:
        return f"{value}{field.suffix}"

    def _field_value(self, field: FormField):
        widget = self._widgets[field.key]

        if field.kind == "textarea":
            return widget.toPlainText()

        if field.kind == "combo":
            return widget.currentText()

        if field.kind == "slider":
            return int(widget.value())

        return widget.text()

    def _accept_if_valid(self):
        values = {}

        for field in self.fields:
            value = self._field_value(field)
            if field.required and not str(value).strip():
                self.error_label.setText(f"{field.label} is required.")
                self.error_label.show()
                self._widgets[field.key].setFocus()
                return
            values[field.key] = value

        self._values = values
        self.accept()

    def values(self) -> dict[str, Any]:
        return dict(self._values)

    @classmethod
    def ask(
        cls,
        parent,
        *,
        title: str,
        subtitle: str = "",
        fields: Sequence[FormField] | None = None,
        accept_text: str = "Save",
        cancel_text: str = "Cancel",
        minimum_width: int = 560,
    ) -> dict[str, Any] | None:
        dialog = cls(
            parent,
            title=title,
            subtitle=subtitle,
            fields=fields,
            accept_text=accept_text,
            cancel_text=cancel_text,
            minimum_width=minimum_width,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.values()


class ThemedMessageDialog(QDialog):
    """Reusable themed message / confirmation dialog for app workflows."""

    def __init__(
        self,
        parent=None,
        *,
        title: str,
        subtitle: str = "",
        body: str = "",
        accept_text: str = "OK",
        cancel_text: str | None = None,
        minimum_width: int = 560,
    ):
        super().__init__(parent)
        self.setObjectName("ThemedMessageDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(minimum_width)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("DialogCard")
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        title_label = QLabel(title)
        title_label.setObjectName("DialogTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("DialogSubtitle")
            subtitle_label.setWordWrap(True)
            layout.addWidget(subtitle_label)

        if body:
            body_label = QLabel(body)
            body_label.setObjectName("DialogBody")
            body_label.setWordWrap(True)
            body_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(body_label)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 6, 0, 0)
        button_row.setSpacing(10)
        button_row.addStretch()

        if cancel_text is not None:
            cancel_button = QPushButton(cancel_text)
            cancel_button.setObjectName("SecondaryButton")
            cancel_button.clicked.connect(self.reject)
            button_row.addWidget(cancel_button)

        accept_button = QPushButton(accept_text)
        accept_button.setObjectName("PrimaryButton")
        accept_button.clicked.connect(self.accept)
        accept_button.setDefault(True)
        button_row.addWidget(accept_button)

        layout.addLayout(button_row)

    @classmethod
    def show(
        cls,
        parent,
        *,
        title: str,
        subtitle: str = "",
        body: str = "",
        accept_text: str = "OK",
        minimum_width: int = 560,
    ) -> None:
        dialog = cls(
            parent,
            title=title,
            subtitle=subtitle,
            body=body,
            accept_text=accept_text,
            cancel_text=None,
            minimum_width=minimum_width,
        )
        dialog.exec()

    @classmethod
    def confirm(
        cls,
        parent,
        *,
        title: str,
        subtitle: str = "",
        body: str = "",
        accept_text: str = "Continue",
        cancel_text: str = "Cancel",
        minimum_width: int = 560,
    ) -> bool:
        dialog = cls(
            parent,
            title=title,
            subtitle=subtitle,
            body=body,
            accept_text=accept_text,
            cancel_text=cancel_text,
            minimum_width=minimum_width,
        )
        return dialog.exec() == QDialog.DialogCode.Accepted


class ThemedProgressDialog(QDialog):
    """Compact themed progress dialog for long-running app actions."""

    def __init__(
        self,
        parent=None,
        *,
        title: str,
        subtitle: str = "",
        initial_status: str = "Preparing...",
        minimum_width: int = 620,
    ):
        super().__init__(parent)
        self.setObjectName("ThemedProgressDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(minimum_width)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("DialogCard")
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        title_label = QLabel(title)
        title_label.setObjectName("DialogTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("DialogSubtitle")
            subtitle_label.setWordWrap(True)
            layout.addWidget(subtitle_label)

        self.status_label = QLabel(initial_status)
        self.status_label.setObjectName("DialogStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("DialogProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        self.detail_label = QLabel("Canvas items are merged locally using stable Canvas IDs, so repeat syncs update existing data instead of duplicating it.")
        self.detail_label.setObjectName("DialogDetail")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

    def set_status(self, message: str, value: int | None = None):
        self.status_label.setText(message)
        if value is not None:
            self.progress_bar.setValue(max(0, min(100, int(value))))
