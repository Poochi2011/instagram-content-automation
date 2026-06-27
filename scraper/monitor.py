"""Coordinates one monitoring pass: sync accounts.txt -> DB, check each
active account for a new post, download it, and record it.

This is the single entry point the CLI and the GUI both call — neither
talks to InstagramClient or the repositories directly.
"""

from __future__ import annotations

from pathlib import Path

from config.settings import Settings
from database.db import Database
from database.repository import AccountRepository, ErrorRepository, PostMediaRepository, PostRepository
from scraper.instagram_client import InstagramClient
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


def check_account(
    username: str,
    settings: Settings,
    client: InstagramClient,
    account_repo: AccountRepository,
    post_repo: PostRepository,
    post_media_repo: PostMediaRepository,
    error_repo: ErrorRepository,
) -> dict:
    """Check one account for a new post. Returns a result dict (never raises)."""
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
        post_repo.create(
            account_id=account.id,
            shortcode=latest.shortcode,
            post_url=latest.post_url,
            caption=latest.caption,
            posted_at=latest.posted_at,
            is_carousel=latest.is_carousel,
        )
        # Set as soon as the row exists so the except block below can mark it
        # 'error' instead of leaving it stuck at 'new' forever if the download fails.
        result["shortcode"] = latest.shortcode

        image_slides = [m for m in latest.media if not m.is_video]
        skipped_video_slides = len(latest.media) - len(image_slides)
        if skipped_video_slides:
            logger.warning(
                "Post %s from @%s has %d video slide(s); video reposting is not supported, skipping them.",
                latest.shortcode, username, skipped_video_slides,
            )

        if not image_slides:
            # Video-only post (no image slides at all) — nothing to repost.
            error_repo.log("scraper", "Video-only post; repost not supported", username)
            post_repo.mark_error(latest.shortcode)
            account_repo.mark_checked(username, latest.shortcode)
            logger.info("Skipped video-only post %s from @%s", latest.shortcode, username)
            return result

        dest_dir = account_download_dir(settings.download_folder_path, username)
        post = post_repo.get_by_shortcode(latest.shortcode)
        for position, slide in enumerate(image_slides):
            suffix = "" if position == 0 else f"_{position}"
            image_path = dest_dir / f"{latest.shortcode}{suffix}.jpg"
            client.download_image(slide.url, latest.shortcode, image_path)
            if position == 0:
                post_repo.mark_downloaded(latest.shortcode, str(image_path))
            else:
                post_media_repo.add(post.id, position, str(image_path))

        account_repo.mark_checked(username, latest.shortcode)
        result["new_post"] = True
        logger.info(
            "Downloaded new post %s from @%s (%d slide(s))",
            latest.shortcode, username, len(image_slides),
        )
        return result

    except ScraperError as exc:
        logger.error("Error checking @%s: %s", username, exc)
        error_repo.log("scraper", str(exc), username)
        if result["shortcode"]:
            post_repo.mark_error(result["shortcode"])
        account_repo.mark_checked(username)
        result["error"] = str(exc)
        return result


def run_check(settings: Settings, db: Database) -> dict:
    """Run one full monitoring pass across all active accounts. Returns a summary dict."""
    account_repo = AccountRepository(db)
    post_repo = PostRepository(db)
    post_media_repo = PostMediaRepository(db)
    error_repo = ErrorRepository(db)

    bootstrap_accounts_if_empty(settings, account_repo)

    client = InstagramClient(settings.instagram_username, settings.instagram_password)
    try:
        client.login_if_configured()
    except ScraperError as exc:
        logger.error("Login failed: %s", exc)
        error_repo.log("scraper", str(exc))
        return {"checked": 0, "new_posts": 0, "results": [], "login_error": str(exc)}

    accounts = account_repo.list_all(active_only=True)
    results = [
        check_account(acc.username, settings, client, account_repo, post_repo, post_media_repo, error_repo)
        for acc in accounts
    ]

    new_posts = sum(1 for r in results if r["new_post"])
    logger.info("Check complete: %d accounts checked, %d new posts", len(results), new_posts)
    return {"checked": len(results), "new_posts": new_posts, "results": results, "login_error": None}
