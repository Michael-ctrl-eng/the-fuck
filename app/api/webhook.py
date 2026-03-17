import logging

from fastapi import APIRouter, BackgroundTasks, Request, Response
from sqlalchemy import select

from app.config import get_settings
from app.database import async_session
from app.models.tenant import Tenant
from app.utils.security import verify_fb_signature

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhook", tags=["Webhook"])


@router.get("/messenger")
async def verify_webhook(request: Request):
    """Facebook webhook verification challenge."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.FB_VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return Response(content=challenge, media_type="text/plain")

    logger.warning("Webhook verification failed")
    return Response(content="Forbidden", status_code=403)


@router.post("/messenger")
async def receive_messenger_event(
    request: Request, background_tasks: BackgroundTasks
):
    """Receive and process Messenger webhook events."""
    body = await request.body()

    # Verify signature (skip in debug mode for testing)
    if not settings.APP_DEBUG:
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not verify_fb_signature(body, signature):
            return Response(content="Invalid signature", status_code=403)

    data = await request.json()

    if data.get("object") != "page":
        return Response(content="Not a page event", status_code=404)

    # Process each entry in background (must respond 200 within 5s)
    for entry in data.get("entry", []):
        page_id = entry.get("id")
        for messaging_event in entry.get("messaging", []):
            background_tasks.add_task(
                _process_message, page_id, messaging_event
            )

    return Response(content="EVENT_RECEIVED", status_code=200)


async def _process_message(page_id: str, event: dict):
    """Process a single messaging event in the background."""
    sender_id = event.get("sender", {}).get("id")
    message = event.get("message", {})
    message_text = message.get("text")

    if not sender_id or not message_text:
        return

    try:
        async with async_session() as db:
            # Find tenant by page ID
            result = await db.execute(
                select(Tenant).where(Tenant.fb_page_id == page_id)
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                logger.warning(f"No tenant found for page {page_id}")
                return

            # Process through AI agent
            from app.ai.agent import process_customer_message

            reply = await process_customer_message(
                db=db,
                tenant=tenant,
                sender_psid=sender_id,
                message_text=message_text,
                fb_message_id=message.get("mid"),
            )

            # Send reply via Messenger
            from app.services.messenger_service import send_text_message

            await send_text_message(tenant.page_access_token, sender_id, reply)
            await db.commit()

    except Exception as e:
        logger.error(f"Error processing message from {sender_id}: {e}", exc_info=True)
