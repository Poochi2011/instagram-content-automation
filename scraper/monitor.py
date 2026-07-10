"""Coordinates one monitoring pass: sync accounts.txt -> DB, check each
active account for a new post, download it, and record it.

This is the single entry point the CLI and the GUI both call — neither
talks to InstagramClient or the repositories directly.
"""

from __future__ import annotations

import random
import time
from pathlib import Path

from config.settings import Settings
from database.db import Database
from database.repository import AccountRepository, ErrorRepository, PostMediaRepository, PostRepository
from scraper.camoufox_client import CamoufoxInstagramClient
from scraper.instagram_client import PostData
from utils.exceptions import ScraperError
from utils.logger import get_logger
from utils.paths import account_download_dir

logger = get_logger(__name__)


def _read_usernames(path: Path) -> list[str]:
    if not path.exists():
        return []
    usernames = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().lstrip("@")
        if not line or line.startswith("#"):
            continue
        usernames.append(line)
    return usernames


def import_accounts_from_file(path: Path, account_repo: AccountRepository) -> int:
    """Import usernames from a text file (one per line, '#' comments ignored).

    Safe to call repeatedly — existing usernames are left untouched (no duplicates,
    no resetting is_active/last_checked_at). Returns the count of newly added accounts.
    """
    return account_repo.import_usernames(_read_usernames(path))


def bootstrap_accounts_if_empty(settings: Settings, account_repo: AccountRepository) -> None:
    """One-time seed from accounts.txt, only when the accounts table is still empty.

    After that first import, the DB (and therefore the GUI) is the source of truth —
    accounts.txt is never read automatically again. Use import_accounts_from_file()
    for any later, explicit bulk import.
    """
    if account_repo.list_all():
        return

    path = settings.accounts_file_path
    if not path.exists():
        path.write_text("# One Instagram username per line.\n", encoding="utf-8")
        return
    import_accounts_from_file(path, account_repo)


def _download_post(
    post_data: PostData,
    account_id: int,
    username: str,
    settings: Settings,
    client: InstagramClient,
    post_repo: PostRepository,
    post_media_repo: PostMediaRepository,
    error_repo: ErrorRepository,
) -> bool:
    """Create the post row and download its image slides. Returns True if any image
    content was downloaded (False for a video-only post, which gets marked 'error'
    instead — there's nothing to repost, but it's still tracked so it's never retried).
    """
    post_repo.create(
        account_id=account_id,
        shortcode=post_data.shortcode,
        post_url=post_data.post_url,
        caption=post_data.caption,
        posted_at=post_data.posted_at,
        is_carousel=post_data.is_carousel,
    )

    image_slides = [m for m in post_data.media if not m.is_video]
    skipped_video_slides = len(post_data.media) - len(image_slides)
    if skipped_video_slides:
        logger.warning(
            "Post %s from @%s has %d video slide(s); video reposting is not supported, skipping them.",
            post_data.shortcode, username, skipped_video_slides,
        )

    if not image_slides:
        error_repo.log("scraper", "Video-only post; repost not supported", username)
        post_repo.mark_error(post_data.shortcode)
        logger.info("Skipped video-only post %s from @%s", post_data.shortcode, username)
        return False

    dest_dir = account_download_dir(settings.download_folder_path, username)
    post = post_repo.get_by_shortcode(post_data.shortcode)
    for position, slide in enumerate(image_slides):
        suffix = "" if position == 0 else f"_{position}"
        image_path = dest_dir / f"{post_data.shortcode}{suffix}.jpg"
        client.download_image(slide.url, post_data.shortcode, image_path)
        if position == 0:
            post_repo.mark_downloaded(post_data.shortcode, str(image_path))
        else:
            post_media_repo.add(post.id, position, str(image_path))

    logger.info(
        "Downloaded post %s from @%s (%d slide(s))", post_data.shortcode, username, len(image_slides),
    )
    return True


def check_account(
    username: str,
    settings: Settings,
    client: InstagramClient,
    account_repo: AccountRepository,
    post_repo: PostRepository,
    post_media_repo: PostMediaRepository,
    error_repo: ErrorRepository,
) -> dict:
    """Check one account for its single latest post. Returns a result dict (never raises)."""
    result = {"username": username, "new_post": False, "shortcode": None, "error": None}
    try:
        latest = client.get_latest_post(username)
        if latest is None:
            account_repo.mark_checked(username)
            return result

        if post_repo.exists(latest.shortcode):
            account_repo.mark_checked(username, latest.shortcode)
            return result

        account = account_repo.upsert(username)
        # Set as soon as the row exists so the except block below can mark it
        # 'error' instead of leaving it stuck at 'new' forever if the download fails.
        result["shortcode"] = latest.shortcode
        result["new_post"] = _download_post(
            latest, account.id, username, settings, client, post_repo, post_media_repo, error_repo
        )
        account_repo.mark_checked(username, latest.shortcode)
        return result

    except ScraperError as exc:
        logger.error("Error checking @%s: %s", username, exc)
        error_repo.log("scraper", str(exc), username)
        if result["shortcode"]:
            post_repo.mark_error(result["shortcode"])
        account_repo.mark_checked(username)
        result["error"] = str(exc)
        return result


