"""Notifications via Knock (the single external API key).

Knock is a workflow engine: we trigger workflows (verify email, import done,
escalation, review queue) with recipients and data. When KNOCK_API_KEY is
absent (sandbox), notifications degrade to structured logs — the product
still works, only delivery is skipped. Email verification tokens are real
in both modes; dev mode returns the verification link so the flow is
testable without an email provider.
"""

from __future__ import annotations

import httpx
import structlog

from ..config import Settings

log = structlog.get_logger("raqib.notify")

KNOCK_API = "https://api.knock.app/v1"


class Notifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    @property
    def configured(self) -> bool:
        return bool(self.settings.knock_api_key)

    def _client_or(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def trigger(
        self,
        workflow_key: str,
        *,
        recipient_id: str,
        data: dict | None = None,
        tenant: str | None = None,
        actor_id: str | None = None,
    ) -> bool:
        if not self.configured:
            log.info(
                "notify.skipped",
                workflow=workflow_key,
                recipient=recipient_id,
                reason="knock_not_configured",
            )
            return False
        body: dict = {
            "recipients": [{"id": recipient_id}],
            "data": data or {},
        }
        if tenant:
            body["tenant"] = tenant
        if actor_id:
            body["actor"] = {"id": actor_id}
        try:
            resp = await self._client_or().post(
                f"{KNOCK_API}/workflows/{workflow_key}/trigger",
                headers={"Authorization": f"Bearer {self.settings.knock_api_key}"},
                json=body,
            )
            if resp.status_code >= 400:
                log.warning("notify.error", workflow=workflow_key, status=resp.status_code, body=resp.text[:500])
                return False
            return True
        except httpx.HTTPError as exc:
            log.warning("notify.error", workflow=workflow_key, error=str(exc))
            return False

    async def send_verification(self, *, user_id: str, email: str, verify_url: str) -> None:
        await self.trigger(
            self.settings.knock_workflow_verify,
            recipient_id=user_id,
            data={"verify_url": verify_url, "email": email},
        )

    async def notify_import_complete(self, *, org_id: str, user_id: str, page_name: str, imported: int, failed: int) -> None:
        await self.trigger(
            self.settings.knock_workflow_import,
            recipient_id=user_id,
            tenant=org_id,
            data={"page_name": page_name, "imported": imported, "failed": failed},
        )

    async def notify_escalation(self, *, org_id: str, user_id: str, conversation_id: str, reason: str) -> None:
        await self.trigger(
            self.settings.knock_workflow_escalation,
            recipient_id=user_id,
            tenant=org_id,
            data={"conversation_id": conversation_id, "reason": reason},
        )

    async def notify_review_queue(self, *, org_id: str, user_id: str, count: int) -> None:
        await self.trigger(
            self.settings.knock_workflow_review,
            recipient_id=user_id,
            tenant=org_id,
            data={"pending": count},
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


_notifier: Notifier | None = None


def get_notifier(settings: Settings) -> Notifier:
    global _notifier
    if _notifier is None:
        _notifier = Notifier(settings)
    return _notifier
