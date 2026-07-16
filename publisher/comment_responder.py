"""Fetches comments on the destination account's posts and answers them.

One call to respond_to_comments() is one cycle, mirroring auto_publisher:

  1. Pull recent posts from the Graph API, then their top-level comments.
  2. Store never-seen comments in SQLite (the comments table is the only
     memory — a fresh GitHub Actions run resumes exactly where the last
     one stopped, and UNIQUE(ig_comment_id) makes double-replying impossible).
  3. Classify + draft replies for everything pending. Crisis language, real
     questions and accusations are flagged for a human; spam/hostility is
     skipped; the rest get a short templated reply.
  4. Post replies — unless reply_dry_run is on (the default), in which case
     drafts are stored for review on the GUI Comments page and nothing is
     sent. Flip the setting off to go live; already-drafted rows get posted.

Caps: max_replies_per_cycle bounds each run, max_replies_per_day bounds the
UTC day (counted from replied_at timestamps in SQLite). Combined with the
hourly Actions schedule this drip-feeds replies instead of bursting 50 at
once when a post takes off — same trick the publisher uses.
"""

from __future__ import annotations

import random
import time
from datetime import datetime, timedelta, timezone

from config.settings import Settings
from database.repository import CommentRepository, ErrorRepository
from publisher import reply_drafter
from publisher.graph_api_client import GraphAPIClient
from utils.exceptions import PermanentPublishError, PublisherError, TransientPublishError
from utils.logger import get_logger

logger = get_logger(__name__)

# Small human-ish pause between consecutive live replies.
_REPLY_PAUSE_RANGE_SECONDS = (4.0, 12.0)


def _empty_summary(dry_run: bool) -> dict:
    return {
        "fetched_new": 0, "replied": 0, "drafted": 0, "flagged": 0,
        "skipped": 0, "failed": 0, "dry_run": dry_run,
    }


def _is_too_old(commented_at: str | None, max_age_days: int) -> bool:
    if not commented_at:
        return False
    try:
        ts = datetime.strptime(commented_at, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return False
    return datetime.now(timezone.utc) - ts > timedelta(days=max_age_days)


def _fetch_new_comments(
    client: GraphAPIClient,
    own_username: str,
    settings: Settings,
    comment_repo: CommentRepository,
    error_repo: ErrorRepository,
) -> int:
    """Sync recent posts' comments into SQLite. Returns how many were new."""
    fetched_new = 0
    for media in client.get_recent_media(settings.reply_media_limit):
        if not media.get("comments_count"):
            continue
        try:
            comments = client.get_comments(media["id"])
        except PublisherError as exc:
            error_repo.log("responder", f"Fetching comments for media {media['id']} failed: {exc}")
            logger.warning("Could not fetch comments for media %s: %s", media["id"], exc)
            continue

        for item in comments:
            username = item.get("username")
            if username and username.lower() == own_username.lower():
                continue  # her own comment on her own post
            is_new = comment_repo.upsert_fetched(
                ig_comment_id=item["id"],
                ig_media_id=media["id"],
                media_caption=media.get("caption"),
                username=username,
                text=item.get("text"),
                commented_at=item.get("timestamp"),
            )
            if not is_new:
                continue
            fetched_new += 1

            replies = (item.get("replies") or {}).get("data", [])
            if any((r.get("username") or "").lower() == own_username.lower() for r in replies):
                # She (or a previous run under another DB) already answered this
                # one manually — never stack an automated reply on top.
                comment_repo.mark_skipped(item["id"], "already_replied")
            elif _is_too_old(item.get("timestamp"), settings.reply_max_comment_age_days):
                comment_repo.mark_skipped(item["id"], "too_old")
    return fetched_new


def respond_to_comments(
    settings: Settings,
    comment_repo: CommentRepository,
    error_repo: ErrorRepository,
) -> dict:
    """Run one fetch+classify+reply cycle. Returns a summary dict for the CLI."""
    dry_run = settings.reply_dry_run
    summary = _empty_summary(dry_run)

    if not settings.auto_reply_enabled:
        logger.info("Auto-reply skipped: disabled in settings.")
        return summary
    if not settings.ig_dest_access_token or not settings.ig_dest_business_account_id:
        logger.info("Auto-reply skipped: destination Graph API credentials are not configured yet.")
        return summary

    client = GraphAPIClient(settings.ig_dest_access_token, settings.ig_dest_business_account_id)

    try:
        own_username = client.get_account_username()
        summary["fetched_new"] = _fetch_new_comments(client, own_username, settings, comment_repo, error_repo)
    except PublisherError as exc:
        # Can't even list posts/own username — nothing sensible to do this cycle.
        error_repo.log("responder", f"Comment fetch failed: {exc}")
        logger.error("Comment fetch failed, skipping this reply cycle: %s", exc)
        summary["failed"] += 1
        return summary

    since_midnight_utc = datetime.utcnow().strftime("%Y-%m-%d 00:00:00")
    replied_today = comment_repo.count_replied_since(since_midnight_utc)
    remaining_today = max(0, settings.max_replies_per_day - replied_today)
    reply_budget = min(settings.max_replies_per_cycle, remaining_today)

    posted = 0
    for comment in comment_repo.list_pending(limit=500):
        classification = comment.classification or reply_drafter.classify(comment.text)
        action = reply_drafter.action_for(classification)

        if action == reply_drafter.ACTION_FLAG:
            comment_repo.mark_flagged(comment.ig_comment_id, classification)
            summary["flagged"] += 1
            continue
        if action == reply_drafter.ACTION_SKIP:
            comment_repo.mark_skipped(comment.ig_comment_id, classification)
            summary["skipped"] += 1
            continue

        reply_text = comment.reply_text or reply_drafter.draft_reply(comment, classification)

        if dry_run or posted >= reply_budget:
            # Store the draft; a live run (or the next cycle's budget) sends it.
            comment_repo.mark_drafted(comment.ig_comment_id, classification, reply_text)
            summary["drafted"] += 1
            continue

        try:
            if posted > 0:
                time.sleep(random.uniform(*_REPLY_PAUSE_RANGE_SECONDS))
            reply_id = client.reply_to_comment(comment.ig_comment_id, reply_text)
            comment_repo.mark_replied(comment.ig_comment_id, reply_id)
            posted += 1
            summary["replied"] += 1
            logger.info("Replied to comment %s on media %s", comment.ig_comment_id, comment.ig_media_id)
        except TransientPublishError as exc:
            # Rate limit / network blip: keep the row pending and stop posting
            # for this cycle — the next hourly run retries with a fresh budget.
            comment_repo.record_reply_error(comment.ig_comment_id, str(exc), permanent=False)
            error_repo.log("responder", str(exc), comment.username)
            logger.warning("Transient reply failure for %s, stopping this cycle: %s", comment.ig_comment_id, exc)
            summary["failed"] += 1
            break
        except PermanentPublishError as exc:
            # e.g. the comment was deleted, or replying is restricted on it.
            comment_repo.record_reply_error(comment.ig_comment_id, str(exc), permanent=True)
            error_repo.log("responder", str(exc), comment.username)
            logger.error("Permanent reply failure for %s: %s", comment.ig_comment_id, exc)
            summary["failed"] += 1

    if remaining_today == 0:
        logger.info("Daily reply cap (%d) already reached; drafting only this cycle.", settings.max_replies_per_day)
    return summary
