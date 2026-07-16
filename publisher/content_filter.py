"""Screens post text for disallowed adult/explicit content.

A post whose caption (or OCR'd overlay text) matches any blocked keyword is
kept out of the publish queue entirely — it never becomes 'ready', so it can
never be reposted to the destination account. Matching is whole-word and
case-insensitive: `\\bsex\\b` blocks "sex" but not "sussex"/"unisex", so common
place/handle names don't trip the filter by accident.

The keyword list is configurable via config.json (`blocked_keywords`); the
default below is a sensible starting set for a general-audience repost account.
"""

from __future__ import annotations

import re


def find_blocked_keyword(text: str | None, blocked_keywords: list[str]) -> str | None:
    """Return the first blocked keyword found in `text`, or None if it's clean."""
    if not text:
        return None
    lowered = text.lower()
    for keyword in blocked_keywords:
        keyword = keyword.strip().lower()
        if not keyword:
            continue
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            return keyword
    return None


def screen_texts(texts: list[str | None], blocked_keywords: list[str]) -> str | None:
    """Return the first blocked keyword found across several text fields, or None."""
    for text in texts:
        match = find_blocked_keyword(text, blocked_keywords)
        if match:
            return match
    return None
