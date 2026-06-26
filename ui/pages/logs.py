"""Log viewer page: tails logs/app.log with a search filter and refresh button."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from utils.paths import logs_dir

_MAX_LINES = 500


class LogsPage(QWidget):
    def __init__(self, context) -> None:
        super().__init__()
        self._context = context

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Logs")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Most recent application log output.")
        subtitle.setObjectName("pageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondaryButton")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter log lines...")
        self.search_box.textChanged.connect(self.refresh)
        layout.addWidget(self.search_box)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

        self.refresh()

    def refresh(self) -> None:
        log_path = logs_dir() / "app.log"
        if not log_path.exists():
            self.log_view.setPlainText("(no log file yet)")
            return

        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = lines[-_MAX_LINES:]

        query = self.search_box.text().strip().lower()
        if query:
            lines = [line for line in lines if query in line.lower()]

        self.log_view.setPlainText("\n".join(lines))
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())
