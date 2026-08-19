from __future__ import annotations

import hashlib
import re

import httpx
import structlog
from bs4 import BeautifulSoup
from pydantic import BaseModel

from ...config import Settings, get_settings

log = structlog.get_logger("raqib.store.scraper")

SEARCH_PATTERNS = [
    "/search?q={q}",
    "/search?term={q}",
    "/search?type=product&q={q}",
    "/?s={q}",
]

OUT_OF_STOCK_MARKERS = ("نفذ", "غير متوفر", "نفذت", "غير متاح", "out of stock", "sold out", "انتهى")
IN_STOCK_MARKERS = ("متوفر", "متاح", "في المخزون", "in stock", "أضف للسلة", "أضف إلى السلة", "اشترِ", "اشتري")


class StoreProduct(BaseModel):
    id: str
    name: str
    price: float
    shipping_price: float = 0.0
    stock_count: int = -1
    in_stock: bool = True
    image_url: str = ""
    url: str = ""


def _product_id(name: str, url: str) -> str:
    return hashlib.md5(f"{name}|{url}".encode("utf-8")).hexdigest()[:16]


def _parse_price(text: str) -> float | None:
    if not text:
        return None
    m = re.search(r"(\d+(?:[.,]\d{1,2})?)", text.replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _parse_product(item, base_url: str, seen: set[str]) -> StoreProduct | None:
    title_el = item.find(["h2", "h3", "h4"], class_=re.compile(r"title|name", re.I))
    if not title_el:
        title_el = item.find(["h2", "h3", "h4"])
    if not title_el:
        title_el = item.find("a", title=True)
    title = title_el.get_text(strip=True) if title_el else ""
    if not title:
        return None

    a_el = item.find("a", href=True)
    link = a_el["href"] if a_el else ""
    if link and not link.startswith("http"):
        link = f"{base_url}{link}" if link.startswith("/") else f"{base_url}/{link}"
    if not link:
        return None
    if link in seen:
        return None
    seen.add(link)

    price_el = item.find(class_=re.compile(r"price|amount", re.I))
    price_text = price_el.get_text(strip=True) if price_el else ""
    prices = [_parse_price(t) for t in re.findall(r"\d+(?:[.,]\d{1,2})?", price_text)]
    prices = [p for p in prices if p is not None]
    price = prices[0] if prices else 0.0
    sale_price = prices[1] if len(prices) > 1 else None

    img_el = item.find("img")
    img_url = ""
    if img_el:
        img_url = img_el.get("src") or img_el.get("data-src") or img_el.get("data-lazy-src") or ""

    stock_text = item.get_text(" ", strip=True).lower()
    in_stock = not any(m in stock_text for m in OUT_OF_STOCK_MARKERS)
    if in_stock:
        in_stock = any(m in stock_text for m in IN_STOCK_MARKERS) or True

    shipping_price = 0.0
    ship_el = item.find(class_=re.compile(r"shipping|delivery|شحن|توصيل", re.I))
    if ship_el:
        ship_text = ship_el.get_text(strip=True)
        if "مجان" in ship_text:
            shipping_price = 0.0
        else:
            sp = _parse_price(ship_text)
            if sp is not None and sp != price:
                shipping_price = sp

    return StoreProduct(
        id=_product_id(title, link),
        name=title,
        price=sale_price if sale_price is not None and sale_price < price else price,
        shipping_price=shipping_price,
        in_stock=in_stock,
        image_url=img_url,
        url=link,
    )


async def search_store(store_url: str, query: str, timeout: float | None = None) -> list[StoreProduct]:
    """Search a store via heuristic web scraping (salla / zid / shopify / woo).

    Returns up to 5 matching products with price, shipping price and stock state.
    """
    if not store_url:
        return []
    if timeout is None:
        try:
            timeout = get_settings().store_search_timeout
        except Exception:
            timeout = 15.0

    base_url = store_url.rstrip("/")
    q = query.strip()
    if not q:
        return []

    products: list[StoreProduct] = []
    seen: set[str] = set()
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
        for pattern in SEARCH_PATTERNS:
            url = f"{base_url}{pattern.format(q=q)}"
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")

                # Match the class token "product" exactly (not containers
                # like "product-grid" or "products-list") to avoid grabbing
                # the whole grid and misreading stock state.
                items = soup.find_all(class_=re.compile(r"(^|\s)product($|\s)", re.I))
                if not items:
                    items = soup.find_all(class_=re.compile(r"(^|\s)(item|card)($|\s)", re.I))
                if not items:
                    continue

                for item in items[:8]:
                    product = _parse_product(item, base_url, seen)
                    if product and product.name:
                        products.append(product)
                if products:
                    break  # found products in this search structure
            except Exception as exc:
                log.warning("scraper.search_failed", url=url, error=str(exc))

    return products[:5]