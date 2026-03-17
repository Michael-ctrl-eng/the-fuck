from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.language import detect_language
from app.ai.llm_client import chat_completion
from app.ai.order_collector import clean_response_for_customer, extract_order_from_response
from app.ai.prompts import get_product_context, get_system_prompt
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.message import Message
from app.models.tenant import Tenant
from app.services.product_service import get_all_products_for_context

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 15


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

    # 5. Get product catalog
    products = await get_all_products_for_context(db, tenant.id)
    products_context = get_product_context(products)

    # 6. Detect language
    lang = detect_language(message_text)

    # 7. Build system prompt
    system_prompt = get_system_prompt(
        business_name=tenant.page_name,
        products_context=products_context,
        language_hint=lang,
    )

    # 8. Build messages for LLM
    llm_messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        role = "user" if msg.role == "customer" else "assistant"
        llm_messages.append({"role": role, "content": msg.content})
    llm_messages.append({"role": "user", "content": message_text})

    # 9. Call LLM
    try:
        raw_response = await chat_completion(llm_messages)
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raw_response = _get_fallback_response(lang)

    # 10. Check for order data in response
    order_data = extract_order_from_response(raw_response)
    if order_data:
        await _create_order_from_data(db, tenant, customer, conversation, order_data, products)
        conversation.status = "order_placed"

    # 11. Clean response (remove JSON blocks)
    clean_reply = clean_response_for_customer(raw_response)

    # 12. Save assistant message
    assistant_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role="assistant",
        content=clean_reply,
    )
    db.add(assistant_msg)

    # 13. Update conversation timestamp
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
    result = await db.execute(
        select(Conversation).where(
            Conversation.tenant_id == tenant_id,
            Conversation.customer_id == customer_id,
            Conversation.status == "active",
        )
    )
    conversation = result.scalar_one_or_none()

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
    products: list[dict],
) -> None:
    """Create an order from extracted AI data."""
    from app.services.order_service import create_order
    from app.services.notification_service import notify_new_order

    # Find matching product for price
    product_name = order_data["product_name"]
    matching_product = None
    for p in products:
        if p["name"].lower() in product_name.lower() or product_name.lower() in p["name"].lower():
            matching_product = p
            break

    unit_price = matching_product["discount_price"] or matching_product["price"] if matching_product else 0
    quantity = order_data.get("quantity", 1)

    items = [
        {
            "product_id": matching_product["id"] if matching_product else None,
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
        )
        logger.info(f"Order {order.order_number} created for tenant {tenant.page_name}")

        # Send notification (best effort)
        try:
            await notify_new_order(tenant, order)
        except Exception as e:
            logger.error(f"Failed to notify order: {e}")

    except Exception as e:
        logger.error(f"Failed to create order: {e}")


def _get_fallback_response(language: str) -> str:
    """Fallback response when LLM is unavailable."""
    if language == "bangla":
        return "দুঃখিত, এই মুহূর্তে আমি উত্তর দিতে পারছি না। অনুগ্রহ করে একটু পরে আবার চেষ্টা করুন। 🙏"
    elif language == "banglish":
        return "Sorry, ekhon reply dite parchi na. Please aktu pore abar try korun. 🙏"
    else:
        return "Sorry, I'm unable to respond at the moment. Please try again shortly. 🙏"
