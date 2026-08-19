"""Stages 5-7 — quality filtering, dataset generation, memory indexing.

Quality: re-compute dataset eligibility (score, flagged, length, presence
of a page reply). Dataset: upsert DatasetRow rows. Memory: embed
conversation chunks into pgvector (or JSON in SQLite sandbox); skips
honestly when no embedding provider is available.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ... import models
from ... import metrics
from ..ai.base import ModelUnavailableError
from .context import StageContext, StageResult

MIN_QUALITY_FOR_DATASET = 0.5


async def _upsert_knowledge(
    session,
    *,
    org_id: str,
    topic: str,
    content: str,
    kind: str = "fact",
    source_id: str | None = None,
    confidence: float = 0.9,
) -> models.KnowledgeItem | None:
    """Idempotently store a business-knowledge item (used by the owner agent)."""
    if not content:
        return None
    existing = (
        await session.execute(
            select(models.KnowledgeItem).where(
                models.KnowledgeItem.org_id == org_id,
                models.KnowledgeItem.content == content,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    item = models.KnowledgeItem(
        org_id=org_id,
        topic=topic,
        kind=kind,
        content=content,
        source_conversation_id=source_id,
        confidence=confidence,
    )
    session.add(item)
    await session.commit()
    return item


def _chunk_messages(messages: list[models.Message]) -> list[str]:
    lines: list[str] = []
    for m in messages:
        if m.is_duplicate:
            continue
        text = m.text_normalized or m.text_raw
        if not text:
            continue
        lines.append(text[:500])
        if len(lines) >= 40:
            break
    if not lines:
        return []
    chunks = []
    for i in range(0, len(lines), 6):
        chunks.append(" | ".join(lines[i:i + 6]))
    return chunks


async def stage_quality(ctx: StageContext) -> StageResult:
    conn_id = ctx.checkpoint().get("page_connection_id") or ctx.job.params.get("page_connection_id")
    rows = await ctx.session.execute(
        select(models.Conversation)
        .options(selectinload(models.Conversation.messages))
        .where(models.Conversation.org_id == ctx.job.org_id)
        .order_by(models.Conversation.updated_at)
    )
    conversations = list(rows.scalars().all())
    if conn_id:
        conversations = [c for c in conversations if c.page_id == conn_id]

    eligible = 0
    for conv in conversations:
        page_replies = sum(1 for m in conv.messages if m.sender_type == "page" and (m.text_normalized or m.text_raw))
        customer_msgs = sum(1 for m in conv.messages if m.sender_type == "customer" and not m.is_duplicate)
        q = conv.quality_score
        ok = (
            q >= MIN_QUALITY_FOR_DATASET
            and not conv.is_flagged
            and customer_msgs >= 1
            and page_replies >= 1
        )
        conv.meta = {**conv.meta, "dataset_eligible": ok, "customer_messages": customer_msgs, "page_replies": page_replies}
        conv.status = "quality_checked"
        if ok:
            eligible += 1
        metrics.PIPELINE_ITEMS.labels(kind=ctx.job.kind, stage="quality", outcome="eligible" if ok else "filtered").inc()
    await ctx.session.commit()
    await ctx.progress(eligible, max(1, len(conversations)), f"مؤهل للمجموعة: {eligible}")
    return StageResult(done=eligible, total=len(conversations), message=f"{eligible} محادثة مؤهلة للمجموعة التدريبية")


async def stage_dataset(ctx: StageContext) -> StageResult:
    rows = await ctx.session.execute(
        select(models.Conversation)
        .options(selectinload(models.Conversation.messages))
        .where(
            models.Conversation.org_id == ctx.job.org_id,
            models.Conversation.status.in_(["quality_checked", "dataset_ready"]),
        )
    )
    conversations = list(rows.scalars().all())
    created = 0
    for conv in conversations:
        if not (conv.meta or {}).get("dataset_eligible", False):
            continue
        existing = (
            await ctx.session.execute(
                select(models.DatasetRow).where(
                    models.DatasetRow.org_id == ctx.job.org_id,
                    models.DatasetRow.conversation_id == conv.id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            conv.dataset_included = True
            conv.status = "dataset_ready"
            continue
        customer = next((m for m in conv.messages if m.sender_type == "customer" and (m.text_normalized or m.text_raw)), None)
        page = next((m for m in conv.messages if m.sender_type == "page" and (m.text_normalized or m.text_raw)), None)
        sample = f"عميل: {customer.text_normalized or customer.text_raw}\nصفحة: {page.text_normalized or page.text_raw}" if customer and page else ""
        ctx.session.add(
            models.DatasetRow(
                org_id=ctx.job.org_id,
                conversation_id=conv.id,
                dialect_label=conv.dialect_label,
                intent_label=conv.intent_label,
                sample=sample[:2000],
                quality_score=conv.quality_score,
            )
        )
        conv.dataset_included = True
        conv.status = "dataset_ready"
        created += 1
    await ctx.session.commit()
    await ctx.progress(created, max(1, created), f"تم توليد {created} صف مجموعة")
    return StageResult(done=created, total=created, message=f"صفوف المجموعة الجديدة: {created}")


async def stage_memory(ctx: StageContext) -> StageResult:
    if not await ctx.providers.embeddings_available():
        await ctx.note("محرك التضمين غير متاح — تم تخطي فهرسة الذاكرة (شغّل صورة العامل الكاملة)")
        await ctx.progress(0, 1, "تخطي فهرسة الذاكرة (لا يوجد محرك تضمين)")
        return StageResult(done=0, total=0, message="تخطي فهرسة الذاكرة — محرك التضمين غير متاح", partial=True)

    rows = await ctx.session.execute(
        select(models.Conversation)
        .options(selectinload(models.Conversation.messages))
        .where(
            models.Conversation.org_id == ctx.job.org_id,
            models.Conversation.status == "dataset_ready",
        )
    )
    conversations = list(rows.scalars().all())
    provider = ctx.providers.embeddings()
    indexed = 0
    for conv in conversations:
        if await ctx.check_cancelled():
            return StageResult(done=indexed, message="أُلجيت الفهرسة")
        chunks = _chunk_messages(conv.messages)
        if not chunks:
            continue
        try:
            vectors = await provider.embed(chunks)
        except ModelUnavailableError:
            await ctx.note("محرك التضمين غير متاح أثناء الفهرسة")
            break
        for chunk, vec in zip(chunks, vectors):
            ctx.session.add(
                models.MemoryChunk(
                    org_id=ctx.job.org_id,
                    conversation_id=conv.id,
                    chunk_text=chunk,
                    embedding=vec,
                    source="conversation",
                )
            )
            metrics.EMBEDDINGS_TOTAL.labels(provider=provider.name, status="ok").inc()
        indexed += len(chunks)
        if indexed % 50 == 0:
            await ctx.session.commit()
            await ctx.progress(indexed, indexed, f"تم تضمين {indexed} مقطع")
    await ctx.session.commit()
    await ctx.progress(indexed, max(1, indexed), f"تمت فهرسة {indexed} مقطع في الذاكرة")
    return StageResult(done=indexed, total=indexed, message=f"فهرسة ذاكرة: {indexed} مقطع مضمن")
