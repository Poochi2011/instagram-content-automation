"""Small colored pill label used to show a post/account status at a glance."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from ui.theme import COLORS

_STATUS_COLORS = {
    "new": COLORS["info"],
    "downloaded": COLORS["warning"],
    "ocr_done": COLORS["warning"],
    "ready": COLORS["success"],
    "processed": COLORS["text_faint"],
    "error": COLORS["danger"],
    "active": COLORS["success"],
    "inactive": COLORS["text_faint"],
}


class StatusBadge(QLabel):
    def __init__(self, status: str) -> None:
        super().__init__(status.replace("_", " ").title())
        self.set_status(status)

    def set_status(self, status: str) -> None:
        self.setText(status.replace("_", " ").title())
        color = _STATUS_COLORS.get(status, COLORS["text_dim"])
        self.setStyleSheet(
            f"background-color: {color}22; color: {color}; border-radius: 8px; "
            f"padding: 3px 10px; font-size: 11px; font-weight: 600;"
        )
