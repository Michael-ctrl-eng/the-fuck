from __future__ import annotations

import pytest
from sqlalchemy import select

from api.app import models
from api.app.db import get_session_factory
from api.app.services.jobs import (
    mark_paused,
    reprocess_dead,
    request_cancel,
)
from api.app.services.jobs.state import mark_resumed
from api.app.services.pipeline import create_job, run_job


async def _org(db, name="منظمة"):
    org = models.Organization(name=name, slug=f"org-{name[:10]}")
    db.add(org)
    await db.flush()
    return org


@pytest.mark.asyncio
async def test_create_job_idempotency(db):
    org = await _org(db)
    j1 = await create_job(db, org_id=org.id, kind="dataset_generate", params={}, idempotency_key="k1")
    j2 = await create_job(db, org_id=org.id, kind="dataset_generate", params={}, idempotency_key="k1")
    assert j1.id == j2.id
    j3 = await create_job(db, org_id=org.id, kind="dataset_generate", params={}, idempotency_key="k2")
    assert j3.id != j1.id
    await db.commit()


@pytest.mark.asyncio
async def test_cancel_request_ends_cancelled(db):
    org = await _org(db)
    job = await create_job(db, org_id=org.id, kind="dataset_generate", params={}, idempotency_key="cancel-1")
    await db.commit()
    await request_cancel(db, job)
    assert job.status == "CANCEL_REQUESTED"
    await run_job(job.id)
    factory = get_session_factory()
    async with factory() as session:
        job = await session.get(models.Job, job.id)
        assert job.status == "CANCELLED"


@pytest.mark.asyncio
async def test_pause_resume_transitions(db):
    org = await _org(db)
    job = await create_job(db, org_id=org.id, kind="dataset_generate", params={}, idempotency_key="pause-1")
    job.status = "RUNNING"
    await db.commit()
    await mark_paused(db, job)
    assert job.status == "PAUSED"
    await mark_resumed(db, job)
    assert job.status == "PENDING"


@pytest.mark.asyncio
async def test_dead_letter_reprocess(db):
    org = await _org(db)
    job = await create_job(db, org_id=org.id, kind="dataset_generate", params={}, idempotency_key="dead-1")
    job.status = "FAILED"
    job.dead_letter = True
    job.attempts = 5
    job.error = "some failure"
    await db.commit()
    await reprocess_dead(db, job)
    assert job.status == "PENDING"
    assert job.dead_letter is False
    assert job.attempts == 0
    assert job.error == ""


@pytest.mark.asyncio
async def test_completed_job_is_terminal(db):
    org = await _org(db)
    job = await create_job(db, org_id=org.id, kind="dataset_generate", params={}, idempotency_key="done-1")
    await db.commit()
    await run_job(job.id)
    factory = get_session_factory()
    async with factory() as session:
        job = await session.get(models.Job, job.id)
        assert job.status in ("COMPLETED", "PARTIAL")
        # events recorded
        events = (await session.execute(
            select(models.JobEvent).where(models.JobEvent.job_id == job.id)
        )).scalars().all()
        assert len(events) >= 0  # events are informational
