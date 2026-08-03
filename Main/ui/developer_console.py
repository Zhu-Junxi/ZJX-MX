from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from services.app_logging import get_app_log_bus, log_warning


class DeveloperConsole(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DeveloperToolsDialog")
        self.setWindowTitle("Developer Console")
        self.setModal(False)
        self.resize(900, 620)
        self.setMinimumSize(720, 460)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        if parent is not None:
            self.setStyleSheet(parent.styleSheet())

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(24, 24, 24, 24)
        outer_layout.setSpacing(0)

        card = QFrame()
        card.setObjectName("DetailsCard")
        outer_layout.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title_row = QHBoxLayout()
        title = QLabel("Developer Console")
        title.setObjectName("CardTitle")
        subtitle = QLabel("Errors, warnings, and terminal output")
        subtitle.setObjectName("MutedText")
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(subtitle)
        layout.addLayout(title_row)

        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("CodePreview")
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.log_view.setMinimumHeight(360)
        layout.addWidget(self.log_view, 1)

        command_row = QHBoxLayout()
        command_row.setSpacing(10)
        prompt = QLabel("Command")
        prompt.setObjectName("FieldLabel")
        self.command_input = QLineEdit()
        self.command_input.setObjectName("DialogInput")
        self.command_input.setEnabled(False)
        self.command_input.setPlaceholderText("Commands reserved for a future developer build")
        command_row.addWidget(prompt)
        command_row.addWidget(self.command_input, 1)
        layout.addLayout(command_row)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 4, 0, 0)
        button_row.setSpacing(10)

        copy_button = QPushButton("Copy")
        copy_button.setObjectName("SmallButton")
        clear_button = QPushButton("Clear View")
        clear_button.setObjectName("SmallButton")
        open_folder_button = QPushButton("Open Log Folder")
        open_folder_button.setObjectName("SmallButton")
        close_button = QPushButton("Close")
        close_button.setObjectName("SmallButton")

        copy_button.clicked.connect(self.copy_logs)
        clear_button.clicked.connect(self.clear_logs)
        open_folder_button.clicked.connect(self.open_log_folder)
        close_button.clicked.connect(self.close)

        button_row.addWidget(copy_button)
        button_row.addWidget(clear_button)
        button_row.addWidget(open_folder_button)
        button_row.addStretch()
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        self.log_bus = get_app_log_bus()
        self.load_existing_entries()
        self.log_bus.entry_added.connect(self.append_entry)

    def load_existing_entries(self):
        self.log_view.setPlainText("\n".join(self.log_bus.entries()))
        self.scroll_to_bottom()

    def append_entry(self, entry):
        self.log_view.appendPlainText(entry)
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def copy_logs(self):
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.log_view.toPlainText())

    def clear_logs(self):
        self.log_bus.clear_session()
        self.log_view.clear()

    def open_log_folder(self):
        log_file = self.log_bus.log_file_path
        if not log_file:
            log_warning("Open Log Folder requested before a log file was configured")
            QMessageBox.information(self, "Developer Console", "No log folder is available yet.")
            return

        folder = Path(log_file).parent
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def closeEvent(self, event):
        try:
            self.log_bus.entry_added.disconnect(self.append_entry)
        except (RuntimeError, TypeError):
            pass
        super().closeEvent(event)
