"""Dashboard page: at-a-glance stats, manual scan trigger, recent activity and errors."""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from scraper.monitor import run_check
from ui.widgets.data_table import SearchableTable
from ui.widgets.stat_card import StatCard
from ui.workers import CallableWorker


class DashboardPage(QWidget):
    def __init__(self, context) -> None:
        super().__init__()
        self._context = context
        self._worker: CallableWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        layout.addLayout(self._build_header())
        layout.addLayout(self._build_stat_cards())

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        activity_label = QLabel("Recent Activity")
        activity_label.setObjectName("cardTitle")
        layout.addWidget(activity_label)
        self.activity_table = SearchableTable(["Username", "Shortcode", "Status", "Time"], "Search activity...")
        layout.addWidget(self.activity_table, stretch=2)

        errors_label = QLabel("Recent Errors")
        errors_label.setObjectName("cardTitle")
        layout.addWidget(errors_label)
        self.errors_table = SearchableTable(["Source", "Message", "Account", "Time"], "Search errors...")
        layout.addWidget(self.errors_table, stretch=1)

        self.refresh()

    def _build_header(self) -> QHBoxLayout:
        h = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        self.status_subtitle = QLabel("Idle")
        self.status_subtitle.setObjectName("pageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(self.status_subtitle)
        h.addLayout(title_box)
        h.addStretch()

        self.run_check_btn = QPushButton("Run Check Now")
        self.run_check_btn.setObjectName("primaryButton")
        self.run_check_btn.clicked.connect(self._run_check)
        h.addWidget(self.run_check_btn)
        return h

    def _build_stat_cards(self) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setSpacing(16)
        self.card_accounts = StatCard("Monitored Accounts")
        self.card_today = StatCard("Posts Downloaded Today")
        self.card_ocr = StatCard("OCR Success Rate")
        self.card_last_scan = StatCard("Last Scan")
        for card in (self.card_accounts, self.card_today, self.card_ocr, self.card_last_scan):
            h.addWidget(card)
        return h

    def refresh(self) -> None:
        accounts = self._context.account_repo.list_all()
        posts = self._context.post_repo.list_by_status()
        today = date.today().isoformat()

        self.card_accounts.set_value(str(len(accounts)))
        self.card_accounts.set_subtext(f"{sum(1 for a in accounts if a.is_active)} active")

        self.card_today.set_value(str(self._context.post_repo.count_downloaded_since(today)))

        self.card_ocr.set_value(f"{self._context.post_repo.ocr_success_rate():.0f}%")

        last_scan = max((a.last_checked_at for a in accounts if a.last_checked_at), default=None)
        self.card_last_scan.set_value(last_scan or "Never")

        accounts_by_id = {a.id: a.username for a in accounts}
        self.activity_table.set_rows(
            [
                [
                    accounts_by_id.get(p.account_id, "?"),
                    p.shortcode,
                    p.status,
                    p.downloaded_at or p.created_at,
                ]
                for p in posts[:25]
            ]
        )

        self.errors_table.set_rows(
            [
                [e.source, e.message, e.account_username or "—", e.occurred_at]
                for e in self._context.error_repo.recent(25)
            ]
        )

    def _run_check(self) -> None:
        if self._worker is not None:
            return
        self.run_check_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.status_subtitle.setText("Scanning monitored accounts...")

        self._worker = CallableWorker(run_check, self._context.settings, self._context.db)
        self._worker.signals.finished.connect(self._on_check_finished)
        self._worker.signals.failed.connect(self._on_check_failed)
        self._worker.start()

    def _on_check_finished(self, result: dict) -> None:
        self.progress.setVisible(False)
        self.run_check_btn.setEnabled(True)
        self.status_subtitle.setText(
            f"Checked {result['checked']} accounts — {result['new_posts']} new post(s) found."
        )
        self._worker = None
        self.refresh()

    def _on_check_failed(self, message: str) -> None:
        self.progress.setVisible(False)
        self.run_check_btn.setEnabled(True)
        self.status_subtitle.setText(f"Scan failed: {message}")
        self._worker = None
