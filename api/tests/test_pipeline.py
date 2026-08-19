from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from api.app import models
from api.app.config import get_settings
from api.app.db import get_session_factory
from api.app.services.pipeline import create_job, run_job
from api.app.services.storage import get_storage

SAMPLES = Path(__file__).resolve().parents[2] / "api" / "sample_data"


async def _org(db, name="منظمة الاختبار"):
    org = models.Organization(name=name, slug="org-test")
    db.add(org)
    await db.flush()
    return org


async def _page(db, org, name="صفحة الاختبار"):
    conn = models.PageConnection(org_id=org.id, page_id="sample-test", page_name=name, is_active=True)
    db.add(conn)
    await db.flush()
    return conn


async def _seed_raw_job(db, org, conn, sample_name: str, count: int) -> models.Job:
    settings = get_settings()
    storage = get_storage(settings)
    data = json.loads((SAMPLES / f"{sample_name}.json").read_text(encoding="utf-8"))
    # The page connection must use the page id from the sample so that
    # page-sent messages classify as sender_type="page" (matches real Meta data).
    conn.page_id = str((data.get("page") or {}).get("id") or conn.page_id)
    convs = data["conversations"][:count]
    job = await create_job(
        db, org_id=org.id, kind="page_import",
        params={"page_connection_id": conn.id, "page_name": conn.page_name},
        idempotency_key=f"test:{sample_name}:{org.id}",
    )
    raw_keys = []
    for i, conv in enumerate(convs):
        key = f"orgs/{org.id}/raw/{job.id}/sample_{i}.json"
        await storage.put_object(
            key,
            json.dumps({"conversation": conv, "page_id": conn.page_id, "page_name": conn.page_name}, ensure_ascii=False).encode(),
            "application/json",
        )
        raw_keys.append(key)
    job.checkpoint = {
        "raw_keys": raw_keys,
        "fetched_conversations": len(raw_keys),
        "processed_conversations": 0,
        "cursor": None,
        "pages": 1,
        "page_connection_id": conn.id,
        "page_name": conn.page_name,
        "completed_stages": ["fetch", "validate"],
    }
    await db.commit()
    return job


@pytest.mark.asyncio
async def test_full_pipeline_on_egyptian_sample(db):
    org = await _org(db)
    conn = await _page(db, org)
    job = await _seed_raw_job(db, org, conn, "egyptian-shop", count=5)

    await run_job(job.id)

    factory = get_session_factory()
    async with factory() as session:
        job = await session.get(models.Job, job.id)
        # memory stage is skipped without an embedding provider → PARTIAL is honest
        assert job.status in ("COMPLETED", "PARTIAL"), job.error
        convs = (await session.execute(
            select(models.Conversation).where(models.Conversation.org_id == org.id)
        )).scalars().all()
        assert len(convs) == 5
        msgs = (await session.execute(
            select(models.Message).where(
                models.Message.conversation_id.in_([c.id for c in convs])
            )
        )).scalars().all()
        assert len(msgs) >= 12
        # normalized Arabic present
        assert any("جنيه" in m.text_normalized for m in msgs)
        # dialect analysis stored
        analyses = (await session.execute(
            select(models.AnalysisResult).where(
                models.AnalysisResult.conversation_id.in_([c.id for c in convs])
            )
        )).scalars().all()
        kinds = {a.kind for a in analyses}
        assert {"dialect", "intent", "entities", "style", "quality"} <= kinds
        # moderation: spam + escalation conversations flagged
        flagged = [c for c in convs if c.is_flagged]
        assert len(flagged) >= 2
        flags = (await session.execute(
            select(models.ModerationDecision).where(models.ModerationDecision.org_id == org.id)
        )).scalars().all()
        severities = {f.severity for f in flags}
        assert "critical" in severities or "spam" in severities
        # dataset rows for eligible conversations
        rows = (await session.execute(
            select(models.DatasetRow).where(models.DatasetRow.org_id == org.id)
        )).scalars().all()
        assert len(rows) >= 2


@pytest.mark.asyncio
async def test_pipeline_dialect_labels(db):
    org = await _org(db)
    conn = await _page(db, org)
    job = await _seed_raw_job(db, org, conn, "levantine-support", count=5)
    await run_job(job.id)

    factory = get_session_factory()
    async with factory() as session:
        job = await session.get(models.Job, job.id)
        assert job.status in ("COMPLETED", "PARTIAL"), job.error
        convs = (await session.execute(
            select(models.Conversation).where(models.Conversation.org_id == org.id)
        )).scalars().all()
        labels = {c.dialect_label for c in convs if c.dialect_label != "unknown"}
        assert labels  # at least some conversations got a dialect label


@pytest.mark.asyncio
async def test_deduplication_and_idempotency(db):
    org = await _org(db)
    conn = await _page(db, org)
    job = await _seed_raw_job(db, org, conn, "gulf-restaurant", count=4)
    await run_job(job.id)

    # run the same job again → still idempotent (unique source ids)
    await run_job(job.id)

    factory = get_session_factory()
    async with factory() as session:
        convs = (await session.execute(
            select(models.Conversation).where(models.Conversation.org_id == org.id)
        )).scalars().all()
        assert len(convs) == 4
        msgs = (await session.execute(
            select(models.Message).where(
                models.Message.conversation_id.in_([c.id for c in convs])
            )
        )).scalars().all()
        ids = [m.source_message_id for m in msgs]
        assert len(ids) == len(set(ids))
