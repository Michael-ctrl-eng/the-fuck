"""Job state machine — DB-backed, with explicit transition guards.

States: PENDING, RUNNING, PAUSED, CANCEL_REQUESTED, CANCELLED, COMPLETED,
PARTIAL, FAILED, DEAD.

- cancel: PENDING/RUNNING/PAUSED → CANCEL_REQUESTED → (orchestrator) CANCELLED
- pause:  RUNNING → PAUSED          (checkpoint preserved)
- resume: PAUSED → PENDING          (executor re-picks, resumes from checkpoint)
- retry:  FAILED/DEAD → PENDING     (reprocess, attempts reset)
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ... import models
from ...errors import ConflictError


async def request_cancel(session: AsyncSession, job: models.Job) -> models.Job:
    if job.status not in ("PENDING", "RUNNING", "PAUSED"):
        raise ConflictError(f"لا يمكن إلغاء وظيفة بحالة {job.status}")
    job.status = "CANCEL_REQUESTED"
    session.add(models.JobEvent(job_id=job.id, event="cancel_requested"))
    await session.commit()
    return job


async def mark_paused(session: AsyncSession, job: models.Job) -> models.Job:
    if job.status != "RUNNING":
        raise ConflictError("يمكن إيقاف الوظائف قيد التشغيل فقط")
    job.status = "PAUSED"
    session.add(models.JobEvent(job_id=job.id, event="paused"))
    await session.commit()
    return job


async def mark_resumed(session: AsyncSession, job: models.Job) -> models.Job:
    if job.status != "PAUSED":
        raise ConflictError("يمكن استئناف الوظائف المتوقفة فقط")
    job.status = "PENDING"
    session.add(models.JobEvent(job_id=job.id, event="resumed"))
    await session.commit()
    return job


async def mark_cancelled(session: AsyncSession, job: models.Job) -> models.Job:
    job.status = "CANCELLED"
    job.completed_at = models.utcnow()
    session.add(models.JobEvent(job_id=job.id, event="cancelled"))
    await session.commit()
    return job


async def reprocess_dead(session: AsyncSession, job: models.Job) -> models.Job:
    if job.status not in ("FAILED", "DEAD"):
        raise ConflictError("يمكن إعادة معالجة الوظائف الفاشلة فقط")
    job.status = "PENDING"
    job.dead_letter = False
    job.attempts = 0
    job.error = ""
    job.completed_at = None
    job.started_at = None
    session.add(models.JobEvent(job_id=job.id, event="reprocess"))
    await session.commit()
    return job


def can_cancel(job: models.Job) -> bool:
    return job.status in ("PENDING", "RUNNING", "PAUSED")


def can_pause(job: models.Job) -> bool:
    return job.status == "RUNNING"


def can_resume(job: models.Job) -> bool:
    return job.status == "PAUSED"
