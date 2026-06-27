"""Left navigation sidebar."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

NAV_ITEMS = [
    ("dashboard", "📊  Dashboard"),
    ("accounts", "👤  Accounts"),
    ("queue", "📥  Queue"),
    ("logs", "📜  Logs"),
    ("settings", "⚙️  Settings"),
]


class Sidebar(QWidget):
    """Emits navigate(page_key) when a nav button is clicked."""

    navigate = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("sidebar")
        self.setFixedWidth(200)

        self._buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 20)
        layout.setSpacing(4)

        brand = QLabel("IG AUTOMATION")
        brand.setObjectName("cardTitle")
        brand.setContentsMargins(8, 0, 0, 16)
        layout.addWidget(brand)

        for key, label in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setObjectName("navButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, k=key: self.navigate.emit(k))
            layout.addWidget(btn)
            self._buttons[key] = btn

        layout.addStretch()
        self.set_active("dashboard")

    def set_active(self, key: str) -> None:
        for k, btn in self._buttons.items():
            btn.setObjectName("navButtonActive" if k == key else "navButton")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
