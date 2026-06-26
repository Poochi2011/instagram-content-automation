"""Coordinates one monitoring pass: sync accounts.txt -> DB, check each
active account for a new post, download it, and record it.

This is the single entry point the CLI and the GUI both call — neither
talks to InstagramClient or the repositories directly.
"""

from __future__ import annotations

from pathlib import Path

from config.settings import Settings
from database.db import Database
from database.repository import AccountRepository, ErrorRepository, PostRepository
from scraper.instagram_client import InstagramClient
from utils.exceptions import ScraperError
from utils.logger import get_logger
from utils.paths import account_download_dir

logger = get_logger(__name__)


def sync_accounts_file(settings: Settings, account_repo: AccountRepository) -> list[str]:
    """Read accounts.txt and ensure every listed username exists in the DB."""
    path = settings.accounts_file_path
    if not path.exists():
        path.write_text("# One Instagram username per line.\n", encoding="utf-8")
        return []

    usernames = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        usernames.append(line)
        account_repo.upsert(line)
    return usernames


def check_account(
    username: str,
    settings: Settings,
    client: InstagramClient,
    account_repo: AccountRepository,
    post_repo: PostRepository,
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
        post = post_repo.create(
            account_id=account.id,
            shortcode=latest.shortcode,
            post_url=latest.post_url,
            caption=latest.caption,
            posted_at=latest.posted_at,
        )

        dest_dir = account_download_dir(settings.download_folder_path, username)
        image_path = dest_dir / f"{latest.shortcode}.jpg"
        client.download_image(latest, image_path)
        post_repo.mark_downloaded(latest.shortcode, str(image_path))

        account_repo.mark_checked(username, latest.shortcode)
        result["new_post"] = True
        result["shortcode"] = latest.shortcode
        logger.info("Downloaded new post %s from @%s", latest.shortcode, username)
        return result

    except ScraperError as exc:
        logger.error("Error checking @%s: %s", username, exc)
        error_repo.log("scraper", str(exc), username)
        if result["shortcode"]:
            post_repo.mark_error(result["shortcode"])
        result["error"] = str(exc)
        return result


def run_check(settings: Settings, db: Database) -> dict:
    """Run one full monitoring pass across all active accounts. Returns a summary dict."""
    account_repo = AccountRepository(db)
    post_repo = PostRepository(db)
    error_repo = ErrorRepository(db)

    sync_accounts_file(settings, account_repo)

    client = InstagramClient(settings.instagram_username, settings.instagram_password)
    try:
        client.login_if_configured()
    except ScraperError as exc:
        logger.error("Login failed: %s", exc)
        error_repo.log("scraper", str(exc))
        return {"checked": 0, "new_posts": 0, "results": [], "login_error": str(exc)}

    accounts = account_repo.list_all(active_only=True)
    results = [
        check_account(acc.username, settings, client, account_repo, post_repo, error_repo)
        for acc in accounts
    ]

    new_posts = sum(1 for r in results if r["new_post"])
    logger.info("Check complete: %d accounts checked, %d new posts", len(results), new_posts)
    return {"checked": len(results), "new_posts": new_posts, "results": results, "login_error": None}
