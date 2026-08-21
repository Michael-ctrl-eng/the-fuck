"""Per-page personality builder — extracts speaking style from conversation history."""

import re
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.tenant import Tenant

logger = structlog.get_logger("raqib.style_builder")

# Egyptian governorate keywords
GOVERNORATES = {
    "القاهرة": "cairo", "قاها": "cairo", "مصر الجديدة": "cairo", "مدينة نصر": "cairo",
    "التجمع": "cairo", "شبرا": "cairo", "حلوان": "cairo",
    "الجيزة": "giza", "جيزا": "giza", "الهرم": "giza", "الدقي": "giza",
    "الإسكندرية": "alexandria", "اسكندرية": "alexandria", "كفر عبده": "alexandria",
    "البحيرة": "beheira", "دمنهور": "beheira",
    "الشرقية": "sharqia", "الزقازيق": "sharqia",
    "الغربية": "gharbia", "طنطا": "gharbia", "المحلة": "gharbia",
    "المنوفية": "monufia", "شبين الكوم": "monufia",
    "القليوبية": "qalyubia", "بنها": "qalyubia",
    "كفر الشيخ": "kafr-el-sheikh",
    "دمياط": "damietta",
    "بورسعيد": "port-said",
    "الإسماعيلية": "ismailia",
    "السويس": "suez",
    "بني سويف": "beni-suef",
    "الفيوم": "fayoum",
    "المنيا": "minya",
    "أسيوط": "assiut",
    "سوهاج": "sohag",
    "قنا": "qena",
    "الأقصر": "luxor",
    "أسوان": "aswan",
    "البحر الأحمر": "red-sea", "الغردقة": "red-sea",
    "الوادي الجديد": "new-valley",
    "مطروح": "matrouh",
    "شمال سيناء": "north-sinai",
    "جنوب سيناء": "south-sinai", "شرم الشيخ": "south-sinai",
}


def detect_governorate(text: str) -> str | None:
    """Detect Egyptian governorate from text."""
    if not text:
        return None
    normalized = text.lower()
    for ar, en in GOVERNORATES.items():
        if ar in normalized or en in normalized:
            return en
    return None


async def build_style_profile(
    db: AsyncSession,
    tenant: Tenant,
) -> dict:
    """Analyze all page replies to build a style profile."""
    # Get all conversations for this tenant
    conv_rows = await db.execute(
        select(Conversation.id).where(Conversation.tenant_id == tenant.id)
    )
    conv_ids = [r[0] for r in conv_rows.all()]
    if not conv_ids:
        return _empty_style()

    # Get all assistant messages
    msg_rows = await db.execute(
        select(Message)
        .where(
            Message.conversation_id.in_(conv_ids),
            Message.role == "assistant",
        )
        .order_by(Message.created_at)
    )
    page_msgs = [m for m in msg_rows.scalars().all() if m.content and m.content.strip()]
    if len(page_msgs) < 6:
        return _empty_style()

    joined = " ".join(m.content for m in page_msgs)

    # Tone detection
    emoji_count = sum(1 for ch in joined if ord(ch) > 0x1F000)
    emoji_ratio = round(emoji_count / max(1, len(page_msgs)), 2)

    # Greeting patterns (Egyptian)
    greetings = ["أهلاً", "أهلا", "مرحبا", "السلام عليكم", "صباح", "مساء", "اهلا بيك", "مرحبا بيك"]
    signoffs = ["شكراً", "شكرا", "ربنا يخليك", "اللهم صلّى على محمد", "في الخدمة", "بانتظارك", "يلا باي"]
    greeting = next((g for g in greetings if g in joined), "")
    signoff = next((s for s in signoffs if s in joined), "")

    avg_len = sum(len(m.content) for m in page_msgs) / max(1, len(page_msgs))
    avg = "short" if avg_len < 60 else ("medium" if avg_len < 160 else "long")

    # Vocabulary
    vocabulary = _extract_vocabulary(page_msgs)

    # Sample replies
    sample_replies = [m.content[:120] for m in page_msgs[-5:]]

    # Detect tone
    formal_words = sum(1 for w in ["حضرتك", "سيدتي", "سيدي", "تفضل", "_bucket"] if w in joined)
    casual_words = sum(1 for w in ["ya3ni", "keda", "yalla", "tayeb", "3ayez"] if w in joined)
    tone = "formal" if formal_words > casual_words else ("friendly" if emoji_ratio > 0.2 or greeting else "casual")

    return {
        "tone": tone,
        "greeting_pattern": greeting,
        "signoff_pattern": signoff,
        "emoji_use": emoji_ratio,
        "avg_length": avg,
        "avg_length_chars": round(avg_len),
        "vocabulary": vocabulary[:10],
        "sample_replies": sample_replies,
        "summary": f"{len(page_msgs)} رد من الصفحة، نبرة {tone}",
    }


