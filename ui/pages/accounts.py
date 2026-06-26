"""Accounts page: add/remove monitored Instagram usernames, toggle monitoring."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ui.widgets.data_table import SearchableTable


class AccountsPage(QWidget):
    def __init__(self, context) -> None:
        super().__init__()
        self._context = context

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_add_row())

        self.table = SearchableTable(
            ["Username", "Status", "Last Checked", "Last Post"], "Search accounts..."
        )
        layout.addWidget(self.table)

        actions = QHBoxLayout()
        self.toggle_btn = QPushButton("Toggle Active/Inactive")
        self.toggle_btn.setObjectName("secondaryButton")
        self.toggle_btn.clicked.connect(self._toggle_selected)
        self.remove_btn = QPushButton("Remove Account")
        self.remove_btn.setObjectName("dangerButton")
        self.remove_btn.clicked.connect(self._remove_selected)
        actions.addWidget(self.toggle_btn)
        actions.addWidget(self.remove_btn)
        actions.addStretch()
        layout.addLayout(actions)

        self.refresh()

    def _build_header(self) -> QWidget:
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        title = QLabel("Accounts")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Manage the Instagram accounts being monitored for new posts.")
        subtitle.setObjectName("pageSubtitle")
        v.addWidget(title)
        v.addWidget(subtitle)
        return box

    def _build_add_row(self) -> QWidget:
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Instagram username (without @)")
        add_btn = QPushButton("Add Account")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self._add_account)
        h.addWidget(self.username_input)
        h.addWidget(add_btn)
        return box

    def refresh(self) -> None:
        accounts = self._context.account_repo.list_all()
        rows = [
            [
                a.username,
                "Active" if a.is_active else "Inactive",
                a.last_checked_at or "Never",
                a.last_post_shortcode or "—",
            ]
            for a in accounts
        ]
        self.table.set_rows(rows)

    def _add_account(self) -> None:
        username = self.username_input.text().strip().lstrip("@")
        if not username:
            return
        self._context.account_repo.upsert(username)
        self.username_input.clear()
        self.refresh()

    def _selected_username(self) -> str | None:
        row = self.table.selected_row_index()
        if row < 0:
            return None
        return self.table.table.item(row, 0).text()

    def _toggle_selected(self) -> None:
        username = self._selected_username()
        if not username:
            return
        account = self._context.account_repo.get_by_username(username)
        if account:
            self._context.account_repo.set_active(username, not account.is_active)
            self.refresh()

    def _remove_selected(self) -> None:
        username = self._selected_username()
        if not username:
            return
        self._context.account_repo.remove(username)
        self.refresh()
