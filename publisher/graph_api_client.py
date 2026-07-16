"""Thin wrapper around the Instagram Graph API's content-publishing endpoints.

Flow for a single image: create a media container (image_url + caption) ->
poll until it's FINISHED -> publish it.

Flow for a carousel: create one child container per image (is_carousel_item=true,
no caption) -> poll each -> create a parent container (media_type=CAROUSEL,
children=[...], caption) -> poll it -> publish it.

Every container must reference a *publicly reachable* image URL — Graph API
fetches the bytes itself, it does not accept a local file or upload stream for
images. That's why the rest of the app needs media_public_base_url configured.
"""

from __future__ import annotations

import time
from typing import Optional

import requests

from utils.exceptions import PermanentPublishError, TransientPublishError
from utils.logger import get_logger

logger = get_logger(__name__)

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Graph API error codes that mean "try again later", not "this will never work".
_RETRYABLE_ERROR_CODES = {1, 2, 4, 17, 32, 613}
_RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}

_POLL_INTERVAL_SECONDS = 5
_POLL_MAX_ATTEMPTS = 12  # ~60s; images finish almost immediately, this is generous headroom


class GraphAPIClient:
    def __init__(self, access_token: str, business_account_id: str, timeout: int = 30) -> None:
        self._access_token = access_token
        self._business_account_id = business_account_id
        self._timeout = timeout

    def publish(self, image_urls: list[str], caption: str) -> str:
        """Publish one or more public image URLs as a single post. Returns the published media id."""
        if not image_urls:
            raise PermanentPublishError("No image URLs to publish.")
        if len(image_urls) == 1:
            return self._publish_single_image(image_urls[0], caption)
        return self._publish_carousel(image_urls, caption)

    def _publish_single_image(self, image_url: str, caption: str) -> str:
        container_id = self._create_container({"image_url": image_url, "caption": caption})
        self._poll_until_finished(container_id)
        return self._publish_container(container_id)

    def _publish_carousel(self, image_urls: list[str], caption: str) -> str:
        if len(image_urls) > 10:
            raise PermanentPublishError(
                f"Carousel has {len(image_urls)} image slides; Instagram allows at most 10."
            )
        child_ids = []
        for image_url in image_urls:
            child_id = self._create_container({"image_url": image_url, "is_carousel_item": "true"})
            self._poll_until_finished(child_id)
            child_ids.append(child_id)

        parent_id = self._create_container(
            {"media_type": "CAROUSEL", "caption": caption, "children": ",".join(child_ids)}
        )
        self._poll_until_finished(parent_id)
        return self._publish_container(parent_id)

    # ---- Comment management (auto-reply pipeline) ----

    def get_account_username(self) -> str:
        """The destination account's own IG username — used to skip self-comments."""
        data = self._request(
            "GET", str(self._business_account_id), {"fields": "username", "access_token": self._access_token}
        )
        username = data.get("username")
        if not username:
            raise PermanentPublishError(f"Graph API did not return the account username: {data}")
        return username

    def get_recent_media(self, limit: int = 20) -> list[dict]:
        """Most recent posts on the destination account, newest first.

        Each dict: id, caption (may be missing), timestamp, comments_count.
        """
        data = self._request(
            "GET",
            f"{self._business_account_id}/media",
            {
                "fields": "id,caption,timestamp,comments_count",
                "limit": min(limit, 50),
                "access_token": self._access_token,
            },
        )
        return data.get("data", [])

    def get_comments(self, media_id: str, max_pages: int = 4) -> list[dict]:
        """Top-level comments on one post (replies to comments are not included
        as separate items — they arrive nested under 'replies', which is exactly
        what we need to detect comments that were already answered manually).

        Each dict: id, text, timestamp, username, and optionally
        replies: {data: [{id, username, text}, ...]}.
        """
        comments: list[dict] = []
        params = {
            "fields": "id,text,timestamp,username,replies{id,username,text}",
            "limit": 50,
            "access_token": self._access_token,
        }
        path = f"{media_id}/comments"
        for _ in range(max_pages):
            data = self._request("GET", path, params)
            comments.extend(data.get("data", []))
            after = data.get("paging", {}).get("cursors", {}).get("after")
            if not after or not data.get("paging", {}).get("next"):
                break
            params = {**params, "after": after}
        return comments

    def reply_to_comment(self, comment_id: str, message: str) -> str:
        """Post a threaded reply under a comment. Returns the new reply's comment id."""
        data = self._request(
            "POST",
            f"{comment_id}/replies",
            {"message": message, "access_token": self._access_token},
        )
        reply_id = data.get("id")
        if not reply_id:
            raise PermanentPublishError(f"Graph API did not return a reply comment id: {data}")
        return reply_id

    # ---- Content publishing internals ----

    def _create_container(self, params: dict) -> str:
        data = self._request("POST", f"{self._business_account_id}/media", {**params, "access_token": self._access_token})
        container_id = data.get("id")
        if not container_id:
            raise PermanentPublishError(f"Graph API did not return a container id: {data}")
        return container_id

    def _publish_container(self, container_id: str) -> str:
        data = self._request(
            "POST",
            f"{self._business_account_id}/media_publish",
            {"creation_id": container_id, "access_token": self._access_token},
        )
        media_id = data.get("id")
        if not media_id:
            raise PermanentPublishError(f"Graph API did not return a published media id: {data}")
        return media_id

    def _poll_until_finished(self, container_id: str) -> None:
        for attempt in range(_POLL_MAX_ATTEMPTS):
            data = self._request(
                "GET", str(container_id), {"fields": "status_code", "access_token": self._access_token}
            )
            status = data.get("status_code")
            if status == "FINISHED":
                return
            if status == "ERROR":
                raise PermanentPublishError(f"Container {container_id} failed processing: {data}")
            if status == "EXPIRED":
                raise PermanentPublishError(f"Container {container_id} expired before it could be published.")
            time.sleep(_POLL_INTERVAL_SECONDS)
        raise TransientPublishError(
            f"Container {container_id} still processing after {_POLL_MAX_ATTEMPTS * _POLL_INTERVAL_SECONDS}s; will retry next cycle."
        )

    def _request(self, method: str, path: str, params: dict) -> dict:
        url = f"{GRAPH_API_BASE}/{path}"
        try:
            response = requests.request(method, url, params=params, timeout=self._timeout)
        except requests.exceptions.RequestException as exc:
            raise TransientPublishError(f"Network error calling Graph API ({path}): {exc}") from exc

        if response.status_code in _RETRYABLE_HTTP_STATUSES:
            raise TransientPublishError(f"Graph API returned HTTP {response.status_code} for {path}: {response.text}")

        try:
            data = response.json()
        except ValueError as exc:
            raise TransientPublishError(f"Graph API returned non-JSON response for {path}: {response.text}") from exc

        if "error" in data:
            self._raise_for_error(path, data["error"])

        if not response.ok:
            raise PermanentPublishError(f"Graph API request to {path} failed (HTTP {response.status_code}): {data}")

        return data

    @staticmethod
    def _raise_for_error(path: str, error: dict) -> None:
        code = error.get("code")
        message = error.get("message", "unknown error")
        detail = f"Graph API error on {path}: [{code}] {message} (subcode={error.get('error_subcode')})"
        if code in _RETRYABLE_ERROR_CODES:
            raise TransientPublishError(detail)
        raise PermanentPublishError(detail)