async def build_knowledge_base(
    db: AsyncSession,
    tenant: Tenant,
) -> list[dict]:
    """Extract knowledge items from page conversations."""
    conv_rows = await db.execute(
        select(Conversation.id).where(Conversation.tenant_id == tenant.id)
    )
    conv_ids = [r[0] for r in conv_rows.all()]
    if not conv_ids:
        return []

    msg_rows = await db.execute(
        select(Message)
        .where(
            Message.conversation_id.in_(conv_ids),
            Message.role == "assistant",
        )
        .order_by(Message.created_at)
    )
    page_msgs = [m for m in msg_rows.scalars().all() if m.content and len(m.content) > 20]

    items: list[dict] = []
    seen: set[str] = set()

    for m in page_msgs:
        text = m.content
        # Product info
        has_price = bool(re.search(r"(\d+(?:[.,]\d+)?)\s*(جنيه|ج\.م|EGP)", text))
        has_availability = any(k in text for k in ("متوفر", "موجود", "نفدت", "نفذ", "مش متوفر", "AVAILABLE"))

        if has_price:
            dedup = text[:80]
            if dedup not in seen:
                seen.add(dedup)
                items.append({"kind": "product", "topic": "pricing", "content": text[:500], "confidence": 0.7})

        # FAQ
        has_faq = any(k in text for k in ("الضمان", "سياسة", "الإرجاع", "التوصيل", "الشحن", "الدفع"))
        if has_faq and len(text) > 40:
            dedup = text[:80]
            if dedup not in seen:
                seen.add(dedup)
                items.append({"kind": "faq", "topic": "policy", "content": text[:500], "confidence": 0.6})

        if len(items) >= 20:
            break

    return items


async def build_and_persist_personality(
    db: AsyncSession,
    tenant: Tenant,
) -> None:
    """Build style + knowledge and save to tenant."""
    style = await build_style_profile(db, tenant)
    knowledge = await build_knowledge_base(db, tenant)
    tenant.style_profile = style
    tenant.knowledge_base = knowledge
    tenant.knowledge_built_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("personality_built", tenant_id=tenant.id, style_keys=len(style), knowledge_items=len(knowledge))


def _extract_vocabulary(msgs: list[Message]) -> list[str]:
    """Extract commonly used keywords from assistant messages."""
    word_freq: dict[str, int] = {}
    for m in msgs:
        words = re.findall(r'[\u0600-\u06FF]{3,}', m.content)
        for w in words:
            w = w.lower()
            if len(w) >= 3:
                word_freq[w] = word_freq.get(w, 0) + 1
    return [w for w, c in sorted(word_freq.items(), key=lambda x: -x[1])[:10]]


def _empty_style() -> dict:
    return {
        "tone": "friendly",
        "greeting_pattern": "",
        "signoff_pattern": "",
        "emoji_use": 0.0,
        "avg_length": "medium",
        "avg_length_chars": 80,
        "vocabulary": [],
        "sample_replies": [],
        "summary": "لم يتم بناء الأسلوب بعد",
    }
