"""Stage 3 — normalize, dedupe, reconstruct.

For each raw conversation payload:
- normalize every message (Arabic normalization + Arabizi transliteration)
- dedupe exact/near-duplicate messages (within + across conversations)
- upsert Conversation and Message rows idempotently (unique source ids),
  preserving ordering via a reconstructed sequence.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from ... import models
from ..arabic import (
    is_arabizi,
    normalize_arabic,
    transliterate_arabizi,
)
from .context import StageContext, StageResult


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _extract_media(message: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return (media_urls, audio_urls) split by attachment type.

    Voice notes are detected from mime_type or file extension and routed to
    audio_urls (to be transcribed) instead of being sent to the vision model.
    """
    from ..ai.transcribe import _classify_attachment

    media: list[str] = []
    audio: list[str] = []
    for att in (message.get("attachments") or {}).get("data") or []:
        kind = _classify_attachment(att)
        if kind == "audio":
            url = att.get("file_url") or ""
            if url:
                audio.append(url)
        elif kind in ("image", "video"):
            img = att.get("image_data") or {}
            vid = att.get("video_data") or {}
            url = att.get("file_url") or img.get("url") or vid.get("url")
            if url:
                media.append(url)
    return media, audio


def normalize_message(raw_text: str) -> tuple[str, str]:
    """Returns (normalized_text, arabizi_transliteration)."""
    if not raw_text:
        return "", ""
    if is_arabizi(raw_text):
        translit, _conf = transliterate_arabizi(raw_text)
        return normalize_arabic(raw_text, strong=True), translit
    return normalize_arabic(raw_text, strong=True), ""


async def _upsert_conversation(
    ctx: StageContext, *, conv_id: str, page_id: str, payload: dict[str, Any]
) -> models.Conversation:
    stmt = select(models.Conversation).where(
        models.Conversation.org_id == ctx.job.org_id,
        models.Conversation.source_conversation_id == conv_id,
    )
    conv = (await ctx.session.execute(stmt)).scalar_one_or_none()
    if conv is None:
        conv = models.Conversation(
            org_id=ctx.job.org_id,
            page_id=page_id,
            source_conversation_id=conv_id,
            status="fetched",
        )
        ctx.session.add(conv)
        await ctx.session.flush()
    return conv


async def _upsert_messages(
    ctx: StageContext, conv: models.Conversation, page_id: str,
    messages: list[dict[str, Any]], normalized_cache: dict[str, str],
) -> tuple[int, int]:
    existing = {
        m.source_message_id: m
        for m in (
            await ctx.session.execute(
                select(models.Message).where(models.Message.conversation_id == conv.id)
            )
        ).scalars()
    }
    seen_normalized: dict[str, str] = {}
    added, dupes = 0, 0
    seq = max((m.sequence for m in existing.values()), default=-1) + 1

    for raw in sorted(messages, key=lambda m: _parse_time(m.get("created_time")) or datetime.min.replace(tzinfo=timezone.utc)):
        mid = str(raw.get("id", ""))
        text_raw = (raw.get("message") or "").strip()
        norm, translit = normalize_message(text_raw)
        from_info = (raw.get("from") or {})
        sender_id = str(from_info.get("id", ""))
        is_page = sender_id == page_id
        sender_type = "page" if is_page else "customer"

        dup_of = None
        if norm:
            if norm in seen_normalized:
                dup_of = seen_normalized[norm]
                dupes += 1
            else:
                seen_normalized[norm] = mid
                if norm in normalized_cache and normalized_cache[norm] != mid:
                    dup_of = normalized_cache[norm]
                    dupes += 1
            if dup_of:
                normalized_cache.setdefault(norm, dup_of)
            else:
                normalized_cache[norm] = mid

        if mid in existing:
            msg = existing[mid]
            if norm:
                msg.text_normalized = norm
            if translit and not msg.text_arabizi:
                msg.text_arabizi = translit
            media_urls, audio_urls = _extract_media(raw)
            if media_urls and not msg.media_urls:
                msg.media_urls = media_urls
            if audio_urls and not msg.audio_urls:
                msg.audio_urls = audio_urls
            continue

        media_urls, audio_urls = _extract_media(raw)
        msg = models.Message(
            conversation_id=conv.id,
            source_message_id=mid,
            sender_type=sender_type,
            sender_id=sender_id,
            author_name=str(from_info.get("name", "")),
            text_raw=text_raw,
            text_normalized=norm,
            text_arabizi=translit,
            is_duplicate=bool(dup_of),
            duplicate_of_id=dup_of,
            media_urls=media_urls,
            audio_urls=audio_urls,
            sequence=seq,
            sent_at=_parse_time(raw.get("created_time")),
        )
        seq += 1
        ctx.session.add(msg)
        added += 1
    return added, dupes


