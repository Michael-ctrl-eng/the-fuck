"""AI responder — drafts replies to customer conversations.

Pipeline: build an Arabic prompt from the reconstructed conversation, the
page style profile, organization knowledge and semantic memory retrieval
(RAG); call the LLM provider; validate the draft (length, dialect
consistency, moderation) and store it as pending_approval for the
human-in-the-loop inbox.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ... import models
from ... import metrics
from ...config import Settings
from ..ai.base import ModelUnavailableError
from ..ai.manager import ProviderManager
from ..arabic import DIALECT_LABELS, detect_dialect, moderation_check
from ..search import search_memory

SYSTEM_PROMPT = """أنت مساعد ردود محترف لصفحة عربية على فيسبوك.
مهمتك: صياغة ردود مهذبة واحترافية على رسائل العملاء، بنفس لهجة الصفحة وأسلوبها.
قواعد صارمة:
- اكتب فقط نص الرد، دون مقدمة أو خاتمة خارجية.
- احترم لهجة المحادثة (استخدم اللهجة نفسها إن لم تكن فصحى).
- كن مختصرًا (٢-٤ جمل) ومفيدًا.
- لا تكذب ولا تختلق معلومات؛ إن لم تعرف، قل إنك ستراجع مع الفريق.
- لا تستخدم كلمات جارحة أو وعودًا تجارية مبالغًا فيها.
- إن كانت الرسالة إساءة أو احتيالًا، اكتب: "نعتذر، لا يمكننا الرد على هذه الرسالة"."""


@dataclass
class ResponderDeps:
    session: AsyncSession
    settings: Settings
    providers: ProviderManager
    org_id: str


def _build_user_prompt(
    messages: list[models.Message],
    style: dict,
    knowledge: list[str],
    memory: list[dict],
    instructions: str,
) -> str:
    lines: list[str] = []
    for m in messages[:20]:
        who = "العميل" if m.sender_type == "customer" else "الصفحة"
        lines.append(f"{who}: {m.text_raw or m.text_normalized}")
    convo_text = "\n".join(lines) or "(لا توجد رسائل)"
    kb = "\n".join(f"- {k}" for k in knowledge[:5]) or "(لا توجد معلومات)"
    mem = "\n".join(f"- {r['chunk_text'][:240]}" for r in memory[:4]) or "(لا توجد أمثلة)"
    return f"""المحادثة:
{convo_text}

أسلوب الصفحة: {json.dumps(style, ensure_ascii=False)}
معلومات نعرفها: {kb}
أمثلة من محادثات سابقة: {mem}
{("تعليمات إضافية: " + instructions) if instructions else ""}

