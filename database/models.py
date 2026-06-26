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
    status: str
    downloaded_at: Optional[str]
    processed_at: Optional[str]
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
            status=row["status"],
            downloaded_at=row["downloaded_at"],
            processed_at=row["processed_at"],
            created_at=row["created_at"],
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
