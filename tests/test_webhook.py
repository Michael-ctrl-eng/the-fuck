"""Tests for Messenger webhook endpoints."""
import json

import pytest

from app.config import get_settings

settings = get_settings()


@pytest.mark.asyncio
class TestWebhook:

    async def test_webhook_verification_success(self, client):
        resp = await client.get("/api/webhook/messenger", params={
            "hub.mode": "subscribe",
            "hub.verify_token": settings.FB_VERIFY_TOKEN,
            "hub.challenge": "challenge_12345",
        })
        assert resp.status_code == 200
        assert resp.text == "challenge_12345"

    async def test_webhook_verification_wrong_token(self, client):
        resp = await client.get("/api/webhook/messenger", params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "challenge_12345",
        })
        assert resp.status_code == 403

    async def test_webhook_verification_missing_params(self, client):
        resp = await client.get("/api/webhook/messenger")
        assert resp.status_code == 403

    async def test_webhook_receive_message(self, client, test_tenant):
        """Test receiving a Messenger event (debug mode — no signature check)."""
        payload = {
            "object": "page",
            "entry": [
                {
                    "id": test_tenant.fb_page_id,
                    "messaging": [
                        {
                            "sender": {"id": "customer_psid_123"},
                            "recipient": {"id": test_tenant.fb_page_id},
                            "message": {
                                "mid": "mid.123",
                                "text": "Hi, what products do you have?",
                            },
                        }
                    ],
                }
            ],
        }
        resp = await client.post(
            "/api/webhook/messenger",
            json=payload,
        )
        assert resp.status_code == 200
        assert resp.text == "EVENT_RECEIVED"

    async def test_webhook_non_page_event(self, client):
        resp = await client.post(
            "/api/webhook/messenger",
            json={"object": "not_a_page"},
        )
        assert resp.status_code == 404

    async def test_webhook_empty_messaging(self, client, test_tenant):
        payload = {
            "object": "page",
            "entry": [{"id": test_tenant.fb_page_id, "messaging": []}],
        }
        resp = await client.post("/api/webhook/messenger", json=payload)
        assert resp.status_code == 200
