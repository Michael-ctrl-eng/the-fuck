"""Stage 4 — Arabic language analysis.

Deterministic analysis always runs (dialect, intent, entities, moderation,
style, quality, knowledge extraction). When an LLM provider is available it
upgrades dialect/intent/moderation with reasoned output; when it is not,
analysis results record provider="deterministic" and the job notes that the
model was unavailable — nothing is faked.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ... import models
from ..arabic import (
    DIALECT_LABELS,
    detect_dialect,
    detect_intent,
    extract_entities,
    moderation_check,
    normalize_arabic,
    quality_score,
)
from ..ai.base import ModelUnavailableError
from .context import StageContext, StageResult

STYLE_PROMPT = """أنت خبير لغة عربية. حلّل أسلوب الصفحة في الردود أدناه وأعد JSON فقط:
{"tone": "formal|casual|friendly", "emoji_use": 0-1, "greeting_pattern": "..." ,
"signoff_pattern": "...", "avg_length": "short|medium|long", "summary": "..."}"""

DIALECT_PROMPT = """أنت خبير لهجات عربية. حدّد لهجة النص التالي من: مصري، سعودي، خليجي، شامي، عراقي، مغاربي، فصحى، أو مختلط.
أعد JSON فقط: {"dialect": "..." , "confidence": 0-1, "reason": "..."}"""

INTENT_PROMPT = """أنت محلل نوايا. صنّف نية الرسالة من: سؤال، شراء، شكوى، دعم فني، إشادة، إعلان/سبام، تصعيد، تحية، أو غير محدد.
أعد JSON فقط: {"intent": "...", "confidence": 0-1, "reason": "..."}"""

MODERATION_PROMPT = """أنت مراقب محتوى. افحص النص التالي عن إساءة أو تهديد أو احتيال أو إعلان مزعج.
أعد JSON فقط: {"flagged": true|false, "severity": "info|warn|critical", "reason": "..."}"""


async def _messages(session, conv_id: str) -> list[models.Message]:
    return list(
        (
            await session.execute(
                select(models.Message)
                .where(models.Message.conversation_id == conv_id)
                .order_by(models.Message.sequence)
            )
        ).scalars().all()
    )


async def _customer_texts(session, conv: models.Conversation) -> str:
    parts = [
        m.text_normalized or m.text_raw
        for m in await _messages(session, conv.id)
        if m.sender_type == "customer" and not m.is_duplicate
    ]
    return " ".join(parts)[:3000]


async def _page_texts(session, conv: models.Conversation) -> list[str]:
    return [
        m.text_normalized or m.text_raw
        for m in await _messages(session, conv.id)
        if m.sender_type == "page"
    ]


async def _upsert_analysis(
    ctx: StageContext, conv: models.Conversation, kind: str,
    *, payload: dict, provider: str = "deterministic", confidence: float = 0.0,
    model: str = "", status: str = "completed", error: str = "",
) -> models.AnalysisResult:
    row = (
        await ctx.session.execute(
            select(models.AnalysisResult).where(
                models.AnalysisResult.conversation_id == conv.id,
                models.AnalysisResult.kind == kind,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = models.AnalysisResult(conversation_id=conv.id, kind=kind)
        ctx.session.add(row)
    row.provider = provider
    row.status = status
    row.confidence = confidence
    row.payload = payload
    row.model = model
    row.error = error
    return row


async def _llm_refine(ctx: StageContext, conv: models.Conversation, text: str) -> bool:
    """Upgrade dialect/intent/moderation with the LLM when available."""
    try:
        provider = ctx.providers.llm()
        if not await provider.available():
            return False
    except ModelUnavailableError:
        return False

    try:
        # dialect
        res = await provider.complete(system=DIALECT_PROMPT, user=text[:2000], json_mode=True, temperature=0.1, kind="dialect")
        parsed = _parse_json(res.text)
        if parsed and parsed.get("dialect"):
            label_map = {
                "مصري": "egyptian", "سعودي": "saudi", "خليجي": "gulf", "شامي": "levantine",
                "عراقي": "iraqi", "مغاربي": "maghrebi", "فصحى": "msa", "مختلط": "mixed",
                "عربيزي": "arabizi", "غير محدد": "unknown",
            }
            label = label_map.get(str(parsed.get("dialect")).strip(), "unknown")
            conf = float(parsed.get("confidence") or 0.0)
            await _upsert_analysis(
                ctx, conv, "dialect",
                payload={"label": label, "confidence": conf, "reason": parsed.get("reason", ""), "deterministic": detect_dialect(text)},
                provider="ollama", confidence=conf, model=res.model,
            )
            conv.dialect_label = label
            conv.dialect_confidence = conf
        # intent
        res = await provider.complete(system=INTENT_PROMPT, user=text[:1500], json_mode=True, temperature=0.1, kind="intent")
        parsed = _parse_json(res.text)
        if parsed and parsed.get("intent"):
            label_map = {
                "سؤال": "question", "شراء": "purchase", "شكوى": "complaint", "دعم فني": "support",
                "إشادة": "praise", "إعلان/سبام": "spam", "تصعيد": "escalation", "تحية": "greeting",
                "غير محدد": "unknown",
            }
            label = label_map.get(str(parsed.get("intent")).strip(), "unknown")
            await _upsert_analysis(
                ctx, conv, "intent",
                payload={"label": label, "confidence": float(parsed.get("confidence") or 0.0), "reason": parsed.get("reason", "")},
                provider="ollama", confidence=float(parsed.get("confidence") or 0.0), model=res.model,
            )
            conv.intent_label = label
        # moderation
        res = await provider.complete(system=MODERATION_PROMPT, user=text[:1500], json_mode=True, temperature=0.0, kind="moderation")
        parsed = _parse_json(res.text)
        if parsed and parsed.get("flagged"):
            await _upsert_analysis(
                ctx, conv, "moderation",
                payload={"severity": parsed.get("severity", "warn"), "reason": parsed.get("reason", "")},
                provider="ollama", confidence=0.9, model=res.model,
            )
        await ctx.session.commit()
        return True
    except ModelUnavailableError:
        return False
    except Exception as exc:
        await ctx.note(f"فشل تحسين LLM للمحادثة {conv.source_conversation_id}: {exc}")
        ctx.session.rollback()
        return False


def _parse_json(text: str) -> dict | None:
    import json

    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _style_profile(page_msgs: list[str]) -> dict:
    if not page_msgs:
        return {"tone": "unknown", "emoji_use": 0.0, "greeting_pattern": "", "signoff_pattern": "", "avg_length": "unknown", "summary": "لا توجد ردود من الصفحة بعد"}
    joined = " ".join(page_msgs)
    emoji = sum(1 for ch in joined if ord(ch) > 0x1F000)
    emoji_ratio = round(emoji / max(1, len(page_msgs)), 2)
    greetings = ["السلام عليكم", "مرحبا", "أهلا", "صباح", "مساء", "أهلاً"]
    signoffs = ["شكرا", "مع التحية", "دمتم", "في الخدمة", "حياكم", "بانتظارك"]
    greeting = next((g for g in greetings if g in joined), "")
    signoff = next((s for s in signoffs if s in joined), "")
    avg_len = sum(len(m) for m in page_msgs) / max(1, len(page_msgs))
    avg = "short" if avg_len < 60 else ("medium" if avg_len < 160 else "long")
    msa_ratio = sum(1 for m in page_msgs if detect_dialect(m)["label"] == "msa") / len(page_msgs)
    tone = "formal" if msa_ratio >= 0.6 else ("friendly" if emoji_ratio > 0 or greeting else "casual")
    return {
        "tone": tone, "emoji_use": emoji_ratio, "greeting_pattern": greeting,
        "signoff_pattern": signoff, "avg_length": avg, "summary": f"{len(page_msgs)} رد من الصفحة، نبرة {tone}",
    }


def _extract_knowledge(conv: models.Conversation, page_msgs: list[str]) -> list[dict]:
    items: list[dict] = []
    for text in page_msgs:
        if not text:
            continue
        has_price = bool(re.search(r"(\d+(?:[.,]\d+)?)\s*(ريال|جنيه|درهم|دينار|دولار|ليرة|يورو)", text))
        is_answer = any(k in text for k in ("نعم", "يمكن", "متوفر", "سعر", "تكلفة", "الخدمة", "المنتج", "ضمان"))
        if has_price and is_answer:
            items.append({"kind": "fact", "topic": "pricing", "content": text[:500], "confidence": 0.6})
        elif is_answer and len(text) > 40:
            items.append({"kind": "faq", "topic": "policy", "content": text[:500], "confidence": 0.45})
        if len(items) >= 5:
            break
    return items


async def analyze_single(ctx: StageContext, conv: models.Conversation, *, force: bool = False) -> bool:
    """Run the full deterministic analysis on one conversation (+LLM upgrade).

    Returns True if an LLM upgrade happened.
    """
    session = ctx.session
    # Voice notes first: transcribe so analysis covers what was said.
    # Bounded concurrency; failures never block analysis (voice stays
    # untranscribed rather than crashing the stage).
    voice_msgs = [
        m for m in await _messages(session, conv.id)
        if (m.audio_urls or []) and not m.transcribed_text
    ]
    if voice_msgs:
        import asyncio

        from ..ai.transcribe import transcribe_message_audio

        _voice_sem = asyncio.Semaphore(2)

        async def _one(m) -> None:
            async with _voice_sem:
                try:
                    await transcribe_message_audio(session, m, ctx.settings)
                except Exception:
                    pass

        await asyncio.gather(*(_one(m) for m in voice_msgs[:6]))
        await ctx.session.commit()

    text = await _customer_texts(session, conv)
    llm_upgraded = False
    if text:
        d = detect_dialect(text)
        await _upsert_analysis(
            ctx, conv, "dialect",
            payload={"label": d["label"], "confidence": round(d["confidence"], 3), "scores": d.get("scores", {}), "candidates": d.get("candidates", [])},
            provider="deterministic", confidence=d["confidence"],
        )
        conv.dialect_label = d["label"]
        conv.dialect_confidence = d["confidence"]
        intent = detect_intent(text)
        await _upsert_analysis(
            ctx, conv, "intent",
            payload={"label": intent["label"], "confidence": round(intent["confidence"], 3), "scores": intent.get("scores", {})},
            provider="deterministic", confidence=intent["confidence"],
        )
        conv.intent_label = intent["label"]
        entities: dict = {"emails": [], "phones": [], "urls": [], "mentions": [], "hashtags": [], "prices": [], "times": [], "dates": [], "numbers": []}
        products: list[dict] = []
        for m in await _messages(session, conv.id):
            if m.sender_type == "customer" and not m.is_duplicate:
                ent = extract_entities(m.text_raw or m.text_normalized)
                for k in entities:
                    entities[k].extend(ent.get(k) or [])

        # Vision: analyze product images with bounded concurrency (never
        # serial per image — that would stall the whole analysis stage).
        if any(m.media_urls for m in await _messages(session, conv.id)):
            import asyncio

            from ..ai.vision import analyze_product_image

            _vision_sem = asyncio.Semaphore(4)

            async def _analyze_image(url: str) -> None:
                async with _vision_sem:
                    try:
                        img_res = await analyze_product_image(ctx.settings, url)
                        if img_res and img_res.product_name:
                            products.append(img_res.model_dump())
                    except Exception:
                        pass

            media_urls = [
                u
                for m in await _messages(session, conv.id)
                for u in (m.media_urls or [])
            ]
            await asyncio.gather(*(_analyze_image(u) for u in media_urls[:8]))
                            
        for k in entities:
            if k == "prices":
                continue  # dict entries — keep as extracted
            entities[k] = list(dict.fromkeys(entities[k]))
            
        payload_entities = dict(entities)
        if products:
            payload_entities["visual_products"] = products
            
        await _upsert_analysis(ctx, conv, "entities", payload=payload_entities, provider="deterministic")
        # moderation per message
        flagged = False
        for m in await _messages(session, conv.id):
            if not (m.text_raw or m.text_normalized):
                continue
            check = moderation_check(m.text_raw or m.text_normalized)
            if not check["flags"]:
                continue
            flagged = True
            existing = (
                await ctx.session.execute(
                    select(models.ModerationDecision).where(
                        models.ModerationDecision.conversation_id == conv.id,
                        models.ModerationDecision.message_id == m.id,
                        models.ModerationDecision.status == "open",
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                ctx.session.add(
                    models.ModerationDecision(
                        org_id=ctx.job.org_id,
                        conversation_id=conv.id,
                        message_id=m.id,
                        severity=check["flags"][0]["severity"],
                        decision=check["decision"],
                        reason=check["summary"],
                        ai_rationale="كشف معجمي حتمي",
                    )
                )
        conv.is_flagged = flagged
        # style + quality
        page_msgs = await _page_texts(session, conv)
        style = _style_profile(page_msgs)
        await _upsert_analysis(ctx, conv, "style", payload=style, provider="deterministic")
        q = quality_score(text, dialect_confidence=conv.dialect_confidence)
        await _upsert_analysis(
            ctx, conv, "quality",
            payload=q, provider="deterministic", confidence=q["score"],
        )
        conv.quality_score = q["score"]
        # knowledge
        for item in _extract_knowledge(conv, page_msgs):
            exists = (
                await ctx.session.execute(
                    select(models.KnowledgeItem).where(
                        models.KnowledgeItem.org_id == ctx.job.org_id,
                        models.KnowledgeItem.content == item["content"],
                    )
                )
            ).scalar_one_or_none()
            if exists is None:
                ctx.session.add(
                    models.KnowledgeItem(
                        org_id=ctx.job.org_id,
                        topic=item["topic"],
                        kind=item["kind"],
                        content=item["content"],
                        source_conversation_id=conv.source_conversation_id,
                        confidence=item["confidence"],
                    )
                )
        # LLM upgrade (best effort)
        try:
            if await _llm_refine(ctx, conv, text):
                llm_upgraded = True
        except Exception:
            ctx.session.rollback()
    conv.status = "analyzed"
    return llm_upgraded


async def stage_analyze(ctx: StageContext) -> StageResult:
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

    done = int(ctx.checkpoint().get("analyzed") or 0)
    analyzed, llm_upgraded = 0, 0
    total = len(conversations)
    for conv in conversations[done:]:
        if await ctx.check_cancelled():
            return StageResult(done=done + analyzed, total=total, message="أُلجيت التحليلات")
        if await analyze_single(ctx, conv):
            llm_upgraded += 1
        analyzed += 1
        await ctx.set_checkpoint(analyzed=done + analyzed)
        if analyzed % 10 == 0:
            await ctx.session.commit()
            await ctx.progress(done + analyzed, total, f"تحليل {done + analyzed}/{total}")
    await ctx.session.commit()
    await ctx.progress(total, total, "اكتمل التحليل اللغوي")
    return StageResult(
        done=total, total=total,
        message=f"تم تحليل {analyzed} محادثة (ترقية ذكاء اصطناعي: {llm_upgraded})",
    )
