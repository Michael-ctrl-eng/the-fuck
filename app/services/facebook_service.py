import httpx

from app.config import get_settings

settings = get_settings()


async def get_user_pages(user_access_token: str) -> list[dict]:
    """Get list of Facebook pages managed by user."""
    url = f"{settings.FB_GRAPH_API_URL}/me/accounts"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            params={"access_token": user_access_token, "fields": "id,name,access_token"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            return resp.json().get("data", [])
        return []


async def subscribe_page_to_webhook(page_id: str, page_access_token: str) -> bool:
    """Subscribe a page to receive webhook events."""
    url = f"{settings.FB_GRAPH_API_URL}/{page_id}/subscribed_apps"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            params={"access_token": page_access_token},
            json={"subscribed_fields": ["messages", "messaging_postbacks"]},
            timeout=10.0,
        )
        return resp.status_code == 200


async def get_page_products(page_id: str, page_access_token: str) -> list[dict]:
    """Fetch products from Facebook page's product catalog."""
    # First get the product catalog ID
    url = f"{settings.FB_GRAPH_API_URL}/{page_id}/product_catalogs"
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            url,
            params={"access_token": page_access_token},
            timeout=10.0,
        )
        if resp.status_code != 200:
            return []

        catalogs = resp.json().get("data", [])
        if not catalogs:
            return []

        # Get products from first catalog
        catalog_id = catalogs[0]["id"]
        products_url = f"{settings.FB_GRAPH_API_URL}/{catalog_id}/products"
        resp = await client.get(
            products_url,
            params={
                "access_token": page_access_token,
                "fields": "id,name,description,price,image_url,availability",
            },
            timeout=10.0,
        )
        if resp.status_code == 200:
            return resp.json().get("data", [])
        return []
