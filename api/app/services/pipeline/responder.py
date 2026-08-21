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
from ..page_personality import detect_governorate, calculate_shipping
from ..search import search_memory


def _build_system_prompt(page_style: dict, page_knowledge: list[dict]) -> str:
    """Build a system prompt that makes the AI talk exactly like the page."""
    tone = page_style.get("tone", "friendly")
    dialect = page_style.get("dialect", "egyptian")
    greeting = page_style.get("greeting_pattern", "")
    signoff = page_style.get("signoff_pattern", "")
    emoji_use = page_style.get("emoji_use", 0.0)
    avg_len = page_style.get("avg_length", "medium")
    vocabulary = page_style.get("vocabulary", [])
    sample_replies = page_style.get("sample_replies", [])

    # Build the page personality section
    personality_lines = [
        f"أنت مساعد ردود لصفحة على فيسبوك.",
        f"alk تكلم بأسلوب الصفحة بالظبط:",
        f"- النبرة: {tone}",
        f"- اللهجة: {dialect}",
    ]
    if greeting:
        personality_lines.append(f"- تبدأ بـ: \"{greeting}\"")
    if signoff:
        personality_lines.append(f"- تنهي بـ: \"{signoff}\"")
    if emoji_use > 0.2:
        personality_lines.append("- تستخدم إيموجي بشكل طبيعي")
    if avg_len == "short":
        personality_lines.append("- ردود قصيرة ومختصرة (جملة أو اتنين)")
    elif avg_len == "long":
        personality_lines.append("- ردود تفصيلية ومفصلة")
    else:
        personality_lines.append("- ردود متوسطة الطول (٢-٤ جمل)")

    if vocabulary:
        personality_lines.append(f"- كلمات مستخدمة كثير: {', '.join(vocabulary[:6])}")

    if sample_replies:
        personality_lines.append("\nأمثلة على أسلوب الصفحة:")
        for i, reply in enumerate(sample_replies[:3], 1):
            personality_lines.append(f"  {i}. {reply}")

    # Knowledge section
    knowledge_lines = []
    for item in page_knowledge[:8]:
        kind = item.get("kind", "")
        content = item.get("content", "")[:200]
        if kind == "product":
            knowledge_lines.append(f"- معلومات منتج: {content}")
        elif kind == "faq":
            knowledge_lines.append(f"- سياسة/سؤال شائع: {content}")

    personality_lines.append("\nقواعد صارمة:")
    personality_lines.append("- اكتب فقط نص الرد، دون مقدمة أو خاتمة.")
    personality_lines.append("- لا تكذب ولا تختلق معلومات؛ إن لم تعرف، قل ستراجع مع الفريق.")
    personality_lines.append("- لا تستخدم كلمات جارحة أو وعودًا مبالغًا فيها.")
    personality_lines.append("- إن كانت الرسالة إساءة أو احتيالاً، اكتب: نعتذر، لا يمكننا الرد على هذه الرسالة.")

    if knowledge_lines:
        personality_lines.append("\nمعلومات الصفحة:")
        personality_lines.extend(knowledge_lines)

    return "\n".join(personality_lines)


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
    governorate: str | None = None,
    shipping_info: dict | None = None,
) -> str:
    lines: list[str] = []
    for m in messages[:20]:
        who = "العميل" if m.sender_type == "customer" else "الصفحة"
        lines.append(f"{who}: {m.text_raw or m.text_normalized}")
    convo_text = "\n".join(lines) or "(لا توجد رسائل)"
    kb = "\n".join(f"- {k}" for k in knowledge[:5]) or ""
    mem = "\n".join(f"- {r['chunk_text'][:240]}" for r in memory[:4]) or ""

    prompt_parts = [f"المحادثة:\n{convo_text}"]

    if kb:
        prompt_parts.append(f"\nمعلومات نعرفها:\n{kb}")
    if mem:
        prompt_parts.append(f"\nأمثلة من محادثات سابقة:\n{mem}")
    if governorate:
        prompt_parts.append(f"\nالعميل من: {governorate}")
    if shipping_info:
        prompt_parts.append(f"\nمعلومات الشحن: {shipping_info.get('message', '')}")
    if instructions:
        prompt_parts.append(f"\nتعليمات إضافية:\n{instructions}")

    prompt_parts.append("\nاكتب الرد الآن:")
    return "\n".join(prompt_parts)


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


async def _collect_knowledge(deps: ResponderDeps, page: models.PageConnection | None) -> list[str]:
    """Collect knowledge from both the org-level KB and the per-page KB."""
    items: list[str] = []

    # Per-page knowledge (from page personality)
    if page and page.knowledge_base:
        for k in page.knowledge_base[:8]:
            content = k.get("content", "")[:200]
            if content:
                items.append(content)

    # Org-level knowledge
    rows = await deps.session.execute(
        select(models.KnowledgeItem)
        .where(models.KnowledgeItem.org_id == deps.org_id)
        .order_by(models.KnowledgeItem.confidence.desc())
        .limit(8)
    )
    for k in rows.scalars().all():
        items.append(f"{k.topic}: {k.content}")

    return items


