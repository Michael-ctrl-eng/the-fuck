"""Meta Messenger webhooks — verification, signature validation, events.

Production setup (docs/SETUP.md): register a webhook in the Meta app
console pointing at /api/meta/webhooks with the verify token, and the
platform delivers real-time page events. Events are normalized with
idempotency keys and ingested through the same pipeline (they become
part of the next sync / real-time upsert).
"""

from __future__ import annotations

import hashlib
import hmac

from ..config import Settings, get_settings
from ..security import constant_time_eq


def verify_hub_challenge(
    hub_mode: str, hub_verify_token: str, hub_challenge: str
) -> str:
    s = get_settings()
    if hub_mode != "subscribe":
        raise ValueError("invalid hub.mode")
    if not s.meta_webhook_verify_token or not constant_time_eq(
        hub_verify_token, s.meta_webhook_verify_token
    ):
        raise ValueError("verification token mismatch")
    return hub_challenge


def verify_signature(payload: bytes, signature_header: str | None) -> bool:
    """Validate X-Hub-Signature-256 with the Meta app secret."""
    s = get_settings()
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        s.meta_app_secret.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()
    return constant_time_eq(signature_header, expected)


def normalize_events(payload: dict) -> list[dict]:
    """Normalize a Messenger webhook payload into individual events.

    Each event carries an idempotency key (page id + message id) so the
    ingest path can dedupe against already-stored messages.
    """
    events: list[dict] = []
    for entry in payload.get("entry", []):
        page_id = str(entry.get("id", ""))
        for messaging in entry.get("messaging", []):
            message = messaging.get("message") or {}
            event_id = message.get("mid") or str(messaging.get("timestamp", ""))
            events.append(
                {
                    "page_id": page_id,
                    "event_id": event_id,
                    "idempotency_key": f"msg:{page_id}:{event_id}",
                    "messaging": messaging,
                    "received_at": messaging.get("timestamp"),
                }
            )
    return events


def webhook_configured(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return bool(s.meta_webhook_verify_token)
