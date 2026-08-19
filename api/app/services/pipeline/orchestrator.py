"""Pipeline orchestrator.

Runs the stage graph for a job with:
- DB-backed state machine (PENDING→RUNNING→COMPLETED/PARTIAL/FAILED/DEAD,
  PAUSED/CANCEL_REQUESTED honored between and inside stages)
- per-stage checkpoints for crash resumption (stages are idempotent)
- retries with exponential backoff + jitter for transient errors
- honest dead-letter state with manual reprocessing support
- metrics + SSE progress events

Works identically from the in-process executor (sandbox) and from a
Celery worker (production): it opens its own DB session via the shared
session factory.
"""

from __future__ import annotations

import asyncio
import traceback

import httpx
import structlog
from sqlalchemy import select

from ... import models
from ... import metrics
from ...config import get_settings
from ...db import get_session_factory
from .. import get_rate_limiter, get_storage
from ..ai.manager import get_provider_manager
from ..meta_client import MetaAPIError, get_meta_client
from ..notify import get_notifier
from ..sse import broker
from .analyze import stage_analyze
from .context import StageContext, StageResult
from .ingest import stage_fetch, stage_validate
from .outputs import stage_dataset, stage_memory, stage_quality
from .process import stage_normalize_reconstruct

log = structlog.get_logger("raqib.pipeline")

MAX_STAGE_ATTEMPTS = 3

_RETRYABLE = (httpx.HTTPError,)


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, MetaAPIError):
        return not exc.is_token_error
    return isinstance(exc, _RETRYABLE)


async def _stage_notify(ctx: StageContext) -> StageResult:
    imported = ctx.checkpoint().get("fetched_conversations") or ctx.job.result.get("imported") or 0
    ctx.job.result = {
        **(ctx.job.result or {}),
        "imported": imported,
        "stage_summary": ctx.checkpoint().get("notes", [])[-3:],
    }
    await ctx.session.commit()
    await ctx.broker.publish(ctx.job.org_id, "job.completed", {
        "job_id": ctx.job.id, "kind": ctx.job.kind, "imported": imported,
    })
    if ctx.settings.is_dev and not ctx.settings.knock_api_key:
        pass  # dev mode: skip external notification, keep moving
    else:
        try:
            from ..notify import get_notifier

            notifier = get_notifier(ctx.settings)
            members = (
                await ctx.session.execute(
                    select(models.OrgMembership).where(
                        models.OrgMembership.org_id == ctx.job.org_id,
                        models.OrgMembership.role.in_(["owner", "admin", "moderator"]),
                    )
                )
            ).scalars().all()
            for m in members[:3]:
                await notifier.notify_import_complete(
                    org_id=ctx.job.org_id, user_id=m.user_id,
                    page_name=ctx.checkpoint().get("page_name") or "الصفحة",
                    imported=int(imported), failed=0,
                )
        except Exception as exc:  # notifications must never fail the job
            log.warning("pipeline.notify_failed", error=str(exc))
    return StageResult(done=1, total=1, message="تم إرسال الإشعارات")


STAGES_BY_KIND: dict[str, list[tuple[str, object]]] = {
    "page_import": [
        ("fetch", stage_fetch),
        ("validate", stage_validate),
        ("reconstruct", stage_normalize_reconstruct),
        ("analyze", stage_analyze),
        ("quality", stage_quality),
        ("dataset", stage_dataset),
        ("memory", stage_memory),
        ("notify", _stage_notify),
    ],
    "page_resync": [
        ("fetch", stage_fetch),
        ("validate", stage_validate),
        ("reconstruct", stage_normalize_reconstruct),
        ("analyze", stage_analyze),
        ("quality", stage_quality),
        ("dataset", stage_dataset),
        ("memory", stage_memory),
        ("notify", _stage_notify),
    ],
    "dataset_generate": [("dataset", stage_dataset)],
    "memory_reindex": [("memory", stage_memory)],
}


