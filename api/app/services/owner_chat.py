from __future__ import annotations

import hashlib
import json
import re

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from .. import models
from ..config import Settings, get_settings
from .ai.ollama import OllamaProvider
from .pipeline.outputs import _upsert_knowledge

log = structlog.get_logger("raqib.owner_chat")

INSTRUCTION_SYSTEM_PROMPT = """أنت مدير متجر إلكتروني الذكي. المالك يعطيك تعليمات بالعربية.
يجب عليك فهم التعليمات وإرجاع JSON يحتوي على:
1. "action": نوع الإجراء (update_stock, update_price, add_rule)
2. "details": تفاصيل الإجراء (المنتج، الكمية، الخ)
3. "response_ar": ردك على المالك بالعربية لتأكيد الفهم

مثال: "بص من البرفان لوفير ناقص منه 3 بس"
{"action": "update_stock", "details": {"product": "لوفير", "quantity_deduct": 3}, "response_ar": "حاضر، تم تقليل مخزون عطر لوفير بـ 3"}
"""


def _extract_json(text: str) -> dict | None:
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


async def parse_owner_instruction(
    db: AsyncSession, org: models.Organization, text: str, image_url: str = ""
) -> tuple[str, dict]:
    settings: Settings = get_settings()
    provider = OllamaProvider(settings)

    if not await provider.available():
        # Store the raw instruction so it is never lost, then answer honestly.
        await _upsert_knowledge(
            db,
            org_id=org.id,
            topic="owner_instruction",
            content=f"تعليمات من المالك: {text}",
            kind="owner_rule",
            source_id="owner_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
            confidence=0.8,
        )
        return "المعذرة، المحرك الذكي غير متصل حالياً لحفظ التعليمات المعقدة.", {}

    try:
        user_prompt = text
        if image_url:
            user_prompt += f"\n(مرفقة صورة: {image_url})"
        res = await provider.complete(
            system=INSTRUCTION_SYSTEM_PROMPT,
            user=user_prompt,
            json_mode=True,
            temperature=0.1,
            kind="owner_instruction",
        )

        data = _extract_json(res.text) or {}
        action = data.get("action", "add_rule")
        response_ar = data.get("response_ar", "تم تحديث المعلومات.")

        # Persist as a knowledge rule so the responder can use it
        await _upsert_knowledge(
            db,
            org_id=org.id,
            topic="owner_instruction",
            content=f"تعليمات من المالك: {text}",
            kind="owner_rule",
            source_id="owner_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
            confidence=0.9,
        )

        return response_ar, {"action": action, "details": data.get("details", {})}
    except Exception as exc:
        log.error("owner_chat.parse_failed", error=str(exc))
        return "حدث خطأ أثناء فهم التعليمات. يرجى المحاولة مرة أخرى.", {}