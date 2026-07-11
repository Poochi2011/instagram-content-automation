"""Camoufox-based Instagram scraper: renders real (anonymous) browser pages
instead of hitting Instagram's private GraphQL API directly.

Instagram now blocks anonymous GraphQL access outright, regardless of IP
reputation (proxy or not) -- see CONTEXT.md. A real, anonymous browser session
loading instagram.com's actual pages is not subject to that specific block,
since it's the same access logged-out human visitors get. This is the
default scraper as of 2026-07; scraper/instagram_client.py (Instaloader) is
kept for a possible future login-based path but is not currently used by
monitor.py.

Separately, the residential proxy identity itself can still get login-walled
or become unreliable (slow/flaky) from cumulative traffic -- see
scraper/proxy_rotation.py and monitor.py's grouped-session-with-retry logic,
added after this was observed 2026-07-11.

Known limitation vs the Instaloader path: carousel posts are only captured as
a single representative image (the first slide). Reliably detecting and
ordering every slide from the embed page's DOM was not solved here, so
multi-slide extraction is not attempted -- is_carousel is always False on
posts from this client.
"""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

from scraper.browser import stealth_browser
from scraper.instagram_client import MediaItem, PostData
from utils.exceptions import DownloadError, ScraperError
from utils.logger import get_logger

logger = get_logger(__name__)

_PROFILE_TIMEOUT_MS = 75000
_POST_TIMEOUT_MS = 60000
# How long to poll for real content to hydrate before giving up. domcontentloaded
# fires on Instagram's initial empty shell, well before its JS bundle finishes
# downloading and rendering over a slow residential proxy connection -- observed
# needing 30+ seconds in practice (2026-07-11), far more than a fixed short sleep
# ever covered. Polling (wait_for_selector/wait_for_function) returns as soon as
# content appears, so a fast connection isn't penalized by this generous ceiling.
_HYDRATION_TIMEOUT_MS = 45000


