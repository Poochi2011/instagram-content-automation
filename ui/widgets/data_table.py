"""A sortable, searchable table widget used across the Accounts/Queue/Logs pages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class SearchableTable(QWidget):
    """Wraps a search box + QTableWidget. Populate via set_rows(); search filters rows live."""

    def __init__(self, headers: list[str], search_placeholder: str = "Search...") -> None:
        super().__init__()
        self._headers = headers
        self._raw_rows: list[list[str]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(search_placeholder)
        self.search_box.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search_box)

        self.table = QTableWidget()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSortingEnabled(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

    def set_rows(self, rows: list[list[str]]) -> None:
        """rows: list of string-cell rows, in the same order as headers."""
        self._raw_rows = rows
        self._render(rows)

    def _render(self, rows: list[list[str]]) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem(value))
        self.table.setSortingEnabled(True)

    def _apply_filter(self, text: str) -> None:
        text = text.strip().lower()
        if not text:
            self._render(self._raw_rows)
            return
        filtered = [row for row in self._raw_rows if any(text in cell.lower() for cell in row)]
        self._render(filtered)

    def selected_row_index(self) -> int:
        """Returns the row index in the *currently rendered* table, or -1 if none selected."""
        selected = self.table.selectionModel().selectedRows()
        return selected[0].row() if selected else -1
