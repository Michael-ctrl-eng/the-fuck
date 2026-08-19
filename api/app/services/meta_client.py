"""First-party Meta Graph API client.

Covers: app access token, user long-lived token exchange, /me/accounts,
page conversation & message pagination, sending replies, token debug and
revocation. All calls pass through the shared rate limiter and return
raw API payloads; pipeline stages are responsible for validation.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog

from .. import metrics
from ..config import Settings
from .rate_limit import RateLimiter, get_rate_limiter

log = structlog.get_logger("raqib.meta")

GRAPH = "https://graph.facebook.com"


class MetaAPIError(RuntimeError):
    def __init__(self, message: str, code: int | None = None, subcode: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.subcode = subcode
        self.is_token_error = code in (190, 10) or subcode in (463, 467, 460)


class MetaClient:
    def __init__(self, settings: Settings, limiter: RateLimiter | None = None) -> None:
        self.settings = settings
        self.limiter = limiter or get_rate_limiter(settings)
        self._client: httpx.AsyncClient | None = None

    def _client_or(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.meta_http_timeout, connect=5.0)
            )
        return self._client

    # ------------------------------------------------------------------
    # low-level request
    # ------------------------------------------------------------------
    async def _call(
        self, method: str, path: str, *, params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None, endpoint: str = "",
    ) -> dict[str, Any]:
        limiter_key = f"meta:{path.split('/')[0]}"
        await self.limiter.acquire(limiter_key, limit=180, window_seconds=60)
        started = time.monotonic()
        try:
            resp = await self._client_or().request(
                method, f"{GRAPH}/{self.settings.meta_api_version}{path}",
                params=params, json=body,
            )
        except httpx.HTTPError as exc:
            metrics.META_API_CALLS.labels(endpoint=endpoint or path, status="error").inc()
            raise MetaAPIError(f"تعذر الاتصال بـ Meta: {exc}") from exc
        finally:
            metrics.META_API_LATENCY.labels(endpoint=endpoint or path).observe(time.monotonic() - started)

        status = resp.status_code
        if status >= 400:
            metrics.META_API_CALLS.labels(endpoint=endpoint or path, status=str(status)).inc()
            try:
                err = resp.json().get("error", {})
            except Exception:
                err = {"message": resp.text[:300]}
            raise MetaAPIError(
                err.get("message", "خطأ من Meta Graph API"),
                code=err.get("code"),
                subcode=err.get("error_subcode"),
            )
        metrics.META_API_CALLS.labels(endpoint=endpoint or path, status="ok").inc()
        return resp.json()

    # ------------------------------------------------------------------
    # tokens
    # ------------------------------------------------------------------
    def app_access_token(self) -> str:
        return f"{self.settings.meta_app_id}|{self.settings.meta_app_secret}"

    async def exchange_code(self, code: str, redirect_uri: str) -> str:
        """Exchange an OAuth code for a short-lived user access token."""
        data = await self._call(
            "GET", "/oauth/access_token",
            params={
                "client_id": self.settings.meta_app_id,
                "client_secret": self.settings.meta_app_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
            endpoint="oauth_access_token",
        )
        return data["access_token"]

    async def exchange_long_lived(self, short_token: str) -> dict[str, Any]:
        """Upgrade a short-lived user token to a 60-day token."""
        data = await self._call(
            "GET", "/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": self.settings.meta_app_id,
                "client_secret": self.settings.meta_app_secret,
                "fb_exchange_token": short_token,
            },
            endpoint="oauth_exchange",
        )
        return data

    async def debug_token(self, input_token: str) -> dict[str, Any]:
        data = await self._call(
            "GET", "/debug_token",
            params={"input_token": input_token, "access_token": self.app_access_token()},
            endpoint="debug_token",
        )
        return data.get("data", {})

    async def revoke(self, user_token: str) -> bool:
        await self._call(
            "DELETE", f"/{self.settings.meta_app_id}/permissions",
            params={"access_token": user_token},
            endpoint="revoke",
        )
        return True

    # ------------------------------------------------------------------
    # pages
    # ------------------------------------------------------------------
    async def me_accounts(self, user_token: str) -> list[dict[str, Any]]:
        data = await self._call(
            "GET", "/me/accounts",
            params={"fields": self.settings.meta_page_fields, "access_token": user_token},
            endpoint="me_accounts",
        )
        return data.get("data", [])

    async def page_info(self, page_token: str, page_id: str) -> dict[str, Any]:
        data = await self._call(
            "GET", f"/{page_id}",
            params={"fields": self.settings.meta_page_fields, "access_token": page_token},
            endpoint="page_info",
        )
        return data

    # ------------------------------------------------------------------
    # conversations
    # ------------------------------------------------------------------
    async def list_conversations(
        self, page_token: str, page_id: str, after: str | None = None, limit: int = 50, platform: str = "facebook"
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Fetch one page of conversations.

        Returns (items, next_cursor). Conversation payloads include nested
        messages (max ~20 per conversation) which the pipeline persists to
        raw storage before reconstruction.
        """
        params: dict[str, Any] = {
            "fields": (
                "id,updated_time,participants{id,name},"
                "messages.limit(50){id,created_time,from{id,name},message,"
                "attachments{id,mime_type,name,size,image_data,video_data,file_url},sticker}"
            ),
            "limit": limit,
            "access_token": page_token,
        }
        if platform == "instagram":
            params["platform"] = "instagram"
            
        if after:
            params["after"] = after
        data = await self._call(
            "GET", f"/{page_id}/conversations", params=params, endpoint="conversations"
        )
        items = data.get("data", [])
        paging = data.get("paging", {})
        next_cursor = None
        if paging.get("cursors", {}).get("after") and paging.get("next"):
            next_cursor = paging["cursors"]["after"]
        return items, next_cursor

    async def send_message(self, page_token: str, conversation_id: str, message: str) -> dict[str, Any]:
        data = await self._call(
            "POST", f"/{conversation_id}/messages",
            params={"access_token": page_token},
            body={"message": message},
            endpoint="send_message",
        )
        return data

    async def send_generic_template(self, page_token: str, recipient_id: str, elements: list[dict[str, Any]]) -> dict[str, Any]:
        """Send a 'button view' / Generic Template containing products."""
        payload = {
            "recipient": {"id": recipient_id},
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "generic",
                        "elements": elements
                    }
                }
            }
        }
        data = await self._call(
            "POST", "/me/messages",
            params={"access_token": page_token},
            body=payload,
            endpoint="send_generic_template",
        )
        return data


_client: MetaClient | None = None


def get_meta_client(settings: Settings) -> MetaClient:
    global _client
    if _client is None:
        _client = MetaClient(settings)
    return _client
