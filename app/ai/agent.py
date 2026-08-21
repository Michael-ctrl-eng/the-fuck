from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.language import detect_language
from app.ai.llm_client import chat_completion_with_usage
from app.ai.order_collector import clean_response_for_customer, extract_order_from_response
from app.ai.prompts import get_system_prompt
from app.knowledge.retriever import retrieve_context
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.message import Message
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 10


async def process_customer_message(
    db: AsyncSession,
    tenant: Tenant,
    sender_psid: str,
    message_text: str,
    fb_message_id: str | None = None,
    customer_name: str | None = None,
    channel: str = "messenger",
    media_urls: list[str] | None = None,
    audio_urls: list[str] | None = None,
) -> str:
    """Process a customer message and return the AI response.

    channel: 'messenger' | 'instagram' | 'whatsapp'
    media_urls: image/video URLs from the message
    audio_urls: voice note URLs to transcribe
    """

    # 0. Transcribe voice notes if present
    if audio_urls:
        transcribed = await _transcribe_audio(audio_urls)
        if transcribed:
            message_text = transcribed

    # 0.5. Analyze product images if present
    vision_results = []
    if media_urls:
        vision_results = await _analyze_images(media_urls, tenant)
        if vision_results and not message_text.strip():
            # Customer sent only an image — ask what they need
            names = ", ".join(v.product_name for v in vision_results if v.product_name)
            message_text = f"إيه المنتج ده؟ {names}" if names else "عايز أعرف عن المنتج ده"

    # 1. Get or create customer
    customer = await _get_or_create_customer(
        db, tenant.id, sender_psid, customer_name, channel
    )

    # 2. Get or create active conversation
    conversation = await _get_or_create_conversation(db, tenant.id, customer.id, channel)

    # 3. Save customer message
    customer_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role="customer",
        content=message_text,
        fb_message_id=fb_message_id,
        channel=channel,
        media_urls=media_urls or [],
    )
    db.add(customer_msg)

    # 4. Load conversation history
    history = await _load_conversation_history(db, conversation.id)

    # 5. Retrieve relevant products + knowledge
    products_context, knowledge_context = await retrieve_context(
        db, tenant.id, message_text, max_nodes=3
    )

    # 6. Detect language
    lang = detect_language(message_text)

    # 7. Build system prompt with tenant settings + per-page personality
    style_profile = tenant.style_profile or {}
    system_prompt = get_system_prompt(
        business_name=tenant.page_name,
        products_context=products_context,
        knowledge_context=knowledge_context,
        language_hint=lang,
        delivery_inside_cairo=float(tenant.delivery_inside_cairo or 35),
        delivery_outside_cairo=float(tenant.delivery_outside_cairo or 60),
        free_delivery_above=float(tenant.free_delivery_above) if tenant.free_delivery_above else None,
        payment_methods=tenant.payment_methods,
        style_profile=style_profile,
    )

    # 8. Build messages for LLM
    llm_messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        role = "user" if msg.role == "customer" else "assistant"
        llm_messages.append({"role": role, "content": msg.content})

    # Add image context if present
    user_content = message_text
    if media_urls:
        if vision_results:
            vision_text = "\n".join(
                f"- صورة: {v.product_name} ({v.category}) {v.color} — {v.details}"
                for v in vision_results if v.product_name
            )
            user_content += f"\n\n[العميل بعت صور. تحليل الصور:]\n{vision_text}"
        else:
            user_content += f"\n\n[العميل بعت صور: {', '.join(media_urls[:3])}]"

    llm_messages.append({"role": "user", "content": user_content})

    # 9. Call LLM
    token_info = None
    try:
        llm_result = await chat_completion_with_usage(llm_messages)
        raw_response = llm_result.content
        token_info = llm_result
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raw_response = _get_fallback_response(lang)

    # 10. Check for order data in response
    order_data = extract_order_from_response(raw_response)
    if order_data:
        await _create_order_from_data(db, tenant, customer, conversation, order_data)
        conversation.status = "order_placed"

    # 11. Clean response
    clean_reply = clean_response_for_customer(raw_response)

    # 12. Save assistant message
    assistant_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role="assistant",
        content=clean_reply,
        channel=channel,
    )
    db.add(assistant_msg)

    # 13. Track token usage
    if token_info:
        from app.models.token_usage import TokenUsage
        usage = TokenUsage(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            usage_type="chat",
            model=token_info.model,
            prompt_tokens=token_info.prompt_tokens,
            completion_tokens=token_info.completion_tokens,
            total_tokens=token_info.total_tokens,
        )
        db.add(usage)

    # 14. Update conversation timestamp
    conversation.last_message_at = datetime.utcnow()
    await db.flush()

    return clean_reply


async def _transcribe_audio(audio_urls: list[str]) -> str | None:
    """Transcribe voice notes using faster-whisper (local, free)."""
    try:
        from app.services.transcription import transcribe_url
        for url in audio_urls[:1]:
            text = await transcribe_url(url)
            if text:
                return text
    except Exception as e:
        logger.warning(f"Voice transcription failed: {e}")
    return None


async def _analyze_images(media_urls: list[str], tenant: Tenant) -> list:
    """Analyze product images using Gemini Vision (free)."""
    from app.config import get_settings
    from app.services.vision import analyze_product_image

    settings = get_settings()
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        return []

    results = []
    for url in media_urls[:3]:
        try:
            result = await analyze_product_image(url, api_key)
            if result:
                results.append(result)
        except Exception as e:
            logger.warning(f"Vision analysis failed for {url}: {e}")
    return results


