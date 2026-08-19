from __future__ import annotations

import pytest
from sqlalchemy import select

from api.app import models
from api.app.db import get_session_factory

from .conftest import csrf_headers, login, register


@pytest.mark.asyncio
async def test_tenant_scoping_between_orgs(client):
    a = await register(client, email="a@example.com", org="منظمة ألف")
    org_a = a["orgs"][0]["id"]
    await client.post("/api/auth/logout")

    b = await register(client, email="b@example.com", org="منظمة باء")
    org_b = b["orgs"][0]["id"]

    # seed a page connection + conversation for org A directly
    factory = get_session_factory()
    async with factory() as session:
        conn = models.PageConnection(
            org_id=org_a, connected_by=a["user"]["id"], page_id="fb-1",
            page_name="صفحة ألف", is_active=True,
        )
        session.add(conn)
        await session.flush()
        conv = models.Conversation(
            org_id=org_a, page_id=conn.id, source_conversation_id="conv-1", status="reconstructed",
        )
        session.add(conv)
        await session.commit()
        conv_id = conv.id

    # user B (org B) must not see org A's pages or conversations
    pages = await client.get("/api/pages")
    assert pages.status_code == 200
    assert pages.json() == []
    detail = await client.get(f"/api/conversations/{conv_id}")
    assert detail.status_code == 404
    lst = await client.get("/api/conversations")
    assert lst.json()["items"] == []


@pytest.mark.asyncio
async def test_role_enforcement(client):
    data = await register(client, email="owner@example.com", org="منظمة الأدوار")
    org_id = data["orgs"][0]["id"]

    factory = get_session_factory()
    async with factory() as session:
        conn = models.PageConnection(
            org_id=org_id, connected_by=data["user"]["id"], page_id="fb-2",
            page_name="صفحة الأدوار", is_active=True,
        )
        session.add(conn)
        await session.commit()
        page_id = conn.id

    # viewer cannot sync a page
    viewer = await register(client, email="viewer@example.com", org="منظمة المشاهد")
    viewer_org = viewer["orgs"][0]["id"]
    # add viewer to owner org with role viewer
    async with factory() as session:
        from api.app.security import hash_password

        viewer_user = (
            await session.execute(select(models.User).where(models.User.email == "viewer@example.com"))
        ).scalar_one()
        session.add(models.OrgMembership(org_id=org_id, user_id=viewer_user.id, role="viewer"))
        await session.commit()
    await client.post("/api/auth/logout")
    await login(client, email="viewer@example.com", password="StrongPass123")
    await client.post("/api/auth/switch-org", json={"org_id": org_id}, headers=csrf_headers(client))

    sync = await client.post(f"/api/pages/{page_id}/sync", headers=csrf_headers(client))
    assert sync.status_code == 403


@pytest.mark.asyncio
async def test_inbox_review_flow(client):
    data = await register(client, email="mod@example.com", org="منظمة المراجعة")
    org_id = data["orgs"][0]["id"]
    factory = get_session_factory()
    async with factory() as session:
        conn = models.PageConnection(
            org_id=org_id, connected_by=data["user"]["id"], page_id="fb-3",
            page_name="صفحة المراجعة", is_active=True,
        )
        session.add(conn)
        await session.flush()
        conv = models.Conversation(
            org_id=org_id, page_id=conn.id, source_conversation_id="conv-2",
            status="analyzed", dialect_label="egyptian", intent_label="question",
        )
        session.add(conv)
        await session.flush()
        resp = models.AiResponse(
            org_id=org_id, conversation_id=conv.id, status="pending_approval",
            provider="ollama", text="أهلاً بك، سعر المنتج 850 جنيه والمقاسات متوفرة",
        )
        session.add(resp)
        await session.commit()
        resp_id, conv_id = resp.id, conv.id

    inbox = await client.get("/api/inbox")
    assert inbox.status_code == 200
    items = inbox.json()["items"]
    assert any(it["id"] == resp_id and it["type"] == "response" for it in items)

    # approve the response
    review = await client.post(
        f"/api/conversations/{conv_id}/responses/{resp_id}/review",
        json={"decision": "approve"},
        headers=csrf_headers(client),
    )
    assert review.status_code == 200
    assert review.json()["status"] == "approved"

    # inbox no longer lists it
    inbox2 = await client.get("/api/inbox")
    assert all(it["id"] != resp_id for it in inbox2.json()["items"])

    stats = await client.get("/api/inbox/stats")
    assert stats.json()["pending_reviews"] == 0


@pytest.mark.asyncio
async def test_jobs_list_serializes_events(client):
    """GET /api/jobs must serialize jobs with their events (async lazy-load guard)."""
    data = await register(client, email="jobs@example.com", org="منظمة الوظائف")
    org_id = data["orgs"][0]["id"]
    factory = get_session_factory()
    async with factory() as session:
        job = models.Job(
            org_id=org_id, kind="dataset_generate", status="COMPLETED",
            idempotency_key="jobs-list-1",
        )
        session.add(job)
        await session.flush()
        session.add(models.JobEvent(job_id=job.id, event="started"))
        session.add(models.JobEvent(job_id=job.id, event="completed"))
        await session.commit()
        job_id = job.id

    resp = await client.get("/api/jobs")
    assert resp.status_code == 200
    items = resp.json()["items"]
    match = next(j for j in items if j["id"] == job_id)
    assert [e["event"] for e in match["events"]] == ["started", "completed"]

    detail = await client.get(f"/api/jobs/{job_id}")
    assert detail.status_code == 200
    assert len(detail.json()["events"]) == 2


@pytest.mark.asyncio
async def test_draft_response_without_model_is_honest(client):
    data = await register(client, email="draft@example.com", org="منظمة المسودة")
    org_id = data["orgs"][0]["id"]
    factory = get_session_factory()
    async with factory() as session:
        conn = models.PageConnection(
            org_id=org_id, connected_by=data["user"]["id"], page_id="fb-4",
            page_name="صفحة المسودة", is_active=True,
        )
        session.add(conn)
        await session.flush()
        conv = models.Conversation(
            org_id=org_id, page_id=conn.id, source_conversation_id="conv-3",
            status="analyzed", dialect_label="msa",
        )
        session.add(conv)
        await session.flush()
        msg = models.Message(
            conversation_id=conv.id, source_message_id="m-1", sender_type="customer",
            sender_id="u-1", text_raw="كم سعر المنتج؟", text_normalized="كم سعر المنتج?",
            sequence=1,
        )
        session.add(msg)
        await session.commit()
        conv_id = conv.id

    # no Ollama reachable in tests → response marked failed with a clear message
    draft = await client.post(
        f"/api/conversations/{conv_id}/responses",
        json={"instructions": ""},
        headers=csrf_headers(client),
    )
    assert draft.status_code == 200
    body = draft.json()
    assert body["status"] == "failed"
    assert "غير متاح" in body["error"]
