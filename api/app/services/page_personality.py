"""Per-page personality — auto-builds style profile + knowledge base from conversation history.

Each page gets its own "brain": how it talks, what it sells, shipping rules,
FAQs. This is what makes the AI sound exactly like the page, not generic.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..config import Settings
from .arabic import detect_dialect, normalize_arabic

log = structlog.get_logger("raqib.page_personality")

# Egyptian governorate keywords for detection
GOVERNORATES = {
    "القاهرة": "cairo", "قاها": "cairo", "مصر الجديدة": "cairo", "مدينة نصر": "cairo",
    "التجمع": "cairo", "شبرا": "cairo", "العبور": "cairo", "حلوان": "cairo",
    "الجيزة": "giza", "جيزا": "giza", "الهرم": "giza", "الدقي": "giza", "مgypt": "giza",
    "الإسكندرية": "alexandria", "اسكندرية": "alexandria", "كفر عبده": "alexandria",
    "البحيرة": "beheira", "دمنهور": "beheira", "كفرالدوار": "beheira",
    "الشرقية": "sharqia", "الزقازيق": "sharqia", "بلبيس": "sharqia",
    "الغربية": "gharbia", "طنطا": "gharbia", "المحلة": "gharbia",
    "المنوفية": "monufia", "شبين الكوم": "monufia",
    "القليوبية": "qalyubia", "بنها": "qalyubia", "قليوب": "qalyubia",
    "كفر الشيخ": "kafr-el-sheikh", "دمنهور": "kafr-el-sheikh",
    "دمياط": "damietta", "فارسكور": "damietta",
    "بورسعيد": "port-said",
    "الإسماعيلية": "ismailia",
    "السويس": "suez",
    "بني سويف": "beni-suef", "بني suef": "beni-suef",
    "الفيوم": "fayoum", "فيوم": "fayoum",
    "المنيا": "minya", "ملوي": "minya",
    "أسيوط": "assiut", "اسيوط": "assiut",
    "سوهاج": "sohag",
    "قنا": "qena",
    "الأقصر": "luxor", "اقصر": "luxor",
    "أسوان": "aswan", "اسوان": "aswan",
    "البحر الأحمر": "red-sea", "الغردقة": "red-sea", "مرسى علم": "red-sea",
    "الوادي الجديد": "new-valley", "ال�arge": "new-valley",
    "مطروح": "matrouh", "الማترُوح": "matrouh",
    "شمال سيناء": "north-sinai", "العريش": "north-sinai",
    "جنوب سيناء": "south-sinai", "شرم الشيخ": "south-sinai", "دهب": "south-sinai",
}


def detect_governorate(text: str) -> str | None:
    """Detect Egyptian governorate from text (phone number area, address, mention)."""
    if not text:
        return None
    normalized = normalize_arabic(text, strong=True).lower()
    # Check all governorate keywords
    for ar, en in GOVERNORATES.items():
        if ar in normalized or en in normalized:
            return en
    # Phone number area code detection (Egyptian mobile prefixes)
    phone_match = re.search(r"(?:\+20|0020|0)?(1[0125]\d{8})", text)
    if phone_match:
        prefix = phone_match.group(1)[:2]
        # All Egyptian mobile prefixes are nationwide (no area distinction)
        # But 012 = older Egypt-wide, 010/011/015 = newer
        # We can't distinguish governorate from mobile prefix alone
        pass
    return None


async def build_page_style(
    session: AsyncSession,
    page: models.PageConnection,
    settings: Settings,
) -> dict:
    """Analyze all page replies to build a style profile.

    Returns a dict with: tone, greeting, signoff, emoji_use, avg_length,
    vocabulary, dialect, summary.
    """
    # Get all conversations for this page
    conv_rows = await session.execute(
        select(models.Conversation.id).where(models.Conversation.page_id == page.id)
    )
    conv_ids = [r[0] for r in conv_rows.all()]
    if not conv_ids:
        return _empty_style()

    # Get all page messages across conversations
    msg_rows = await session.execute(
        select(models.Message)
        .where(
            models.Message.conversation_id.in_(conv_ids),
            models.Message.sender_type == "page",
        )
        .order_by(models.Message.created_at)
    )
    page_msgs = [m for m in msg_rows.scalars().all() if (m.text_normalized or m.text_raw or "").strip()]
    if len(page_msgs) < settings.style_build_min_messages:
        return _empty_style()

    joined = " ".join(m.text_normalized or m.text_raw or "" for m in page_msgs)

    # Tone detection
    emoji_count = sum(1 for ch in joined if ord(ch) > 0x1F000)
    emoji_ratio = round(emoji_count / max(1, len(page_msgs)), 2)
    greetings = ["السلام عليكم", "مرحبا", "أهلا", "صباح", "مساء", "أهلاً", "اهلا", "مرحبا بيك"]
    signoffs = ["شكرا", "مع التحية", "دمتم", "في الخدمة", "حياكم", "بانتظارك", "ربنا يخليك", "اللهم صلّى على محمد"]
    greeting = next((g for g in greetings if g in joined), "")
    signoff = next((s for s in signoffs if s in joined), "")
    avg_len = sum(len(m.text_normalized or m.text_raw or "") for m in page_msgs) / max(1, len(page_msgs))
    avg = "short" if avg_len < 60 else ("medium" if avg_len < 160 else "long")

    # Dialect
    dialect = detect_dialect(joined[:3000])
    tone = "formal" if dialect["label"] == "msa" else ("friendly" if emoji_ratio > 0.2 or greeting else "casual")

    # Extract common vocabulary (product names, prices, keywords)
    vocabulary = _extract_vocabulary(page_msgs)

    # Extract pricing patterns
    pricing = _extract_pricing_patterns(page_msgs)

    # Extract shipping mentions
    shipping_rules = _extract_shipping_rules(page_msgs)

    style = {
        "tone": tone,
        "dialect": dialect["label"],
        "greeting_pattern": greeting,
        "signoff_pattern": signoff,
        "emoji_use": emoji_ratio,
        "avg_length": avg,
        "avg_length_chars": round(avg_len),
        "vocabulary": vocabulary[:10],
        "pricing_patterns": pricing[:5],
        "shipping_rules": shipping_rules[:3],
        "sample_replies": [_sample_reply(m) for m in page_msgs[-5:]],
        "summary": f"{len(page_msgs)} رد من الصفحة، نبرة {tone}، لهجة {dialect['label']}",
    }
    return style


async def build_page_knowledge(
    session: AsyncSession,
    page: models.PageConnection,
    settings: Settings,
) -> list[dict]:
    """Extract knowledge items from page conversations: products, FAQ, policies."""
    conv_rows = await session.execute(
        select(models.Conversation.id).where(models.Conversation.page_id == page.id)
    )
    conv_ids = [r[0] for r in conv_rows.all()]
    if not conv_ids:
        return []

    msg_rows = await session.execute(
        select(models.Message)
        .where(
            models.Message.conversation_id.in_(conv_ids),
            models.Message.sender_type == "page",
        )
        .order_by(models.Message.created_at)
    )
    page_msgs = [m for m in msg_rows.scalars().all() if (m.text_normalized or m.text_raw or "").strip()]

    items: list[dict] = []
    seen: set[str] = set()

    for m in page_msgs:
        text = m.text_normalized or m.text_raw or ""
        if not text or len(text) < 20:
            continue

        # Product info (price + availability)
        has_price = bool(re.search(r"(\d+(?:[.,]\d+)?)\s*(ريال|جنيه|درهم|دينار|دولار|ليرة|يورو|جنيها)", text))
        has_availability = any(k in text for k in ("متوفر", "في المخزون", "موجود", " sẵn", "نفدت", "نفذ", "خ_int", "لا يوجد", "مش متوفر"))

        if has_price:
            dedup_key = text[:80]
            if dedup_key not in seen:
                seen.add(dedup_key)
                items.append({
                    "kind": "product",
                    "topic": "pricing",
                    "content": text[:500],
                    "confidence": 0.7,
                })

        # FAQ / policy
        has_faq = any(k in text for k in ("الخدمة", "الضمان", "سياسة", "الإرجاع", "التوصيل", "الشحن", "الدفع", "التقسيط", "الكفاله"))
        if has_faq and len(text) > 40:
            dedup_key = text[:80]
            if dedup_key not in seen:
                seen.add(dedup_key)
                items.append({
                    "kind": "faq",
                    "topic": "policy",
                    "content": text[:500],
                    "confidence": 0.6,
                })

        # Greeting / welcome pattern
        if any(k in text for k in ("أهلا بيك", "مرحبا بيك", "اهلا فيك", "بيanned welcome")):
            dedup_key = "greeting"
            if dedup_key not in seen:
                seen.add(dedup_key)
                items.append({
                    "kind": "style",
                    "topic": "greeting",
                    "content": text[:300],
                    "confidence": 0.8,
                })

        if len(items) >= settings.knowledge_max_items:
            break

    return items


async def build_and_persist_personality(
    session: AsyncSession,
    page: models.PageConnection,
    settings: Settings,
) -> None:
    """Build style + knowledge and save to PageConnection columns."""
    style = await build_page_style(session, page, settings)
    knowledge = await build_page_knowledge(session, page, settings)
    page.style_profile = style
    page.knowledge_base = knowledge
    page.knowledge_built_at = datetime.now(timezone.utc)
    await session.commit()
    log.info(
        "page.personality_built",
        page_id=page.id,
        style_keys=len(style),
        knowledge_items=len(knowledge),
    )


def calculate_shipping(
    settings: Settings,
    governorate: str | None,
    cart_total: float = 0.0,
) -> dict:
    """Calculate shipping cost based on governorate + cart total."""
    if not governorate:
        return {
            "cost": settings.default_shipping_cost,
            "free": False,
            "governorate": None,
            "message": f"شحن بسعر {settings.default_shipping_cost} جنيه",
        }

    zone_config = settings.shipping_zones.get(governorate, None)
    if zone_config is None:
        return {
            "cost": settings.default_shipping_cost,
            "free": False,
            "governorate": governorate,
            "message": f"شحن بسعر {settings.default_shipping_cost} جنيه",
        }

    cost = zone_config["cost"]
    threshold = zone_config["free_threshold"]
    is_free = cart_total >= threshold

    if is_free:
        return {
            "cost": 0,
            "free": True,
            "governorate": governorate,
            "message": f"شحن مجاني! (للطلبات فوق {threshold} جنيه)",
        }

    return {
        "cost": cost,
        "free": False,
        "governorate": governorate,
        "message": f"شحن {cost} جنيه إلى {governorate}",
        "free_threshold": threshold,
        "remaining": threshold - cart_total,
    }


def _sample_reply(msg: models.Message) -> str:
    text = msg.text_normalized or msg.text_raw or ""
    return text[:120] + ("..." if len(text) > 120 else "")


def _extract_vocabulary(msgs: list[models.Message]) -> list[str]:
    """Extract commonly used product/brand keywords from page messages."""
    word_freq: dict[str, int] = {}
    for m in msgs:
        text = m.text_normalized or m.text_raw or ""
        # Extract meaningful words (3+ chars, Arabic)
        words = re.findall(r"[\u0600-\u06FF]{3,}", text)
        for w in words:
            w = normalize_arabic(w, strong=True)
            if len(w) >= 3:
                word_freq[w] = word_freq.get(w, 0) + 1
    # Sort by frequency, return top keywords
    return [w for w, c in sorted(word_freq.items(), key=lambda x: -x[1])[:10]]


def _extract_pricing_patterns(msgs: list[models.Message]) -> list[str]:
    """Extract pricing patterns from page messages."""
    patterns: list[str] = []
    seen: set[str] = set()
    for m in msgs:
        text = m.text_normalized or m.text_raw or ""
        for match in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(ريال|جنيه|درهم|دينار|دولار|ليرة|يورو|جنيها)", text):
            price_str = match.group(0)
            if price_str not in seen:
                seen.add(price_str)
                patterns.append(price_str)
            if len(patterns) >= 5:
                return patterns
    return patterns


def _extract_shipping_rules(msgs: list[models.Message]) -> list[str]:
    """Extract shipping-related mentions from page messages."""
    rules: list[str] = []
    seen: set[str] = set()
    for m in msgs:
        text = m.text_normalized or m.text_raw or ""
        if any(k in text for k in ("شحن", "توصيل", "التوصيل", "التوصيل المجاني", "مجانا")):
            snippet = text[:200]
            if snippet not in seen:
                seen.add(snippet)
                rules.append(snippet)
            if len(rules) >= 3:
                return rules
    return rules


def _empty_style() -> dict:
    return {
        "tone": "friendly",
        "dialect": "egyptian",
        "greeting_pattern": "",
        "signoff_pattern": "",
        "emoji_use": 0.0,
        "avg_length": "medium",
        "avg_length_chars": 80,
        "vocabulary": [],
        "pricing_patterns": [],
        "shipping_rules": [],
        "sample_replies": [],
        "summary": "لم يتم بناء الأسلوب بعد (لا توجد ردود كافية)",
    }