async def _latest_style(deps: ResponderDeps, conv: models.Conversation, page: models.PageConnection | None) -> dict:
    """Get style from per-page profile (preferred) or per-conversation analysis."""
    # Prefer per-page style profile (built from ALL page conversations)
    if page and page.style_profile and page.style_profile.get("summary", "") != "لم يتم بناء الأسلوب بعد (لا توجد ردود كافية)":
        return page.style_profile

    # Fallback to per-conversation analysis
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
    """Generate a draft AI response; returns the stored AiResponse row."""
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
        resp.error = "النموذج الذكي غير متاح — تأكد من ضبط GEMINI_API_KEY أو OPENAI_API_KEY"
        await deps.session.commit()
        metrics.AI_INVOCATIONS.labels(provider="none", kind="response", status="unavailable").inc()
        raise ModelUnavailableError(resp.error)

    try:
        # Load page connection for per-page personality
        page = None
        if conv.page_id:
            page = await deps.session.get(models.PageConnection, conv.page_id)

        messages = list(
            (
                await deps.session.execute(
                    select(models.Message)
                    .where(models.Message.conversation_id == conv.id)
                    .order_by(models.Message.sequence)
                )
            ).scalars().all()
        )
        style = await _latest_style(deps, conv, page)
        knowledge = await _collect_knowledge(deps, page)
        query = " ".join(
            (m.text_normalized or m.text_raw)
            for m in messages[:8]
            if m.sender_type == "customer"
        )

        # Governorate detection from customer messages
        governorate = None
        for m in messages:
            if m.sender_type == "customer":
                governorate = detect_governorate(m.text_raw or m.text_normalized or "")
                if governorate:
                    break

        # Shipping calculation
        shipping_info = None
        if governorate:
            # Try to extract cart total from messages
            cart_total = 0.0
            import re
            for m in messages:
                if m.sender_type == "customer":
                    price_match = re.search(r"(\d+(?:[.,]\d+)?)", m.text_raw or "")
                    if price_match:
                        try:
                            cart_total = float(price_match.group(1).replace(",", "."))
                        except ValueError:
                            pass
            shipping_info = calculate_shipping(deps.settings, governorate, cart_total)

        # Scrape store dynamically for product info
        from ..store.scraper import search_store
        store_url = deps.settings.store_url if hasattr(deps.settings, "store_url") else ""
        if store_url and len(query) > 3:
            try:
                scraped = await search_store(store_url, query[:50])
                for p in scraped:
                    knowledge.insert(0, f"{p.name} — السعر: {p.price or 'غير محدد'}، الشحن: {p.shipping_price or 'مجاني'}، الحالة: {'متوفر' if p.in_stock else 'نفذ'}")
            except Exception:
                pass

        memory = await _retrieve_memory(deps, query)

        # Build prompts with per-page personality
        system_prompt = _build_system_prompt(style, page.knowledge_base if page else [])
        user_prompt = _build_user_prompt(messages, style, knowledge, memory, instructions, governorate, shipping_info)

        started = time.monotonic()
        last_error = ""
        for attempt in range(2):
            res = await provider.complete(
                system=system_prompt,
                user=user_prompt,
                temperature=0.4 if attempt == 0 else 0.7,
                max_tokens=1024,
                kind="response",
            )
            draft = res.text.strip()
            ok, reason = _validate_draft(draft, conv)
            if ok:
                resp.text = draft
                resp.provider = provider.name
                resp.model = res.model
                resp.status = "pending_approval"
                resp.error = ""
                metrics.AI_LATENCY.labels(provider=provider.name).observe(time.monotonic() - started)
                metrics.AI_INVOCATIONS.labels(provider=provider.name, kind="response", status="ok").inc()
                await deps.session.commit()
                return resp
            last_error = reason
        resp.status = "failed"
        resp.error = f"فشل توليد رد صالح: {last_error}"
        metrics.AI_INVOCATIONS.labels(provider=provider.name, kind="response", status="failed").inc()
        await deps.session.commit()
        return resp
    except ModelUnavailableError:
        resp.status = "failed"
        resp.provider = "none"
        resp.error = "النموذج الذكي غير متاح — تأكد من ضبط GEMINI_API_KEY أو OPENAI_API_KEY"
        await deps.session.commit()
        raise
    except Exception as exc:
        resp.status = "failed"
        resp.error = str(exc)[:500]
        await deps.session.commit()
        raise
