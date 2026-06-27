"""Publishes 'ready' posts to the destination Instagram account, unattended.

Each call to publish_due_posts() is one cycle: pick the oldest due post, try to
publish it, record the outcome, repeat up to max_per_cycle times (or until the
configured daily cap is hit). All retry state (attempt count, next attempt
time, last error) lives on the post row in SQLite, never in memory — so a
daemon restart or a fresh GitHub Actions run picks up exactly where the last
one left off instead of losing track of in-flight retries.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath

from config.settings import PROJECT_ROOT, Settings
from database.models import Post
from database.repository import ErrorRepository, PostMediaRepository, PostRepository
from publisher.graph_api_client import GraphAPIClient
from utils.exceptions import PermanentPublishError, TransientPublishError
from utils.logger import get_logger

logger = get_logger(__name__)

_DB_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"  # matches SQLite's datetime('now') format, so TEXT comparison sorts correctly
_MAX_BACKOFF_MINUTES = 24 * 60


def _now_str() -> str:
    return datetime.utcnow().strftime(_DB_TIME_FORMAT)


def _to_public_url(media_public_base_url: str, local_path: str) -> str:
    relative = Path(local_path).resolve().relative_to(PROJECT_ROOT)
    base = media_public_base_url.rstrip("/")
    return f"{base}/{PurePosixPath(relative.as_posix())}"


def _media_urls_for_post(post: Post, post_media_repo: PostMediaRepository, media_public_base_url: str) -> list[str]:
    local_paths = [post.image_path]
    local_paths.extend(m.image_path for m in post_media_repo.list_for_post(post.id))
    return [_to_public_url(media_public_base_url, p) for p in local_paths if p]


def publish_post(
    post: Post,
    settings: Settings,
    post_repo: PostRepository,
    post_media_repo: PostMediaRepository,
    error_repo: ErrorRepository,
) -> bool:
    """Try to publish one 'ready' post. Returns True on success."""
    client = GraphAPIClient(settings.ig_dest_access_token, settings.ig_dest_business_account_id)
    try:
        media_urls = _media_urls_for_post(post, post_media_repo, settings.media_public_base_url)
        media_id = client.publish(media_urls, post.repost_caption or "")
        post_repo.mark_published(post.shortcode, media_id)
        logger.info("Published post %s as Instagram media %s", post.shortcode, media_id)
        return True

    except TransientPublishError as exc:
        attempts_after = post.publish_attempts + 1
        if attempts_after >= settings.publish_retry_max_attempts:
            post_repo.mark_publish_permanently_failed(post.shortcode, str(exc))
            error_repo.log("publisher", f"Giving up after {attempts_after} attempts: {exc}", post.shortcode)
            logger.error("Post %s permanently failed after %d attempts: %s", post.shortcode, attempts_after, exc)
        else:
            backoff_minutes = min(
                settings.publish_retry_backoff_minutes * (2 ** post.publish_attempts), _MAX_BACKOFF_MINUTES
            )
            next_attempt = datetime.utcnow() + timedelta(minutes=backoff_minutes)
            post_repo.record_publish_failure(post.shortcode, str(exc), next_attempt.strftime(_DB_TIME_FORMAT))
            error_repo.log("publisher", str(exc), post.shortcode)
            logger.warning(
                "Transient publish failure for %s (attempt %d/%d), retrying in %d min: %s",
                post.shortcode, attempts_after, settings.publish_retry_max_attempts, backoff_minutes, exc,
            )
        return False

    except PermanentPublishError as exc:
        post_repo.mark_publish_permanently_failed(post.shortcode, str(exc))
        error_repo.log("publisher", str(exc), post.shortcode)
        logger.error("Permanent publish failure for %s: %s", post.shortcode, exc)
        return False


def publish_due_posts(
    settings: Settings,
    post_repo: PostRepository,
    post_media_repo: PostMediaRepository,
    error_repo: ErrorRepository,
) -> dict:
    """Publish up to settings.max_publish_per_cycle posts, never exceeding the daily cap."""
    if not settings.ig_dest_access_token or not settings.ig_dest_business_account_id:
        logger.info("Auto-publish skipped: destination Graph API credentials are not configured yet.")
        return {"published": 0, "failed": 0, "skipped_daily_cap": False}

    since_midnight_utc = datetime.utcnow().strftime("%Y-%m-%d 00:00:00")
    published_today = post_repo.count_published_since(since_midnight_utc)
    remaining_today = max(0, settings.max_publish_per_day - published_today)
    if remaining_today == 0:
        logger.info("Daily publish cap (%d) already reached; skipping this cycle.", settings.max_publish_per_day)
        return {"published": 0, "failed": 0, "skipped_daily_cap": True}

    to_attempt = min(settings.max_publish_per_cycle, remaining_today)
    published = 0
    failed = 0
    for post in post_repo.list_publishable(_now_str())[:to_attempt]:
        if publish_post(post, settings, post_repo, post_media_repo, error_repo):
            published += 1
        else:
            failed += 1

    return {"published": published, "failed": failed, "skipped_daily_cap": False}
