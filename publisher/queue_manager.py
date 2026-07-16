"""Prepares downloaded posts for reposting and tracks their queue status.

Note: this does not post to Instagram. It runs OCR, builds the repost
caption, and marks the post 'ready'/'processed' in the DB. The actual
publish API call is a placeholder until those credentials are provided.
"""

from __future__ import annotations

from pathlib import Path

from database.models import Post
from database.repository import AccountRepository, ErrorRepository, PostRepository
from ocr.extractor import extract_text
from publisher.caption_builder import build_repost_caption
from publisher.content_filter import screen_texts
from utils.exceptions import OCRError
from utils.logger import get_logger

logger = get_logger(__name__)


def prepare_post(
    post: Post,
    username: str,
    tesseract_path: str,
    post_repo: PostRepository,
    error_repo: ErrorRepository,
    blocked_keywords: list[str],
) -> bool:
    """Run OCR + build caption for a single downloaded post. Returns True on success."""
    if not post.image_path:
        return False

    try:
        text = extract_text(Path(post.image_path), tesseract_path)
        post_repo.mark_ocr_done(post.shortcode, text)

        # Screen caption + OCR'd overlay text for adult/explicit keywords. A hit
        # rejects the post here so it never becomes 'ready' and never publishes.
        blocked = screen_texts([post.caption, text], blocked_keywords)
        if blocked:
            reason = f"Blocked by content filter: matched '{blocked}'"
            post_repo.mark_rejected(post.shortcode, reason)
            logger.info("Rejected post %s — %s", post.shortcode, reason)
            return False

        caption = build_repost_caption(username, post.caption)
        post_repo.mark_ready(post.shortcode, caption)
        return True
    except OCRError as exc:
        logger.error("OCR failed for post %s: %s", post.shortcode, exc)
        error_repo.log("ocr", str(exc), username)
        post_repo.mark_error(post.shortcode)
        return False


def prepare_pending_posts(
    post_repo: PostRepository,
    account_repo: AccountRepository,
    error_repo: ErrorRepository,
    tesseract_path: str,
    blocked_keywords: list[str],
) -> int:
    """Run prepare_post() on every post still in 'downloaded' status. Returns count prepared."""
    pending = post_repo.list_by_status("downloaded")
    accounts_by_id = {a.id: a for a in account_repo.list_all()}
    prepared = 0
    for post in pending:
        account = accounts_by_id.get(post.account_id)
        if account is None:
            continue
        if prepare_post(
            post, account.username, tesseract_path, post_repo, error_repo, blocked_keywords
        ):
            prepared += 1
    return prepared


def mark_reposted(shortcode: str, post_repo: PostRepository) -> None:
    """Mark a 'ready' post as 'processed' once it has actually been reposted."""
    post_repo.mark_processed(shortcode)
