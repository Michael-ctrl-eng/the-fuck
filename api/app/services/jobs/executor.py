"""InProcessExecutor — runs DB-backed jobs inside the API process.

Used when no Celery/Redis is configured (sandbox, local dev). It polls for
PENDING jobs, reclaims stale RUNNING jobs after a crash, and executes the
pipeline with a small concurrency cap. The exact same pipeline code runs
under Celery in production (see celery_app.py).
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import structlog
from sqlalchemy import select

from ... import models
from ...config import get_settings
from ...db import get_session_factory
from ...metrics import JOBS_ACTIVE
from ..pipeline.orchestrator import run_job

log = structlog.get_logger("raqib.jobs.executor")

POLL_INTERVAL = 2.0
STALE_AFTER_SECONDS = 600
MAX_CONCURRENCY = 3


class InProcessExecutor:
    def __init__(self, max_concurrency: int = MAX_CONCURRENCY) -> None:
        self._sem = asyncio.Semaphore(max_concurrency)
        self._task: asyncio.Task | None = None
        self._stopping = False

    async def start(self) -> None:
        if self._task is None:
            self._stopping = False
            self._task = asyncio.create_task(self._loop(), name="raqib-job-executor")

    async def stop(self) -> None:
        self._stopping = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _reclaim_stale(self, session) -> int:
        """Crash recovery: RUNNING jobs that are orphaned go back to PENDING."""
        cutoff = models.utcnow() - timedelta(seconds=STALE_AFTER_SECONDS)
        rows = await session.execute(
            select(models.Job).where(
                models.Job.status == "RUNNING",
                models.Job.updated_at < cutoff,
            )
        )
        reclaimed = 0
        for job in rows.scalars().all():
            job.status = "PENDING"
            session.add(models.JobEvent(job_id=job.id, event="reclaimed"))
            reclaimed += 1
        if reclaimed:
            await session.commit()
            log.info("jobs.reclaimed_stale", count=reclaimed)
        return reclaimed

    async def _loop(self) -> None:
        factory = get_session_factory()
        log.info("jobs.executor_started")
        while not self._stopping:
            try:
                async with factory() as session:
                    await self._reclaim_stale(session)
                    rows = await session.execute(
                        select(models.Job)
                        .where(models.Job.status.in_(["PENDING", "CANCEL_REQUESTED"]))
                        .order_by(models.Job.created_at)
                        .limit(20)
                    )
                    jobs = list(rows.scalars().all())
                for job in jobs:
                    await self._sem.acquire()
                    asyncio.create_task(self._run(job.id))
            except Exception as exc:  # pragma: no cover - keep the loop alive
                log.error("jobs.executor_loop_error", error=str(exc))
            await asyncio.sleep(POLL_INTERVAL)

    async def _run(self, job_id: str) -> None:
        try:
            await run_job(job_id)
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # pragma: no cover - defensive
            log.error("jobs.run_error", job_id=job_id, error=str(exc))
        finally:
            self._sem.release()


_executor: InProcessExecutor | None = None


def get_executor() -> InProcessExecutor:
    global _executor
    if _executor is None:
        _executor = InProcessExecutor()
    return _executor
