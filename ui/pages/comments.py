"""Comments page: auto-reply activity on the destination account.

Shows every comment the responder has seen with its classification and reply
state. The important bucket is 'flagged' — crisis language, real questions,
accusations — which the automation deliberately leaves for a human. After
answering one of those on Instagram, select it and click "Mark as Handled"
so it stops showing as needing attention.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.data_table import SearchableTable

_STATUS_FILTERS = ["all", "flagged", "drafted", "replied", "pending", "skipped", "error"]


class CommentsPage(QWidget):
    def __init__(self, context) -> None:
        super().__init__()
        self._context = context
        self._ig_comment_ids: list[str] = []
        self._selected_ig_comment_id: str | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 28)
        outer.setSpacing(16)
        outer.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(20)

        self.table = SearchableTable(
            ["Username", "Comment", "Class", "Status", "When"], "Search comments..."
        )
        self.table.table.itemSelectionChanged.connect(self._on_selection_changed)
        body.addWidget(self.table, stretch=3)

        body.addWidget(self._build_detail_panel(), stretch=2)
        outer.addLayout(body)

        self.refresh()

    def _build_header(self) -> QWidget:
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)

        title_box = QVBoxLayout()
        title = QLabel("Comments")
        title.setObjectName("pageTitle")
        self.subtitle = QLabel("Auto-reply activity on the destination account.")
        self.subtitle.setObjectName("pageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(self.subtitle)
        h.addLayout(title_box)
        h.addStretch()

        self.status_filter = QComboBox()
        self.status_filter.addItems(_STATUS_FILTERS)
        self.status_filter.currentTextChanged.connect(lambda _t: self.refresh())
        h.addWidget(self.status_filter)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondaryButton")
        refresh_btn.clicked.connect(self.refresh)
        h.addWidget(refresh_btn)
        return box

    def _build_detail_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("card")
        v = QVBoxLayout(panel)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(10)

        comment_label = QLabel("Comment")
        comment_label.setObjectName("cardTitle")
        v.addWidget(comment_label)

        self.comment_view = QTextEdit()
        self.comment_view.setReadOnly(True)
        v.addWidget(self.comment_view)

        reply_label = QLabel("Reply (drafted or sent)")
        reply_label.setObjectName("cardTitle")
        v.addWidget(reply_label)

        self.reply_view = QTextEdit()
        self.reply_view.setReadOnly(True)
        v.addWidget(self.reply_view)

        self.mark_handled_btn = QPushButton("Mark as Handled")
        self.mark_handled_btn.setObjectName("primaryButton")
        self.mark_handled_btn.clicked.connect(self._mark_handled)
        self.mark_handled_btn.setEnabled(False)
        v.addWidget(self.mark_handled_btn)

        return panel

    def refresh(self) -> None:
        status = self.status_filter.currentText()
        comments = self._context.comment_repo.list_by_status(None if status == "all" else status)

        counts = self._context.comment_repo.count_by_status()
        flagged = counts.get("flagged", 0)
        attention = f" — {flagged} flagged for your attention" if flagged else ""
        self.subtitle.setText("Auto-reply activity on the destination account." + attention)

        rows = [
            [
                c.username or "?",
                (c.text or "").replace("\n", " ")[:80],
                c.classification or "—",
                c.status,
                c.replied_at or c.commented_at or "—",
            ]
            for c in comments
        ]
        self._comments_by_row_key = {(r[0], r[1]): c for r, c in zip(rows, comments)}
        self._comments = comments
        self.table.set_rows(rows)
        self._clear_detail()

    def _on_selection_changed(self) -> None:
        row = self.table.selected_row_index()
        if row < 0:
            self._clear_detail()
            return
        # Comment text is truncated in the table, so resolve the row back to the
        # full record via username + truncated-text pair.
        key = (self.table.table.item(row, 0).text(), self.table.table.item(row, 1).text())
        comment = self._comments_by_row_key.get(key)
        if not comment:
            self._clear_detail()
            return

        self._selected_ig_comment_id = comment.ig_comment_id
        header = f"@{comment.username or '?'} · {comment.commented_at or 'unknown time'}\n\n"
        self.comment_view.setPlainText(header + (comment.text or "(no text)"))
        reply = comment.reply_text or "(no reply drafted)"
        if comment.last_error:
            reply += f"\n\nLast error: {comment.last_error}"
        self.reply_view.setPlainText(reply)
        self.mark_handled_btn.setEnabled(comment.status in ("flagged", "pending", "drafted"))

    def _clear_detail(self) -> None:
        self._selected_ig_comment_id = None
        self.comment_view.clear()
        self.reply_view.clear()
        self.mark_handled_btn.setEnabled(False)

    def _mark_handled(self) -> None:
        if self._selected_ig_comment_id:
            self._context.comment_repo.mark_skipped(self._selected_ig_comment_id, "handled_manually")
            self.refresh()