class CamoufoxInstagramClient:
    """Anonymous, browser-rendered Instagram scraper.

    A context manager: opens one Camoufox session for the whole `with` block
    so a monitoring run across many accounts doesn't pay browser-launch cost
    (a few seconds) per account.

        with CamoufoxInstagramClient(proxy_url) as client:
            posts = client.get_recent_posts("someaccount", max_posts=5)
    """

    def __init__(self, proxy_url: str = "") -> None:
        self._proxy_url = proxy_url
        self._browser_cm = None
        self._page = None

    def __enter__(self) -> "CamoufoxInstagramClient":
        self._browser_cm = stealth_browser(proxy_url=self._proxy_url, headless=True)
        self._page = self._browser_cm.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._browser_cm is not None:
            self._browser_cm.__exit__(exc_type, exc, tb)
        self._page = None
        self._browser_cm = None

    def login_if_configured(self) -> None:
        """No-op: this client is always anonymous. Exists so monitor.py can
        treat CamoufoxInstagramClient and InstagramClient interchangeably.
        """
        return

    def get_latest_post(self, username: str) -> Optional[PostData]:
        posts = self.get_recent_posts(username, max_posts=1)
        return posts[0] if posts else None

    def get_recent_posts(self, username: str, max_posts: int = 1) -> list[PostData]:
        if self._page is None:
            raise ScraperError("CamoufoxInstagramClient must be used as a context manager (with ... as client).")

        shortcodes = self._fetch_profile_shortcodes(username, max_posts)
        posts: list[PostData] = []
        for i, shortcode in enumerate(shortcodes):
            if i > 0:
                time.sleep(random.uniform(2.0, 4.0))
            try:
                post = self._fetch_post(username, shortcode)
            except Exception as exc:
                logger.warning("Camoufox: failed to fetch post %s for @%s: %s", shortcode, username, exc)
                continue
            if post:
                posts.append(post)
        return posts

    def _fetch_profile_shortcodes(self, username: str, max_posts: int) -> list[str]:
        try:
            self._page.goto(
                f"https://www.instagram.com/{username}/", timeout=_PROFILE_TIMEOUT_MS, wait_until="domcontentloaded"
            )
        except Exception as exc:
            raise ScraperError(f"Failed to load profile @{username}: {exc}") from exc

        if "/accounts/login" in self._page.url:
            raise ScraperError(f"Profile @{username} redirected to a login wall.")

        try:
            self._page.wait_for_selector("a[href*='/p/']", timeout=_HYDRATION_TIMEOUT_MS)
        except Exception:
            # Could be a genuinely empty/private profile, or hydration that never
            # finished. A login redirect can also happen mid-hydration, not just
            # on the initial navigation, so re-check it here too.
            if "/accounts/login" in self._page.url:
                raise ScraperError(f"Profile @{username} redirected to a login wall.")
            logger.warning(
                "No post links appeared for @%s within %dms; profile may be empty, or the page never finished loading.",
                username, _HYDRATION_TIMEOUT_MS,
            )

        links = self._page.eval_on_selector_all("a[href*='/p/']", "els => els.map(e => e.href)")
        shortcodes: list[str] = []
        seen: set[str] = set()
        for link in links:
            parts = [p for p in link.split("/") if p]
            if "p" in parts:
                shortcode = parts[parts.index("p") + 1]
                if shortcode not in seen:
                    seen.add(shortcode)
                    shortcodes.append(shortcode)
            if len(shortcodes) >= max_posts:
                break
        return shortcodes

    def _fetch_post(self, username: str, shortcode: str) -> Optional[PostData]:
        url = f"https://www.instagram.com/p/{shortcode}/embed/captioned"
        self._page.goto(url, timeout=_POST_TIMEOUT_MS, wait_until="domcontentloaded")

        real_image_js = (
            "() => Array.from(document.querySelectorAll('img')).some(e => "
            "(e.src.includes('cdninstagram') || e.src.includes('fbcdn')) "
            "&& !e.src.includes('s100x100') && !e.src.includes('s150x150') && !e.src.includes('profile_pic'))"
        )
        try:
            self._page.wait_for_function(real_image_js, timeout=_HYDRATION_TIMEOUT_MS)
        except Exception:
            logger.warning(
                "Post %s (@%s) didn't render a real image within %dms.", shortcode, username, _HYDRATION_TIMEOUT_MS,
            )

        images = self._page.eval_on_selector_all(
            "img",
            "els => els.map(e => e.src)"
            ".filter(s => s.includes('cdninstagram') || s.includes('fbcdn'))"
            ".filter(s => !s.includes('s100x100') && !s.includes('s150x150') && !s.includes('profile_pic'))",
        )
        if not images:
            logger.warning("No image found for post %s (@%s); skipping.", shortcode, username)
            return None

        try:
            raw_caption = self._page.eval_on_selector(".Caption", "el => el.innerText") or ""
        except Exception:
            raw_caption = ""
        lines = raw_caption.split("\n", 2)
        caption = lines[2].strip() if len(lines) > 2 else (raw_caption.strip() or None)

        time_els = self._page.eval_on_selector_all("time", "els => els.map(e => e.getAttribute('datetime'))")
        posted_at = time_els[0] if time_els else None

        return PostData(
            shortcode=shortcode,
            post_url=f"https://www.instagram.com/p/{shortcode}/",
            caption=caption,
            posted_at=posted_at,
            is_carousel=False,  # single representative image only -- see module docstring
            media=[MediaItem(url=images[0], is_video=False)],
        )

    def download_image(self, image_url: str, shortcode: str, destination_path) -> None:
        """Download a single image via a plain proxied HTTP request (no browser needed
        for this part) and re-encode to a clean baseline JPEG, same as InstagramClient
        does -- Graph API's content-publishing endpoint rejects some CDN encodings.
        """
        proxies = {"http": self._proxy_url, "https": self._proxy_url} if self._proxy_url else None
        try:
            response = requests.get(image_url, proxies=proxies, timeout=30)
            response.raise_for_status()
            Path(destination_path).write_bytes(response.content)
        except requests.exceptions.RequestException as exc:
            raise DownloadError(f"Failed to download image for {shortcode}: {exc}") from exc

        try:
            with Image.open(destination_path) as img:
                img.convert("RGB").save(destination_path, "JPEG", quality=92)
        except OSError as exc:
            raise DownloadError(f"Failed to re-encode image for {shortcode}: {exc}") from exc