async def ingest_incoming_message(
    session,
    *,
    org_id: str,
    conn: models.PageConnection,
    sender_id: str,
    sender_name: str,
    message_id: str,
    text: str,
    created_time: str | None,
    media_urls: list[str] | None = None,
    audio_urls: list[str] | None = None,
) -> models.Message | None:
    """Real-time webhook ingest: upsert a single incoming message.

    Conversation keying: Meta webhook events do not include a conversation
    id, so we deterministically map (page, sender) to a conversation and
    reuse the source_conversation_id namespace.
    """
    media_urls = media_urls or []
    audio_urls = audio_urls or []
    if (not text or not text.strip()) and not media_urls and not audio_urls:
        return None
    if not message_id:
        return None
    conv_key = f"{conn.page_id}_{sender_id}"
    conv = (
        await session.execute(
            select(models.Conversation).where(
                models.Conversation.org_id == org_id,
                models.Conversation.source_conversation_id == conv_key,
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        conv = models.Conversation(
            org_id=org_id,
            page_id=conn.id,
            source_conversation_id=conv_key,
            status="reconstructed",
            participants=[sender_id, conn.page_id],
            participant_names={sender_id: sender_name, conn.page_id: conn.page_name},
        )
        session.add(conv)
        await session.flush()
    else:
        conv.participants = list(dict.fromkeys([*conv.participants, sender_id, conn.page_id]))
        conv.participant_names = {**conv.participant_names, sender_id: sender_name}

    existing = (
        await session.execute(
            select(models.Message).where(
                models.Message.conversation_id == conv.id,
                models.Message.source_message_id == message_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    norm, translit = normalize_message(text)
    seq = (await session.execute(
        select(models.Message.sequence)
        .where(models.Message.conversation_id == conv.id)
        .order_by(models.Message.sequence.desc())
        .limit(1)
    )).scalar_one_or_none()
    msg = models.Message(
        conversation_id=conv.id,
        source_message_id=message_id,
        sender_type="customer" if sender_id != conn.page_id else "page",
        sender_id=sender_id,
        author_name=sender_name,
        text_raw=text,
        text_normalized=norm,
        text_arabizi=translit,
        media_urls=media_urls,
        audio_urls=audio_urls,
        sequence=(seq or 0) + 1,
        sent_at=_parse_time(created_time),
    )
    session.add(msg)
    conv.status = "reconstructed"
    conv.last_message_at = msg.sent_at or conv.last_message_at
    await session.commit()
    return msg


async def stage_normalize_reconstruct(ctx: StageContext) -> StageResult:
    cp = ctx.checkpoint()
    raw_keys = list(cp.get("raw_keys") or [])
    if not raw_keys:
        return StageResult(done=0, message="لا توجد بيانات خام للمعالجة")
    page_id = cp.get("page_connection_id") or ctx.job.params.get("page_connection_id")
    conn = await ctx.session.get(models.PageConnection, page_id)
    if conn is None:
        return StageResult(done=0, message="صفحة غير موجودة", partial=True)

    normalized_cache: dict[str, str] = {}
    convs_done = int(cp.get("processed_conversations") or 0)
    total_msgs, total_dupes, total_new_convs = 0, 0, 0

    for idx in range(convs_done, len(raw_keys)):
        if idx % 20 == 0 and await ctx.check_cancelled():
            return StageResult(done=idx, total=len(raw_keys), message="أُلجيت المعالجة")
        key = raw_keys[idx]
        try:
            data = json.loads(await ctx.storage.get_object(key))
            conv_raw = data.get("conversation") or {}
            conv_id = str(conv_raw.get("id", ""))
            msgs = (conv_raw.get("messages") or {}).get("data") or []
            if not conv_id:
                await ctx.set_checkpoint(processed_conversations=idx + 1)
                continue
            conv = await _upsert_conversation(ctx, conv_id=conv_id, page_id=conn.id, payload=data)
            added, dupes = await _upsert_messages(ctx, conv, conn.page_id, msgs, normalized_cache)
            total_msgs += added
            total_dupes += dupes
            total_new_convs += 1

            participants = [str(p.get("id", "")) for p in (conv_raw.get("participants") or {}).get("data") or []]
            names = {str(p.get("id", "")): str(p.get("name", "")) for p in (conv_raw.get("participants") or {}).get("data") or []}
            conv.participants = list(dict.fromkeys(participants))
            conv.participant_names = {**conv.participant_names, **names}
            conv.status = "reconstructed"
            times = (
                await ctx.session.execute(
                    select(models.Message.sent_at).where(
                        models.Message.conversation_id == conv.id,
                        models.Message.sent_at.is_not(None),
                    )
                )
            ).scalars().all()
            if times:
                conv.first_message_at = min(times)
                conv.last_message_at = max(times)
            await ctx.session.commit()
        except Exception as exc:
            await ctx.note(f"فشل معالجة {key}: {exc}")
            await ctx.session.rollback()
        await ctx.set_checkpoint(processed_conversations=idx + 1)
        if (idx + 1) % 20 == 0:
            await ctx.progress(idx + 1, len(raw_keys), f"تمت إعادة بناء {idx + 1}/{len(raw_keys)} محادثة")

    await ctx.progress(len(raw_keys), len(raw_keys), "اكتملت إعادة البناء")
    return StageResult(
        done=len(raw_keys), total=len(raw_keys),
        message=f"محادثات: {total_new_convs}، رسائل جديدة: {total_msgs}، مكررة: {total_dupes}",
        partial=total_dupes > 0,
    )
