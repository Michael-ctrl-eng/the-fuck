import httpx

from app.config import get_settings

settings = get_settings()


async def send_text_message(page_access_token: str, recipient_id: str, text: str) -> dict:
    """Send a text message via Facebook Messenger."""
    url = f"{settings.FB_GRAPH_API_URL}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            json=payload,
            params={"access_token": page_access_token},
            timeout=10.0,
        )
        return resp.json()


async def send_quick_replies(
    page_access_token: str,
    recipient_id: str,
    text: str,
    options: list[str],
) -> dict:
    """Send a message with quick reply buttons."""
    url = f"{settings.FB_GRAPH_API_URL}/me/messages"
    quick_replies = [
        {"content_type": "text", "title": opt, "payload": opt} for opt in options[:13]
    ]
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text, "quick_replies": quick_replies},
        "messaging_type": "RESPONSE",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            json=payload,
            params={"access_token": page_access_token},
            timeout=10.0,
        )
        return resp.json()


async def get_user_profile(page_access_token: str, psid: str) -> dict:
    """Get user profile info from Facebook."""
    url = f"{settings.FB_GRAPH_API_URL}/{psid}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            params={
                "access_token": page_access_token,
                "fields": "first_name,last_name,profile_pic",
            },
            timeout=10.0,
        )
        if resp.status_code == 200:
            return resp.json()
        return {}