def backfill_account(
    username: str,
    settings: Settings,
    client: InstagramClient,
    account_repo: AccountRepository,
    post_repo: PostRepository,
    post_media_repo: PostMediaRepository,
    error_repo: ErrorRepository,
    max_posts: int,
) -> dict:
    """Fetch up to max_posts recent posts for one account (newest first), downloading
    any not already seen. Unlike check_account, this doesn't stop at the first
    already-known post — it always inspects up to max_posts, skipping duplicates
    individually, so it's safe to re-run without re-downloading anything.
    """
    result = {"username": username, "new_posts": 0, "error": None}
    try:
        posts = client.get_recent_posts(username, max_posts=max_posts)
        if not posts:
            account_repo.mark_checked(username)
            return result

        account = account_repo.upsert(username)
        for post_data in posts:
            if post_repo.exists(post_data.shortcode):
                continue
            if _download_post(
                post_data, account.id, username, settings, client, post_repo, post_media_repo, error_repo
            ):
                result["new_posts"] += 1

        account_repo.mark_checked(username, posts[0].shortcode)  # posts[0] is newest
        return result

    except ScraperError as exc:
        logger.error("Error backfilling @%s: %s", username, exc)
        error_repo.log("scraper", str(exc), username)
        account_repo.mark_checked(username)
        result["error"] = str(exc)
        return result


def _stagger() -> None:
    """Sleep a few seconds between per-account requests through the same browser
    session. A tight back-to-back burst across many accounts (no gap at all) is a
    much more bot-like request pattern than a human browsing session ever produces,
    even routed through a good residential IP -- observed this trip Instagram's
    login wall on every account in one run (2026-07-10) despite proven success on
    the same code/proxy minutes earlier with more naturally spaced-out requests.
    """
    time.sleep(random.uniform(3.0, 7.0))


def run_check(settings: Settings, db: Database) -> dict:
    """Run one full monitoring pass across all active accounts. Returns a summary dict."""
    account_repo = AccountRepository(db)
    post_repo = PostRepository(db)
    post_media_repo = PostMediaRepository(db)
    error_repo = ErrorRepository(db)

    bootstrap_accounts_if_empty(settings, account_repo)
    accounts = account_repo.list_all(active_only=True)

    try:
        with CamoufoxInstagramClient(settings.scraper_proxy_url) as client:
            results = []
            for i, acc in enumerate(accounts):
                if i > 0:
                    _stagger()
                results.append(
                    check_account(acc.username, settings, client, account_repo, post_repo, post_media_repo, error_repo)
                )
    except ScraperError as exc:
        logger.error("Scraper session failed to start: %s", exc)
        error_repo.log("scraper", str(exc))
        return {"checked": 0, "new_posts": 0, "results": [], "login_error": str(exc)}

    new_posts = sum(1 for r in results if r["new_post"])
    logger.info("Check complete: %d accounts checked, %d new posts", len(results), new_posts)
    return {"checked": len(results), "new_posts": new_posts, "results": results, "login_error": None}


def run_backfill(settings: Settings, db: Database, max_posts_per_account: int) -> dict:
    """Fetch each active account's recent post history (not just the latest one),
    to seed the queue with a batch in one pass. Useful while waiting on a cloud
    scraping fix: run this once from a residential IP, then let the existing
    daily publish cap drip the backlog out automatically.
    """
    account_repo = AccountRepository(db)
    post_repo = PostRepository(db)
    post_media_repo = PostMediaRepository(db)
    error_repo = ErrorRepository(db)

    bootstrap_accounts_if_empty(settings, account_repo)
    accounts = account_repo.list_all(active_only=True)

    try:
        with CamoufoxInstagramClient(settings.scraper_proxy_url) as client:
            results = []
            for i, acc in enumerate(accounts):
                if i > 0:
                    _stagger()
                results.append(
                    backfill_account(
                        acc.username, settings, client, account_repo, post_repo, post_media_repo, error_repo,
                        max_posts_per_account,
                    )
                )
    except ScraperError as exc:
        logger.error("Scraper session failed to start: %s", exc)
        error_repo.log("scraper", str(exc))
        return {"checked": 0, "new_posts": 0, "results": [], "login_error": str(exc)}

    new_posts = sum(r["new_posts"] for r in results)
    logger.info("Backfill complete: %d accounts checked, %d new posts", len(results), new_posts)
    return {"checked": len(results), "new_posts": new_posts, "results": results, "login_error": None}
