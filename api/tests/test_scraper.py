"""Store scraper — product availability / price / shipping extraction.

Uses a local fixture HTML page (no network) so the parsing contract
(price, shipping, stock state, deterministic ids) is locked in.
"""

from __future__ import annotations

import asyncio

import pytest

from api.app.services.store.scraper import search_store, _product_id

FIXTURE_HTML = """<!DOCTYPE html><html><body>
<div class="product-grid">
  <div class="product">
    <h3 class="product-title"><a href="/p/loveer">عطر لوفير</a></h3>
    <div class="product-price">350 ريال</div>
    <span class="product-shipping">الشحن 25 ريال</span>
    <div class="stock">متوفر في المخزون</div>
    <img src="/img/loveer.jpg">
  </div>
  <div class="product">
    <h3 class="product-title"><a href="/p/rose">عطر روز</a></h3>
    <div class="product-price">120 ريال</div>
    <span class="product-shipping">شحن مجاني</span>
    <div class="stock">نفذ من المخزون</div>
    <img src="/img/rose.jpg">
  </div>
</div>
</body></html>"""


@pytest.fixture(scope="module")
def store_server():
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading

    class _H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(FIXTURE_HTML.encode("utf-8"))

        def log_message(self, *args):  # pragma: no cover
            pass

    srv = HTTPServer(("127.0.0.1", 0), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.mark.asyncio
async def test_scraper_extracts_price_shipping_stock(store_server):
    products = await search_store(store_server, "عطر لوفير")

    assert len(products) == 2
    by_name = {p.name: p for p in products}

    loveer = by_name["عطر لوفير"]
    assert loveer.price == 350.0
    assert loveer.shipping_price == 25.0
    assert loveer.in_stock is True
    assert loveer.url == f"{store_server}/p/loveer"

    rose = by_name["عطر روز"]
    assert rose.price == 120.0
    assert rose.shipping_price == 0.0  # شحن مجاني
    assert rose.in_stock is False  # نفذ من المخزون


def test_product_id_is_deterministic():
    a = _product_id("عطر", "/p/1")
    b = _product_id("عطر", "/p/1")
    assert a == b
    assert _product_id("عطر", "/p/1") != _product_id("عطر", "/p/2")


@pytest.mark.asyncio
async def test_scraper_empty_store_url_returns_nothing():
    assert await search_store("", "عطر") == []