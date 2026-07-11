"""Application settings: typed access to config.json with safe defaults."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

# Env vars override config.json — lets CI (GitHub Actions secrets) inject credentials
# without ever writing them to a file that could be committed.
_ENV_OVERRIDES = {
    "instagram_username": "INSTAGRAM_USERNAME",
    "instagram_password": "INSTAGRAM_PASSWORD",
    "tesseract_path": "TESSERACT_PATH",
    "ig_dest_access_token": "IG_DEST_ACCESS_TOKEN",
    "ig_dest_business_account_id": "IG_DEST_BUSINESS_ACCOUNT_ID",
    "media_public_base_url": "MEDIA_PUBLIC_BASE_URL",
    "scraper_proxy_url": "SCRAPER_PROXY_URL",
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"
CONFIG_EXAMPLE_PATH = PROJECT_ROOT / "config" / "config.example.json"


@dataclass
class Settings:
    """Strongly-typed view of config.json. Paths are stored relative to PROJECT_ROOT."""

    accounts_file: str = "accounts.txt"
    download_folder: str = "downloads"
    database_path: str = "database/app.db"
    tesseract_path: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    polling_interval_minutes: int = 30
    theme: str = "dark"
    log_level: str = "INFO"
    instagram_username: str = ""
    instagram_password: str = ""
    # Full proxy URL incl. credentials, e.g. http://user:pass@host:port — routes
    # scraping through a residential proxy so datacenter IPs (GitHub Actions
    # runners) aren't what Instagram sees. Used for both http:// and https:// traffic.
    scraper_proxy_url: str = ""

    # Destination-account auto-publish (Instagram Graph API).
    ig_dest_access_token: str = ""
    ig_dest_business_account_id: str = ""
    # Repo root, not the downloads folder — the relative path (e.g. downloads/x.jpg)
    # is computed from PROJECT_ROOT and appended, so this should NOT end in /downloads.
    media_public_base_url: str = ""  # e.g. https://raw.githubusercontent.com/<user>/<repo>/main
    max_publish_per_cycle: int = 2
    max_publish_per_day: int = 16
    publish_retry_max_attempts: int = 5
    publish_retry_backoff_minutes: int = 15

    @property
    def accounts_file_path(self) -> Path:
        return PROJECT_ROOT / self.accounts_file

    @property
    def download_folder_path(self) -> Path:
        return PROJECT_ROOT / self.download_folder

    @property
    def database_file_path(self) -> Path:
        return PROJECT_ROOT / self.database_path

    def to_dict(self) -> dict:
        return asdict(self)


def load_settings(path: Path = CONFIG_PATH) -> Settings:
    """Load settings from config.json, falling back to config.example.json, then defaults.

    If config.json does not exist yet, it is created from the example/defaults so the
    rest of the app always has a real file to read and the user has something to edit.
    """
    if not path.exists():
        source = CONFIG_EXAMPLE_PATH if CONFIG_EXAMPLE_PATH.exists() else None
        data = json.loads(source.read_text(encoding="utf-8")) if source else {}
        values = {**Settings().to_dict(), **data}
        save_settings(Settings(**values), path)  # persist without secrets from env
        _apply_env_overrides(values)
        return Settings(**values)

    raw = json.loads(path.read_text(encoding="utf-8"))
    defaults = Settings().to_dict()
    # Unknown keys in the file are ignored; missing keys fall back to defaults.
    merged = {**defaults, **{k: v for k, v in raw.items() if k in defaults}}
    _apply_env_overrides(merged)
    return Settings(**merged)


def _apply_env_overrides(values: dict) -> None:
    for field_name, env_var in _ENV_OVERRIDES.items():
        env_value = os.environ.get(env_var)
        if env_value:
            values[field_name] = env_value


def save_settings(settings: Settings, path: Path = CONFIG_PATH) -> None:
    """Persist settings to config.json, creating the parent directory if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings.to_dict(), indent=2), encoding="utf-8")
