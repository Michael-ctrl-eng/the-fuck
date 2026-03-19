import asyncio
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper to run async code in Celery synchronous tasks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=2)
def run_crawl_pipeline(self, job_id: str, tenant_id: str, url: str, depth: int = 3):
    """Full crawl pipeline: crawl -> extract products -> build knowledge index."""
    _run_async(_crawl_pipeline_async(job_id, tenant_id, url, depth))


async def _crawl_pipeline_async(job_id: str, tenant_id: str, url: str, depth: int):
    from app.database import async_session
    from app.models.crawl_job import CrawlJob
    from app.knowledge.crawler import crawl_website
    from app.knowledge.indexer import build_knowledge_index

    async with async_session() as db:
        # Get job
        job = await db.get(CrawlJob, uuid.UUID(job_id))
        if not job:
            return

        try:
            # Update status
            job.status = "crawling"
            job.started_at = datetime.utcnow()
            await db.commit()

            # Crawl website
            pages = await crawl_website(url, depth)
            job.pages_found = len(pages)
            await db.commit()

            if not pages:
                job.status = "failed"
                job.error_message = "No pages found to crawl"
                job.completed_at = datetime.utcnow()
                await db.commit()
                return

            # Extract products from crawled content
            job.status = "indexing"
            await db.commit()

            products_count = await _extract_and_save_products(
                db, uuid.UUID(tenant_id), pages
            )
            job.products_extracted = products_count

            # Build knowledge index
            await build_knowledge_index(db, uuid.UUID(tenant_id), pages)

            job.status = "completed"
            job.completed_at = datetime.utcnow()
            await db.commit()

            logger.info(
                f"Crawl completed for {url}: "
                f"{len(pages)} pages, {products_count} products"
            )

        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)[:500]
            job.completed_at = datetime.utcnow()
            await db.commit()
            logger.error(f"Crawl pipeline failed: {e}", exc_info=True)


async def _extract_and_save_products(db, tenant_id: uuid.UUID, pages: list[dict]) -> int:
    """Use LLM to extract product data from crawled pages."""
    from app.ai.llm_client import chat_completion
    from app.services.product_service import create_product
    import json
    import re

    all_content = "\n\n---\n\n".join(
        f"Page: {p.get('title', p.get('url', ''))}\n{p.get('content', '')[:2000]}"
        for p in pages[:20]
    )

    prompt = f"""Extract all products from this website content.

For each product, extract:
- "name" (required): product name
- "price" (required): numeric price (just the number, no currency symbol)
- Any other relevant attributes you find (description, category, color, size, weight, brand, material, flavor, specs, etc.)

Return as a JSON array. Include ALL attributes you can find for each product.

Example outputs:
[{{"name": "Cotton Saree", "price": 1500, "description": "Premium quality", "category": "Clothing", "material": "cotton", "color": "white"}}]
[{{"name": "Samsung A15", "price": 18000, "brand": "Samsung", "RAM": "6GB", "storage": "128GB"}}]
[{{"name": "Chocolate Cake", "price": 850, "weight": "1kg", "flavor": "dark chocolate"}}]

If no products found, return an empty array [].

Website content:
{all_content[:6000]}"""

    try:
        response = await chat_completion(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=3000,
        )

        # Parse JSON from response
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if not json_match:
            return 0

        products = json.loads(json_match.group())
        count = 0
        base_url = pages[0].get("url", "") if pages else ""

        for i, p in enumerate(products):
            try:
                price = Decimal(str(p.get("price", 0)))
                if price <= 0:
                    continue

                name = p.pop("name", "Unknown Product")
                p.pop("price", None)
                # Everything else becomes attributes
                attributes = {k: v for k, v in p.items() if v is not None}

                # Unique source_ref per product to avoid constraint violations
                source_ref = f"{base_url}#product-{i}"

                await create_product(
                    db,
                    tenant_id,
                    name=name,
                    price=price,
                    source="crawl",
                    source_ref=source_ref,
                    attributes=attributes if attributes else None,
                )
                await db.commit()
                count += 1
                logger.info(f"Saved product: {name} ৳{price}")
            except Exception as e:
                await db.rollback()
                logger.warning(f"Skipped product '{p.get('name', '?')}': {e}")

        return count

    except Exception as e:
        logger.error(f"Product extraction failed: {e}")
        return 0
