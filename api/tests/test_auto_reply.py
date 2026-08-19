"""Auto-reply — graceful skip and unanswered-message detection."""

from __future__ import annotations

import pytest
import pytest_asyncio

from api.app import models
from api.app.config import get_settings
from api.app.services.ai.manager import get_provider_manager
from api.app.services.pipeline.auto_reply import _latest_unanswered, handle_auto_reply


@pytest_asyncio.fixture
async def org(db):
    row = models.Organization(name="اختبار", slug="test-auto")
    db.add(row)
    await db.flush()
    yield row


@pytest_asyncio.fixture
async def page(db, org):
    row = models.PageConnection(
        org_id=org.id,
        page_id="page-1",
        page_name="صفحة",
        is_active=False,
        access_token_enc="",
    )
    db.add(row)
    await db.flush()
    yield row


@pytest.mark.asyncio
async def test_auto_reply_skips_inactive_page(db, org, page):
    conv = models.Conversation(
        org_id=org.id,
        page_id=page.id,
        source_conversation_id="page-1_customer-1",
        participants=["customer-1", "page-1"],
        participant_names={"customer-1": "عميل", "page-1": "صفحة"},
    )
    db.add(conv)
    await db.flush()
    await handle_auto_reply(
        db, get_settings(), get_provider_manager(get_settings()), conv, page
    )
    from sqlalchemy import select

    rows = (await db.execute(select(models.AiResponse))).scalars().all()
    assert rows == []


def _msg(conv_id, seq, sender_type):
    return models.Message(
        conversation_id=conv_id,
        source_message_id=f"m-{seq}",
        sender_type=sender_type,
        sender_id=sender_type,
        text_raw=f"رسالة {seq}",
        text_normalized=f"رسالة {seq}",
        sequence=seq,
    )


@pytest.mark.asyncio
async def test_latest_unanswered_picks_newest_customer_message(db):
    conv = models.Conversation(id="c-1")
    db.add(_msg("c-1", 1, "customer"))
    db.add(_msg("c-1", 2, "customer"))
    db.add(_msg("c-1", 3, "page"))
    db.add(_msg("c-1", 4, "customer"))

    found = await _latest_unanswered(db, conv)
    assert found is not None and found.sequence == 4


@pytest.mark.asyncio
async def test_latest_unanswered_none_when_page_replied(db):
    conv = models.Conversation(id="c-2")
    db.add(_msg("c-2", 1, "customer"))
    db.add(_msg("c-2", 2, "page"))

    assert await _latest_unanswered(db, conv) is None


@pytest.mark.asyncio
async def test_latest_unanswered_old_customer_when_no_reply(db):
    conv = models.Conversation(id="c-3")
    db.add(_msg("c-3", 1, "customer"))

    found = await _latest_unanswered(db, conv)
    assert found is not None and found.sequence == 1