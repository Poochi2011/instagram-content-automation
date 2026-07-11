"""Builds per-session DataImpulse proxy URLs so different account groups (and
retries) get genuinely different residential IPs instead of one identity
absorbing an entire run's traffic.

Background: reusing one sticky identity (same proxy URL) for a full day of
testing plus ~10 hours of hourly CI runs led to every account hitting a login
wall or timeout, both in CI and in local re-tests -- see CONTEXT.md
(2026-07-11). DataImpulse's `sessid` parameter lets a specific session id be
pinned to its own IP for ~30 min, independent of any other session id, on the
rotating port (823) -- see docs.dataimpulse.com/proxies/parameters/session-id.
"""

from __future__ import annotations

from datetime import date
from urllib.parse import urlparse


def with_session_id(base_proxy_url: str, session_id: str) -> str:
    """Insert a DataImpulse sessid into a proxy URL's username.

    base_proxy_url is expected as http://login__cr.xx:password@host:823 (the
    rotating port -- sessid controls stickiness instead of the 10000-20000
    sticky port range). Returns the URL unchanged if it doesn't look like a
    DataImpulse-style proxy URL (e.g. blank, or missing credentials).
    """
    if not base_proxy_url:
        return base_proxy_url
    parsed = urlparse(base_proxy_url)
    if not parsed.username or not parsed.hostname:
        return base_proxy_url
    new_username = f"{parsed.username};sessid.{session_id}"
    netloc = f"{new_username}:{parsed.password}@{parsed.hostname}:{parsed.port}"
    return f"{parsed.scheme}://{netloc}"


def daily_group_session_id(group_index: int, retry: int = 0) -> str:
    """A session id stable for one calendar day + account group, so a run's
    requests to the same handful of accounts look like one recurring visitor
    across a day (not a brand-new identity every single request -- itself a
    bot signal) but automatically rotates to a fresh identity the next day,
    and immediately on retry after a failure.
    """
    today = date.today().isoformat()
    suffix = f"-r{retry}" if retry else ""
    return f"{today}-g{group_index}{suffix}"


def chunk(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]
