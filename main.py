"""CLI entry point.

Usage:
    python main.py --check     Run one monitoring pass (scrape + download new posts)
    python main.py --backfill  Fetch each account's recent post history in one pass
                                (--backfill-count N, default 10, posts per account)
    python main.py --prepare   Run OCR + caption generation on downloaded posts
    python main.py --publish   Publish due 'ready' posts to the destination IG account
    python main.py --status    Print a dashboard-style summary
    python main.py --gui       Launch the desktop GUI
    python main.py --daemon    Run --check + --prepare + --publish forever on the configured interval

--check/--prepare/--status print a single JSON object to stdout so n8n (or any
caller) can parse it directly. All logging goes to logs/app.log and stderr,
never stdout. --daemon is for unattended 24/7 operation and logs each cycle
instead of printing JSON (there's no caller waiting on stdout).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date

from config.settings import load_settings
from database.db import Database
from database.repository import AccountRepository, ErrorRepository, PostMediaRepository, PostRepository
from publisher.auto_publisher import publish_due_posts
from publisher.queue_manager import prepare_pending_posts
from scraper.monitor import run_backfill, run_check
from utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


def cmd_check() -> dict:
    settings = load_settings()
    db = Database(settings.database_file_path)
    db.initialize_schema()
    try:
        return run_check(settings, db)
    finally:
        db.close()


def cmd_backfill(max_posts_per_account: int) -> dict:
    settings = load_settings()
    db = Database(settings.database_file_path)
    db.initialize_schema()
    try:
        return run_backfill(settings, db, max_posts_per_account)
    finally:
        db.close()


def cmd_prepare() -> dict:
    settings = load_settings()
    db = Database(settings.database_file_path)
    db.initialize_schema()
    try:
        account_repo = AccountRepository(db)
        post_repo = PostRepository(db)
        error_repo = ErrorRepository(db)
        prepared = prepare_pending_posts(post_repo, account_repo, error_repo, settings.tesseract_path)
        return {"prepared": prepared}
    finally:
        db.close()


def cmd_publish() -> dict:
    settings = load_settings()
    db = Database(settings.database_file_path)
    db.initialize_schema()
    try:
        post_repo = PostRepository(db)
        post_media_repo = PostMediaRepository(db)
        error_repo = ErrorRepository(db)
        return publish_due_posts(settings, post_repo, post_media_repo, error_repo)
    finally:
        db.close()


def cmd_status() -> dict:
    settings = load_settings()
    db = Database(settings.database_file_path)
    db.initialize_schema()
    try:
        account_repo = AccountRepository(db)
        post_repo = PostRepository(db)
        error_repo = ErrorRepository(db)

        accounts = account_repo.list_all()
        today = date.today().isoformat()

        return {
            "monitored_accounts": len(accounts),
            "active_accounts": sum(1 for a in accounts if a.is_active),
            "posts_downloaded_today": post_repo.count_downloaded_since(today),
            "ocr_success_rate": round(post_repo.ocr_success_rate(), 1),
            "last_checked_at": max(
                (a.last_checked_at for a in accounts if a.last_checked_at), default=None
            ),
            "queue_pending": len(post_repo.list_by_status("downloaded")),
            "queue_ready": len(post_repo.list_by_status("ready")),
            "recent_errors": [
                {"source": e.source, "message": e.message, "occurred_at": e.occurred_at}
                for e in error_repo.recent(5)
            ],
        }
    finally:
        db.close()


def cmd_gui() -> None:
    from ui.app import run_app

    run_app()


def cmd_daemon() -> None:
    """Run --check, --prepare, then --publish forever on settings.polling_interval_minutes.

    Each cycle is isolated in its own try/except: a failure (network outage,
    rate limit, OCR crash, Graph API error) is logged and counted as an error,
    but never stops the loop. This is what makes 24/7 unattended operation
    possible — restart the process and it just picks back up on the next
    interval, since all retry/queue state lives in SQLite, not memory.
    """
    settings = load_settings()
    interval_seconds = settings.polling_interval_minutes * 60
    logger.info("Daemon started. Polling every %d minute(s).", settings.polling_interval_minutes)

    while True:
        cycle_started = time.monotonic()
        try:
            check_result = cmd_check()
            logger.info(
                "Daemon cycle: checked %d account(s), %d new post(s).",
                check_result["checked"],
                check_result["new_posts"],
            )
            prepare_result = cmd_prepare()
            logger.info("Daemon cycle: prepared %d post(s).", prepare_result["prepared"])
            publish_result = cmd_publish()
            logger.info(
                "Daemon cycle: published %d post(s), %d failed.",
                publish_result["published"],
                publish_result["failed"],
            )
        except Exception:
            logger.exception("Daemon cycle failed; will retry next interval.")

        elapsed = time.monotonic() - cycle_started
        sleep_for = max(0.0, interval_seconds - elapsed)
        time.sleep(sleep_for)


def main() -> int:
    parser = argparse.ArgumentParser(description="Instagram Content Automation")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Scan monitored accounts for new posts")
    group.add_argument(
        "--backfill", action="store_true",
        help="Fetch recent post history per account (not just the latest) to seed the queue in one pass",
    )
    parser.add_argument(
        "--backfill-count", type=int, default=10,
        help="Posts per account to fetch with --backfill (default 10)",
    )
    group.add_argument("--prepare", action="store_true", help="Run OCR + caption prep on the queue")
    group.add_argument(
        "--publish", action="store_true", help="Publish due 'ready' posts to the destination IG account"
    )
    group.add_argument("--status", action="store_true", help="Print a dashboard-style status summary")
    group.add_argument("--gui", action="store_true", help="Launch the desktop GUI")
    group.add_argument(
        "--daemon", action="store_true", help="Run check+prepare+publish forever on the configured interval"
    )
    args = parser.parse_args()

    settings = load_settings()
    setup_logging(settings.log_level)

    if args.gui:
        cmd_gui()
        return 0

    if args.daemon:
        try:
            cmd_daemon()
        except KeyboardInterrupt:
            logger.info("Daemon stopped by user.")
        return 0

    try:
        if args.check:
            output = cmd_check()
        elif args.backfill:
            output = cmd_backfill(args.backfill_count)
        elif args.prepare:
            output = cmd_prepare()
        elif args.publish:
            output = cmd_publish()
        else:
            output = cmd_status()
        print(json.dumps(output, indent=2))
        return 0
    except Exception as exc:  # CLI boundary: never crash without structured output
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
