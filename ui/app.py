"""QApplication bootstrap and main window: sidebar navigation + stacked pages."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QStackedWidget, QWidget

from config.settings import Settings, load_settings
from database.db import Database
from database.repository import AccountRepository, CommentRepository, ErrorRepository, PostRepository
from ui.pages.accounts import AccountsPage
from ui.pages.comments import CommentsPage
from ui.pages.dashboard import DashboardPage
from ui.pages.logs import LogsPage
from ui.pages.queue import QueuePage
from ui.pages.settings import SettingsPage
from ui.theme import STYLESHEET
from ui.widgets.sidebar import Sidebar
from utils.logger import setup_logging


@dataclass
class AppContext:
    """Shared app-wide handles passed into every page: settings, DB, repositories."""

    settings: Settings
    db: Database
    account_repo: AccountRepository
    post_repo: PostRepository
    error_repo: ErrorRepository
    comment_repo: CommentRepository

    @classmethod
    def build(cls) -> "AppContext":
        settings = load_settings()
        db = Database(settings.database_file_path)
        db.initialize_schema()
        return cls(
            settings=settings,
            db=db,
            account_repo=AccountRepository(db),
            post_repo=PostRepository(db),
            error_repo=ErrorRepository(db),
            comment_repo=CommentRepository(db),
        )


class MainWindow(QMainWindow):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.setWindowTitle("Instagram Content Automation")
        self.resize(1280, 800)

        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.navigate.connect(self._navigate)
        layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        self.dashboard_page = DashboardPage(context)
        self.accounts_page = AccountsPage(context)
        self.queue_page = QueuePage(context)
        self.comments_page = CommentsPage(context)
        self.logs_page = LogsPage(context)
        self.settings_page = SettingsPage(context)

        self._pages = {
            "dashboard": self.dashboard_page,
            "accounts": self.accounts_page,
            "queue": self.queue_page,
            "comments": self.comments_page,
            "logs": self.logs_page,
            "settings": self.settings_page,
        }
        for page in self._pages.values():
            self.stack.addWidget(page)

        self._navigate("dashboard")

    def _navigate(self, key: str) -> None:
        page = self._pages.get(key)
        if page is None:
            return
        self.sidebar.set_active(key)
        if hasattr(page, "refresh"):
            page.refresh()
        self.stack.setCurrentWidget(page)


def run_app() -> None:
    """Entry point called from main.py --gui."""
    context = AppContext.build()
    setup_logging(context.settings.log_level)

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)

    window = MainWindow(context)
    window.show()

    exit_code = app.exec()
    context.db.close()
    sys.exit(exit_code)
