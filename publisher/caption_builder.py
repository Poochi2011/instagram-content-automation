"""Builds the repost caption template from an original post's data."""

from __future__ import annotations


def build_repost_caption(username: str, original_caption: str | None) -> str:
    """Return the "Reposted from @username" caption block used for reposting."""
    caption_body = original_caption.strip() if original_caption else "(no caption)"
    return f"📌 Reposted from @{username}\n\nOriginal Caption:\n{caption_body}"
