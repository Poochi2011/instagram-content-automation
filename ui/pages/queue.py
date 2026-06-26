"""Queue page: downloaded posts awaiting OCR/repost prep, with image + OCR preview."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.data_table import SearchableTable


class QueuePage(QWidget):
    def __init__(self, context) -> None:
        super().__init__()
        self._context = context
        self._shortcodes: list[str] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 28)
        outer.setSpacing(16)
        outer.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(20)

        self.table = SearchableTable(
            ["Username", "Shortcode", "Status", "Downloaded"], "Search queue..."
        )
        self.table.table.itemSelectionChanged.connect(self._on_selection_changed)
        body.addWidget(self.table, stretch=3)

        body.addWidget(self._build_preview_panel(), stretch=2)
        outer.addLayout(body)

        self.refresh()

    def _build_header(self) -> QWidget:
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        title = QLabel("Queue")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Downloaded posts waiting for OCR and repost preparation.")
        subtitle.setObjectName("pageSubtitle")
        v.addWidget(title)
        v.addWidget(subtitle)
        return box

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("card")
        v = QVBoxLayout(panel)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(10)

        self.image_preview = QLabel("Select a post to preview")
        self.image_preview.setObjectName("pageSubtitle")
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setFixedHeight(220)
        self.image_preview.setScaledContents(False)
        v.addWidget(self.image_preview)

        ocr_label = QLabel("OCR Text")
        ocr_label.setObjectName("cardTitle")
        v.addWidget(ocr_label)

        self.ocr_preview = QTextEdit()
        self.ocr_preview.setReadOnly(True)
        v.addWidget(self.ocr_preview)

        self.mark_processed_btn = QPushButton("Mark as Processed")
        self.mark_processed_btn.setObjectName("primaryButton")
        self.mark_processed_btn.clicked.connect(self._mark_processed)
        self.mark_processed_btn.setEnabled(False)
        v.addWidget(self.mark_processed_btn)

        return panel

    def refresh(self) -> None:
        posts = self._context.post_repo.list_by_status()
        accounts_by_id = {a.id: a.username for a in self._context.account_repo.list_all()}
        self._shortcodes = [p.shortcode for p in posts]
        rows = [
            [
                accounts_by_id.get(p.account_id, "?"),
                p.shortcode,
                p.status,
                p.downloaded_at or "—",
            ]
            for p in posts
        ]
        self.table.set_rows(rows)
        self._clear_preview()

    def _on_selection_changed(self) -> None:
        row = self.table.selected_row_index()
        if row < 0:
            self._clear_preview()
            return
        shortcode = self.table.table.item(row, 1).text()
        post = self._context.post_repo.get_by_shortcode(shortcode)
        if not post:
            self._clear_preview()
            return

        if post.image_path:
            pixmap = QPixmap(post.image_path)
            if not pixmap.isNull():
                self.image_preview.setPixmap(
                    pixmap.scaledToHeight(220, Qt.TransformationMode.SmoothTransformation)
                )
            else:
                self.image_preview.setText("Image not found")
        else:
            self.image_preview.setText("No image yet")

        self.ocr_preview.setPlainText(post.ocr_text or "(no OCR text yet)")
        self.mark_processed_btn.setEnabled(True)
        self._selected_shortcode = shortcode

    def _clear_preview(self) -> None:
        self.image_preview.setPixmap(QPixmap())
        self.image_preview.setText("Select a post to preview")
        self.ocr_preview.clear()
        self.mark_processed_btn.setEnabled(False)
        self._selected_shortcode = None

    def _mark_processed(self) -> None:
        if getattr(self, "_selected_shortcode", None):
            self._context.post_repo.mark_processed(self._selected_shortcode)
            self.refresh()
