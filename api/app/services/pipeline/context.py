"""StageContext — everything a pipeline stage needs, plus progress/cancel helpers."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from ... import models
from ...config import Settings
from ..ai.manager import ProviderManager
from ..meta_client import MetaClient
from ..notify import Notifier
from ..rate_limit import RateLimiter
from ..sse import EventBroker
from ..storage import StorageProvider

log = structlog.get_logger("raqib.pipeline")


@dataclass
class StageResult:
    done: int = 0
    total: int = 0
    message: str = ""
    checkpoint: dict[str, Any] = field(default_factory=dict)
    partial: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass
class StageContext:
    session: AsyncSession
    job: models.Job
    settings: Settings
    meta: MetaClient
    storage: StorageProvider
    providers: ProviderManager
    notifier: Notifier
    limiter: RateLimiter
    broker: EventBroker

    def checkpoint(self) -> dict[str, Any]:
        cp = self.job.checkpoint or {}
        return cp if isinstance(cp, dict) else {}

    async def set_checkpoint(self, **updates: Any) -> None:
        cp = dict(self.checkpoint())
        cp.update(updates)
        self.job.checkpoint = cp

    async def progress(self, done: int, total: int, message: str = "") -> None:
        self.job.progress_done = done
        self.job.progress_total = total
        self.job.progress_message = message
        self.job.updated_at = models.utcnow()
        await self.session.commit()
        await self._publish("job.progress", {
            "job_id": self.job.id,
            "status": self.job.status,
            "stage": self.job.stage,
            "done": done,
            "total": total,
            "message": message,
        })

    async def note(self, text: str) -> None:
        notes = list(self.job.checkpoint.get("notes") or [])
        notes.append(text)
        await self.set_checkpoint(notes=notes[-20:])

    async def check_cancelled(self) -> bool:
        """Returns True when the job should stop (cancelled or pause requested)."""
        if self.job.status == models.JOB_STATES[4]:  # CANCEL_REQUESTED
            self.job.status = "CANCELLED"
            self.job.completed_at = models.utcnow()
            await self.session.commit()
            await self._publish("job.state", {"job_id": self.job.id, "status": "CANCELLED"})
            return True
        if self.job.status == "PAUSED":
            await self._publish("job.state", {"job_id": self.job.id, "status": "PAUSED"})
            return True
        return False

    async def _publish(self, event: str, payload: dict[str, Any]) -> None:
        try:
            await self.broker.publish(self.job.org_id, event, payload)
        except Exception:  # pragma: no cover - broker must never break the pipeline
            log.warning("pipeline.publish_failed", event=event)

    def sleep_with_backoff(self, attempt: int, base: float = 2.0) -> float:
        delay = base * (2 ** attempt) + random.uniform(0, 0.5 * base)
        return delay
