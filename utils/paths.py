"""Filesystem path helpers shared across modules."""

from __future__ import annotations

from pathlib import Path

from config.settings import PROJECT_ROOT


def ensure_dir(path: Path) -> Path:
    """Create a directory (and parents) if it doesn't exist, and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def account_download_dir(download_root: Path, username: str) -> Path:
    """Return (and create) the per-account subfolder under the download root."""
    return ensure_dir(download_root / username)


def logs_dir() -> Path:
    return ensure_dir(PROJECT_ROOT / "logs")
