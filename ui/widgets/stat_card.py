"""Dashboard stat card: a title, a big value, and an optional subtext."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class StatCard(QWidget):
    def __init__(self, title: str, value: str = "—", subtext: str = "") -> None:
        super().__init__()
        self.setObjectName("card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        self._title_label = QLabel(title)
        self._title_label.setObjectName("cardTitle")

        self._value_label = QLabel(value)
        self._value_label.setObjectName("cardValue")

        self._subtext_label = QLabel(subtext)
        self._subtext_label.setObjectName("pageSubtitle")
        self._subtext_label.setVisible(bool(subtext))

        layout.addWidget(self._title_label)
        layout.addWidget(self._value_label)
        layout.addWidget(self._subtext_label)

    def set_value(self, value: str) -> None:
        self._value_label.setText(value)

    def set_subtext(self, subtext: str) -> None:
        self._subtext_label.setText(subtext)
        self._subtext_label.setVisible(bool(subtext))