async def run_job(job_id: str) -> None:
    """Execute one job to completion (or a terminal state)."""
    settings = get_settings()
    factory = get_session_factory()
    async with factory() as session:
        job = await session.get(models.Job, job_id)
        if job is None:
            log.warning("pipeline.job_missing", job_id=job_id)
            return

        if job.status not in ("PENDING", "CANCEL_REQUESTED", "PAUSED"):
            return  # already running/terminal — idempotent skip

        if job.status == "PENDING":
            job.status = "RUNNING"
            job.started_at = job.started_at or models.utcnow()
            job.attempts = (job.attempts or 0) + 1
            metrics.JOBS_ACTIVE.inc()
            await session.commit()
            await broker.publish(job.org_id, "job.state", {"job_id": job.id, "status": "RUNNING"})

        ctx = StageContext(
            session=session,
            job=job,
            settings=settings,
            meta=get_meta_client(settings),
            storage=get_storage(settings),
            providers=get_provider_manager(settings),
            notifier=get_notifier(settings),
            limiter=get_rate_limiter(settings),
            broker=broker,
        )

        stages = STAGES_BY_KIND.get(job.kind, [])
        completed_stages = set((job.checkpoint or {}).get("completed_stages") or [])
        partial = False
        failed_stage = ""

        try:
            for stage_name, fn in stages:
                if stage_name in completed_stages:
                    continue
                if job.status == "CANCEL_REQUESTED":
                    await _finish_cancelled(ctx)
                    return
                if job.status == "PAUSED":
                    return  # stays paused; resume() re-enqueues
                job.stage = stage_name
                await session.commit()

                attempt = 0
                while True:
                    attempt += 1
                    try:
                        started = _now()
                        result = await fn(ctx)
                        metrics.PIPELINE_STAGE_DURATION.labels(kind=job.kind, stage=stage_name).observe(_now() - started)
                        if getattr(result, "partial", False):
                            partial = True
                        if getattr(result, "notes", None):
                            await ctx.note(f"{stage_name}: {'; '.join(result.notes[:2])}")
                        completed_stages.add(stage_name)
                        await ctx.set_checkpoint(completed_stages=sorted(completed_stages))
                        await session.commit()
                        break
                    except asyncio.CancelledError:
                        await session.rollback()
                        raise
                    except Exception as exc:
                        await session.rollback()
                        await session.refresh(job)  # rollback expired attributes
                        if isinstance(exc, MetaAPIError) and exc.is_token_error:
                            job.status = "FAILED"
                            job.error = f"انتهت صلاحية رمز ميتا: {exc.message}"
                            job.completed_at = models.utcnow()
                            await _record_error(ctx, stage_name, exc, job)
                            await session.commit()
                            await broker.publish(job.org_id, "job.state", {"job_id": job.id, "status": "FAILED"})
                            return
                        if attempt >= MAX_STAGE_ATTEMPTS:
                            failed_stage = stage_name
                            job.status = "FAILED"
                            job.error = f"فشل المرحلة {stage_name}: {exc}"
                            job.completed_at = models.utcnow()
                            await _record_error(ctx, stage_name, exc, job)
                            await session.commit()
                            await broker.publish(job.org_id, "job.state", {"job_id": job.id, "status": "FAILED"})
                            return
                        delay = ctx.sleep_with_backoff(attempt)
                        log.info("pipeline.retry", job_id=job.id, stage=stage_name, attempt=attempt, error=str(exc))
                        await ctx.note(f"إعادة محاولة {stage_name} ({attempt}): {exc}")
                        await session.commit()
                        await asyncio.sleep(delay)

            # done
            if job.status == "CANCEL_REQUESTED":
                await _finish_cancelled(ctx)
                return
            if job.status == "PAUSED":
                return
            job.status = "PARTIAL" if partial else "COMPLETED"
            job.completed_at = models.utcnow()
            job.stage = "done"
            await session.commit()
            metrics.JOBS_TOTAL.labels(kind=job.kind, status=job.status).inc()
            await broker.publish(job.org_id, "job.state", {"job_id": job.id, "status": job.status})
            log.info("pipeline.done", job_id=job.id, status=job.status, kind=job.kind)
        except asyncio.CancelledError:
            await session.rollback()
            log.info("pipeline.cancelled_task", job_id=job_id)
            raise
        except Exception as exc:  # unrecoverable orchestrator error → dead letter
            await session.rollback()
            try:
                await session.refresh(job)
            except Exception:
                pass
            job.status = "FAILED"
            job.error = str(exc)[:1000]
            job.completed_at = models.utcnow()
            await _record_error(ctx, failed_stage or job.stage, exc, job)
            await session.commit()
            await _maybe_dead_letter(job_id)
            await broker.publish(job.org_id, "job.state", {"job_id": job.id, "status": "FAILED"})
        finally:
            metrics.JOBS_ACTIVE.dec()
            if job.status in models.JOB_TERMINAL:
                await _maybe_dead_letter(job.id)


async def _finish_cancelled(ctx: StageContext) -> None:
    ctx.job.status = "CANCELLED"
    ctx.job.completed_at = models.utcnow()
    await ctx.session.commit()
    metrics.JOBS_TOTAL.labels(kind=ctx.job.kind, status="CANCELLED").inc()
    await ctx.broker.publish(ctx.job.org_id, "job.state", {"job_id": ctx.job.id, "status": "CANCELLED"})


async def _record_error(ctx: StageContext, stage: str, exc: Exception, job: models.Job) -> None:
    ctx.session.add(
        models.ErrorEvent(
            org_id=job.org_id,
            job_id=job.id,
            stage=stage,
            kind=type(exc).__name__,
            message=str(exc)[:2000],
            traceback=traceback.format_exc(limit=8),
        )
    )


async def _maybe_dead_letter(job_id: str) -> None:
    """After repeated failures, move the job to an explicit DEAD state."""
    factory = get_session_factory()
    async with factory() as session:
        job = await session.get(models.Job, job_id)
        if job is None:
            return
        if job.status == "FAILED" and (job.attempts or 0) >= MAX_STAGE_ATTEMPTS + 1:
            job.status = "DEAD"
            job.dead_letter = True
            await session.commit()
            metrics.JOBS_DEAD.inc()
            log.warning("pipeline.dead_letter", job_id=job_id)


def _now() -> float:
    import time

    return time.monotonic()


async def create_job(
    session,
    *,
    org_id: str,
    kind: str,
    params: dict,
    created_by: str | None = None,
    idempotency_key: str | None = None,
) -> models.Job:
    """Create a job with an idempotency key; returns existing job if re-created."""
    key = idempotency_key or f"{kind}:{org_id}:{params.get('page_connection_id', '')}:{int(_now())}"
    existing = (
        await session.execute(
            select(models.Job).where(
                models.Job.org_id == org_id,
                models.Job.idempotency_key == key,
                models.Job.status.in_(["PENDING", "RUNNING", "PAUSED", "CANCEL_REQUESTED"]),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    job = models.Job(
        org_id=org_id,
        kind=kind,
        status="PENDING",
        params=params,
        created_by=created_by,
        idempotency_key=key,
    )
    session.add(job)
    await session.flush()
    metrics.JOBS_TOTAL.labels(kind=kind, status="PENDING").inc()
    return job
