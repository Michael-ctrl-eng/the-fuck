import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.tenant import Tenant
from app.schemas.webhook import TestChatRequest, TestChatResponse
from sqlalchemy import select

router = APIRouter(prefix="/api/test", tags=["Testing"])


@router.post("/chat", response_model=TestChatResponse)
async def test_chat(
    req: TestChatRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Simulate a customer message for local testing without Facebook.

    This endpoint mimics the Messenger webhook flow but works locally.
    Use it to test the AI sales agent without connecting to Facebook.
    """
    result = await db.execute(
        select(Tenant).where(
            Tenant.id == uuid.UUID(req.tenant_id),
            Tenant.owner_id == user.id,
        )
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Use a test PSID
    test_psid = f"test_{user.id}"

    from app.ai.agent import process_customer_message

    reply = await process_customer_message(
        db=db,
        tenant=tenant,
        sender_psid=test_psid,
        message_text=req.message,
        customer_name=req.customer_name,
    )

    # Get conversation and customer IDs for response
    from app.models.customer import Customer
    from app.models.conversation import Conversation

    cust_result = await db.execute(
        select(Customer).where(
            Customer.tenant_id == tenant.id,
            Customer.fb_psid == test_psid,
        )
    )
    customer = cust_result.scalar_one_or_none()

    conv_result = await db.execute(
        select(Conversation)
        .where(
            Conversation.tenant_id == tenant.id,
            Conversation.customer_id == customer.id,
        )
        .order_by(Conversation.last_message_at.desc())
        .limit(1)
    )
    conversation = conv_result.scalar_one_or_none()

    return TestChatResponse(
        reply=reply,
        conversation_id=str(conversation.id) if conversation else "",
        customer_id=str(customer.id) if customer else "",
    )
