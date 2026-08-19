from __future__ import annotations

import asyncio
import structlog
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ... import models
from ...config import Settings
from ..ai.manager import ProviderManager
from ..ai.vision import analyze_product_image
from ..meta_client import get_meta_client
from ..store.scraper import StoreProduct, search_store
from .responder import ResponderDeps, draft_response

log = structlog.get_logger("raqib.auto_reply")

# Concurrency cap: up to 50 auto-replies in flight across all pages.
_auto_reply_semaphore = asyncio.Semaphore(50)
_vision_semaphore = asyncio.Semaphore(5)

MAX_PRODUCTS_IN_TEMPLATE = 8


async def _latest_unanswered(session: AsyncSession, conv: models.Conversation) -> models.Message | None:
    """The newest customer message that has no page reply after it."""
    rows = (
        (
            await session.execute(
                select(models.Message)
                .where(models.Message.conversation_id == conv.id)
                .order_by(models.Message.sequence.desc())
                .limit(40)
            )
        )
        .scalars()
        .all()
    )
    for i, msg in enumerate(rows):
        if msg.sender_type != "customer":
            continue
        # rows are newest-first: any page message newer than this one means it was answered
        if any(m.sender_type == "page" for m in rows[:i]):
            return None
        return msg
    return None


async def _analyze_media(
    settings: Settings, media_urls: list[str]
) -> list[dict[str, Any]]:
    """Vision analysis of the images in the incoming message (bounded concurrency)."""
    if not media_urls:
        return []
    results: list[dict[str, Any]] = []
    async def _one(url: str) -> None:
        async with _vision_semaphore:
            try:
                res = await analyze_product_image(settings, url)
                if res and res.product_name:
                    results.append(res.model_dump())
            except Exception as exc:
                log.warning("auto_reply.vision_failed", url=url[:120], error=str(exc))
    await asyncio.gather(*(_one(u) for u in media_urls[:5]))
    return results


async def _search_products(
    settings: Settings, query: str
) -> list[StoreProduct]:
    """Search the owner's store for a product; returns availability/price/shipping."""
    if not settings.store_url:
        return []
    query = query.strip().strip("؟?")
    if len(query) < 3:
        return []
    try:
        return await search_store(settings.store_url, query[:60])
    except Exception as exc:
        log.warning("auto_reply.store_search_failed", error=str(exc))
        return []


def _product_grounding(products: list[StoreProduct], vision_products: list[dict[str, Any]]) -> str:
    """Build the grounded product facts passed to the responder prompt."""
    lines: list[str] = []
    for p in products:
        state = "متوفر" if p.in_stock else "نفذ من المخزون"
        price = f"{p.price:g}" if p.price else "غير محدد"
        shipping = f"{p.shipping_price:g}" if p.shipping_price else "مجاني"
        lines.append(
            f"- {p.name}: السعر {price}، الشحن {shipping}، الحالة: {state}، رابط: {p.url}"
        )
    for v in vision_products[:2]:
        details = " ".join(x for x in (v.get("product_name"), v.get("category"), v.get("color"), v.get("details")) if x)
        lines.append(f"- المنتج في الصورة: {details}")
    return "\n".join(lines) or ""


async def handle_auto_reply(
    session: AsyncSession,
    settings: Settings,
    providers: ProviderManager,
    conv: models.Conversation,
    page: models.PageConnection,
    *,
    trigger_message_id: str | None = None,
) -> None:
    async with _auto_reply_semaphore:
        if not page.is_active or not page.access_token_enc:
            return
        if not conv or conv.org_id != page.org_id:
            return

        from ...security import TokenCipher

        cipher = TokenCipher.from_secret(settings.effective_secret_key)
        page_token = cipher.decrypt(page.access_token_enc)
        if not page_token:
            return

        try:
            trigger: models.Message | None = None
            if trigger_message_id:
                trigger = await session.get(models.Message, trigger_message_id)
            if trigger is None or trigger.sender_type != "customer":
                trigger = await _latest_unanswered(session, conv)
            if trigger is None:
                return

            # 1) Vision: analyze product images sent by the customer
            vision_products = await _analyze_media(settings, trigger.media_urls or [])

            # 2) Store search: product query from the message + vision result
            query = (trigger.text_normalized or trigger.text_raw or "").strip()
            vision_name = (vision_products[0].get("product_name") if vision_products else "") or ""
            products = await _search_products(settings, f"{query} {vision_name}".strip())

            # 3) Draft a warm, grounded reply
            deps = ResponderDeps(session=session, settings=settings, providers=providers, org_id=conv.org_id)
            grounding = _product_grounding(products, vision_products)
            instructions = ""
            if grounding:
                instructions = (
                    "معلومات من متجرنا (لا تختلق غيرها):\n"
                    + grounding
                    + "\nأجب العميل بحرارة ووضوح، واذكر السعر والشحن والتوفر إن وُجدت."
                )
            elif vision_products:
                instructions = (
                    "رأى العميل منتجًا في صورة. تأكد من توافره معه واسأله عما يحتاج معرفته عن السعر أو الشحن."
                )

            resp = await draft_response(deps, conv, instructions=instructions)
            if resp.status != "pending_approval":
                log.warning("auto_reply.draft_failed", conv_id=conv.id, error=resp.error)
                return

            meta_client = get_meta_client(settings)

            # 4) Send the text reply
            await meta_client.send_message(
                page_token, conv.source_conversation_id, resp.edited_text or resp.text
            )
            resp.status = "sent"
            resp.sent_to_meta_at = models.utcnow()
            await session.commit()

            # 5) Send a product card (generic template) when the store matched
            if products:
                customer_id = next(
                    (pid for pid in conv.participants if pid != page.meta_user_id), None
                )
                if customer_id:
                    elements = []
                    for p in products[:MAX_PRODUCTS_IN_TEMPLATE]:
                        elements.append(
                            {
                                "title": p.name,
                                "subtitle": (
                                    f"{p.price:g} ريال — شحن {p.shipping_price:g}" if p.price
                                    else "السعر متوفر عند الطلب"
                                ) + (" — متوفر" if p.in_stock else " — نفذ"),
                                "image_url": p.image_url or "",
                                "buttons": [
                                    {
                                        "type": "web_url",
                                        "url": p.url,
                                        "title": "عرض في المتجر",
                                    },
                                    {
                                        "type": "postback",
                                        "title": "اطلب الآن",
                                        "payload": f"ORDER_{p.id}",
                                    },
                                ],
                            }
                        )
                    try:
                        await meta_client.send_generic_template(page_token, customer_id, elements)
                    except Exception as exc:
                        log.error("auto_reply.send_template_failed", error=str(exc))

            log.info("auto_reply.sent", conv_id=conv.id, products=len(products))
        except Exception as exc:
            log.error("auto_reply.failed", conv_id=conv.id, error=str(exc))
            try:
                session.add(
                    models.ErrorEvent(
                        org_id=conv.org_id,
                        stage="auto_reply",
                        kind=type(exc).__name__,
                        message=str(exc)[:2000],
                    )
                )
                await session.rollback()
            except Exception:
                pass