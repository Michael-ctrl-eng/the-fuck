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
) -> str:
    """Process a customer message and return the AI response."""

    # 1. Get or create customer
    customer = await _get_or_create_customer(
        db, tenant.id, sender_psid, customer_name
    )

    # 2. Get or create active conversation
    conversation = await _get_or_create_conversation(db, tenant.id, customer.id)

    # 3. Save customer message
    customer_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role="customer",
        content=message_text,
        fb_message_id=fb_message_id,
    )
    db.add(customer_msg)

    # 4. Load conversation history
    history = await _load_conversation_history(db, conversation.id)

    # 5. Retrieve relevant products + knowledge from PageIndex tree
    # LLM reads tree TOC → picks relevant nodes → fetches content
    # Handles Bangla, Banglish, English, typos, synonyms
    # Cost: ~50 tokens for TOC navigation
    products_context, knowledge_context = await retrieve_context(
        db, tenant.id, message_text, max_nodes=3
    )

    # 6. Detect language
    lang = detect_language(message_text)

    # 7. Build system prompt with tenant's delivery + payment settings
    system_prompt = get_system_prompt(
        business_name=tenant.page_name,
        products_context=products_context,
        knowledge_context=knowledge_context,
        language_hint=lang,
        delivery_inside=float(tenant.delivery_inside_dhaka or 80),
        delivery_outside=float(tenant.delivery_outside_dhaka or 150),
        free_delivery_above=float(tenant.free_delivery_above) if tenant.free_delivery_above else None,
        mfs_numbers=tenant.mfs_numbers,
    )

    # 9. Build messages for LLM
    llm_messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        role = "user" if msg.role == "customer" else "assistant"
        llm_messages.append({"role": role, "content": msg.content})
    llm_messages.append({"role": "user", "content": message_text})

    # 10. Call LLM
    token_info = None
    try:
        llm_result = await chat_completion_with_usage(llm_messages)
        raw_response = llm_result.content
        token_info = llm_result
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raw_response = _get_fallback_response(lang)

    # 11. Check for order data in response
    order_data = extract_order_from_response(raw_response)
    if order_data:
        await _create_order_from_data(db, tenant, customer, conversation, order_data)
        conversation.status = "order_placed"

    # 12. Clean response (remove JSON blocks)
    clean_reply = clean_response_for_customer(raw_response)

    # 13. Save assistant message
    assistant_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role="assistant",
        content=clean_reply,
    )
    db.add(assistant_msg)

    # 14. Track token usage
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

    # 15. Update conversation timestamp
    conversation.last_message_at = datetime.utcnow()
    await db.flush()

    return clean_reply


async def _get_or_create_customer(
    db: AsyncSession, tenant_id: uuid.UUID, psid: str, name: str | None = None
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
            name=name or "Customer",
        )
        db.add(customer)
        await db.flush()

    return customer


async def _get_or_create_conversation(
    db: AsyncSession, tenant_id: uuid.UUID, customer_id: uuid.UUID
) -> Conversation:
    # One conversation per customer per business — always reuse existing
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
        # Reactivate if it was closed
        if conversation.status != "active":
            conversation.status = "active"
        return conversation

    if not conversation:
        conversation = Conversation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            customer_id=customer_id,
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
    messages.reverse()  # Oldest first
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

    # Find matching product in DB for price
    product_name = order_data["product_name"]
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
    quantity = order_data.get("quantity", 1)

    items = [
        {
            "product_id": str(matching.id) if matching else None,
            "product_name": product_name,
            "quantity": quantity,
            "unit_price": unit_price,
        }
    ]

    # Update customer details
    customer.name = order_data.get("customer_name", customer.name)
    customer.phone = order_data.get("customer_phone")
    customer.division = order_data.get("division")
    customer.district = order_data.get("district")
    customer.upazila = order_data.get("upazila")
    customer.address_detail = order_data.get("address_detail")

    try:
        order = await create_order(
            db=db,
            tenant_id=tenant.id,
            customer_id=customer.id,
            conversation_id=conversation.id,
            customer_name=order_data["customer_name"],
            customer_phone=order_data["customer_phone"],
            division=order_data["division"],
            district=order_data["district"],
            upazila=order_data.get("upazila"),
            address_detail=order_data["address_detail"],
            payment_method=order_data.get("payment_method", "cod"),
            items=items,
            delivery_charge=_calc_delivery(tenant, order_data.get("division", ""), items, matching),
        )
        logger.info(f"Order {order.order_number} created for tenant {tenant.page_name}")

        # Send notification (best effort)
        try:
            await notify_new_order(tenant, order)
        except Exception as e:
            logger.error(f"Failed to notify order: {e}")

    except Exception as e:
        logger.error(f"Failed to create order: {e}")


def _calc_delivery(tenant: Tenant, division: str, items: list[dict], product=None) -> Decimal:
    """Calculate delivery charge from tenant settings + product overrides."""
    from decimal import Decimal

    # Check product-level override
    if product and product.attributes:
        prod_delivery = product.attributes.get("delivery_charge")
        if prod_delivery is not None:
            return Decimal(str(prod_delivery))
        if product.attributes.get("free_delivery"):
            return Decimal("0")

    # Calculate subtotal for free delivery check
    subtotal = sum(Decimal(str(i.get("unit_price", 0))) * i.get("quantity", 1) for i in items)
    if tenant.free_delivery_above and subtotal >= tenant.free_delivery_above:
        return Decimal("0")

    # Zone-based from tenant settings
    is_dhaka = division.lower() in ("dhaka", "ঢাকা")
    if is_dhaka:
        return Decimal(str(tenant.delivery_inside_dhaka or 80))
    return Decimal(str(tenant.delivery_outside_dhaka or 150))


def _get_fallback_response(language: str) -> str:
    """Fallback response when LLM is unavailable."""
    if language == "bangla":
        return "দুঃখিত, এই মুহূর্তে আমি উত্তর দিতে পারছি না। অনুগ্রহ করে একটু পরে আবার চেষ্টা করুন। 🙏"
    elif language == "banglish":
        return "Sorry, ekhon reply dite parchi na. Please aktu pore abar try korun. 🙏"
    else:
        return "Sorry, I'm unable to respond at the moment. Please try again shortly. 🙏"
