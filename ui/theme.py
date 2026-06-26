"""Design tokens and the QSS stylesheet for the dark, Linear/Notion-style UI."""

from __future__ import annotations

COLORS = {
    "bg": "#0f1115",
    "surface": "#161922",
    "surface_alt": "#1c2029",
    "border": "#272b36",
    "text": "#e6e8eb",
    "text_dim": "#9aa1ad",
    "text_faint": "#6b7280",
    "accent": "#6366f1",
    "accent_hover": "#7779f3",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "info": "#38bdf8",
}

RADIUS = 10
SPACING = 12

FONT_FAMILY = "Segoe UI, -apple-system, sans-serif"

STYLESHEET = f"""
* {{
    font-family: {FONT_FAMILY};
    color: {COLORS['text']};
}}

QMainWindow, QWidget#centralWidget {{
    background-color: {COLORS['bg']};
}}

QWidget#sidebar {{
    background-color: {COLORS['surface']};
    border-right: 1px solid {COLORS['border']};
}}

QPushButton#navButton {{
    background-color: transparent;
    color: {COLORS['text_dim']};
    border: none;
    border-radius: {RADIUS}px;
    text-align: left;
    padding: 10px 14px;
    font-size: 13px;
    font-weight: 500;
}}

QPushButton#navButton:hover {{
    background-color: {COLORS['surface_alt']};
    color: {COLORS['text']};
}}

QPushButton#navButtonActive {{
    background-color: {COLORS['accent']};
    color: white;
    border: none;
    border-radius: {RADIUS}px;
    text-align: left;
    padding: 10px 14px;
    font-size: 13px;
    font-weight: 600;
}}

QWidget#card {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: {RADIUS}px;
}}

QLabel#cardTitle {{
    color: {COLORS['text_dim']};
    font-size: 12px;
    font-weight: 600;
}}

QLabel#cardValue {{
    color: {COLORS['text']};
    font-size: 26px;
    font-weight: 700;
}}

QLabel#pageTitle {{
    font-size: 20px;
    font-weight: 700;
    color: {COLORS['text']};
}}

QLabel#pageSubtitle {{
    font-size: 13px;
    color: {COLORS['text_dim']};
}}

QPushButton#primaryButton {{
    background-color: {COLORS['accent']};
    color: white;
    border: none;
    border-radius: {RADIUS}px;
    padding: 9px 16px;
    font-size: 13px;
    font-weight: 600;
}}

QPushButton#primaryButton:hover {{
    background-color: {COLORS['accent_hover']};
}}

QPushButton#primaryButton:disabled {{
    background-color: {COLORS['surface_alt']};
    color: {COLORS['text_faint']};
}}

QPushButton#secondaryButton {{
    background-color: {COLORS['surface_alt']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: {RADIUS}px;
    padding: 9px 16px;
    font-size: 13px;
    font-weight: 500;
}}

QPushButton#secondaryButton:hover {{
    background-color: {COLORS['border']};
}}

QPushButton#dangerButton {{
    background-color: transparent;
    color: {COLORS['danger']};
    border: 1px solid {COLORS['danger']};
    border-radius: {RADIUS}px;
    padding: 6px 12px;
    font-size: 12px;
}}

QLineEdit, QSpinBox, QComboBox {{
    background-color: {COLORS['surface_alt']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 13px;
    color: {COLORS['text']};
}}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {COLORS['accent']};
}}

QTableView {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: {RADIUS}px;
    gridline-color: {COLORS['border']};
    selection-background-color: {COLORS['accent']};
    selection-color: white;
    font-size: 13px;
}}

QHeaderView::section {{
    background-color: {COLORS['surface_alt']};
    color: {COLORS['text_dim']};
    border: none;
    border-bottom: 1px solid {COLORS['border']};
    padding: 8px;
    font-size: 12px;
    font-weight: 600;
}}

QTextEdit, QPlainTextEdit {{
    background-color: {COLORS['surface_alt']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 8px;
    font-family: Consolas, monospace;
    font-size: 12px;
    color: {COLORS['text']};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
}}

QScrollBar::handle:vertical {{
    background: {COLORS['border']};
    border-radius: 5px;
    min-height: 20px;
}}

QProgressBar {{
    background-color: {COLORS['surface_alt']};
    border: none;
    border-radius: 6px;
    height: 8px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {COLORS['accent']};
    border-radius: 6px;
}}
"""
