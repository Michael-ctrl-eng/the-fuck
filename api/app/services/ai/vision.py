from __future__ import annotations

import base64
import httpx
import structlog
from pydantic import BaseModel
from typing import Any

from ...config import Settings
from .ollama import OllamaProvider

log = structlog.get_logger("raqib.ai.vision")

VISION_PROMPT = """أنت مساعد متخصص في التجارة الإلكترونية.
حدد المنتج الموجود في الصورة. صِف التفاصيل الأساسية التي ستساعد في البحث عنه في المتجر.
أعد الناتج بتنسيق JSON فقط يحتوي على المفاتيح التالية:
{"product_name": "اسم المنتج بشكل عام", "category": "فئة المنتج", "color": "لون المنتج إذا كان واضحا", "details": "تفاصيل إضافية"}"""

class ProductImageResult(BaseModel):
    product_name: str
    category: str
    color: str = ""
    details: str = ""

async def download_image_as_base64(url: str, timeout: float = 10.0) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return base64.b64encode(resp.content).decode("utf-8")
    except Exception as exc:
        log.warning("vision.download_failed", url=url, error=str(exc))
    return None

async def analyze_product_image(settings: Settings, image_url: str) -> ProductImageResult | None:
    """Analyze a product image using Ollama vision capabilities (e.g., llava or qwen-vl)."""
    b64_image = await download_image_as_base64(image_url)
    if not b64_image:
        return None
        
    provider = OllamaProvider(settings)
    if not await provider.available():
        return None
        
    try:
        res = await provider.complete(
            system=VISION_PROMPT,
            user="قم بتحليل هذه الصورة.",
            images=[b64_image],
            json_mode=True,
            temperature=0.1,
            kind="vision"
        )
        
        # Parse JSON
        import json
        import re
        text = res.text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        
        # Try to extract JSON if it's mixed with text
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            text = m.group(0)
            
        data = json.loads(text)
        
        return ProductImageResult(
            product_name=data.get("product_name", ""),
            category=data.get("category", ""),
            color=data.get("color", ""),
            details=data.get("details", ""),
        )
    except Exception as exc:
        log.error("vision.analyze_failed", error=str(exc))
        return None
