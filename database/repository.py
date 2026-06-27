"""Repository layer: all SQL lives here, nowhere else in the app."""

from __future__ import annotations

from typing import Optional

from database.db import Database
from database.models import Account, ErrorLog, Post, PostMedia


class AccountRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def upsert(self, username: str) -> Account:
        """Insert the account if new; otherwise leave existing row untouched."""
        with self._db.cursor() as cur:
            cur.execute(
                "INSERT INTO accounts (username) VALUES (?) "
                "ON CONFLICT(username) DO NOTHING",
                (username,),
            )
        return self.get_by_username(username)  # type: ignore[return-value]

    def get_by_username(self, username: str) -> Optional[Account]:
        row = self._db.connection.execute(
            "SELECT * FROM accounts WHERE username = ?", (username,)
        ).fetchone()
        return Account.from_row(row) if row else None

    def list_all(self, active_only: bool = False) -> list[Account]:
        query = "SELECT * FROM accounts"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY username"
        rows = self._db.connection.execute(query).fetchall()
        return [Account.from_row(r) for r in rows]

    def set_active(self, username: str, is_active: bool) -> None:
        with self._db.cursor() as cur:
            cur.execute(
                "UPDATE accounts SET is_active = ? WHERE username = ?",
                (int(is_active), username),
            )

    def remove(self, username: str) -> None:
        with self._db.cursor() as cur:
            cur.execute("DELETE FROM accounts WHERE username = ?", (username,))

    def mark_checked(self, username: str, last_post_shortcode: Optional[str] = None) -> None:
        with self._db.cursor() as cur:
            if last_post_shortcode:
                cur.execute(
                    "UPDATE accounts SET last_checked_at = datetime('now'), "
                    "last_post_shortcode = ? WHERE username = ?",
                    (last_post_shortcode, username),
                )
            else:
                cur.execute(
                    "UPDATE accounts SET last_checked_at = datetime('now') WHERE username = ?",
                    (username,),
                )


class PostRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def exists(self, shortcode: str) -> bool:
        row = self._db.connection.execute(
            "SELECT 1 FROM posts WHERE shortcode = ?", (shortcode,)
        ).fetchone()
        return row is not None

    def create(
        self,
        account_id: int,
        shortcode: str,
        post_url: str,
        caption: Optional[str],
        posted_at: Optional[str],
        is_carousel: bool = False,
    ) -> Post:
        with self._db.cursor() as cur:
            cur.execute(
                "INSERT INTO posts (account_id, shortcode, post_url, caption, posted_at, is_carousel) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (account_id, shortcode, post_url, caption, posted_at, int(is_carousel)),
            )
        return self.get_by_shortcode(shortcode)  # type: ignore[return-value]

    def get_by_shortcode(self, shortcode: str) -> Optional[Post]:
        row = self._db.connection.execute(
            "SELECT * FROM posts WHERE shortcode = ?", (shortcode,)
        ).fetchone()
        return Post.from_row(row) if row else None

    def get_by_id(self, post_id: int) -> Optional[Post]:
        row = self._db.connection.execute(
            "SELECT * FROM posts WHERE id = ?", (post_id,)
        ).fetchone()
        return Post.from_row(row) if row else None

    def list_by_status(self, status: Optional[str] = None) -> list[Post]:
        if status:
            rows = self._db.connection.execute(
                "SELECT * FROM posts WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = self._db.connection.execute(
                "SELECT * FROM posts ORDER BY created_at DESC"
            ).fetchall()
        return [Post.from_row(r) for r in rows]

    def mark_downloaded(self, shortcode: str, image_path: str) -> None:
        with self._db.cursor() as cur:
            cur.execute(
                "UPDATE posts SET status = 'downloaded', image_path = ?, "
                "downloaded_at = datetime('now') WHERE shortcode = ?",
                (image_path, shortcode),
            )

    def mark_ocr_done(self, shortcode: str, ocr_text: str) -> None:
        with self._db.cursor() as cur:
            cur.execute(
                "UPDATE posts SET status = 'ocr_done', ocr_text = ? WHERE shortcode = ?",
                (ocr_text, shortcode),
            )

    def mark_ready(self, shortcode: str, repost_caption: str) -> None:
        with self._db.cursor() as cur:
            cur.execute(
                "UPDATE posts SET status = 'ready', repost_caption = ? WHERE shortcode = ?",
                (repost_caption, shortcode),
            )

    def mark_processed(self, shortcode: str) -> None:
        with self._db.cursor() as cur:
            cur.execute(
                "UPDATE posts SET status = 'processed', processed_at = datetime('now') "
                "WHERE shortcode = ?",
                (shortcode,),
            )

    def mark_error(self, shortcode: str) -> None:
        with self._db.cursor() as cur:
            cur.execute("UPDATE posts SET status = 'error' WHERE shortcode = ?", (shortcode,))

    def list_publishable(self, now_iso: str) -> list[Post]:
        """'ready' posts due for a publish attempt now, oldest source post first."""
        rows = self._db.connection.execute(
            "SELECT * FROM posts WHERE status = 'ready' "
            "AND (next_publish_attempt_at IS NULL OR next_publish_attempt_at <= ?) "
            "ORDER BY created_at ASC",
            (now_iso,),
        ).fetchall()
        return [Post.from_row(r) for r in rows]

    def mark_published(self, shortcode: str, ig_media_id: str) -> None:
        with self._db.cursor() as cur:
            cur.execute(
                "UPDATE posts SET status = 'processed', published_at = datetime('now'), "
                "ig_media_id = ? WHERE shortcode = ?",
                (ig_media_id, shortcode),
            )

    def record_publish_failure(self, shortcode: str, error_message: str, next_attempt_at: str) -> None:
        """Transient failure: bump the attempt count and schedule a retry. Stays 'ready'."""
        with self._db.cursor() as cur:
            cur.execute(
                "UPDATE posts SET publish_attempts = publish_attempts + 1, "
                "last_publish_error = ?, next_publish_attempt_at = ? WHERE shortcode = ?",
                (error_message, next_attempt_at, shortcode),
            )

    def mark_publish_permanently_failed(self, shortcode: str, error_message: str) -> None:
        """Permanent failure or retries exhausted: stop retrying, surface it as an error."""
        with self._db.cursor() as cur:
            cur.execute(
                "UPDATE posts SET status = 'error', publish_attempts = publish_attempts + 1, "
                "last_publish_error = ? WHERE shortcode = ?",
                (error_message, shortcode),
            )

    def count_published_since(self, since_iso: str) -> int:
        row = self._db.connection.execute(
            "SELECT COUNT(*) AS n FROM posts WHERE published_at >= ?", (since_iso,)
        ).fetchone()
        return row["n"]

    def count_downloaded_since(self, since_iso_date: str) -> int:
        row = self._db.connection.execute(
            "SELECT COUNT(*) AS n FROM posts WHERE downloaded_at >= ?", (since_iso_date,)
        ).fetchone()
        return row["n"]

    def ocr_success_rate(self) -> float:
        row = self._db.connection.execute(
            "SELECT "
            "  SUM(CASE WHEN status != 'downloaded' THEN 1 ELSE 0 END) AS attempted, "
            "  SUM(CASE WHEN ocr_text IS NOT NULL AND ocr_text != '' THEN 1 ELSE 0 END) AS succeeded "
            "FROM posts WHERE status NOT IN ('new', 'downloaded')"
        ).fetchone()
        attempted = row["attempted"] or 0
        succeeded = row["succeeded"] or 0
        return (succeeded / attempted * 100.0) if attempted else 0.0


class PostMediaRepository:
    """Extra slides (position >= 1) for carousel posts. Position 0 lives on posts.image_path."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, post_id: int, position: int, image_path: str, is_video: bool = False) -> None:
        with self._db.cursor() as cur:
            cur.execute(
                "INSERT INTO post_media (post_id, position, image_path, is_video) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(post_id, position) DO NOTHING",
                (post_id, position, image_path, int(is_video)),
            )

    def list_for_post(self, post_id: int) -> list[PostMedia]:
        rows = self._db.connection.execute(
            "SELECT * FROM post_media WHERE post_id = ? ORDER BY position ASC", (post_id,)
        ).fetchall()
        return [PostMedia.from_row(r) for r in rows]


class ErrorRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def log(self, source: str, message: str, account_username: Optional[str] = None) -> None:
        with self._db.cursor() as cur:
            cur.execute(
                "INSERT INTO errors (source, message, account_username) VALUES (?, ?, ?)",
                (source, message, account_username),
            )

    def recent(self, limit: int = 50) -> list[ErrorLog]:
        rows = self._db.connection.execute(
            "SELECT * FROM errors ORDER BY occurred_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [ErrorLog.from_row(r) for r in rows]


class SettingsRepository:
    """Key-value store for small runtime state (e.g. last_scan_at) — not user config."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self, key: str) -> Optional[str]:
        row = self._db.connection.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def set(self, key: str, value: str) -> None:
        with self._db.cursor() as cur:
            cur.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
