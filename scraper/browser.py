"""Camoufox (anti-detect Firefox) launcher for browser-based scraping.

Instaloader talks to Instagram's private HTTP API directly, which is what gets
fingerprinted and 429'd on datacenter IPs. Camoufox (github.com/daijro/camoufox)
is a hardened Firefox build that spoofs real device fingerprints and keeps
Playwright's automation hooks out of page-visible JavaScript, so scraping
through it looks like a normal person browsing instagram.com.

This module keeps every camoufox/playwright-specific detail in one place, same
as instagram_client.py does for instaloader. Usage:

    from scraper.browser import stealth_browser

    with stealth_browser(proxy_url=settings.proxy_url) as page:
        page.goto("https://www.instagram.com/natgeo/")
        html = page.content()

The browser binary itself is downloaded once via `python -m camoufox fetch`
(stored per-user by the OS, not in the repo/venv).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional
from urllib.parse import urlparse

from camoufox.sync_api import Camoufox

from utils.logger import get_logger

logger = get_logger(__name__)


def _proxy_config(proxy_url: str) -> Optional[dict]:
    """Convert a proxy URL (http://user:pass@host:port) to Playwright's proxy dict."""
    if not proxy_url:
        return None
    parsed = urlparse(proxy_url)
    if not parsed.hostname:
        logger.warning("Ignoring malformed proxy URL for browser: %r", proxy_url)
        return None
    config = {"server": f"{parsed.scheme or 'http'}://{parsed.hostname}:{parsed.port or 80}"}
    if parsed.username:
        config["username"] = parsed.username
    if parsed.password:
        config["password"] = parsed.password
    return config


@contextmanager
def stealth_browser(proxy_url: str = "", headless: bool = True) -> Iterator["Page"]:  # noqa: F821
    """Yield a Playwright Page inside a freshly-fingerprinted Camoufox instance.

    Each launch generates a new realistic device fingerprint automatically.
    When a proxy is configured, geoip=True makes Camoufox derive timezone,
    locale, and geolocation from the proxy's exit IP so they don't contradict
    each other — mismatches there are a classic bot tell.
    """
    proxy = _proxy_config(proxy_url)
    launch_kwargs = {
        "headless": headless,
        # Windows-only fingerprints: matches this machine locally, and on a
        # Linux CI runner it still presents as a plausible consumer device.
        "os": "windows",
    }
    if proxy:
        launch_kwargs["proxy"] = proxy
        launch_kwargs["geoip"] = True

    with Camoufox(**launch_kwargs) as browser:
        page = browser.new_page()
        try:
            yield page
        finally:
            page.close()
