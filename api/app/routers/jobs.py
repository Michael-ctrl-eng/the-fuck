from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from .. import models
from ..deps import DbDep, MembershipDep, OrgDep, UserDep, csrf_dep
from ..errors import APIError, NotFoundError, PermissionError
from ..schemas import JobActionResponse, JobListResponse, JobOut
from ..services.jobs import (
    mark_paused,
    reprocess_dead,
    request_cancel,
)
from ..services.jobs.state import mark_resumed
from ..services.sse import broker

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


async def _get_job(db, org_id: str, job_id: str) -> models.Job:
    # Eager-load events: JobOut serializes them synchronously, and async
    # SQLAlchemy forbids lazy loads outside of IO context.
    job = await db.get(
        models.Job, job_id, options=[selectinload(models.Job.events)]
    )
    if job is None or job.org_id != org_id:
        raise NotFoundError("الوظيفة غير موجودة")
    return job


@router.get("", response_model=JobListResponse)
async def list_jobs(db: DbDep, org: OrgDep, membership: MembershipDep, cursor: str | None = None, limit: int = 30):
    limit = max(1, min(limit, 100))
    stmt = select(models.Job).where(models.Job.org_id == org.id)
    if cursor:
        try:
            last_ts, last_id = cursor.split("|", 1)
            last_dt = datetime.fromisoformat(last_ts)
        except (ValueError, AttributeError):
            raise APIError("مؤشر ترقيم غير صالح")
        stmt = stmt.where(
            or_(
                models.Job.created_at < last_dt,
                (models.Job.created_at == last_dt) & (models.Job.id < last_id),
            )
        )
    stmt = stmt.options(selectinload(models.Job.events)).order_by(
        models.Job.created_at.desc(), models.Job.id.desc()
    ).limit(limit + 1)
    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    items = list(rows[:limit])
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = f"{last.created_at.isoformat()}|{last.id}"
    return JobListResponse(items=[JobOut.model_validate(j) for j in items], next_cursor=next_cursor)


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: str, db: DbDep, org: OrgDep, membership: MembershipDep):
    job = await _get_job(db, org.id, job_id)
    return JobOut.model_validate(job)


@router.post("/{job_id}/cancel", response_model=JobActionResponse, dependencies=[csrf_dep])
async def cancel_job(job_id: str, db: DbDep, org: OrgDep, membership: MembershipDep):
    if membership.role not in ("owner", "admin", "moderator"):
        raise PermissionError()
    job = await _get_job(db, org.id, job_id)
    await request_cancel(db, job)
    await broker.publish(org.id, "job.state", {"job_id": job.id, "status": "CANCEL_REQUESTED"})
    return JobActionResponse(job=JobOut.model_validate(job))


@router.post("/{job_id}/pause", response_model=JobActionResponse, dependencies=[csrf_dep])
async def pause_job(job_id: str, db: DbDep, org: OrgDep, membership: MembershipDep):
    if membership.role not in ("owner", "admin", "moderator"):
        raise PermissionError()
    job = await _get_job(db, org.id, job_id)
    await mark_paused(db, job)
    await broker.publish(org.id, "job.state", {"job_id": job.id, "status": "PAUSED"})
    return JobActionResponse(job=JobOut.model_validate(job))


@router.post("/{job_id}/resume", response_model=JobActionResponse, dependencies=[csrf_dep])
async def resume_job(job_id: str, db: DbDep, org: OrgDep, membership: MembershipDep):
    if membership.role not in ("owner", "admin", "moderator"):
        raise PermissionError()
    job = await _get_job(db, org.id, job_id)
    await mark_resumed(db, job)
    await broker.publish(org.id, "job.state", {"job_id": job.id, "status": "PENDING"})
    return JobActionResponse(job=JobOut.model_validate(job))


@router.post("/{job_id}/retry", response_model=JobActionResponse, dependencies=[csrf_dep])
async def retry_job(job_id: str, db: DbDep, org: OrgDep, membership: MembershipDep):
    if membership.role not in ("owner", "admin", "moderator"):
        raise PermissionError()
    job = await _get_job(db, org.id, job_id)
    await reprocess_dead(db, job)
    from ..routers.pages import _enqueue

    _enqueue(job.id)
    await broker.publish(org.id, "job.state", {"job_id": job.id, "status": "PENDING"})
    return JobActionResponse(job=JobOut.model_validate(job))
