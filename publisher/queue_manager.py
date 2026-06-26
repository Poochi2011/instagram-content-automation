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
from utils.exceptions import OCRError
from utils.logger import get_logger

logger = get_logger(__name__)


def prepare_post(
    post: Post,
    username: str,
    tesseract_path: str,
    post_repo: PostRepository,
    error_repo: ErrorRepository,
) -> bool:
    """Run OCR + build caption for a single downloaded post. Returns True on success."""
    if not post.image_path:
        return False

    try:
        text = extract_text(Path(post.image_path), tesseract_path)
        post_repo.mark_ocr_done(post.shortcode, text)

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
) -> int:
    """Run prepare_post() on every post still in 'downloaded' status. Returns count prepared."""
    pending = post_repo.list_by_status("downloaded")
    prepared = 0
    for post in pending:
        account = next(
            (a for a in account_repo.list_all() if a.id == post.account_id), None
        )
        if account is None:
            continue
        if prepare_post(post, account.username, tesseract_path, post_repo, error_repo):
            prepared += 1
    return prepared


def mark_reposted(shortcode: str, post_repo: PostRepository) -> None:
    """Mark a 'ready' post as 'processed' once it has actually been reposted."""
    post_repo.mark_processed(shortcode)
