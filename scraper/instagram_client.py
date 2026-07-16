"""Thin wrapper around Instaloader: one client, one Instagram session.

Keeps every instaloader-specific call in one place so the rest of the app
only deals with plain dicts/values and our own exception types.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import instaloader
from PIL import Image

from utils.exceptions import DownloadError, LoginRequiredError, RateLimitError, ScraperError
from utils.logger import get_logger

logger = get_logger(__name__)

SESSIONS_DIR = Path(__file__).resolve().parent.parent / "config" / "sessions"


@dataclass
class MediaItem:
    """One slide of a post (a single-image post has exactly one)."""

    url: str
    is_video: bool


@dataclass
class PostData:
    """Plain data pulled from an instaloader Post, decoupled from the library type."""

    shortcode: str
    post_url: str
    caption: Optional[str]
    posted_at: str
    is_carousel: bool
    media: list[MediaItem]


class InstagramClient:
    """Wraps an instaloader.Instaloader instance for read-only profile/post access."""

    def __init__(self, username: str = "", password: str = "", proxy_url: str = "") -> None:
        self._loader = instaloader.Instaloader(
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            post_metadata_txt_pattern="",
            quiet=True,
            # Defaults are request_timeout=300s x max_connection_attempts=3 — up to
            # 15 minutes hung on a single rate-limited/unreachable account. With
            # several accounts checked every cycle, that risks an hourly cron job
            # piling up for hours. Fail fast instead; a rate-limited account just
            # gets logged as an error and retried next cycle.
            request_timeout=20.0,
            max_connection_attempts=1,
            sleep=False,
            # The "iPhone" CDN variant (only fetched when logged in) is inconsistently
            # encoded — progressive JPEG or even WebP-with-a-.jpg-name — and Instagram's
            # Graph API content-publishing endpoint rejects both. download_image() also
            # re-encodes defensively, but avoiding this variant in the first place means
            # fewer requests per post too.
            iphone_support=False,
        )
        self._username = username
        self._password = password
        self._proxy_url = proxy_url
        self._logged_in = False

    def _ensure_proxy_applied(self) -> None:
        """Set the configured proxy on whatever requests.Session is currently active.

        Instaloader replaces self._loader.context._session wholesale on login and on
        load_session_from_file(), which would silently drop a proxy set any earlier —
        so this is called right before every actual network call instead of once at
        construction time. Routes scraping through a residential proxy so GitHub
        Actions' (otherwise rate-limited) datacenter IPs aren't what Instagram sees.
        """
        if not self._proxy_url:
            return
        session = self._loader.context._session
        session.proxies.update({"http": self._proxy_url, "https": self._proxy_url})

    def login_if_configured(self) -> None:
        """Log in only if credentials were provided; anonymous access works for public profiles.

        Reuses a saved session file across runs so the app never has to re-send the
        password (or hit a 2FA prompt) on every scheduled check — required for
        unattended 24/7 operation. Only falls back to a fresh password login if no
        valid session file exists yet.
        """
        if not self._username or not self._password:
            logger.info("No Instagram credentials configured; using anonymous access.")
            return

        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        session_path = SESSIONS_DIR / f"{self._username}.session"

        if session_path.exists():
            try:
                self._loader.load_session_from_file(self._username, str(session_path))
                self._logged_in = True
                self._ensure_proxy_applied()
                logger.info("Restored saved Instagram session for %s", self._username)
                return
            except (instaloader.exceptions.InvalidArgumentException, FileNotFoundError) as exc:
                logger.warning("Saved session invalid, will re-login: %s", exc)

        self._ensure_proxy_applied()
        try:
            self._loader.login(self._username, self._password)
            self._loader.save_session_to_file(str(session_path))
            self._logged_in = True
            logger.info("Logged in to Instagram as %s and saved session", self._username)
        except instaloader.exceptions.TwoFactorAuthRequiredException as exc:
            raise LoginRequiredError(
                "Instagram requires two-factor authentication; complete the login once "
                "interactively (instaloader --login=<username>) so a session file is saved, "
                "then this app can reuse it."
            ) from exc
        except instaloader.exceptions.ConnectionException as exc:
            raise RateLimitError(f"Login failed (possible rate limit): {exc}") from exc
        except instaloader.exceptions.InstaloaderException as exc:
            raise LoginRequiredError(f"Instagram login failed: {exc}") from exc

    def get_latest_post(self, username: str) -> Optional[PostData]:
        """Return the most recent post for a public profile, or None if it has no posts."""
        posts = self.get_recent_posts(username, max_posts=1)
        return posts[0] if posts else None

    def get_recent_posts(self, username: str, max_posts: int = 1) -> list[PostData]:
        """Return up to max_posts most recent posts for a public profile, newest first.

        Used both for the normal one-post-per-cycle check (max_posts=1) and for a
        manual backfill to seed the queue with a batch of recent history at once
        (e.g. while waiting on proxy setup, scraping from a local/residential IP).
        """
        self._ensure_proxy_applied()
        try:
            profile = instaloader.Profile.from_username(self._loader.context, username)
            posts = []
            for post in profile.get_posts():
                posts.append(self._post_to_data(post))
                if len(posts) >= max_posts:
                    break
            return posts
        except instaloader.exceptions.ProfileNotExistsException as exc:
            raise ScraperError(f"Profile '{username}' does not exist: {exc}") from exc
        except instaloader.exceptions.LoginRequiredException as exc:
            raise LoginRequiredError(f"Profile '{username}' requires login: {exc}") from exc
        except instaloader.exceptions.ConnectionException as exc:
            raise RateLimitError(f"Connection issue fetching '{username}' (possible rate limit): {exc}") from exc
        except instaloader.exceptions.InstaloaderException as exc:
            raise ScraperError(f"Failed to fetch posts for '{username}': {exc}") from exc

    def _post_to_data(self, post) -> PostData:
        return PostData(
            shortcode=post.shortcode,
            post_url=f"https://www.instagram.com/p/{post.shortcode}/",
            caption=post.caption,
            posted_at=post.date_utc.isoformat(),
            is_carousel=(post.typename == "GraphSidecar"),
            media=self._extract_media(post),
        )

    @staticmethod
    def _extract_media(post) -> list[MediaItem]:
        """All slides of a post. Video slides are included (is_video=True) but the caller
        does not download or repost them — video reposting is out of scope (the loader is
        configured with download_videos=False project-wide).
        """
        if post.typename == "GraphSidecar":
            return [
                MediaItem(url=node.video_url if node.is_video else node.display_url, is_video=node.is_video)
                for node in post.get_sidecar_nodes()
            ]
        return [MediaItem(url=post.url, is_video=post.is_video)]

    def download_image(self, image_url: str, shortcode: str, destination_path) -> None:
        """Download a single image slide to an exact file path using the loader's HTTP session.

        Instagram's CDN serves images in whatever format/encoding it feels like
        (progressive JPEG, WebP saved with a .jpg name, etc.) — Graph API's content
        publishing endpoint rejects some of these with an opaque "media type" error.
        Re-encoding through Pillow to a clean baseline JPEG guarantees a format Graph
        API accepts, regardless of what Instagram actually served.
        """
        self._ensure_proxy_applied()
        try:
            self._loader.context.get_and_write_raw(image_url, str(destination_path))
        except instaloader.exceptions.InstaloaderException as exc:
            raise DownloadError(f"Failed to download image for {shortcode}: {exc}") from exc
        except OSError as exc:
            raise DownloadError(f"Failed to write image file for {shortcode}: {exc}") from exc

        try:
            with Image.open(destination_path) as img:
                img.convert("RGB").save(destination_path, "JPEG", quality=92)
        except OSError as exc:
            raise DownloadError(f"Failed to re-encode image for {shortcode}: {exc}") from exc
