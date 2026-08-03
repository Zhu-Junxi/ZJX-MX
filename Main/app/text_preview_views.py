from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QTransform
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.detail_text import details_pairs_from_text, make_wrap_friendly_text
from services.file_preview import is_structured_preview_html
from ui.components import card_frame, text_label


class TextPreviewViewsMixin:
    """Preview/details card construction and right-panel display helpers."""

    def build_text_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self.text_scroll_area = QScrollArea()
        self.text_scroll_area.setWidgetResizable(True)
        self.text_scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.text_content_widget = QWidget()
        self.text_content_layout = QVBoxLayout(self.text_content_widget)
        self.text_content_layout.setContentsMargins(0, 0, 0, 0)
        self.text_content_layout.setSpacing(12)
        self.text_content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.text_scroll_area.setWidget(self.text_content_widget)
        layout.addWidget(self.text_scroll_area)

        return page

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()

    def create_content_card(self, title=None, body=None, code=False, card_type="preview", html=False):
        card, layout = card_frame("PreviewCard" if card_type == "preview" else "DetailsCard")

        if title:
            title_label = text_label(title, "CardTitle")
            layout.addWidget(title_label)

        if body:
            if html or is_structured_preview_html(body):
                body_widget = QTextEdit()
                body_widget.setObjectName("RichDocumentPreview")
                body_widget.setReadOnly(True)
                body_widget.setFrameShape(QFrame.Shape.NoFrame)
                body_widget.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
                body_widget.setHtml(body.strip())
                body_widget.setMinimumHeight(420)
                layout.addWidget(body_widget)
            elif code:
                body_widget = QTextEdit()
                body_widget.setObjectName("CodePreview")
                body_widget.setReadOnly(True)
                body_widget.setFrameShape(QFrame.Shape.NoFrame)
                body_widget.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
                body_widget.setText(body.strip())
                body_widget.setMinimumHeight(360)
                layout.addWidget(body_widget)
            else:
                body_label = text_label(make_wrap_friendly_text(body.strip()), "CardBody", selectable=True)
                layout.addWidget(body_label)

        return card

    def stop_media_preview(self):
        player = getattr(self, "media_player", None)
        if player is not None:
            player.stop()

    def _process_preview_release_events(self, cycles=4):
        app = QApplication.instance()
        if app is not None:
            for _ in range(cycles):
                app.processEvents()

    def _connect_media_player_signals(self):
        self.media_player.positionChanged.connect(self.update_media_position)
        self.media_player.durationChanged.connect(self.update_media_duration)
        self.media_player.playbackStateChanged.connect(self.update_media_button)

    def _rebuild_media_backend(self):
        if not hasattr(self, "media_video_widget"):
            return

        volume_value = getattr(getattr(self, "media_volume_slider", None), "value", lambda: 75)()

        old_player = getattr(self, "media_player", None)
        if old_player is not None:
            try:
                old_player.stop()
                old_player.setSource(QUrl())
                old_player.setVideoOutput(None)
                old_player.setAudioOutput(None)
            except RuntimeError:
                pass
            old_player.deleteLater()

        old_audio = getattr(self, "media_audio", None)
        if old_audio is not None:
            old_audio.deleteLater()

        self.media_player = QMediaPlayer(self)
        self.media_audio = QAudioOutput(self)
        self.media_audio.setVolume(max(0.0, min(1.0, float(volume_value or 0) / 100.0)))
        self.media_audio.setMuted((volume_value or 0) <= 0)
        self.media_player.setAudioOutput(self.media_audio)
        self.media_player.setVideoOutput(self.media_video_widget)
        self._connect_media_player_signals()
        self.update_media_button()

    def release_current_preview_handles(self):
        """Release file handles held by preview widgets before file operations."""
        player = getattr(self, "media_player", None)
        if player is not None:
            player.stop()
            player.setSource(QUrl())
            player.setVideoOutput(None)
            player.setAudioOutput(None)
            self._process_preview_release_events()
            self._rebuild_media_backend()

        document = getattr(self, "pdf_document", None)
        if document is not None:
            if hasattr(document, "close"):
                document.close()
            else:
                document.load("")

        pdf_buffer = getattr(self, "_pdf_preview_buffer", None)
        if pdf_buffer is not None:
            pdf_buffer.close()
            pdf_buffer.deleteLater()

        image_label = getattr(self, "image_label", None)
        if image_label is not None:
            image_label.clear()

        self._current_image_pixmap = None
        self._image_rotation_degrees = 0
        self._current_pdf_path = None
        self._current_media_path = None
        self._pdf_preview_buffer = None
        self._pdf_preview_bytes = None

        self._process_preview_release_events()

    def open_preview_path_external(self, path):
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))



    def populate_details_layout(self, layout, details_text):
        self.clear_layout(layout)
        pairs, notes = details_pairs_from_text(details_text)

        row = 0
        for key, value in pairs:
            key_label = text_label(key, "DetailKey", word_wrap=False)
            key_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

            compact_path = self.detail_value_should_stay_single_line(key, value)
            display_value = str(value or "") if compact_path else make_wrap_friendly_text(value)
            value_label = text_label(display_value, "DetailValue", word_wrap=not compact_path, selectable=True)
            value_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            value_label.setMinimumWidth(0)
            if str(value or "") != display_value or len(str(value or "")) > 80:
                value_label.setToolTip(str(value or ""))

            layout.addWidget(key_label, row, 0)
            layout.addWidget(value_label, row, 1)
            row += 1

        if notes:
            note_label = text_label(notes, "CardBody", selectable=True)
            layout.addWidget(note_label, row, 0, 1, 2)
            row += 1

        if row == 0:
            empty_label = text_label("No details available.", "MutedText")
            layout.addWidget(empty_label, 0, 0, 1, 2)

    def detail_value_should_stay_single_line(self, key, value):
        key = str(key or "").strip().lower()
        value = str(value or "")
        if key in {"absolute path", "relative path", "path", "url"}:
            return False
        return ("\\" in value or "/" in value) and len(value) > 42

    def create_details_card(self, title="Details", details_text=""):
        card, outer_layout = card_frame("DetailsCard", spacing=12)

        title_label = text_label(title, "CardTitle")
        outer_layout.addWidget(title_label)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        outer_layout.addLayout(grid)

        self.populate_details_layout(grid, details_text)
        return card

    def create_tip_card(self, title, tips, subtitle=None):
        card, layout = card_frame("DetailsCard")

        title_label = text_label(title, "CardTitle")
        layout.addWidget(title_label)

        if subtitle:
            subtitle_label = text_label(subtitle, "MutedText")
            layout.addWidget(subtitle_label)

        for tip in tips:
            tip_label = text_label(f"• {tip}", "CardBody", selectable=True)
            layout.addWidget(tip_label)

        return card

    def show_card_page(self, title, subtitle, cards):
        self.stop_media_preview()
        self.detail_title.setText(title)
        self.detail_subtitle.setText(subtitle)
        self.detail_stack.setCurrentWidget(self.text_page)
        self.clear_layout(self.text_content_layout)

        for card in cards:
            self.text_content_layout.addWidget(card)

        self.text_content_layout.addStretch()
        self.register_app_scroll_widgets()
        self.scroll_tuner.refresh()
        self.animate_detail_change()

    def add_text_content_cards(self, text):
        self.clear_layout(self.text_content_layout)

        text = (text or "").strip()

        if not text:
            self.text_content_layout.addWidget(self.create_content_card("Preview", "Nothing to show yet."))
            self.text_content_layout.addWidget(self.create_details_card("Details", "Status: Empty"))
            self.text_content_layout.addStretch()
            return

        preview_marker = "==================== PREVIEW ===================="

        if preview_marker in text:
            details, preview = text.split(preview_marker, 1)
            # Product rule: Preview is always above Details.
            self.text_content_layout.addWidget(self.create_content_card("Preview", preview.strip(), code=not is_structured_preview_html(preview), html=is_structured_preview_html(preview), card_type="preview"))
            self.text_content_layout.addWidget(self.create_details_card("Details", details.strip()))
            self.text_content_layout.addStretch()
            return

        paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
        colon_lines = sum(1 for line in text.splitlines() if ":" in line)

        if colon_lines >= 2:
            self.text_content_layout.addWidget(self.create_content_card("Preview", paragraphs[0] if paragraphs else "Information"))
            self.text_content_layout.addWidget(self.create_details_card("Details", text))
        elif len(paragraphs) <= 2:
            self.text_content_layout.addWidget(self.create_content_card("Preview", text))
            self.text_content_layout.addWidget(self.create_details_card("Details", "Type: Information"))
        else:
            first = paragraphs[0]
            remaining = "\n\n".join(paragraphs[1:])
            self.text_content_layout.addWidget(self.create_content_card("Preview", first))
            self.text_content_layout.addWidget(self.create_content_card("Details", remaining, card_type="details"))

        self.text_content_layout.addStretch()

    def build_image_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.image_scroll_area = QScrollArea()
        self.image_scroll_area.setWidgetResizable(True)
        self.image_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.image_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.image_scroll_area.setMinimumWidth(0)
        self.image_scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_scroll_area.viewport().installEventFilter(self)

        content = QWidget()
        content.setMinimumWidth(0)
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        self.image_content_widget = content

        image_panel = QFrame()
        image_panel.setObjectName("PreviewCard")
        image_panel.setMinimumWidth(0)
        image_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.image_preview_panel = image_panel
        image_layout = QVBoxLayout(image_panel)
        image_layout.setContentsMargins(18, 18, 18, 18)
        image_layout.setSpacing(12)

        preview_title = QLabel("Preview")
        preview_title.setObjectName("CardTitle")

        image_header = QHBoxLayout()
        image_header.setContentsMargins(0, 0, 0, 0)
        image_header.setSpacing(8)
        image_header.addWidget(preview_title)
        image_header.addStretch()

        rotate_button_size = self.zpx(34) if hasattr(self, "zpx") else 34
        self.image_rotate_left_btn = QPushButton("↶")
        self.image_rotate_left_btn.setObjectName("ImageRotateButton")
        self.image_rotate_left_btn.setToolTip("Rotate image left")
        self.image_rotate_left_btn.setFixedSize(rotate_button_size, rotate_button_size)
        self.image_rotate_left_btn.clicked.connect(lambda: self.rotate_image_preview(-90))

        self.image_rotate_right_btn = QPushButton("↷")
        self.image_rotate_right_btn.setObjectName("ImageRotateButton")
        self.image_rotate_right_btn.setToolTip("Rotate image right")
        self.image_rotate_right_btn.setFixedSize(rotate_button_size, rotate_button_size)
        self.image_rotate_right_btn.clicked.connect(lambda: self.rotate_image_preview(90))

        image_header.addWidget(self.image_rotate_left_btn)
        image_header.addWidget(self.image_rotate_right_btn)

        self.image_label = QLabel()
        self.image_label.setObjectName("ImagePreview")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(360)
        self.image_label.setMinimumWidth(0)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        image_layout.addLayout(image_header)
        image_layout.addWidget(self.image_label, 1)

        details_panel = QFrame()
        details_panel.setObjectName("DetailsCard")
        details_panel.setMinimumWidth(0)
        details_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        details_outer_layout = QVBoxLayout(details_panel)
        details_outer_layout.setContentsMargins(18, 16, 18, 16)
        details_outer_layout.setSpacing(12)

        details_title = QLabel("Details")
        details_title.setObjectName("CardTitle")
        details_outer_layout.addWidget(details_title)

        self.image_details_layout = QGridLayout()
        self.image_details_layout.setContentsMargins(0, 0, 0, 0)
        self.image_details_layout.setHorizontalSpacing(18)
        self.image_details_layout.setVerticalSpacing(10)
        self.image_details_layout.setColumnStretch(0, 0)
        self.image_details_layout.setColumnStretch(1, 1)
        details_outer_layout.addLayout(self.image_details_layout)

        content_layout.addWidget(image_panel)
        content_layout.addWidget(details_panel)
        content_layout.addStretch()

        self.image_scroll_area.setWidget(content)
        layout.addWidget(self.image_scroll_area)

        return page

    def build_pdf_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.pdf_document = QPdfDocument(self)

        panel = QFrame()
        panel.setObjectName("PreviewCard")
        self.media_preview_panel = panel
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 18, 18, 18)
        panel_layout.setSpacing(12)

        top_row = QHBoxLayout()
        title = QLabel("PDF Preview")
        title.setObjectName("CardTitle")
        self.pdf_open_button = QPushButton("Open Externally")
        self.pdf_open_button.setObjectName("SmallButton")
        self.pdf_open_button.clicked.connect(lambda: self.open_preview_path_external(getattr(self, "_current_pdf_path", None)))
        top_row.addWidget(title)
        top_row.addStretch()
        top_row.addWidget(self.pdf_open_button)

        self.pdf_view = QPdfView()
        self.pdf_view.setObjectName("PdfPreview")
        self.pdf_view.setDocument(self.pdf_document)
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.pdf_view.setPageSpacing(10)
        self.pdf_view.setMinimumHeight(520)

        panel_layout.addLayout(top_row)
        panel_layout.addWidget(self.pdf_view, 1)

        details_panel = QFrame()
        details_panel.setObjectName("DetailsCard")
        self.media_details_panel = details_panel
        details_layout = QVBoxLayout(details_panel)
        details_layout.setContentsMargins(18, 16, 18, 16)
        details_layout.setSpacing(12)
        details_title = QLabel("Details")
        details_title.setObjectName("CardTitle")
        details_layout.addWidget(details_title)
        self.pdf_details_layout = QGridLayout()
        self.pdf_details_layout.setContentsMargins(0, 0, 0, 0)
        self.pdf_details_layout.setHorizontalSpacing(18)
        self.pdf_details_layout.setVerticalSpacing(10)
        details_layout.addLayout(self.pdf_details_layout)

        layout.addWidget(panel, 1)
        layout.addWidget(details_panel)
        return page

    def build_media_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.media_page_layout = layout

        self.media_player = QMediaPlayer(self)
        self.media_audio = QAudioOutput(self)
        self.media_audio.setVolume(0.75)
        self.media_player.setAudioOutput(self.media_audio)

        panel = QFrame()
        panel.setObjectName("PreviewCard")
        self.media_preview_panel = panel
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 18, 18, 18)
        panel_layout.setSpacing(14)

        top_row = QHBoxLayout()
        self.media_preview_title = QLabel("Media Preview")
        self.media_preview_title.setObjectName("CardTitle")
        self.media_open_button = QPushButton("Open Externally")
        self.media_open_button.setObjectName("SmallButton")
        self.media_open_button.clicked.connect(lambda: self.open_preview_path_external(getattr(self, "_current_media_path", None)))
        top_row.addWidget(self.media_preview_title)
        top_row.addStretch()
        top_row.addWidget(self.media_open_button)

        self.media_video_widget = QVideoWidget()
        self.media_video_widget.setObjectName("MediaPreview")
        self.media_video_widget.setMinimumHeight(380)
        self.media_player.setVideoOutput(self.media_video_widget)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 8, 0, 2)
        controls.setSpacing(14)
        self.media_play_button = QPushButton("Play")
        self.media_play_button.setObjectName("SmallButton")
        self.media_play_button.setMinimumWidth(78)
        self.media_play_button.setMinimumHeight(34)
        self.media_play_button.clicked.connect(self.toggle_media_playback)

        self.media_position_slider = QSlider(Qt.Orientation.Horizontal)
        self.media_position_slider.setObjectName("MediaSlider")
        self.media_position_slider.setMinimumWidth(180)
        self.media_position_slider.setMinimumHeight(36)
        self.media_position_slider.sliderMoved.connect(self.seek_media_position)

        self.media_time_label = QLabel("00:00 / 00:00")
        self.media_time_label.setObjectName("CardMeta")
        self.media_time_label.setMinimumWidth(104)

        self.media_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.media_volume_slider.setObjectName("MediaVolume")
        self.media_volume_slider.setRange(0, 100)
        self.media_volume_slider.setValue(75)
        self.media_volume_slider.setMinimumWidth(120)
        self.media_volume_slider.setMaximumWidth(170)
        self.media_volume_slider.setMinimumHeight(36)
        self.media_volume_slider.valueChanged.connect(self.set_media_volume)
        self.media_volume_label = QLabel("Volume")
        self.media_volume_label.setObjectName("CardMeta")
        self.media_volume_label.setMinimumWidth(52)

        controls.addWidget(self.media_play_button)
        controls.addWidget(self.media_position_slider, 1)
        controls.addWidget(self.media_time_label)
        controls.addSpacing(4)
        controls.addWidget(self.media_volume_label)
        controls.addWidget(self.media_volume_slider)

        self._connect_media_player_signals()

        panel_layout.addLayout(top_row)
        panel_layout.addWidget(self.media_video_widget, 1)
        panel_layout.addLayout(controls)

        details_panel = QFrame()
        details_panel.setObjectName("DetailsCard")
        self.media_details_panel = details_panel
        details_layout = QVBoxLayout(details_panel)
        details_layout.setContentsMargins(18, 16, 18, 16)
        details_layout.setSpacing(12)
        details_title = QLabel("Details")
        details_title.setObjectName("CardTitle")
        details_layout.addWidget(details_title)
        self.media_details_layout = QGridLayout()
        self.media_details_layout.setContentsMargins(0, 0, 0, 0)
        self.media_details_layout.setHorizontalSpacing(18)
        self.media_details_layout.setVerticalSpacing(7)
        self.media_details_layout.setColumnStretch(0, 0)
        self.media_details_layout.setColumnStretch(1, 1)
        details_layout.addLayout(self.media_details_layout)

        layout.addWidget(panel, 0)
        layout.addWidget(details_panel)
        layout.addStretch()
        return page

    def seek_media_position(self, position):
        player = getattr(self, "media_player", None)
        if player is not None:
            player.setPosition(position)

    def show_preview_details_page(self, title, subtitle="", preview_text="", details_text="", preview_code=False):
        """Show a clean Preview + Details layout without onboarding/help copy."""
        self.stop_media_preview()
        self.detail_title.setText(title)
        self.detail_subtitle.setText(subtitle)
        self.detail_stack.setCurrentWidget(self.text_page)

        self.clear_layout(self.text_content_layout)
        self.text_content_layout.addWidget(
            self.create_content_card(
                "Preview",
                preview_text or "No file selected.",
                code=preview_code,
                card_type="preview",
            )
        )
        self.text_content_layout.addWidget(
            self.create_details_card("Details", details_text or "Status: No resource selected.")
        )
        self.text_content_layout.addStretch()
        self.animate_detail_change()

    def show_text_page(self, title, subtitle, text):
        self.stop_media_preview()
        self.detail_title.setText(title)
        self.detail_subtitle.setText(subtitle)
        self.detail_stack.setCurrentWidget(self.text_page)
        self.add_text_content_cards(text)
        self.animate_detail_change()

    def show_image_page(self, title, subtitle, pixmap, details):
        self.stop_media_preview()
        self.detail_title.setText(title)
        self.detail_subtitle.setText(subtitle)
        self.detail_stack.setCurrentWidget(self.image_page)

        self._current_image_pixmap = pixmap
        self._image_rotation_degrees = 0
        self.update_image_preview_scale()
        self.populate_details_layout(self.image_details_layout, details)
        self.animate_detail_change()

    def rotate_image_preview(self, degrees):
        pixmap = getattr(self, "_current_image_pixmap", None)
        if pixmap is None or pixmap.isNull():
            return
        self._image_rotation_degrees = (getattr(self, "_image_rotation_degrees", 0) + degrees) % 360
        self.update_image_preview_scale()

    def update_image_preview_scale(self):
        pixmap = getattr(self, "_current_image_pixmap", None)
        image_label = getattr(self, "image_label", None)
        if pixmap is None or image_label is None or pixmap.isNull():
            return

        viewport_width = 0
        scroll_area = getattr(self, "image_scroll_area", None)
        if scroll_area is not None and scroll_area.viewport() is not None:
            viewport_width = scroll_area.viewport().width()

        label_width = image_label.width()
        available_width = max(240, viewport_width or label_width or 900)
        # Card and label margins are 18px each side, plus a little breathing room.
        target_width = max(220, available_width - 48)
        target_height = max(220, min(520, int(self.height() * 0.58) if hasattr(self, "height") else 500))

        rotation = getattr(self, "_image_rotation_degrees", 0) % 360
        display_pixmap = pixmap
        if rotation:
            display_pixmap = pixmap.transformed(QTransform().rotate(rotation), Qt.TransformationMode.SmoothTransformation)

        scaled = display_pixmap.scaled(
            target_width,
            target_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        image_label.setPixmap(scaled)

    def show_pdf_page(self, title, subtitle, path, details):
        self.stop_media_preview()
        self.detail_title.setText(title)
        self.detail_subtitle.setText(subtitle)
        self.detail_stack.setCurrentWidget(self.pdf_page)
        self._current_pdf_path = Path(path)
        self.load_pdf_preview_from_memory(self.pdf_document, path)
        self.populate_details_layout(self.pdf_details_layout, details)
        self.animate_detail_change()

    def load_pdf_preview_from_memory(self, document, path):
        document.close()

        pdf_buffer = getattr(self, "_pdf_preview_buffer", None)
        if pdf_buffer is not None:
            pdf_buffer.close()
            pdf_buffer.deleteLater()

        self._pdf_preview_bytes = QByteArray(Path(path).read_bytes())
        self._pdf_preview_buffer = QBuffer(self)
        self._pdf_preview_buffer.setData(self._pdf_preview_bytes)
        self._pdf_preview_buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        document.load(self._pdf_preview_buffer)

    def show_media_page(self, title, subtitle, path, details, media_kind="video"):
        self.detail_title.setText(title)
        self.detail_subtitle.setText(subtitle)
        self.detail_stack.setCurrentWidget(self.media_page)
        self._current_media_path = Path(path)
        self.media_preview_title.setText("Audio Preview" if media_kind == "audio" else "Video Preview")
        audio_mode = media_kind == "audio"
        self.media_video_widget.setVisible(not audio_mode)
        if audio_mode:
            self.media_page_layout.setStretch(0, 0)
            self.media_page_layout.setStretch(1, 0)
            self.media_page_layout.setStretch(2, 1)
            self.media_preview_panel.setMinimumHeight(150)
            self.media_preview_panel.setMaximumHeight(190)
            self.media_details_panel.setMaximumHeight(16777215)
        else:
            self.media_page_layout.setStretch(0, 1)
            self.media_page_layout.setStretch(1, 0)
            self.media_page_layout.setStretch(2, 0)
            self.media_preview_panel.setMinimumHeight(0)
            self.media_preview_panel.setMaximumHeight(16777215)
            self.media_details_panel.setMaximumHeight(16777215)
        self.media_player.stop()
        self.media_player.setAudioOutput(self.media_audio)
        self.media_player.setVideoOutput(None if audio_mode else self.media_video_widget)
        self.media_player.setSource(QUrl.fromLocalFile(str(path)))
        self.set_media_volume(self.media_volume_slider.value())
        self.media_position_slider.setValue(0)
        self.media_time_label.setText("00:00 / 00:00")
        self.update_media_button()
        self.populate_details_layout(self.media_details_layout, details)
        self.animate_detail_change()

    def toggle_media_playback(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()

    def update_media_position(self, position):
        if not self.media_position_slider.isSliderDown():
            self.media_position_slider.setValue(position)
        self.update_media_time_label()

    def update_media_duration(self, duration):
        self.media_position_slider.setRange(0, max(0, duration))
        self.update_media_time_label()

    def set_media_volume(self, value):
        volume = max(0.0, min(1.0, float(value or 0) / 100.0))
        self.media_audio.setMuted(volume <= 0)
        self.media_audio.setVolume(volume)

    def update_media_button(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_play_button.setText("Pause")
        else:
            self.media_play_button.setText("Play")

    def update_media_time_label(self):
        position = self.media_player.position()
        duration = self.media_player.duration()
        self.media_time_label.setText(f"{self.format_media_time(position)} / {self.format_media_time(duration)}")

    def format_media_time(self, milliseconds):
        seconds = max(0, int(milliseconds or 0) // 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
