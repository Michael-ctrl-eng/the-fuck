import logging
import hashlib
import hmac

from fastapi import APIRouter, BackgroundTasks, Request, Response
from sqlalchemy import select

from app.config import get_settings
from app.database import async_session
from app.models.tenant import Tenant
from app.utils.security import verify_fb_signature

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhook", tags=["Webhook"])


# --------------------------------------------------------------------------
# Facebook Messenger
# --------------------------------------------------------------------------

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

    if not settings.APP_DEBUG:
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not verify_fb_signature(body, signature):
            return Response(content="Invalid signature", status_code=403)

    data = await request.json()

    if data.get("object") != "page":
        return Response(content="Not a page event", status_code=404)

    for entry in data.get("entry", []):
        page_id = entry.get("id")
        for messaging_event in entry.get("messaging", []):
            background_tasks.add_task(
                _process_messenger_message, page_id, messaging_event
            )

    return Response(content="EVENT_RECEIVED", status_code=200)


async def _process_messenger_message(page_id: str, event: dict):
    """Process a single Messenger messaging event in the background."""
    sender_id = event.get("sender", {}).get("id")
    message = event.get("message", {})
    message_text = message.get("text", "")

    # Handle attachments (images, audio)
    media_urls = []
    audio_urls = []
    for att in message.get("attachments", []):
        att_type = att.get("type", "")
        url = att.get("payload", {}).get("url", "")
        if att_type == "image":
            media_urls.append(url)
        elif att_type == "audio":
            audio_urls.append(url)

    if not sender_id:
        return

    if not message_text and not media_urls and not audio_urls:
        return

    try:
        async with async_session() as db:
            result = await db.execute(
                select(Tenant).where(Tenant.fb_page_id == page_id)
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                logger.warning(f"No tenant found for page {page_id}")
                return

            from app.ai.agent import process_customer_message

            reply = await process_customer_message(
                db=db,
                tenant=tenant,
                sender_psid=sender_id,
                message_text=message_text or "(صورة)" if media_urls else message_text or "(رسالة صوتية)" if audio_urls else message_text,
                fb_message_id=message.get("mid"),
                channel="messenger",
                media_urls=media_urls,
                audio_urls=audio_urls,
            )

            from app.services.messenger_service import send_text_message
            await send_text_message(tenant.page_access_token, sender_id, reply)
            await db.commit()

    except Exception as e:
        logger.error(f"Error processing Messenger message from {sender_id}: {e}", exc_info=True)


# --------------------------------------------------------------------------
# Instagram DMs
# --------------------------------------------------------------------------

@router.get("/instagram")
async def verify_instagram_webhook(request: Request):
    """Instagram webhook verification (same as Messenger)."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.FB_VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Forbidden", status_code=403)


@router.post("/instagram")
async def receive_instagram_event(
    request: Request, background_tasks: BackgroundTasks
):
    """Receive and process Instagram webhook events."""
    body = await request.body()

    if not settings.APP_DEBUG:
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not verify_fb_signature(body, signature):
            return Response(content="Invalid signature", status_code=403)

    data = await request.json()

    for entry in data.get("entry", []):
        page_id = entry.get("id")
        for messaging_event in entry.get("messaging", []):
            background_tasks.add_task(
                _process_instagram_message, page_id, messaging_event
            )

    return Response(content="EVENT_RECEIVED", status_code=200)


async def _process_instagram_message(page_id: str, event: dict):
    """Process a single Instagram DM event."""
    sender_id = event.get("sender", {}).get("id")
    message = event.get("message", {})
    message_text = message.get("text", "")

    media_urls = []
    audio_urls = []
    for att in message.get("attachments", []):
        att_type = att.get("type", "")
        url = att.get("payload", {}).get("url", "")
        if att_type == "image":
            media_urls.append(url)
        elif att_type == "audio":
            audio_urls.append(url)

    if not sender_id:
        return

    if not message_text and not media_urls and not audio_urls:
        return

    try:
        async with async_session() as db:
            result = await db.execute(
                select(Tenant).where(Tenant.ig_user_id == page_id)
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                # Try fb_page_id fallback (Instagram Business connected to FB page)
                result = await db.execute(
                    select(Tenant).where(Tenant.fb_page_id == page_id)
                )
                tenant = result.scalar_one_or_none()
            if not tenant:
                logger.warning(f"No tenant found for Instagram page {page_id}")
                return

            from app.ai.agent import process_customer_message

            reply = await process_customer_message(
                db=db,
                tenant=tenant,
                sender_psid=sender_id,
                message_text=message_text or "(صورة)" if media_urls else message_text or "(رسالة صوتية)" if audio_urls else message_text,
                fb_message_id=message.get("mid"),
                channel="instagram",
                media_urls=media_urls,
                audio_urls=audio_urls,
            )

            # Send reply via Instagram API (same endpoint as Messenger)
            from app.services.messenger_service import send_text_message
            token = tenant.ig_access_token or tenant.page_access_token
            if token:
                await send_text_message(token, sender_id, reply)
            await db.commit()

    except Exception as e:
        logger.error(f"Error processing Instagram message from {sender_id}: {e}", exc_info=True)


# --------------------------------------------------------------------------
# WhatsApp (via WhatsApp Business API)
# --------------------------------------------------------------------------

@router.post("/whatsapp")
async def receive_whatsapp_event(
    request: Request, background_tasks: BackgroundTasks
):
    """Receive and process WhatsApp Business API webhook events."""
    body = await request.body()

    # Verify signature (WhatsApp uses X-Hub-Signature-256)
    if not settings.APP_DEBUG:
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not _verify_whatsapp_signature(body, signature):
            return Response(content="Invalid signature", status_code=403)

    data = await request.json()

    for entry in data.get("entry", []):
        phone_number_id = entry.get("id")
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            for msg in messages:
                background_tasks.add_task(
                    _process_whatsapp_message, phone_number_id, msg, value.get("contacts", [])
                )

    return Response(content="EVENT_RECEIVED", status_code=200)


async def _process_whatsapp_message(phone_number_id: str, msg: dict, contacts: list):
    """Process a single WhatsApp message."""
    sender_id = msg.get("from", "")
    msg_type = msg.get("type", "")
    message_text = ""
    media_urls = []
    audio_urls = []

    if msg_type == "text":
        message_text = msg.get("text", {}).get("body", "")
    elif msg_type == "image":
        media_urls.append(msg.get("image", {}).get("id", ""))
    elif msg_type == "audio":
        audio_urls.append(msg.get("audio", {}).get("id", ""))
    elif msg_type == "interactive":
        message_text = msg.get("interactive", {}).get("button_reply", {}).get("id", "")

    if not sender_id or not message_text and not media_urls and not audio_urls:
        return

    # Get customer name from contacts
    customer_name = ""
    for c in contacts:
        if c.get("wa_id") == sender_id:
            customer_name = c.get("profile", {}).get("name", "")
            break

    try:
        async with async_session() as db:
            result = await db.execute(
                select(Tenant).where(Tenant.wa_phone_number_id == phone_number_id)
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                logger.warning(f"No tenant found for WhatsApp number {phone_number_id}")
                return

            from app.ai.agent import process_customer_message

            reply = await process_customer_message(
                db=db,
                tenant=tenant,
                sender_psid=sender_id,
                message_text=message_text or "(صورة)" if media_urls else message_text or "(رسالة صوتية)" if audio_urls else message_text,
                fb_message_id=msg.get("id"),
                customer_name=customer_name,
                channel="whatsapp",
                media_urls=media_urls,
                audio_urls=audio_urls,
            )

            # Send reply via WhatsApp Business API
            from app.services.whatsapp_service import send_whatsapp_message
            await send_whatsapp_message(tenant, sender_id, reply)
            await db.commit()

    except Exception as e:
        logger.error(f"Error processing WhatsApp message from {sender_id}: {e}", exc_info=True)


def _verify_whatsapp_signature(body: bytes, signature: str) -> bool:
    """Verify WhatsApp webhook signature."""
    if not signature:
        return False
    expected = hmac.new(
        settings.FB_APP_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
