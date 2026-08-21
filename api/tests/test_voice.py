"""Voice notes — attachment classification + transcription persistence (mocked)."""

from __future__ import annotations

import pytest
import pytest_asyncio

from api.app import models
from api.app.config import get_settings
from api.app.services.ai.transcribe import _classify_attachment, transcribe_message_audio


def _att(mime: str = "", url: str = "", image: bool = False, video: bool = False) -> dict:
    att: dict = {"mime_type": mime, "file_url": url}
    if image:
        att["image_data"] = {"url": "https://cdn.example/img.jpg"}
    if video:
        att["video_data"] = {"url": "https://cdn.example/v.mp4"}
    return att


def test_classify_audio_by_mime():
    assert _classify_attachment(_att(mime="audio/mpeg", url="https://x/m.mp4")) == "audio"
    assert _classify_attachment(_att(mime="audio/ogg", url="https://x/v.ogg")) == "audio"
    assert _classify_attachment(_att(url="https://x/voice.m4a")) == "audio"
    assert _classify_attachment(_att(url="https://x/voice.opus")) == "audio"


def test_classify_image_and_video():
    assert _classify_attachment(_att(mime="image/jpeg")) == "image"
    assert _classify_attachment(_att(image=True)) == "image"
    assert _classify_attachment(_att(video=True)) == "video"
    assert _classify_attachment(_att()) is None


@pytest_asyncio.fixture
async def conv(db):
    org = models.Organization(name="اختبار", slug="test-voice")
    db.add(org)
    await db.flush()
    row = models.Conversation(org_id=org.id, page_id="p-1", source_conversation_id="x")
    db.add(row)
    await db.flush()
    yield row


@pytest.mark.asyncio
async def test_transcribe_sets_text_fields(db, conv, monkeypatch):
    async def fake_transcribe(settings, url):  # noqa: ARG001
        return "عايز اعرف سعر العطر بليز وبكام الشحن"

    monkeypatch.setattr("api.app.services.ai.transcribe.transcribe_audio", fake_transcribe)

    msg = models.Message(
        conversation_id=conv.id,
        source_message_id="m-1",
        sender_type="customer",
        text_raw="",
        audio_urls=["https://cdn.example/voice.m4a"],
        sequence=1,
    )
    db.add(msg)
    await db.flush()

    out = await transcribe_message_audio(db, msg, get_settings())
    assert out == "عايز اعرف سعر العطر بليز وبكام الشحن"
    assert msg.transcribed_text == out
    assert msg.text_raw == out
    assert msg.text_normalized  # normalized Arabic
    await db.commit()

    # idempotent: second call does not re-transcribe
    calls = {"n": 0}

    async def counting(settings, url):  # noqa: ARG001
        calls["n"] += 1
        return "second"

    monkeypatch.setattr("api.app.services.ai.transcribe.transcribe_audio", counting)
    again = await transcribe_message_audio(db, msg, get_settings())
    assert again == out
    assert calls["n"] == 0


@pytest.mark.asyncio
async def test_transcribe_skips_without_audio(db, conv, monkeypatch):
    called = {"n": 0}

    async def counting(settings, url):  # noqa: ARG001
        called["n"] += 1
        return "x"

    monkeypatch.setattr("api.app.services.ai.transcribe.transcribe_audio", counting)
    msg = models.Message(
        conversation_id=conv.id,
        source_message_id="m-2",
        sender_type="customer",
        text_raw="نص عادي",
        sequence=2,
    )
    db.add(msg)
    await db.flush()
    assert await transcribe_message_audio(db, msg, get_settings()) is None
    assert called["n"] == 0
    assert msg.text_raw == "نص عادي"