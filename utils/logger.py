"""Centralized logging setup: rotating file handler + console handler.

Important: handlers attach to the console via stderr, never stdout, so the
CLI's JSON output (printed to stdout for n8n) is never polluted by log lines.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from utils.paths import logs_dir

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_CONFIGURED = False


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger once. Safe to call multiple times."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    file_handler = RotatingFileHandler(
        logs_dir() / "app.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler(stream=sys.stderr)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Get a module-level logger. Call setup_logging() first (main.py does this)."""
    return logging.getLogger(name)