async def _get_or_create_customer(
    db: AsyncSession, tenant_id: uuid.UUID, psid: str, name: str | None = None,
    channel: str = "messenger",
) -> Customer:
    result = await db.execute(
        select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.fb_psid == psid,
        )
    )
    customer = result.scalar_one_or_none()

    if not customer:
        customer = Customer(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            fb_psid=psid,
            name=name or "عميل",
            channel=channel,
        )
        db.add(customer)
        await db.flush()

    return customer


async def _get_or_create_conversation(
    db: AsyncSession, tenant_id: uuid.UUID, customer_id: uuid.UUID,
    channel: str = "messenger",
) -> Conversation:
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.tenant_id == tenant_id,
            Conversation.customer_id == customer_id,
        )
        .order_by(Conversation.started_at.desc())
        .limit(1)
    )
    conversation = result.scalar_one_or_none()

    if conversation:
        if conversation.status != "active":
            conversation.status = "active"
        return conversation

    if not conversation:
        conversation = Conversation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            customer_id=customer_id,
            channel=channel,
        )
        db.add(conversation)
        await db.flush()

    return conversation


async def _load_conversation_history(
    db: AsyncSession, conversation_id: uuid.UUID
) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(MAX_HISTORY_MESSAGES)
    )
    messages = list(result.scalars().all())
    messages.reverse()
    return messages


async def _create_order_from_data(
    db: AsyncSession,
    tenant: Tenant,
    customer: Customer,
    conversation: Conversation,
    order_data: dict,
) -> None:
    """Create an order from extracted AI data."""
    from app.services.order_service import create_order
    from app.services.notification_service import notify_new_order
    from app.models.product import Product

    order_items = order_data.get("items", [])
    items = []
    for item in order_items:
        product_name = item["product_name"]
        quantity = item.get("quantity", 1)

        result = await db.execute(
            select(Product).where(
                Product.tenant_id == tenant.id,
                Product.is_active == True,
                Product.name.ilike(f"%{product_name}%"),
            ).limit(1)
        )
        matching = result.scalar_one_or_none()

        if matching:
            attrs = matching.attributes or {}
            unit_price = attrs.get("discount_price") or matching.price
        else:
            unit_price = 0

        items.append({
            "product_id": str(matching.id) if matching else None,
            "product_name": product_name,
            "quantity": quantity,
            "unit_price": unit_price,
        })

    if not items:
        logger.warning("No items in order data")
        return

    # Update customer details
    customer.name = order_data.get("customer_name", customer.name)
    customer.phone = order_data.get("customer_phone")
    customer.governorate = order_data.get("governorate")
    customer.city = order_data.get("city")
    customer.area = order_data.get("area")
    customer.address_detail = order_data.get("address_detail")

    first_product = None
    if items[0].get("product_id"):
        first_product = await db.get(Product, uuid.UUID(items[0]["product_id"]))

    try:
        order = await create_order(
            db=db,
            tenant_id=tenant.id,
            customer_id=customer.id,
            conversation_id=conversation.id,
            customer_name=order_data["customer_name"],
            customer_phone=order_data["customer_phone"],
            governorate=order_data.get("governorate", ""),
            city=order_data.get("city", ""),
            area=order_data.get("area"),
            address_detail=order_data["address_detail"],
            payment_method=order_data.get("payment_method", "cod"),
            items=items,
            delivery_charge=_calc_delivery(tenant, order_data.get("governorate", ""), items, first_product),
        )

        logger.info(f"Order {order.order_number} created: {len(items)} items")

        try:
            await notify_new_order(tenant, order)
        except Exception as e:
            logger.error(f"Failed to notify order: {e}")

    except Exception as e:
        logger.error(f"Failed to create order: {e}")


def _calc_delivery(tenant: Tenant, governorate: str, items: list[dict], product=None):
    """Calculate delivery charge for Egyptian governorates."""
    from decimal import Decimal

    if product and product.attributes:
        prod_delivery = product.attributes.get("delivery_charge")
        if prod_delivery is not None:
            return Decimal(str(prod_delivery))
        if product.attributes.get("free_delivery"):
            return Decimal("0")

    subtotal = sum(Decimal(str(i.get("unit_price", 0))) * i.get("quantity", 1) for i in items)
    if tenant.free_delivery_above and subtotal >= tenant.free_delivery_above:
        return Decimal("0")

    # Cairo/Giza = inside, rest = outside
    is_cairo = governorate.lower() in ("cairo", "giza", "القاهرة", "الجيزة")
    if is_cairo:
        return Decimal(str(tenant.delivery_inside_cairo or 35))
    return Decimal(str(tenant.delivery_outside_cairo or 60))


def _get_fallback_response(language: str) -> str:
    """Fallback response when LLM is unavailable."""
    if language == "arabic":
        return "لو سمحت، مقدرش أرد دلوقتي. جرب تاني بعد شوية. 🙏"
    elif language == "arabizi":
        return "Sorry, msh a2dar arud dilwaqti. Try tani ba3d shwaya. 🙏"
    else:
        return "Sorry, I'm unable to respond at the moment. Please try again shortly. 🙏"