اكتب الرد الآن:"""


def _validate_draft(draft: str, conv: models.Conversation) -> tuple[bool, str]:
    if not draft or len(draft) < 5:
        return False, "الرد فارغ أو قصير جدًا"
    if len(draft) > 6000:
        return False, "الرد طويل جدًا"
    check = moderation_check(draft)
    if any(f["severity"] == "critical" for f in check["flags"]):
        return False, "الرد يحتوي على محتوى مرفوض"
    target = conv.dialect_label
    if target not in ("unknown", "mixed", "arabizi"):
        draft_dialect = detect_dialect(draft)["label"]
        if draft_dialect not in ("unknown", "msa", target):
            return False, f"اللهجة غير متسقة (متوقع: {DIALECT_LABELS.get(target)})"
    return True, ""


async def _collect_knowledge(deps: ResponderDeps) -> list[str]:
    rows = await deps.session.execute(
        select(models.KnowledgeItem)
        .where(models.KnowledgeItem.org_id == deps.org_id)
        .order_by(models.KnowledgeItem.confidence.desc())
        .limit(8)
    )
    return [f"{k.topic}: {k.content}" for k in rows.scalars().all()]


async def _latest_style(deps: ResponderDeps, conv: models.Conversation) -> dict:
    row = (
        await deps.session.execute(
            select(models.AnalysisResult).where(
                models.AnalysisResult.conversation_id == conv.id,
                models.AnalysisResult.kind == "style",
            )
        )
    ).scalar_one_or_none()
    if row and row.payload:
        return row.payload
    return {"tone": "friendly", "emoji_use": 0.0, "greeting_pattern": "", "signoff_pattern": "", "avg_length": "medium", "summary": ""}


async def _retrieve_memory(deps: ResponderDeps, query: str) -> list[dict]:
    try:
        if not await deps.providers.embeddings_available():
            return []
        vec = (await deps.providers.embeddings().embed([query]))[0]
        return await search_memory(deps.session, deps.org_id, vec, limit=4, min_score=0.4)
    except Exception:
        return []


async def draft_response(
    deps: ResponderDeps,
    conv: models.Conversation,
    *,
    instructions: str = "",
    regenerate_of: models.AiResponse | None = None,
) -> models.AiResponse:
    """Generate a draft AI response; returns the stored AiResponse row.

    Raises ModelUnavailableError when no LLM is reachable — the caller
    surfaces that honestly (response marked failed with a clear message).
    """
    if regenerate_of is None:
        resp = models.AiResponse(
            org_id=deps.org_id,
            conversation_id=conv.id,
            status="pending",
            provider="none",
        )
        deps.session.add(resp)
        await deps.session.flush()
    else:
        resp = regenerate_of
        resp.status = "pending"

    provider = deps.providers.llm()
    if not await provider.available():
        resp.status = "failed"
        resp.provider = "none"
        resp.error = "النموذج الذكي غير متاح — شغّل Ollama (qwen2.5) من خادمك"
        await deps.session.commit()
        metrics.AI_INVOCATIONS.labels(provider="none", kind="response", status="unavailable").inc()
        raise ModelUnavailableError(resp.error)

    try:
        messages = list(
            (
                await deps.session.execute(
                    select(models.Message)
                    .where(models.Message.conversation_id == conv.id)
                    .order_by(models.Message.sequence)
                )
            ).scalars().all()
        )
        style = await _latest_style(deps, conv)
        knowledge = await _collect_knowledge(deps)
        query = " ".join(
            (m.text_normalized or m.text_raw)
            for m in messages[:8]
            if m.sender_type == "customer"
        )
        
        # Scrape store dynamically if query seems to be about products
        from ..store.scraper import search_store
        store_url = deps.settings.store_url if hasattr(deps.settings, "store_url") else ""
        if store_url and len(query) > 3:
            # We just use the query (or key nouns) to search the store
            # In a real setup, we'd extract the actual product entity
            scraped = await search_store(store_url, query[:50])
            for p in scraped:
                knowledge.insert(0, f"مخزون: {p.name} - السعر: {p.price}")
                
        memory = await _retrieve_memory(deps, query)
        started = time.monotonic()
        last_error = ""
        for attempt in range(2):
            res = await provider.complete(
                system=SYSTEM_PROMPT,
                user=_build_user_prompt(messages, style, knowledge, memory, instructions),
                temperature=0.4 if attempt == 0 else 0.7,
                max_tokens=1024,
                kind="response",
            )
            draft = res.text.strip()
            ok, reason = _validate_draft(draft, conv)
            if ok:
                resp.text = draft
                resp.provider = "ollama"
                resp.model = res.model
                resp.status = "pending_approval"
                resp.error = ""
                metrics.AI_LATENCY.labels(provider="ollama").observe(time.monotonic() - started)
                metrics.AI_INVOCATIONS.labels(provider="ollama", kind="response", status="ok").inc()
                await deps.session.commit()
                return resp
            last_error = reason
        resp.status = "failed"
        resp.error = f"فشل توليد رد صالح: {last_error}"
        metrics.AI_INVOCATIONS.labels(provider="ollama", kind="response", status="failed").inc()
        await deps.session.commit()
        return resp
    except ModelUnavailableError:
        resp.status = "failed"
        resp.provider = "none"
        resp.error = "النموذج الذكي غير متاح — شغّل Ollama (qwen2.5) من خادمك"
        await deps.session.commit()
        raise
    except Exception as exc:
        resp.status = "failed"
        resp.error = str(exc)[:500]
        await deps.session.commit()
        raise
