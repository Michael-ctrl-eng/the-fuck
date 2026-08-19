"""Celery application for production job execution.

Worker command (docker-compose):
    celery -A api.app.services.jobs.celery_app worker -l info -Q raqib

Broker: the self-hosted Redis. Task payloads are just job ids; the real
state lives in PostgreSQL (shared with the API), so the same pipeline code
runs here with identical semantics (checkpoints, dead-letter, retries).
"""

from __future__ import annotations

import structlog

from ...config import get_settings

log = structlog.get_logger("raqib.jobs.celery")

_settings = get_settings()


def _make_celery():
    try:
        from celery import Celery
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Celery is not installed — install api/requirements-full.txt "
            "or use the in-process executor (default without REDIS_URL)."
        ) from exc

    broker_url = _settings.redis_url or "redis://127.0.0.1:6379/0"
    app = Celery(
        "raqib",
        broker=broker_url,
        backend=broker_url,
        include=["api.app.services.jobs.tasks"],
    )
    app.conf.update(
        task_default_queue="raqib",
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_time_limit=60 * 60,
        task_soft_time_limit=55 * 60,
        result_expires=60 * 60 * 24,
        broker_connection_retry_on_startup=True,
    )
    return app


celery_app = _make_celery()


@celery_app.task(name="raqib.run_job", bind=True, max_retries=3, default_retry_delay=5)
def run_job_task(self, job_id: str) -> str:
    import asyncio
    import threading

    from ...db import dispose_db, init_db
    from ..pipeline.orchestrator import run_job

    async def _go() -> str:
        await init_db()
        try:
            await run_job(job_id)
            return job_id
        finally:
            # SQLAlchemy async engines are bound to the loop they were
            # created in; each task runs in its own loop via asyncio.run,
            # so the engine MUST be disposed (and globals reset) before
            # the next task creates a fresh one. Serialized by _task_lock
            # so concurrent workers never share loop-bound engines.
            await dispose_db()

    try:
        with _task_lock:
            return asyncio.run(_go())
    except Exception as exc:
        # transient broker/db errors → retry with backoff
        raise self.retry(exc=exc, countdown=5 * (2 ** (self.request.retries or 0)))


# Serializes task execution in this worker process; see _go() above.
_task_lock = threading.Lock()
