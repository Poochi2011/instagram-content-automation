"""Plain dataclasses representing database rows.

These are read-only views of a row — writes go through Repository methods,
never by mutating these objects and expecting persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Account:
    id: Optional[int]
    username: str
    is_active: bool
    last_checked_at: Optional[str]
    last_post_shortcode: Optional[str]
    created_at: str

    @classmethod
    def from_row(cls, row) -> "Account":
        return cls(
            id=row["id"],
            username=row["username"],
            is_active=bool(row["is_active"]),
            last_checked_at=row["last_checked_at"],
            last_post_shortcode=row["last_post_shortcode"],
            created_at=row["created_at"],
        )


@dataclass
class Post:
    id: Optional[int]
    account_id: int
    shortcode: str
    post_url: str
    caption: Optional[str]
    posted_at: Optional[str]
    image_path: Optional[str]
    ocr_text: Optional[str]
    repost_caption: Optional[str]
    is_carousel: bool
    status: str
    downloaded_at: Optional[str]
    processed_at: Optional[str]
    publish_attempts: int
    last_publish_error: Optional[str]
    next_publish_attempt_at: Optional[str]
    published_at: Optional[str]
    ig_media_id: Optional[str]
    created_at: str

    @classmethod
    def from_row(cls, row) -> "Post":
        return cls(
            id=row["id"],
            account_id=row["account_id"],
            shortcode=row["shortcode"],
            post_url=row["post_url"],
            caption=row["caption"],
            posted_at=row["posted_at"],
            image_path=row["image_path"],
            ocr_text=row["ocr_text"],
            repost_caption=row["repost_caption"],
            is_carousel=bool(row["is_carousel"]),
            status=row["status"],
            downloaded_at=row["downloaded_at"],
            processed_at=row["processed_at"],
            publish_attempts=row["publish_attempts"],
            last_publish_error=row["last_publish_error"],
            next_publish_attempt_at=row["next_publish_attempt_at"],
            published_at=row["published_at"],
            ig_media_id=row["ig_media_id"],
            created_at=row["created_at"],
        )


@dataclass
class PostMedia:
    id: Optional[int]
    post_id: int
    position: int
    image_path: str
    is_video: bool

    @classmethod
    def from_row(cls, row) -> "PostMedia":
        return cls(
            id=row["id"],
            post_id=row["post_id"],
            position=row["position"],
            image_path=row["image_path"],
            is_video=bool(row["is_video"]),
        )


@dataclass
class ErrorLog:
    id: Optional[int]
    source: str
    message: str
    account_username: Optional[str]
    occurred_at: str

    @classmethod
    def from_row(cls, row) -> "ErrorLog":
        return cls(
            id=row["id"],
            source=row["source"],
            message=row["message"],
            account_username=row["account_username"],
            occurred_at=row["occurred_at"],
        )
